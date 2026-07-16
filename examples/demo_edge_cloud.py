#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
NexusFlow 端-边-云调度 Demo
实际运行 EdgeCloudScheduler，展示 5 种调度策略 + 层间迁移
"""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from nexusflow.core.edge_cloud_scheduler import (
    EdgeCloudScheduler, TierResource, DeployTier, SchedulingPolicy, SchedulingDecision
)

# ── 颜色 ──
C = {"edge":"\033[96m","fog":"\033[93m","cloud":"\033[95m",
     "ok":"\033[92m","warn":"\033[91m","bold":"\033[1m","reset":"\033[0m"}

def tier_color(t): return C.get(t.value, "")

def banner(title):
    print(f"\n{'='*70}")
    print(f"  {C['bold']}{title}{C['reset']}")
    print(f"{'='*70}")

def print_decision(label: str, d: SchedulingDecision):
    tc = tier_color(d.selected_tier)
    priv = "🔒 隐私保障" if d.privacy_guaranteed else "  "
    print(f"  {C['bold']}{label}{C['reset']}")
    print(f"    → {tc}{d.selected_tier.value.upper():5s}{C['reset']} | "
          f"资源: {d.selected_resource:20s} | "
          f"延迟: {d.estimated_latency_ms:6.1f}ms | "
          f"置信: {d.confidence:.2f} | {priv}")
    print(f"    原因: {d.reason}")
    if d.fallback_tier:
        print(f"    备选: {tier_color(d.fallback_tier)}{d.fallback_tier.value}{C['reset']}")

# ═══════════════════════════════════════════
# 1. 初始化三层资源池
# ═══════════════════════════════════════════
banner("🏗️  场景 1: 初始化端-边-云三层资源池")

scheduler = EdgeCloudScheduler(policy=SchedulingPolicy.BALANCED)
scheduler.setup_default_tiers(local_gpu=True)

resources = scheduler.get_all_resources()
for tier_name, res_list in resources.items():
    label = {"edge":"📱 Edge(端侧)","fog":"🖥️  Fog(边缘)","cloud":"☁️  Cloud(云端)"}[tier_name]
    print(f"\n  {C['bold']}{label}{C['reset']}")
    for r in res_list:
        models = ", ".join(r["models"][:3])
        print(f"    • {r['name']:20s} | GPU:{r['gpu']} | RAM:{r['ram_gb']:.0f}GB | "
              f"延迟:{r['latency_ms']:.0f}ms | 模型:[{models}...]")

# ═══════════════════════════════════════════
# 2. 均衡策略调度
# ═══════════════════════════════════════════
banner("⚖️  场景 2: 均衡策略 — 不同任务特征自动选层")

tasks = [
    ("简单问答-公开数据",    {"needs_gpu":False, "privacy_level":0, "context_window":2048,  "latency_budget_ms":5000}),
    ("文献分析-中等隐私",    {"needs_gpu":False, "privacy_level":1, "context_window":16384, "latency_budget_ms":10000}),
    ("敏感医疗数据推理",     {"needs_gpu":True,  "privacy_level":2, "context_window":8192,  "latency_budget_ms":30000}),
    ("超大上下文长文档",     {"needs_gpu":False,"privacy_level":0, "context_window":100000,"latency_budget_ms":60000}),
    ("低延迟实时翻译",       {"needs_gpu":False,"privacy_level":0, "context_window":4096,  "latency_budget_ms":100}),
]

for label, req in tasks:
    decision = scheduler.schedule({**req, "task_id": label})
    print_decision(label, decision)
    print()

# ═══════════════════════════════════════════
# 3. 隐私优先策略
# ═══════════════════════════════════════════
banner("🔒  场景 3: 隐私优先策略 — 敏感数据强制端侧处理")

priv_scheduler = EdgeCloudScheduler(policy=SchedulingPolicy.PRIVACY_FIRST)
priv_scheduler.setup_default_tiers(local_gpu=True)

priv_tasks = [
    ("用户密码验证",       {"privacy_level":2, "needs_gpu":False, "context_window":2048}),
    ("企业财报分析(内部)", {"privacy_level":1, "needs_gpu":False, "context_window":32768}),
    ("公开新闻摘要",       {"privacy_level":0, "needs_gpu":False, "context_window":4096}),
]

for label, req in priv_tasks:
    decision = priv_scheduler.schedule({**req, "task_id": label})
    print_decision(label, decision)
    print()

# ═══════════════════════════════════════════
# 4. 成本优先策略
# ═══════════════════════════════════════════
banner("💰  场景 4: 成本优先策略 — 寻找最便宜执行位置")

cost_scheduler = EdgeCloudScheduler(policy=SchedulingPolicy.COST_FIRST)
cost_scheduler.setup_default_tires = cost_scheduler.setup_default_tiers  # typo guard
cost_scheduler.setup_default_tiers(local_gpu=True)

cost_tasks = [
    ("大批量数据处理",     {"needs_gpu":False, "context_window":8192}),
    ("GPU密集推理",        {"needs_gpu":True, "min_gpu_memory_gb":12, "context_window":8192}),
]

for label, req in cost_tasks:
    decision = cost_scheduler.schedule({**req, "task_id": label})
    print_decision(label, decision)
    print()

# ═══════════════════════════════════════════
# 5. 层间迁移
# ═══════════════════════════════════════════
banner("🔄  场景 5: 层间迁移 — Edge处理不了，上抛到Fog/Cloud")

mig_scheduler = EdgeCloudScheduler(policy=SchedulingPolicy.LATENCY_FIRST)
mig_scheduler.setup_default_tiers(local_gpu=True)

# 模拟: 先在Edge启动任务
d1 = mig_scheduler.schedule({"task_id":"migrate-demo","needs_gpu":True,"privacy_level":0,"context_window":4096})
print_decision("Step 1: 初始调度", d1)

# 端侧算力不够 → 迁移到 Fog
ok1 = mig_scheduler.migrate("migrate-demo", DeployTier.EDGE, DeployTier.FOG,
                            reason="Edge GPU memory insufficient for 72B model")
print(f"\n  {'✅' if ok1 else '❌'} Edge → Fog 迁移: {'成功' if ok1 else '失败'}")

# Fog也超载 → 继续迁移到 Cloud
mig_scheduler.update_resource_state(DeployTier.FOG, "campus-server", load_factor=0.95)
ok2 = mig_scheduler.migrate("migrate-demo", DeployTier.FOG, DeployTier.CLOUD,
                            reason="Fog server overloaded (95%), escalate to cloud")
print(f"  {'✅' if ok2 else '❌'} Fog → Cloud 迁移: {'成功' if ok2 else '失败'}")

# ═══════════════════════════════════════════
# 6. 动态负载变化下的调度切换
# ═══════════════════════════════════════════
banner("📊  场景 6: 动态负载 — Edge离线后自动切换到Fog/Cloud")

dyn_scheduler = EdgeCloudScheduler(policy=SchedulingPolicy.BALANCED)
dyn_scheduler.setup_default_tiers(local_gpu=True)

d_before = dyn_scheduler.schedule({"task_id":"dyn-demo","needs_gpu":False,"privacy_level":0,"context_window":4096})
print_decision("Edge在线时", d_before)

dyn_scheduler.update_resource_state(DeployTier.EDGE, "local-device", available=False)
d_after = dyn_scheduler.schedule({"task_id":"dyn-demo-2","needs_gpu":False,"privacy_level":0,"context_window":4096})
print_decision("Edge离线后", d_after)

# ═══════════════════════════════════════════
# 7. 统计汇总
# ═══════════════════════════════════════════
banner("📈  调度统计汇总")

stats = scheduler.get_scheduling_stats()
print(f"\n  策略: {stats['policy']}")
print(f"  总调度次数: {stats['total_decisions']}")
print(f"  层级分布:")
for tier, count in stats['tier_distribution'].items():
    bar = "█" * count
    print(f"    {tier:5s}: {count:2d} {bar}")
print(f"  层间迁移: {len(scheduler._migration_log)} 次")

print(f"\n{'='*70}")
print(f"  {C['ok']}✅ 端-边-云调度 Demo 完成 — 6 场景全部真实执行{C['reset']}")
print(f"{'='*70}\n")
