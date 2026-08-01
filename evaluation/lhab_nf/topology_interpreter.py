"""
Topology Interpreter
=====================
Generates human-readable explanations for routing decisions.
Makes the dynamic topology router interpretable and debuggable.
"""

from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field
import json


@dataclass
class FactorContribution:
    """单个因子的贡献度"""
    factor_name: str
    contribution: float          # -1.0 到 1.0（负=不利因素，正=有利因素）
    weight: float                # 该因子在决策中的权重
    description: str             # 人类可读描述
    affected_agents: List[str] = field(default_factory=list)


@dataclass
class AlternativeOption:
    """备选方案"""
    plan_id: str
    agent_chain: List[str]
    topology_type: str
    score: float
    reason_rejected: str


@dataclass
class RoutingExplanation:
    """路由决策的完整解释"""
    plan_id: str
    decision_summary: str                    # 一句话总结
    factor_breakdown: List[FactorContribution]  # 因子分析
    alternatives: List[AlternativeOption]    # 备选方案
    confidence_factors: List[str]            # 影响置信度的因素
    bottlenecks: List[str]                   # 识别的瓶颈
    human_readable: str                      # 完整自然语言解释
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict:
        return {
            "plan_id": self.plan_id,
            "decision_summary": self.decision_summary,
            "factor_breakdown": [
                {
                    "factor": f.factor_name,
                    "contribution": f.contribution,
                    "weight": f.weight,
                    "description": f.description,
                    "agents": f.affected_agents,
                }
                for f in self.factor_breakdown
            ],
            "alternatives": [
                {
                    "plan_id": a.plan_id,
                    "chain": a.agent_chain,
                    "topology": a.topology_type,
                    "score": a.score,
                    "reason": a.reason_rejected,
                }
                for a in self.alternatives
            ],
            "confidence_factors": self.confidence_factors,
            "bottlenecks": self.bottlenecks,
            "human_readable": self.human_readable,
        }
    
    def to_markdown(self) -> str:
        """生成 Markdown 格式的解释报告"""
        lines = [
            f"# 路由决策解释: {self.plan_id}",
            "",
            f"## 决策摘要",
            self.decision_summary,
            "",
            "## 因子分析",
        ]
        
        for f in sorted(self.factor_breakdown, key=lambda x: abs(x.contribution), reverse=True):
            emoji = "✅" if f.contribution > 0 else "❌" if f.contribution < 0 else "⚠️"
            lines.append(f"- {emoji} **{f.factor_name}** (贡献: {f.contribution:+.2f}, 权重: {f.weight:.2f})")
            lines.append(f"  - {f.description}")
            if f.affected_agents:
                lines.append(f"  - 影响: {', '.join(f.affected_agents)}")
        
        if self.alternatives:
            lines.extend([
                "",
                "## 备选方案",
            ])
            for i, alt in enumerate(self.alternatives, 1):
                lines.append(f"### 方案 {i}: {alt.plan_id} (评分: {alt.score:.3f})")
                lines.append(f"- Agent 链: {' → '.join(alt.agent_chain)}")
                lines.append(f"- 拓扑类型: {alt.topology_type}")
                lines.append(f"- 未选择原因: {alt.reason_rejected}")
        
        if self.bottlenecks:
            lines.extend([
                "",
                "## 识别的瓶颈",
            ])
            for b in self.bottlenecks:
                lines.append(f"- ⚠️ {b}")
        
        lines.extend([
            "",
            "## 完整解释",
            self.human_readable,
        ])
        
        return "\n".join(lines)


class TopologyInterpreter:
    """
    拓扑解释器
    
    分析路由决策，生成人类可读的解释。
    """
    
    def __init__(self):
        self.explanation_history: List[RoutingExplanation] = []
    
    def explain(self, plan: Any, task: Any, candidates: List[Any] = None, 
                edge_weights: Dict = None) -> RoutingExplanation:
        """
        生成路由决策的解释
        
        Args:
            plan: RoutePlan 对象
            task: TaskRequirement 对象
            candidates: 候选 Agent 列表
            edge_weights: 边权重字典 {(src, dst): weight}
        
        Returns:
            RoutingExplanation 对象
        """
        # 1. 生成决策摘要
        summary = self._generate_summary(plan, task)
        
        # 2. 分析因子贡献
        factors = self._analyze_factors(plan, task, candidates, edge_weights)
        
        # 3. 生成备选方案
        alternatives = self._generate_alternatives(plan, candidates)
        
        # 4. 识别置信度因素
        confidence_factors = self._identify_confidence_factors(plan, task)
        
        # 5. 识别瓶颈
        bottlenecks = self._identify_bottlenecks(plan, edge_weights)
        
        # 6. 生成自然语言解释
        human_readable = self._generate_narrative(
            plan, task, summary, factors, alternatives, bottlenecks
        )
        
        explanation = RoutingExplanation(
            plan_id=plan.plan_id,
            decision_summary=summary,
            factor_breakdown=factors,
            alternatives=alternatives,
            confidence_factors=confidence_factors,
            bottlenecks=bottlenecks,
            human_readable=human_readable,
            metadata={
                "task_id": task.task_id,
                "task_complexity": task.complexity.name if hasattr(task.complexity, 'name') else str(task.complexity),
                "agent_count": len(plan.agent_chain),
                "topology_type": plan.topology_type,
                "estimated_cost": plan.estimated_cost,
                "estimated_latency_ms": plan.estimated_latency_ms,
                "confidence": plan.confidence,
            }
        )
        
        self.explanation_history.append(explanation)
        return explanation
    
    def _generate_summary(self, plan: Any, task: Any) -> str:
        """生成一句话决策摘要"""
        chain_str = " → ".join(plan.agent_chain[:5])
        if len(plan.agent_chain) > 5:
            chain_str += f" ... (共{len(plan.agent_chain)}个)"
        
        topology_names = {
            "sequential": "串行",
            "parallel": "并行",
            "hybrid": "混合",
            "star": "星型",
            "dynamic": "动态",
        }
        topology_cn = topology_names.get(plan.topology_type, plan.topology_type)
        
        return (
            f"为任务选择{topology_cn}拓扑，"
            f"由 {len(plan.agent_chain)} 个 Agent 协作执行："
            f"{chain_str}。"
            f"预估延迟 {plan.estimated_latency_ms/1000:.1f}s，"
            f"置信度 {plan.confidence:.1%}。"
        )
    
    def _analyze_factors(self, plan: Any, task: Any, 
                         candidates: List[Any] = None,
                         edge_weights: Dict = None) -> List[FactorContribution]:
        """分析各因子对决策的贡献"""
        factors = []
        
        # 1. 能力匹配度
        if candidates:
            avg_capability_score = sum(
                self._capability_match_score(c, task) for c in candidates[:len(plan.agent_chain)]
            ) / max(1, len(plan.agent_chain))
            
            factors.append(FactorContribution(
                factor_name="能力匹配度",
                contribution=avg_capability_score,
                weight=0.35,
                description=f"候选 Agent 与任务需求的平均能力匹配度为 {avg_capability_score:.2f}",
                affected_agents=plan.agent_chain,
            ))
        
        # 2. 负载状态
        if candidates:
            avg_load_score = sum(c.compute_score() for c in candidates[:len(plan.agent_chain)]) / max(1, len(plan.agent_chain))
            load_factor = (avg_load_score - 0.5) * 2  # 归一化到 [-1, 1]
            
            factors.append(FactorContribution(
                factor_name="负载状态",
                contribution=load_factor,
                weight=0.25,
                description=f"选中 Agent 的平均可用性评分为 {avg_load_score:.2f}（0=不可用，1=最佳）",
                affected_agents=plan.agent_chain,
            ))
        
        # 3. 跨层通信成本
        if candidates:
            tiers = [c.tier for c in candidates[:len(plan.agent_chain)]]
            cross_tier_count = len(set(tiers)) - 1
            if cross_tier_count > 0:
                penalty = -0.3 * cross_tier_count
                factors.append(FactorContribution(
                    factor_name="跨层通信",
                    contribution=penalty,
                    weight=0.15,
                    description=f"涉及 {cross_tier_count + 1} 个部署层（{', '.join(set(tiers))}），增加跨层通信延迟",
                    affected_agents=plan.agent_chain,
                ))
        
        # 4. 协作偏好
        if candidates and len(candidates) > 1:
            preference_matches = 0
            for i in range(len(plan.agent_chain) - 1):
                src = next((c for c in candidates if c.agent_id == plan.agent_chain[i]), None)
                dst = next((c for c in candidates if c.agent_id == plan.agent_chain[i+1]), None)
                if src and dst and dst.agent_id in src.preferred_partners:
                    preference_matches += 1
            
            if preference_matches > 0:
                factors.append(FactorContribution(
                    factor_name="协作偏好",
                    contribution=0.2 * preference_matches,
                    weight=0.15,
                    description=f"{preference_matches} 对相邻 Agent 存在协作偏好，降低协作成本",
                    affected_agents=plan.agent_chain,
                ))
        
        # 5. 延迟约束
        if hasattr(task, 'latency_budget_ms') and task.latency_budget_ms:
            if plan.estimated_latency_ms > task.latency_budget_ms:
                factors.append(FactorContribution(
                    factor_name="延迟约束",
                    contribution=-0.5,
                    weight=0.10,
                    description=f"预估延迟 {plan.estimated_latency_ms:.0f}ms 超出预算 {task.latency_budget_ms:.0f}ms",
                ))
            else:
                margin = (task.latency_budget_ms - plan.estimated_latency_ms) / task.latency_budget_ms
                factors.append(FactorContribution(
                    factor_name="延迟约束",
                    contribution=margin * 0.3,
                    weight=0.10,
                    description=f"预估延迟在预算内，余量 {margin:.1%}",
                ))
        
        return factors
    
    def _generate_alternatives(self, plan: Any, candidates: List[Any] = None) -> List[AlternativeOption]:
        """生成备选方案"""
        alternatives = []
        
        if not candidates or len(candidates) < 2:
            return alternatives
        
        # 生成 2-3 个备选方案（简化版）
        # 实际应该基于不同的拓扑类型或 Agent 组合
        
        # 备选 1: 最短链（最少 Agent）
        if len(plan.agent_chain) > 2:
            short_chain = plan.agent_chain[:2]
            alternatives.append(AlternativeOption(
                plan_id=f"{plan.plan_id}_alt_short",
                agent_chain=short_chain,
                topology_type="sequential",
                score=plan.confidence * 0.85,  # 预估置信度较低
                reason_rejected="Agent 数量不足，可能无法覆盖所有任务需求",
            ))
        
        # 备选 2: 并行拓扑
        if plan.topology_type == "sequential" and len(plan.agent_chain) >= 3:
            alternatives.append(AlternativeOption(
                plan_id=f"{plan.plan_id}_alt_parallel",
                agent_chain=plan.agent_chain[:3],
                topology_type="parallel",
                score=plan.confidence * 0.90,
                reason_rejected="并行拓扑可能增加协调开销，当前任务更适合串行",
            ))
        
        return alternatives[:3]  # 最多 3 个备选
    
    def _identify_confidence_factors(self, plan: Any, task: Any) -> List[str]:
        """识别影响置信度的因素"""
        factors = []
        
        if plan.confidence < 0.5:
            factors.append("候选 Agent 能力匹配度较低")
        
        if plan.estimated_latency_ms > 30000:
            factors.append("预估延迟较长，增加不确定性")
        
        if hasattr(task, 'complexity'):
            complexity_val = task.complexity.value if hasattr(task.complexity, 'value') else 3
            if complexity_val >= 4:
                factors.append("任务复杂度高，执行路径不确定性增大")
        
        if not factors:
            factors.append("各项指标正常，置信度可靠")
        
        return factors
    
    def _identify_bottlenecks(self, plan: Any, edge_weights: Dict = None) -> List[str]:
        """识别瓶颈"""
        bottlenecks = []
        
        if not edge_weights:
            return bottlenecks
        
        # 找出权重最高的边
        max_weight = 0
        max_edge = None
        for (src, dst), weight in edge_weights.items():
            if src in plan.agent_chain and dst in plan.agent_chain:
                if weight > max_weight:
                    max_weight = weight
                    max_edge = (src, dst)
        
        if max_edge and max_weight > 2.0:
            bottlenecks.append(
                f"Agent {max_edge[0]} → {max_edge[1]} 协作成本较高（权重 {max_weight:.2f}），"
                f"可能成为性能瓶颈"
            )
        
        # 检查是否有过载 Agent
        # (需要 candidates 信息，这里简化)
        
        return bottlenecks
    
    def _generate_narrative(self, plan: Any, task: Any, summary: str,
                           factors: List[FactorContribution],
                           alternatives: List[AlternativeOption],
                           bottlenecks: List[str]) -> str:
        """生成完整自然语言解释"""
        parts = [summary, ""]
        
        # 因子分析
        parts.append("决策因素分析：")
        positive_factors = [f for f in factors if f.contribution > 0]
        negative_factors = [f for f in factors if f.contribution < 0]
        
        if positive_factors:
            parts.append("有利因素：")
            for f in positive_factors[:3]:
                parts.append(f"  • {f.description}")
        
        if negative_factors:
            parts.append("不利因素：")
            for f in negative_factors[:3]:
                parts.append(f"  • {f.description}")
        
        # 备选方案
        if alternatives:
            parts.append("")
            parts.append(f"同时考虑了 {len(alternatives)} 个备选方案，但均未采用：")
            for alt in alternatives[:2]:
                parts.append(f"  • {alt.reason_rejected}")
        
        # 瓶颈
        if bottlenecks:
            parts.append("")
            parts.append("潜在瓶颈：")
            for b in bottlenecks:
                parts.append(f"  ⚠️ {b}")
        
        return "\n".join(parts)
    
    def _capability_match_score(self, candidate: Any, task: Any) -> float:
        """计算能力匹配度（简化版）"""
        if not hasattr(task, 'required_capabilities') or not task.required_capabilities:
            return 0.5  # 无明确要求时给中等分
        
        match_count = sum(1 for cap in task.required_capabilities if cap in candidate.capabilities)
        return match_count / max(1, len(task.required_capabilities))
