# -*- coding: utf-8 -*-
"""
nexus_orchestrator 模块单元测试
覆盖: TaskRoute 枚举值, TaskResult dataclass,
      NexusOrchestrator._route_task 路由逻辑,
      _select_participants 选择逻辑,
      get_status / get_roster 输出。
所有测试脱离 LLM。
"""
import pytest
from unittest.mock import patch, MagicMock

from nexus_orchestrator import (
    NexusOrchestrator,
    TaskRoute,
    TaskResult,
    COMPLEX_KEYWORDS,
    RESEARCH_KEYWORDS,
    CODING_KEYWORDS,
    DEFAULT_AGENT_MAP,
)


# ---------------------------------------------------------------------------
# TaskRoute 枚举
# ---------------------------------------------------------------------------

def test_task_route_values():
    assert TaskRoute.SIMPLE.value == "simple"
    assert TaskRoute.CDOL.value == "cdol"
    assert TaskRoute.RESEARCH.value == "research"
    assert TaskRoute.CODING.value == "coding"


def test_task_route_is_str_enum():
    assert isinstance(TaskRoute.SIMPLE, str)
    assert TaskRoute.SIMPLE == "simple"


def test_task_route_all_members():
    members = {m.value for m in TaskRoute}
    assert members == {"simple", "cdol", "research", "coding"}


# ---------------------------------------------------------------------------
# TaskResult dataclass
# ---------------------------------------------------------------------------

def test_task_result_defaults():
    tr = TaskResult()
    assert tr.task_id == ""
    assert tr.status == "pending"
    assert tr.participants == []
    assert tr.duration_seconds == 0.0
    assert tr.error is None
    assert tr.metadata == {}


def test_task_result_with_fields():
    tr = TaskResult(
        task_id="t1",
        task_description="测试任务",
        route="cdol",
        status="completed",
        result={"answer": "ok"},
        participants=["a1", "a2"],
        duration_seconds=1.5,
    )
    assert tr.task_id == "t1"
    assert tr.route == "cdol"
    assert tr.status == "completed"
    assert tr.result["answer"] == "ok"
    assert len(tr.participants) == 2


# ---------------------------------------------------------------------------
# NexusOrchestrator 构造
# ---------------------------------------------------------------------------

def _make_orchestrator(agents=None):
    """创建一个不依赖 LLM 的 orchestrator"""
    return NexusOrchestrator(agents=agents or {}, llm_chat=None)


def test_orchestrator_creation():
    orch = _make_orchestrator()
    assert orch._task_counter == 0
    assert orch._task_history == []
    assert orch.information_policy is not None


def test_orchestrator_with_agents():
    fake_agent = MagicMock()
    fake_agent.capabilities = ["test"]
    orch = _make_orchestrator(agents={"researcher": fake_agent})
    assert "researcher" in orch._agents


# ---------------------------------------------------------------------------
# _route_task 路由逻辑
# ---------------------------------------------------------------------------

def test_route_task_research():
    orch = _make_orchestrator()
    # 需要 >= 2 个 research keywords
    assert orch._route_task("文献检索与论文分析") == TaskRoute.RESEARCH
    assert orch._route_task("paper search survey") == TaskRoute.RESEARCH


def test_route_task_coding():
    orch = _make_orchestrator()
    assert orch._route_task("代码编程与实现") == TaskRoute.CODING
    assert orch._route_task("code implement develop") == TaskRoute.CODING


def test_route_task_cdol_complex():
    orch = _make_orchestrator()
    # 需要 >= 2 个 complex keywords
    assert orch._route_task("分析对比综合评估") == TaskRoute.CDOL


def test_route_task_simple():
    orch = _make_orchestrator()
    assert orch._route_task("你好") == TaskRoute.SIMPLE
    assert orch._route_task("简单的问题") == TaskRoute.SIMPLE


def test_route_task_single_keyword_simple():
    """单个关键词不足以触发特殊路由"""
    orch = _make_orchestrator()
    # 只有1个 research keyword → 不够 research_score >= 2
    assert orch._route_task("查看一篇文献") == TaskRoute.SIMPLE


def test_route_task_mixed_keywords_cdol():
    """research_score=1 + coding_score=1 → 合计>=2 且各自<2 → CDOL"""
    orch = _make_orchestrator()
    # "文献"→research=1, "实现"→coding=1, 各自不够2但合计>=2
    assert orch._route_task("文献与实现") == TaskRoute.CDOL


# ---------------------------------------------------------------------------
# _select_participants 选择逻辑
# ---------------------------------------------------------------------------

def test_select_participants_uses_policy_recommendation():
    agents = {"miner": MagicMock(), "researcher": MagicMock(), "assayer": MagicMock()}
    orch = _make_orchestrator(agents=agents)
    result = orch._select_participants("文献检索论文", TaskRoute.RESEARCH, max_agents=3)
    # 信息策略对文献类推荐 miner, researcher, assayer
    assert "miner" in result
    assert "researcher" in result
    assert len(result) <= 3


def test_select_participants_fallback_to_default():
    """当推荐 Agent 不在 agent 池中时，降级到默认映射"""
    # agent 池为空，推荐不可用
    orch = _make_orchestrator(agents={})
    result = orch._select_participants("文献检索", TaskRoute.RESEARCH, max_agents=3)
    # 降级到 DEFAULT_AGENT_MAP[RESEARCH]
    assert result == DEFAULT_AGENT_MAP[TaskRoute.RESEARCH][:3]


def test_select_participants_max_agents_limit():
    agents = {name: MagicMock() for name in
              ["miner", "researcher", "assayer", "caster", "executor"]}
    orch = _make_orchestrator(agents=agents)
    result = orch._select_participants("文献检索论文分析", TaskRoute.RESEARCH, max_agents=2)
    assert len(result) <= 2


# ---------------------------------------------------------------------------
# get_status
# ---------------------------------------------------------------------------

def test_get_status_structure():
    orch = _make_orchestrator()
    status = orch.get_status()
    assert "orchestrator" in status
    assert "agents" in status
    assert "context_manager" in status
    assert "information_policy" in status
    assert status["orchestrator"]["total_tasks"] == 0
    assert status["orchestrator"]["task_history_count"] == 0


def test_get_status_with_agents():
    agents = {"researcher": MagicMock(), "executor": MagicMock()}
    orch = _make_orchestrator(agents=agents)
    status = orch.get_status()
    assert "researcher" in status["agents"]
    assert status["agents"]["researcher"]["tier"] == "cdol"
    assert status["agents"]["executor"]["tier"] == "cdol"


def test_get_status_after_task():
    orch = _make_orchestrator()
    # execute 一个简单任务
    orch.execute("你好")
    status = orch.get_status()
    assert status["orchestrator"]["total_tasks"] == 1
    assert len(status["orchestrator"]["recent_tasks"]) == 1
    assert status["orchestrator"]["recent_tasks"][0]["status"] == "completed"


# ---------------------------------------------------------------------------
# get_roster
# ---------------------------------------------------------------------------

def test_get_roster_empty():
    orch = _make_orchestrator()
    assert orch.get_roster() == []


def test_get_roster_with_agents():
    agent1 = MagicMock()
    agent1.display_name = "研究员"
    agent1.capabilities = ["search", "analysis"]
    agent2 = MagicMock()
    agent2.display_name = "执行者"
    agent2.capabilities = ["execute"]

    orch = _make_orchestrator(agents={"researcher": agent1, "executor": agent2})
    roster = orch.get_roster()
    assert len(roster) == 2

    names = {r["name"] for r in roster}
    assert "researcher" in names
    assert "executor" in names

    researcher_entry = next(r for r in roster if r["name"] == "researcher")
    assert researcher_entry["tier"] == "cdol"
    assert researcher_entry["display_name"] == "研究员"
    assert "search" in researcher_entry["capabilities"]


def test_get_roster_unknown_agent_tier():
    """不在信息策略中的 Agent → tier='unknown'"""
    agent = MagicMock()
    agent.display_name = "自定义"
    agent.capabilities = []
    orch = _make_orchestrator(agents={"custom_agent": agent})
    roster = orch.get_roster()
    assert len(roster) == 1
    assert roster[0]["tier"] == "unknown"


# ---------------------------------------------------------------------------
# execute — 简单任务路由
# ---------------------------------------------------------------------------

def test_execute_simple_task():
    orch = _make_orchestrator()
    result = orch.execute("你好")
    assert result.status == "completed"
    assert result.route == TaskRoute.SIMPLE
    assert result.task_id == "task_0001"
    assert result.duration_seconds >= 0


def test_execute_increments_task_counter():
    orch = _make_orchestrator()
    orch.execute("任务1")
    orch.execute("任务2")
    assert orch._task_counter == 2
    assert len(orch._task_history) == 2


def test_execute_force_route():
    orch = _make_orchestrator()
    result = orch.execute("简单问题", force_route=TaskRoute.SIMPLE)
    assert result.route == TaskRoute.SIMPLE


def test_execute_records_history():
    orch = _make_orchestrator()
    result = orch.execute("测试任务")
    assert result in orch._task_history
    assert result.task_description == "测试任务"


# ---------------------------------------------------------------------------
# set_agents
# ---------------------------------------------------------------------------

def test_set_agents():
    orch = _make_orchestrator()
    assert len(orch._agents) == 0
    new_agents = {"researcher": MagicMock()}
    orch.set_agents(new_agents)
    assert "researcher" in orch._agents
