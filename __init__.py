# NexusFlow v2.9 — 面向超长程复杂任务的群体智能引擎
# 向后兼容层：所有模块已迁移至 nexusflow/ 子包
# 本文件保留裸导入兼容性，从新位置重导出所有公开API

# 核心引擎
from nexusflow.core.nexus_orchestrator import NexusOrchestrator, TaskResult, create_orchestrator
from nexusflow.core.dynamic_router import DynamicTopologyRouter, AgentCapabilityProfile, AgentLoadState
from nexusflow.core.cognitive_division_engine import CognitiveDivisionEngine, CDoLResult
from nexusflow.core.adaptive_context_manager import (
    AdaptiveContextManager, GlobalMemoryPool, LazinessDetector,
)
from nexusflow.core.agent_information_policy import (
    AgentInformationPolicy, AgentTier, InfoSliceType,
    InformationProfile, get_information_policy, recommend_cdol_config,
)
from nexusflow.core.edge_cloud_scheduler import EdgeCloudScheduler
from nexusflow.core.goal_verifier import GoalVerifier
from nexusflow.core.skill_retriever import SkillRetriever

# Agent 基础设施
from nexusflow.agents.base_agent import BaseAgent
from nexusflow.agents.checkpoint import CheckpointManager
from nexusflow.agents.checkpoint_writer import CheckpointWriter
from nexusflow.agents.circuit_breaker import CircuitBreakerConfig
from nexusflow.agents.handoff import HandoffManager
from nexusflow.agents.guardrails import GuardrailManager, create_default_guardrails, AntiPatternOutputGuard
from nexusflow.agents.observability import AgentTracer, MetricsCollector
from nexusflow.agents.quality import QualityDials, AgentMode, ReviewPipeline, create_default_pipeline

# 记忆系统
from nexusflow.memory.memory_manager import MemoryManager, create_memory_manager
from nexusflow.memory.core_memory import CoreMemory
from nexusflow.memory.archival_memory import ArchivalMemory
from nexusflow.memory.recall_memory import RecallMemory
from nexusflow.memory.vector_memory import VectorMemory, EnhancedVectorMemory, StructuredSlotMemory
from nexusflow.memory.sleeptime import SleeptimeEngine
from nexusflow.memory.multi_hop_rag import MultiHopRAG

# 认知能力
from nexusflow.cognition.autonomous import AutonomousGoalHandler
from nexusflow.cognition.meta_cognition import MetaCognition
from nexusflow.cognition.cross_domain import CrossDomainTransfer
from nexusflow.cognition.continuous_learning import ContinuousLearningPipeline
from nexusflow.cognition.reflection import ReflectionLoop
from nexusflow.cognition.task_tree import TaskTree, TaskNode, TaskScheduler
from nexusflow.cognition.tot import TreeOfThought, GraphOfThought

# 协议层
from nexusflow.protocol.a2a_protocol import A2AProtocol, A2ANetwork, P2PChannel
from nexusflow.protocol.a2a_gateway import A2AGateway
from nexusflow.protocol.mcp_client import MCPClient
from nexusflow.protocol.mcp_client_v2 import MCPClientV2
from nexusflow.protocol.mcp_server import XuanshuMCPServer

# 工具
from tools.base_tool import BaseTool, ToolManager

__version__ = "2.9.0"

__all__ = [
    # 核心引擎
    "NexusOrchestrator", "TaskResult", "create_orchestrator",
    "DynamicTopologyRouter", "AgentCapabilityProfile", "AgentLoadState",
    "CognitiveDivisionEngine", "CDoLResult",
    "AdaptiveContextManager", "GlobalMemoryPool", "LazinessDetector",
    "AgentInformationPolicy", "AgentTier", "InfoSliceType",
    "InformationProfile", "get_information_policy", "recommend_cdol_config",
    "EdgeCloudScheduler", "GoalVerifier", "SkillRetriever",
    # Agent 基础设施
    "BaseAgent", "CheckpointManager", "CheckpointWriter",
    "CircuitBreakerConfig", "HandoffManager",
    "GuardrailManager", "create_default_guardrails", "AntiPatternOutputGuard",
    "QualityDials", "AgentMode", "ReviewPipeline", "create_default_pipeline",
    "AgentTracer", "MetricsCollector",
    # 记忆系统
    "MemoryManager", "create_memory_manager", "CoreMemory",
    "ArchivalMemory", "RecallMemory", "VectorMemory",
    "EnhancedVectorMemory", "StructuredSlotMemory",
    "SleeptimeEngine", "MultiHopRAG",
    # 认知能力
    "AutonomousGoalHandler", "MetaCognition", "CrossDomainTransfer",
    "ContinuousLearningPipeline", "ReflectionLoop",
    "TaskTree", "TaskNode", "TaskScheduler",
    "TreeOfThought", "GraphOfThought",
    # 协议层
    "A2AProtocol", "A2ANetwork", "P2PChannel", "A2AGateway",
    "MCPClient", "MCPClientV2", "XuanshuMCPServer",
    # 工具
    "BaseTool", "ToolManager",
]
