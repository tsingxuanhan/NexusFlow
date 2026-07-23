# -*- coding: utf-8 -*-
"""集成测试 — 使用 mock LLM 验证端到端流程"""
import pytest
from unittest.mock import patch, MagicMock
import json

from nexusflow.agents.base_agent import BaseAgent, AgentRole, AgentRunMode, Message


class TestBaseAgentIntegration:
    """BaseAgent 端到端集成测试（mock LLM）"""

    def test_agent_creation_with_role(self):
        agent = BaseAgent(name="test_planner", role=AgentRole.PLANNER)
        assert agent.name == "test_planner"
        assert agent.agent_role == AgentRole.PLANNER

    def test_agent_plan_with_mock(self):
        agent = BaseAgent(name="test_planner", role=AgentRole.PLANNER)
        with patch.object(agent, '_chat_nonstream', return_value="## Plan\n1. Step one\n2. Step two\n3. Step three"):
            result = agent.plan("Analyze climate data")
        assert result is not None

    def test_agent_reflect_with_mock(self):
        agent = BaseAgent(name="test_reviewer", role=AgentRole.REVIEWER)
        agent.messages = [
            Message(role="user", content="Analyze this data"),
            Message(role="assistant", content="Here is the analysis..."),
        ]
        with patch.object(agent, '_chat_nonstream', return_value="## Reflection\nQuality: Good\nIssues: None"):
            result = agent.reflect("The analysis results")
        assert result is not None

    def test_agent_chat_with_mock(self):
        agent = BaseAgent(name="test_executor", role=AgentRole.EXECUTOR)
        with patch.object(agent, '_chat_nonstream', return_value="Task completed successfully."):
            result = agent.chat("Execute step 1")
        assert "Task completed" in result or result is not None

    def test_agent_set_mode(self):
        from nexusflow.agents.quality import AgentMode
        agent = BaseAgent(name="test_agent", role=AgentRole.RESEARCHER)
        agent.set_mode("creative")
        assert agent.agent_mode == AgentMode.CREATIVE
        agent.set_mode("balanced")
        assert agent.agent_mode == AgentMode.BALANCED

    def test_agent_get_stats(self):
        agent = BaseAgent(name="test_stats", role=AgentRole.PLANNER)
        stats = agent.get_stats()
        assert isinstance(stats, dict)

    def test_agent_reset(self):
        agent = BaseAgent(name="test_reset", role=AgentRole.EXECUTOR)
        agent.messages = [Message(role="user", content="hello")]
        agent.reset()
        assert len(agent.messages) == 0


class TestCDoLIntegration:
    """CDoL 认知分工集成测试"""

    def test_information_policy_all_roles(self):
        from nexusflow.core.agent_information_policy import AgentInformationPolicy
        policy = AgentInformationPolicy()
        # The policy supports the core 4 roles
        for role in ["planner", "researcher", "executor", "reviewer"]:
            profile = policy.get_profile(role)
            assert profile is not None
            assert profile.tier is not None

    def test_cognitive_division_engine_creation(self):
        from nexusflow.core.cognitive_division_engine import CognitiveDivisionEngine
        engine = CognitiveDivisionEngine()
        assert engine is not None

    def test_dynamic_router_task_routing(self):
        from nexusflow.core.dynamic_router import DynamicTopologyRouter, TaskRequirement
        router = DynamicTopologyRouter()
        task = TaskRequirement(
            task_id="test-001",
            description="Analyze global warming trends",
            required_capabilities=["research", "analysis"],
            required_domains=["climate"],
            execution_mode="cognitive_division",
        )
        topology = router.route(task)
        assert topology is not None
        assert topology.task_id == "test-001"
        assert topology.confidence >= 0


class TestAdaptiveContextManager:
    """自适应上下文管理测试"""

    def test_context_manager_creation(self):
        from nexusflow.core.adaptive_context_manager import AdaptiveContextManager
        mgr = AdaptiveContextManager(initial_window=4096, sync_interval=5)
        assert mgr is not None

    def test_context_manager_get_stats(self):
        from nexusflow.core.adaptive_context_manager import AdaptiveContextManager
        mgr = AdaptiveContextManager(initial_window=4096)
        stats = mgr.get_stats()
        assert isinstance(stats, dict)


class TestNexusOrchestrator:
    """NexusOrchestrator 集成测试"""

    def test_orchestrator_creation(self):
        from nexusflow.core.nexus_orchestrator import NexusOrchestrator
        orch = NexusOrchestrator()
        assert orch is not None

    def test_orchestrator_get_roster(self):
        from nexusflow.core.nexus_orchestrator import NexusOrchestrator
        orch = NexusOrchestrator()
        roster = orch.get_roster()
        assert roster is not None


class TestProtocolA2A:
    """A2A 协议测试"""

    def test_a2a_protocol_creation(self):
        from nexusflow.protocol.a2a_protocol import A2AProtocol
        a2a = A2AProtocol(agent_id="test-agent", agent_name="Test Agent")
        assert a2a.agent_id == "test-agent"

    def test_a2a_create_message(self):
        from nexusflow.protocol.a2a_protocol import A2AProtocol, A2AMessageType
        a2a = A2AProtocol(agent_id="agent-1", agent_name="Agent 1")
        msg = a2a.create_message(
            message_type=A2AMessageType.TASK_REQUEST,
            receiver_id="agent-2",
            content="Hello from agent 1",
        )
        assert msg is not None
        assert msg.sender_id == "agent-1"
        assert msg.receiver_id == "agent-2"


class TestQualityDials:
    """质量门禁集成"""

    def test_quality_dials_affect_params(self):
        from nexusflow.agents.quality import QualityDials
        dials = QualityDials(creativity=0.9, precision=0.3)
        params = dials.to_generation_params()
        assert params.get("temperature", 0) > 0.5

    def test_quality_dials_low_creativity(self):
        from nexusflow.agents.quality import QualityDials
        dials = QualityDials(creativity=0.1, precision=0.9)
        params = dials.to_generation_params()
        assert params.get("temperature", 1) < 0.5

    def test_quality_dials_defaults(self):
        from nexusflow.agents.quality import QualityDials
        dials = QualityDials()
        assert dials.creativity == 0.5
        assert dials.precision == 0.7
        assert dials.verbosity == 0.5
        assert dials.caution == 0.5

    def test_quality_dials_dict_roundtrip(self):
        from nexusflow.agents.quality import QualityDials
        dials = QualityDials(creativity=0.8, precision=0.6)
        d = dials.to_dict()
        dials2 = QualityDials.from_dict(d)
        assert dials2.creativity == 0.8
        assert dials2.precision == 0.6
