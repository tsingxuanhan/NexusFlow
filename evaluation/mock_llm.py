"""
Mock LLM 响应生成模块

为100步超长程任务提供Mock LLM响应，支持：
1. 置信度随步数衰减（CDoL OFF时衰减更明显）
2. 在关键决策点生成可检测的虚假一致
3. 多Agent视角分离模拟
"""

import random
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, Any
from enum import Enum


class AgentType(Enum):
    """Agent类型枚举"""
    MINER = "Miner"       # 实验数据视角
    ASSAYER = "Assayer"   # 理论分析视角
    EVALUATOR = "Evaluator"  # 综合评估视角


@dataclass
class MockResponse:
    """Mock LLM响应"""
    agent_id: str
    step_num: int
    content: str
    confidence: float           # 置信度 (0-1)
    reasoning_depth: int         # 推理链深度
    insights: List[str]          # 关键洞察
    recommended_formula: str      # 推荐配方
    recommendation_strength: float  # 推荐强度 (0-1)
    context_usable: bool          # 上下文是否可用
    is_reliable: bool            # 是否可靠
    raw_reasoning: List[str]     # 原始推理链
    
    def to_dict(self) -> Dict:
        """转换为字典"""
        return {
            "agent_id": self.agent_id,
            "step_num": self.step_num,
            "content": self.content,
            "confidence": self.confidence,
            "reasoning_depth": self.reasoning_depth,
            "insights": self.insights,
            "recommended_formula": self.recommended_formula,
            "recommendation_strength": self.recommendation_strength,
            "context_usable": self.context_usable,
            "is_reliable": self.is_reliable,
            "raw_reasoning": self.raw_reasoning
        }


@dataclass
class FalseConsensusCase:
    """虚假一致案例"""
    agents_involved: List[str]
    surface_consensus: str       # 表面一致的结论
    hidden_disagreement: str      # 隐藏的分歧
    root_cause: str               # 根本原因
    detection_method: str        # 检测方法
    cdol_resolution: str         # CDoL解决方案


class MockLLM100Steps:
    """
    100步场景Mock LLM
    
    关键设计: 
    - 支持步数影响的置信度衰减
    - 在关键决策点生成可检测的虚假一致
    """
    
    # Agent配置（基础参数）
    AGENT_CONFIGS = {
        "Miner": {
            "base_confidence": 0.82,
            "base_depth": 5,
            "perspective": "实验数据视角",
            "focus": ["实验强度数据", "成本数据", "误差分析"],
            "blind_spot": ["理论模型", "LCA结果", "长期趋势"]
        },
        "Assayer": {
            "base_confidence": 0.75,
            "base_depth": 4,
            "perspective": "理论分析视角",
            "focus": ["动力学模型", "LCA结果", "文献趋势"],
            "blind_spot": ["原始实验数字", "成本明细", "误差范围"]
        },
        "Evaluator": {
            "base_confidence": 0.70,
            "base_depth": 3,
            "perspective": "综合评估视角",
            "focus": ["多维度评分", "敏感性分析", "风险评估"],
            "blind_spot": ["具体数值", "细节数据", "实验条件"]
        }
    }
    
    # 虚假一致检测点配置
    FALSE_CONSENSUS_POINTS = ["D2"]  # D2决策点检测虚假一致
    
    def __init__(self, cdol_mode: bool = True, seed: int = 42):
        """
        初始化Mock LLM
        
        Args:
            cdol_mode: 是否启用CDoL模式
            seed: 随机种子（保证可复现）
        """
        self.cdol_mode = cdol_mode
        random.seed(seed)
        
        # 各Agent的上下文记忆容量（视角分离后容量增加）
        if cdol_mode:
            # CDoL ON: 每个Agent只关注自己的视角，信息量可控
            self.context_capacity = 200  # 上下文容量（相对值）
        else:
            # CDoL OFF: 全局共享上下文，100步远超容量
            self.context_capacity = 50   # 上下文容量（相对值）
    
    def _calculate_decay(self, step_num: int, agent_id: str) -> Tuple[float, int]:
        """
        计算置信度和推理深度衰减
        
        Args:
            step_num: 当前步数
            agent_id: Agent ID
            
        Returns:
            (衰减后置信度, 衰减后推理深度)
        """
        base_config = self.AGENT_CONFIGS[agent_id]
        base_conf = base_config["base_confidence"]
        base_depth = base_config["base_depth"]
        
        # 衰减因子计算（CDoL OFF时衰减更明显）
        if self.cdol_mode:
            # CDoL ON: 视角分离，衰减较慢
            decay_factor = 1.0 - (step_num / 250)
            depth_decay = step_num / 40  # 每40步降1级
        else:
            # CDoL OFF: 上下文遗忘，衰减较快
            decay_factor = 1.0 - (step_num / 120)  # 更快的衰减
            depth_decay = step_num / 25  # 每25步降1级
        
        # 确保衰减后置信度不低于最低值
        min_confidence = 0.45 if self.cdol_mode else 0.30
        decay_confidence = max(min_confidence, base_conf * decay_factor)
        
        # 推理深度衰减
        decay_depth = max(2, base_depth - int(depth_decay))
        
        return decay_confidence, decay_depth
    
    def _check_false_consensus(self, step_num: int, decision_id: str) -> Optional[FalseConsensusCase]:
        """检查是否在虚假一致点"""
        if decision_id in self.FALSE_CONSENSUS_POINTS and not self.cdol_mode:
            # CDoL OFF模式在D2点会出现虚假一致
            return FalseConsensusCase(
                agents_involved=["Miner", "Evaluator"],
                surface_consensus="推荐15%NM",
                hidden_disagreement="Miner基于数据支持NM，Evaluator忽略LS价值",
                root_cause="两Agent看到相同数据表面一致，但Assayer的反对揭示深层矛盾",
                detection_method="Assayer基于理论模型反对，揭示虚假一致",
                cdol_resolution="生成条件依赖型方案（3场景），而非强制NM胜出"
            )
        return None
    
    def generate_for_step(
        self, 
        step_num: int, 
        agent_id: str,
        decision_id: Optional[str] = None,
        round_num: int = 0,
        previous_responses: Optional[List[MockResponse]] = None
    ) -> MockResponse:
        """
        根据步数生成Mock响应
        
        Args:
            step_num: 当前步数
            agent_id: Agent ID
            decision_id: 决策点ID（如果有）
            round_num: 当前轮次
            previous_responses: 前几轮的响应（用于归因）
            
        Returns:
            MockResponse对象
        """
        config = self.AGENT_CONFIGS[agent_id]
        confidence, depth = self._calculate_decay(step_num, agent_id)
        
        # 上下文可用性判断
        context_usable = step_num < self.context_capacity
        
        # 生成内容
        if decision_id:
            content, formula, strength, insights, reasoning = self._generate_decision_content(
                agent_id, decision_id, round_num, previous_responses, confidence
            )
        else:
            content, formula, strength, insights, reasoning = self._generate_regular_content(
                agent_id, step_num, confidence
            )
        
        return MockResponse(
            agent_id=agent_id,
            step_num=step_num,
            content=content,
            confidence=confidence,
            reasoning_depth=depth,
            insights=insights,
            recommended_formula=formula,
            recommendation_strength=strength,
            context_usable=context_usable,
            is_reliable=context_usable and confidence > 0.5,
            raw_reasoning=reasoning
        )
    
    def _generate_decision_content(
        self,
        agent_id: str,
        decision_id: str,
        round_num: int,
        previous_responses: Optional[List[MockResponse]],
        confidence: float
    ) -> Tuple[str, str, float, List[str], List[str]]:
        """为决策点生成内容"""
        
        if decision_id == "D2":
            return self._generate_d2_content(agent_id, round_num, previous_responses, confidence)
        elif decision_id == "D1":
            return self._generate_d1_content(agent_id, round_num, previous_responses, confidence)
        elif decision_id == "D3":
            return self._generate_d3_content(agent_id, round_num, previous_responses, confidence)
        
        # 默认
        return self._generate_d2_content(agent_id, round_num, previous_responses, confidence)
    
    def _generate_d2_content(
        self,
        agent_id: str,
        round_num: int,
        previous_responses: Optional[List[MockResponse]],
        confidence: float
    ) -> Tuple[str, str, float, List[str], List[str]]:
        """D2决策点内容生成（最优配方初选）"""
        
        # Round 0: 独立推理
        if round_num == 0:
            if agent_id == "Miner":
                return self._miner_round0_d2(confidence)
            elif agent_id == "Assayer":
                return self._assayer_round0_d2(confidence)
            elif agent_id == "Evaluator":
                return self._evaluator_round0_d2(confidence)
        
        # Round 1: 差异归因
        elif round_num == 1:
            if agent_id == "Miner":
                return self._miner_round1_d2(confidence, previous_responses)
            elif agent_id == "Assayer":
                return self._assayer_round1_d2(confidence, previous_responses)
            elif agent_id == "Evaluator":
                return self._evaluator_round1_d2(confidence, previous_responses)
        
        # Round 2: 修正收敛
        elif round_num == 2:
            if agent_id == "Miner":
                return self._miner_round2_d2(confidence)
            elif agent_id == "Assayer":
                return self._assayer_round2_d2(confidence)
            elif agent_id == "Evaluator":
                return self._evaluator_round2_d2(confidence)
        
        return self._miner_round0_d2(confidence)
    
    def _miner_round0_d2(self, confidence: float) -> Tuple[str, str, float, List[str], List[str]]:
        """Miner Round 0"""
        content = (
            "基于实验数据(Step 41-65)，15%NM+5%LS配方28d抗压强度达到48MPa，"
            "比基准OPC提升20%。实验组一致性良好(CV<5%)，数据可信度高。"
            "建议以此作为核心配方进行优化。"
        )
        formula = "15%NM + 5%LS"
        strength = 0.82
        insights = [
            "实验数据显示NM对早期强度贡献显著",
            "LS在5%掺量下无负面影响",
            "复配样品孔结构优于单掺"
        ]
        reasoning = [
            "观察: 实验数据(15%NM+5%LS)强度最优",
            "假设: NM的火山灰效应与LS的晶核作用产生协同",
            "验证: 28d强度48MPa，超过预期",
            "结论: 推荐15%NM+5%LS为核心配方"
        ]
        return content, formula, strength, insights, reasoning
    
    def _assayer_round0_d2(self, confidence: float) -> Tuple[str, str, float, List[str], List[str]]:
        """Assayer Round 0"""
        content = (
            "基于动力学模型和文献趋势分析，LS(20%)在全生命周期内表现最优。"
            "虽然NM早期强度好，但考虑到碳化硬化过程的长期稳定性，"
            "建议优先考虑LS优势方向。理论推导表明，LS掺量可进一步提高。"
        )
        formula = "20%LS + 0.5%早强剂"
        strength = 0.75
        insights = [
            "动力学模型显示LS长期反应更稳定",
            "碳化硬化理论支持高LS掺量",
            "但早期强度需通过早强剂补偿"
        ]
        reasoning = [
            "理论: LS碳化硬化可持续数十年",
            "模型: NM火山灰反应存在后期放缓现象",
            "预测: LS方案全生命周期LCA更优",
            "结论: 推荐20%LS为主攻方向"
        ]
        return content, formula, strength, insights, reasoning
    
    def _evaluator_round0_d2(self, confidence: float) -> Tuple[str, str, float, List[str], List[str]]:
        """Evaluator Round 0"""
        content = (
            "综合多维度评估，15%NM方案在TOPSIS评价中得分最高(0.82)。"
            "考虑早期强度、28d强度、成本、环保性的加权得分，"
            "推荐以15%NM为基础进行优化。LS作为辅助添加。"
        )
        formula = "15%NM + 5%LS (与Miner一致)"
        strength = 0.70
        insights = [
            "TOPSIS综合评分15%NM最高",
            "早期强度是重要加分项",
            "成本因素影响权重适中"
        ]
        reasoning = [
            "数据: 多维度评分矩阵显示15%NM优势",
            "权重: 早期强度权重30%，经济性25%",
            "计算: 15%NM综合得分0.82",
            "结论: 推荐15%NM为基础方案"
        ]
        return content, formula, strength, insights, reasoning
    
    def _miner_round1_d2(
        self, 
        confidence: float,
        previous_responses: Optional[List[MockResponse]]
    ) -> Tuple[str, str, float, List[str], List[str]]:
        """Miner Round 1: 归因分析"""
        content = (
            "重新审视Assayer的理论分析后，承认早期强度优势可能部分源于实验条件。"
            "LS的长期耐久性数据被低估。建议修正配方，接受LS掺量可适当提高的观点。"
        )
        formula = "12%NM + 8%LS"
        strength = 0.78
        insights = [
            "Assayer的模型提示实验条件可能有偏差",
            "LS的长期价值被初期数据低估",
            "修正: 提高LS掺量至8%"
        ]
        reasoning = [
            "回顾: Assayer质疑实验数据代表性",
            "反思: 实验样本量有限(N=15)",
            "调整: 接受LS价值，上调掺量",
            "修正结论: 12%NM + 8%LS"
        ]
        return content, formula, strength, insights, reasoning
    
    def _assayer_round1_d2(
        self,
        confidence: float,
        previous_responses: Optional[List[MockResponse]]
    ) -> Tuple[str, str, float, List[str], List[str]]:
        """Assayer Round 1: 归因分析"""
        content = (
            "理解Miner强调的实验数据价值后，承认早期强度确实是不可忽视的约束。"
            "修正观点: 维持LS优势，但接受复配方案。理论模型需要纳入早期强度约束。"
        )
        formula = "15%NM + 5%LS (修正后)"
        strength = 0.72
        insights = [
            "Miner数据揭示早期强度不可忽视",
            "修正理论模型以纳入早期约束",
            "接受复配优于纯LS的理论"
        ]
        reasoning = [
            "数据: Miner实验数据显示早期强度关键",
            "修正: 理论模型需考虑早期性能",
            "调整: 接受复配方案理论基础",
            "新结论: 15%NM+5%LS可接受"
        ]
        return content, formula, strength, insights, reasoning
    
    def _evaluator_round1_d2(
        self,
        confidence: float,
        previous_responses: Optional[List[MockResponse]]
    ) -> Tuple[str, str, float, List[str], List[str]]:
        """Evaluator Round 1: 归因分析"""
        content = (
            "识别到与Miner的表面一致可能掩盖了深层问题。"
            "Assayer的反对揭示了我们的共同盲点: 忽视了LS的长期价值。"
            "需要生成条件依赖型方案，而非单一结论。"
        )
        formula = "条件依赖型方案(3场景)"
        strength = 0.68
        insights = [
            "⚠️ 发现潜在虚假一致(Miner↔Evaluator)",
            "Assayer反对揭示深层矛盾",
            "决策: 生成多场景方案而非强制统一"
        ]
        reasoning = [
            "发现: Miner和我都推荐NM，表面一致",
            "质疑: Assayer反对，说明有深层矛盾",
            "原因: 我们都忽视了LS长期价值",
            "决策: 生成条件依赖型方案"
        ]
        return content, formula, strength, insights, reasoning
    
    def _miner_round2_d2(self, confidence: float) -> Tuple[str, str, float, List[str], List[str]]:
        """Miner Round 2: 修正收敛"""
        content = "综合两轮讨论，修正为: 接受12-15%NM为最优范围，具体根据场景确定。"
        formula = "12-15%NM + 5-8%LS"
        strength = 0.80
        insights = ["收敛: 接受NM最优范围12-15%", "保留LS调整空间"]
        reasoning = ["Round 1-2收敛", "共识: NM范围12-15%, LS 5-8%"]
        return content, formula, strength, insights, reasoning
    
    def _assayer_round2_d2(self, confidence: float) -> Tuple[str, str, float, List[str], List[str]]:
        """Assayer Round 2: 修正收敛"""
        content = "接受复配方案理论可行性。最终推荐考虑长期耐久性，NM控制在15%以下。"
        formula = "13%NM + 7%LS"
        strength = 0.78
        insights = ["收敛: 接受13%NM+7%LS作为平衡点"]
        reasoning = ["Round 1-2收敛", "共识: 13%NM+7%LS平衡点"]
        return content, formula, strength, insights, reasoning
    
    def _evaluator_round2_d2(self, confidence: float) -> Tuple[str, str, float, List[str], List[str]]:
        """Evaluator Round 2: 修正收敛"""
        content = "综合三方收敛结果，生成条件依赖型方案，覆盖3种应用场景。"
        formula = "场景A/B/C"
        strength = 0.75
        insights = ["收敛: 生成3场景条件方案"]
        reasoning = ["Round 1-2收敛", "生成: 场景A/B/C三方案"]
        return content, formula, strength, insights, reasoning
    
    def _generate_d1_content(
        self,
        agent_id: str,
        round_num: int,
        previous_responses: Optional[List[MockResponse]],
        confidence: float
    ) -> Tuple[str, str, float, List[str], List[str]]:
        """D1决策点内容（研发方向确定）"""
        if agent_id == "Miner":
            return (
                "基于文献分析，NM在强度方面优势明显，建议以NM复配为核心方向。",
                "NM为主",
                0.80,
                ["NM强度数据优异", "文献支持充分"],
                ["文献调研结论", "推荐NM方向"]
            )
        elif agent_id == "Assayer":
            return (
                "综合技术成熟度和成本考量，LS更适合大规模推广。",
                "LS为主",
                0.75,
                ["LS成本优势", "技术成熟度高"],
                ["成本分析", "推荐LS方向"]
            )
        else:
            return (
                "建议采用NM+LS复配方向，兼顾性能与成本。",
                "NM+LS复配",
                0.72,
                ["复配兼顾两端", "风险分散"],
                ["综合评估", "推荐复配"]
            )
    
    def _generate_d3_content(
        self,
        agent_id: str,
        round_num: int,
        previous_responses: Optional[List[MockResponse]],
        confidence: float
    ) -> Tuple[str, str, float, List[str], List[str]]:
        """D3决策点内容（配方定型）"""
        if agent_id == "Miner":
            return (
                "基于中试数据，配方稳定性良好，建议定型。",
                "13%NM + 7%LS",
                0.82,
                ["中试成功", "稳定性验证"],
                ["中试验证", "建议定型"]
            )
        else:
            return (
                "综合工程化考量，配方可定型，但需保留调整空间。",
                "13%NM + 7%LS (±1%)",
                0.78,
                ["可定型", "保留微调空间"],
                ["工程评估", "有条件定型"]
            )
    
    def _generate_regular_content(
        self,
        agent_id: str,
        step_num: int,
        confidence: float
    ) -> Tuple[str, str, float, List[str], List[str]]:
        """普通步骤内容生成"""
        contents = {
            "Miner": [
                f"Step {step_num}: 完成实验数据采集与初步分析，数据一致性良好。",
                f"Step {step_num}: 实验结果显示当前方案性能稳定，符合预期。"
            ],
            "Assayer": [
                f"Step {step_num}: 理论模型验证中，推导过程自洽。",
                f"Step {step_num}: 文献分析显示当前方法具有可行性。"
            ],
            "Evaluator": [
                f"Step {step_num}: 综合评估指标在预期范围内。",
                f"Step {step_num}: 风险评估显示方案可控。"
            ]
        }
        
        options = contents.get(agent_id, contents["Miner"])
        content = random.choice(options)
        
        return (
            content,
            "待定",
            0.70,
            [f"Step {step_num}常规进展"],
            [f"Step {step_num}分析"]
        )
    
    def detect_false_consensus(
        self,
        responses: List[MockResponse]
    ) -> List[FalseConsensusCase]:
        """
        检测虚假一致
        
        Args:
            responses: 当前决策点的所有响应
            
        Returns:
            检测到的虚假一致案例列表
        """
        cases = []
        
        # 检查Miner和Evaluator是否表面一致
        miner_resp = None
        evaluator_resp = None
        assayer_resp = None
        
        for resp in responses:
            if resp.agent_id == "Miner":
                miner_resp = resp
            elif resp.agent_id == "Evaluator":
                evaluator_resp = resp
            elif resp.agent_id == "Assayer":
                assayer_resp = resp
        
        # 检测虚假一致条件
        if (miner_resp and evaluator_resp and assayer_resp):
            # 表面一致: Miner和Evaluator都推荐NM
            miner_nm = "NM" in miner_resp.recommended_formula or "15%" in miner_resp.recommended_formula
            eval_nm = "NM" in evaluator_resp.recommended_formula or "15%" in evaluator_resp.recommended_formula
            
            # 隐藏分歧: Assayer推荐LS
            assayer_ls = "LS" in assayer_resp.recommended_formula or "20%" in assayer_resp.recommended_formula
            
            if miner_nm and eval_nm and assayer_ls:
                cases.append(FalseConsensusCase(
                    agents_involved=["Miner", "Evaluator", "Assayer"],
                    surface_consensus="Miner与Evaluator表面一致(推荐NM)",
                    hidden_disagreement="Assayer基于理论反对，推荐LS方案",
                    root_cause="Miner和Evaluator都看到相同数据，未考虑LS长期价值",
                    detection_method="Assayer的反对揭示了视角盲点",
                    cdol_resolution="生成条件依赖型方案(A/B/C三场景)，覆盖不同优先级"
                ))
        
        return cases


def create_mock_llm(cdol_mode: bool = True, seed: int = 42) -> MockLLM100Steps:
    """创建Mock LLM实例"""
    return MockLLM100Steps(cdol_mode=cdol_mode, seed=seed)


if __name__ == "__main__":
    # 测试Mock LLM
    print("测试 CDoL ON 模式:")
    mock_on = create_mock_llm(cdol_mode=True)
    
    # 测试D2决策点 Round 0
    print("\n--- D2 Round 0 ---")
    for agent in ["Miner", "Assayer", "Evaluator"]:
        resp = mock_on.generate_for_step(66, agent, "D2", 0)
        print(f"\n{agent}:")
        print(f"  置信度: {resp.confidence:.2f}")
        print(f"  推理深度: {resp.reasoning_depth}")
        print(f"  推荐配方: {resp.recommended_formula}")
        print(f"  上下文可用: {resp.context_usable}")
    
    print("\n" + "="*60)
    print("测试 CDoL OFF 模式:")
    mock_off = create_mock_llm(cdol_mode=False)
    
    # 测试衰减
    print("\n置信度衰减对比:")
    print("步数\t\tCDoL ON\t\tCDoL OFF")
    print("-"*40)
    for step in [20, 50, 66, 80, 100]:
        on_conf = mock_on._calculate_decay(step, "Miner")[0]
        off_conf = mock_off._calculate_decay(step, "Miner")[0]
        print(f"{step}\t\t{on_conf:.2f}\t\t{off_conf:.2f}")
