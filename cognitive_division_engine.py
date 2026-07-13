# -*- coding: utf-8 -*-
"""
认知分工协同推理引擎 (Cognitive Division of Labor Engine)
XuanHub v4.0 Phase 7 — 深度协同推理核心

核心理论贡献：
协同推理的增益不来自"多模型ensemble的统计降噪"，而来自
"在信息受限条件下被迫完成的认知过程"——任何单体Agent（即使拿到完整信息）
都无法独立达到的推理深度。

核心组件：
- PerspectiveDecomposer: 视角分解器（6种分解策略 + bridgeability评估）
- CommunicationLayer: 有损通信层（Round 0/1/2 协议，严格只传递IntermediateConclusion）
- FusionJudge: 融合判断器（4类矛盾分类：可归因/不可归因/虚假一致/真实收敛）
- CognitiveDivisionEngine: 编排入口

依赖：仅需 base_agent.py + a2a_protocol.py + 现有LLM调用能力
不依赖：networkx、gradio 等可选依赖
"""


import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple, Callable

logger = logging.getLogger("CognitiveDivisionEngine")


# ============================================================================
# 数据结构
# ============================================================================

class DecompositionStrategy(Enum):
    """视角分解策略"""
    EVIDENCE_SPLIT = "evidence_split"           # 证据拆分：文献分为互补子集
    ROLE_CONSTRAINT = "role_constraint"         # 角色约束：注入对抗角色
    LAYER_SEPARATION = "layer_separation"       # 层级分离：抽象层 vs 实施层
    MODALITY_SPLIT = "modality_split"           # 模态拆分：结构化 vs 非结构化
    TIME_SLICE = "time_slice"                   # 时间切片：按时间分割序列数据
    ABSTRACTION_LEVEL = "abstraction_level"     # 抽象层级：具体实例 vs 抽象规则


@dataclass
class ContextMask:
    """上下文掩码——主动不对称的核心
    
    每个Agent看到的证据子集不同，这是认知分工的关键。
    """
    allowed_evidence: List[str] = field(default_factory=list)
    blocked_evidence: List[str] = field(default_factory=list)
    allowed_domains: List[str] = field(default_factory=list)
    blocked_domains: List[str] = field(default_factory=list)
    abstraction_level: str = "mixed"  # "concrete" | "abstract" | "mixed"
    time_slice: Optional[Tuple[str, str]] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """序列化为字典"""
        return {
            "allowed_evidence": self.allowed_evidence,
            "blocked_evidence": self.blocked_evidence,
            "allowed_domains": self.allowed_domains,
            "blocked_domains": self.blocked_domains,
            "abstraction_level": self.abstraction_level,
            "time_slice": self.time_slice,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ContextMask":
        """从字典反序列化"""
        return cls(
            allowed_evidence=data.get("allowed_evidence", []),
            blocked_evidence=data.get("blocked_evidence", []),
            allowed_domains=data.get("allowed_domains", []),
            blocked_domains=data.get("blocked_domains", []),
            abstraction_level=data.get("abstraction_level", "mixed"),
            time_slice=tuple(data["time_slice"]) if data.get("time_slice") else None,
        )


@dataclass
class PerspectiveAssignment:
    """单个视角分配"""
    agent_id: str
    perspective_question: str          # 该Agent看到的子问题
    context_mask: ContextMask          # 上下文掩码
    role_constraint: Optional[str] = None  # 角色约束（如"质疑者"/"辩护者"）
    resource_subset: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "agent_id": self.agent_id,
            "perspective_question": self.perspective_question,
            "context_mask": self.context_mask.to_dict(),
            "role_constraint": self.role_constraint,
            "resource_subset": self.resource_subset,
        }


@dataclass
class DecompositionPlan:
    """视角分解方案"""
    input_question: str
    strategy: str                      # 使用的分解策略名称
    assignments: List[PerspectiveAssignment] = field(default_factory=list)
    rationale: str = ""                # 分解理由
    bridgeability_score: float = 0.5   # 视角间可桥接性评分（0-1）


@dataclass
class Step:
    """推理链中的单步"""
    step_id: int
    operation: str     # "infer" | "exclude" | "confirm" | "question"
    input_desc: str    # 这一步的输入描述
    output: str        # 这一步的输出
    basis: str         # 依据（引用证据或逻辑规则）
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "step_id": self.step_id,
            "operation": self.operation,
            "input": self.input_desc,
            "output": self.output,
            "basis": self.basis,
        }


@dataclass
class IntermediateConclusion:
    """Agent产出的中间结论——通信的唯一载体
    
    核心约束：CommunicationLayer 只传递此对象，
    禁止传递原始视角、上下文掩码内容、"我看到了什么"。
    """
    agent_id: str
    conclusion: str                     # 推理结论
    confidence: float = 0.5             # 置信度 0-1
    reasoning_chain: List[Step] = field(default_factory=list)
    active_hypotheses: List[str] = field(default_factory=list)
    eliminated_hypotheses: List[str] = field(default_factory=list)
    key_assumptions: List[str] = field(default_factory=list)
    uncertainty_markers: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "agent_id": self.agent_id,
            "conclusion": self.conclusion,
            "confidence": self.confidence,
            "reasoning_chain": [s.to_dict() for s in self.reasoning_chain],
            "active_hypotheses": self.active_hypotheses,
            "eliminated_hypotheses": self.eliminated_hypotheses,
            "key_assumptions": self.key_assumptions,
            "uncertainty_markers": self.uncertainty_markers,
        }


@dataclass
class Contradiction:
    """矛盾描述"""
    contradiction_id: int = 0
    my_position: str = ""
    other_position: str = ""
    other_agent_id: str = ""
    severity: float = 0.5              # 矛盾严重程度 0-1
    attributable: bool = True          # 能否从视角差异解释


@dataclass
class Attribution:
    """差异归因"""
    contradiction_id: int = 0
    explanation: str = ""              # 对矛盾的解释
    inferred_other_context: str = ""   # 推断对方可能看到的上下文


@dataclass
class DifferenceAttribution:
    """Agent在Round 1产出的差异归因"""
    agent_id: str
    my_conclusion: str = ""
    other_conclusions: List[str] = field(default_factory=list)
    contradictions: List[Contradiction] = field(default_factory=list)
    attributions: List[Attribution] = field(default_factory=list)
    revision: Optional[str] = None     # 修正后的结论
    revision_reason: str = ""


@dataclass
class CDoLResult:
    """认知分工执行结果"""
    final_answer: str = ""
    reasoning_tree: Dict[str, Any] = field(default_factory=dict)
    contradiction_report: Dict[str, Any] = field(default_factory=dict)
    metrics: Dict[str, float] = field(default_factory=dict)
    perspective_assignments: List[PerspectiveAssignment] = field(default_factory=list)
    round0_conclusions: List[IntermediateConclusion] = field(default_factory=list)
    round1_attributions: List[DifferenceAttribution] = field(default_factory=list)
    round2_revised: List[IntermediateConclusion] = field(default_factory=list)
    judgment: Optional[Any] = None     # Judgment对象
    synergy_gain: float = 1.0          # 协同增益比
    insights: Dict[str, Any] = field(default_factory=dict)  # P0: 结构化insight
    information_policy_summary: str = ""  # Phase 7: 信息策略摘要


# ============================================================================
# PerspectiveDecomposer — 视角分解器
# ============================================================================

class PerspectiveDecomposer:
    """视角分解器
    
    将原始问题分解为N个非对称视角，分配给不同Agent。
    支持6种分解策略，自动评估bridgeability_score。
    
    核心设计：分解本身是一次轻量级LLM调用（flash模型）。
    """
    
    # 六种策略的prompt模板
    STRATEGY_PROMPTS = {
        "evidence_split": (
            "将证据分为互补子集分配给不同Agent。\n"
            "例如：Agent1看实验数据，Agent2看理论推导。"
        ),
        "role_constraint": (
            "为每个Agent注入对抗角色。\n"
            "例如：Agent1为'质疑者'，Agent2为'辩护者'。"
        ),
        "layer_separation": (
            "按层级分离：抽象层 vs 实施层。\n"
            "例如：Agent1做方法论设计，Agent2做可行性验证。"
        ),
        "modality_split": (
            "按模态拆分：结构化数据 vs 非结构化文本。\n"
            "例如：Agent1看数值数据表，Agent2看论文文本描述。"
        ),
        "time_slice": (
            "按时间切片分割数据。\n"
            "例如：Agent1看早期研究，Agent2看最新进展。"
        ),
        "abstraction_level": (
            "按抽象层级拆分：具体实例 vs 抽象规则。\n"
            "例如：Agent1看案例，Agent2看理论框架。"
        ),
    }
    
    def __init__(self, llm_chat: Optional[Callable] = None, insight_store: Optional[Any] = None):
        """
        Args:
            llm_chat: LLM调用函数，签名为 chat(prompt) -> str。
                      为None时使用简单的规则分解。
            insight_store: InsightStore实例，提供历史经验反馈（P1增强）。
        """
        self.llm_chat = llm_chat
        self.insight_store = insight_store
    
    def decompose(
        self,
        question: str,
        agents: List[Any],
        strategy: Optional[str] = None,
        perspective_count: int = 2,
    ) -> DecompositionPlan:
        """自动生成视角分配方案
        
        Args:
            question: 原始问题
            agents: 可用Agent列表（含agent_id和能力信息）
            strategy: 指定分解策略，None时自动选择
            perspective_count: 视角数量
            
        Returns:
            DecompositionPlan: 视角分配方案
        """
        # 选择策略
        if strategy is None:
            strategy = self._auto_select_strategy(question)
        
        # 生成视角分配
        if self.llm_chat:
            plan = self._llm_decompose(question, agents, strategy, perspective_count)
        else:
            plan = self._rule_based_decompose(question, agents, strategy, perspective_count)
        
        # 自检：bridgeability不能太低
        if plan.bridgeability_score < 0.3:
            logger.warning(
                f"[PerspectiveDecomposer] bridgeability_score={plan.bridgeability_score:.2f} "
                f"过低，降级为evidence_split策略"
            )
            plan = self._fallback_to_evidence_split(plan, question, agents, perspective_count)
        
        logger.info(
            f"[PerspectiveDecomposer] 分解完成: strategy={strategy}, "
            f"perspectives={len(plan.assignments)}, "
            f"bridgeability={plan.bridgeability_score:.2f}"
        )
        return plan
    
    def _auto_select_strategy(self, question: str) -> str:
        """根据问题特征自动选择分解策略
        
        P1增强：优先从历史insight推荐，无历史数据时回退到规则匹配。
        """
        # 优先使用历史insight反馈
        if self.insight_store:
            recommended = self.insight_store.get_best_strategy()
            if recommended and recommended in self.STRATEGY_PROMPTS:
                logger.info(f"[PerspectiveDecomposer] 从历史insight推荐策略: {recommended}")
                return recommended
        
        # 回退到规则匹配
        q_lower = question.lower()
        
        # 包含实验数据、文献 → 证据拆分
        if any(kw in q_lower for kw in ["实验", "数据", "文献", "evidence", "data", "paper"]):
            return "evidence_split"
        
        # 包含假设、验证 → 角色约束
        if any(kw in q_lower for kw in ["假设", "验证", "hypothesis", "verify", "论证"]):
            return "role_constraint"
        
        # 包含方法、设计、实现 → 层级分离
        if any(kw in q_lower for kw in ["方法", "设计", "实现", "method", "design"]):
            return "layer_separation"
        
        # 包含对比、评估 → 抽象层级
        if any(kw in q_lower for kw in ["对比", "评估", "compare", "evaluate"]):
            return "abstraction_level"
        
        # 包含趋势、发展 → 时间切片
        if any(kw in q_lower for kw in ["趋势", "发展", "演进", "trend", "evolution"]):
            return "time_slice"
        
        # 默认：证据拆分
        return "evidence_split"
    
    def _llm_decompose(
        self,
        question: str,
        agents: List[Any],
        strategy: str,
        perspective_count: int,
    ) -> DecompositionPlan:
        """使用LLM生成视角分配方案"""
        agent_descriptions = []
        for a in agents[:perspective_count]:
            aid = getattr(a, "agent_id", str(a))
            caps = getattr(a, "capabilities", [])
            domains = getattr(a, "domain_expertise", [])
            agent_descriptions.append(f"  - {aid}: 能力={caps}, 领域={domains}")
        
        strategy_desc = self.STRATEGY_PROMPTS.get(strategy, strategy)
        
        prompt = f"""你是一个视角分解专家。请将以下问题分解为{perspective_count}个非对称视角。

## 原始问题
{question}

## 分解策略
{strategy}: {strategy_desc}

## 可用Agent
{chr(10).join(agent_descriptions)}

## 输出要求
请严格按JSON格式输出：
```json
{{
  "rationale": "分解理由（简要说明为什么这样分）",
  "bridgeability_score": 0.7,
  "assignments": [
    {{
      "agent_id": "agent1的id",
      "perspective_question": "该Agent看到的子问题",
      "allowed_evidence": ["该Agent可见的证据描述"],
      "blocked_evidence": ["该Agent不可见的证据描述"],
      "role_constraint": "角色约束（可选，null或字符串）",
      "abstraction_level": "concrete/abstract/mixed"
    }}
  ]
}}
```

注意：
1. bridgeability_score范围0-1，表示视角间能否通过通信弥合差异。太低(<0.3)会导致通信失败。
2. 每个Agent的视角应该非对称——它们看到的信息子集应该不同。
3. perspective_question应该是一个具体问题，不是泛泛的描述。"""
        
        try:
            response = self.llm_chat(prompt)
            plan = self._parse_llm_response(response, question, strategy, agents)
            return plan
        except Exception as e:
            logger.warning(f"[PerspectiveDecomposer] LLM分解失败: {e}，降级为规则分解")
            return self._rule_based_decompose(question, agents, strategy, perspective_count)
    
    def _rule_based_decompose(
        self,
        question: str,
        agents: List[Any],
        strategy: str,
        perspective_count: int,
    ) -> DecompositionPlan:
        """基于规则的视角分解（无LLM时的降级方案）"""
        assignments = []
        agent_ids = [getattr(a, "agent_id", f"agent_{i}") for i, a in enumerate(agents)]
        
        if strategy == "evidence_split":
            assignments = [
                PerspectiveAssignment(
                    agent_id=agent_ids[i] if i < len(agent_ids) else f"agent_{i}",
                    perspective_question=f"从{'实验数据' if i == 0 else '理论推导'}角度分析: {question}",
                    context_mask=ContextMask(
                        allowed_evidence=["实验数据"] if i == 0 else ["理论推导"],
                        blocked_evidence=["理论推导"] if i == 0 else ["实验数据"],
                        allowed_domains=["experimental"] if i == 0 else ["theoretical"],
                        blocked_domains=["theoretical"] if i == 0 else ["experimental"],
                        abstraction_level="concrete" if i == 0 else "abstract",
                    ),
                    role_constraint=None,
                    resource_subset=["experimental_data"] if i == 0 else ["theoretical_framework"],
                )
                for i in range(min(perspective_count, max(len(agent_ids), 2)))
            ]
        elif strategy == "role_constraint":
            roles = [("质疑者", "challenge"), ("辩护者", "defend")]
            assignments = [
                PerspectiveAssignment(
                    agent_id=agent_ids[i] if i < len(agent_ids) else f"agent_{i}",
                    perspective_question=f"作为{roles[i][0]}，对以下问题进行论证: {question}",
                    context_mask=ContextMask(
                        allowed_evidence=["all_evidence"],
                        blocked_evidence=[],
                        abstraction_level="mixed",
                    ),
                    role_constraint=roles[i][1],
                    resource_subset=["all_evidence"],
                )
                for i in range(min(perspective_count, max(len(agent_ids), 2)))
            ]
        elif strategy == "layer_separation":
            layers = [("方法论设计", "abstract"), ("可行性验证", "concrete")]
            assignments = [
                PerspectiveAssignment(
                    agent_id=agent_ids[i] if i < len(agent_ids) else f"agent_{i}",
                    perspective_question=f"从{layers[i][0]}层面分析: {question}",
                    context_mask=ContextMask(
                        allowed_evidence=["all_evidence"],
                        abstraction_level=layers[i][1],
                    ),
                    resource_subset=["methodology"] if i == 0 else ["implementation"],
                )
                for i in range(min(perspective_count, max(len(agent_ids), 2)))
            ]
        else:
            # 通用降级：等分为N个视角
            for i in range(min(perspective_count, max(len(agent_ids), 2))):
                assignments.append(PerspectiveAssignment(
                    agent_id=agent_ids[i] if i < len(agent_ids) else f"agent_{i}",
                    perspective_question=f"从第{i+1}个视角分析: {question}",
                    context_mask=ContextMask(
                        allowed_evidence=["all_evidence"],
                        abstraction_level="mixed",
                    ),
                ))
        
        # 计算bridgeability_score
        bridgeability = self._estimate_bridgeability(assignments, strategy)
        
        return DecompositionPlan(
            input_question=question,
            strategy=strategy,
            assignments=assignments,
            rationale=f"使用{strategy}策略进行{len(assignments)}视角分解",
            bridgeability_score=bridgeability,
        )
    
    def _parse_llm_response(
        self,
        response: str,
        question: str,
        strategy: str,
        agents: List[Any],
    ) -> DecompositionPlan:
        """解析LLM返回的JSON方案"""
        import json
        import re
        
        # 提取JSON部分
        json_match = re.search(r'\{[\s\S]*\}', response)
        if not json_match:
            raise ValueError("LLM返回中未找到JSON")
        
        data = json.loads(json_match.group())
        
        assignments = []
        for a_data in data.get("assignments", []):
            mask = ContextMask(
                allowed_evidence=a_data.get("allowed_evidence", []),
                blocked_evidence=a_data.get("blocked_evidence", []),
                allowed_domains=a_data.get("allowed_domains", []),
                blocked_domains=a_data.get("blocked_domains", []),
                abstraction_level=a_data.get("abstraction_level", "mixed"),
            )
            assignments.append(PerspectiveAssignment(
                agent_id=a_data.get("agent_id", "unknown"),
                perspective_question=a_data.get("perspective_question", ""),
                context_mask=mask,
                role_constraint=a_data.get("role_constraint"),
                resource_subset=a_data.get("resource_subset", []),
            ))
        
        return DecompositionPlan(
            input_question=question,
            strategy=strategy,
            assignments=assignments,
            rationale=data.get("rationale", ""),
            bridgeability_score=float(data.get("bridgeability_score", 0.5)),
        )
    
    def _estimate_bridgeability(self, assignments: List[PerspectiveAssignment], strategy: str) -> float:
        """估算视角间的可桥接性分数
        
        策略相关：
        - evidence_split: 通常bridgeability较高（0.6-0.8），因为证据可以互补
        - role_constraint: 中等（0.5-0.7），因为共享证据但角色不同
        - layer_separation: 中等偏低（0.4-0.6），层级差异可能导致鸿沟
        """
        base_scores = {
            "evidence_split": 0.7,
            "role_constraint": 0.65,
            "layer_separation": 0.55,
            "modality_split": 0.6,
            "time_slice": 0.65,
            "abstraction_level": 0.5,
        }
        
        score = base_scores.get(strategy, 0.5)
        
        # 视角数量越多，bridgeability越低
        n = len(assignments)
        if n > 2:
            score *= 0.9 ** (n - 2)
        
        return round(min(1.0, max(0.0, score)), 2)
    
    def _fallback_to_evidence_split(
        self,
        original_plan: DecompositionPlan,
        question: str,
        agents: List[Any],
        perspective_count: int,
    ) -> DecompositionPlan:
        """bridgeability过低时的降级方案"""
        return self._rule_based_decompose(question, agents, "evidence_split", perspective_count)


# ============================================================================
# CommunicationLayer — 有损通信层
# ============================================================================

# 差异归因prompt模板
DIFFERENCE_ATTRIBUTION_PROMPT = """你是协同推理中的一环。你刚刚完成独立推理，现在需要查看其他Agent的中间结论，并进行差异归因。

## 你的结论
{my_conclusion}
置信度: {my_confidence}

## 你的活跃假设
{active_hypotheses}

## 你排除的假设
{eliminated_hypotheses}

## 其他Agent的中间结论
{other_conclusions_text}

## 任务
1. 识别你与其他Agent结论之间的矛盾（如有）
2. 对每个矛盾进行归因：差异是因为你们看到了不同的证据？还是推理方法不同？
3. 尝试推断其他Agent可能拥有什么你没看到的信息
4. 如果必要，修正你的结论

请严格按JSON格式输出：
```json
{{
  "contradictions": [
    {{
      "contradiction_id": 1,
      "my_position": "你的立场",
      "other_position": "对方的立场",
      "other_agent_id": "对方agent_id",
      "severity": 0.7,
      "attributable": true
    }}
  ],
  "attributions": [
    {{
      "contradiction_id": 1,
      "explanation": "差异可能的原因",
      "inferred_other_context": "推断对方可能拥有的信息"
    }}
  ],
  "revision": "修正后的结论（如果没有修正则为null）",
  "revision_reason": "修正原因"
}}
```"""


class CommunicationLayer:
    """有损通信层——认知分工的理论核心
    
    核心约束：
    - 允许传递：IntermediateConclusion、置信度、关键假设、排除的假设列表
    - 禁止传递：原始视角Q_i、上下文掩码内容、"我看到了什么"
    
    通信协议：
    - Round 0: 各Agent在受限上下文下独立推理，无通信
    - Round 1: 每个Agent收到其他人的C_j（中间结论），进行差异归因
    - Round 2: 基于归因修正结论（可选）
    """
    
    def __init__(self, llm_chat: Optional[Callable] = None):
        """
        Args:
            llm_chat: LLM调用函数
        """
        self.llm_chat = llm_chat
        self.round_history: List[Dict[str, Any]] = []
    
    def run_round_0(
        self,
        assignments: List[PerspectiveAssignment],
        agents: Dict[str, Any],
        task_description: str = "",
    ) -> List[IntermediateConclusion]:
        """Round 0: 各Agent独立推理，无通信
        
        每个Agent在受限上下文（由ContextMask定义）下独立推理。
        
        Args:
            assignments: 视角分配方案
            agents: agent_id -> agent对象 的映射
            task_description: 任务描述
            
        Returns:
            各Agent的中间结论列表
        """
        conclusions = []
        
        for assignment in assignments:
            agent = agents.get(assignment.agent_id)
            
            if agent and hasattr(agent, 'chat'):
                # 使用实际Agent进行推理
                conclusion = self._agent_reason_with_llm(agent, assignment, task_description)
            else:
                # 模拟推理（Demo模式或Agent不可用）
                conclusion = self._simulate_reason(assignment, task_description)
            
            conclusions.append(conclusion)
        
        self.round_history.append({
            "round": 0,
            "timestamp": time.time(),
            "conclusions": [c.to_dict() for c in conclusions],
        })
        
        logger.info(f"[CommunicationLayer] Round 0 完成: {len(conclusions)}个中间结论")
        return conclusions
    
    def run_round_1(
        self,
        conclusions: List[IntermediateConclusion],
        assignments: List[PerspectiveAssignment],
        agents: Dict[str, Any],
    ) -> List[DifferenceAttribution]:
        """Round 1: 差异归因
        
        关键：每个Agent只收到其他人的C_j（中间结论），不收到Q_j（视角问题）。
        Agent必须从C_j逆向推断Agent_j可能拥有什么信息。
        
        Args:
            conclusions: Round 0的中间结论
            assignments: 视角分配方案
            agents: agent_id -> agent对象 的映射
            
        Returns:
            各Agent的差异归因列表
        """
        attributions = []
        
        for i, assignment in enumerate(assignments):
            my_conclusion = conclusions[i] if i < len(conclusions) else None
            if not my_conclusion:
                continue
            
            # 构建"其他人的结论"文本（严格不包含视角信息）
            other_conclusions_text = self._build_other_conclusions_text(
                my_index=i, conclusions=conclusions
            )
            
            agent = agents.get(assignment.agent_id)
            
            if agent and hasattr(agent, 'chat') and self.llm_chat:
                attribution = self._agent_attribute_with_llm(
                    agent, my_conclusion, other_conclusions_text, assignment
                )
            else:
                attribution = self._simulate_attribute(
                    my_conclusion, conclusions, i, assignment
                )
            
            attributions.append(attribution)
        
        self.round_history.append({
            "round": 1,
            "timestamp": time.time(),
            "attributions": [
                {"agent_id": a.agent_id, "revision": a.revision, "revision_reason": a.revision_reason}
                for a in attributions
            ],
        })
        
        logger.info(f"[CommunicationLayer] Round 1 完成: {len(attributions)}个差异归因")
        return attributions
    
    def run_round_2(
        self,
        attributions: List[DifferenceAttribution],
        original_conclusions: List[IntermediateConclusion],
    ) -> List[IntermediateConclusion]:
        """Round 2: 基于归因修正结论
        
        如果Agent在Round 1中产生了修正结论，使用修正版本；
        否则保留原始结论。
        
        Args:
            attributions: Round 1的差异归因
            original_conclusions: Round 0的原始结论
            
        Returns:
            修正后的结论列表
        """
        revised = []
        
        for i, (attr, original) in enumerate(zip(attributions, original_conclusions)):
            if attr.revision:
                # 使用修正后的结论
                revised_conclusion = IntermediateConclusion(
                    agent_id=original.agent_id,
                    conclusion=attr.revision,
                    confidence=min(1.0, original.confidence + 0.1),  # 修正后略微提升置信
                    reasoning_chain=original.reasoning_chain,
                    active_hypotheses=original.active_hypotheses,
                    eliminated_hypotheses=original.eliminated_hypotheses,
                    key_assumptions=original.key_assumptions,
                    uncertainty_markers=original.uncertainty_markers + [
                        f"经Round 1修正: {attr.revision_reason}"
                    ],
                )
            else:
                revised_conclusion = original
            
            revised.append(revised_conclusion)
        
        self.round_history.append({
            "round": 2,
            "timestamp": time.time(),
            "revised_count": sum(1 for a in attributions if a.revision),
        })
        
        logger.info(f"[CommunicationLayer] Round 2 完成: {len(revised)}个结论")
        return revised
    
    def _build_other_conclusions_text(
        self,
        my_index: int,
        conclusions: List[IntermediateConclusion],
    ) -> str:
        """构建"其他人结论"的文本（严格不含视角信息）"""
        lines = []
        for j, c in enumerate(conclusions):
            if j == my_index:
                continue
            lines.append(f"### Agent {c.agent_id} 的中间结论")
            lines.append(f"结论: {c.conclusion}")
            lines.append(f"置信度: {c.confidence:.2f}")
            if c.active_hypotheses:
                lines.append(f"活跃假设: {', '.join(c.active_hypotheses)}")
            if c.eliminated_hypotheses:
                lines.append(f"排除假设: {', '.join(c.eliminated_hypotheses)}")
            if c.uncertainty_markers:
                lines.append(f"不确定性: {', '.join(c.uncertainty_markers)}")
            lines.append("")
        return "\n".join(lines)
    
    def _simulate_reason(
        self,
        assignment: PerspectiveAssignment,
        task_description: str,
    ) -> IntermediateConclusion:
        """模拟Agent推理（Demo模式）"""
        # 根据视角分配生成模拟结论
        mask = assignment.context_mask
        perspective = assignment.perspective_question
        
        return IntermediateConclusion(
            agent_id=assignment.agent_id,
            conclusion=f"基于{'、'.join(mask.allowed_evidence) if mask.allowed_evidence else '可用证据'}的分析，"
                       f"针对'{perspective[:50]}...'的推理结论",
            confidence=0.65,
            reasoning_chain=[
                Step(step_id=1, operation="infer", input_desc=task_description,
                     output=f"从{'、'.join(mask.allowed_domains) if mask.allowed_domains else '多领域'}角度分析",
                     basis="视角分配的证据子集"),
                Step(step_id=2, operation="confirm", input_desc="分析结果",
                     output=perspective[:80],
                     basis="逻辑推理"),
            ],
            active_hypotheses=[f"H1_{assignment.agent_id}: 初步假设"],
            eliminated_hypotheses=[f"H_excluded_{assignment.agent_id}: 被证据排除的假设"],
            key_assumptions=[f"假设{'、'.join(mask.allowed_domains) if mask.allowed_domains else '现有'}证据充分"],
            uncertainty_markers=["证据子集可能不完整"],
        )
    
    def _simulate_attribute(
        self,
        my_conclusion: IntermediateConclusion,
        all_conclusions: List[IntermediateConclusion],
        my_index: int,
        assignment: PerspectiveAssignment,
    ) -> DifferenceAttribution:
        """模拟差异归因（Demo模式）"""
        contradictions = []
        attributions_list = []
        
        for j, other_c in enumerate(all_conclusions):
            if j == my_index:
                continue
            
            # 检测矛盾
            if my_conclusion.conclusion != other_c.conclusion:
                contradictions.append(Contradiction(
                    contradiction_id=len(contradictions) + 1,
                    my_position=my_conclusion.conclusion[:80],
                    other_position=other_c.conclusion[:80],
                    other_agent_id=other_c.agent_id,
                    severity=0.6,
                    attributable=True,
                ))
                attributions_list.append(Attribution(
                    contradiction_id=len(contradictions),
                    explanation=f"对方Agent {other_c.agent_id}可能拥有不同的证据子集，导致结论偏差",
                    inferred_other_context=f"对方可能看到了我未见的证据领域",
                ))
        
        revision = None
        revision_reason = ""
        if contradictions:
            revision = f"在考虑{len(contradictions)}个矛盾后修正: {my_conclusion.conclusion[:60]}...需要结合更多证据"
            revision_reason = f"发现{len(contradictions)}个可归因矛盾，部分修正结论"
        
        return DifferenceAttribution(
            agent_id=my_conclusion.agent_id,
            my_conclusion=my_conclusion.conclusion,
            other_conclusions=[c.conclusion for j, c in enumerate(all_conclusions) if j != my_index],
            contradictions=contradictions,
            attributions=attributions_list,
            revision=revision,
            revision_reason=revision_reason,
        )
    
    def _agent_reason_with_llm(
        self,
        agent: Any,
        assignment: PerspectiveAssignment,
        task_description: str,
    ) -> IntermediateConclusion:
        """使用实际Agent进行推理"""
        mask = assignment.context_mask
        
        # 构建受限上下文的推理prompt
        role_text = ""
        if assignment.role_constraint:
            role_text = f"\n## 角色约束\n你当前的角色是: {assignment.role_constraint}"
        
        prompt = f"""请基于以下约束条件进行独立推理。

## 任务
{task_description}

## 你的视角问题
{assignment.perspective_question}

## 你可使用的证据范围
允许: {', '.join(mask.allowed_evidence) if mask.allowed_evidence else '所有可用证据'}
禁止: {', '.join(mask.blocked_evidence) if mask.blocked_evidence else '无'}
知识域: {', '.join(mask.allowed_domains) if mask.allowed_domains else '通用'}
抽象层级: {mask.abstraction_level}
{role_text}

## 输出要求
请严格按JSON格式输出：
```json
{{
  "conclusion": "你的推理结论",
  "confidence": 0.7,
  "active_hypotheses": ["当前活跃假设列表"],
  "eliminated_hypotheses": ["你排除的假设及理由"],
  "key_assumptions": ["你的关键假设"],
  "uncertainty_markers": ["不确定性标记"]
}}
```"""
        
        try:
            response = agent.chat(prompt)
            import json
            import re
            json_match = re.search(r'\{[\s\S]*\}', response)
            if json_match:
                data = json.loads(json_match.group())
                return IntermediateConclusion(
                    agent_id=assignment.agent_id,
                    conclusion=data.get("conclusion", ""),
                    confidence=float(data.get("confidence", 0.5)),
                    active_hypotheses=data.get("active_hypotheses", []),
                    eliminated_hypotheses=data.get("eliminated_hypotheses", []),
                    key_assumptions=data.get("key_assumptions", []),
                    uncertainty_markers=data.get("uncertainty_markers", []),
                )
        except Exception as e:
            logger.warning(f"[CommunicationLayer] Agent {assignment.agent_id} LLM推理失败: {e}")
        
        return self._simulate_reason(assignment, task_description)
    
    def _agent_attribute_with_llm(
        self,
        agent: Any,
        my_conclusion: IntermediateConclusion,
        other_conclusions_text: str,
        assignment: PerspectiveAssignment,
    ) -> DifferenceAttribution:
        """使用实际Agent进行差异归因"""
        prompt = DIFFERENCE_ATTRIBUTION_PROMPT.format(
            my_conclusion=my_conclusion.conclusion,
            my_confidence=my_conclusion.confidence,
            active_hypotheses=', '.join(my_conclusion.active_hypotheses),
            eliminated_hypotheses=', '.join(my_conclusion.eliminated_hypotheses),
            other_conclusions_text=other_conclusions_text,
        )
        
        try:
            response = agent.chat(prompt)
            import json
            import re
            json_match = re.search(r'\{[\s\S]*\}', response)
            if json_match:
                data = json.loads(json_match.group())
                contradictions = [
                    Contradiction(**c) for c in data.get("contradictions", [])
                ]
                attributions_list = [
                    Attribution(**a) for a in data.get("attributions", [])
                ]
                return DifferenceAttribution(
                    agent_id=my_conclusion.agent_id,
                    my_conclusion=my_conclusion.conclusion,
                    other_conclusions=[],
                    contradictions=contradictions,
                    attributions=attributions_list,
                    revision=data.get("revision"),
                    revision_reason=data.get("revision_reason", ""),
                )
        except Exception as e:
            logger.warning(f"[CommunicationLayer] Agent {assignment.agent_id} 差异归因失败: {e}")
        
        return self._simulate_attribute(
            my_conclusion, [], 0, assignment
        )


# ============================================================================
# FusionJudge — 融合判断器
# ============================================================================

class ContradictionType(Enum):
    """矛盾分类——融合判断器的核心"""
    ATTRIBUTABLE = "attributable"            # 可归因：从视角差异能解释
    UNATTRIBUTABLE = "unattributable"        # 不可归因：需要回溯
    FALSE_CONSENSUS = "false_consensus"      # 虚假一致：答案同但推理链矛盾
    TRUE_CONVERGENCE = "true_convergence"    # 真实收敛：答案+推理链一致


@dataclass
class Judgment:
    """融合判断结果"""
    action: str = "converge"       # "converge" | "backtrack" | "deep_review" | "revision_round"
    final_answer: str = ""
    reasoning_tree: Dict[str, Any] = field(default_factory=dict)
    contradiction_report: Dict[str, Any] = field(default_factory=dict)
    reason: str = ""
    contradiction_type: str = ""
    review_targets: List[str] = field(default_factory=list)


class FusionJudge:
    """融合判断器——检测矛盾，决定回溯或输出
    
    不是投票器，是矛盾检测器。
    
    四类矛盾：
    1. 可归因（ATTRIBUTABLE）：从视角差异能解释 → 触发修正轮次
    2. 不可归因（UNATTRIBUTABLE）：无法从视角差异解释 → 需要回溯
    3. 虚假一致（FALSE_CONSENSUS）：答案同但推理链矛盾 → 最危险，需深度审查
    4. 真实收敛（TRUE_CONVERGENCE）：答案+推理链一致 → 输出
    
    核心理论贡献：虚假一致检测
    关键洞察：不比较答案，比较假设空间。
    - Agent1排除{H2,H3}确认H1（因为证据A否定了H2/H3）
    - Agent2排除{H1,H4}确认H1（因为证据B否定了H1/H4）
    → 答案相同(H1)，但Agent2的推理链中曾排除H1！
    → 这是虚假一致的信号
    """
    
    def __init__(self, llm_chat: Optional[Callable] = None):
        """
        Args:
            llm_chat: LLM调用函数（用于辅助判断）
        """
        self.llm_chat = llm_chat
        self.judgment_history: List[Dict[str, Any]] = []
    
    def judge(self, conclusions: List[IntermediateConclusion]) -> Judgment:
        """融合判断核心流程
        
        1. 提取所有结论的推理链
        2. 逐对比较推理链（不是比较答案！）
        3. 分类矛盾
        4. 决定下一步
        
        Args:
            conclusions: 各Agent的（修正后）结论
            
        Returns:
            Judgment: 融合判断结果
        """
        if len(conclusions) < 2:
            return Judgment(
                action="converge",
                final_answer=conclusions[0].conclusion if conclusions else "",
                reason="单个结论，直接收敛",
                contradiction_type="single_agent",
            )
        
        # Step 1: 逐对比较
        chain_pairs = self._extract_chain_pairs(conclusions)
        
        # Step 2: 矛盾分类
        all_contradictions = []
        types_found = set()
        
        for pair_info in chain_pairs:
            ctype = self._classify_contradiction(
                pair_info["conclusion_a"],
                pair_info["conclusion_b"],
            )
            all_contradictions.append({
                "pair": (pair_info["conclusion_a"].agent_id, pair_info["conclusion_b"].agent_id),
                "type": ctype.value,
                "detail": pair_info,
            })
            types_found.add(ctype)
        
        # Step 3: 决策
        judgment = Judgment()
        judgment.contradiction_report = {
            "total_pairs": len(chain_pairs),
            "contradictions": all_contradictions,
            "types_summary": {ct.value: 0 for ct in ContradictionType},
        }
        
        for c in all_contradictions:
            judgment.contradiction_report["types_summary"][c["type"]] += 1
        
        # 优先级：不可归因 > 虚假一致 > 可归因 > 真实收敛
        if ContradictionType.UNATTRIBUTABLE in types_found:
            judgment.action = "backtrack"
            judgment.reason = "存在无法从视角差异解释的矛盾，需要增补视角"
            judgment.contradiction_type = ContradictionType.UNATTRIBUTABLE.value
            
        elif ContradictionType.FALSE_CONSENSUS in types_found:
            judgment.action = "deep_review"
            judgment.reason = "检测到虚假一致：结论相同但推理路径矛盾"
            judgment.contradiction_type = ContradictionType.FALSE_CONSENSUS.value
            judgment.review_targets = self._identify_false_consensus_targets(
                all_contradictions
            )
            
        elif ContradictionType.ATTRIBUTABLE in types_found:
            judgment.action = "revision_round"
            judgment.reason = "矛盾可从视角差异解释，触发修正轮次"
            judgment.contradiction_type = ContradictionType.ATTRIBUTABLE.value
            
        else:
            judgment.action = "converge"
            judgment.contradiction_type = ContradictionType.TRUE_CONVERGENCE.value
            judgment.final_answer = self._synthesize_answer(conclusions)
            judgment.reasoning_tree = self._build_reasoning_tree(conclusions)
            judgment.reason = "真实收敛：所有Agent的答案和推理路径一致"
        
        # 对于可归因和虚假一致，也生成最终答案（作为参考）
        if judgment.action in ("revision_round", "deep_review"):
            judgment.final_answer = self._synthesize_answer(conclusions)
            judgment.reasoning_tree = self._build_reasoning_tree(conclusions)
        
        self.judgment_history.append({
            "timestamp": time.time(),
            "action": judgment.action,
            "type": judgment.contradiction_type,
            "conclusion_count": len(conclusions),
        })
        
        logger.info(
            f"[FusionJudge] 判断完成: action={judgment.action}, "
            f"type={judgment.contradiction_type}, "
            f"pairs={len(chain_pairs)}"
        )
        return judgment
    
    def _extract_chain_pairs(
        self,
        conclusions: List[IntermediateConclusion],
    ) -> List[Dict[str, Any]]:
        """提取所有结论对用于比较"""
        pairs = []
        for i in range(len(conclusions)):
            for j in range(i + 1, len(conclusions)):
                pairs.append({
                    "conclusion_a": conclusions[i],
                    "conclusion_b": conclusions[j],
                    "index_a": i,
                    "index_b": j,
                })
        return pairs
    
    def _classify_contradiction(
        self,
        a: IntermediateConclusion,
        b: IntermediateConclusion,
    ) -> ContradictionType:
        """矛盾分类的核心逻辑
        
        关键洞察：不比较答案，比较假设空间。
        
        虚假一致检测：
        - 如果a和b的结论相同，但a排除的假设中包含b的活跃假设，
          或b排除的假设中包含a的活跃假设 → 虚假一致
        """
        a_conclusion = a.conclusion.strip().lower()
        b_conclusion = b.conclusion.strip().lower()
        
        a_excluded = set(h.strip().lower() for h in a.eliminated_hypotheses)
        b_excluded = set(h.strip().lower() for h in b.eliminated_hypotheses)
        a_active = set(h.strip().lower() for h in a.active_hypotheses)
        b_active = set(h.strip().lower() for h in b.active_hypotheses)
        
        # 答案是否相同（语义级别的简单比较）
        same_answer = self._semantic_similarity(a.conclusion, b.conclusion) > 0.7
        
        if same_answer:
            # 答案相同——检查推理链是否矛盾
            
            # 虚假一致检测核心：
            # a排除的假设中是否包含b的活跃假设？
            if a_excluded & b_active:
                return ContradictionType.FALSE_CONSENSUS
            
            # b排除的假设中是否包含a的活跃假设？
            if b_excluded & a_active:
                return ContradictionType.FALSE_CONSENSUS
            
            # 检查推理链步骤是否有矛盾
            if self._has_reasoning_chain_conflict(a, b):
                return ContradictionType.FALSE_CONSENSUS
            
            # 答案相同，推理链无矛盾 → 真实收敛
            return ContradictionType.TRUE_CONVERGENCE
        
        # 答案不同
        # 检查是否能从视角差异解释
        if self._can_explain_from_perspective_diff(a, b):
            return ContradictionType.ATTRIBUTABLE
        else:
            return ContradictionType.UNATTRIBUTABLE
    
    def _semantic_similarity(self, text_a: str, text_b: str) -> float:
        """简单的语义相似度计算（基于词重叠）
        
        不需要精确的语义模型，只需判断两段文本是否在说同一件事。
        """
        # 分词（简单按空格和标点分割）
        import re
        words_a = set(re.findall(r'[\w\u4e00-\u9fff]+', text_a.lower()))
        words_b = set(re.findall(r'[\w\u4e00-\u9fff]+', text_b.lower()))
        
        if not words_a or not words_b:
            return 0.0
        
        # Jaccard相似度
        intersection = words_a & words_b
        union = words_a | words_b
        
        return len(intersection) / len(union) if union else 0.0
    
    def _has_reasoning_chain_conflict(
        self,
        a: IntermediateConclusion,
        b: IntermediateConclusion,
    ) -> bool:
        """检查两个推理链是否存在步骤级冲突"""
        if not a.reasoning_chain or not b.reasoning_chain:
            return False
        
        # 检查：一方的"confirm"步骤是否与另一方的"exclude"步骤冲突
        for step_a in a.reasoning_chain:
            for step_b in b.reasoning_chain:
                if step_a.operation == "confirm" and step_b.operation == "exclude":
                    # 如果确认和排除的是同一事物
                    if self._semantic_similarity(step_a.output, step_b.output) > 0.6:
                        return True
                elif step_a.operation == "exclude" and step_b.operation == "confirm":
                    if self._semantic_similarity(step_a.output, step_b.output) > 0.6:
                        return True
        
        return False
    
    def _can_explain_from_perspective_diff(
        self,
        a: IntermediateConclusion,
        b: IntermediateConclusion,
    ) -> bool:
        """判断矛盾是否可以从视角差异解释
        
        启发式：如果两个Agent的关键假设不重叠，说明它们基于不同证据，
        矛盾可能是视角差异导致的。
        """
        a_assumptions = set(h.strip().lower() for h in a.key_assumptions)
        b_assumptions = set(h.strip().lower() for h in b.key_assumptions)
        
        if not a_assumptions or not b_assumptions:
            return True  # 信息不足时默认可归因
        
        # 假设重叠度低 → 可能是视角差异导致的
        overlap = len(a_assumptions & b_assumptions)
        total = len(a_assumptions | b_assumptions)
        
        return (overlap / total) < 0.5 if total > 0 else True
    
    def _identify_false_consensus_targets(
        self,
        contradictions: List[Dict[str, Any]],
    ) -> List[str]:
        """识别虚假一致中需要深度审查的目标"""
        targets = []
        for c in contradictions:
            if c["type"] == ContradictionType.FALSE_CONSENSUS.value:
                pair = c["pair"]
                targets.extend(list(pair))
        return list(set(targets))
    
    def _synthesize_answer(self, conclusions: List[IntermediateConclusion]) -> str:
        """综合所有结论生成最终答案"""
        if not conclusions:
            return ""
        
        # 按置信度加权
        total_conf = sum(c.confidence for c in conclusions)
        if total_conf == 0:
            total_conf = 1.0
        
        # 选择置信度最高的结论作为基础
        best = max(conclusions, key=lambda c: c.confidence)
        
        # 如果有多个结论，合成条件依赖型答案
        unique_conclusions = set()
        for c in conclusions:
            unique_conclusions.add(c.conclusion[:100])
        
        if len(unique_conclusions) == 1:
            return best.conclusion
        
        # 多结论合成
        parts = [f"综合{len(conclusions)}个视角的分析结果："]
        for c in conclusions:
            parts.append(f"- [{c.agent_id}, 置信度{c.confidence:.2f}] {c.conclusion[:150]}")
        
        parts.append(f"\n主要结论（基于最高置信度{best.confidence:.2f}）: {best.conclusion}")
        
        return "\n".join(parts)
    
    def _build_reasoning_tree(self, conclusions: List[IntermediateConclusion]) -> Dict[str, Any]:
        """构建推理树——展示各Agent的推理路径如何汇聚"""
        tree = {
            "root": "融合推理",
            "branches": [],
        }
        
        for c in conclusions:
            branch = {
                "agent_id": c.agent_id,
                "conclusion": c.conclusion,
                "confidence": c.confidence,
                "steps": [s.to_dict() for s in c.reasoning_chain],
                "active_hypotheses": c.active_hypotheses,
                "eliminated_hypotheses": c.eliminated_hypotheses,
            }
            tree["branches"].append(branch)
        
        return tree


# ============================================================================
# CognitiveDivisionEngine — 编排入口
# ============================================================================

class CognitiveDivisionEngine:
    """认知分工引擎 — 编排入口
    
    调用链：
    TaskNode(execution_mode="cognitive_division")
      → DynamicTopologyRouter.route() → RoutePlan(cdol_enabled=True)
      → CognitiveDivisionEngine.execute(route_plan)
      → 返回CDoLResult给TaskTree
    
    接收 RoutePlan + TaskRequirement，返回 CDoLResult。
    """
    
    def __init__(
        self,
        agents: Optional[Dict[str, Any]] = None,
        memory_pool: Optional[Any] = None,
        llm_chat: Optional[Callable] = None,
        insight_store: Optional[Any] = None,
        information_policy: Optional[Any] = None,
    ):
        """
        Args:
            agents: agent_id -> agent对象 的映射
            memory_pool: GlobalMemoryPool实例（可选）
            llm_chat: LLM调用函数
            insight_store: InsightStore实例（可选，用于跨执行经验积累）
            information_policy: AgentInformationPolicy实例（可选，用于三层信息架构）
        """
        self.agents = agents or {}
        self.memory_pool = memory_pool
        self.llm_chat = llm_chat
        
        # P0+P1: Insight机制集成
        self.insight_store = insight_store or InsightStore()
        self.distiller = InsightDistiller()
        
        # Phase 7: 信息策略集成
        self.information_policy = information_policy
        
        self.decomposer = PerspectiveDecomposer(llm_chat=llm_chat, insight_store=self.insight_store)
        self.comm_layer = CommunicationLayer(llm_chat=llm_chat)
        self.judge = FusionJudge(llm_chat=llm_chat)
    
    def execute(
        self,
        task_description: str,
        assignments: Optional[List[PerspectiveAssignment]] = None,
        strategy: Optional[str] = None,
        perspective_count: int = 2,
    ) -> CDoLResult:
        """认知分工执行流程
        
        Args:
            task_description: 任务描述
            assignments: 预设的视角分配（None时自动生成）
            strategy: 分解策略（None时自动选择）
            perspective_count: 视角数量
            
        Returns:
            CDoLResult: 认知分工执行结果
        """
        logger.info(f"[CDoLEngine] 开始执行: {task_description[:50]}...")
        
        # Phase 7: 信息策略摘要（用于结果记录）
        policy_summary = ""
        
        # Step 0: 如果没有预设分配，自动生成
        if not assignments:
            # Phase 7: 如果有信息策略，使用它来智能选择参与者
            if self.information_policy:
                recommended = self.information_policy.get_recommended_participants(
                    task_description, max_count=perspective_count
                )
                # 过滤出实际可用的Agent
                available_agents = {
                    name: agent for name, agent in self.agents.items()
                    if name in recommended
                }
                agent_list = list(available_agents.values()) if available_agents else list(self.agents.values())
                policy_summary = (
                    f"信息策略: 推荐参与者={recommended}, "
                    f"可用={list(available_agents.keys()) if available_agents else 'all'}"
                )
                logger.info(f"[CDoLEngine] {policy_summary}")
            else:
                agent_list = list(self.agents.values()) if self.agents else []
            
            plan = self.decomposer.decompose(
                task_description,
                agents=agent_list,
                strategy=strategy,
                perspective_count=perspective_count,
            )
            assignments = plan.assignments
            
            # Phase 7: 为每个分配应用基于角色的信息裁剪
            if self.information_policy:
                for assignment in assignments:
                    agent_id = assignment.agent_id
                    try:
                        policy_mask = self.information_policy.generate_context_mask(
                            agent_id, {"task": task_description}
                        )
                        # 用策略mask覆盖默认的context_mask
                        assignment.context_mask = ContextMask(
                            allowed_evidence=policy_mask.get("allowed_evidence", assignment.context_mask.allowed_evidence),
                            blocked_evidence=policy_mask.get("blocked_evidence", assignment.context_mask.blocked_evidence),
                            allowed_domains=policy_mask.get("allowed_domains", assignment.context_mask.allowed_domains),
                            blocked_domains=policy_mask.get("blocked_domains", assignment.context_mask.blocked_domains),
                            abstraction_level=policy_mask.get("abstraction_level", assignment.context_mask.abstraction_level),
                        )
                    except (ValueError, KeyError) as e:
                        logger.warning(f"[CDoLEngine] 信息策略应用失败 for {agent_id}: {e}")
        else:
            plan = None
            # Phase 7: 即使有预设分配，也应用信息策略的context mask
            if self.information_policy:
                for assignment in assignments:
                    agent_id = assignment.agent_id
                    try:
                        policy_mask = self.information_policy.generate_context_mask(
                            agent_id, {"task": task_description}
                        )
                        assignment.context_mask = ContextMask(
                            allowed_evidence=policy_mask.get("allowed_evidence", assignment.context_mask.allowed_evidence),
                            blocked_evidence=policy_mask.get("blocked_evidence", assignment.context_mask.blocked_evidence),
                            allowed_domains=policy_mask.get("allowed_domains", assignment.context_mask.allowed_domains),
                            blocked_domains=policy_mask.get("blocked_domains", assignment.context_mask.blocked_domains),
                            abstraction_level=policy_mask.get("abstraction_level", assignment.context_mask.abstraction_level),
                        )
                    except (ValueError, KeyError):
                        pass  # 未知Agent，保持原有mask
        
        # Step 1: Round 0 — 各Agent独立推理
        round0_conclusions = self.comm_layer.run_round_0(
            assignments=assignments,
            agents=self.agents,
            task_description=task_description,
        )
        
        # 中间结论写入全局记忆池
        if self.memory_pool:
            for c in round0_conclusions:
                self.memory_pool.add_conclusion(c.agent_id, c)
        
        # Step 2: Round 1 — 差异归因
        round1_attributions = self.comm_layer.run_round_1(
            conclusions=round0_conclusions,
            assignments=assignments,
            agents=self.agents,
        )
        
        # Step 3: Round 2 — 修正结论
        round2_revised = self.comm_layer.run_round_2(
            attributions=round1_attributions,
            original_conclusions=round0_conclusions,
        )
        
        # Step 4: 融合判断
        judgment = self.judge.judge(round2_revised)
        
        # Step 5: 计算指标
        metrics = self._compute_metrics(
            round0_conclusions, round2_revised, judgment
        )
        
        result = CDoLResult(
            final_answer=judgment.final_answer,
            reasoning_tree=judgment.reasoning_tree,
            contradiction_report=judgment.contradiction_report,
            metrics=metrics,
            perspective_assignments=assignments,
            round0_conclusions=round0_conclusions,
            round1_attributions=round1_attributions,
            round2_revised=round2_revised,
            judgment=judgment,
            synergy_gain=metrics.get("synergy_gain", 1.0),
            information_policy_summary=policy_summary,
        )
        
        # P0: Insight提炼 — 从本次执行中提取可复用经验
        insight = self.distiller.distill(result, task_description)
        self.insight_store.add(insight)
        result.insights = insight  # 动态附加，不修改dataclass定义
        logger.info(
            f"[CDoLEngine] Insight提炼完成: "
            f"strategy={insight['strategy_effectiveness']['strategy']}, "
            f"synergy={insight['synergy_analysis']['assessment']}"
        )
        
        logger.info(
            f"[CDoLEngine] 执行完成: action={judgment.action}, "
            f"synergy_gain={metrics.get('synergy_gain', 1.0):.2f}"
        )
        
        return result
    
    def _compute_metrics(
        self,
        round0: List[IntermediateConclusion],
        revised: List[IntermediateConclusion],
        judgment: Judgment,
    ) -> Dict[str, float]:
        """计算认知分工的量化指标"""
        metrics = {}
        
        # 1. 平均置信度
        if round0:
            metrics["avg_confidence_r0"] = sum(c.confidence for c in round0) / len(round0)
        if revised:
            metrics["avg_confidence_revised"] = sum(c.confidence for c in revised) / len(revised)
        
        # 2. 修正率（Round 1中产生修正的比例）
        revision_count = sum(1 for c in revised if c.uncertainty_markers)
        metrics["revision_rate"] = revision_count / max(len(revised), 1)
        
        # 3. 矛盾类型分布
        if judgment.contradiction_report:
            summary = judgment.contradiction_report.get("types_summary", {})
            total = sum(summary.values()) or 1
            for ctype, count in summary.items():
                metrics[f"ratio_{ctype}"] = count / total
        
        # 4. 协同增益比（三分量加权公式，§4.1.5a）
        # synergy_gain = 0.4 × conclusion_delta + 0.3 × contradiction_resolution + 0.3 × confidence_delta
        
        # 4a. conclusion_delta: 结论修正幅度（round0→round2的推理链变化）
        avg_chain_depth = 0
        avg_revised_depth = 0
        if round0:
            avg_chain_depth = sum(len(c.reasoning_chain) for c in round0) / len(round0)
        if revised:
            avg_revised_depth = sum(len(c.reasoning_chain) for c in revised) / len(revised)
        metrics["avg_reasoning_depth"] = avg_chain_depth
        
        # 推理链增长归一化（上限2倍→映射到0-1）
        if avg_chain_depth > 0 and avg_revised_depth > 0:
            depth_ratio = avg_revised_depth / avg_chain_depth
            conclusion_delta = min(max((depth_ratio - 1.0), 0.0), 1.0)  # clip to [0,1]
        else:
            conclusion_delta = 0.0
        metrics["conclusion_delta"] = conclusion_delta
        
        # 4b. contradiction_resolution: 矛盾解决率（可归因矛盾占比）
        contradiction_resolution = 0.0
        if judgment.contradiction_report:
            total_pairs = judgment.contradiction_report.get("total_pairs", 0)
            if total_pairs > 0:
                types_summary = judgment.contradiction_report.get("types_summary", {})
                # attributable + true_convergence = resolved; unattributable + false_consensus = unresolved
                resolved = types_summary.get("attributable", 0) + types_summary.get("true_convergence", 0)
                contradiction_resolution = resolved / total_pairs
        metrics["contradiction_resolution"] = contradiction_resolution
        
        # 4c. confidence_delta: 置信度提升幅度
        avg_conf_r0 = sum(c.confidence for c in round0) / len(round0) if round0 else 0.5
        avg_conf_rev = sum(c.confidence for c in revised) / len(revised) if revised else 0.5
        # 归一化到0-1：最大提升0.5（从0.5到1.0）→ 映射到0-1
        confidence_delta = min(max((avg_conf_rev - avg_conf_r0) / 0.5, 0.0), 1.0)
        metrics["confidence_delta"] = confidence_delta
        
        # 三分量加权
        metrics["synergy_gain"] = (
            0.4 * conclusion_delta + 0.3 * contradiction_resolution + 0.3 * confidence_delta
        )
        
        # 5. 视角桥接度
        if judgment.contradiction_report:
            total_pairs = judgment.contradiction_report.get("total_pairs", 1)
            attributable = judgment.contradiction_report.get("types_summary", {}).get(
                "attributable", 0
            )
            metrics["bridgeability"] = attributable / max(total_pairs, 1)
        
        return metrics


# ============================================================================
# InsightDistiller — 结构化经验提炼器 (P0, 借鉴Arbor HTR)
# ============================================================================

class InsightDistiller:
    """从CDoL执行结果中提炼可复用的结构化insight
    
    借鉴Arbor的Distill()机制，适配CDoL横向协同场景。
    不是Arbor的纵向树回传，而是跨执行的经验积累：
    - 哪种策略在什么任务特征下效果好
    - 哪种矛盾模式频繁出现
    - 视角分解质量如何
    """
    
    def distill(self, result: CDoLResult, task_description: str = "") -> Dict[str, Any]:
        """从单次CDoL执行中提炼insight
        
        Args:
            result: CDoL执行结果
            task_description: 原始任务描述（用于分析任务特征）
            
        Returns:
            结构化insight字典
        """
        insights: Dict[str, Any] = {
            "task_type": self._classify_task(task_description),
            "strategy_effectiveness": self._analyze_strategy(result),
            "contradiction_patterns": self._analyze_contradictions(result),
            "decomposition_quality": self._analyze_decomposition(result),
            "synergy_analysis": self._analyze_synergy(result),
            "task_skills": self._extract_task_skills(result, task_description),  # 任务技能蒸馏
            "timestamp": time.time(),
        }
        return insights
    
    def _classify_task(self, task_desc: str) -> str:
        """根据任务描述分类任务类型"""
        if not task_desc:
            return "unknown"
        q = task_desc.lower()
        if any(kw in q for kw in ["实验", "数据", "evidence", "data"]):
            return "evidence_based"
        if any(kw in q for kw in ["假设", "验证", "hypothesis", "verify"]):
            return "hypothesis_driven"
        if any(kw in q for kw in ["设计", "方法", "design", "method"]):
            return "design_oriented"
        if any(kw in q for kw in ["对比", "评估", "compare", "evaluate"]):
            return "evaluation"
        return "general"
    
    def _analyze_strategy(self, result: CDoLResult) -> Dict[str, Any]:
        """分析本次策略有效性"""
        strategy = "unknown"
        if result.perspective_assignments:
            mask = result.perspective_assignments[0].context_mask
            strategy = mask.abstraction_level or "evidence_split"
        
        revision_rate = result.metrics.get("revision_rate", 0.0)
        
        return {
            "strategy": strategy,
            "effectiveness": result.synergy_gain,
            "revision_rate": revision_rate,
            "recommendation": (
                "increase_perspectives" if revision_rate < 0.3
                else "good_balance" if revision_rate < 0.7
                else "reduce_complexity"
            ),
        }
    
    def _analyze_contradictions(self, result: CDoLResult) -> Dict[str, Any]:
        """分析矛盾模式"""
        if not result.contradiction_report:
            return {"dominant_type": None, "false_consensus_detected": False}
        
        types = result.contradiction_report.get("types_summary", {})
        total = sum(types.values()) if types else 1
        
        dominant = max(types, key=types.get) if types else None
        false_consensus_count = types.get("false_consensus", 0)
        
        return {
            "dominant_type": dominant,
            "false_consensus_detected": false_consensus_count > 0,
            "distribution": {k: v / total for k, v in types.items()},
            "insight": self._contradiction_insight(types),
        }
    
    def _contradiction_insight(self, types: Dict[str, int]) -> str:
        """从矛盾分布生成自然语言insight"""
        if not types:
            return "无显著矛盾模式"
        
        total = sum(types.values())
        attributable = types.get("attributable", 0)
        false_consensus = types.get("false_consensus", 0)
        
        if false_consensus > total * 0.3:
            return "虚假一致频发——Agent答案相同但推理链矛盾，需增强ContextMask非对称性"
        if attributable > total * 0.7:
            return "可归因矛盾为主——视角分解有效，差异可从信息差异解释"
        return "矛盾类型分散——建议调整分解策略增强视角互补性"
    
    def _analyze_decomposition(self, result: CDoLResult) -> Dict[str, Any]:
        """分析视角分解质量"""
        bridgeability = result.metrics.get("bridgeability", 0.5)
        
        return {
            "bridgeability": bridgeability,
            "assessment": (
                "high_quality" if bridgeability > 0.7
                else "adequate" if bridgeability > 0.4
                else "needs_improvement"
            ),
        }
    
    def _analyze_synergy(self, result: CDoLResult) -> Dict[str, Any]:
        """分析协同增益来源"""
        synergy = result.synergy_gain
        revision_rate = result.metrics.get("revision_rate", 0.0)
        avg_depth = result.metrics.get("avg_reasoning_depth", 0.0)
        
        return {
            "synergy_gain": synergy,
            "revision_rate": revision_rate,
            "avg_reasoning_depth": avg_depth,
            "assessment": (
                "strong_synergy" if synergy > 1.3
                else "moderate" if synergy > 1.0
                else "no_synergy"
            ),
        }
    
    def _extract_task_skills(self, result: CDoLResult, task_description: str) -> Optional[Dict]:
        """从CDoL执行结果中提取科研任务技能（借鉴技能蒸馏范式）
        
        当任务涉及科研操作时，将成功执行的路径蒸馏为自然语言TaskSkillCard。
        仅在任务包含科研任务相关关键词时触发。
        """
        # 科研任务关键词
        task_keywords = ["文献", "论文", "学术", "检索", "搜索", "分析", "实验", 
                        "设计", "数据", "code", "paper", "research", "analysis"]
        
        if not any(kw in task_description.lower() for kw in task_keywords):
            return None  # 非科研任务，跳过
        
        # 仅当执行成功时提取
        if not result.final_answer or result.synergy_gain < 1.0:
            return None
        
        # 构建 TaskSkillCard
        skill_card = {
            "skill_id": f"skill_{int(time.time())}",
            "applicable_scenario": self._infer_task_scenario(task_description),
            "task_description": task_description,
            "execution_steps": self._extract_execution_path(result),
            "completion_criteria": self._infer_completion_criteria(result),
            "failure_handling": "如果执行失败，回顾推理过程并检查假设是否成立",
            "source": "InsightDistiller_auto_extraction",
            "timestamp": time.time(),
            "model_compatible": True,  # 自然语言格式，跨模型兼容
        }
        return skill_card
    
    def _infer_task_scenario(self, task_desc: str) -> str:
        """推断科研任务的适用场景"""
        # 文献综述/学术检索
        if any(kw in task_desc.lower() for kw in ["文献", "论文", "学术", "检索", "搜索", "review", "paper", "literature", "scholar", "arxiv", "pubmed"]):
            return "文献综述/学术检索"
        # 数据分析/实验处理
        if any(kw in task_desc.lower() for kw in ["数据", "分析", "实验", "统计", "处理", "data", "analysis", "experiment", "statistic", "process"]):
            return "数据分析/实验处理"
        # 实验设计/方案规划
        if any(kw in task_desc.lower() for kw in ["设计", "方案", "规划", "配方", "材料", "design", "experiment", "plan", "formula", "material"]):
            return "实验设计/方案规划"
        # 代码开发/工程实现
        if any(kw in task_desc.lower() for kw in ["代码", "编程", "开发", "实现", "调试", "code", "programming", "develop", "implement", "debug"]):
            return "代码开发/工程实现"
        # 信息检索/知识查询
        if any(kw in task_desc.lower() for kw in ["查询", "信息", "知识", "报告", "总结", "query", "information", "knowledge", "report", "summary"]):
            return "信息检索/知识查询"
        return "通用"
    
    def _extract_execution_path(self, result: CDoLResult) -> List[str]:
        """从执行结果中提取步骤序列"""
        steps = []
        if hasattr(result, 'communication_rounds') and result.communication_rounds:
            for round_data in result.communication_rounds:
                if hasattr(round_data, 'conclusions'):
                    for conclusion in round_data.conclusions:
                        if hasattr(conclusion, 'content') and conclusion.content:
                            steps.append(str(conclusion.content)[:200])
        if not steps:
            steps = ["根据任务目标导航到目标页面", "定位关键交互元素", "执行操作并验证结果"]
        return steps[:10]  # 限制步骤数量
    
    def _infer_completion_criteria(self, result: CDoLResult) -> List[str]:
        """推断任务完成标准"""
        criteria = ["页面状态符合预期", "操作结果已验证"]
        if result.synergy_gain > 1.2:
            criteria.append("多Agent交叉验证通过")
        return criteria


class InsightStore:
    """Insight持久化存储
    
    支持内存列表和JSON文件两种模式。
    为PerspectiveDecomposer提供历史经验反馈。
    """
    
    def __init__(self, filepath: Optional[str] = None):
        """
        Args:
            filepath: JSON文件路径。None时仅内存存储。
        """
        self.filepath = filepath
        self.insights: List[Dict[str, Any]] = []
        if filepath:
            self._load()
    
    def add(self, insight: Dict[str, Any]) -> None:
        """添加一条insight并持久化"""
        self.insights.append(insight)
        if self.filepath:
            self._save()
    
    def get_best_strategy(self, task_type: str = "general") -> Optional[str]:
        """根据历史insight推荐最佳策略
        
        Args:
            task_type: 任务类型，用于筛选相似场景
            
        Returns:
            推荐的策略名称，无历史数据时返回None
        """
        # 按任务类型筛选（优先同类型，不够则用全部）
        relevant = [
            i for i in self.insights
            if i.get("task_type") == task_type
        ]
        if len(relevant) < 3:
            relevant = self.insights
        if not relevant:
            return None
        
        # 统计各策略加权得分
        scores: Dict[str, List[float]] = {}
        for ins in relevant:
            se = ins.get("strategy_effectiveness", {})
            if se:
                name = se.get("strategy", "unknown")
                eff = se.get("effectiveness", 0.5)
                scores.setdefault(name, []).append(eff)
        
        if not scores:
            return None
        
        # 加权平均 + 探索奖励（少用的策略有小bonus）
        best_score, best_name = -1.0, None
        total = len(relevant)
        for name, vals in scores.items():
            avg = sum(vals) / len(vals)
            exploration_bonus = 0.05 * (1.0 - len(vals) / total)
            final = avg + exploration_bonus
            if final > best_score:
                best_score, best_name = final, name
        
        return best_name
    
    def get_stats(self) -> Dict[str, Any]:
        """获取insight库统计摘要"""
        if not self.insights:
            return {"count": 0}
        
        strategy_counts: Dict[str, int] = {}
        total_synergy = 0.0
        task_skill_count = 0
        for ins in self.insights:
            se = ins.get("strategy_effectiveness", {})
            s = se.get("strategy", "unknown")
            strategy_counts[s] = strategy_counts.get(s, 0) + 1
            total_synergy += se.get("effectiveness", 0.5)
            if ins.get("task_skills") is not None:
                task_skill_count += 1
        
        return {
            "count": len(self.insights),
            "strategy_distribution": strategy_counts,
            "avg_synergy_gain": total_synergy / len(self.insights),
            "task_skills_count": task_skill_count,  # 任务技能蒸馏统计
        }
    
    def _load(self) -> None:
        """从JSON加载"""
        import json as _json
        try:
            with open(self.filepath, "r", encoding="utf-8") as f:
                self.insights = _json.load(f)
        except (FileNotFoundError, _json.JSONDecodeError):
            self.insights = []
    
    def _save(self) -> None:
        """保存到JSON"""
        import json as _json
        try:
            with open(self.filepath, "w", encoding="utf-8") as f:
                _json.dump(self.insights, f, ensure_ascii=False, indent=2)
        except OSError as e:
            logger.warning(f"[InsightStore] 保存失败: {e}")
    
    def get_task_skills(self, task_type: str = None, top_k: int = 3) -> List[Dict]:
        """检索相关任务技能卡（借鉴TaskSkillCard格式）
        
        Args:
            task_type: 任务场景类型（如"文献综述"、"数据分析"），None则返回全部
            top_k: 返回最相关的k个技能卡
        
        Returns:
            TaskSkillCard列表，按相关性排序
        """
        task_skills = [
            ins.get("task_skills") 
            for ins in self.insights 
            if ins.get("task_skills") is not None
        ]
        
        if not task_skills:
            return []
        
        if task_type:
            # 按场景类型过滤
            relevant = [
                s for s in task_skills 
                if task_type.lower() in s.get("applicable_scenario", "").lower()
            ]
            if relevant:
                task_skills = relevant
        
        # 按时间倒序（最新优先）
        task_skills.sort(key=lambda s: s.get("timestamp", 0), reverse=True)
        return task_skills[:top_k]
    
    def add_task_skill(self, skill: Dict) -> None:
        """存储任务技能卡（通常由InsightDistiller调用）"""
        # 查找对应的insight并添加task_skills字段
        # 如果没有对应insight，创建新的
        insight_with_skill = {
            "task_type": "research_task",
            "task_skills": skill,
            "timestamp": time.time(),
        }
        self.add(insight_with_skill)
    
    def get_skill_count(self) -> int:
        """获取已存储的任务技能数量"""
        return sum(1 for ins in self.insights if ins.get("task_skills") is not None)


# ============================================================================
# 便捷函数
# ============================================================================

def create_cdol_engine(
    agents: Optional[Dict[str, Any]] = None,
    memory_pool: Optional[Any] = None,
    llm_chat: Optional[Callable] = None,
    insight_store: Optional[Any] = None,
) -> CognitiveDivisionEngine:
    """创建认知分工引擎的工厂函数
    
    Args:
        agents: agent_id -> agent对象 的映射
        memory_pool: GlobalMemoryPool实例
        llm_chat: LLM调用函数
        insight_store: InsightStore实例（可选，用于跨执行经验积累）
    """
    return CognitiveDivisionEngine(
        agents=agents,
        memory_pool=memory_pool,
        llm_chat=llm_chat,
        insight_store=insight_store,
    )
