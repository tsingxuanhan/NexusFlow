#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
NexusFlow × 荣耀MagicOS 跨设备AI协同场景Demo
Honor Terminal Scenario: Cross-Device AI Investment Research Assistant

场景：用户对荣耀手机说"帮我分析比亚迪的投资价值，我持有500股成本价210元"
任务被分解为6步长程流程，跨端-边-云三层协同执行：

  Step 1 [📱 Terminal] 意图解析+隐私提取 → 持仓数据不出设备
  Step 2 [☁️ Cloud]    财报数据获取+行业分析 → 大上下文需求
  Step 3 [🖥️ Fog]      深度财务推理 → 14B模型推理能力
  Step 4 [☁️ Cloud]    综合分析+建议生成 → 大上下文整合
  Step 5 [📱 Terminal] 持仓盈亏计算 → 隐私数据端侧处理
  Step 6 [🖥️ Fog]      质量审核 → Reviewer闭环

使用项目真实 EdgeCloudScheduler 进行每步调度决策。
"""

import sys
import os
import json
import time
from datetime import datetime
from pathlib import Path

import requests

# ═══════════════════════════════════════════════════
# 导入 NexusFlow 项目真实调度器
# ═══════════════════════════════════════════════════

project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, project_root)

from nexusflow.core.edge_cloud_scheduler import (
    EdgeCloudScheduler, TierResource, DeployTier, SchedulingPolicy, SchedulingDecision
)

# ═══════════════════════════════════════════════════
# 配置
# ═══════════════════════════════════════════════════

DEEPSEEK_API_KEY = os.environ.get("DEEPSEEK_API_KEY", "")
if not DEEPSEEK_API_KEY:
    print("ERROR: 请设置 DEEPSEEK_API_KEY 环境变量")
    sys.exit(1)

OLLAMA_BASE_URL = "http://localhost:11434"
DEEPSEEK_BASE_URL = "https://api.deepseek.com/v1"

TIER_ENDPOINTS = {
    DeployTier.EDGE: {"model": "qwen3.5:9b", "endpoint": f"{OLLAMA_BASE_URL}/api/chat", "type": "ollama", "label": "📱 Terminal(荣耀手机)"},
    DeployTier.FOG: {"model": "deepseek-r1:14b", "endpoint": f"{OLLAMA_BASE_URL}/api/chat", "type": "ollama", "label": "🖥️ Fog(荣耀平板/PC)"},
    DeployTier.CLOUD: {"model": "deepseek-chat", "endpoint": f"{DEEPSEEK_BASE_URL}/chat/completions", "type": "openai", "label": "☁️ Cloud(荣耀云服务)"},
}


def strip_think_tags(content):
    if not content:
        return content
    if "</think>" in content:
        parts = content.split("</think>", 1)
        answer = parts[1].strip()
        return answer if answer else content
    return content


def call_ollama(endpoint, model, messages, max_tokens=300):
    msgs = [m.copy() for m in messages]
    payload = {"model": model, "messages": msgs, "stream": False,
               "options": {"num_predict": max_tokens, "temperature": 0.7}}
    if "qwen3.5" in model:
        payload["think"] = False
    resp = requests.post(endpoint, json=payload, timeout=300)
    resp.raise_for_status()
    data = resp.json()
    content = strip_think_tags(data.get("message", {}).get("content", ""))
    return {"content": content, "prompt_tokens": data.get("prompt_eval_count", 0),
            "completion_tokens": data.get("eval_count", 0)}


def call_deepseek(endpoint, api_key, model, messages, max_tokens=300):
    resp = requests.post(endpoint, headers={"Authorization": f"Bearer {api_key}",
                        "Content-Type": "application/json"},
                        json={"model": model, "messages": messages, "max_tokens": max_tokens, "temperature": 0.7},
                        timeout=60)
    resp.raise_for_status()
    data = resp.json()
    usage = data.get("usage", {})
    return {"content": data["choices"][0]["message"]["content"],
            "prompt_tokens": usage.get("prompt_tokens", 0),
            "completion_tokens": usage.get("completion_tokens", 0)}


def execute_on_tier(tier, messages, max_tokens=300):
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
        result["model"] = ep["model"]
        result["cost"] = round(result["prompt_tokens"] + result["completion_tokens"] / 1000 * 0.001, 6) if tier == DeployTier.CLOUD else 0.0
        return result
    except Exception as e:
        return {"content": "", "prompt_tokens": 0, "completion_tokens": 0,
                "latency_ms": round((time.time() - t0) * 1000, 1), "tier": tier.value,
                "success": False, "error": str(e)[:200], "model": ep["model"], "cost": 0.0}


def create_scheduler():
    """创建 EdgeCloudScheduler 并注册荣耀生态三层资源"""
    scheduler = EdgeCloudScheduler(policy=SchedulingPolicy.BALANCED)

    # 📱 Terminal: 荣耀手机 (MagicOS AI助手)
    scheduler.register_tier(TierResource(
        tier=DeployTier.EDGE, name="honor-phone-magicos",
        endpoint=f"{OLLAMA_BASE_URL}/api/chat",
        cpu_cores=8, gpu_count=0, gpu_memory_gb=0.0, ram_gb=12.0,
        available=True, load_factor=0.2, latency_to_user_ms=5.0,
        supported_models=["qwen3.5:9b"], max_context_window=8192, cost_per_token=0.0,
    ))

    # 🖥️ Fog: 荣耀平板/PC (YOYO助手)
    scheduler.register_tier(TierResource(
        tier=DeployTier.FOG, name="honor-tablet-yoyo",
        endpoint=f"{OLLAMA_BASE_URL}/api/chat",
        cpu_cores=16, gpu_count=1, gpu_memory_gb=16.0, ram_gb=32.0,
        available=True, load_factor=0.3, latency_to_user_ms=15.0,
        supported_models=["deepseek-r1:14b"], max_context_window=32768, cost_per_token=0.0,
    ))

    # ☁️ Cloud: 荣耀云服务
    scheduler.register_tier(TierResource(
        tier=DeployTier.CLOUD, name="honor-cloud-service",
        endpoint=f"{DEEPSEEK_BASE_URL}/chat/completions",
        available=True, load_factor=0.5, latency_to_user_ms=150.0,
        supported_models=["deepseek-chat"], max_context_window=65536, cost_per_token=0.000001,
    ))

    return scheduler


# ═══════════════════════════════════════════════════
# 6步长程任务定义
# ═══════════════════════════════════════════════════

def define_workflow():
    """定义荣耀MagicOS跨设备投研任务的6步工作流"""
    return [
        {
            "step": 1,
            "name": "意图解析与隐私提取",
            "description": "解析用户投资分析意图，提取持仓隐私数据（500股，成本价210元）",
            "prompt": "用户说：'帮我分析比亚迪的投资价值，我持有500股成本价210元，结合最新财报给个建议'。"
                    "请提取以下信息并输出JSON格式：{intent, stock_name, shares, cost_price, needs_financial_data, needs_industry_analysis}。"
                    "注意：持仓数据属于用户隐私，不可外传。",
            "requirements": {"privacy_level": 2, "needs_gpu": False, "context_window": 2048, "latency_budget_ms": 30000},
            "policy": SchedulingPolicy.PRIVACY_FIRST,
            "max_tokens": 200,
            "device": "荣耀手机 (MagicOS AI助手)",
        },
        {
            "step": 2,
            "name": "财报数据获取与行业分析",
            "description": "获取比亚迪最新财报摘要和新能源汽车行业趋势分析",
            "prompt": "作为投研分析师，请分析比亚迪（002594.SZ）的投资价值。包括：\n"
                    "1. 2024年营收和利润增长情况\n"
                    "2. 新能源汽车市场份额和竞争格局\n"
                    "3. 动力电池和储能业务前景\n"
                    "4. 主要风险因素\n"
                    "请给出结构化分析。",
            "requirements": {"privacy_level": 0, "needs_gpu": False, "context_window": 40960, "latency_budget_ms": 30000},
            "policy": SchedulingPolicy.BALANCED,
            "max_tokens": 400,
            "device": "荣耀云服务",
        },
        {
            "step": 3,
            "name": "深度财务推理",
            "description": "基于财报数据进行估值分析和投资逻辑推理",
            "prompt": "基于以下比亚迪分析要点，进行深度财务推理：\n"
                    "1. 营收增速约30%，净利润增速约40%\n"
                    "2. 全球新能源汽车销量第一，市场份额约20%\n"
                    "3. 动力电池产能持续扩张，储能业务高增长\n"
                    "4. 估值PE约20倍，处于历史低位\n\n"
                    "请推理：当前估值是否合理？给出买入/持有/卖出建议及理由。",
            "requirements": {"privacy_level": 0, "needs_gpu": True, "min_gpu_memory_gb": 8.0, "context_window": 8192, "latency_budget_ms": 30000},
            "policy": SchedulingPolicy.BALANCED,
            "max_tokens": 300,
            "device": "荣耀平板/PC (YOYO助手)",
        },
        {
            "step": 4,
            "name": "综合分析与建议生成",
            "description": "整合行业分析+财务推理，生成完整投资建议报告",
            "prompt": "请综合以下信息，生成比亚迪投资建议报告：\n"
                    "行业分析：全球新能源汽车龙头，市场份额20%，营收增速30%，利润增速40%\n"
                    "财务推理：PE约20倍处于历史低位，估值合理偏低，建议买入\n"
                    "风险提示：行业竞争加剧、原材料价格波动、政策变化\n\n"
                    "请生成一份结构化的投资建议报告，包含：投资评级、目标价、核心逻辑、风险提示。",
            "requirements": {"privacy_level": 0, "needs_gpu": False, "context_window": 40960, "latency_budget_ms": 30000},
            "policy": SchedulingPolicy.BALANCED,
            "max_tokens": 400,
            "device": "荣耀云服务",
        },
        {
            "step": 5,
            "name": "持仓盈亏计算",
            "description": "结合用户持仓数据（500股，成本210元）计算潜在盈亏，隐私数据端侧处理",
            "prompt": "用户持有比亚迪500股，成本价210元。当前股价约250元。\n"
                    "请计算：1. 当前持仓市值 2. 浮动盈亏 3. 盈亏比例 4. 基于投资建议的操作建议。\n"
                    "注意：这是用户的隐私持仓数据，仅在端侧处理。",
            "requirements": {"privacy_level": 2, "needs_gpu": False, "context_window": 2048, "latency_budget_ms": 15000},
            "policy": SchedulingPolicy.PRIVACY_FIRST,
            "max_tokens": 200,
            "device": "荣耀手机 (MagicOS AI助手)",
        },
        {
            "step": 6,
            "name": "质量审核",
            "description": "Reviewer审核投资建议的合理性和完整性",
            "prompt": "请审核以下投资建议的质量和合理性：\n"
                    "建议：买入比亚迪，目标价280元。核心逻辑：全球新能源龙头，PE 20倍历史低位，营收利润高增长。\n"
                    "持仓分析：500股成本210元，当前250元，浮盈20000元（+19%）。\n\n"
                    "请从以下维度审核：1. 逻辑是否自洽 2. 数据是否有矛盾 3. 风险提示是否充分 4. 建议是否合理。"
                    "给出审核结论：通过/需修改/拒绝。",
            "requirements": {"privacy_level": 0, "needs_gpu": True, "min_gpu_memory_gb": 8.0, "context_window": 8192, "latency_budget_ms": 30000},
            "policy": SchedulingPolicy.BALANCED,
            "max_tokens": 250,
            "device": "荣耀平板/PC (YOYO助手)",
        },
    ]


# ═══════════════════════════════════════════════════
# 主流程
# ═══════════════════════════════════════════════════

def run_demo():
    print("=" * 70)
    print("  NexusFlow × 荣耀MagicOS 跨设备AI协同场景Demo")
    print("  场景：用户对荣耀手机说'帮我分析比亚迪的投资价值'")
    print("=" * 70)
    print()

    scheduler = create_scheduler()
    workflow = define_workflow()
    start_time = time.time()
    results = []
    context = {}  # 跨步骤共享的上下文

    print(f"用户输入：'帮我分析比亚迪的投资价值，我持有500股成本价210元'")
    print(f"任务分解：{len(workflow)}步长程流程，跨端-边-云三层协同")
    print()

    for step_def in workflow:
        step_num = step_def["step"]
        step_name = step_def["name"]
        device = step_def["device"]

        print(f"┌─ Step {step_num}: {step_name}")
        print(f"│  目标设备: {device}")
        print(f"│  描述: {step_def['description']}")

        # 调度器决策
        scheduler._policy = step_def["policy"]
        decision = scheduler.schedule(step_def["requirements"])
        tier = decision.selected_tier
        tier_label = TIER_ENDPOINTS[tier]["label"]

        print(f"│  调度决策: {tier_label} | 置信度={decision.confidence:.3f}")
        print(f"│  调度原因: {decision.reason}")
        if decision.privacy_guaranteed:
            print(f"│  🔒 隐私保障: 数据不出设备")

        # 执行LLM推理
        messages = [{"role": "user", "content": step_def["prompt"]}]
        max_tokens = step_def["max_tokens"]
        if tier in (DeployTier.EDGE, DeployTier.FOG):
            max_tokens = max(max_tokens * 3, 600)

        exec_result = execute_on_tier(tier, messages, max_tokens)

        # 记录结果
        record = {
            "step": step_num,
            "name": step_name,
            "device": device,
            "scheduled_tier": tier.value,
            "selected_resource": decision.selected_resource,
            "confidence": decision.confidence,
            "privacy_guaranteed": decision.privacy_guaranteed,
            "reason": decision.reason,
            "model": exec_result["model"],
            "success": exec_result["success"],
            "latency_ms": exec_result["latency_ms"],
            "prompt_tokens": exec_result["prompt_tokens"],
            "completion_tokens": exec_result["completion_tokens"],
            "total_tokens": exec_result["prompt_tokens"] + exec_result["completion_tokens"],
            "response": exec_result["content"],
            "response_preview": exec_result["content"][:200],
            "error": exec_result.get("error"),
        }
        results.append(record)

        # 保存上下文供后续步骤使用
        context[f"step_{step_num}_result"] = exec_result["content"][:500]

        print(f"│  执行结果: {'OK' if exec_result['success'] else 'FAIL'} | "
              f"延迟={exec_result['latency_ms']:.0f}ms | "
              f"tokens={record['total_tokens']}")
        print(f"│  响应预览: {exec_result['content'][:120].replace(chr(10), ' ')}...")
        print(f"└{'─' * 68}")
        print()

    elapsed = time.time() - start_time

    # ─── 统计汇总 ───
    print("=" * 70)
    print("  场景执行统计")
    print("=" * 70)

    total_latency = sum(r["latency_ms"] for r in results)
    total_tokens = sum(r["total_tokens"] for r in results)
    success_count = sum(1 for r in results if r["success"])
    privacy_steps = sum(1 for r in results if r["privacy_guaranteed"])

    tier_dist = {}
    for r in results:
        tier_dist[r["scheduled_tier"]] = tier_dist.get(r["scheduled_tier"], 0) + 1

    print(f"  总步骤数: {len(results)}")
    print(f"  成功步骤: {success_count}/{len(results)}")
    print(f"  总延迟: {total_latency:.0f}ms ({total_latency/1000:.1f}s)")
    print(f"  总Token: {total_tokens}")
    print(f"  隐私保障步骤: {privacy_steps}/{len(results)}")
    print(f"  层分布: {tier_dist}")
    print(f"  实验耗时: {elapsed:.1f}s")
    print()

    # ─── 任务执行轨迹 ───
    print("  任务执行轨迹（端-边-云协同）:")
    print()
    for r in results:
        emoji = {"edge": "📱", "fog": "🖥️", "cloud": "☁️"}.get(r["scheduled_tier"], "?")
        priv = " 🔒" if r["privacy_guaranteed"] else ""
        print(f"    Step {r['step']}: {emoji} {r['scheduled_tier']:5s} | {r['name']:20s} | "
              f"{r['latency_ms']:6.0f}ms | {r['total_tokens']:4d} tokens{priv}")
    print()

    # ─── 保存数据 ───
    output = {
        "scenario": "荣耀MagicOS跨设备AI投研助手",
        "user_input": "帮我分析比亚迪的投资价值，我持有500股成本价210元",
        "experiment_time": datetime.now().isoformat(),
        "elapsed_seconds": round(elapsed, 1),
        "scheduler": "nexusflow.core.edge_cloud_scheduler.EdgeCloudScheduler",
        "steps": results,
        "summary": {
            "total_steps": len(results),
            "success_count": success_count,
            "total_latency_ms": round(total_latency, 1),
            "total_tokens": total_tokens,
            "privacy_steps": privacy_steps,
            "tier_distribution": tier_dist,
        },
    }

    output_dir = Path(__file__).parent / "honor_scenario"
    output_dir.mkdir(exist_ok=True)
    data_path = output_dir / "honor_magicos_demo_data.json"
    with open(data_path, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"  数据已保存: {data_path}")
    print()
    print("=" * 70)
    print("  ✅ 荣耀MagicOS跨设备AI协同场景Demo完成！")
    print("=" * 70)

    return output


if __name__ == "__main__":
    run_demo()
