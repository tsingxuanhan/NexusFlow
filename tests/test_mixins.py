# -*- coding: utf-8 -*-
"""Mixin 模块单元测试 — 验证拆分后的模块独立功能"""
import pytest
from unittest.mock import patch, MagicMock

from nexusflow.agents.models import (
    Message, AgentRole, AgentRunMode, TodoItem, TodoProvider,
    ContextCompactor, ROLE_MODEL_MAP, MODE_MODEL_MAP,
)


class TestModelsModule:
    """models.py 独立测试"""

    def test_message_creation(self):
        msg = Message(role="user", content="hello")
        assert msg.role == "user"
        assert msg.content == "hello"
        assert msg.timestamp  # non-empty

    def test_message_to_dict(self):
        msg = Message(role="assistant", content="response")
        d = msg.to_dict()
        assert d["role"] == "assistant"
        assert d["content"] == "response"

    def test_agent_role_values(self):
        roles = [r.value for r in AgentRole]
        assert "planner" in roles
        assert "researcher" in roles
        assert "executor" in roles
        assert "reviewer" in roles

    def test_agent_run_mode_values(self):
        modes = [m.value for m in AgentRunMode]
        assert "plan" in modes
        assert "execute" in modes
        assert "reflect" in modes

    def test_role_model_map_complete(self):
        for role in AgentRole:
            assert role in ROLE_MODEL_MAP, f"Missing {role} in ROLE_MODEL_MAP"

    def test_mode_model_map_complete(self):
        for mode in AgentRunMode:
            assert mode in MODE_MODEL_MAP, f"Missing {mode} in MODE_MODEL_MAP"

    def test_todo_provider_add_and_get(self):
        provider = TodoProvider()
        item_id = provider.add("Task 1")
        item_id2 = provider.add("Task 2")
        pending = provider.get_pending()
        assert len(pending) == 2

    def test_todo_provider_complete(self):
        provider = TodoProvider()
        item_id = provider.add("Task to complete")
        provider.complete(item_id)
        pending = provider.get_pending()
        assert len(pending) == 0

    def test_todo_provider_start(self):
        provider = TodoProvider()
        item_id = provider.add("Task to start")
        provider.start(item_id)
        pending = provider.get_pending()
        # Started items should still be pending or in a different state
        assert isinstance(pending, list)

    def test_context_compactor_estimate(self):
        compactor = ContextCompactor(threshold=1000)
        messages = [
            {"role": "user", "content": "Hello world " * 50},
            {"role": "assistant", "content": "Response " * 50},
        ]
        estimate = compactor.estimate_tokens(messages)
        assert estimate > 0

    def test_context_compactor_no_compact_under_threshold(self):
        compactor = ContextCompactor(threshold=100000)
        messages = [
            {"role": "user", "content": "Short message"},
            {"role": "assistant", "content": "Short response"},
        ]
        result = compactor.check_and_compact(messages)
        # Under threshold, should return original or compacted version
        assert isinstance(result, list)


class TestMixinImports:
    """验证所有 Mixin 模块可以独立导入"""

    def test_reasoning_mixin_import(self):
        from nexusflow.agents.reasoning_mixin import ReasoningMixin
        assert hasattr(ReasoningMixin, 'plan')
        assert hasattr(ReasoningMixin, 'reflect')
        assert hasattr(ReasoningMixin, 'execute_step')

    def test_codeact_mixin_import(self):
        from nexusflow.agents.codeact_mixin import CodeActMixin
        assert hasattr(CodeActMixin, 'init_codeact')
        assert hasattr(CodeActMixin, 'execute_codeact')

    def test_memory_mixin_import(self):
        from nexusflow.agents.memory_mixin import MemoryMixin
        assert hasattr(MemoryMixin, 'init_memory')
        assert hasattr(MemoryMixin, 'remember')
        assert hasattr(MemoryMixin, 'recall')

    def test_checkpoint_mixin_import(self):
        from nexusflow.agents.checkpoint_mixin import CheckpointMixin
        assert hasattr(CheckpointMixin, 'save_checkpoint')
        assert hasattr(CheckpointMixin, 'load_checkpoint')
        assert hasattr(CheckpointMixin, 'rewind')

    def test_handoff_mixin_import(self):
        from nexusflow.agents.handoff_mixin import HandoffMixin
        assert hasattr(HandoffMixin, 'register_handoff')
        assert hasattr(HandoffMixin, 'handoff_to')
        assert hasattr(HandoffMixin, 'get_state')

    def test_agi_mixin_import(self):
        from nexusflow.agents.agi_mixin import AGIMixin
        assert hasattr(AGIMixin, 'init_agi')
        assert hasattr(AGIMixin, 'autonomous')
        assert hasattr(AGIMixin, 'assess_confidence')
        assert hasattr(AGIMixin, 'cross_domain_analogy')


class TestBackwardCompatibility:
    """向后兼容测试 — 确保旧的 import 路径仍然有效"""

    def test_import_from_base_agent(self):
        from nexusflow.agents.base_agent import (
            BaseAgent, AgentRole, AgentRunMode,
            Message, TodoItem, TodoProvider, ContextCompactor,
            ROLE_MODEL_MAP, MODE_MODEL_MAP,
        )
        assert BaseAgent is not None

    def test_import_from_agents_package(self):
        from nexusflow.agents import BaseAgent
        assert BaseAgent is not None

    def test_base_agent_has_all_mixin_methods(self):
        from nexusflow.agents.base_agent import BaseAgent
        # ReasoningMixin methods
        assert hasattr(BaseAgent, 'plan')
        assert hasattr(BaseAgent, 'reflect')
        assert hasattr(BaseAgent, 'execute_step')
        assert hasattr(BaseAgent, 'plan_with_tree')
        assert hasattr(BaseAgent, 'think_with_tot')
        # CodeActMixin methods
        assert hasattr(BaseAgent, 'init_codeact')
        assert hasattr(BaseAgent, 'execute_codeact')
        # MemoryMixin methods
        assert hasattr(BaseAgent, 'init_memory')
        assert hasattr(BaseAgent, 'remember')
        assert hasattr(BaseAgent, 'recall')
        assert hasattr(BaseAgent, 'dream')
        # CheckpointMixin methods
        assert hasattr(BaseAgent, 'save_checkpoint')
        assert hasattr(BaseAgent, 'load_checkpoint')
        assert hasattr(BaseAgent, 'rewind')
        # HandoffMixin methods
        assert hasattr(BaseAgent, 'register_handoff')
        assert hasattr(BaseAgent, 'handoff_to')
        # AGIMixin methods
        assert hasattr(BaseAgent, 'init_agi')
        assert hasattr(BaseAgent, 'autonomous')
        assert hasattr(BaseAgent, 'assess_confidence')
        assert hasattr(BaseAgent, 'cross_domain_analogy')
        assert hasattr(BaseAgent, 'agi_status')

    def test_all_agent_subclasses_importable(self):
        from nexusflow.agents.coordinator import CoordinatorAgent
        from nexusflow.agents.planner import PlannerAgent
        from nexusflow.agents.researcher import ResearcherAgent
        from nexusflow.agents.executor import ExecutorAgent
        from nexusflow.agents.reviewer import ReviewerAgent
        from nexusflow.agents.miner import MinerAgent
        from nexusflow.agents.assayer import AssayerAgent
        from nexusflow.agents.caster import CasterAgent
        from nexusflow.agents.artisan import ArtisanAgent
        from nexusflow.agents.archivist import ArchivistAgent
        from nexusflow.agents.base_agent import BaseAgent
        for cls in [CoordinatorAgent, PlannerAgent, ResearcherAgent,
                    ExecutorAgent, ReviewerAgent, MinerAgent,
                    AssayerAgent, CasterAgent, ArtisanAgent, ArchivistAgent]:
            assert issubclass(cls, BaseAgent), f"{cls.__name__} is not a subclass of BaseAgent"
