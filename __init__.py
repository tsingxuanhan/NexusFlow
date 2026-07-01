# xuanshu-agents v4.0
from base_agent import BaseAgent
from a2a_protocol import A2AProtocol, A2ANetwork, P2PChannel
from vector_memory import VectorMemory, EnhancedVectorMemory, StructuredSlotMemory
from guardrails import GuardrailManager, create_default_guardrails, AntiPatternOutputGuard
from quality import QualityDials, AgentMode, ReviewPipeline, create_default_pipeline
from checkpoint import CheckpointManager
from handoff import HandoffManager
from circuit_breaker import CircuitBreakerConfig
from observability import AgentTracer, MetricsCollector
from mcp_client import MCPClient
from tools.base_tool import BaseTool, ToolManager

# Phase 7: CDoL + 自适应上下文 + 信息策略 + 编排器
from agent_information_policy import (
    AgentInformationPolicy, AgentTier, InfoSliceType,
    InformationProfile, get_information_policy, recommend_cdol_config,
)
from cognitive_division_engine import CognitiveDivisionEngine, CDoLResult
from adaptive_context_manager import (
    AdaptiveContextManager, GlobalMemoryPool, LazinessDetector,
)
from nexus_orchestrator import NexusOrchestrator, TaskResult, create_orchestrator

__version__ = "4.0.0"

__all__ = [
    # 基础
    "BaseAgent", "A2AProtocol", "A2ANetwork", "P2PChannel",
    "VectorMemory", "EnhancedVectorMemory", "StructuredSlotMemory",
    "GuardrailManager", "create_default_guardrails", "AntiPatternOutputGuard",
    "QualityDials", "AgentMode", "ReviewPipeline", "create_default_pipeline",
    "CheckpointManager", "HandoffManager", "CircuitBreakerConfig",
    "AgentTracer", "MetricsCollector", "MCPClient",
    "BaseTool", "ToolManager",
    # Phase 7: CDoL + 信息策略 + 编排器
    "AgentInformationPolicy", "AgentTier", "InfoSliceType",
    "InformationProfile", "get_information_policy", "recommend_cdol_config",
    "CognitiveDivisionEngine", "CDoLResult",
    "AdaptiveContextManager", "GlobalMemoryPool", "LazinessDetector",
    "NexusOrchestrator", "TaskResult", "create_orchestrator",
]
