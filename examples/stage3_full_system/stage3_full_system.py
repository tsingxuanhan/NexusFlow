#!/usr/bin/env python3
"""
NexusFlow Stage-3: Full System Integration Benchmark
=====================================================
用NexusFlow完整项目系统跑NOAA和WHO benchmark任务。

完整管线:
  Task → NexusOrchestrator → AgentInformationPolicy(信息不对称)
       → CognitiveDivisionEngine(CDoL三轮协议)
         → PerspectiveDecomposer(视角分解) 
         → CommunicationLayer(Round0/1/2)
         → FusionJudge(融合判断)
         → InsightDistiller(经验蒸馏)
       → GlobalMemoryPool(记忆归档)
       → AdaptiveContextManager(自适应上下文)

10个Agent全部通过DeepSeek API真实调用LLM。
Researcher通过CLI真实调用NOAA/WHO数据技能。
"""

import sys
import os
import json
import time
import subprocess
import logging
import urllib.request
import traceback
from typing import Any, Dict, List, Optional, Callable
from dataclasses import dataclass, field

# ============================================================
# 0. 环境配置
# ============================================================
NEXUSFLOW_DIR = "/app/data/所有对话/主对话/NexusFlow-repo"
OUTPUT_BASE = "/app/data/所有对话/主对话/nexusflow-ppt"
NOAA_CLI = "/app/data/所有对话/主对话/.skills/skill_noaa-data-skill/bin/_cli_wrapper.py"
WHO_CLI = "/app/data/所有对话/主对话/.skills/skill_who-data-skill/scripts/_cli_wrapper.py"

DEEPSEEK_API_KEY = "YOUR_DEEPSEEK_API_KEY"  # Set your API key here
DEEPSEEK_URL = "https://api.deepseek.com/v1/chat/completions"

# 添加NexusFlow到sys.path
sys.path.insert(0, NEXUSFLOW_DIR)

# 日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(name)s] %(levelname)s: %(message)s',
    datefmt='%H:%M:%S',
)
logger = logging.getLogger("Stage3")

# 全局统计
_stats = {
    "api_calls": 0,
    "data_calls": 0,
    "total_tokens": 0,
    "start_time": 0,
    "agent_interactions": [],
}


# ============================================================
# 1. DeepSeek LLM Wrapper
# ============================================================

def deepseek_chat(prompt: str, system: str = "", model: str = "deepseek-chat",
                  max_tokens: int = 4096, temperature: float = 0.3) -> str:
    """DeepSeek API调用 — NexusFlow所有Agent共享此LLM"""
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
        with urllib.request.urlopen(req, timeout=120) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            _stats["api_calls"] += 1
            _stats["total_tokens"] += data.get("usage", {}).get("total_tokens", 0)
            return data["choices"][0]["message"]["content"]
    except Exception as e:
        logger.error(f"DeepSeek API error: {e}")
        return f"[API_ERROR: {e}]"


# ============================================================
# 2. Data Skill Tools (NOAA / WHO CLI)
# ============================================================

def call_noaa(operation: str, params: Dict[str, str] = None) -> str:
    _stats["data_calls"] += 1
    cmd = ["python3", NOAA_CLI, "call", operation]
    if params:
        for k, v in params.items():
            cmd.extend(["--param", f"{k}={v}"])
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=60,
                          cwd="/app/data/所有对话/主对话/.skills/skill_noaa-data-skill")
        return r.stdout.strip()
    except Exception as e:
        return f"[NOAA_ERROR: {e}]"


def call_who(operation: str, params: Dict[str, str] = None) -> str:
    _stats["data_calls"] += 1
    cmd = ["python3", WHO_CLI, "call", operation]
    if params:
        for k, v in params.items():
            cmd.extend(["--param", f"{k}={v}"])
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=60,
                          cwd="/app/data/所有对话/主对话/.skills/skill_who-data-skill")
        return r.stdout.strip()
    except Exception as e:
        return f"[WHO_ERROR: {e}]"


# ============================================================
# 3. 10-Agent Registry (真实Agent实例)
# ============================================================

@dataclass
class SimpleAgent:
    """轻量Agent — 用于CDoL引擎"""
    agent_id: str
    display_name: str
    capabilities: List[str] = field(default_factory=list)
    domain_expertise: List[str] = field(default_factory=list)
    tier: str = "cloud"  # cloud/edge/terminal
    system_prompt: str = ""

    def chat(self, prompt: str, context: str = "") -> str:
        """Agent推理 — 通过DeepSeek API"""
        full_prompt = prompt
        if context:
            full_prompt += f"\n\n## 可用上下文\n{context}"
        
        _stats["agent_interactions"].append({
            "agent": self.agent_id,
            "tier": self.tier,
            "time": time.time() - _stats["start_time"],
            "prompt_len": len(full_prompt) + len(self.system_prompt),
        })
        
        return deepseek_chat(full_prompt, system=self.system_prompt)


# 10个Agent的系统提示词（来自NexusFlow Agent Registry的CDoL角色映射）
AGENT_PROMPTS = {
    "coordinator": """你是NexusFlow的协调者(Coordinator)。
职责：任务拆解、角色分配、进度协调、结论汇总。
你拥有全局视野，可以看到所有Agent的输出。
输出格式：JSON（assignments/progress/summary）。""",

    "strategist": """你是NexusFlow的策略师(Strategist)。
职责：设计分析框架、方法论选择、权重方案、评估标准。
你的输出是其他角色的方法论蓝图。
输出格式：结构化方案（维度/方法/公式/权重/验证）。""",

    "researcher": """你是NexusFlow的研究员(Researcher)。
职责：从数据源获取原始数据。你有NOAA/WHO数据技能的访问权限。
只负责获取数据，不做分析。输出JSON格式数据+元信息。
工具：call_noaa(operation, params) / call_who(operation, params)""",

    "coder": """你是NexusFlow的编码专家(Coder)。
职责：实现归一化/统计/回归等计算。编写可复现的Python代码。
只输出代码和计算结果，不做结论性解读。""",

    "analyst": """你是NexusFlow的分析师(Analyst)。
职责：基于Coder的计算结果解读数据、发现趋势、生成分析结论。
输出：各维度结论 + 排名 + 置信度。""",

    "observer": """你是NexusFlow的监控者(Observer)。
职责：数据质量监控、异常值检测、数据完整性检查。
只关注数据层面的问题，不做结论性判断。""",

    "monitor": """你是NexusFlow的进度监控者(Monitor)。
职责：追踪执行进度、统计API调用、识别效率问题、超时预警。
输出结构化进度报告。""",

    "critic": """你是NexusFlow的批评者(Critic)——结论质量守门人。
核心职责：
1. 质疑每一个假设（是否有依据？）
2. 挑战每一个结论（是否过度声称？）
3. 检查方法论缺陷（是否有偏差？）
4. 验证数据使用（是否有遗漏？）

规则：
- 必须找出至少3个具体问题
- 每个质疑必须有证据支撑
- 不要给出正面评价，只指出问题
- 严重程度分级：high/medium/low""",

    "synthesizer": """你是NexusFlow的综合者(Synthesizer)。
职责：整合所有角色结论、处理Critic质疑、生成最终结论。
当Critic提出质疑时，权衡各方做出裁决。
输出：修正后的结论 + 置信度 + 局限性。""",

    "archivist": """你是NexusFlow的档案师(Archivist)。
职责：整理所有产物、生成结构化Markdown报告、确保可追溯。
报告必须包含：方法/数据/结论/质疑记录/修正/置信度。""",
}

# Agent层级分配
AGENT_TIERS = {
    "coordinator": "cloud", "strategist": "cloud", "researcher": "cloud",
    "critic": "cloud", "synthesizer": "cloud", "archivist": "cloud",
    "coder": "edge", "analyst": "edge",
    "observer": "terminal", "monitor": "terminal",
}

AGENT_CAPS = {
    "coordinator": ["task_decomposition", "orchestration", "summary"],
    "strategist": ["methodology", "framework_design", "weight_design"],
    "researcher": ["data_collection", "noaa_skill", "who_skill"],
    "coder": ["python", "statistics", "regression", "normalization"],
    "analyst": ["trend_analysis", "statistical_inference", "ranking"],
    "observer": ["quality_check", "anomaly_detection", "completeness"],
    "monitor": ["progress_tracking", "api_counting", "timeout_warning"],
    "critic": ["hypothesis_challenge", "conclusion_review", "methodology_audit"],
    "synthesizer": ["conclusion_integration", "conflict_resolution", "final_judgment"],
    "archivist": ["report_generation", "traceability", "documentation"],
}


def create_agents() -> Dict[str, SimpleAgent]:
    """创建10个Agent实例"""
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
# 4. 导入NexusFlow核心模块
# ============================================================

def import_nexusflow():
    """导入NexusFlow核心组件"""
    from agent_information_policy import (
        AgentInformationPolicy, AgentTier, get_information_policy
    )
    from cognitive_division_engine import (
        CognitiveDivisionEngine, PerspectiveDecomposer,
        CommunicationLayer, FusionJudge, InsightDistiller, InsightStore,
        ContextMask, IntermediateConclusion, CDoLResult,
    )
    from adaptive_context_manager import GlobalMemoryPool, create_context_manager
    
    return {
        "AgentInformationPolicy": AgentInformationPolicy,
        "AgentTier": AgentTier,
        "get_information_policy": get_information_policy,
        "CognitiveDivisionEngine": CognitiveDivisionEngine,
        "PerspectiveDecomposer": PerspectiveDecomposer,
        "CommunicationLayer": CommunicationLayer,
        "FusionJudge": FusionJudge,
        "InsightDistiller": InsightDistiller,
        "InsightStore": InsightStore,
        "ContextMask": ContextMask,
        "IntermediateConclusion": IntermediateConclusion,
        "CDoLResult": CDoLResult,
        "GlobalMemoryPool": GlobalMemoryPool,
        "create_context_manager": create_context_manager,
    }


# ============================================================
# 5. 数据采集管线
# ============================================================

def collect_noaa_data() -> str:
    """Researcher: 采集NOAA数据"""
    stations = {
        "北京": "GHCND:CHM00054511",
        "天津": "GHCND:CHM00054527",
        "石家庄": "GHCND:CHM00053698",
        "济南": "GHCND:CHM00054823",
        "太原": "GHCND:CHM00053772",
    }
    all_data = []
    for city, sid in stations.items():
        logger.info(f"  [Researcher] 采集 {city} ({sid})")
        temp = call_noaa("get-annual-summaries", {
            "dataset_id": "GHCND", "station_id": sid,
            "start_year": "2015", "end_year": "2024",
        })
        all_data.append({"city": city, "station": sid, "data": temp[:1500]})
        time.sleep(0.3)
    return json.dumps(all_data, ensure_ascii=False)[:6000]


def collect_who_data() -> str:
    """Researcher: 采集WHO数据"""
    indicators = {
        "life_expectancy": "WHOSIS_000001",
        "cancer_mortality": "WHS2_160",
        "maternal_mortality": "MDG_0000000026",
        "dtp3_immunization": "WHS4_100",
        "air_pollution": "AIR_9",
    }
    countries = {"中国": "CHN", "巴西": "BRA", "俄罗斯": "RUS", "印度": "IND", "南非": "ZAF"}
    
    all_data = []
    for ind_name, ind_code in indicators.items():
        for country, code in countries.items():
            logger.info(f"  [Researcher] 采集 {ind_name} / {country}")
            raw = call_who("get-indicator-data", {
                "indicator_code": ind_code, "spatial_dim": code, "top": "5",
            })
            all_data.append({
                "indicator": ind_name, "code": ind_code,
                "country": country, "cc": code, "data": raw[:800],
            })
            time.sleep(0.2)
    return json.dumps(all_data, ensure_ascii=False)[:8000]


# ============================================================
# 6. Stage-3 Full Pipeline Execution
# ============================================================

def run_stage3(task_name: str, task_desc: str, data_collector, output_dir: str):
    """
    完整NexusFlow管线执行：
    1. 初始化所有组件
    2. Agent信息采集
    3. CDoL引擎执行（含信息策略+三轮协议+融合判断+经验蒸馏）
    4. 产物输出
    """
    _stats["start_time"] = time.time()
    os.makedirs(output_dir, exist_ok=True)
    
    logger.info(f"{'='*60}")
    logger.info(f"NexusFlow Stage-3 Full System: {task_name}")
    logger.info(f"{'='*60}")
    
    # ---- Step 0: 导入NexusFlow核心模块 ----
    logger.info("[Step 0] 导入NexusFlow核心模块...")
    nf = import_nexusflow()
    logger.info(f"  模块导入完成: {list(nf.keys())}")
    
    # ---- Step 1: 创建Agent池 ----
    logger.info("[Step 1] 创建10个Agent实例...")
    agents = create_agents()
    logger.info(f"  Agent池: {list(agents.keys())}")
    
    # ---- Step 2: 初始化信息策略 ----
    logger.info("[Step 2] 初始化AgentInformationPolicy...")
    info_policy = nf["get_information_policy"]()
    policy_summary = info_policy.get_policy_summary()
    logger.info(f"  信息策略: {json.dumps(policy_summary, ensure_ascii=False)[:500]}")
    
    # ---- Step 3: 初始化记忆系统 ----
    logger.info("[Step 3] 初始化GlobalMemoryPool + AdaptiveContextManager...")
    memory_pool = nf["GlobalMemoryPool"]()
    context_mgr = nf["create_context_manager"](
        information_policy=info_policy, llm_chat=deepseek_chat
    )
    logger.info("  记忆系统就绪")
    
    # ---- Step 4: 初始化CDoL引擎 ----
    logger.info("[Step 4] 初始化CognitiveDivisionEngine...")
    insight_store = nf["InsightStore"](filepath=f"{output_dir}/insight_store.json")
    cdol_engine = nf["CognitiveDivisionEngine"](
        agents=agents,
        memory_pool=memory_pool,
        llm_chat=deepseek_chat,
        insight_store=insight_store,
        information_policy=info_policy,
    )
    logger.info("  CDoL引擎就绪")
    
    # ---- Step 5: 数据采集 ----
    logger.info("[Step 5] Researcher采集数据...")
    raw_data = data_collector()
    logger.info(f"  数据采集完成: {len(raw_data)} chars, {_stats['data_calls']} API calls")
    
    # ---- Step 6: CDoL执行（核心） ----
    logger.info("[Step 6] 执行CDoL三轮协议...")
    logger.info("  Round 0: 各Agent独立推理")
    logger.info("  Round 1: 差异归因")
    logger.info("  Round 2: 修正结论")
    
    # 构造完整的任务描述（含数据）
    full_task = f"""{task_desc}

## 已采集数据
{raw_data[:4000]}

## 分析要求
1. 每个维度独立评分(0-100)
2. 综合排名
3. 置信度评估
4. 局限性说明
"""
    
    cdol_result = cdol_engine.execute(
        task_description=full_task,
        perspective_count=6,  # CDoL引擎内部选6个主要perspective
    )
    
    logger.info(f"  CDoL执行完成: synergy_gain={cdol_result.synergy_gain:.2f}")
    logger.info(f"  Round0结论: {len(cdol_result.round0_conclusions)}")
    logger.info(f"  Round1归因: {len(cdol_result.round1_attributions)}")
    logger.info(f"  Round2修正: {len(cdol_result.round2_revised)}")
    
    # ---- Step 7: 额外角色执行（Critic专项质疑 + Archivist报告） ----
    logger.info("[Step 7] Critic独立审查 + Synthesizer综合 + Archivist报告...")
    
    # 汇总CDoL产物
    cdol_summary = _summarize_cdol_result(cdol_result)
    
    # Critic专项质疑
    critic = agents["critic"]
    critic_output = critic.chat(f"""审查以下NexusFlow CDoL分析过程和结论，找出所有问题：

任务：{task_desc[:500]}
CDoL最终结论：{cdol_result.final_answer[:2000]}
CDoL指标：{json.dumps(cdol_result.metrics, ensure_ascii=False)[:500]}
原始数据摘要：{raw_data[:1000]}

必须找出至少3个具体问题，每个问题需有证据支撑。
输出JSON: {{"challenges": [{{"target":"", "issue":"", "evidence":"", "severity":"", "suggestion":""}}]}}
""", context=cdol_summary[:2000])
    
    logger.info(f"  Critic输出: {len(critic_output)} chars")
    
    # Synthesizer回应质疑并生成最终结论
    synthesizer = agents["synthesizer"]
    final_conclusion = synthesizer.chat(f"""综合CDoL结果和Critic质疑，生成最终修正结论：

CDoL最终结论：{cdol_result.final_answer[:2000]}
Critic质疑：{critic_output[:1500]}
CDoL矛盾报告：{str(cdol_result.contradiction_report)[:500]}

输出：
1. 核心发现（修正后）
2. 综合排名/评分
3. 对Critic质疑的逐条回应
4. 置信度评估
5. 关键局限性
""", context=f"CDoL: {cdol_summary}\nCritic: {critic_output}")
    
    logger.info(f"  Synthesizer最终结论: {len(final_conclusion)} chars")
    
    # Archivist生成报告
    archivist = agents["archivist"]
    report = archivist.chat(f"""生成完整的NexusFlow Stage-3 Benchmark执行报告：

任务：{task_name}
任务描述：{task_desc[:300]}
CDoL最终结论：{cdol_result.final_answer[:1500]}
修正后结论：{final_conclusion[:1500]}
Critic质疑：{critic_output[:1000]}
CDoL指标：{json.dumps(cdol_result.metrics, ensure_ascii=False)[:300]}
执行统计：API={_stats['api_calls']}, Data={_stats['data_calls']}, Tokens={_stats['total_tokens']}

Markdown报告格式：
# {task_name} - NexusFlow Stage-3 Full System Report
## 1. 系统架构
## 2. 执行管线
## 3. 数据
## 4. CDoL分析过程
## 5. Critic审查记录
## 6. 修正后结论
## 7. 量化指标
## 8. 局限性
""", context=f"All: {cdol_summary[:1000]}\nFinal: {final_conclusion[:1000]}")
    
    # ---- Step 8: 保存产物 ----
    logger.info("[Step 8] 保存产物...")
    elapsed = time.time() - _stats["start_time"]
    
    # 报告
    with open(f"{output_dir}/ten_roles_report.md", "w", encoding="utf-8") as f:
        f.write(report)
    
    # Critic质疑
    with open(f"{output_dir}/critic_challenges.md", "w", encoding="utf-8") as f:
        f.write(f"# Critic审查记录 - {task_name}\n\n")
        f.write(f"## Critic输出\n\n{critic_output}\n\n")
        f.write(f"## Synthesizer回应\n\n{final_conclusion}\n\n")
    
    # CDoL完整结果
    cdol_dump = {
        "final_answer": cdol_result.final_answer[:3000],
        "synergy_gain": cdol_result.synergy_gain,
        "metrics": cdol_result.metrics,
        "contradiction_report": str(cdol_result.contradiction_report)[:2000],
        "round0_count": len(cdol_result.round0_conclusions),
        "round1_count": len(cdol_result.round1_attributions),
        "round2_count": len(cdol_result.round2_revised),
        "insights": str(getattr(cdol_result, 'insights', {}))[:1000],
        "information_policy_summary": cdol_result.information_policy_summary,
    }
    with open(f"{output_dir}/cdol_result.json", "w", encoding="utf-8") as f:
        json.dump(cdol_dump, f, ensure_ascii=False, indent=2, default=str)
    
    # 执行统计
    metrics = {
        "task_name": task_name,
        "total_time_seconds": elapsed,
        "deepseek_api_calls": _stats["api_calls"],
        "data_skill_calls": _stats["data_calls"],
        "total_tokens": _stats["total_tokens"],
        "agent_interactions": len(_stats["agent_interactions"]),
        "cdol_synergy_gain": cdol_result.synergy_gain,
        "cdol_round0_conclusions": len(cdol_result.round0_conclusions),
        "cdol_round1_attributions": len(cdol_result.round1_attributions),
        "cdol_round2_revised": len(cdol_result.round2_revised),
        "nexusflow_modules_used": list(nf.keys()),
    }
    with open(f"{output_dir}/execution_stats.json", "w", encoding="utf-8") as f:
        json.dump(metrics, f, ensure_ascii=False, indent=2)
    
    # Agent交互日志
    with open(f"{output_dir}/agent_interactions.json", "w", encoding="utf-8") as f:
        json.dump(_stats["agent_interactions"], f, ensure_ascii=False, indent=2, default=str)
    
    # 原始数据
    with open(f"{output_dir}/raw_data.json", "w", encoding="utf-8") as f:
        f.write(raw_data)
    
    logger.info(f"{'='*60}")
    logger.info(f"Stage-3 完成: {task_name}")
    logger.info(f"  耗时: {elapsed:.1f}s")
    logger.info(f"  API调用: {_stats['api_calls']}")
    logger.info(f"  数据调用: {_stats['data_calls']}")
    logger.info(f"  Tokens: {_stats['total_tokens']}")
    logger.info(f"  CDoL协同增益: {cdol_result.synergy_gain:.2f}")
    logger.info(f"  产物: {output_dir}/")
    logger.info(f"{'='*60}")
    
    return {
        "report": report,
        "critic": critic_output,
        "final_conclusion": final_conclusion,
        "cdol_result": cdol_dump,
        "metrics": metrics,
    }


def _summarize_cdol_result(result) -> str:
    """将CDoL结果序列化为文本摘要"""
    parts = []
    parts.append(f"最终结论: {result.final_answer[:1000]}")
    parts.append(f"协同增益: {result.synergy_gain:.2f}")
    parts.append(f"指标: {json.dumps(result.metrics, ensure_ascii=False)[:300]}")
    
    if result.round0_conclusions:
        parts.append("\n--- Round 0 结论 ---")
        for c in result.round0_conclusions[:6]:
            parts.append(f"  [{c.agent_id}] {c.conclusion[:200]} (置信度:{c.confidence:.2f})")
    
    if result.round1_attributions:
        parts.append("\n--- Round 1 归因 ---")
        for a in result.round1_attributions[:6]:
            parts.append(f"  [{a.agent_id}] 修正: {a.revision[:100] if a.revision else 'N/A'}")
    
    if result.contradiction_report:
        try:
            parts.append(f"\n矛盾报告: {json.dumps(result.contradiction_report, ensure_ascii=False, default=str)[:500]}")
        except Exception:
            parts.append(f"\n矛盾报告: {str(result.contradiction_report)[:500]}")
    
    return "\n".join(parts)


# ============================================================
# 7. 任务定义
# ============================================================

NOAA_TASK = """NOAA气候综合诊断任务：对中国华北5城市（北京、天津、石家庄、济南、太原）2015-2024年气候数据进行多维度分析。
维度：1)温度趋势 2)降水变化 3)极端事件频率 4)气候舒适度 5)城市综合排名。
要求：各维度评分(0-100)、综合排名、置信度。"""

WHO_TASK = """WHO全球健康综合诊断任务：对BRICS五国（中国、巴西、俄罗斯、印度、南非）健康状况进行多维度评估。
维度：1)预期寿命 2)疾病负担 3)妇幼健康 4)免疫覆盖 5)环境健康 6)综合健康指数。
要求：各国各维度评分(0-100)、综合排名、置信度。"""


# ============================================================
# Main
# ============================================================

if __name__ == "__main__":
    task = sys.argv[1] if len(sys.argv) > 1 else "who"
    
    results = {}
    
    if task in ("noaa", "both"):
        results["noaa"] = run_stage3(
            "NOAA Climate Diagnosis",
            NOAA_TASK,
            collect_noaa_data,
            f"{OUTPUT_BASE}/stage3_noaa/ten_roles"
        )
    
    if task in ("who", "both"):
        results["who"] = run_stage3(
            "WHO Health Diagnosis",
            WHO_TASK,
            collect_who_data,
            f"{OUTPUT_BASE}/stage3_who/ten_roles"
        )
    
    # 总统计
    print(f"\n{'='*60}")
    print(f"NexusFlow Stage-3 Full System Benchmark 完成!")
    print(f"Total API: {_stats['api_calls']}, Data: {_stats['data_calls']}, Tokens: {_stats['total_tokens']}")
    print(f"{'='*60}")
