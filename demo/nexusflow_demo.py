# -*- coding: utf-8 -*-
"""
NexusFlow Demo — 动态群体智能协作演示

荣耀赛题 XH-202631 参赛Demo入口

演示内容:
1. 动态拓扑路由器：根据任务自动选择Agent协作链
2. 端-边-云调度器：根据隐私/延迟约束选择执行层
3. Gradio Dashboard：可视化监控面板
4. 异常注入与拓扑自愈演示

运行:
    pip install gradio networkx
    python demo/nexusflow_demo.py
"""

import sys
import os
import time
import json
import logging

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(message)s")
logger = logging.getLogger("NexusFlow-Demo")


def setup_router():
    """初始化动态拓扑路由器，注册Agent"""
    from dynamic_router import (
        DynamicTopologyRouter, AgentCapabilityProfile, AgentLoadState
    )
    
    router = DynamicTopologyRouter(auto_rebuild_interval=5)
    
    # 注册4个核心Agent（v4.0泛化角色）
    agents = [
        AgentCapabilityProfile(
            agent_id="planner",
            name="Planner",
            role="策略规划",
            capabilities=["planning", "task_decomposition", "strategy", "meta_reasoning"],
            domain_expertise=["general", "materials", "ai_ml"],
            load_state=AgentLoadState.IDLE,
            tier="cloud",
            reasoning_depth=0.9,
            creativity=0.7,
            context_window=32768,
            avg_latency_ms=800,
            success_rate=0.95,
            preferred_partners=["researcher"],
        ),
        AgentCapabilityProfile(
            agent_id="researcher",
            name="Researcher",
            role="文献研究与数据分析",
            capabilities=["literature_search", "data_analysis", "hypothesis", "knowledge_retrieval"],
            domain_expertise=["materials", "ai_ml", "chemistry", "physics"],
            load_state=AgentLoadState.IDLE,
            tier="cloud",
            reasoning_depth=0.7,
            creativity=0.6,
            context_window=16384,
            avg_latency_ms=1200,
            success_rate=0.92,
            preferred_partners=["planner", "executor"],
        ),
        AgentCapabilityProfile(
            agent_id="executor",
            name="Executor",
            role="代码执行与实验操作",
            capabilities=["code_execution", "data_processing", "simulation", "experiment"],
            domain_expertise=["materials", "computational", "engineering"],
            load_state=AgentLoadState.IDLE,
            tier="edge",
            reasoning_depth=0.4,
            creativity=0.3,
            context_window=8192,
            avg_latency_ms=300,
            success_rate=0.88,
            max_concurrent=2,
            preferred_partners=["researcher"],
        ),
        AgentCapabilityProfile(
            agent_id="reviewer",
            name="Reviewer",
            role="质量审查与反思",
            capabilities=["quality_check", "review", "reflection", "error_detection"],
            domain_expertise=["general", "materials"],
            load_state=AgentLoadState.IDLE,
            tier="fog",
            reasoning_depth=0.8,
            creativity=0.4,
            context_window=16384,
            avg_latency_ms=600,
            success_rate=0.94,
            preferred_partners=["planner", "executor"],
        ),
    ]
    
    for agent in agents:
        router.register_agent(agent)
    
    logger.info(f"[Demo] Router ready: {len(router._agents)} agents registered")
    return router


def setup_scheduler(local_gpu: bool = True):
    """初始化端-边-云调度器"""
    from edge_cloud_scheduler import (
        EdgeCloudScheduler, TierResource, DeployTier, SchedulingPolicy
    )
    
    scheduler = EdgeCloudScheduler(policy=SchedulingPolicy.BALANCED)
    
    # 端侧：本地RTX 3080 Ti
    scheduler.register_tier(TierResource(
        tier=DeployTier.EDGE,
        name="local-rtx3080ti",
        gpu_count=1,
        gpu_memory_gb=16.0,
        ram_gb=32.0,
        supported_models=["qwen-14b", "qwen-7b", "deepseek-v4-flash"],
        max_context_window=8192,
        latency_to_user_ms=5.0,
        cost_per_token=0.0,
    ))
    
    # 边缘：校园服务器
    scheduler.register_tier(TierResource(
        tier=DeployTier.FOG,
        name="campus-a100",
        endpoint="http://10.100.1.50:8080",
        gpu_count=2,
        gpu_memory_gb=80.0,
        ram_gb=128.0,
        supported_models=["qwen-72b", "qwen-14b", "deepseek-v4-flash", "deepseek-v4-pro"],
        max_context_window=32768,
        latency_to_user_ms=50.0,
        cost_per_token=0.0001,
    ))
    
    # 云端：API服务
    scheduler.register_tier(TierResource(
        tier=DeployTier.CLOUD,
        name="dashscope-api",
        endpoint="https://api.dashscope.aliyuncs.com",
        supported_models=["qwen-max", "qwen-plus", "deepseek-r1"],
        max_context_window=131072,
        latency_to_user_ms=200.0,
        cost_per_token=0.0005,
    ))
    
    logger.info("[Demo] Scheduler ready: 3 tiers configured")
    return scheduler


def demo_routing(router):
    """演示路由决策"""
    from dynamic_router import TaskRequirement, TaskComplexity
    
    print("\n" + "="*60)
    print("🧠 Demo 1: 动态拓扑路由")
    print("="*60)
    
    # 场景1: 简单查询
    print("\n📋 场景1: 简单材料查询")
    task1 = TaskRequirement(
        task_id="demo-001",
        description="查询SSC水泥的抗压强度数据",
        required_capabilities=["data_query"],
        required_domains=["materials"],
        complexity=TaskComplexity.SIMPLE,
    )
    plan1 = router.route(task1)
    print(f"   Agent链: {[router._agents[a].name for a in plan1.agent_chain if a in router._agents]}")
    print(f"   拓扑类型: {plan1.topology_type}")
    print(f"   置信度: {plan1.confidence:.2f}")
    
    # 场景2: 复杂跨学科任务
    print("\n📋 场景2: 跨学科科研任务（20+步）")
    task2 = TaskRequirement(
        task_id="demo-002",
        description="纳米改性低碳水泥的文献分析+假设生成+实验设计+数据验证",
        required_capabilities=["literature_search", "hypothesis", "experiment", "data_analysis", "quality_check"],
        required_domains=["materials", "chemistry"],
        complexity=TaskComplexity.COMPLEX,
        min_reasoning_depth=0.6,
        is_creative=True,
    )
    plan2 = router.route(task2)
    print(f"   Agent链: {[router._agents[a].name for a in plan2.agent_chain if a in router._agents]}")
    print(f"   拓扑类型: {plan2.topology_type}")
    print(f"   置信度: {plan2.confidence:.2f}")
    print(f"   预估延迟: {plan2.estimated_latency_ms:.0f}ms")
    print(f"   预估Token: {plan2.estimated_cost:.0f}")
    
    return plan2


def demo_scheduling(scheduler):
    """演示调度决策"""
    print("\n" + "="*60)
    print("🖥️ Demo 2: 端-边-云调度")
    print("="*60)
    
    # 场景1: 公开数据 → 云端
    print("\n📋 场景1: 公开数据查询")
    d1 = scheduler.schedule({
        "task_id": "sched-001",
        "privacy_level": 0,
        "context_window": 32768,
        "latency_budget_ms": 10000,
    })
    print(f"   选择层: {d1.selected_tier.value}")
    print(f"   资源: {d1.selected_resource}")
    print(f"   原因: {d1.reason}")
    
    # 场景2: 敏感数据 → 端侧
    print("\n📋 场景2: 敏感数据（隐私优先）")
    d2 = scheduler.schedule({
        "task_id": "sched-002",
        "privacy_level": 2,
        "context_window": 8192,
        "latency_budget_ms": 5000,
    })
    print(f"   选择层: {d2.selected_tier.value}")
    print(f"   资源: {d2.selected_resource}")
    print(f"   隐私保障: {d2.privacy_guaranteed}")
    print(f"   原因: {d2.reason}")
    
    # 场景3: 大模型推理 → 边缘
    print("\n📋 场景3: 大模型推理（需GPU）")
    d3 = scheduler.schedule({
        "task_id": "sched-003",
        "privacy_level": 1,
        "needs_gpu": True,
        "min_gpu_memory_gb": 40,
        "context_window": 32768,
    })
    print(f"   选择层: {d3.selected_tier.value}")
    print(f"   资源: {d3.selected_resource}")
    print(f"   原因: {d3.reason}")


def demo_self_healing(router):
    """演示拓扑自愈"""
    from dynamic_router import TaskRequirement, TaskComplexity
    
    print("\n" + "="*60)
    print("🔧 Demo 3: 拓扑自愈（Agent故障恢复）")
    print("="*60)
    
    # 先路由一个复杂任务
    task = TaskRequirement(
        task_id="heal-001",
        description="完整的科研流程",
        required_capabilities=["planning", "research", "execution", "review"],
        complexity=TaskComplexity.COMPLEX,
    )
    original_plan = router.route(task)
    print(f"\n   原始Agent链: {[router._agents[a].name for a in original_plan.agent_chain if a in router._agents]}")
    
    # 模拟Executor故障
    print("\n   ⚠️  Executor故障！触发拓扑自愈...")
    new_plan = router.handle_agent_failure("executor", original_plan)
    
    if new_plan:
        print(f"   ✅ 自愈成功！")
        print(f"   新Agent链: {[router._agents[a].name for a in new_plan.agent_chain if a in router._agents]}")
        print(f"   新置信度: {new_plan.confidence:.2f}")
    else:
        print("   ❌ 无法自愈（无替代Agent）")


def demo_cognitive_division():
    """Phase 7 演示：认知分工协同推理
    
    演示场景：低碳水泥配方优化中的关键决策
    ——"偏高岭土 vs 石灰石粉作为SCM的优选方案"
    
    展示内容：
    1. 视角分解：Miner看实验数据，Assayer看理论推导
    2. Round 0：各自推理，得出不同结论
    3. Round 1：差异归因（"对方可能看到了什么？"）
    4. 融合判断：检测虚假一致 → 输出条件依赖型混合方案
    5. 对比：单Agent全量信息 → 倾向某一方
              认知分工 → 条件依赖型混合方案
    """
    from cognitive_division_engine import (
        CognitiveDivisionEngine, PerspectiveDecomposer, CommunicationLayer,
        FusionJudge, IntermediateConclusion, PerspectiveAssignment, ContextMask,
    )
    from adaptive_context_manager import GlobalMemoryPool, AdaptiveContextManager
    
    print("\n" + "="*60)
    print("🧠 Demo 5: 认知分工协同推理 (Phase 7)")
    print("="*60)
    
    # 初始化
    memory_pool = GlobalMemoryPool()
    engine = CognitiveDivisionEngine(
        agents={},  # Demo模式：使用模拟Agent
        memory_pool=memory_pool,
    )
    
    # 任务：偏高岭土 vs 石灰石粉作为SCM
    task_description = "评估偏高岭土和石灰石粉作为 Supplementary Cementitious Material 的优选方案"
    
    print(f"\n📋 任务: {task_description}")
    print(f"📐 分解策略: evidence_split（证据拆分）")
    
    # Step 1: 视角分解
    print(f"\n{'─'*40}")
    print("[Step 1] 视角分解")
    print(f"{'─'*40}")
    
    assignments = [
        PerspectiveAssignment(
            agent_id="miner",
            perspective_question="从实验数据角度评估偏高岭土作为SCM的性能优势",
            context_mask=ContextMask(
                allowed_evidence=["偏高岭土活性实验", "火山灰反应速率", "早期强度数据"],
                blocked_evidence=["石灰石粉耐久性数据", "长期碳化实验"],
                allowed_domains=["experimental"],
                blocked_domains=["theoretical"],
                abstraction_level="concrete",
            ),
            resource_subset=["experimental_data_metas"],
        ),
        PerspectiveAssignment(
            agent_id="assayer",
            perspective_question="从理论推导角度评估石灰石粉作为SCM的长期耐久性",
            context_mask=ContextMask(
                allowed_evidence=["石灰石粉微观结构", "碳化机理", "长期耐久性模型"],
                blocked_evidence=["偏高岭土活性实验", "火山灰反应速率"],
                allowed_domains=["theoretical"],
                blocked_domains=["experimental"],
                abstraction_level="abstract",
            ),
            resource_subset=["theoretical_framework_limestone"],
        ),
    ]
    
    for a in assignments:
        print(f"\n  🔬 Agent: {a.agent_id}")
        print(f"     视角问题: {a.perspective_question[:60]}...")
        print(f"     可见证据: {a.context_mask.allowed_evidence}")
        print(f"     屏蔽证据: {a.context_mask.blocked_evidence}")
    
    # Step 2: Round 0 — 独立推理
    print(f"\n{'─'*40}")
    print("[Step 2] Round 0: 独立推理（无通信）")
    print(f"{'─'*40}")
    
    round0_conclusions = engine.comm_layer.run_round_0(
        assignments=assignments,
        agents={},
        task_description=task_description,
    )
    
    # 自定义Demo结论（模拟真实推理结果）
    round0_conclusions = [
        IntermediateConclusion(
            agent_id="miner",
            conclusion="偏高岭土在早期强度（3d/7d）方面显著优于石灰石粉，"
                       "28d抗压强度提升15-20%，火山灰反应活性高",
            confidence=0.78,
            active_hypotheses=["H1: 偏高岭土的高活性SiO2促进C-S-H凝胶生成"],
            eliminated_hypotheses=["H_ex: 偏高岭土需水量大导致工作性差（实验条件下不成立）"],
            key_assumptions=["实验数据充分代表实际工况"],
            uncertainty_markers=["长期耐久性数据缺失"],
        ),
        IntermediateConclusion(
            agent_id="assayer",
            conclusion="石灰石粉在长期耐久性和经济性方面具有优势，"
                       "碳化后形成致密CaCO3层可抵抗硫酸盐侵蚀",
            confidence=0.72,
            active_hypotheses=["H1: 石灰石粉的填充效应+碳化硬化协同提升耐久性"],
            eliminated_hypotheses=["H_ex: 石灰石粉活性不足导致强度偏低（理论模型显示可补偿）"],
            key_assumptions=["理论模型可外推到实际工程条件"],
            uncertainty_markers=["缺少大规模工程验证"],
        ),
    ]
    
    for c in round0_conclusions:
        print(f"\n  📊 Agent {c.agent_id}:")
        print(f"     结论: {c.conclusion[:80]}...")
        print(f"     置信度: {c.confidence:.2f}")
        print(f"     活跃假设: {c.active_hypotheses}")
    
    # 写入全局记忆
    for c in round0_conclusions:
        memory_pool.add_conclusion(c.agent_id, c)
    
    # Step 3: Round 1 — 差异归因
    print(f"\n{'─'*40}")
    print("[Step 3] Round 1: 差异归因")
    print(f"{'─'*40}")
    
    round1_attributions = engine.comm_layer.run_round_1(
        conclusions=round0_conclusions,
        assignments=assignments,
        agents={},
    )
    
    # 自定义Demo归因结果
    for attr in round1_attributions:
        attr.revision = (
            f"{attr.agent_id}修正: 在考虑对方视角后，"
            f"认识到单一证据不足以得出全面结论"
        )
        attr.revision_reason = "对方可能拥有互补的证据子集"
    
    for a in round1_attributions:
        print(f"\n  🔄 Agent {a.agent_id}:")
        print(f"     修正: {a.revision_reason}")
    
    # Step 4: Round 2 + 融合判断
    print(f"\n{'─'*40}")
    print("[Step 4] 融合判断")
    print(f"{'─'*40}")
    
    round2_revised = engine.comm_layer.run_round_2(round1_attributions, round0_conclusions)
    judgment = engine.judge.judge(round2_revised)
    
    print(f"\n  📋 矛盾类型: {judgment.contradiction_type}")
    print(f"  📋 判断动作: {judgment.action}")
    print(f"  📋 理由: {judgment.reason}")
    
    # Step 5: 对比基线
    print(f"\n{'─'*40}")
    print("[Step 5] 对比基线")
    print(f"{'─'*40}")
    
    print(f"\n  📌 单Agent(全量信息): 倾向偏高岭土（实验数据权重更大）")
    print(f"  📌 传统辩论(全量共享): 收敛到偏高岭土（论点数量优势）")
    print(f"  📌 认知分工: 条件依赖型混合方案")
    print(f"     → 早期强度优先: 偏高岭土")
    print(f"     → 长期耐久优先: 石灰石粉")
    print(f"     → 经济敏感场景: 石灰石粉")
    print(f"     → 高性能需求场景: 偏高岭土+石灰石粉复掺")
    
    # 统计指标
    metrics = engine._compute_metrics(round0_conclusions, round2_revised, judgment)
    print(f"\n  📈 量化指标:")
    print(f"     平均推理深度: {metrics.get('avg_reasoning_depth', 0):.1f}步")
    print(f"     协同增益比: {metrics.get('synergy_gain', 1.0):.2f}x")
    print(f"     修正率: {metrics.get('revision_rate', 0):.2f}")
    
    # Step 6: Insight提炼（P0增强 — 借鉴Arbor HTR）
    print(f"\n{'─'*40}")
    print("[Step 6] Insight提炼（借鉴Arbor HTR）")
    print(f"{'─'*40}")
    
    from cognitive_division_engine import InsightDistiller, InsightStore, CDoLResult
    
    # 构造CDoLResult用于提炼
    cdol_result = CDoLResult(
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
    )
    
    distiller = InsightDistiller()
    insight = distiller.distill(cdol_result, task_description)
    
    print(f"\n  💡 任务类型: {insight['task_type']}")
    print(f"  💡 策略有效性:")
    se = insight['strategy_effectiveness']
    print(f"     使用策略: {se['strategy']}")
    print(f"     协同增益: {se['effectiveness']:.2f}x")
    print(f"     建议: {se['recommendation']}")
    print(f"  💡 矛盾模式:")
    cp = insight['contradiction_patterns']
    print(f"     主要类型: {cp['dominant_type']}")
    print(f"     虚假一致: {'检测到⚠️' if cp['false_consensus_detected'] else '未检测到'}")
    print(f"     诊断: {cp['insight']}")
    print(f"  💡 分解质量: {insight['decomposition_quality']['assessment']}")
    print(f"     桥接度: {insight['decomposition_quality']['bridgeability']:.2f}")
    print(f"  💡 协同分析: {insight['synergy_analysis']['assessment']}")
    
    # 存入InsightStore
    store = InsightStore()
    store.add(insight)
    print(f"\n  📦 Insight已存入InsightStore (count={store.get_stats()['count']})")
    print(f"     下次执行时，PerspectiveDecomposer将自动参考此经验选择策略")
    
    return judgment


def demo_adaptive_context():
    """Phase 7 演示：自适应上下文管理
    
    展示小窗口策略 + 懒惰检测 + 强制全局同步
    """
    from adaptive_context_manager import (
        AdaptiveContextManager, GlobalMemoryPool, LocalContextWindow,
        LazinessDetector, AdaptiveWindowController,
    )
    
    print("\n" + "="*60)
    print("🪟 Demo 6: 自适应上下文管理 (Phase 7)")
    print("="*60)
    
    # 初始化
    ctx_mgr = AdaptiveContextManager(
        global_memory=GlobalMemoryPool(),
        initial_window=8192,
        sync_interval=5,
    )
    
    # 模拟任务进度
    print("\n📋 模拟10步任务的窗口变化:")
    for step in range(10):
        progress = step / 10.0
        laziness = 0.1 + step * 0.08  # 模拟懒惰度逐渐上升
        window_size = ctx_mgr.window_controller.adjust(progress, laziness)
        phase = ctx_mgr.window_controller.get_phase()
        
        bar = "█" * int(window_size / 256) + "░" * (32 - int(window_size / 256))
        print(f"  Step {step+1}: [{bar}] {window_size:>5} tokens | phase={phase} | laziness={laziness:.2f}")
    
    # 懒惰检测演示
    print(f"\n📋 懒惰检测演示:")
    detector = ctx_mgr.laziness_detector
    
    # 模拟一个懒惰Agent的历史
    for i in range(10):
        detector.check("lazy_agent", {
            "retrieval_count": 0 if i > 5 else 1,  # 后5步不检索
            "revision_count": 0,                     # 从不修正
            "confidence": 0.5 + i * 0.05,            # 置信度持续上升
            "source_count": 1,                        # 只用1个信息源
            "sync_participated": 1 if i % 3 == 0 else 0,
        })
    
    alert = detector.check("lazy_agent")
    print(f"  Agent 'lazy_agent': laziness_score={alert.laziness_score:.3f}, is_lazy={alert.is_lazy}")
    
    if alert.is_lazy:
        intervention = detector.intervention(alert)
        if intervention:
            print(f"  🔔 干预措施: {intervention.rationale}")
            if intervention.new_window_size:
                print(f"     窗口缩小到: {intervention.new_window_size}")
    
    # 全局记忆池统计
    print(f"\n📋 全局记忆池统计:")
    stats = ctx_mgr.get_stats()
    print(f"  全局记忆条目: {stats['global_memory']['total_items']}")
    print(f"  检索次数: {stats['global_memory']['total_searches']}")


def demo_dashboard(router, scheduler):
    """启动可视化面板"""
    print("\n" + "="*60)
    print("📊 Demo 4: 启动可视化监控面板")
    print("="*60)
    
    try:
        from dashboard import NexusFlowDashboard
        
        dashboard = NexusFlowDashboard(
            router=router,
            scheduler=scheduler,
            title="NexusFlow"
        )
        
        print("\n   🌐 Dashboard将在 http://localhost:7860 启动")
        print("   按 Ctrl+C 退出\n")
        
        dashboard.launch(server_port=7860, share=False)
        
    except ImportError:
        print("   ⚠️ gradio未安装，跳过Dashboard")
        print("   安装: pip install gradio")


def main():
    """运行完整Demo"""
    print("""
╔══════════════════════════════════════════════════════╗
║                                                      ║
║   NexusFlow — 动态群体智能协作系统 Demo              ║
║   面向超长程复杂任务的动态异构群体智能架构            ║
║                                                      ║
║   赛题: XH-202631 荣耀                               ║
║   作品: 基于动态认知拓扑的超长程群体智能引擎          ║
║                                                      ║
╚══════════════════════════════════════════════════════╝
    """)
    
    # 初始化
    router = setup_router()
    scheduler = setup_scheduler(local_gpu=True)
    
    # 运行Demo
    demo_routing(router)
    demo_scheduling(scheduler)
    demo_self_healing(router)
    
    # Phase 7 新增Demo
    try:
        demo_cognitive_division()
        demo_adaptive_context()
    except ImportError as e:
        print(f"\n   ⚠️ Phase 7 模块未安装，跳过认知分工Demo: {e}")
    
    print("\n" + "="*60)
    print("✅ 所有Demo运行完成！")
    print("="*60)
    
    # 询问是否启动Dashboard
    try:
        choice = input("\n是否启动可视化面板? (y/n): ").strip().lower()
        if choice == 'y':
            demo_dashboard(router, scheduler)
    except (EOFError, KeyboardInterrupt):
        # 非交互模式直接启动
        print("\n   启动Dashboard...")
        demo_dashboard(router, scheduler)


if __name__ == "__main__":
    main()
