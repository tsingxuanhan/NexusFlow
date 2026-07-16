# -*- coding: utf-8 -*-
"""
base_agent 模块单元测试
覆盖: AgentRole, AgentRunMode, Message, TodoProvider,
      ContextCompactor, BaseAgent 初始化与基础方法
所有 LLM 调用已 mock。
"""
import pytest
from unittest.mock import patch, MagicMock, PropertyMock
from datetime import datetime

from nexusflow.agents.base_agent import (
    AgentRole,
    AgentRunMode,
    Message,
    TodoItem,
    TodoProvider,
    ContextCompactor,
    ROLE_MODEL_MAP,
    MODE_MODEL_MAP,
)


# ---------------------------------------------------------------------------
# AgentRole 枚举
# ---------------------------------------------------------------------------

def test_agent_role_values():
    assert AgentRole.PLANNER.value == "planner"
    assert AgentRole.RESEARCHER.value == "researcher"
    assert AgentRole.EXECUTOR.value == "executor"
    assert AgentRole.REVIEWER.value == "reviewer"


def test_agent_role_all_members():
    members = {r.value for r in AgentRole}
    assert members == {"planner", "researcher", "executor", "reviewer"}


# ---------------------------------------------------------------------------
# AgentRunMode 枚举
# ---------------------------------------------------------------------------

def test_agent_run_mode_values():
    assert AgentRunMode.PLAN.value == "plan"
    assert AgentRunMode.EXECUTE.value == "execute"
    assert AgentRunMode.REFLECT.value == "reflect"


def test_agent_run_mode_from_string():
    assert AgentRunMode("plan") == AgentRunMode.PLAN
    assert AgentRunMode("execute") == AgentRunMode.EXECUTE
    assert AgentRunMode("reflect") == AgentRunMode.REFLECT


def test_agent_run_mode_invalid():
    with pytest.raises(ValueError):
        AgentRunMode("invalid")


# ---------------------------------------------------------------------------
# Message 数据类
# ---------------------------------------------------------------------------

def test_message_creation():
    msg = Message(role="user", content="hello")
    assert msg.role == "user"
    assert msg.content == "hello"
    assert msg.timestamp  # non-empty


def test_message_to_dict():
    msg = Message(role="assistant", content="hi")
    d = msg.to_dict()
    assert d == {"role": "assistant", "content": "hi"}


def test_message_default_timestamp():
    msg = Message(role="system", content="test")
    # Timestamp should be a valid ISO format string
    assert "T" in msg.timestamp


# ---------------------------------------------------------------------------
# TodoItem 数据类
# ---------------------------------------------------------------------------

def test_todo_item_defaults():
    item = TodoItem(id="todo_1", task="do something")
    assert item.priority == 0
    assert item.status == "pending"
    assert item.result is None


def test_todo_item_to_dict():
    item = TodoItem(id="todo_1", task="do something", priority=2, status="done", result="ok")
    d = item.to_dict()
    assert d["id"] == "todo_1"
    assert d["task"] == "do something"
    assert d["priority"] == 2
    assert d["status"] == "done"
    assert d["result"] == "ok"


# ---------------------------------------------------------------------------
# TodoProvider
# ---------------------------------------------------------------------------

def test_todo_provider_add():
    tp = TodoProvider()
    tid = tp.add("task A", priority=1)
    assert tid == "todo_1"
    items = tp.get_all()
    assert len(items) == 1
    assert items[0].task == "task A"


def test_todo_provider_complete():
    tp = TodoProvider()
    tid = tp.add("task A")
    assert tp.complete(tid, result="done!")
    items = tp.get_all()
    assert items[0].status == "done"
    assert items[0].result == "done!"


def test_todo_provider_fail():
    tp = TodoProvider()
    tid = tp.add("task B")
    assert tp.fail(tid, reason="error")
    items = tp.get_all()
    assert items[0].status == "failed"
    assert items[0].result == "error"


def test_todo_provider_start():
    tp = TodoProvider()
    tid = tp.add("task C")
    assert tp.start(tid)
    running = tp.get_running()
    assert len(running) == 1
    assert running[0].id == tid


def test_todo_provider_get_pending_sorted():
    tp = TodoProvider()
    tp.add("low", priority=1)
    tp.add("high", priority=5)
    tp.add("mid", priority=3)
    pending = tp.get_pending()
    assert pending[0].priority == 5
    assert pending[1].priority == 3
    assert pending[2].priority == 1


def test_todo_provider_complete_nonexistent():
    tp = TodoProvider()
    assert not tp.complete("nonexistent")


def test_todo_provider_fail_nonexistent():
    tp = TodoProvider()
    assert not tp.fail("nonexistent")


def test_todo_provider_start_nonexistent():
    tp = TodoProvider()
    assert not tp.start("nonexistent")


def test_todo_provider_to_context_empty():
    tp = TodoProvider()
    assert tp.to_context() == ""


def test_todo_provider_to_context_with_items():
    tp = TodoProvider()
    tp.add("task A", priority=2)
    tp.start("todo_1")
    tp.add("task B", priority=1)
    ctx = tp.to_context()
    assert "当前任务列表" in ctx
    assert "进行中" in ctx
    assert "待执行" in ctx


# ---------------------------------------------------------------------------
# ContextCompactor
# ---------------------------------------------------------------------------

def test_context_compactor_estimate_tokens_english():
    cc = ContextCompactor()
    messages = [{"role": "user", "content": "hello world"}]
    tokens = cc.estimate_tokens(messages)
    assert tokens > 0


def test_context_compactor_estimate_tokens_chinese():
    cc = ContextCompactor()
    messages = [{"role": "user", "content": "你好世界"}]
    tokens = cc.estimate_tokens(messages)
    # 4 Chinese chars * 2 = 8 tokens
    assert tokens == 8


def test_context_compactor_no_compact_under_threshold():
    cc = ContextCompactor(threshold=8000, keep_recent=4)
    messages = [{"role": "user", "content": "short message"}]
    result = cc.check_and_compact(messages)
    assert result == messages  # no change


def test_context_compactor_truncate_when_over_threshold():
    cc = ContextCompactor(threshold=10, keep_recent=2)
    # Create many messages to exceed threshold
    messages = [{"role": "user", "content": "x" * 100} for _ in range(10)]
    result = cc.check_and_compact(messages)
    # Should have truncated — fewer non-system messages
    non_system = [m for m in result if m.get("role") != "system"]
    # keep_recent=2, so we expect <= 3 (2 recent + 1 truncation notice)
    assert len(non_system) <= 3


def test_context_compactor_preserves_system_messages():
    cc = ContextCompactor(threshold=10, keep_recent=2)
    messages = [
        {"role": "system", "content": "You are a helper."},
        {"role": "user", "content": "x" * 100},
        {"role": "assistant", "content": "y" * 100},
        {"role": "user", "content": "z" * 100},
    ]
    result = cc.check_and_compact(messages)
    system_msgs = [m for m in result if m.get("role") == "system"]
    assert len(system_msgs) >= 1
    assert system_msgs[0]["content"] == "You are a helper."


# ---------------------------------------------------------------------------
# ROLE_MODEL_MAP and MODE_MODEL_MAP
# ---------------------------------------------------------------------------

def test_role_model_map_completeness():
    for role in AgentRole:
        assert role in ROLE_MODEL_MAP


def test_mode_model_map_completeness():
    for mode in AgentRunMode:
        assert mode in MODE_MODEL_MAP


# ---------------------------------------------------------------------------
# BaseAgent 初始化 (需要 mock 外部依赖)
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_base_agent_deps():
    """Mock BaseAgent 的所有外部依赖，使初始化不依赖真实 API"""
    with patch.dict('os.environ', {"DEEPSEEK_API_KEY": "test_key"}):
        yield


def test_base_agent_role_description():
    from nexusflow.agents.base_agent import BaseAgent
    desc = BaseAgent._get_role_description(AgentRole.PLANNER)
    assert "规划" in desc or "策略" in desc
    
    desc2 = BaseAgent._get_role_description(AgentRole.EXECUTOR)
    assert "执行" in desc2


def test_base_agent_invalid_role_description():
    from nexusflow.agents.base_agent import BaseAgent
    desc = BaseAgent._get_role_description(None)
    assert desc == "通用智能体"


def test_base_agent_classify_error():
    from nexusflow.agents.base_agent import BaseAgent
    # Use class constants directly to avoid MagicMock intercepting class attrs
    assert BaseAgent.ERROR_RATE_LIMIT == "rate_limit"
    assert BaseAgent.ERROR_SERVER == "server_error"
    assert BaseAgent.ERROR_BAD_REQUEST == "bad_request"
    assert BaseAgent.ERROR_AUTH == "auth_error"
    assert BaseAgent.ERROR_TIMEOUT == "timeout"
    assert BaseAgent.ERROR_UNKNOWN == "unknown"
    
    # Test _classify_error with a minimal dummy self that has class constants
    class DummySelf:
        ERROR_RATE_LIMIT = "rate_limit"
        ERROR_SERVER = "server_error"
        ERROR_BAD_REQUEST = "bad_request"
        ERROR_AUTH = "auth_error"
        ERROR_TIMEOUT = "timeout"
        ERROR_UNKNOWN = "unknown"
    
    dummy = DummySelf()
    assert BaseAgent._classify_error(dummy, 429) == "rate_limit"
    assert BaseAgent._classify_error(dummy, 500) == "server_error"
    assert BaseAgent._classify_error(dummy, 400) == "bad_request"
    assert BaseAgent._classify_error(dummy, 401) == "auth_error"
    assert BaseAgent._classify_error(dummy, 418) == "unknown"


def test_base_agent_classify_error_timeout():
    from nexusflow.agents.base_agent import BaseAgent
    
    class DummySelf:
        ERROR_RATE_LIMIT = "rate_limit"
        ERROR_SERVER = "server_error"
        ERROR_BAD_REQUEST = "bad_request"
        ERROR_AUTH = "auth_error"
        ERROR_TIMEOUT = "timeout"
        ERROR_UNKNOWN = "unknown"
    
    dummy = DummySelf()
    exc = TimeoutError("timeout")
    assert BaseAgent._classify_error(dummy, 0, exc) == "timeout"


def test_base_agent_classify_error_connection():
    from nexusflow.agents.base_agent import BaseAgent
    
    class DummySelf:
        ERROR_RATE_LIMIT = "rate_limit"
        ERROR_SERVER = "server_error"
        ERROR_BAD_REQUEST = "bad_request"
        ERROR_AUTH = "auth_error"
        ERROR_TIMEOUT = "timeout"
        ERROR_UNKNOWN = "unknown"
    
    dummy = DummySelf()
    exc = ConnectionError("conn failed")
    assert BaseAgent._classify_error(dummy, 0, exc) == "timeout"


# ---------------------------------------------------------------------------
# _parse_plan_to_todos
# ---------------------------------------------------------------------------

def test_parse_plan_to_todos():
    from nexusflow.agents.base_agent import BaseAgent
    agent = MagicMock(spec=BaseAgent)
    agent.todo = TodoProvider()
    
    plan_text = """
1. 分析需求
2. 设计方案
3. 编写代码
4. 测试验证
"""
    BaseAgent._parse_plan_to_todos(agent, plan_text)
    pending = agent.todo.get_pending()
    assert len(pending) == 4
    assert "分析需求" in pending[0].task


def test_parse_plan_to_todos_step_format():
    from nexusflow.agents.base_agent import BaseAgent
    agent = MagicMock(spec=BaseAgent)
    agent.todo = TodoProvider()
    
    plan_text = """
步骤1: 收集数据
步骤2: 处理数据
"""
    BaseAgent._parse_plan_to_todos(agent, plan_text)
    pending = agent.todo.get_pending()
    assert len(pending) == 2


# ---------------------------------------------------------------------------
# _get_retry_config
# ---------------------------------------------------------------------------

def test_get_retry_config():
    from nexusflow.agents.base_agent import BaseAgent
    
    # _get_retry_config uses self.ERROR_RATE_LIMIT etc. as dict keys.
    # We need a self with the same class-level constants.
    class DummySelf:
        ERROR_RATE_LIMIT = BaseAgent.ERROR_RATE_LIMIT
        ERROR_SERVER = BaseAgent.ERROR_SERVER
        ERROR_BAD_REQUEST = BaseAgent.ERROR_BAD_REQUEST
        ERROR_AUTH = BaseAgent.ERROR_AUTH
        ERROR_TIMEOUT = BaseAgent.ERROR_TIMEOUT
        ERROR_UNKNOWN = BaseAgent.ERROR_UNKNOWN
    
    dummy = DummySelf()
    config = BaseAgent._get_retry_config(dummy, "rate_limit")
    assert config["max_retries"] == 5
    
    config2 = BaseAgent._get_retry_config(dummy, "auth_error")
    assert config2["max_retries"] == 0
    
    config3 = BaseAgent._get_retry_config(dummy, "unknown_type")
    assert config3["max_retries"] == 1
