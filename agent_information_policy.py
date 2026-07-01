# -*- coding: utf-8 -*-
"""
Agent信息策略 (Agent Information Policy)
XuanHub v4.0 Phase 7 — CDoL信息不对称分配

核心设计：不是10个Agent都参与信息不对称，而是分层：
- 全局视野层（Coordinator, Planner）：看到完整信息，负责调度与规划
- CDoL参与层（其余7个）：按角色分配信息切片，产生认知增益
- 旁观记录层（Archivist）：看到结论但看不到原始上下文，负责蒸馏

每个参与CDoL的Agent看到的信息切片根据其认知角色精心裁剪，
不是随机子集——确保"被迫在自己的认知区间内深挖"。
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Set, Any
import logging

logger = logging.getLogger("AgentInformationPolicy")


# ============================================================================
# Agent分层
# ============================================================================

class AgentTier(str, Enum):
    """Agent在信息策略中的层级"""
    GLOBAL = "global"          # 全局视野层：看到完整信息
    CDOL_PARTICIPANT = "cdol"  # CDoL参与层：信息不对称
    OBSERVER = "observer"      # 旁观记录层：只看结论不看过程


# Agent分层映射
AGENT_TIER_MAP: Dict[str, AgentTier] = {
    "coordinator": AgentTier.GLOBAL,
    "planner":     AgentTier.GLOBAL,
    "researcher":  AgentTier.CDOL_PARTICIPANT,
    "executor":    AgentTier.CDOL_PARTICIPANT,
    "reviewer":    AgentTier.CDOL_PARTICIPANT,
    "miner":       AgentTier.CDOL_PARTICIPANT,
    "assayer":     AgentTier.CDOL_PARTICIPANT,
    "caster":      AgentTier.CDOL_PARTICIPANT,
    "artisan":     AgentTier.CDOL_PARTICIPANT,
    "archivist":   AgentTier.OBSERVER,
}


# ============================================================================
# 信息切片类型
# ============================================================================

class InfoSliceType(str, Enum):
    """信息切片类型——定义Agent能看到什么类别的信息"""
    RAW_EVIDENCE = "raw_evidence"           # 原始证据/数据
    TASK_SPEC = "task_spec"                 # 任务规范/约束
    FINAL_OUTPUT = "final_output"           # 最终输出（不含推理过程）
    LITERATURE_FRAGMENT = "literature_fragment"  # 文献片段（不含解读）
    VERIFICATION_ENTRY = "verification_entry"    # 验证条目（不含来源上下文）
    FUNCTIONAL_REQUIREMENT = "functional_requirement"  # 功能需求（不含业务全貌）
    DOMAIN_QUESTION = "domain_question"     # 领域问题（不含他人结论）
    REASONING_CHAIN = "reasoning_chain"     # 推理链（仅Planner可见）
    FULL_CONTEXT = "full_context"           # 完整上下文（仅全局视野层）
    INTERMEDIATE_CONCLUSION = "intermediate_conclusion"  # 中间结论（仅Observer可见）


# ============================================================================
# 角色→信息切片映射
# ============================================================================

@dataclass
class InformationProfile:
    """单个Agent的信息画像
    
    定义该Agent在CDoL中能看到什么、不能看到什么。
    """
    agent_name: str
    tier: AgentTier
    allowed_slices: Set[InfoSliceType]      # 允许看到的信息类型
    blocked_slices: Set[InfoSliceType]      # 明确屏蔽的信息类型
    visible_agents: Set[str]                # 能看到哪些Agent的输出
    receives_sync: bool = False             # 是否接收全局同步消息
    can_query_global_memory: bool = False   # 能否主动检索全局记忆
    
    @property
    def is_cdol_participant(self) -> bool:
        return self.tier == AgentTier.CDOL_PARTICIPANT
    
    @property
    def has_global_vision(self) -> bool:
        return self.tier == AgentTier.GLOBAL


# 十个Agent的信息画像
AGENT_INFORMATION_PROFILES: Dict[str, InformationProfile] = {
    
    # ═══════ 全局视野层 ═══════
    
    "coordinator": InformationProfile(
        agent_name="coordinator",
        tier=AgentTier.GLOBAL,
        allowed_slices={InfoSliceType.FULL_CONTEXT},
        blocked_slices=set(),
        visible_agents={"planner", "researcher", "executor", "reviewer",
                        "miner", "assayer", "caster", "artisan", "archivist"},
        receives_sync=True,
        can_query_global_memory=True,
    ),
    
    "planner": InformationProfile(
        agent_name="planner",
        tier=AgentTier.GLOBAL,
        allowed_slices={InfoSliceType.FULL_CONTEXT, InfoSliceType.REASONING_CHAIN},
        blocked_slices=set(),
        visible_agents={"coordinator", "researcher", "executor", "reviewer",
                        "miner", "assayer", "caster", "artisan"},
        receives_sync=True,
        can_query_global_memory=True,
    ),
    
    # ═══════ CDoL参与层 — 按角色裁剪 ═══════
    
    "researcher": InformationProfile(
        agent_name="researcher",
        tier=AgentTier.CDOL_PARTICIPANT,
        # Researcher是"眼睛"：只看到原始证据和数据，不看结论
        allowed_slices={InfoSliceType.RAW_EVIDENCE, InfoSliceType.LITERATURE_FRAGMENT},
        blocked_slices={InfoSliceType.FINAL_OUTPUT, InfoSliceType.REASONING_CHAIN},
        visible_agents={"miner"},  # 只能看到Miner的文献产出
        receives_sync=True,
        can_query_global_memory=True,  # 可以检索，但检索结果经过过滤
    ),
    
    "executor": InformationProfile(
        agent_name="executor",
        tier=AgentTier.CDOL_PARTICIPANT,
        # Executor是"手"：只看到任务规范，不看别人的推理过程
        allowed_slices={InfoSliceType.TASK_SPEC, InfoSliceType.FUNCTIONAL_REQUIREMENT},
        blocked_slices={InfoSliceType.REASONING_CHAIN, InfoSliceType.FINAL_OUTPUT},
        visible_agents={"planner"},  # 只能看到Planner的任务分配
        receives_sync=True,
        can_query_global_memory=False,  # 不能主动检索，防止分心
    ),
    
    "reviewer": InformationProfile(
        agent_name="reviewer",
        tier=AgentTier.CDOL_PARTICIPANT,
        # Reviewer是"质检"：只看到最终输出，不看推理过程（保证审查客观性）
        allowed_slices={InfoSliceType.FINAL_OUTPUT},
        blocked_slices={InfoSliceType.REASONING_CHAIN, InfoSliceType.RAW_EVIDENCE},
        visible_agents={"executor", "caster"},  # 只能看到执行者/铸师的产出
        receives_sync=True,
        can_query_global_memory=True,  # 可以检索来交叉验证
    ),
    
    "miner": InformationProfile(
        agent_name="miner",
        tier=AgentTier.CDOL_PARTICIPANT,
        # Miner是"矿工"：只看到文献片段，不看研究者的解读
        allowed_slices={InfoSliceType.LITERATURE_FRAGMENT},
        blocked_slices={InfoSliceType.REASONING_CHAIN, InfoSliceType.FINAL_OUTPUT},
        visible_agents=set(),  # 独立工作，不看其他Agent
        receives_sync=False,  # 不参与全局同步（独立挖掘）
        can_query_global_memory=True,
    ),
    
    "assayer": InformationProfile(
        agent_name="assayer",
        tier=AgentTier.CDOL_PARTICIPANT,
        # Assayer是"试金"：只看到验证条目，不看来源上下文
        allowed_slices={InfoSliceType.VERIFICATION_ENTRY},
        blocked_slices={InfoSliceType.RAW_EVIDENCE, InfoSliceType.REASONING_CHAIN},
        visible_agents={"researcher"},  # 只能看到Researcher的提取结果
        receives_sync=False,
        can_query_global_memory=True,
    ),
    
    "caster": InformationProfile(
        agent_name="caster",
        tier=AgentTier.CDOL_PARTICIPANT,
        # Caster是"铸师"：只看到功能需求和接口规范，不看业务全貌
        allowed_slices={InfoSliceType.FUNCTIONAL_REQUIREMENT, InfoSliceType.TASK_SPEC},
        blocked_slices={InfoSliceType.REASONING_CHAIN, InfoSliceType.FINAL_OUTPUT},
        visible_agents={"planner", "executor"},  # 看Planner的规范和Executor的接口
        receives_sync=True,
        can_query_global_memory=False,
    ),
    
    "artisan": InformationProfile(
        agent_name="artisan",
        tier=AgentTier.CDOL_PARTICIPANT,
        # Artisan是"匠人"：只看到领域问题，不看其他Agent的结论
        allowed_slices={InfoSliceType.DOMAIN_QUESTION},
        blocked_slices={InfoSliceType.REASONING_CHAIN, InfoSliceType.FINAL_OUTPUT},
        visible_agents=set(),  # 独立领域问答
        receives_sync=False,
        can_query_global_memory=True,
    ),
    
    # ═══════ 旁观记录层 ═══════
    
    "archivist": InformationProfile(
        agent_name="archivist",
        tier=AgentTier.OBSERVER,
        # Archivist是"海马体"：看到所有中间结论，但不看原始上下文
        allowed_slices={InfoSliceType.INTERMEDIATE_CONCLUSION},
        blocked_slices={InfoSliceType.RAW_EVIDENCE, InfoSliceType.LITERATURE_FRAGMENT},
        visible_agents={"planner", "researcher", "executor", "reviewer",
                        "miner", "assayer", "caster", "artisan"},
        receives_sync=True,
        can_query_global_memory=True,
    ),
}


# ============================================================================
# CDoL任务下的Agent选择策略
# ============================================================================

# 不同CDoL分解策略下，应该选哪几个Agent参与
CDOL_PARTICIPATION_MAP: Dict[str, List[str]] = {
    # 证据拆分：需要看到不同证据子集的Agent
    "evidence_split": ["researcher", "executor"],
    
    # 角色约束：需要对抗角色的Agent
    "role_constraint": ["researcher", "reviewer"],
    
    # 层级分离：抽象层 vs 实施层
    "layer_separation": ["planner", "executor"],
    
    # 模态拆分：结构化 vs 非结构化
    "modality_split": ["miner", "assayer"],
    
    # 时间切片：不同时间段的信息
    "time_slice": ["researcher", "artisan"],
    
    # 抽象层级：具体实例 vs 抽象规则
    "abstraction_level": ["artisan", "planner"],
    
    # 全量CDoL：所有参与层Agent
    "full_cdol": ["researcher", "executor", "reviewer", "miner", 
                   "assayer", "caster", "artisan"],
}

# 标准任务流推荐参与数
DEFAULT_PERSPECTIVE_COUNT = 3  # 默认3个视角，不是2个也不是10个


# ============================================================================
# AgentInformationPolicy — 核心类
# ============================================================================

class AgentInformationPolicy:
    """Agent信息策略管理器
    
    核心职责：
    1. 根据Agent角色决定其信息切片
    2. 为CDoL引擎提供ContextMask生成
    3. 管理Agent间的可见性
    4. 在任务执行中动态调整信息分配
    """
    
    def __init__(self):
        self.profiles = AGENT_INFORMATION_PROFILES.copy()
        self._usage_log: List[Dict[str, Any]] = []
    
    def get_profile(self, agent_name: str) -> InformationProfile:
        """获取Agent的信息画像"""
        profile = self.profiles.get(agent_name.lower())
        if not profile:
            raise ValueError(f"未知Agent: {agent_name}")
        return profile
    
    def get_tier(self, agent_name: str) -> AgentTier:
        """获取Agent的信息层级"""
        return self.get_profile(agent_name).tier
    
    def should_participate_cdol(self, agent_name: str) -> bool:
        """判断Agent是否应参与CDoL信息不对称"""
        return self.get_tier(agent_name) == AgentTier.CDOL_PARTICIPANT
    
    def get_cdol_participants(self, strategy: str = "full_cdol") -> List[str]:
        """获取指定策略下应参与CDoL的Agent列表"""
        return CDOL_PARTICIPATION_MAP.get(strategy, 
               CDOL_PARTICIPATION_MAP["full_cdol"])
    
    def get_recommended_participants(self, task_description: str, 
                                      max_count: int = DEFAULT_PERSPECTIVE_COUNT) -> List[str]:
        """根据任务描述推荐最合适的CDoL参与者
        
        不是所有任务都需要10个Agent参与——
        精选2-4个最相关的Agent参与CDoL效果更好。
        
        Args:
            task_description: 任务描述
            max_count: 最大参与Agent数
            
        Returns:
            Agent名称列表
        """
        desc = task_description.lower()
        
        # 文献/研究类任务
        if any(kw in desc for kw in ["文献", "论文", "检索", "搜索", "paper", "literature"]):
            candidates = ["miner", "researcher", "assayer"]
        
        # 代码/开发类任务
        elif any(kw in desc for kw in ["代码", "编程", "实现", "开发", "code", "develop"]):
            candidates = ["caster", "executor", "reviewer"]
        
        # 验证/评估类任务
        elif any(kw in desc for kw in ["验证", "评估", "对比", "verify", "evaluate"]):
            candidates = ["researcher", "reviewer", "assayer"]
        
        # 设计/规划类任务
        elif any(kw in desc for kw in ["设计", "规划", "架构", "design", "plan"]):
            candidates = ["planner", "artisan", "executor"]
        
        # 领域问答
        elif any(kw in desc for kw in ["解释", "问答", "概念", "explain", "concept"]):
            candidates = ["artisan", "researcher"]
        
        # 通用任务
        else:
            candidates = ["researcher", "executor", "reviewer"]
        
        return candidates[:max_count]
    
    def generate_context_mask(self, agent_name: str, 
                               task_context: Dict[str, Any]) -> Dict[str, Any]:
        """为指定Agent生成ContextMask
        
        根据Agent的信息画像，决定它在这次任务中能看到什么。
        
        Args:
            agent_name: Agent名称
            task_context: 任务的完整上下文
            
        Returns:
            ContextMask字典（可直接传入PerspectiveAssignment）
        """
        profile = self.get_profile(agent_name)
        
        # 全局视野层：不限制
        if profile.tier == AgentTier.GLOBAL:
            return {
                "allowed_evidence": ["all"],
                "blocked_evidence": [],
                "allowed_domains": ["all"],
                "blocked_domains": [],
                "abstraction_level": "mixed",
            }
        
        # 旁观记录层：只看结论
        if profile.tier == AgentTier.OBSERVER:
            return {
                "allowed_evidence": ["intermediate_conclusions"],
                "blocked_evidence": ["raw_evidence", "literature_text", "source_context"],
                "allowed_domains": ["all"],
                "blocked_domains": [],
                "abstraction_level": "mixed",
            }
        
        # CDoL参与层：按角色裁剪
        mask = {
            "allowed_evidence": [],
            "blocked_evidence": [],
            "allowed_domains": [],
            "blocked_domains": [],
            "abstraction_level": "mixed",
        }
        
        # 根据允许的信息切片类型生成mask
        for slice_type in profile.allowed_slices:
            if slice_type == InfoSliceType.RAW_EVIDENCE:
                mask["allowed_evidence"].append("data")
                mask["allowed_evidence"].append("measurements")
                mask["allowed_domains"].append("experimental")
            elif slice_type == InfoSliceType.TASK_SPEC:
                mask["allowed_evidence"].append("task_description")
                mask["allowed_evidence"].append("constraints")
                mask["allowed_domains"].append("specification")
            elif slice_type == InfoSliceType.FINAL_OUTPUT:
                mask["allowed_evidence"].append("output")
                mask["allowed_domains"].append("result")
            elif slice_type == InfoSliceType.LITERATURE_FRAGMENT:
                mask["allowed_evidence"].append("paper_text")
                mask["allowed_evidence"].append("abstract")
                mask["allowed_domains"].append("literature")
            elif slice_type == InfoSliceType.VERIFICATION_ENTRY:
                mask["allowed_evidence"].append("claim")
                mask["allowed_evidence"].append("data_point")
                mask["allowed_domains"].append("verification")
            elif slice_type == InfoSliceType.FUNCTIONAL_REQUIREMENT:
                mask["allowed_evidence"].append("requirement")
                mask["allowed_evidence"].append("interface_spec")
                mask["allowed_domains"].append("engineering")
            elif slice_type == InfoSliceType.DOMAIN_QUESTION:
                mask["allowed_evidence"].append("domain_question")
                mask["allowed_domains"].append("domain_knowledge")
        
        # 明确屏蔽的信息
        for slice_type in profile.blocked_slices:
            if slice_type == InfoSliceType.REASONING_CHAIN:
                mask["blocked_evidence"].append("reasoning_process")
                mask["blocked_evidence"].append("other_agent_thoughts")
            elif slice_type == InfoSliceType.FINAL_OUTPUT:
                mask["blocked_evidence"].append("final_answer")
            elif slice_type == InfoSliceType.RAW_EVIDENCE:
                mask["blocked_evidence"].append("raw_data")
            elif slice_type == InfoSliceType.LITERATURE_FRAGMENT:
                mask["blocked_evidence"].append("paper_text")
        
        # 设置抽象层级
        if agent_name == "executor":
            mask["abstraction_level"] = "concrete"  # 执行者只看具体实现
        elif agent_name == "artisan":
            mask["abstraction_level"] = "mixed"     # 匠人需要理论和实践结合
        elif agent_name == "reviewer":
            mask["abstraction_level"] = "abstract"   # 审查者看抽象层面
        
        return mask
    
    def can_see_agent_output(self, viewer: str, target: str) -> bool:
        """判断viewer是否能看到target Agent的输出"""
        profile = self.get_profile(viewer)
        return target.lower() in profile.visible_agents
    
    def get_visible_agents(self, agent_name: str) -> Set[str]:
        """获取指定Agent能看到哪些其他Agent的输出"""
        return self.get_profile(agent_name).visible_agents
    
    def log_usage(self, agent_name: str, slices_granted: List[str], 
                  task_id: str = "") -> None:
        """记录信息分配日志"""
        self._usage_log.append({
            "agent": agent_name,
            "slices": slices_granted,
            "task_id": task_id,
            "timestamp": __import__("time").time(),
        })
    
    def get_policy_summary(self) -> str:
        """生成信息策略摘要（用于Dashboard展示）"""
        lines = [
            "# NexusFlow 信息不对称策略",
            "",
            "## 全局视野层（完整信息）",
        ]
        for name, profile in self.profiles.items():
            if profile.tier == AgentTier.GLOBAL:
                lines.append(f"- **{name}**: 完整上下文 + 可检索全局记忆")
        
        lines.append("\n## CDoL参与层（信息裁剪）")
        for name, profile in self.profiles.items():
            if profile.tier == AgentTier.CDOL_PARTICIPANT:
                allowed = ", ".join(s.value for s in profile.allowed_slices)
                blocked = ", ".join(s.value for s in profile.blocked_slices)
                visible = ", ".join(profile.visible_agents) or "无"
                lines.append(f"- **{name}**")
                lines.append(f"  - 可见: {allowed}")
                lines.append(f"  - 屏蔽: {blocked}")
                lines.append(f"  - 可见Agent: {visible}")
        
        lines.append("\n## 旁观记录层（只看结论）")
        for name, profile in self.profiles.items():
            if profile.tier == AgentTier.OBSERVER:
                lines.append(f"- **{name}**: 中间结论 + 蒸馏产物")
        
        return "\n".join(lines)


# ============================================================================
# 便捷函数
# ============================================================================

def get_information_policy() -> AgentInformationPolicy:
    """获取全局信息策略实例"""
    return AgentInformationPolicy()


def recommend_cdol_config(task_description: str) -> Dict[str, Any]:
    """为任务推荐CDoL配置
    
    返回：推荐的参与者、策略、perspective_count
    """
    policy = get_information_policy()
    participants = policy.get_recommended_participants(task_description)
    
    # 根据参与者自动选择策略
    desc = task_description.lower()
    if any(kw in desc for kw in ["文献", "论文", "数据"]):
        strategy = "evidence_split"
    elif any(kw in desc for kw in ["假设", "验证"]):
        strategy = "role_constraint"
    elif any(kw in desc for kw in ["设计", "方法"]):
        strategy = "layer_separation"
    elif any(kw in desc for kw in ["对比", "评估"]):
        strategy = "abstraction_level"
    else:
        strategy = "evidence_split"
    
    return {
        "participants": participants,
        "perspective_count": len(participants),
        "strategy": strategy,
        "information_masks": {
            p: policy.generate_context_mask(p, {"task": task_description})
            for p in participants
        },
    }
