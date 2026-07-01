# -*- coding: utf-8 -*-
"""
铉枢·炉守 v4.2 Integration — 统一初始化入口
XuanHub v4.2 Integration Module

v4.2 新增6个模块的统一初始化入口。
负责：
1. 按依赖顺序初始化所有新模块
2. 建立模块间的引用关系
3. 提供统一的初始化钩子供 BaseAgent.init_agi() 调用
4. 支持懒加载和可选初始化

初始化顺序（按依赖关系）：
1. KnowledgeLibrary (无依赖)
2. HypothesisEngine (依赖 KnowledgeLibrary)
3. SelfHealingLoop (依赖 CheckpointWriter)
4. SuccinctCommunicationManager (依赖 Knowledge + Hypothesis)
5. DiscoveryExploitation (依赖 Hypothesis + Knowledge + Agents)
6. StructuredPatternMemory (依赖 KnowledgeLibrary)

使用方式：
    from v4.2_integration import V42Initializer

    initializer = V42Initializer(
        vector_memory=agent._memory,
        checkpoint_writer=agent._checkpoint_writer,
    )
    modules = initializer.initialize_all()
    # modules = {
    #     "knowledge_library": KnowledgeLibrary,
    #     "hypothesis_engine": HypothesisEngine,
    #     "self_healing": SelfHealingLoop,
    #     "succinct_comm": SuccinctCommunicationManager,
    #     "discovery_exploitation": DiscoveryExploitation,
    #     "pattern_memory": StructuredPatternMemory,
    # }
"""

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, Optional

logger = logging.getLogger("V42Integration")

# Import all v4.2 modules
from knowledge_library import KnowledgeLibrary, DomainScope
from hypothesis_engine import HypothesisEngine
from self_healing import SelfHealingLoop
from succinct_comm import SuccinctCommunicationManager
from discovery_exploitation import DiscoveryExploitation
from structured_pattern_memory import StructuredPatternMemory


# ============================================================================
# Configuration
# ============================================================================

@dataclass
class V42Config:
    """Configuration for v4.2 module initialization"""

    # Storage directories (relative to project root)
    knowledge_library_dir: str = "./knowledge_library"
    hypothesis_engine_dir: str = "./hypotheses"
    pattern_memory_dir: str = "./pattern_memory"

    # Self-Healing config
    healing_max_retries: int = 5

    # Succinct Communication config
    comm_token_budget: int = 500

    # Discovery Exploitation budget
    exploitation_max_attempts_per_discovery: int = 5
    exploitation_max_total_attempts: int = 20
    exploitation_max_token_budget: int = 5_000_000

    # Module toggle (set False to skip initialization)
    enable_knowledge_library: bool = True
    enable_hypothesis_engine: bool = True
    enable_self_healing: bool = True
    enable_succinct_comm: bool = True
    enable_discovery_exploitation: bool = True
    enable_pattern_memory: bool = True


# ============================================================================
# V42Initializer
# ============================================================================

class V42Initializer:
    """
    Unified initialization entry point for all v4.2 modules.

    Handles:
    1. Dependency-ordered initialization
    2. Cross-module reference wiring
    3. Agent function registration for DiscoveryExploitation
    4. Graceful degradation if a module fails to initialize

    Usage in BaseAgent.init_agi():
        from v4.2_integration import V42Initializer, V42Config

        config = V42Config(
            knowledge_library_dir="./knowledge_library",
            healing_max_retries=5,
        )
        initializer = V42Initializer(
            vector_memory=self._memory,
            checkpoint_writer=self._checkpoint_writer,
            config=config,
        )
        self._v42_modules = initializer.initialize_all()
        self._knowledge_lib = self._v42_modules.get("knowledge_library")
        self._hypothesis_engine = self._v42_modules.get("hypothesis_engine")
        # ... etc
    """

    def __init__(
        self,
        vector_memory: Any = None,
        checkpoint_writer: Any = None,
        config: Optional[V42Config] = None,
    ):
        self.vector_memory = vector_memory
        self.checkpoint_writer = checkpoint_writer
        self.config = config or V42Config()

        self._modules: Dict[str, Any] = {}
        self._init_errors: Dict[str, str] = {}

    # ============ Public API ============

    def initialize_all(self) -> Dict[str, Any]:
        """
        Initialize all enabled v4.2 modules in dependency order.

        Returns:
            Dict mapping module names to initialized instances.
            Modules that failed to initialize are omitted.
        """
        logger.info("[V42Integration] Starting v4.2 module initialization...")

        # Phase 1: Knowledge Library (no dependencies)
        if self.config.enable_knowledge_library:
            self._init_knowledge_library()

        # Phase 2: Hypothesis Engine (depends on Knowledge Library)
        if self.config.enable_hypothesis_engine:
            self._init_hypothesis_engine()

        # Phase 3: Self-Healing Loop (depends on CheckpointWriter)
        if self.config.enable_self_healing:
            self._init_self_healing()

        # Phase 4: Succinct Communication (depends on Knowledge + Hypothesis)
        if self.config.enable_succinct_comm:
            self._init_succinct_comm()

        # Phase 5: Discovery Exploitation (depends on Hypothesis + Knowledge)
        if self.config.enable_discovery_exploitation:
            self._init_discovery_exploitation()

        # Phase 6: Pattern Memory (depends on Knowledge Library)
        if self.config.enable_pattern_memory:
            self._init_pattern_memory()

        # Summary
        initialized = list(self._modules.keys())
        errors = dict(self._init_errors)
        logger.info(
            f"[V42Integration] Initialization complete: "
            f"{len(initialized)} modules initialized, {len(errors)} errors"
        )
        if errors:
            logger.warning(f"[V42Integration] Init errors: {errors}")

        return self._modules

    def initialize_single(self, module_name: str) -> Any:
        """Initialize a single module by name (for lazy loading)."""
        init_methods = {
            "knowledge_library": self._init_knowledge_library,
            "hypothesis_engine": self._init_hypothesis_engine,
            "self_healing": self._init_self_healing,
            "succinct_comm": self._init_succinct_comm,
            "discovery_exploitation": self._init_discovery_exploitation,
            "pattern_memory": self._init_pattern_memory,
        }

        method = init_methods.get(module_name)
        if method:
            method()
            return self._modules.get(module_name)
        else:
            raise ValueError(f"Unknown module: {module_name}")

    def register_agent_functions(
        self,
        architect_fn: Callable = None,
        miner_fn: Callable = None,
        assayer_fn: Callable = None,
    ) -> None:
        """
        Register agent execution functions for DiscoveryExploitation.
        Call this after agents are initialized.
        """
        exploitation = self._modules.get("discovery_exploitation")
        if exploitation:
            exploitation.set_agent_functions(
                architect_fn=architect_fn,
                miner_fn=miner_fn,
                assayer_fn=assayer_fn,
            )
            logger.info("[V42Integration] Agent functions registered for DiscoveryExploitation")

    def get_module(self, name: str) -> Any:
        """Get an initialized module by name."""
        return self._modules.get(name)

    def get_all_modules(self) -> Dict[str, Any]:
        """Get all initialized modules."""
        return self._modules.copy()

    def get_init_status(self) -> Dict:
        """Get initialization status summary."""
        return {
            "initialized": list(self._modules.keys()),
            "errors": dict(self._init_errors),
            "total_initialized": len(self._modules),
            "total_errors": len(self._init_errors),
        }

    # ============ Private Init Methods ============

    def _init_knowledge_library(self) -> None:
        """Phase 1: Initialize KnowledgeLibrary"""
        try:
            module = KnowledgeLibrary(
                storage_dir=self.config.knowledge_library_dir,
                vector_memory=self.vector_memory,
            )
            self._modules["knowledge_library"] = module
            logger.info("[V42Integration] ✓ KnowledgeLibrary initialized")
        except Exception as e:
            self._init_errors["knowledge_library"] = str(e)
            logger.error(f"[V42Integration] ✗ KnowledgeLibrary failed: {e}")

    def _init_hypothesis_engine(self) -> None:
        """Phase 2: Initialize HypothesisEngine"""
        try:
            knowledge_lib = self._modules.get("knowledge_library")
            module = HypothesisEngine(
                storage_dir=self.config.hypothesis_engine_dir,
                knowledge_library=knowledge_lib,
            )
            self._modules["hypothesis_engine"] = module
            logger.info("[V42Integration] ✓ HypothesisEngine initialized")
        except Exception as e:
            self._init_errors["hypothesis_engine"] = str(e)
            logger.error(f"[V42Integration] ✗ HypothesisEngine failed: {e}")

    def _init_self_healing(self) -> None:
        """Phase 3: Initialize SelfHealingLoop"""
        try:
            module = SelfHealingLoop(
                max_retries=self.config.healing_max_retries,
                checkpoint_writer=self.checkpoint_writer,
            )
            self._modules["self_healing"] = module
            logger.info("[V42Integration] ✓ SelfHealingLoop initialized")
        except Exception as e:
            self._init_errors["self_healing"] = str(e)
            logger.error(f"[V42Integration] ✗ SelfHealingLoop failed: {e}")

    def _init_succinct_comm(self) -> None:
        """Phase 4: Initialize SuccinctCommunicationManager"""
        try:
            module = SuccinctCommunicationManager(
                knowledge_library=self._modules.get("knowledge_library"),
                hypothesis_engine=self._modules.get("hypothesis_engine"),
                token_budget=self.config.comm_token_budget,
            )
            self._modules["succinct_comm"] = module
            logger.info("[V42Integration] ✓ SuccinctCommunicationManager initialized")
        except Exception as e:
            self._init_errors["succinct_comm"] = str(e)
            logger.error(f"[V42Integration] ✗ SuccinctCommunicationManager failed: {e}")

    def _init_discovery_exploitation(self) -> None:
        """Phase 5: Initialize DiscoveryExploitation"""
        try:
            module = DiscoveryExploitation(
                hypothesis_engine=self._modules.get("hypothesis_engine"),
                knowledge_library=self._modules.get("knowledge_library"),
                budget_config={
                    "max_attempts_per_discovery": self.config.exploitation_max_attempts_per_discovery,
                    "max_total_attempts": self.config.exploitation_max_total_attempts,
                    "max_token_budget": self.config.exploitation_max_token_budget,
                },
            )
            self._modules["discovery_exploitation"] = module
            logger.info("[V42Integration] ✓ DiscoveryExploitation initialized")
        except Exception as e:
            self._init_errors["discovery_exploitation"] = str(e)
            logger.error(f"[V42Integration] ✗ DiscoveryExploitation failed: {e}")

    def _init_pattern_memory(self) -> None:
        """Phase 6: Initialize StructuredPatternMemory"""
        try:
            module = StructuredPatternMemory(
                storage_dir=self.config.pattern_memory_dir,
            )
            self._modules["pattern_memory"] = module
            logger.info("[V42Integration] ✓ StructuredPatternMemory initialized")
        except Exception as e:
            self._init_errors["pattern_memory"] = str(e)
            logger.error(f"[V42Integration] ✗ StructuredPatternMemory failed: {e}")


# ============================================================================
# Convenience Functions
# ============================================================================

def create_v42_modules(
    vector_memory: Any = None,
    checkpoint_writer: Any = None,
    config: Optional[V42Config] = None,
) -> Dict[str, Any]:
    """
    Convenience function to create all v4.2 modules in one call.

    Usage:
        from v4.2_integration import create_v42_modules

        modules = create_v42_modules(
            vector_memory=agent._memory,
            checkpoint_writer=agent._checkpoint_writer,
        )
    """
    initializer = V42Initializer(
        vector_memory=vector_memory,
        checkpoint_writer=checkpoint_writer,
        config=config,
    )
    return initializer.initialize_all()


def get_v42_stats(modules: Dict[str, Any]) -> Dict:
    """
    Get combined stats from all v4.2 modules.

    Usage:
        stats = get_v42_stats(modules)
        print(stats)
    """
    stats = {}

    kl = modules.get("knowledge_library")
    if kl:
        stats["knowledge_library"] = kl.get_stats()

    he = modules.get("hypothesis_engine")
    if he:
        stats["hypothesis_engine"] = he.get_stats()

    sh = modules.get("self_healing")
    if sh:
        stats["self_healing"] = sh.get_stats()

    sc = modules.get("succinct_comm")
    if sc:
        stats["succinct_comm"] = sc.get_stats()

    de = modules.get("discovery_exploitation")
    if de:
        stats["discovery_exploitation"] = de.get_stats()

    pm = modules.get("pattern_memory")
    if pm:
        stats["pattern_memory"] = pm.get_stats()

    return stats
