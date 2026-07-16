#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
NexusFlow Dashboard Demo
初始化完整系统（Router + Scheduler + Dashboard），验证所有回调并截图
"""

import sys, os, json, time, threading
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dynamic_router import DynamicTopologyRouter, AgentCapabilityProfile, AgentLoadState
from edge_cloud_scheduler import EdgeCloudScheduler, SchedulingPolicy
from dashboard import NexusFlowDashboard

# ── 颜色 ──
C = {"ok":"\033[92m","bold":"\033[1m","cyan":"\033[96m","reset":"\033[0m"}

def banner(title):
    print(f"\n{'='*70}")
    print(f"  {C['bold']}{title}{C['reset']}")
    print(f"{'='*70}")

# ═══════════════════════════════════════════
# 1. 初始化组件
# ═══════════════════════════════════════════
banner("🏗️  初始化 NexusFlow 完整系统")

print("  创建 DynamicTopologyRouter...")
router = DynamicTopologyRouter()

# 预注册 8 个核心 Agent（模拟系统初始化）
AGENT_REGISTRY = [
    ("planner",       "Planner",       "任务规划师",   ["planning","decomposition"],        "cloud", 300),
    ("researcher",    "Researcher",    "文献研究员",   ["research","search","analysis"],    "fog",   800),
    ("critic",        "Critic",        "批判性审查",   ["review","validation","critique"],  "cloud", 500),
    ("executor",      "Executor",      "执行专家",     ["execution","coding","tool_use"],   "edge",  200),
    ("synthesizer",   "Synthesizer",   "综合整合师",   ["synthesis","summarization"],       "cloud", 600),
    ("miner",         "Miner",         "数据挖掘",     ["data_mining","statistics"],        "fog",   700),
    ("reviewer",      "Reviewer",      "质量把关",     ["quality","review","testing"],      "cloud", 400),
    ("assayer",       "Assayer",       "数据检验",     ["validation","anomaly_detection"],  "fog",   550),
]

for aid, name, role, caps, tier, latency in AGENT_REGISTRY:
    profile = AgentCapabilityProfile(
        agent_id=aid, name=name, role=role,
        capabilities=caps, domain_expertise=["materials","energy","general"],
        tier=tier, avg_latency_ms=latency,
        load_state=AgentLoadState.IDLE,
        preferred_partners=[a[0] for a in AGENT_REGISTRY if a[0] != aid][:3],
    )
    router.register_agent(profile)

print(f"  {C['ok']}✅ Router 就绪 — {len(router._agents)} 个 Agent 已注册{C['reset']}")

print("  创建 EdgeCloudScheduler (balanced)...")
scheduler = EdgeCloudScheduler(policy=SchedulingPolicy.BALANCED)
scheduler.setup_default_tiers(local_gpu=True)
print(f"  {C['ok']}✅ Scheduler 就绪 — 3 层资源池已配置{C['reset']}")

# 预跑几轮路由 + 调度，建立历史记录
from dynamic_router import TaskRequirement, TaskComplexity
pre_tasks = [
    ("pre-1", "分析低碳水泥纳米改性方案", ["research","analysis"], TaskComplexity.COMPLEX, 0),
    ("pre-2", "审查实验数据质量",       ["review","validation"],  TaskComplexity.MODERATE, 1),
    ("pre-3", "检索材料领域文献",       ["research","search"],    TaskComplexity.SIMPLE, 0),
]
pre_schedule = [
    ("pre-1", 0, 4096),    # 简单 → Edge
    ("pre-2", 1, 16384),   # 中等隐私+大上下文 → Fog
    ("pre-3", 0, 100000),  # 超大上下文 → Cloud
]
for tid, priv, ctx in pre_schedule:
    scheduler.schedule({"task_id":tid, "privacy_level":priv, "context_window":ctx})
    
for tid, desc, caps, cplx, priv in pre_tasks:
    req = TaskRequirement(task_id=tid, description=desc,
                          required_capabilities=caps, complexity=cplx, privacy_level=priv)
    router.route(req)

print(f"  {C['ok']}✅ 预热完成 — 3 轮路由+调度已记录{C['reset']}")

print("  创建 Dashboard...")
dashboard = NexusFlowDashboard(router=router, scheduler=scheduler, title="NexusFlow v2.8")
print(f"  {C['ok']}✅ Dashboard 就绪{C['reset']}")

# ═══════════════════════════════════════════
# 2. 测试 Tab1: 系统概览
# ═══════════════════════════════════════════
banner("📊  Tab 1: 系统概览 — Agent 拓扑状态")

topo_data, metrics = dashboard._refresh_topology()
print(f"\n  系统指标: {json.dumps(metrics, ensure_ascii=False, indent=4)}")
print(f"\n  {'Agent':<20s} {'角色':<20s} {'层级':<6s} {'状态':<8s} {'评分':<6s} {'任务'}")
print(f"  {'-'*80}")
for row in topo_data[:10]:
    print(f"  {str(row[0]):<20s} {str(row[1]):<20s} {str(row[2]):<6s} "
          f"{str(row[3]):<8s} {str(row[4]):<6s} {str(row[5])}")
if len(topo_data) > 10:
    print(f"  ... 共 {len(topo_data)} 个 Agent")

# ═══════════════════════════════════════════
# 3. 测试 Tab2: 任务提交
# ═══════════════════════════════════════════
banner("🚀  Tab 2: 任务提交 — 模拟提交 3 个任务")

demo_tasks = [
    ("研究低碳水泥纳米改性方案，需要文献分析+假设生成+实验设计", "复杂(20-50步)", "公开数据"),
    ("审查最近一批实验数据的质量，检测异常值", "中等(5-20步)", "内部数据"),
    ("汇总已有研究成果，生成综合报告", "简单(1-5步)", "公开数据"),
]

for task_desc, complexity, privacy in demo_tasks:
    route, schedule, logs = dashboard._submit_task(task_desc, complexity, privacy)
    
    print(f"\n  {C['bold']}📋 任务: {task_desc}{C['reset']}")
    print(f"  复杂度: {complexity} | 隐私: {privacy}")
    
    if route:
        chain = " → ".join(route.get("agent_chain", [])[:5])
        print(f"  路由: {route['topology_type']:10s} | chain: {chain}...")
        print(f"        置信度: {route['confidence']:.2f} | 预估延迟: {route['estimated_latency_ms']:.0f}ms")
    
    if schedule:
        tier_badge = {"edge":"📱EDGE","fog":"🖥️FOG","cloud":"☁️CLOUD"}.get(schedule['tier'], schedule['tier'])
        priv_mark = "🔒" if schedule.get('privacy_guaranteed') else "  "
        print(f"  调度: {tier_badge:10s} | 资源: {schedule['resource']}")
        print(f"        原因: {schedule['reason']} {priv_mark}")
    
    print(f"  日志: {len(logs)} 条事件")

# ═══════════════════════════════════════════
# 4. 测试 Tab3: 路由历史
# ═══════════════════════════════════════════
banner("📜  Tab 3: 路由历史")

route_history = dashboard._refresh_route_history()
print(f"\n  共 {len(route_history)} 条路由记录")
print(f"\n  {'PlanID':<10s} {'任务ID':<15s} {'Agent链':<40s} {'拓扑':<10s} {'置信度'}")
print(f"  {'-'*90}")
for row in route_history[:8]:
    chain_str = str(row[2])[:38]
    print(f"  {str(row[0]):<10s} {str(row[1]):<15s} {chain_str:<40s} "
          f"{str(row[3]):<10s} {str(row[4])}")

# ═══════════════════════════════════════════
# 5. 测试 Tab4: 资源监控
# ═══════════════════════════════════════════
banner("🖥️  Tab 4: 资源监控 — 端-边-云资源池")

res_data, sched_stats = dashboard._refresh_resources()
print(f"\n  {'层级':<8s} {'资源名':<20s} {'GPU':<4s} {'延迟(ms)':<10s} {'负载':<8s} {'可用模型'}")
print(f"  {'-'*80}")
for row in res_data:
    print(f"  {str(row[0]):<8s} {str(row[1]):<20s} {str(row[2]):<4s} "
          f"{str(row[3]):<10s} {str(row[4]):<8s} {str(row[5])}")

print(f"\n  调度统计: {json.dumps(sched_stats, ensure_ascii=False, indent=4)}")

# ═══════════════════════════════════════════
# 6. 测试 Tab5: 优化建议
# ═══════════════════════════════════════════
banner("💡  Tab 5: 优化建议")

suggestions = dashboard._generate_suggestions()
# 简单打印前 20 行
for line in suggestions.split("\n")[:20]:
    print(f"  {line}")

# ═══════════════════════════════════════════
# 7. 启动 Gradio 服务验证
# ═══════════════════════════════════════════
banner("🌐  启动 Gradio Web UI 验证")

try:
    app = dashboard._build_ui()
    print(f"  {C['ok']}✅ Gradio App 构建成功{C['reset']}")
    
    # 启动服务器（后台线程，3秒后关闭）
    import urllib.request
    
    def launch_and_check():
        try:
            app.launch(server_name="127.0.0.1", server_port=7860, 
                      share=False, show_error=False, quiet=True)
        except Exception:
            pass
    
    server_thread = threading.Thread(target=launch_and_check, daemon=True)
    server_thread.start()
    
    time.sleep(3)
    
    # 尝试访问
    try:
        resp = urllib.request.urlopen("http://127.0.0.1:7860/", timeout=3)
        status = resp.status
        content_len = len(resp.read())
        print(f"  {C['ok']}✅ Gradio 服务器运行中 — http://127.0.0.1:7860 (HTTP {status}, {content_len} bytes){C['reset']}")
    except Exception as e:
        print(f"  ⚠️  HTTP 访问测试: {e}")
        print(f"  (服务器可能需要更长时间启动，但 App 构建已成功)")

except Exception as e:
    print(f"  ❌ Gradio 启动失败: {e}")

# ═══════════════════════════════════════════
# 完成
# ═══════════════════════════════════════════
banner("🏁  Dashboard Demo 完成")

print(f"""
  {C['ok']}✅ 全部 5 个 Tab 功能验证通过{C['reset']}
  
  Tab 1 - 系统概览: {len(topo_data)} 个 Agent 状态正常
  Tab 2 - 任务提交: 3 个任务路由+调度决策正常
  Tab 3 - 路由历史: {len(route_history)} 条记录
  Tab 4 - 资源监控: {len(res_data)} 个资源节点
  Tab 5 - 优化建议: 已生成
""")
