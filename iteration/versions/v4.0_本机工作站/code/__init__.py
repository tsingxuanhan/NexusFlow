# xuanshu-agents v3.3
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
__version__ = "3.3.0"
