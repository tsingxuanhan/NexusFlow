#!/usr/bin/env python3
"""
P2 Demo: 可解释动态拓扑
========================
演示 DynamicRouter 的 P2 功能：
1. 路由决策解释（为什么选这个拓扑）
2. 优化器学习（从历史数据改进）
3. 改进建议生成
"""

import sys
import os
import json
from datetime import datetime

# Add nexusflow to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'nexusflow'))

from core.dynamic_router import (
    DynamicTopologyRouter,
    AgentCapabilityProfile,
    TaskRequirement,
    TaskComplexity,
    AgentLoadState,
)


def setup_demo_router() -> DynamicTopologyRouter:
    """创建演示用的路由器，注册几个 Agent"""
    router = DynamicTopologyRouter()
    
    # 注册 Coordinator
    router.register_agent(AgentCapabilityProfile(
        agent_id="coordinator",
        name="协调师",
        role="coordinator",
        capabilities=["task_decomposition", "agent_routing", "workflow_management"],
        domain_expertise=["general", "planning"],
        load_state=AgentLoadState.IDLE,
        tier="cloud",
        reasoning_depth=0.8,
        creativity=0.5,
    ))
    
    # 注册 Researcher
    router.register_agent(AgentCapabilityProfile(
        agent_id="researcher",
        name="研究员",
        role="researcher",
        capabilities=["web_search", "document_analysis", "synthesis"],
        domain_expertise=["research", "analysis"],
        load_state=AgentLoadState.IDLE,
        tier="cloud",
        avg_latency_ms=2000,
        reasoning_depth=0.9,
        creativity=0.6,
    ))
    
    # 注册 Executor
    router.register_agent(AgentCapabilityProfile(
        agent_id="executor",
        name="执行者",
        role="executor",
        capabilities=["code_generation", "file_operations", "tool_usage"],
        domain_expertise=["engineering", "implementation"],
        load_state=AgentLoadState.IDLE,
        tier="edge",
        avg_latency_ms=800,
        reasoning_depth=0.7,
        creativity=0.4,
    ))
    
    # 注册 Reviewer
    router.register_agent(AgentCapabilityProfile(
        agent_id="reviewer",
        name="审查师",
        role="reviewer",
        capabilities=["code_review", "quality_assurance", "testing"],
        domain_expertise=["quality", "validation"],
        load_state=AgentLoadState.IDLE,
        tier="cloud",
        avg_latency_ms=1500,
        reasoning_depth=0.85,
        creativity=0.3,
    ))
    
    return router


def demo_routing_explanation():
    """演示 1: 路由决策解释"""
    print("=" * 70)
    print("  演示 1: 路由决策解释")
    print("=" * 70)
    print()
    
    router = setup_demo_router()
    
    # 创建一个中等复杂度任务
    task = TaskRequirement(
        task_id="demo_task_001",
        description="分析 GitHub 仓库的代码质量并提出改进建议",
        required_capabilities=["code_analysis", "quality_assurance"],
        required_domains=["engineering"],
        complexity=TaskComplexity.MODERATE,
        latency_budget_ms=30000,
    )
    
    print(f"任务: {task.description}")
    print(f"复杂度: {task.complexity.name}")
    print(f"需要能力: {', '.join(task.required_capabilities)}")
    print()
    
    # 路由决策
    plan = router.route(task)
    
    print(f"路由方案 ID: {plan.plan_id}")
    print(f"Agent 链: {' → '.join(plan.agent_chain)}")
    print(f"拓扑类型: {plan.topology_type}")
    print(f"预估延迟: {plan.estimated_latency_ms/1000:.1f}s")
    print(f"置信度: {plan.confidence:.1%}")
    print()
    
    # 显示解释
    if hasattr(plan, 'explanation') and plan.explanation:
        print("📋 决策解释:")
        print(plan.explanation.human_readable)
        print()
        
        print("📊 因子分析:")
        for factor in plan.explanation.factor_breakdown:
            emoji = "✅" if factor.contribution > 0 else "❌"
            print(f"  {emoji} {factor.factor_name}: {factor.contribution:+.2f}")
            print(f"     {factor.description}")
        print()
        
        if plan.explanation.bottlenecks:
            print("⚠️  识别的瓶颈:")
            for bottleneck in plan.explanation.bottlenecks:
                print(f"  - {bottleneck}")
            print()
    else:
        print("❌ 未生成解释（P2 模块可能未加载）")
    
    print()


def demo_optimization_learning():
    """演示 2: 优化器学习"""
    print("=" * 70)
    print("  演示 2: 优化器学习")
    print("=" * 70)
    print()
    
    router = setup_demo_router()
    
    # 模拟多次任务执行
    tasks = [
        TaskRequirement(
            task_id=f"task_{i}",
            description="数据分析任务",
            required_capabilities=["data_analysis"],
            complexity=TaskComplexity.MODERATE,
        )
        for i in range(5)
    ]
    
    print("模拟执行 5 个类似任务...")
    print()
    
    for i, task in enumerate(tasks, 1):
        plan = router.route(task)
        
        # 模拟执行结果
        success = i != 3  # 第 3 个失败
        outcome = {
            "success": success,
            "latency_ms": 15000 + i * 1000,
            "cost": 0.05 * len(plan.agent_chain),
            "tokens": 2000 * len(plan.agent_chain),
            "errors": [] if success else ["timeout"],
            "completion_rate": 1.0 if success else 0.6,
        }
        
        # 记录结果
        router.record_execution_outcome(plan.plan_id, outcome)
        
        status = "✅" if success else "❌"
        print(f"  {status} 任务 {i}: {len(plan.agent_chain)} agents, "
              f"latency={outcome['latency_ms']}ms, "
              f"success={success}")
    
    print()
    
    # 显示优化器统计
    stats = router.get_optimization_stats()
    print("📈 优化器统计:")
    print(f"  启用: {stats['enabled']}")
    if stats['enabled']:
        opt_stats = stats['optimizer']
        print(f"  总模式数: {opt_stats['total_patterns']}")
        print(f"  总执行数: {opt_stats['total_executions']}")
        print(f"  成功率: {opt_stats['success_rate']:.1%}")
        print(f"  已学习权重: {opt_stats['learned_weight_count']}")
    
    print()
    
    # 生成建议
    if router._p2_enabled:
        print("💡 优化建议:")
        recommendations = router.optimizer.recommend_improvements(plan)
        for rec in recommendations[:3]:
            print(f"  - {rec}")
    
    print()


def demo_comparison():
    """演示 3: 不同任务的拓扑对比"""
    print("=" * 70)
    print("  演示 3: 不同任务的拓扑对比")
    print("=" * 70)
    print()
    
    router = setup_demo_router()
    
    tasks = [
        ("简单任务", TaskRequirement(
            description="格式化代码",
            complexity=TaskComplexity.SIMPLE,
            required_capabilities=["code_formatting"],
        )),
        ("中等任务", TaskRequirement(
            description="重构一个模块",
            complexity=TaskComplexity.MODERATE,
            required_capabilities=["code_analysis", "refactoring"],
        )),
        ("复杂任务", TaskRequirement(
            description="跨模块重构并添加新功能",
            complexity=TaskComplexity.COMPLEX,
            required_capabilities=["architecture", "code_generation", "testing"],
        )),
    ]
    
    print(f"{'任务':<10} {'Agent数':<10} {'拓扑类型':<15} {'延迟(ms)':<10} {'置信度':<10}")
    print("-" * 70)
    
    for name, task in tasks:
        plan = router.route(task)
        print(f"{name:<10} {len(plan.agent_chain):<10} {plan.topology_type:<15} "
              f"{plan.estimated_latency_ms:<10.0f} {plan.confidence:<10.1%}")
    
    print()
    print("观察: 随着任务复杂度增加，系统选择更多 Agent 协作，拓扑更复杂")
    print()


def main():
    """主函数"""
    print()
    print("╔" + "=" * 68 + "╗")
    print("║" + " " * 20 + "P2 可解释动态拓扑演示" + " " * 25 + "║")
    print("╚" + "=" * 68 + "╝")
    print()
    print(f"时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    demo_routing_explanation()
    demo_optimization_learning()
    demo_comparison()
    
    print("=" * 70)
    print("  演示完成")
    print("=" * 70)
    print()
    print("总结:")
    print("  1. 路由决策可解释：每个决策都有清晰的因子分析和备选方案对比")
    print("  2. 优化器持续学习：从执行结果中学习最优路由模式")
    print("  3. 拓扑自适应：根据任务复杂度自动调整 Agent 数量和协作方式")
    print()


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"\n❌ 演示失败: {e}")
        print("\n可能原因:")
        print("  - P2 模块未正确安装")
        print("  - 依赖缺失（networkx 等）")
        print(f"\n详细错误: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
