#!/usr/bin/env python3
"""
NexusFlow Full System Demo — 动态拓扑 × CDoL × 端边云调度 真实运行
===================================================================
完整演示 NexusFlow 系统的核心能力：
1. 动态拓扑路由：不同子任务选择不同拓扑（sequential/parallel/hybrid/dynamic/star）
2. CDoL 三轮协议：信息不对称下的认知分工（Round0→Round1→Round2→FusionJudge）
3. 端边云调度：每个 Agent 步骤的部署层决策
4. 信息策略：10 个 Agent 的 ContextMask 差异
5. 全局记忆与上下文管理

任务：AI大模型技术趋势分析（4个阶段 × 不同拓扑）
"""

import sys
import os
import json
import time
import urllib.request
import logging
import traceback
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

# ============================================================
# 0. 环境配置
# ============================================================
NEXUSFLOW_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(NEXUSFLOW_DIR)
sys.path.insert(0, NEXUSFLOW_DIR)

DEEPSEEK_API_KEY = os.environ.get("DEEPSEEK_API_KEY", "")
DEEPSEEK_URL = "https://api.deepseek.com/chat/completions"
DEEPSEEK_MODEL = "deepseek-chat"

OUTPUT_DIR = os.path.join(NEXUSFLOW_DIR, "examples")
HTML_REPORT_PATH = os.path.join(OUTPUT_DIR, "demo_dashboard_report.html")
JSON_DATA_PATH = os.path.join(OUTPUT_DIR, "demo_execution_data.json")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("NexusFlowDemo")

# 全局执行数据（供 HTML 报告使用）
EXEC_DATA = {
    "phases": [],
    "topology_timeline": [],
    "route_plans": [],
    "scheduler_decisions": [],
    "cdol_details": {},
    "info_policy_masks": {},
    "agents": [],
    "stats": {"api_calls": 0, "total_tokens": 0, "start_time": 0, "elapsed": 0},
    "final_conclusion": "",
}


# ============================================================
# 1. DeepSeek LLM Wrapper
# ============================================================
def deepseek_chat(prompt: str, system: str = "", model: str = DEEPSEEK_MODEL,
                  max_tokens: int = 4096, temperature: float = 0.3) -> str:
    """DeepSeek API 调用"""
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})

    payload = json.dumps({
        "model": model,
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": temperature,
    }).encode("utf-8")

    req = urllib.request.Request(
        DEEPSEEK_URL, data=payload,
        headers={
            "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
            "Content-Type": "application/json",
        },
    )

    try:
        with urllib.request.urlopen(req, timeout=180) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            EXEC_DATA["stats"]["api_calls"] += 1
            EXEC_DATA["stats"]["total_tokens"] += data.get("usage", {}).get("total_tokens", 0)
            return data["choices"][0]["message"]["content"]
    except Exception as e:
        logger.error(f"DeepSeek API error: {e}")
        return f"[API_ERROR: {e}]"


# ============================================================
# 2. 10-Agent 定义
# ============================================================
@dataclass
class SimpleAgent:
    """轻量 Agent"""
    agent_id: str
    display_name: str
    capabilities: List[str] = field(default_factory=list)
    domain_expertise: List[str] = field(default_factory=list)
    tier: str = "cloud"
    system_prompt: str = ""

    def chat(self, prompt: str, context: str = "") -> str:
        full_prompt = prompt
        if context:
            full_prompt += f"\n\n## 可用上下文\n{context}"
        return deepseek_chat(full_prompt, system=self.system_prompt)


AGENT_PROMPTS = {
    "coordinator": "你是NexusFlow的协调者(Coordinator)。职责：任务拆解、角色分配、进度协调、结论汇总。你拥有全局视野。输出格式：JSON（assignments/progress/summary）。",
    "strategist": "你是NexusFlow的策略师(Strategist)。职责：设计分析框架、方法论选择、权重方案、评估标准。输出格式：结构化方案（维度/方法/公式/权重/验证）。",
    "researcher": "你是NexusFlow的研究员(Researcher)。职责：从数据源获取原始数据，只负责获取数据不做分析。输出JSON格式数据+元信息。",
    "coder": "你是NexusFlow的编码专家(Coder)。职责：实现归一化/统计/回归等计算。编写可复现的Python代码。只输出代码和计算结果不做结论性解读。",
    "analyst": "你是NexusFlow的分析师(Analyst)。职责：基于计算结果解读数据、发现趋势、生成分析结论。输出：各维度结论+排名+置信度。",
    "observer": "你是NexusFlow的监控者(Observer)。职责：数据质量监控、异常值检测、数据完整性检查。只关注数据层面的问题不做结论性判断。",
    "monitor": "你是NexusFlow的进度监控者(Monitor)。职责：追踪执行进度、统计API调用、识别效率问题、超时预警。输出结构化进度报告。",
    "critic": "你是NexusFlow的批评者(Critic)。核心职责：质疑假设、挑战结论、检查方法论缺陷、验证数据使用。必须找出至少3个具体问题，每个质疑必须有证据。严重程度分级：high/medium/low。",
    "synthesizer": "你是NexusFlow的综合者(Synthesizer)。职责：整合所有角色结论、处理Critic质疑、生成最终结论。当Critic提出质疑时，权衡各方做出裁决。输出：修正后的结论+置信度+局限性。",
    "archivist": "你是NexusFlow的档案师(Archivist)。职责：整理所有产物、生成结构化Markdown报告、确保可追溯。报告必须包含：方法/数据/结论/质疑记录/修正/置信度。",
}

AGENT_TIERS = {
    "coordinator": "cloud", "strategist": "cloud", "researcher": "cloud",
    "critic": "cloud", "synthesizer": "cloud", "archivist": "cloud",
    "coder": "edge", "analyst": "edge",
    "observer": "terminal", "monitor": "terminal",
}

AGENT_CAPS = {
    "coordinator": ["task_decomposition", "orchestration", "summary"],
    "strategist": ["methodology", "framework_design", "weight_design"],
    "researcher": ["data_collection", "search", "fact_checking"],
    "coder": ["python", "statistics", "regression", "normalization"],
    "analyst": ["trend_analysis", "statistical_inference", "ranking"],
    "observer": ["quality_check", "anomaly_detection", "completeness"],
    "monitor": ["progress_tracking", "api_counting", "timeout_warning"],
    "critic": ["hypothesis_challenge", "conclusion_review", "methodology_audit"],
    "synthesizer": ["conclusion_integration", "conflict_resolution", "final_judgment"],
    "archivist": ["report_generation", "traceability", "documentation"],
}


def create_agents() -> Dict[str, SimpleAgent]:
    agents = {}
    for name, prompt in AGENT_PROMPTS.items():
        agents[name] = SimpleAgent(
            agent_id=name,
            display_name=name.capitalize(),
            capabilities=AGENT_CAPS.get(name, []),
            domain_expertise=[name],
            tier=AGENT_TIERS.get(name, "cloud"),
            system_prompt=prompt,
        )
    return agents


# ============================================================
# 3. 导入 NexusFlow 核心模块
# ============================================================
def import_nexusflow():
    from dynamic_router import (
        DynamicTopologyRouter, AgentCapabilityProfile,
        TaskRequirement, TaskComplexity, RoutePlan, AgentLoadState,
    )
    from cognitive_division_engine import (
        CognitiveDivisionEngine, PerspectiveDecomposer,
        CommunicationLayer, FusionJudge, InsightDistiller, InsightStore,
        ContextMask, IntermediateConclusion, CDoLResult,
        PerspectiveAssignment, DecompositionPlan,
    )
    from edge_cloud_scheduler import (
        EdgeCloudScheduler, DeployTier, SchedulingPolicy,
        TierResource, SchedulingDecision,
    )
    from agent_information_policy import (
        AgentInformationPolicy, AgentTier, InfoSliceType,
        InformationProfile, get_information_policy,
    )
    from adaptive_context_manager import GlobalMemoryPool, create_context_manager
    from nexus_orchestrator import NexusOrchestrator

    return {
        "DynamicTopologyRouter": DynamicTopologyRouter,
        "AgentCapabilityProfile": AgentCapabilityProfile,
        "TaskRequirement": TaskRequirement,
        "TaskComplexity": TaskComplexity,
        "RoutePlan": RoutePlan,
        "AgentLoadState": AgentLoadState,
        "CognitiveDivisionEngine": CognitiveDivisionEngine,
        "PerspectiveDecomposer": PerspectiveDecomposer,
        "CommunicationLayer": CommunicationLayer,
        "FusionJudge": FusionJudge,
        "InsightDistiller": InsightDistiller,
        "InsightStore": InsightStore,
        "ContextMask": ContextMask,
        "IntermediateConclusion": IntermediateConclusion,
        "CDoLResult": CDoLResult,
        "PerspectiveAssignment": PerspectiveAssignment,
        "DecompositionPlan": DecompositionPlan,
        "EdgeCloudScheduler": EdgeCloudScheduler,
        "DeployTier": DeployTier,
        "SchedulingPolicy": SchedulingPolicy,
        "TierResource": TierResource,
        "SchedulingDecision": SchedulingDecision,
        "AgentInformationPolicy": AgentInformationPolicy,
        "AgentTier": AgentTier,
        "InfoSliceType": InfoSliceType,
        "InformationProfile": InformationProfile,
        "get_information_policy": get_information_policy,
        "GlobalMemoryPool": GlobalMemoryPool,
        "create_context_manager": create_context_manager,
        "NexusOrchestrator": NexusOrchestrator,
    }


# ============================================================
# 4. 修补信息策略的 Agent 画像
# ============================================================
def patch_info_policy(nf, info_policy):
    """为 stage3 的 10 个 Agent 补充信息策略画像"""
    AgentTier = nf["AgentTier"]
    InfoSliceType = nf["InfoSliceType"]
    InformationProfile = nf["InformationProfile"]

    EXTRA_PROFILES = {
        "strategist": InformationProfile(
            agent_name="strategist",
            tier=AgentTier.GLOBAL,
            allowed_slices={InfoSliceType.FULL_CONTEXT, InfoSliceType.REASONING_CHAIN},
            blocked_slices=set(),
            visible_agents={"coordinator", "researcher", "analyst", "critic", "synthesizer"},
            receives_sync=True,
            can_query_global_memory=True,
        ),
        "coder": InformationProfile(
            agent_name="coder",
            tier=AgentTier.CDOL_PARTICIPANT,
            allowed_slices={InfoSliceType.TASK_SPEC, InfoSliceType.FUNCTIONAL_REQUIREMENT},
            blocked_slices={InfoSliceType.REASONING_CHAIN, InfoSliceType.FINAL_OUTPUT},
            visible_agents={"strategist"},
            receives_sync=True,
            can_query_global_memory=False,
        ),
        "analyst": InformationProfile(
            agent_name="analyst",
            tier=AgentTier.CDOL_PARTICIPANT,
            allowed_slices={InfoSliceType.RAW_EVIDENCE, InfoSliceType.VERIFICATION_ENTRY},
            blocked_slices={InfoSliceType.FINAL_OUTPUT, InfoSliceType.REASONING_CHAIN},
            visible_agents={"coder", "researcher"},
            receives_sync=True,
            can_query_global_memory=True,
        ),
        "observer": InformationProfile(
            agent_name="observer",
            tier=AgentTier.CDOL_PARTICIPANT,
            allowed_slices={InfoSliceType.RAW_EVIDENCE},
            blocked_slices={InfoSliceType.REASONING_CHAIN, InfoSliceType.FINAL_OUTPUT},
            visible_agents={"researcher"},
            receives_sync=False,
            can_query_global_memory=True,
        ),
        "monitor": InformationProfile(
            agent_name="monitor",
            tier=AgentTier.CDOL_PARTICIPANT,
            allowed_slices={InfoSliceType.TASK_SPEC},
            blocked_slices={InfoSliceType.RAW_EVIDENCE, InfoSliceType.REASONING_CHAIN},
            visible_agents={"coordinator"},
            receives_sync=True,
            can_query_global_memory=False,
        ),
        "critic": InformationProfile(
            agent_name="critic",
            tier=AgentTier.CDOL_PARTICIPANT,
            allowed_slices={InfoSliceType.FINAL_OUTPUT, InfoSliceType.VERIFICATION_ENTRY},
            blocked_slices={InfoSliceType.REASONING_CHAIN, InfoSliceType.RAW_EVIDENCE},
            visible_agents={"analyst", "synthesizer", "coder"},
            receives_sync=True,
            can_query_global_memory=True,
        ),
        "synthesizer": InformationProfile(
            agent_name="synthesizer",
            tier=AgentTier.GLOBAL,
            allowed_slices={InfoSliceType.FULL_CONTEXT},
            blocked_slices=set(),
            visible_agents={"coordinator", "strategist", "researcher", "analyst",
                            "critic", "coder", "observer", "monitor", "archivist"},
            receives_sync=True,
            can_query_global_memory=True,
        ),
    }

    # 保留 coordinator 和 archivist 原有映射，补充其余
    info_policy.profiles["coordinator"] = InformationProfile(
        agent_name="coordinator",
        tier=AgentTier.GLOBAL,
        allowed_slices={InfoSliceType.FULL_CONTEXT},
        blocked_slices=set(),
        visible_agents={"strategist", "researcher", "coder", "analyst",
                        "observer", "monitor", "critic", "synthesizer", "archivist"},
        receives_sync=True,
        can_query_global_memory=True,
    )
    info_policy.profiles["researcher"] = InformationProfile(
        agent_name="researcher",
        tier=AgentTier.CDOL_PARTICIPANT,
        allowed_slices={InfoSliceType.RAW_EVIDENCE, InfoSliceType.LITERATURE_FRAGMENT},
        blocked_slices={InfoSliceType.FINAL_OUTPUT, InfoSliceType.REASONING_CHAIN},
        visible_agents={"observer"},
        receives_sync=True,
        can_query_global_memory=True,
    )
    info_policy.profiles["archivist"] = InformationProfile(
        agent_name="archivist",
        tier=AgentTier.OBSERVER,
        allowed_slices={InfoSliceType.INTERMEDIATE_CONCLUSION},
        blocked_slices={InfoSliceType.RAW_EVIDENCE, InfoSliceType.LITERATURE_FRAGMENT},
        visible_agents={"coordinator", "strategist", "researcher", "coder",
                        "analyst", "observer", "monitor", "critic", "synthesizer"},
        receives_sync=True,
        can_query_global_memory=True,
    )

    info_policy.profiles.update(EXTRA_PROFILES)
    logger.info(f"信息策略画像已修补：{list(info_policy.profiles.keys())}")


# ============================================================
# 5. 注册 Agent 到 DynamicTopologyRouter
# ============================================================
def register_agents_to_router(nf, router, agents):
    """将 10 个 Agent 注册到动态拓扑路由器"""
    AgentCapabilityProfile = nf["AgentCapabilityProfile"]
    AgentLoadState = nf["AgentLoadState"]

    tier_map = {"cloud": "cloud", "edge": "fog", "terminal": "edge"}

    for name, agent in agents.items():
        profile = AgentCapabilityProfile(
            agent_id=name,
            name=agent.display_name,
            role=name,
            capabilities=agent.capabilities,
            domain_expertise=agent.domain_expertise,
            tier=tier_map.get(agent.tier, "cloud"),
            load_state=AgentLoadState.IDLE,
            reasoning_depth=0.8 if name in ("strategist", "critic", "synthesizer") else 0.5,
            creativity=0.7 if name == "strategist" else 0.4,
        )
        router.register_agent(profile)


# ============================================================
# 6. 为每个 Agent 步骤做端边云调度决策
# ============================================================
def schedule_agent_step(nf, scheduler, agent_name, step_desc, privacy_level=0):
    """调度单个 Agent 步骤"""
    agent_tier = AGENT_TIERS.get(agent_name, "cloud")
    needs_gpu = agent_name in ("coder", "analyst")

    decision = scheduler.schedule({
        "task_id": f"step_{agent_name}",
        "needs_gpu": needs_gpu,
        "privacy_level": privacy_level,
        "context_window": 8192,
        "latency_budget_ms": 30000,
        "model_name": "deepseek-chat",
    })

    EXEC_DATA["scheduler_decisions"].append({
        "agent": agent_name,
        "tier": agent_tier,
        "step": step_desc,
        "scheduled_tier": decision.selected_tier.value,
        "resource": decision.selected_resource,
        "reason": decision.reason,
        "confidence": decision.confidence,
        "latency_ms": decision.estimated_latency_ms,
    })
    return decision


# ============================================================
# 7. 收集每个 Agent 的 ContextMask
# ============================================================
def collect_context_masks(info_policy, agents):
    """收集所有 Agent 的 ContextMask"""
    masks = {}
    for name in agents:
        try:
            mask = info_policy.generate_context_mask(name, {"task": "AI大模型技术趋势分析"})
            tier = info_policy.get_tier(name).value
            masks[name] = {"mask": mask, "tier": tier}
        except (ValueError, KeyError) as e:
            masks[name] = {"mask": {"error": str(e)}, "tier": "unknown"}
    EXEC_DATA["info_policy_masks"] = masks
    return masks


# ============================================================
# 8. 主执行流程
# ============================================================
def run_demo():
    """运行完整 NexusFlow Demo"""
    EXEC_DATA["stats"]["start_time"] = time.time()
    logger.info("=" * 70)
    logger.info("NexusFlow Full System Demo — 动态拓扑 × CDoL × 端边云调度")
    logger.info("=" * 70)

    # ---- Step 0: 导入模块 ----
    logger.info("[Step 0] 导入 NexusFlow 核心模块...")
    nf = import_nexusflow()
    logger.info(f"  模块导入完成: {len(nf)} 个组件")

    # ---- Step 1: 创建 Agent ----
    logger.info("[Step 1] 创建 10 个 Agent...")
    agents = create_agents()
    EXEC_DATA["agents"] = [
        {"id": name, "tier": a.tier, "caps": a.capabilities}
        for name, a in agents.items()
    ]
    logger.info(f"  Agent 池: {list(agents.keys())}")

    # ---- Step 2: 初始化信息策略 ----
    logger.info("[Step 2] 初始化信息策略 + 修补画像...")
    info_policy = nf["get_information_policy"]()
    patch_info_policy(nf, info_policy)

    # 收集 ContextMask
    masks = collect_context_masks(info_policy, agents)
    logger.info(f"  ContextMask 收集完成: {len(masks)} 个 Agent")

    # ---- Step 3: 初始化端边云调度器 ----
    logger.info("[Step 3] 初始化 EdgeCloudScheduler...")
    scheduler = nf["EdgeCloudScheduler"](policy=nf["SchedulingPolicy"].BALANCED)
    scheduler.setup_default_tiers(local_gpu=False)
    logger.info("  三层资源就绪: Edge / Fog / Cloud")

    # ---- Step 4: 初始化动态拓扑路由器 ----
    logger.info("[Step 4] 初始化 DynamicTopologyRouter + 注册 Agent...")
    router = nf["DynamicTopologyRouter"]()
    register_agents_to_router(nf, router, agents)
    logger.info(f"  Router 注册完成: {len(router._agents)} 个 Agent")

    # ---- Step 5: 初始化记忆和上下文 ----
    logger.info("[Step 5] 初始化 GlobalMemoryPool + AdaptiveContextManager...")
    memory_pool = nf["GlobalMemoryPool"]()
    context_mgr = nf["create_context_manager"](
        information_policy=info_policy, llm_chat=deepseek_chat
    )
    logger.info("  记忆系统就绪")

    # ---- Step 6: 初始化 CDoL 引擎 ----
    logger.info("[Step 6] 初始化 CognitiveDivisionEngine...")
    insight_store = nf["InsightStore"]()
    cdol_engine = nf["CognitiveDivisionEngine"](
        agents=agents,
        memory_pool=memory_pool,
        llm_chat=deepseek_chat,
        insight_store=insight_store,
        information_policy=info_policy,
    )
    logger.info("  CDoL 引擎就绪")

    # ============================================================
    # 阶段一：任务分解与路由（sequential 拓扑）
    # ============================================================
    logger.info("\n" + "=" * 70)
    logger.info("阶段一：任务分解 — Coordinator 串行规划 (sequential 拓扑)")
    logger.info("=" * 70)

    phase1_start = time.time()

    # 用 Coordinator 做任务分解
    coord_plan = agents["coordinator"].chat(
        """你是一个AI技术趋势分析项目的协调者。请将以下宏观任务分解为4个具体子任务：

宏观任务：AI大模型技术趋势分析（2024-2026）

要求：
1. 子任务A：简单数据获取 — 收集主流大模型（GPT-4o、Claude、Gemini、DeepSeek、Llama、Qwen）的最新参数和性能指标
2. 子任务B：多维度分析 — 从技术架构、训练范式、应用场景、安全治理四个维度分析趋势
3. 子任务C：深度推理与评估 — 综合各维度结论，评估各模型/路线的技术成熟度和未来潜力
4. 子任务D：报告整合 — 汇总分析结果，生成趋势预测和建议

输出JSON格式：
{
  "subtasks": [
    {"id": "A", "name": "...", "description": "...", "complexity": "simple/moderate/complex",
     "required_capabilities": [...], "recommended_agents": [...]}
  ]
}"""
    )
    logger.info(f"  Coordinator 分解完成: {len(coord_plan)} chars")

    # 路由子任务A → sequential 拓扑
    task_A = nf["TaskRequirement"](
        task_id="subtask_A",
        description="收集主流大模型（GPT-4o、Claude、Gemini、DeepSeek、Llama、Qwen）的最新参数规格和基准性能数据",
        required_capabilities=["data_collection", "search", "fact_checking"],
        complexity=nf["TaskComplexity"].SIMPLE,
        execution_mode="sequential",
    )
    plan_A = router.route(task_A)

    # 调度
    for aid in plan_A.agent_chain:
        schedule_agent_step(nf, scheduler, aid, "子任务A：数据获取", privacy_level=0)

    phase1_time = time.time() - phase1_start
    EXEC_DATA["phases"].append({
        "name": "阶段一：任务分解",
        "topology": plan_A.topology_type,
        "agents": plan_A.agent_chain,
        "time": phase1_time,
        "coordinator_output": coord_plan[:2000],
    })
    EXEC_DATA["topology_timeline"].append({
        "phase": "A-数据获取",
        "topology": plan_A.topology_type,
        "agents": plan_A.agent_chain,
        "confidence": plan_A.confidence,
    })
    EXEC_DATA["route_plans"].append({
        "subtask": "A-数据获取",
        "plan_id": plan_A.plan_id,
        "chain": plan_A.agent_chain,
        "topology": plan_A.topology_type,
        "confidence": plan_A.confidence,
        "estimated_cost": plan_A.estimated_cost,
        "estimated_latency_ms": plan_A.estimated_latency_ms,
    })
    logger.info(f"  路由结果: topology={plan_A.topology_type}, chain={plan_A.agent_chain}, conf={plan_A.confidence:.2f}")

    # ============================================================
    # 阶段二：多维度分析（parallel/hybrid 拓扑）
    # ============================================================
    logger.info("\n" + "=" * 70)
    logger.info("阶段二：多维度分析 — Analyst+Coder 并行分析 (parallel/hybrid 拓扑)")
    logger.info("=" * 70)

    phase2_start = time.time()

    # Researcher 获取数据
    data_result = agents["researcher"].chat(
        """请收集以下大模型的最新公开信息，以JSON格式输出：

大模型列表：GPT-4o, Claude 3.5 Sonnet, Gemini 1.5 Pro, DeepSeek-V3, Llama 3.1 405B, Qwen2.5 72B

对每个模型，请提供：
1. 参数规模（B=十亿参数）
2. 上下文窗口大小
3. 关键基准得分（MMLU, HumanEval, GSM8K等，如有公开数据）
4. 训练范式特点（RLHF/DPO/MoE等）
5. 主要应用场景

输出JSON数组格式。如果某些数据不确定，标注为"estimated"。"""
    )
    logger.info(f"  Researcher 数据获取完成: {len(data_result)} chars")

    # 路由子任务B → parallel 拓扑
    task_B = nf["TaskRequirement"](
        task_id="subtask_B",
        description="从技术架构、训练范式、应用场景、安全治理四个维度对AI大模型趋势进行多维度分析",
        required_capabilities=["trend_analysis", "statistical_inference", "methodology", "python"],
        complexity=nf["TaskComplexity"].COMPLEX,
        execution_mode="sequential",
    )
    plan_B = router.route(task_B)

    # 调度
    for aid in plan_B.agent_chain:
        schedule_agent_step(nf, scheduler, aid, "子任务B：多维度分析", privacy_level=0)

    # 使用 Analyst 和 Strategist 并行分析
    analyst_prompt = f"""基于以下大模型数据，从技术架构和训练范式两个维度进行趋势分析：

{data_result[:3000]}

请输出：
1. 技术架构趋势（MoE、长上下文、多模态融合等）
2. 训练范式演进（RLHF→DPO→新方法等）
3. 每个趋势的置信度(0-1)
4. 关键发现列表"""

    strategy_prompt = f"""基于以下大模型数据，从应用场景和安全治理两个维度进行趋势分析：

{data_result[:3000]}

请输出：
1. 应用场景趋势（代码生成、科学推理、Agent等）
2. 安全治理发展（对齐方法、可解释性、监管框架等）
3. 每个趋势的置信度(0-1)
4. 关键发现列表"""

    # 并行调用（串行实现，模拟并行）
    analyst_result = agents["analyst"].chat(analyst_prompt)
    strategy_result = agents["strategist"].chat(strategy_prompt)

    phase2_time = time.time() - phase2_start
    EXEC_DATA["phases"].append({
        "name": "阶段二：多维度分析",
        "topology": plan_B.topology_type,
        "agents": plan_B.agent_chain,
        "time": phase2_time,
        "analyst_result": analyst_result[:2000],
        "strategy_result": strategy_result[:2000],
    })
    EXEC_DATA["topology_timeline"].append({
        "phase": "B-多维度分析",
        "topology": plan_B.topology_type,
        "agents": plan_B.agent_chain,
        "confidence": plan_B.confidence,
    })
    EXEC_DATA["route_plans"].append({
        "subtask": "B-多维度分析",
        "plan_id": plan_B.plan_id,
        "chain": plan_B.agent_chain,
        "topology": plan_B.topology_type,
        "confidence": plan_B.confidence,
        "estimated_cost": plan_B.estimated_cost,
        "estimated_latency_ms": plan_B.estimated_latency_ms,
    })
    logger.info(f"  路由结果: topology={plan_B.topology_type}, chain={plan_B.agent_chain}, conf={plan_B.confidence:.2f}")

    # ============================================================
    # 阶段三：CDoL 核心推理（star 拓扑 + CDoL 三轮协议）
    # ============================================================
    logger.info("\n" + "=" * 70)
    logger.info("阶段三：CDoL 核心推理 — star 拓扑 + 信息不对称三轮协议")
    logger.info("=" * 70)

    phase3_start = time.time()

    # 路由子任务C → star 拓扑 + cognitive_division 模式
    task_C = nf["TaskRequirement"](
        task_id="subtask_C",
        description="综合各维度结论，评估AI大模型各技术路线的成熟度、潜力和风险，预测2025-2026年技术演进方向",
        required_capabilities=["conclusion_integration", "hypothesis_challenge", "methodology",
                               "trend_analysis", "conflict_resolution", "final_judgment"],
        complexity=nf["TaskComplexity"].EPIC,
        execution_mode="cognitive_division",
        perspective_count=5,
    )
    plan_C = router.route(task_C)

    # 调度
    for aid in plan_C.agent_chain:
        schedule_agent_step(nf, scheduler, aid, "子任务C：CDoL核心推理", privacy_level=1)

    # 构造 CDoL 任务描述
    cdol_task = f"""AI大模型技术趋势综合评估

## 已收集数据摘要
{data_result[:2000]}

## 分析师结论（技术架构+训练范式）
{analyst_result[:1500]}

## 策略师结论（应用场景+安全治理）
{strategy_result[:1500]}

## 评估要求
1. 各技术路线（Transformer/MoE/多模态/Agent）的成熟度评分(0-100)
2. 2025-2026年技术演进方向预测
3. 关键风险和不确定性
4. 对研发投入的建议优先级
"""

    # 手动构造 PerspectiveAssignment — 使用真实的10个Agent ID
    # 这样 CDoL 引擎的 CommunicationLayer 会真正调用 Agent.chat() → DeepSeek API
    PerspectiveAssignment = nf["PerspectiveAssignment"]
    ContextMask = nf["ContextMask"]

    cdol_assignments = [
        PerspectiveAssignment(
            agent_id="strategist",
            perspective_question="从方法论和框架设计角度，评估各AI技术路线的成熟度和未来潜力。你只能看到技术架构和训练范式的分析数据，不能看到应用场景和安全治理的结论。",
            context_mask=ContextMask(
                allowed_evidence=["technical_data", "architecture_analysis", "benchmark_scores"],
                blocked_evidence=["application_scenarios", "safety_governance", "user_feedback"],
                allowed_domains=["technology", "methodology"],
                blocked_domains=["application", "governance"],
                abstraction_level="abstract",
            ),
            role_constraint="methodology_expert",
        ),
        PerspectiveAssignment(
            agent_id="analyst",
            perspective_question="从数据趋势和统计推断角度，分析各模型的能力差距和增长趋势。你只能看到基准性能数据和应用场景分析，不能看到技术架构细节和安全治理结论。",
            context_mask=ContextMask(
                allowed_evidence=["benchmark_scores", "performance_data", "application_analysis"],
                blocked_evidence=["architecture_details", "safety_policies", "internal_design"],
                allowed_domains=["performance", "trend_analysis"],
                blocked_domains=["architecture", "governance"],
                abstraction_level="concrete",
            ),
            role_constraint="data_analyst",
        ),
        PerspectiveAssignment(
            agent_id="critic",
            perspective_question="从质疑和审计角度，审视各技术路线声称的能力是否可靠，风险是否被低估。你只能看到最终输出和验证条目，不能看到推理过程和原始数据。",
            context_mask=ContextMask(
                allowed_evidence=["final_outputs", "verification_entries", "claims"],
                blocked_evidence=["reasoning_process", "raw_data", "internal_discussions"],
                allowed_domains=["verification", "audit"],
                blocked_domains=["experimental", "theoretical"],
                abstraction_level="abstract",
            ),
            role_constraint="skeptic_auditor",
        ),
        PerspectiveAssignment(
            agent_id="researcher",
            perspective_question="从数据和证据收集角度，评估各路线的实证支持强度。你只能看到原始数据和文献片段，不能看到分析结论和治理评估。",
            context_mask=ContextMask(
                allowed_evidence=["raw_evidence", "literature_fragments", "measurement_data"],
                blocked_evidence=["final_conclusions", "synthesis_reports", "policy_recommendations"],
                allowed_domains=["evidence", "literature"],
                blocked_domains=["synthesis", "governance"],
                abstraction_level="concrete",
            ),
            role_constraint="evidence_collector",
        ),
        PerspectiveAssignment(
            agent_id="coder",
            perspective_question="从工程实现和成本效益角度，评估各技术路线的部署可行性和资源需求。你只能看到功能需求和接口规范，不能看到业务全貌和治理结论。",
            context_mask=ContextMask(
                allowed_evidence=["functional_requirements", "interface_specs", "resource_constraints"],
                blocked_evidence=["business_strategy", "safety_policies", "market_analysis"],
                allowed_domains=["engineering", "implementation"],
                blocked_domains=["strategy", "governance"],
                abstraction_level="concrete",
            ),
            role_constraint="implementation_engineer",
        ),
    ]

    # 执行 CDoL 动态协议 — 传入自定义 assignments，启用动态终止
    logger.info("  启动 CDoL 引擎 — Round 0 (独立推理) → [Round 1 (差异归因) → Round 2 (修正) → FusionJudge] × N")
    logger.info(f"  自定义分配: {[a.agent_id for a in cdol_assignments]}")
    logger.info("  动态终止: 最大3轮，FusionJudge判定converge时提前退出")
    cdol_result = cdol_engine.execute(
        task_description=cdol_task,
        assignments=cdol_assignments,
        strategy="evidence_split",
        perspective_count=5,
        max_rounds=3,
    )

    # 收集 CDoL 详情
    cdol_details = {
        "final_answer": cdol_result.final_answer[:3000],
        "synergy_gain": cdol_result.synergy_gain,
        "metrics": cdol_result.metrics,
        "strategy": "evidence_split",
        "perspective_count": 5,
        "max_rounds": 3,
        "total_revision_rounds": cdol_result.total_revision_rounds,
        "terminated_early": cdol_result.terminated_early,
        "communication_rounds": cdol_result.communication_rounds,
        "round0_conclusions": [],
        "round1_attributions": [],
        "round2_revised": [],
        "judgment": {},
        "contradiction_report": {},
    }

    for c in cdol_result.round0_conclusions:
        cdol_details["round0_conclusions"].append({
            "agent_id": c.agent_id,
            "conclusion": c.conclusion[:500],
            "confidence": c.confidence,
            "active_hypotheses": c.active_hypotheses[:3],
            "eliminated_hypotheses": c.eliminated_hypotheses[:3],
            "key_assumptions": c.key_assumptions[:3],
            "uncertainty_markers": c.uncertainty_markers[:3],
        })

    for a in cdol_result.round1_attributions:
        cdol_details["round1_attributions"].append({
            "agent_id": a.agent_id,
            "my_conclusion": a.my_conclusion[:300],
            "contradictions_count": len(a.contradictions),
            "attributions_count": len(a.attributions),
            "revision": (a.revision or "无修正")[:300],
            "revision_reason": a.revision_reason[:200],
        })

    for c in cdol_result.round2_revised:
        cdol_details["round2_revised"].append({
            "agent_id": c.agent_id,
            "conclusion": c.conclusion[:500],
            "confidence": c.confidence,
            "uncertainty_markers": c.uncertainty_markers[:3],
        })

    if cdol_result.judgment:
        j = cdol_result.judgment
        cdol_details["judgment"] = {
            "action": j.action,
            "reason": j.reason,
            "contradiction_type": getattr(j, "contradiction_type", ""),
            "review_targets": getattr(j, "review_targets", []),
        }

    if cdol_result.contradiction_report:
        cdol_details["contradiction_report"] = {
            "total_pairs": cdol_result.contradiction_report.get("total_pairs", 0),
            "types_summary": cdol_result.contradiction_report.get("types_summary", {}),
        }

    EXEC_DATA["cdol_details"] = cdol_details

    phase3_time = time.time() - phase3_start
    EXEC_DATA["phases"].append({
        "name": "阶段三：CDoL核心推理",
        "topology": "star",
        "agents": plan_C.agent_chain,
        "time": phase3_time,
        "synergy_gain": cdol_result.synergy_gain,
        "cdol_action": cdol_details.get("judgment", {}).get("action", "N/A"),
    })
    EXEC_DATA["topology_timeline"].append({
        "phase": "C-CDoL推理",
        "topology": "star",
        "agents": plan_C.agent_chain,
        "confidence": plan_C.confidence,
    })
    EXEC_DATA["route_plans"].append({
        "subtask": "C-CDoL推理",
        "plan_id": plan_C.plan_id,
        "chain": plan_C.agent_chain,
        "topology": "star",
        "confidence": plan_C.confidence,
        "cdol_enabled": plan_C.cdol_enabled,
        "perspective_assignments_count": len(plan_C.perspective_assignments),
    })

    logger.info(f"  CDoL 完成: synergy_gain={cdol_result.synergy_gain:.2f}, "
                f"Round0={len(cdol_result.round0_conclusions)}, "
                f"Round1={len(cdol_result.round1_attributions)}, "
                f"Round2={len(cdol_result.round2_revised)}")

    # ============================================================
    # 阶段四：Critic 质疑 + Synthesizer 综合（dynamic 拓扑）
    # ============================================================
    logger.info("\n" + "=" * 70)
    logger.info("阶段四：Critic质疑 + Synthesizer综合 + Archivist报告 (dynamic 拓扑)")
    logger.info("=" * 70)

    phase4_start = time.time()

    # 路由子任务D → dynamic 拓扑
    task_D = nf["TaskRequirement"](
        task_id="subtask_D",
        description="Critic对CDoL结论进行独立审查，Synthesizer综合质疑生成最终结论，Archivist归档报告",
        required_capabilities=["hypothesis_challenge", "conclusion_review",
                               "conclusion_integration", "conflict_resolution",
                               "report_generation", "traceability"],
        complexity=nf["TaskComplexity"].COMPLEX,
        execution_mode="sequential",
    )
    plan_D = router.route(task_D)

    for aid in plan_D.agent_chain:
        schedule_agent_step(nf, scheduler, aid, "子任务D：质疑+综合+归档", privacy_level=0)

    # Critic 专项质疑
    critic_output = agents["critic"].chat(
        f"""审查以下 NexusFlow CDoL 分析过程和结论，找出所有问题：

CDoL 最终结论：{cdol_result.final_answer[:2000]}
CDoL 指标：synergy_gain={cdol_result.synergy_gain:.2f}
CDoL 矛盾报告：{json.dumps(cdol_result.contradiction_report, ensure_ascii=False, default=str)[:500]}
分析师结论：{analyst_result[:800]}
策略师结论：{strategy_result[:800]}

必须找出至少3个具体问题，每个问题需有证据支撑。
输出JSON: {{"challenges": [{{"target":"", "issue":"", "evidence":"", "severity":"", "suggestion":""}}]}}"""
    )
    logger.info(f"  Critic 输出: {len(critic_output)} chars")

    # Synthesizer 综合
    final_conclusion = agents["synthesizer"].chat(
        f"""综合 CDoL 结果和 Critic 质疑，生成最终修正结论：

CDoL 最终结论：{cdol_result.final_answer[:1500]}
Critic 质疑：{critic_output[:1500]}
CDoL 矛盾报告：{json.dumps(cdol_result.contradiction_report, ensure_ascii=False, default=str)[:300]}

输出：
1. 核心发现（修正后）
2. 各技术路线成熟度评分
3. 2025-2026趋势预测
4. 对 Critic 质疑的逐条回应
5. 置信度评估
6. 关键局限性"""
    )
    logger.info(f"  Synthesizer 最终结论: {len(final_conclusion)} chars")

    # Archivist 报告
    archivist_output = agents["archivist"].chat(
        f"""生成完整的 NexusFlow AI技术趋势分析执行报告：

CDoL 最终结论：{cdol_result.final_answer[:1200]}
修正后结论：{final_conclusion[:1200]}
Critic 质疑：{critic_output[:800]}
CDoL指标：synergy_gain={cdol_result.synergy_gain:.2f}

Markdown报告，包含：方法/数据/结论/质疑记录/修正/置信度"""
    )
    logger.info(f"  Archivist 报告: {len(archivist_output)} chars")

    phase4_time = time.time() - phase4_start
    EXEC_DATA["phases"].append({
        "name": "阶段四：质疑+综合+归档",
        "topology": plan_D.topology_type,
        "agents": plan_D.agent_chain,
        "time": phase4_time,
        "critic_output": critic_output[:2000],
        "final_conclusion": final_conclusion[:2000],
    })
    EXEC_DATA["topology_timeline"].append({
        "phase": "D-质疑综合",
        "topology": plan_D.topology_type,
        "agents": plan_D.agent_chain,
        "confidence": plan_D.confidence,
    })
    EXEC_DATA["route_plans"].append({
        "subtask": "D-质疑综合",
        "plan_id": plan_D.plan_id,
        "chain": plan_D.agent_chain,
        "topology": plan_D.topology_type,
        "confidence": plan_D.confidence,
    })

    EXEC_DATA["final_conclusion"] = final_conclusion[:3000]

    # ---- 全局统计 ----
    EXEC_DATA["stats"]["elapsed"] = time.time() - EXEC_DATA["stats"]["start_time"]

    logger.info("\n" + "=" * 70)
    logger.info(f"Demo 完成! 耗时={EXEC_DATA['stats']['elapsed']:.1f}s, "
                f"API调用={EXEC_DATA['stats']['api_calls']}, "
                f"Tokens={EXEC_DATA['stats']['total_tokens']}")
    logger.info("=" * 70)

    # ---- 保存 JSON 数据 ----
    with open(JSON_DATA_PATH, "w", encoding="utf-8") as f:
        json.dump(EXEC_DATA, f, ensure_ascii=False, indent=2, default=str)
    logger.info(f"执行数据已保存: {JSON_DATA_PATH}")

    # ---- 生成 HTML 报告 ----
    generate_html_report(EXEC_DATA)
    logger.info(f"HTML 报告已生成: {HTML_REPORT_PATH}")

    return EXEC_DATA


# ============================================================
# 9. HTML 报告生成
# ============================================================
def generate_html_report(data: dict):
    """生成深色科技风 HTML 可视化报告"""

    phases_html = ""
    for p in data["phases"]:
        phases_html += f"""
        <div class="phase-card">
            <div class="phase-header">
                <span class="phase-name">{p['name']}</span>
                <span class="topology-badge topology-{p['topology']}">{p['topology'].upper()}</span>
            </div>
            <div class="phase-body">
                <div class="phase-meta">Agents: {', '.join(p['agents'])} | 耗时: {p['time']:.1f}s</div>
                {f'<div class="synergy-gain">Synergy Gain: {p.get("synergy_gain", "N/A")}</div>' if p.get('synergy_gain') else ''}
                {f'<div class="cdol-action">CDoL Action: {p.get("cdol_action", "N/A")}</div>' if p.get('cdol_action') else ''}
            </div>
        </div>"""

    # 拓扑时间线
    timeline_html = ""
    for t in data["topology_timeline"]:
        timeline_html += f"""
        <div class="timeline-item">
            <div class="timeline-phase">{t['phase']}</div>
            <div class="topology-badge topology-{t['topology']}">{t['topology'].upper()}</div>
            <div class="timeline-agents">{', '.join(t['agents'])}</div>
            <div class="timeline-conf">置信度: {t['confidence']:.2f}</div>
        </div>"""

    # 路由决策表
    route_rows = ""
    for r in data["route_plans"]:
        route_rows += f"""
        <tr>
            <td>{r['subtask']}</td>
            <td><span class="topology-badge topology-{r['topology']}">{r['topology'].upper()}</span></td>
            <td>{', '.join(r['chain'])}</td>
            <td>{r['confidence']:.2f}</td>
            <td>{r.get('estimated_cost', 'N/A')}</td>
            <td>{r.get('estimated_latency_ms', 0):.0f}ms</td>
            <td>{'✅ CDoL' if r.get('cdol_enabled') else '—'}</td>
        </tr>"""

    # 调度决策表
    sched_rows = ""
    for s in data["scheduler_decisions"]:
        sched_rows += f"""
        <tr>
            <td>{s['agent']}</td>
            <td>{s['tier']}</td>
            <td>{s['step'][:40]}</td>
            <td><span class="tier-badge tier-{s['scheduled_tier']}">{s['scheduled_tier'].upper()}</span></td>
            <td>{s['resource']}</td>
            <td>{s['reason'][:50]}</td>
            <td>{s['confidence']:.2f}</td>
        </tr>"""

    # CDoL 详情
    cdol = data["cdol_details"]

    r0_rows = ""
    for c in cdol.get("round0_conclusions", []):
        r0_rows += f"""
        <tr>
            <td>{c['agent_id']}</td>
            <td class="conclusion-cell">{c['conclusion'][:200]}</td>
            <td>{c['confidence']:.2f}</td>
            <td>{', '.join(c.get('active_hypotheses', []))[:80]}</td>
            <td>{', '.join(c.get('key_assumptions', []))[:80]}</td>
        </tr>"""

    r1_rows = ""
    for a in cdol.get("round1_attributions", []):
        r1_rows += f"""
        <tr>
            <td>{a['agent_id']}</td>
            <td>{a['contradictions_count']}</td>
            <td>{a['attributions_count']}</td>
            <td class="conclusion-cell">{a['revision'][:200]}</td>
            <td>{a['revision_reason'][:100]}</td>
        </tr>"""

    r2_rows = ""
    for c in cdol.get("round2_revised", []):
        r2_rows += f"""
        <tr>
            <td>{c['agent_id']}</td>
            <td class="conclusion-cell">{c['conclusion'][:200]}</td>
            <td>{c['confidence']:.2f}</td>
            <td>{', '.join(c.get('uncertainty_markers', []))[:80]}</td>
        </tr>"""

    # 信息策略摘要
    mask_rows = ""
    for name, info in data["info_policy_masks"].items():
        m = info.get("mask", {})
        if "error" in m:
            mask_rows += f"""<tr><td>{name}</td><td>{info['tier']}</td><td colspan="4">Error: {m['error']}</td></tr>"""
        else:
            mask_rows += f"""
            <tr>
                <td>{name}</td>
                <td><span class="tier-badge tier-{info['tier']}">{info['tier'].upper()}</span></td>
                <td>{', '.join(m.get('allowed_evidence', []))[:60]}</td>
                <td>{', '.join(m.get('blocked_evidence', []))[:60]}</td>
                <td>{', '.join(m.get('allowed_domains', []))[:50]}</td>
                <td>{m.get('abstraction_level', 'N/A')}</td>
            </tr>"""

    # 矛盾报告
    contr_report = cdol.get("contradiction_report", {})
    types_summary = contr_report.get("types_summary", {})
    contr_summary_html = ""
    for ctype, count in types_summary.items():
        color = {"attributable": "#4ade80", "unattributable": "#f87171",
                 "false_consensus": "#fbbf24", "true_convergence": "#60a5fa"}.get(ctype, "#94a3b8")
        contr_summary_html += f"""<span class="contr-type" style="border-color:{color};color:{color}">{ctype}: {count}</span> """

    judgment = cdol.get("judgment", {})

    # Pre-compute metrics for HTML template (can't use {{}} dict inside f-string)
    cdol_metrics = cdol.get("metrics", {})
    conclusion_delta = cdol_metrics.get("conclusion_delta", "N/A")
    contradiction_resolution = cdol_metrics.get("contradiction_resolution", "N/A")
    confidence_delta = cdol_metrics.get("confidence_delta", "N/A")
    synergy_gain_val = cdol.get("synergy_gain", "N/A")

    stats = data["stats"]

    html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>NexusFlow 系统演示报告 — 动态拓扑 × CDoL × 端边云调度</title>
<style>
:root {{
  --bg: #0f172a; --surface: #1e293b; --surface2: #334155;
  --text: #e2e8f0; --text2: #94a3b8; --accent: #38bdf8;
  --green: #4ade80; --red: #f87171; --yellow: #fbbf24; --purple: #a78bfa;
}}
* {{ margin:0; padding:0; box-sizing:border-box; }}
body {{ background:var(--bg); color:var(--text); font-family:'SF Mono','Fira Code',monospace; padding:20px; line-height:1.6; }}
h1 {{ font-size:1.8em; text-align:center; padding:30px 0 10px; background:linear-gradient(135deg,#38bdf8,#a78bfa); -webkit-background-clip:text; -webkit-text-fill-color:transparent; }}
h2 {{ font-size:1.3em; color:var(--accent); margin:30px 0 15px; padding-bottom:8px; border-bottom:1px solid var(--surface2); }}
h3 {{ font-size:1.1em; color:var(--purple); margin:20px 0 10px; }}
.container {{ max-width:1400px; margin:0 auto; }}
.card {{ background:var(--surface); border:1px solid var(--surface2); border-radius:12px; padding:20px; margin:15px 0; }}
.grid {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(300px,1fr)); gap:15px; }}
.stat-card {{ background:var(--surface); border:1px solid var(--surface2); border-radius:10px; padding:15px; text-align:center; }}
.stat-value {{ font-size:2em; font-weight:bold; color:var(--accent); }}
.stat-label {{ font-size:0.85em; color:var(--text2); margin-top:4px; }}
.topology-badge {{ display:inline-block; padding:3px 12px; border-radius:20px; font-size:0.75em; font-weight:bold; }}
.topology-sequential {{ background:#1e3a5f; color:#60a5fa; }}
.topology-parallel {{ background:#1e3f30; color:#4ade80; }}
.topology-hybrid {{ background:#3f3a1e; color:#fbbf24; }}
.topology-dynamic {{ background:#3f1e3a; color:#f472b6; }}
.topology-star {{ background:#2d1e3f; color:#a78bfa; }}
.tier-badge {{ display:inline-block; padding:2px 8px; border-radius:10px; font-size:0.75em; font-weight:bold; }}
.tier-global {{ background:#1e3a5f; color:#60a5fa; }}
.tier-cdol {{ background:#1e3f30; color:#4ade80; }}
.tier-observer {{ background:#3f3a1e; color:#fbbf24; }}
.tier-edge {{ background:#1e3a5f; color:#60a5fa; }}
.tier-fog {{ background:#1e3f30; color:#4ade80; }}
.tier-cloud {{ background:#2d1e3f; color:#a78bfa; }}
.phase-card {{ background:var(--surface); border:1px solid var(--surface2); border-radius:10px; padding:15px; margin:10px 0; }}
.phase-header {{ display:flex; justify-content:space-between; align-items:center; margin-bottom:10px; }}
.phase-name {{ font-weight:bold; font-size:1.05em; }}
.phase-meta {{ font-size:0.85em; color:var(--text2); margin:5px 0; }}
.synergy-gain {{ color:var(--green); font-weight:bold; margin-top:5px; }}
.cdol-action {{ color:var(--yellow); margin-top:3px; }}
.timeline-item {{ display:flex; align-items:center; gap:15px; padding:10px 15px; background:var(--surface2); border-radius:8px; margin:6px 0; }}
.timeline-phase {{ min-width:140px; font-weight:bold; }}
.timeline-agents {{ color:var(--text2); font-size:0.85em; flex:1; }}
.timeline-conf {{ font-size:0.85em; color:var(--accent); }}
table {{ width:100%; border-collapse:collapse; margin:10px 0; font-size:0.85em; }}
th {{ background:var(--surface2); padding:10px; text-align:left; font-weight:bold; color:var(--accent); border-bottom:2px solid #475569; }}
td {{ padding:8px 10px; border-bottom:1px solid var(--surface2); vertical-align:top; }}
tr:hover td {{ background:rgba(56,189,248,0.05); }}
.conclusion-cell {{ max-width:300px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }}
.contr-type {{ display:inline-block; padding:3px 10px; margin:3px; border:1px solid; border-radius:15px; font-size:0.8em; }}
.svg-container {{ text-align:center; padding:20px; }}
.svg-container svg {{ max-width:100%; height:auto; }}
.final-box {{ background:linear-gradient(135deg,rgba(56,189,248,0.1),rgba(167,139,250,0.1)); border:1px solid var(--accent); border-radius:12px; padding:25px; margin:20px 0; }}
.final-box h3 {{ color:var(--accent); margin-bottom:15px; }}
.final-text {{ white-space:pre-wrap; line-height:1.8; }}
.tag {{ display:inline-block; background:var(--surface2); padding:2px 8px; border-radius:4px; font-size:0.8em; margin:2px; }}
</style>
</head>
<body>
<div class="container">

<h1>🧠 NexusFlow 系统演示报告</h1>
<p style="text-align:center;color:var(--text2);margin-bottom:30px;">动态拓扑路由 × CDoL 三轮协议 × 端边云调度 × 信息不对称策略</p>

<!-- 统计概览 -->
<h2>📊 执行统计</h2>
<div class="grid">
  <div class="stat-card"><div class="stat-value">{stats['elapsed']:.1f}s</div><div class="stat-label">总耗时</div></div>
  <div class="stat-card"><div class="stat-value">{stats['api_calls']}</div><div class="stat-label">API 调用</div></div>
  <div class="stat-card"><div class="stat-value">{stats['total_tokens']:,}</div><div class="stat-label">总 Token</div></div>
  <div class="stat-card"><div class="stat-value">{cdol.get('synergy_gain', 'N/A')}</div><div class="stat-label">CDoL Synergy Gain</div></div>
  <div class="stat-card"><div class="stat-value">{len(data['agents'])}</div><div class="stat-label">Agent 数量</div></div>
  <div class="stat-card"><div class="stat-value">{len(data['topology_timeline'])}</div><div class="stat-label">拓扑切换次数</div></div>
</div>

<!-- 系统架构流程图 -->
<h2>🏗️ 系统架构流程</h2>
<div class="card svg-container">
<svg viewBox="0 0 900 420" xmlns="http://www.w3.org/2000/svg" style="max-width:900px">
  <defs>
    <marker id="arrow" markerWidth="10" markerHeight="7" refX="10" refY="3.5" orient="auto"><polygon points="0 0, 10 3.5, 0 7" fill="#38bdf8"/></marker>
    <linearGradient id="g1" x1="0%" y1="0%" x2="100%" y2="0%"><stop offset="0%" style="stop-color:#38bdf8;stop-opacity:1"/><stop offset="100%" style="stop-color:#a78bfa;stop-opacity:1"/></linearGradient>
  </defs>
  <!-- 用户任务 -->
  <rect x="350" y="10" width="200" height="40" rx="20" fill="url(#g1)" opacity="0.9"/>
  <text x="450" y="35" text-anchor="middle" fill="white" font-size="14" font-weight="bold">用户任务：AI趋势分析</text>
  <!-- DynamicRouter -->
  <rect x="30" y="90" width="220" height="50" rx="10" fill="#1e293b" stroke="#38bdf8" stroke-width="2"/>
  <text x="140" y="112" text-anchor="middle" fill="#38bdf8" font-size="13" font-weight="bold">DynamicTopologyRouter</text>
  <text x="140" y="128" text-anchor="middle" fill="#94a3b8" font-size="10">5种拓扑 · 动态选择</text>
  <!-- 拓扑类型 -->
  <rect x="280" y="85" width="70" height="22" rx="11" fill="#1e3a5f"/><text x="315" y="100" text-anchor="middle" fill="#60a5fa" font-size="9">SEQUENTIAL</text>
  <rect x="360" y="85" width="70" height="22" rx="11" fill="#1e3f30"/><text x="395" y="100" text-anchor="middle" fill="#4ade80" font-size="9">PARALLEL</text>
  <rect x="440" y="85" width="60" height="22" rx="11" fill="#3f3a1e"/><text x="470" y="100" text-anchor="middle" fill="#fbbf24" font-size="9">HYBRID</text>
  <rect x="510" y="85" width="70" height="22" rx="11" fill="#3f1e3a"/><text x="545" y="100" text-anchor="middle" fill="#f472b6" font-size="9">DYNAMIC</text>
  <rect x="590" y="85" width="50" height="22" rx="11" fill="#2d1e3f"/><text x="615" y="100" text-anchor="middle" fill="#a78bfa" font-size="9">STAR</text>
  <!-- EdgeCloudScheduler -->
  <rect x="660" y="90" width="220" height="50" rx="10" fill="#1e293b" stroke="#4ade80" stroke-width="2"/>
  <text x="770" y="112" text-anchor="middle" fill="#4ade80" font-size="13" font-weight="bold">EdgeCloudScheduler</text>
  <text x="770" y="128" text-anchor="middle" fill="#94a3b8" font-size="10">Edge/Fog/Cloud 三层调度</text>
  <!-- InfoPolicy -->
  <rect x="30" y="170" width="220" height="50" rx="10" fill="#1e293b" stroke="#fbbf24" stroke-width="2"/>
  <text x="140" y="192" text-anchor="middle" fill="#fbbf24" font-size="13" font-weight="bold">AgentInformationPolicy</text>
  <text x="140" y="208" text-anchor="middle" fill="#94a3b8" font-size="10">三层信息架构 · ContextMask</text>
  <!-- CDoL Engine -->
  <rect x="300" y="160" width="300" height="70" rx="10" fill="#1e293b" stroke="#a78bfa" stroke-width="2"/>
  <text x="450" y="185" text-anchor="middle" fill="#a78bfa" font-size="14" font-weight="bold">CDoL 三轮协议引擎</text>
  <text x="370" y="210" text-anchor="middle" fill="#94a3b8" font-size="10">R0:独立推理</text>
  <text x="470" y="210" text-anchor="middle" fill="#94a3b8" font-size="10">R1:差异归因</text>
  <text x="560" y="210" text-anchor="middle" fill="#94a3b8" font-size="10">R2:修正</text>
  <!-- FusionJudge -->
  <rect x="340" y="260" width="220" height="45" rx="10" fill="#1e293b" stroke="#f87171" stroke-width="2"/>
  <text x="450" y="282" text-anchor="middle" fill="#f87171" font-size="13" font-weight="bold">FusionJudge 融合判断</text>
  <text x="450" y="297" text-anchor="middle" fill="#94a3b8" font-size="10">4类矛盾分类 · 真实收敛检测</text>
  <!-- 10 Agents -->
  <rect x="660" y="170" width="220" height="50" rx="10" fill="#1e293b" stroke="#60a5fa" stroke-width="2"/>
  <text x="770" y="192" text-anchor="middle" fill="#60a5fa" font-size="13" font-weight="bold">10-Agent 协作池</text>
  <text x="770" y="208" text-anchor="middle" fill="#94a3b8" font-size="10">Cloud/Edge/Terminal 三层</text>
  <!-- GlobalMemory -->
  <rect x="30" y="260" width="220" height="45" rx="10" fill="#1e293b" stroke="#38bdf8" stroke-width="1.5"/>
  <text x="140" y="282" text-anchor="middle" fill="#38bdf8" font-size="12" font-weight="bold">GlobalMemoryPool</text>
  <text x="140" y="297" text-anchor="middle" fill="#94a3b8" font-size="10">语义检索 · 强制全局同步</text>
  <!-- 结论 -->
  <rect x="300" y="340" width="300" height="45" rx="22" fill="url(#g1)" opacity="0.8"/>
  <text x="450" y="367" text-anchor="middle" fill="white" font-size="14" font-weight="bold">最终结论 + HTML 报告</text>
  <!-- 箭头 -->
  <line x1="450" y1="50" x2="140" y2="90" stroke="#38bdf8" stroke-width="1.5" marker-end="url(#arrow)"/>
  <line x1="450" y1="50" x2="770" y2="90" stroke="#4ade80" stroke-width="1.5" marker-end="url(#arrow)"/>
  <line x1="140" y1="140" x2="140" y2="170" stroke="#fbbf24" stroke-width="1.5" marker-end="url(#arrow)"/>
  <line x1="250" y1="195" x2="300" y2="195" stroke="#a78bfa" stroke-width="1.5" marker-end="url(#arrow)"/>
  <line x1="600" y1="195" x2="660" y2="195" stroke="#60a5fa" stroke-width="1.5" marker-end="url(#arrow)"/>
  <line x1="450" y1="230" x2="450" y2="260" stroke="#f87171" stroke-width="1.5" marker-end="url(#arrow)"/>
  <line x1="140" y1="220" x2="140" y2="260" stroke="#38bdf8" stroke-width="1.5" marker-end="url(#arrow)"/>
  <line x1="450" y1="305" x2="450" y2="340" stroke="#38bdf8" stroke-width="1.5" marker-end="url(#arrow)"/>
</svg>
</div>

<!-- 动态拓扑切换时间线 -->
<h2>🔀 动态拓扑切换时间线</h2>
<div class="card">
  {timeline_html}
</div>

<!-- 各阶段执行详情 -->
<h2>📋 各阶段执行详情</h2>
{phases_html}

<!-- 路由决策详情 -->
<h2>🧭 路由决策详情</h2>
<div class="card" style="overflow-x:auto;">
<table>
  <tr><th>子任务</th><th>拓扑</th><th>Agent链</th><th>置信度</th><th>预估Token成本</th><th>预估延迟</th><th>CDoL</th></tr>
  {route_rows}
</table>
</div>

<!-- 端边云调度决策 -->
<h2>☁️ 端边云调度决策</h2>
<div class="card" style="overflow-x:auto;">
<table>
  <tr><th>Agent</th><th>角色层</th><th>步骤</th><th>调度层</th><th>资源</th><th>原因</th><th>置信度</th></tr>
  {sched_rows}
</table>
</div>

<!-- CDoL 三轮协议详情 -->
<h2>🧬 CDoL 三轮协议详情</h2>
<div class="card">
  <div class="grid">
    <div class="stat-card"><div class="stat-value" style="color:var(--green)">{cdol.get('synergy_gain', 'N/A')}</div><div class="stat-label">Synergy Gain</div></div>
    <div class="stat-card"><div class="stat-value" style="color:var(--yellow)">{judgment.get('action', 'N/A')}</div><div class="stat-label">FusionJudge 决策</div></div>
    <div class="stat-card"><div class="stat-value" style="color:var(--purple)">{cdol.get('strategy', 'N/A')}</div><div class="stat-label">分解策略</div></div>
    <div class="stat-card"><div class="stat-value" style="color:var(--accent)">{contr_report.get('total_pairs', 0)}</div><div class="stat-label">矛盾对数</div></div>
  </div>

  <h3>Round 0 — 独立推理（信息不对称）</h3>
  <p style="color:var(--text2);font-size:0.85em;margin-bottom:10px;">每个Agent在受限上下文下独立推理，产生不同的中间结论</p>
  <table>
    <tr><th>Agent</th><th>结论</th><th>置信度</th><th>活跃假设</th><th>关键假设</th></tr>
    {r0_rows}
  </table>

  <h3>Round 1 — 差异归因</h3>
  <p style="color:var(--text2);font-size:0.85em;margin-bottom:10px;">每个Agent看到其他人的中间结论（但看不到对方的视角问题），进行差异归因</p>
  <table>
    <tr><th>Agent</th><th>矛盾数</th><th>归因数</th><th>修正结论</th><th>修正原因</th></tr>
    {r1_rows}
  </table>

  <h3>Round 2 — 修正结论</h3>
  <p style="color:var(--text2);font-size:0.85em;margin-bottom:10px;">基于归因修正结论</p>
  <table>
    <tr><th>Agent</th><th>修正后结论</th><th>置信度</th><th>不确定性标记</th></tr>
    {r2_rows}
  </table>

  <h3>FusionJudge — 融合判断</h3>
  <div class="card">
    <div><strong>决策动作:</strong> <span class="tag" style="background:{'#1e3f30' if judgment.get('action')=='converge' else '#3f3a1e'};color:{'#4ade80' if judgment.get('action')=='converge' else '#fbbf24'}">{judgment.get('action', 'N/A')}</span></div>
    <div style="margin-top:8px"><strong>原因:</strong> {judgment.get('reason', 'N/A')}</div>
    <div style="margin-top:8px"><strong>矛盾类型:</strong> {judgment.get('contradiction_type', 'N/A')}</div>
    <div style="margin-top:10px"><strong>矛盾分类:</strong> {contr_summary_html or '无'}</div>
  </div>

  <h3>Synergy Gain 计算</h3>
  <div class="card">
    <p style="color:var(--text2);font-size:0.85em;">synergy_gain = 0.4 × conclusion_delta + 0.3 × contradiction_resolution + 0.3 × confidence_delta</p>
    <div class="grid" style="margin-top:10px;">
      <div class="stat-card"><div class="stat-value" style="font-size:1.2em">{conclusion_delta}</div><div class="stat-label">conclusion_delta (×0.4)</div></div>
      <div class="stat-card"><div class="stat-value" style="font-size:1.2em">{contradiction_resolution}</div><div class="stat-label">contradiction_resolution (×0.3)</div></div>
      <div class="stat-card"><div class="stat-value" style="font-size:1.2em">{confidence_delta}</div><div class="stat-label">confidence_delta (×0.3)</div></div>
      <div class="stat-card"><div class="stat-value" style="font-size:1.2em;color:var(--green)">{synergy_gain_val}</div><div class="stat-label">synergy_gain (加权总和)</div></div>
    </div>
  </div>
</div>

<!-- 信息策略摘要 -->
<h2>🔒 信息不对称策略 (ContextMask)</h2>
<div class="card" style="overflow-x:auto;">
<table>
  <tr><th>Agent</th><th>层级</th><th>可见证据</th><th>屏蔽证据</th><th>可见领域</th><th>抽象层级</th></tr>
  {mask_rows}
</table>
</div>

<!-- 最终结论 -->
<h2>🎯 最终结论</h2>
<div class="final-box">
  <h3>Synthesizer 综合结论</h3>
  <div class="final-text">{data.get('final_conclusion', '无')}</div>
</div>

<p style="text-align:center;color:var(--text2);margin-top:40px;font-size:0.8em;">
  NexusFlow v4.0 · 动态拓扑 × CDoL × 端边云调度 · {time.strftime('%Y-%m-%d %H:%M')}
</p>

</div>
</body>
</html>"""

    with open(HTML_REPORT_PATH, "w", encoding="utf-8") as f:
        f.write(html)
    logger.info(f"HTML 报告已写入: {HTML_REPORT_PATH}")


# ============================================================
# Main
# ============================================================
if __name__ == "__main__":
    try:
        result = run_demo()
        print(f"\n✅ Demo 完成!")
        print(f"  耗时: {result['stats']['elapsed']:.1f}s")
        print(f"  API调用: {result['stats']['api_calls']}")
        print(f"  Tokens: {result['stats']['total_tokens']}")
        print(f"  CDoL Synergy Gain: {result['cdol_details'].get('synergy_gain', 'N/A')}")
        print(f"  HTML报告: {HTML_REPORT_PATH}")
        print(f"  JSON数据: {JSON_DATA_PATH}")
    except Exception as e:
        traceback.print_exc()
        print(f"\n❌ Demo 失败: {e}")
