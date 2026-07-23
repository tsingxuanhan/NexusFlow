#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
NexusFlow 端-边-云三层调度实机验证（使用项目真实 EdgeCloudScheduler）
Edge-Fog-Cloud Real-Machine Verification with Actual Project Code

核心改进：直接 import 并使用 nexusflow.core.edge_cloud_scheduler.EdgeCloudScheduler，
不再使用简化版if-else调度逻辑。验证的是项目本身的代码，不是重新实现。

三层资源配置（注册到真实 EdgeCloudScheduler）：
  Edge(端侧)   → Ollama qwen3.5:9b     — 模拟手机/边缘轻量设备 (6.6GB)
  Fog(边缘)    → Ollama deepseek-r1:14b — 模拟边缘网关/本地PC (9GB)
  Cloud(云端)  → DeepSeek API          — 真实云服务
"""

import sys
import os
import json
import time
import re
from datetime import datetime
from pathlib import Path

import requests

# ═══════════════════════════════════════════════════
# 导入 NexusFlow 项目真实调度器
# ═══════════════════════════════════════════════════

# 添加项目根目录到路径（支持 examples/edge_cloud_scheduling/ 下的导入）
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, project_root)

from nexusflow.core.edge_cloud_scheduler import (
    EdgeCloudScheduler,
    TierResource,
    DeployTier,
    SchedulingPolicy,
    SchedulingDecision,
)

# ═══════════════════════════════════════════════════
# 配置
# ═══════════════════════════════════════════════════

DEEPSEEK_API_KEY = os.environ.get("DEEPSEEK_API_KEY", "")
if not DEEPSEEK_API_KEY:
    print("ERROR: DEEPSEEK_API_KEY environment variable not set.")
    sys.exit(1)
DEEPSEEK_BASE_URL = "https://api.deepseek.com/v1"
OLLAMA_BASE_URL = "http://localhost:11434"

# DeployTier → 实际LLM端点映射
# NexusFlow中: EDGE=端侧, FOG=边缘, CLOUD=云端
TIER_ENDPOINTS = {
    DeployTier.EDGE: {
        "model": "qwen3.5:9b",
        "endpoint": f"{OLLAMA_BASE_URL}/api/chat",
        "type": "ollama",
        "label": "📱 Edge(端侧)",
        "cost_per_1k_tokens": 0.0,
        "privacy": True,
        "description": "端侧: Ollama qwen3.5:9b (6.6GB, 模拟手机/边缘轻量设备)",
    },
    DeployTier.FOG: {
        "model": "deepseek-r1:14b",
        "endpoint": f"{OLLAMA_BASE_URL}/api/chat",
        "type": "ollama",
        "label": "🖥️ Fog(边缘)",
        "cost_per_1k_tokens": 0.0,
        "privacy": True,
        "description": "边缘: Ollama deepseek-r1:14b (9GB, 模拟边缘网关)",
    },
    DeployTier.CLOUD: {
        "model": "deepseek-chat",
        "endpoint": f"{DEEPSEEK_BASE_URL}/chat/completions",
        "type": "openai",
        "label": "☁️ Cloud(云端)",
        "cost_per_1k_tokens": 0.001,
        "privacy": False,
        "description": "云端: DeepSeek API (真实云服务)",
    },
}


# ═══════════════════════════════════════════════════
# 注册真实三层资源到 EdgeCloudScheduler
# ═══════════════════════════════════════════════════

def create_scheduler_with_real_resources(policy=SchedulingPolicy.BALANCED):
    """
    创建 EdgeCloudScheduler 实例，注册真实端点资源

    使用项目实际的 TierResource 类和 EdgeCloudScheduler.register_tier() 方法。
    资源参数取自真实硬件/API规格。
    """
    scheduler = EdgeCloudScheduler(policy=policy)

    # Edge层（端侧）：qwen3.5:9b，模拟手机/边缘轻量设备
    scheduler.register_tier(TierResource(
        tier=DeployTier.EDGE,
        name="terminal-qwen3.5-9b",
        endpoint=f"{OLLAMA_BASE_URL}/api/chat",
        cpu_cores=8,
        gpu_count=0,
        gpu_memory_gb=0.0,
        ram_gb=16.0,
        storage_gb=512.0,
        available=True,
        load_factor=0.2,
        latency_to_user_ms=5.0,
        supported_models=["qwen3.5:9b"],
        max_context_window=8192,
        cost_per_token=0.0,
    ))

    # Fog层（边缘）：deepseek-r1:14b，模拟边缘网关/本地PC
    scheduler.register_tier(TierResource(
        tier=DeployTier.FOG,
        name="edge-deepseek-r1-14b",
        endpoint=f"{OLLAMA_BASE_URL}/api/chat",
        cpu_cores=16,
        gpu_count=1,
        gpu_memory_gb=16.0,
        ram_gb=32.0,
        storage_gb=2048.0,
        available=True,
        load_factor=0.3,
        latency_to_user_ms=15.0,
        supported_models=["deepseek-r1:14b"],
        max_context_window=32768,
        cost_per_token=0.0,
    ))

    # Cloud层（云端）：DeepSeek API
    scheduler.register_tier(TierResource(
        tier=DeployTier.CLOUD,
        name="cloud-deepseek-api",
        endpoint=f"{DEEPSEEK_BASE_URL}/chat/completions",
        cpu_cores=0,
        gpu_count=0,
        ram_gb=0.0,
        storage_gb=0.0,
        available=True,
        load_factor=0.5,
        latency_to_user_ms=150.0,
        supported_models=["deepseek-chat"],
        max_context_window=65536,
        cost_per_token=0.000001,  # ¥0.001/1K tokens = ¥0.000001/token
    ))

    return scheduler


# ═══════════════════════════════════════════════════
# LLM 执行器
# ═══════════════════════════════════════════════════

def strip_think_tags(content):
    """提取 deepseek-r1 等模型 </think> 之后的实际回答"""
    if not content:
        return content
    if "</think>" in content:
        parts = content.split("</think>", 1)
        answer = parts[1].strip()
        return answer if answer else content
    return content


def call_ollama(endpoint, model, messages, max_tokens=200):
    """调用 Ollama API — qwen3.5系列使用think=false关闭思考模式"""
    msgs = [m.copy() for m in messages]
    payload = {
        "model": model,
        "messages": msgs,
        "stream": False,
        "options": {"num_predict": max_tokens, "temperature": 0.7},
    }
    if "qwen3.5" in model:
        payload["think"] = False
    resp = requests.post(endpoint, json=payload, timeout=300)
    resp.raise_for_status()
    data = resp.json()
    content = data.get("message", {}).get("content", "")
    content = strip_think_tags(content)
    prompt_tokens = data.get("prompt_eval_count", 0)
    completion_tokens = data.get("eval_count", 0)
    return {
        "content": content,
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "total_tokens": prompt_tokens + completion_tokens,
    }


def call_deepseek(endpoint, api_key, model, messages, max_tokens=200):
    """调用 DeepSeek API"""
    payload = {
        "model": model,
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": 0.7,
    }
    resp = requests.post(
        endpoint,
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        json=payload,
        timeout=60,
    )
    resp.raise_for_status()
    data = resp.json()
    content = data["choices"][0]["message"]["content"]
    usage = data.get("usage", {})
    return {
        "content": content,
        "prompt_tokens": usage.get("prompt_tokens", 0),
        "completion_tokens": usage.get("completion_tokens", 0),
        "total_tokens": usage.get("total_tokens", 0),
    }


def execute_on_tier(tier: DeployTier, messages, max_tokens=200):
    """
    根据调度器决策的 DeployTier，在对应层执行真实LLM推理

    Args:
        tier: EdgeCloudScheduler 调度决策返回的 DeployTier
        messages: LLM消息列表
        max_tokens: 最大生成token数
    """
    ep = TIER_ENDPOINTS[tier]
    t0 = time.time()

    try:
        if ep["type"] == "ollama":
            result = call_ollama(ep["endpoint"], ep["model"], messages, max_tokens)
        else:
            result = call_deepseek(ep["endpoint"], DEEPSEEK_API_KEY, ep["model"], messages, max_tokens)

        latency = (time.time() - t0) * 1000
        result["latency_ms"] = round(latency, 1)
        result["tier"] = tier.value
        result["success"] = True
        result["error"] = None
        result["cost"] = round(result["total_tokens"] / 1000 * ep["cost_per_1k_tokens"], 6)
        result["model"] = ep["model"]
        return result

    except Exception as e:
        latency = (time.time() - t0) * 1000
        return {
            "content": "", "prompt_tokens": 0, "completion_tokens": 0,
            "total_tokens": 0, "latency_ms": round(latency, 1),
            "tier": tier.value, "success": False, "error": str(e)[:200],
            "cost": 0.0, "model": ep["model"],
        }


# ═══════════════════════════════════════════════════
# 质量评估
# ═══════════════════════════════════════════════════

def evaluate_response(content, expected_keywords):
    if not content:
        return 0.0, 0, 0
    content_lower = content.lower()
    hits = sum(1 for kw in expected_keywords if kw.lower() in content_lower)
    keyword_score = hits / len(expected_keywords) if expected_keywords else 1.0
    length = len(content)
    if length < 20:
        length_score = 0.3
    elif length > 2000:
        length_score = 0.7
    else:
        length_score = 1.0
    quality = keyword_score * 0.7 + length_score * 0.3
    return round(quality, 3), hits, length


# ═══════════════════════════════════════════════════
# 实验任务定义
# ═══════════════════════════════════════════════════

def define_tasks():
    return [
        {
            "task_id": "T01_privacy_health",
            "description": "个人健康数据分析（隐私敏感）",
            "prompt": "患者男性45岁，血压145/95，空腹血糖7.2mmol/L，BMI 28.5。请简要分析健康风险并给出3条建议。",
            "requirements": {"privacy_level": 2, "needs_gpu": False, "context_window": 4096, "latency_budget_ms": 30000},
            "max_tokens": 200, "expected_keywords": ["血压", "血糖", "建议"],
        },
        {
            "task_id": "T02_realtime_qa",
            "description": "实时问答（低延迟要求）",
            "prompt": "什么是量子纠缠？用一句话解释。",
            "requirements": {"privacy_level": 0, "needs_gpu": False, "context_window": 1024, "latency_budget_ms": 1500},
            "max_tokens": 100, "expected_keywords": ["量子", "纠缠"],
        },
        {
            "task_id": "T03_code_generation",
            "description": "代码生成（需GPU算力）",
            "prompt": "写一个Python函数，实现二分查找算法，包含类型注解和docstring。",
            "requirements": {"privacy_level": 0, "needs_gpu": True, "min_gpu_memory_gb": 8.0, "context_window": 2048, "latency_budget_ms": 30000},
            "max_tokens": 300, "expected_keywords": ["def", "binary", "search"],
        },
        {
            "task_id": "T04_long_analysis",
            "description": "长文档分析（大上下文需求）",
            "prompt": "请分析以下文本的主题、情感和关键信息：人工智能正在重塑软件开发流程。从需求分析到代码生成，从测试到部署，AI工具已经渗透到软件工程的每个环节。然而，这也带来了新的挑战：代码质量把控、AI幻觉风险、开发者技能退化等问题日益突出。企业需要在效率提升和质量保障之间找到平衡点。请给出主题、情感倾向和3个关键信息点。",
            "requirements": {"privacy_level": 0, "needs_gpu": False, "context_window": 40960, "latency_budget_ms": 30000},
            "max_tokens": 250, "expected_keywords": ["主题", "情感", "关键"],
        },
        {
            "task_id": "T05_privacy_finance",
            "description": "个人财务数据分析（隐私+低延迟）",
            "prompt": "月收入15000元，房租3500元，餐饮2000元，交通800元，其他支出2000元。计算储蓄额和储蓄率，给出优化建议。",
            "requirements": {"privacy_level": 2, "needs_gpu": False, "context_window": 2048, "latency_budget_ms": 10000},
            "max_tokens": 200, "expected_keywords": ["储蓄", "建议"],
        },
        {
            "task_id": "T06_general_summary",
            "description": "通用文本摘要（无特殊约束）",
            "prompt": "请将以下文本摘要为50字以内：人工智能技术近年来快速发展，大语言模型在自然语言处理领域取得了突破性进展。这些模型能够理解和生成人类语言，在对话、写作、编程等多个领域展现出强大能力。然而，模型规模的增长也带来了计算成本和能源消耗的挑战。",
            "requirements": {"privacy_level": 0, "needs_gpu": False, "context_window": 2048, "latency_budget_ms": 30000},
            "max_tokens": 100, "expected_keywords": ["人工智能", "大语言"],
        },
        {
            "task_id": "T07_complex_reasoning",
            "description": "复杂推理任务（高算力需求）",
            "prompt": "一个农场有鸡和兔子共35只，总腿数94。请用方程求解鸡和兔子各多少只，并解释推理过程。",
            "requirements": {"privacy_level": 0, "needs_gpu": True, "min_gpu_memory_gb": 8.0, "context_window": 2048, "latency_budget_ms": 30000},
            "max_tokens": 250, "expected_keywords": ["鸡", "兔", "方程"],
        },
        {
            "task_id": "T08_offline_classify",
            "description": "离线文本分类（端侧执行）",
            "prompt": "将以下文本分类为[科技/体育/财经/娱乐]之一：苹果公司发布最新财报，营收同比增长15%，iPhone销量创下新高，服务业务收入也大幅增长。",
            "requirements": {"privacy_level": 1, "needs_gpu": False, "context_window": 1024, "latency_budget_ms": 15000},
            "max_tokens": 50, "expected_keywords": ["财经"],
        },
    ]


# ═══════════════════════════════════════════════════
# 实验主流程
# ═══════════════════════════════════════════════════

def run_experiment():
    print("=" * 70)
    print("  NexusFlow 端-边-云三层调度实机验证")
    print("  使用项目真实 EdgeCloudScheduler（非简化版）")
    print("=" * 70)
    print()

    experiment_start = time.time()
    all_results = {}

    # ─── Phase 1: 创建调度器并注册真实资源 ───
    print("[Phase 1] 创建 EdgeCloudScheduler 并注册真实三层资源")
    print("-" * 50)
    scheduler = create_scheduler_with_real_resources(policy=SchedulingPolicy.BALANCED)
    resources = scheduler.get_all_resources()
    for tier_name, res_list in resources.items():
        tier_enum = DeployTier(tier_name)
        ep = TIER_ENDPOINTS[tier_enum]
        print(f"  {ep['label']} | {res_list[0]['name']:25s} | model={ep['model']:20s} | "
              f"cost=¥{ep['cost_per_1k_tokens']:.4f}/1K | privacy={'YES' if ep['privacy'] else 'NO'}")
    print()

    # ─── Phase 2: 逐层连通性验证 ───
    print("[Phase 2] 逐层连通性验证（真实LLM推理）")
    print("-" * 50)
    ping_results = {}
    for tier in DeployTier:
        result = execute_on_tier(tier, [{"role": "user", "content": "Say OK"}], max_tokens=5)
        status = "OK" if result["success"] else f"FAIL: {result['error']}"
        print(f"  {tier.value:8s} | status={status:30s} | latency={result['latency_ms']:8.1f}ms | tokens={result['total_tokens']}")
        ping_results[tier] = result
    print()

    # ─── Phase 3: 端边云混合调度（真实EdgeCloudScheduler决策 + 真实LLM执行）───
    print("[Phase 3] 端边云混合调度（EdgeCloudScheduler.schedule() + 真实LLM执行）")
    print("-" * 50)
    tasks = define_tasks()
    hybrid_results = []

    for task in tasks:
        # Step 1: 根据任务特征选择调度策略（真实编排器的合理用法）
        req = task["requirements"]
        if req.get("privacy_level", 0) >= 2:
            scheduler._policy = SchedulingPolicy.PRIVACY_FIRST
        elif req.get("latency_budget_ms", 30000) < 2000:
            scheduler._policy = SchedulingPolicy.LATENCY_FIRST
        else:
            scheduler._policy = SchedulingPolicy.BALANCED

        # Step 2: 调用项目真实的 EdgeCloudScheduler.schedule() 进行调度决策
        decision: SchedulingDecision = scheduler.schedule(req)
        selected_tier = decision.selected_tier

        # Step 2: 根据调度决策，在对应层执行真实LLM推理
        messages = [{"role": "user", "content": task["prompt"]}]
        effective_max = task["max_tokens"]
        if selected_tier in (DeployTier.EDGE, DeployTier.FOG):
            effective_max = max(task["max_tokens"] * 3, 600)
        exec_result = execute_on_tier(selected_tier, messages, effective_max)

        # Step 3: 质量评估
        quality, kw_hits, resp_len = evaluate_response(exec_result["content"], task["expected_keywords"])

        record = {
            "task_id": task["task_id"],
            "description": task["description"],
            "scheduled_tier": selected_tier.value,
            "selected_resource": decision.selected_resource,
            "schedule_reason": decision.reason,
            "schedule_confidence": decision.confidence,
            "privacy_guaranteed": decision.privacy_guaranteed,
            "model": exec_result["model"],
            "success": exec_result["success"],
            "latency_ms": exec_result["latency_ms"],
            "prompt_tokens": exec_result["prompt_tokens"],
            "completion_tokens": exec_result["completion_tokens"],
            "total_tokens": exec_result["total_tokens"],
            "cost_cny": exec_result["cost"],
            "quality_score": quality,
            "keyword_hits": kw_hits,
            "keyword_total": len(task["expected_keywords"]),
            "response_length": resp_len,
            "response_preview": exec_result["content"][:120],
            "error": exec_result["error"],
        }
        hybrid_results.append(record)

        emoji = {"edge": "📱", "fog": "🖥️", "cloud": "☁️"}.get(selected_tier.value, "?")
        print(f"  {emoji} {task['task_id']:25s} → {selected_tier.value:5s} | "
              f"conf={decision.confidence:.3f} | latency={exec_result['latency_ms']:8.1f}ms | "
              f"tokens={exec_result['total_tokens']:4d} | cost=¥{exec_result['cost']:.4f} | "
              f"quality={quality:.2f} | {'OK' if exec_result['success'] else 'FAIL'}")

    all_results["hybrid"] = hybrid_results
    print()

    # ─── Phase 4: 纯云端模式对比 ───
    print("[Phase 4] 纯云端模式对比（所有任务强制Cloud层）")
    print("-" * 50)
    cloud_only_results = []

    for task in tasks:
        messages = [{"role": "user", "content": task["prompt"]}]
        exec_result = execute_on_tier(DeployTier.CLOUD, messages, task["max_tokens"])
        quality, kw_hits, resp_len = evaluate_response(exec_result["content"], task["expected_keywords"])

        record = {
            "task_id": task["task_id"],
            "description": task["description"],
            "scheduled_tier": "cloud",
            "schedule_reason": "cloud_only_mode",
            "schedule_confidence": 1.0,
            "privacy_guaranteed": False,
            "model": exec_result["model"],
            "success": exec_result["success"],
            "latency_ms": exec_result["latency_ms"],
            "prompt_tokens": exec_result["prompt_tokens"],
            "completion_tokens": exec_result["completion_tokens"],
            "total_tokens": exec_result["total_tokens"],
            "cost_cny": exec_result["cost"],
            "quality_score": quality,
            "keyword_hits": kw_hits,
            "keyword_total": len(task["expected_keywords"]),
            "response_length": resp_len,
            "response_preview": exec_result["content"][:120],
            "error": exec_result["error"],
        }
        cloud_only_results.append(record)

        print(f"  ☁️ {task['task_id']:25s} → cloud | "
              f"latency={exec_result['latency_ms']:8.1f}ms | "
              f"tokens={exec_result['total_tokens']:4d} | cost=¥{exec_result['cost']:.4f} | "
              f"quality={quality:.2f} | {'OK' if exec_result['success'] else 'FAIL'}")

    all_results["cloud_only"] = cloud_only_results
    print()

    # ─── Phase 5: 层间迁移（使用 EdgeCloudScheduler.migrate() + 真实重新执行）───
    print("[Phase 5] 层间迁移实验（scheduler.migrate() + 真实重新执行）")
    print("-" * 50)
    migration_results = []

    # 场景1: Fog算力不足 → 上抛到Cloud
    mig_task = tasks[2]  # T03_code_generation
    messages = [{"role": "user", "content": mig_task["prompt"]}]
    print(f"  场景1: Fog算力不足 → 上抛到Cloud ({mig_task['task_id']})")
    fog_exec = execute_on_tier(DeployTier.FOG, messages, max(mig_task["max_tokens"] * 3, 600))
    q_fog, _, _ = evaluate_response(fog_exec["content"], mig_task["expected_keywords"])
    print(f"    Fog执行: latency={fog_exec['latency_ms']:.0f}ms, quality={q_fog:.2f}")
    # 调用真实 migrate()
    mig_ok = scheduler.migrate(mig_task["task_id"], DeployTier.FOG, DeployTier.CLOUD,
                               "Fog层推理质量不足，迁移到Cloud获取高质量输出")
    cloud_exec = execute_on_tier(DeployTier.CLOUD, messages, mig_task["max_tokens"])
    q_cloud, _, _ = evaluate_response(cloud_exec["content"], mig_task["expected_keywords"])
    print(f"    Cloud执行: latency={cloud_exec['latency_ms']:.0f}ms, quality={q_cloud:.2f} | migrate={mig_ok}")

    migration_results.append({
        "scenario": "算力不足上抛 Fog→Cloud",
        "task_id": mig_task["task_id"],
        "from_tier": "fog", "to_tier": "cloud",
        "from_latency": fog_exec["latency_ms"], "to_latency": cloud_exec["latency_ms"],
        "from_quality": q_fog, "to_quality": q_cloud,
        "from_tokens": fog_exec["total_tokens"], "to_tokens": cloud_exec["total_tokens"],
        "migrate_success": mig_ok,
        "reason": "Fog层推理质量不足，迁移到Cloud",
    })

    # 场景2: Cloud隐私违规 → 下推到Edge
    mig_task2 = tasks[0]  # T01_privacy_health
    messages2 = [{"role": "user", "content": mig_task2["prompt"]}]
    print(f"  场景2: Cloud隐私违规 → 下推到Edge ({mig_task2['task_id']})")
    cloud_exec2 = execute_on_tier(DeployTier.CLOUD, messages2, mig_task2["max_tokens"])
    q_c2, _, _ = evaluate_response(cloud_exec2["content"], mig_task2["expected_keywords"])
    print(f"    Cloud执行: latency={cloud_exec2['latency_ms']:.0f}ms, quality={q_c2:.2f}, privacy=VIOLATED")
    mig_ok2 = scheduler.migrate(mig_task2["task_id"], DeployTier.CLOUD, DeployTier.EDGE,
                                "检测到敏感健康数据，从Cloud强制迁移到Edge保障隐私")
    edge_exec = execute_on_tier(DeployTier.EDGE, messages2, max(mig_task2["max_tokens"] * 3, 600))
    q_e, _, _ = evaluate_response(edge_exec["content"], mig_task2["expected_keywords"])
    print(f"    Edge执行: latency={edge_exec['latency_ms']:.0f}ms, quality={q_e:.2f}, privacy=GUARANTEED | migrate={mig_ok2}")

    migration_results.append({
        "scenario": "隐私触发下推 Cloud→Edge",
        "task_id": mig_task2["task_id"],
        "from_tier": "cloud", "to_tier": "edge",
        "from_latency": cloud_exec2["latency_ms"], "to_latency": edge_exec["latency_ms"],
        "from_quality": q_c2, "to_quality": q_e,
        "from_tokens": cloud_exec2["total_tokens"], "to_tokens": edge_exec["total_tokens"],
        "migrate_success": mig_ok2,
        "reason": "检测到敏感健康数据，从Cloud强制迁移到Edge保障隐私",
    })

    all_results["migrations"] = migration_results
    print()

    # ─── Phase 6: 容错Fallback（使用 update_resource_state() + 真实重新调度执行）───
    print("[Phase 6] 容错Fallback实验（update_resource_state() + 真实重新调度执行）")
    print("-" * 50)
    fault_results = []

    # 场景1: Edge不可用 → 隐私任务重新调度
    ft_task = tasks[0]  # T01_privacy_health
    messages_ft = [{"role": "user", "content": ft_task["prompt"]}]
    print(f"  场景1: Edge不可用 → 隐私任务重新调度 ({ft_task['task_id']})")
    scheduler.update_resource_state(DeployTier.EDGE, "terminal-qwen3.5-9b", available=False)
    ft_decision = scheduler.schedule(ft_task["requirements"])
    ft_exec = execute_on_tier(ft_decision.selected_tier, messages_ft, max(ft_task["max_tokens"] * 3, 600))
    q_ft, _, _ = evaluate_response(ft_exec["content"], ft_task["expected_keywords"])
    print(f"    重新调度→{ft_decision.selected_tier.value}: latency={ft_exec['latency_ms']:.0f}ms, quality={q_ft:.2f}, privacy={ft_decision.privacy_guaranteed}")
    scheduler.update_resource_state(DeployTier.EDGE, "terminal-qwen3.5-9b", available=True)
    fault_results.append({
        "scenario": "Edge不可用→重新调度",
        "task_id": ft_task["task_id"],
        "fallback_tier": ft_decision.selected_tier.value,
        "latency_ms": ft_exec["latency_ms"], "quality": q_ft,
        "success": ft_exec["success"], "privacy": ft_decision.privacy_guaranteed,
    })

    # 场景2: Cloud不可用 → 大上下文任务重新调度
    ft_task2 = tasks[3]  # T04_long_analysis
    messages_ft2 = [{"role": "user", "content": ft_task2["prompt"]}]
    print(f"  场景2: Cloud不可用 → 大上下文任务重新调度 ({ft_task2['task_id']})")
    scheduler.update_resource_state(DeployTier.CLOUD, "cloud-deepseek-api", available=False)
    ft_decision2 = scheduler.schedule(ft_task2["requirements"])
    ft_exec2 = execute_on_tier(ft_decision2.selected_tier, messages_ft2, max(ft_task2["max_tokens"] * 3, 600))
    q_ft2, _, _ = evaluate_response(ft_exec2["content"], ft_task2["expected_keywords"])
    print(f"    重新调度→{ft_decision2.selected_tier.value}: latency={ft_exec2['latency_ms']:.0f}ms, quality={q_ft2:.2f}")
    scheduler.update_resource_state(DeployTier.CLOUD, "cloud-deepseek-api", available=True)
    fault_results.append({
        "scenario": "Cloud不可用→重新调度",
        "task_id": ft_task2["task_id"],
        "fallback_tier": ft_decision2.selected_tier.value,
        "latency_ms": ft_exec2["latency_ms"], "quality": q_ft2,
        "success": ft_exec2["success"], "privacy": ft_decision2.privacy_guaranteed,
    })

    # 场景3: Fog不可用 → GPU任务重新调度
    ft_task3 = tasks[2]  # T03_code_generation
    messages_ft3 = [{"role": "user", "content": ft_task3["prompt"]}]
    print(f"  场景3: Fog不可用 → GPU任务重新调度 ({ft_task3['task_id']})")
    scheduler.update_resource_state(DeployTier.FOG, "edge-deepseek-r1-14b", available=False)
    ft_decision3 = scheduler.schedule(ft_task3["requirements"])
    ft_exec3 = execute_on_tier(ft_decision3.selected_tier, messages_ft3, ft_task3["max_tokens"])
    q_ft3, _, _ = evaluate_response(ft_exec3["content"], ft_task3["expected_keywords"])
    print(f"    重新调度→{ft_decision3.selected_tier.value}: latency={ft_exec3['latency_ms']:.0f}ms, quality={q_ft3:.2f}")
    scheduler.update_resource_state(DeployTier.FOG, "edge-deepseek-r1-14b", available=True)
    fault_results.append({
        "scenario": "Fog不可用→重新调度",
        "task_id": ft_task3["task_id"],
        "fallback_tier": ft_decision3.selected_tier.value,
        "latency_ms": ft_exec3["latency_ms"], "quality": q_ft3,
        "success": ft_exec3["success"], "privacy": ft_decision3.privacy_guaranteed,
    })

    all_results["fault_tolerance"] = fault_results
    print()

    # ─── Phase 7: 统计汇总 ───
    print("[Phase 7] 统计汇总")
    print("-" * 50)
    experiment_elapsed = time.time() - experiment_start

    h_success = sum(1 for r in hybrid_results if r["success"])
    h_total_latency = sum(r["latency_ms"] for r in hybrid_results)
    h_total_tokens = sum(r["total_tokens"] for r in hybrid_results)
    h_total_cost = sum(r["cost_cny"] for r in hybrid_results)
    h_avg_quality = sum(r["quality_score"] for r in hybrid_results) / len(hybrid_results)
    h_privacy_ok = sum(1 for r in hybrid_results if r["privacy_guaranteed"] and r["success"])

    c_success = sum(1 for r in cloud_only_results if r["success"])
    c_total_latency = sum(r["latency_ms"] for r in cloud_only_results)
    c_total_tokens = sum(r["total_tokens"] for r in cloud_only_results)
    c_total_cost = sum(r["cost_cny"] for r in cloud_only_results)
    c_avg_quality = sum(r["quality_score"] for r in cloud_only_results) / len(cloud_only_results)

    # 调度器统计
    sched_stats = scheduler.get_scheduling_stats()

    print(f"  {'指标':20s} | {'混合调度':>12s} | {'纯云端':>12s} | {'差异':>10s}")
    print(f"  {'-'*65}")
    print(f"  {'成功率':20s} | {h_success}/{len(hybrid_results):<3d}      | {c_success}/{len(cloud_only_results):<3d}      |")
    print(f"  {'总延迟(ms)':20s} | {h_total_latency:>12.0f} | {c_total_latency:>12.0f} | {h_total_latency-c_total_latency:>+10.0f}")
    print(f"  {'总Token':20s} | {h_total_tokens:>12d} | {c_total_tokens:>12d} | {h_total_tokens-c_total_tokens:>+10d}")
    print(f"  {'总成本(¥)':20s} | {h_total_cost:>12.4f} | {c_total_cost:>12.4f} | {h_total_cost-c_total_cost:>+10.4f}")
    print(f"  {'平均质量':20s} | {h_avg_quality:>12.3f} | {c_avg_quality:>12.3f} | {h_avg_quality-c_avg_quality:>+10.3f}")
    print(f"  {'隐私合规任务':20s} | {h_privacy_ok:>12d} | {0:>12d} |")
    print(f"  {'实验耗时(s)':20s} | {experiment_elapsed:>12.1f} |")
    print(f"  {'调度器总决策数':20s} | {sched_stats['total_decisions']:>12d} |")
    print(f"  {'调度器迁移次数':20s} | {sched_stats['total_migrations']:>12d} |")
    print()

    tier_dist = {}
    for r in hybrid_results:
        tier_dist[r["scheduled_tier"]] = tier_dist.get(r["scheduled_tier"], 0) + 1
    print(f"  混合调度层分布: {tier_dist}")
    print()

    # ─── 保存结果 ───
    output = {
        "experiment_time": datetime.now().isoformat(),
        "experiment_elapsed_seconds": round(experiment_elapsed, 1),
        "scheduler_class": "nexusflow.core.edge_cloud_scheduler.EdgeCloudScheduler",
        "scheduler_policy": SchedulingPolicy.BALANCED.value,
        "scheduler_stats": sched_stats,
        "tiers": {k.value: v for k, v in TIER_ENDPOINTS.items()},
        "connectivity": {k.value: {"success": v["success"], "latency_ms": v["latency_ms"], "total_tokens": v["total_tokens"]} for k, v in ping_results.items()},
        "hybrid_mode": hybrid_results,
        "cloud_only_mode": cloud_only_results,
        "migrations": migration_results,
        "fault_tolerance": fault_results,
        "summary": {
            "hybrid": {"success_count": h_success, "total_latency_ms": round(h_total_latency, 1),
                       "total_tokens": h_total_tokens, "total_cost_cny": round(h_total_cost, 6),
                       "avg_quality": round(h_avg_quality, 3), "privacy_compliant": h_privacy_ok, "tier_distribution": tier_dist},
            "cloud_only": {"success_count": c_success, "total_latency_ms": round(c_total_latency, 1),
                           "total_tokens": c_total_tokens, "total_cost_cny": round(c_total_cost, 6),
                           "avg_quality": round(c_avg_quality, 3), "privacy_compliant": 0},
        },
    }

    output_dir = Path(__file__).parent / "edge_cloud_verification"
    output_dir.mkdir(exist_ok=True)
    data_path = output_dir / "real_machine_data.json"
    with open(data_path, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"  数据已保存: {data_path}")
    print()
    print("=" * 70)
    print("  ✅ 端-边-云三层调度实机验证完成！")
    print(f"  使用项目真实 EdgeCloudScheduler（{sched_stats['total_decisions']}次调度决策）")
    print("=" * 70)

    return output


if __name__ == "__main__":
    run_experiment()
