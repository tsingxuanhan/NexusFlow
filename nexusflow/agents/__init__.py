# -*- coding: utf-8 -*-
"""
NexusFlow Agent Package
基础设施 + 角色Agent + 团队创建
"""

# === 基础设施 ===
from .base_agent import BaseAgent
from .checkpoint import CheckpointManager
from .checkpoint_writer import CheckpointWriter
from .circuit_breaker import CircuitBreakerConfig
from .handoff import HandoffManager
from .guardrails import GuardrailManager, create_default_guardrails, AntiPatternOutputGuard
from .observability import AgentTracer, MetricsCollector
from .quality import QualityDials, AgentMode, ReviewPipeline, create_default_pipeline

# === v4.0 泛化角色 ===
from .planner import PlannerAgent
from .researcher import ResearcherAgent
from .executor import ExecutorAgent
from .reviewer import ReviewerAgent

# === v3.3 旧角色（向后兼容） ===
from .miner import MinerAgent
from .assayer import AssayerAgent
from .caster import CasterAgent
from .artisan import ArtisanAgent

# === AgentRegistry ===
from .agent_registry import ModelTier, RunLayer, AgentSpec, get_model_for_agent, get_agents_by_layer, get_agents_by_model_tier, get_agent_by_capability, get_full_roster

# === Phase 6: 编排者 + 档案师 ===
from .coordinator import CoordinatorAgent
from .archivist import ArchivistAgent


__all__ = [
    # 基础设施
    "BaseAgent", "CheckpointManager", "CheckpointWriter", "CircuitBreakerConfig",
    "HandoffManager", "GuardrailManager", "create_default_guardrails", "AntiPatternOutputGuard",
    "AgentTracer", "MetricsCollector",
    "QualityDials", "AgentMode", "ReviewPipeline", "create_default_pipeline",
    # v4.0 泛化角色
    "PlannerAgent", "ResearcherAgent", "ExecutorAgent", "ReviewerAgent",
    # v3.3 旧角色
    "MinerAgent", "AssayerAgent", "CasterAgent", "ArtisanAgent",
    # AgentRegistry
    "ModelTier", "RunLayer", "AgentSpec",
    "get_model_for_agent", "get_agents_by_layer", "get_agents_by_model_tier",
    "get_agent_by_capability", "get_full_roster",
    # Phase 6
    "CoordinatorAgent", "ArchivistAgent",
]
