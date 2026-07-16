# -*- coding: utf-8 -*-
"""
dynamic_router 模块单元测试
覆盖: AgentLoadState, TaskComplexity, AgentCapabilityProfile,
      TaskRequirement, RoutePlan, DynamicTopologyRouter
"""
import pytest
from unittest.mock import patch, MagicMock

from nexusflow.core.dynamic_router import (
    AgentLoadState,
    TaskComplexity,
    AgentCapabilityProfile,
    TaskRequirement,
    RoutePlan,
    DynamicTopologyRouter,
)


# ---------------------------------------------------------------------------
# AgentLoadState 枚举
# ---------------------------------------------------------------------------

def test_agent_load_state_values():
    assert AgentLoadState.IDLE.value == "idle"
    assert AgentLoadState.BUSY.value == "busy"
    assert AgentLoadState.OVERLOADED.value == "overloaded"
    assert AgentLoadState.OFFLINE.value == "offline"
    assert AgentLoadState.WARMING.value == "warming"


def test_agent_load_state_all_members():
    members = {s.value for s in AgentLoadState}
    assert members == {"idle", "busy", "overloaded", "offline", "warming"}


# ---------------------------------------------------------------------------
# TaskComplexity 枚举
# ---------------------------------------------------------------------------

def test_task_complexity_values():
    assert TaskComplexity.TRIVIAL.value == 1
    assert TaskComplexity.SIMPLE.value == 2
    assert TaskComplexity.MODERATE.value == 3
    assert TaskComplexity.COMPLEX.value == 4
    assert TaskComplexity.EPIC.value == 5


def test_task_complexity_ordering():
    assert TaskComplexity.TRIVIAL.value < TaskComplexity.EPIC.value


# ---------------------------------------------------------------------------
# AgentCapabilityProfile 数据类
# ---------------------------------------------------------------------------

def test_agent_capability_profile_defaults():
    p = AgentCapabilityProfile(agent_id="a1", name="Agent1", role="executor")
    assert p.load_state == AgentLoadState.IDLE
    assert p.current_tasks == 0
    assert p.max_concurrent == 3
    assert p.success_rate == 1.0
    assert p.tier == "cloud"
    assert p.capabilities == []
    assert p.domain_expertise == []
    assert p.can_handoff is True
    assert p.preferred_partners == []


def test_agent_capability_profile_compute_score_idle():
    p = AgentCapabilityProfile(agent_id="a1", name="Agent1", role="executor")
    score = p.compute_score()
    # idle, 0 tasks, success_rate=1.0, latency=500
    # load_factor=1.0, health_factor=1.0, latency_factor=1/(1+0.5)=0.6667
    assert score > 0
    assert score <= 1.0


def test_agent_capability_profile_compute_score_offline():
    p = AgentCapabilityProfile(
        agent_id="a1", name="Agent1", role="executor",
        load_state=AgentLoadState.OFFLINE
    )
    assert p.compute_score() == 0.0


def test_agent_capability_profile_compute_score_overloaded():
    p = AgentCapabilityProfile(
        agent_id="a1", name="Agent1", role="executor",
        load_state=AgentLoadState.OVERLOADED,
        current_tasks=3, max_concurrent=3,
    )
    score = p.compute_score()
    # load_factor=0 * 0.3 = 0
    assert score == 0.0


def test_agent_capability_profile_compute_score_warming():
    p = AgentCapabilityProfile(
        agent_id="a1", name="Agent1", role="executor",
        load_state=AgentLoadState.WARMING,
        current_tasks=0, max_concurrent=3,
    )
    score = p.compute_score()
    # load_factor=1.0 * 0.5 = 0.5
    assert 0 < score < 1.0


def test_agent_capability_profile_compute_score_busy():
    p = AgentCapabilityProfile(
        agent_id="a1", name="Agent1", role="executor",
        load_state=AgentLoadState.BUSY,
        current_tasks=2, max_concurrent=4,
        success_rate=0.9, avg_latency_ms=200.0,
    )
    score = p.compute_score()
    assert 0 < score <= 1.0


# ---------------------------------------------------------------------------
# TaskRequirement 数据类
# ---------------------------------------------------------------------------

def test_task_requirement_defaults():
    t = TaskRequirement()
    assert t.task_id == ""
    assert t.complexity == TaskComplexity.MODERATE
    assert t.latency_budget_ms == 30000.0
    assert t.privacy_level == 0
    assert t.is_creative is False
    assert t.execution_mode == "sequential"
    assert t.perspective_count == 2


def test_task_requirement_custom():
    t = TaskRequirement(
        task_id="t1",
        required_capabilities=["coding"],
        required_domains=["math"],
        complexity=TaskComplexity.COMPLEX,
        is_creative=True,
    )
    assert t.task_id == "t1"
    assert t.complexity == TaskComplexity.COMPLEX
    assert t.is_creative is True


# ---------------------------------------------------------------------------
# RoutePlan 数据类
# ---------------------------------------------------------------------------

def test_route_plan_defaults():
    rp = RoutePlan()
    assert rp.plan_id == ""
    assert rp.agent_chain == []
    assert rp.topology_type == "sequential"
    assert rp.status == "planned"
    assert rp.cdol_enabled is False


# ---------------------------------------------------------------------------
# DynamicTopologyRouter 核心类
# ---------------------------------------------------------------------------

def _make_router_with_agents():
    """创建一个预注册了若干 Agent 的路由器"""
    router = DynamicTopologyRouter(auto_rebuild_interval=10)
    
    a1 = AgentCapabilityProfile(
        agent_id="a1", name="Planner", role="planner",
        capabilities=["planning", "analysis"],
        domain_expertise=["general"],
        tier="cloud", avg_latency_ms=300, success_rate=0.95,
    )
    a2 = AgentCapabilityProfile(
        agent_id="a2", name="Coder", role="executor",
        capabilities=["coding", "debugging"],
        domain_expertise=["programming"],
        tier="cloud", avg_latency_ms=400, success_rate=0.9,
    )
    a3 = AgentCapabilityProfile(
        agent_id="a3", name="Reviewer", role="reviewer",
        capabilities=["review", "testing"],
        domain_expertise=["quality"],
        tier="cloud", avg_latency_ms=200, success_rate=0.98,
    )
    router.register_agent(a1)
    router.register_agent(a2)
    router.register_agent(a3)
    return router


def test_router_init():
    router = DynamicTopologyRouter()
    assert router._agents == {}
    assert router._request_count == 0
    assert router._auto_rebuild_interval == 10


def test_router_register_agent():
    router = DynamicTopologyRouter()
    p = AgentCapabilityProfile(agent_id="a1", name="Test", role="executor")
    router.register_agent(p)
    assert "a1" in router._agents
    assert router._agents["a1"].name == "Test"


def test_router_unregister_agent():
    router = _make_router_with_agents()
    assert "a1" in router._agents
    router.unregister_agent("a1")
    assert "a1" not in router._agents


def test_router_unregister_nonexistent():
    router = DynamicTopologyRouter()
    router.unregister_agent("nonexistent")  # should not raise


def test_router_update_agent_state():
    router = _make_router_with_agents()
    router.update_agent_state("a1", load_state=AgentLoadState.BUSY, current_tasks=2)
    assert router._agents["a1"].load_state == AgentLoadState.BUSY
    assert router._agents["a1"].current_tasks == 2


def test_router_update_agent_state_unknown():
    router = DynamicTopologyRouter()
    router.update_agent_state("unknown", load_state=AgentLoadState.BUSY)  # should not raise


def test_router_route_simple_task():
    router = _make_router_with_agents()
    task = TaskRequirement(
        task_id="t1",
        required_capabilities=["planning"],
        complexity=TaskComplexity.TRIVIAL,
    )
    plan = router.route(task)
    assert plan.task_id == "t1"
    assert plan.status != "failed"
    assert len(plan.agent_chain) >= 1


def test_router_route_no_candidates():
    router = _make_router_with_agents()
    task = TaskRequirement(
        task_id="t2",
        required_capabilities=["quantum_computing"],  # no agent has this
        complexity=TaskComplexity.SIMPLE,
    )
    plan = router.route(task)
    assert plan.status == "failed"
    assert plan.confidence == 0.0


def test_router_route_complex_task():
    router = _make_router_with_agents()
    task = TaskRequirement(
        task_id="t3",
        required_capabilities=["planning", "coding", "review"],
        complexity=TaskComplexity.COMPLEX,
    )
    plan = router.route(task)
    assert len(plan.agent_chain) > 1


def test_router_route_offline_agents():
    router = _make_router_with_agents()
    # Mark all agents offline
    for aid in list(router._agents.keys()):
        router._agents[aid].load_state = AgentLoadState.OFFLINE
    task = TaskRequirement(task_id="t4", required_capabilities=["planning"])
    plan = router.route(task)
    assert plan.status == "failed"


def test_router_get_topology_summary():
    router = _make_router_with_agents()
    summary = router.get_topology_summary()
    assert summary["total_agents"] == 3
    assert summary["online_agents"] == 3
    assert len(summary["agents"]) == 3


def test_router_get_route_history():
    router = _make_router_with_agents()
    task = TaskRequirement(task_id="t1", required_capabilities=["planning"])
    router.route(task)
    router.route(task)
    history = router.get_route_history()
    assert len(history) == 2


def test_router_get_agent_detail():
    router = _make_router_with_agents()
    detail = router.get_agent_detail("a1")
    assert detail is not None
    assert detail["name"] == "Planner"
    assert detail["role"] == "planner"


def test_router_get_agent_detail_nonexistent():
    router = DynamicTopologyRouter()
    assert router.get_agent_detail("nope") is None


def test_router_handle_agent_failure_with_replacement():
    router = _make_router_with_agents()
    # Register a 4th agent with overlapping "planning" capability so replacement exists
    a4 = AgentCapabilityProfile(
        agent_id="a4", name="Analyst", role="planner",
        capabilities=["planning", "analysis", "research"],
        domain_expertise=["general"],
        tier="cloud", avg_latency_ms=350, success_rate=0.92,
    )
    router.register_agent(a4)
    task = TaskRequirement(task_id="t1", required_capabilities=["planning"])
    plan = router.route(task)
    plan.status = "executing"
    plan.agent_chain = ["a1", "a2", "a3"]  # ensure multi-agent chain
    # a1 fails → should be replaced by a4
    new_plan = router.handle_agent_failure("a1", plan)
    assert new_plan is not None
    assert "a1" not in new_plan.agent_chain
    assert new_plan.status == "rerouted"


def test_router_handle_agent_failure_no_replacement_empty_chain():
    """When no replacement found and remaining chain is empty, returns None"""
    router = _make_router_with_agents()
    task = TaskRequirement(
        task_id="t1",
        required_capabilities=["planning"],
        complexity=TaskComplexity.TRIVIAL,
    )
    plan = router.route(task)
    # With TRIVIAL task, chain likely has 1 agent. Removing it → empty chain.
    failed_agent = plan.agent_chain[0] if plan.agent_chain else "a1"
    new_plan = router.handle_agent_failure(failed_agent, plan)
    # If remaining chain is empty and no replacement → None
    if not [a for a in plan.agent_chain if a != failed_agent]:
        assert new_plan is None
    else:
        assert new_plan is not None


def test_router_handle_agent_failure_not_in_chain():
    router = _make_router_with_agents()
    plan = RoutePlan(agent_chain=["a1", "a2"], task_id="t1")
    result = router.handle_agent_failure("a3", plan)
    # a3 not in chain → return same plan
    assert result is plan


def test_router_suggest_optimization_no_history():
    router = DynamicTopologyRouter()
    suggestions = router.suggest_optimization()
    assert "No routing history yet" in suggestions


def test_router_suggest_optimization_with_overload():
    router = _make_router_with_agents()
    router._agents["a1"].load_state = AgentLoadState.OVERLOADED
    task = TaskRequirement(task_id="t1", required_capabilities=["planning"])
    router.route(task)
    suggestions = router.suggest_optimization()
    assert any("Overloaded" in s for s in suggestions)


def test_router_route_with_privacy_constraint():
    router = _make_router_with_agents()
    # Set a1 to edge tier
    router._agents["a1"].tier = "edge"
    task = TaskRequirement(
        task_id="t5",
        required_capabilities=["planning"],
        privacy_level=2,
        preferred_tier="edge",
    )
    plan = router.route(task)
    # Only edge tier agents should be candidates
    if plan.status != "failed":
        for aid in plan.agent_chain:
            if aid in router._agents:
                assert router._agents[aid].tier == "edge"


def test_router_route_increments_request_count():
    router = _make_router_with_agents()
    assert router._request_count == 0
    task = TaskRequirement(task_id="t1")
    router.route(task)
    assert router._request_count == 1
    router.route(task)
    assert router._request_count == 2
