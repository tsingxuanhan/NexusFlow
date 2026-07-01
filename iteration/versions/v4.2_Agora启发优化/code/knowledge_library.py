# -*- coding: utf-8 -*-
"""
铉枢·炉守 Knowledge Library — 领域知识库
XuanHub Knowledge Library v4.2

基于 Agora (ICML 2026) Knowledge Library 设计，适配 AI4Science 场景。
为 Agent 提供结构化的领域知识注入系统：Scientific Invariants + Experiment Patterns + Domain Constraints。

核心功能：
1. 统一领域知识访问接口，所有 Agent 角色均可查询
2. 知识按领域/类型结构化存储，支持增量更新
3. 与现有 NGram+RRF 向量记忆系统兼容共存（不替换）
4. 在 Agent 任务执行前自动注入相关约束（DomainConstraintPack）
5. 支持 Dream/Distill 周期同步提取的模式

知识类型（5种）：
- INVARIANT: 领域不变性（守恒定律、热力学约束）
- EXPERIMENT_PATTERN: 实验模式（成功/失败实验模式）
- CONSTRAINT: 实验约束（设备极限、安全边界）
- FAILURE_MODE: 已知失败模式及其特征
- SUCCESS_PATH: 验证过的成功研究路径
- METHOD_TEMPLATE: 抽象方法模板（非具体代码）

领域范围（6级）：
- GLOBAL / GENERAL / DOMAIN / SUBDOMAIN / SPECIFIC / TASK
"""

import json
import logging
import re
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

logger = logging.getLogger("KnowledgeLibrary")


# ============================================================================
# 枚举定义
# ============================================================================

class KnowledgeType(Enum):
    """Knowledge entry types adapted for AI4Science"""
    INVARIANT = "invariant"
    EXPERIMENT_PATTERN = "exp_pattern"
    CONSTRAINT = "constraint"
    FAILURE_MODE = "failure_mode"
    SUCCESS_PATH = "success_path"
    METHOD_TEMPLATE = "method_template"


class DomainScope(Enum):
    """Domain scope for knowledge entries — 6-level hierarchy"""
    GLOBAL = "global"
    GENERAL = "general_science"
    DOMAIN = "domain"
    SUBDOMAIN = "subdomain"
    SPECIFIC = "specific"
    TASK = "task"

    # Legacy aliases for backward compat with specific science domains
    MATERIALS_SCIENCE = "materials_science"
    CEMENT_CHEMISTRY = "cement_chemistry"
    SSC = "ssc"
    MBCMS = "mbcms"
    LC3 = "lc3"
    NANO_CONCRETE = "nano_concrete"
    DURABILITY = "durability"
    CROSS_DOMAIN = "cross_domain"


# ============================================================================
# 核心数据结构
# ============================================================================

@dataclass
class KnowledgeEntry:
    """
    A single knowledge entry in the library.

    Analogous to Agora's Bug Pattern, but for scientific domains:
    - Invariant: "Conservation of mass must hold in all cement hydration reactions"
    - Experiment Pattern: "When SSC curing temp > 60°C, early strength drops 30%"
    - Constraint: "MBCMs MgO/PH ratio must stay within [2, 6] for structural integrity"
    """
    entry_id: str
    knowledge_type: KnowledgeType
    domain: DomainScope

    # Core content
    title: str
    description: str
    conditions: List[str]
    implications: List[str]
    evidence_sources: List[str]

    # Metadata
    confidence: float = 0.8
    usage_count: int = 0
    last_referenced: str = ""
    tags: List[str] = field(default_factory=list)
    related_entries: List[str] = field(default_factory=list)

    # Lifecycle
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat())
    version: int = 1
    validated: bool = False

    def to_dict(self) -> Dict:
        """Serialize to dictionary"""
        return {
            "entry_id": self.entry_id,
            "knowledge_type": self.knowledge_type.value,
            "domain": self.domain.value,
            "title": self.title,
            "description": self.description,
            "conditions": self.conditions,
            "implications": self.implications,
            "evidence_sources": self.evidence_sources,
            "confidence": self.confidence,
            "usage_count": self.usage_count,
            "last_referenced": self.last_referenced,
            "tags": self.tags,
            "related_entries": self.related_entries,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "version": self.version,
            "validated": self.validated,
        }

    @classmethod
    def from_dict(cls, data: Dict) -> "KnowledgeEntry":
        """Deserialize from dictionary"""
        return cls(
            entry_id=data["entry_id"],
            knowledge_type=KnowledgeType(data["knowledge_type"]),
            domain=DomainScope(data["domain"]),
            title=data["title"],
            description=data["description"],
            conditions=data.get("conditions", []),
            implications=data.get("implications", []),
            evidence_sources=data.get("evidence_sources", []),
            confidence=data.get("confidence", 0.8),
            usage_count=data.get("usage_count", 0),
            last_referenced=data.get("last_referenced", ""),
            tags=data.get("tags", []),
            related_entries=data.get("related_entries", []),
            created_at=data.get("created_at", datetime.now().isoformat()),
            updated_at=data.get("updated_at", datetime.now().isoformat()),
            version=data.get("version", 1),
            validated=data.get("validated", False),
        )


@dataclass
class KnowledgeQuery:
    """Query parameters for knowledge retrieval"""
    domain: Optional[DomainScope] = None
    knowledge_types: List[KnowledgeType] = field(default_factory=list)
    tags: List[str] = field(default_factory=list)
    min_confidence: float = 0.5
    validated_only: bool = False
    max_results: int = 20
    search_text: str = ""


@dataclass
class DomainConstraintPack:
    """
    A packaged set of constraints injected into agent's system prompt.
    Analogous to Agora's CFT/BFT constraint injection.
    """
    domain: DomainScope
    invariants: List[KnowledgeEntry] = field(default_factory=list)
    patterns: List[KnowledgeEntry] = field(default_factory=list)
    constraints: List[KnowledgeEntry] = field(default_factory=list)
    failure_modes: List[KnowledgeEntry] = field(default_factory=list)

    def to_prompt_section(self) -> str:
        """Format as injectable prompt section"""
        sections = []

        if self.invariants:
            inv_text = "\n".join(
                f"  - [{e.entry_id}] {e.title}: {e.description}" for e in self.invariants
            )
            sections.append(f"## 领域不变性约束\n{inv_text}")

        if self.patterns:
            pat_text = "\n".join(
                f"  - [{e.entry_id}] {e.title}: 条件={'; '.join(e.conditions)} → {e.description}"
                for e in self.patterns
            )
            sections.append(f"## 已知实验模式\n{pat_text}")

        if self.constraints:
            con_text = "\n".join(
                f"  - [{e.entry_id}] {e.title}: {e.description}" for e in self.constraints
            )
            sections.append(f"## 实验约束\n{con_text}")

        if self.failure_modes:
            fail_text = "\n".join(
                f"  - [{e.entry_id}] {e.title}: {e.description}\n    条件: {'; '.join(e.conditions)}"
                for e in self.failure_modes
            )
            sections.append(f"## 已知失败模式\n{fail_text}")

        if not sections:
            return ""

        header = f"## 领域知识库注入 [{self.domain.value}]\n"
        header += "以下知识来自领域知识库，请在推理中参考这些约束，但不要机械复制。\n\n"
        return header + "\n\n".join(sections)


# ============================================================================
# KnowledgeLibrary 主类
# ============================================================================

class KnowledgeLibrary:
    """
    Domain Knowledge Library for AI4Science.

    Core responsibilities:
    1. Store and retrieve structured domain knowledge
    2. Generate constraint packs for agent prompt injection
    3. Track knowledge usage and update confidence
    4. Integrate with NGram+RRF vector memory for hybrid retrieval

    Integration with existing system:
    - Queried by Dispatcher before task assignment
    - Injected into Agent system prompts via DomainConstraintPack
    - Updated by GoalVerifier when discoveries are confirmed
    - Queried by Miner/Assayer/Architect during reasoning
    """

    def __init__(
        self,
        storage_dir: str = "./knowledge_library",
        vector_memory: Any = None,
    ):
        self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(parents=True, exist_ok=True)

        # In-memory index
        self._entries: Dict[str, KnowledgeEntry] = {}
        self._domain_index: Dict[DomainScope, Set[str]] = {d: set() for d in DomainScope}
        self._type_index: Dict[KnowledgeType, Set[str]] = {t: set() for t in KnowledgeType}

        # Reference to existing vector memory for hybrid retrieval
        self._vector_memory = vector_memory

        # Persistence file
        self._data_file = self.storage_dir / "knowledge_entries.json"

        # Stats
        self._stats: Dict[str, Any] = {
            "total_entries": 0,
            "total_queries": 0,
            "total_injections": 0,
            "entries_by_type": {},
            "entries_by_domain": {},
        }

        # Load existing data
        self._load_from_disk()
        logger.info(f"[KnowledgeLibrary] Initialized with {len(self._entries)} entries")

    # ============ Core API ============

    def add_entry(self, entry: KnowledgeEntry) -> str:
        """Add a new knowledge entry to the library."""
        self._entries[entry.entry_id] = entry
        self._domain_index[entry.domain].add(entry.entry_id)
        self._type_index[entry.knowledge_type].add(entry.entry_id)
        self._persist()
        self._update_stats()
        return entry.entry_id

    def query(self, query: KnowledgeQuery) -> List[KnowledgeEntry]:
        """
        Query the knowledge library.

        Retrieval strategy (hybrid):
        1. Filter by domain/type/tags/confidence (structured filtering)
        2. If search_text provided, also search vector memory (semantic)
        3. Merge results, deduplicate, sort by relevance
        """
        self._stats["total_queries"] += 1
        results: List[KnowledgeEntry] = []

        # Step 1: Structured filtering
        candidates = self._structured_filter(query)

        # Step 2: Semantic search (if applicable)
        if query.search_text and self._vector_memory:
            semantic_results = self._semantic_search(query.search_text, query.max_results)
            candidates = self._merge_results(candidates, semantic_results)

        # Step 3: Sort by relevance (confidence * usage_weight)
        results = sorted(
            candidates,
            key=lambda e: e.confidence * (1 + 0.1 * min(e.usage_count, 10)),
            reverse=True,
        )

        return results[:query.max_results]

    def get_constraint_pack(
        self,
        domain: DomainScope,
        task_context: str = "",
        agent_role: str = "",
    ) -> DomainConstraintPack:
        """
        Generate a constraint pack for injection into agent's system prompt.

        Called by Dispatcher before task assignment, or by agents during reasoning.

        Args:
            domain: Target domain scope
            task_context: Brief description of the task (for relevance filtering)
            agent_role: "miner" / "assayer" / "caster" / "artisan"

        Returns:
            DomainConstraintPack with relevant knowledge entries
        """
        self._stats["total_injections"] += 1
        pack = DomainConstraintPack(domain=domain)

        # Always include invariants (they're fundamental)
        query = KnowledgeQuery(
            domain=domain,
            knowledge_types=[KnowledgeType.INVARIANT],
            min_confidence=0.6,
            max_results=10,
        )
        pack.invariants = self.query(query)

        # Role-specific knowledge injection
        if agent_role == "miner":
            for kt in [KnowledgeType.EXPERIMENT_PATTERN, KnowledgeType.SUCCESS_PATH, KnowledgeType.METHOD_TEMPLATE]:
                q = KnowledgeQuery(domain=domain, knowledge_types=[kt], max_results=5)
                pack.patterns.extend(self.query(q))

        elif agent_role == "assayer":
            for kt in [KnowledgeType.FAILURE_MODE, KnowledgeType.CONSTRAINT]:
                q = KnowledgeQuery(domain=domain, knowledge_types=[kt], max_results=5)
                pack.failure_modes.extend(self.query(q))

        elif agent_role in ("caster", "artisan"):
            q = KnowledgeQuery(domain=domain, knowledge_types=[KnowledgeType.CONSTRAINT], max_results=5)
            pack.constraints = self.query(q)

        # If task_context provided, boost relevance
        if task_context:
            pack = self._boost_relevance(pack, task_context)

        return pack

    def record_usage(self, entry_id: str, was_helpful: bool = True) -> None:
        """Record that a knowledge entry was used by an agent."""
        if entry_id not in self._entries:
            return

        entry = self._entries[entry_id]
        entry.usage_count += 1
        entry.last_referenced = datetime.now().isoformat()

        if was_helpful:
            entry.confidence = min(1.0, entry.confidence + 0.01)
        else:
            entry.confidence = max(0.1, entry.confidence - 0.05)

        self._persist()

    def validate_entry(self, entry_id: str, validated_by: str = "") -> None:
        """Mark a knowledge entry as validated by agent execution."""
        if entry_id in self._entries:
            self._entries[entry_id].validated = True
            self._entries[entry_id].confidence = min(
                1.0, self._entries[entry_id].confidence + 0.1
            )
            self._persist()

    def add_from_discovery(self, discovery_description: str, domain: DomainScope, source_agent: str) -> str:
        """
        Add a knowledge entry from an agent's discovery.
        Called by Discovery Exploitation module after root cause analysis.
        """
        entry_id = f"disc_{int(datetime.now().timestamp())}_{source_agent}"
        entry = KnowledgeEntry(
            entry_id=entry_id,
            knowledge_type=KnowledgeType.SUCCESS_PATH,
            domain=domain,
            title=f"Discovery by {source_agent}",
            description=discovery_description,
            conditions=[],
            implications=[],
            evidence_sources=[f"Agent: {source_agent}"],
            confidence=0.6,
            tags=["auto_discovered", source_agent],
        )
        return self.add_entry(entry)

    # ============ Integration with ContinuousLearning ============

    def sync_from_dream_cycle(self, patterns: List[Dict]) -> int:
        """
        Sync patterns extracted by DreamCycle into KnowledgeLibrary.
        Integration point: ContinuousLearningPipelineV41._deep_pattern_extraction()
        """
        added = 0
        for pattern in patterns:
            entry = KnowledgeEntry(
                entry_id=f"dream_{int(datetime.now().timestamp())}_{added}",
                knowledge_type=KnowledgeType.EXPERIMENT_PATTERN,
                domain=DomainScope.CROSS_DOMAIN,
                title=pattern.get("name", "Extracted Pattern"),
                description=pattern.get("description", ""),
                conditions=[],
                implications=[],
                evidence_sources=["Dream Cycle auto-extraction"],
                confidence=0.5,
                tags=["dream_extracted"],
            )
            self.add_entry(entry)
            added += 1
        return added

    def sync_from_distill(self, sops: List[Dict], rules: List[str]) -> int:
        """
        Sync SOPs and rules from Distill into KnowledgeLibrary.
        Integration point: ContinuousLearningPipelineV41.distill()
        """
        added = 0
        for rule in rules:
            entry = KnowledgeEntry(
                entry_id=f"distill_{int(datetime.now().timestamp())}_{added}",
                knowledge_type=KnowledgeType.CONSTRAINT,
                domain=DomainScope.CROSS_DOMAIN,
                title=f"Distilled Rule: {rule[:50]}",
                description=rule,
                conditions=[],
                implications=[],
                evidence_sources=["Distill auto-extraction"],
                confidence=0.7,
                tags=["distill_extracted"],
            )
            self.add_entry(entry)
            added += 1
        return added

    # ============ Internal Methods ============

    def _structured_filter(self, query: KnowledgeQuery) -> List[KnowledgeEntry]:
        """Filter entries by structured criteria"""
        results: List[KnowledgeEntry] = []

        if query.domain:
            candidate_ids = self._domain_index.get(query.domain, set())
        else:
            candidate_ids = set(self._entries.keys())

        if query.knowledge_types:
            type_ids: Set[str] = set()
            for kt in query.knowledge_types:
                type_ids |= self._type_index.get(kt, set())
            candidate_ids &= type_ids

        for entry_id in candidate_ids:
            entry = self._entries.get(entry_id)
            if not entry:
                continue
            if entry.confidence < query.min_confidence:
                continue
            if query.validated_only and not entry.validated:
                continue
            if query.tags and not any(t in entry.tags for t in query.tags):
                continue
            results.append(entry)

        return results

    def _semantic_search(self, text: str, max_results: int) -> List[KnowledgeEntry]:
        """Search using existing NGram+RRF vector memory"""
        if not self._vector_memory:
            return []

        try:
            search_results = self._vector_memory.hybrid_retrieve(
                query=text, top_k=max_results,
            )
            entries: List[KnowledgeEntry] = []
            for result in search_results:
                entry_id = getattr(result, 'entry_id', None)
                if entry_id is None and hasattr(result, 'metadata'):
                    entry_id = result.metadata.get('entry_id', '')
                if entry_id and entry_id in self._entries:
                    entries.append(self._entries[entry_id])
            return entries
        except Exception as e:
            logger.warning(f"[KnowledgeLibrary] Semantic search failed: {e}")
            return []

    def _merge_results(
        self,
        structured: List[KnowledgeEntry],
        semantic: List[KnowledgeEntry],
    ) -> List[KnowledgeEntry]:
        """Merge and deduplicate structured + semantic results"""
        seen_ids: Set[str] = set()
        merged: List[KnowledgeEntry] = []

        for entry in structured:
            if entry.entry_id not in seen_ids:
                seen_ids.add(entry.entry_id)
                merged.append(entry)

        for entry in semantic:
            if entry.entry_id not in seen_ids:
                seen_ids.add(entry.entry_id)
                merged.append(entry)

        return merged

    def _boost_relevance(self, pack: DomainConstraintPack, task_context: str) -> DomainConstraintPack:
        """Boost entries whose content is relevant to the task context (keyword overlap)."""
        context_words = set(task_context.lower().split())

        def relevance_score(entry: KnowledgeEntry) -> float:
            text = f"{entry.title} {entry.description} {' '.join(entry.tags)}".lower()
            overlap = len(context_words & set(text.split()))
            return overlap / max(1, len(context_words))

        pack.invariants.sort(key=relevance_score, reverse=True)
        pack.patterns.sort(key=relevance_score, reverse=True)
        pack.constraints.sort(key=relevance_score, reverse=True)
        pack.failure_modes.sort(key=relevance_score, reverse=True)

        return pack

    def _persist(self) -> None:
        """Persist entries to disk"""
        try:
            data = {eid: entry.to_dict() for eid, entry in self._entries.items()}
            with open(self._data_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"[KnowledgeLibrary] Persist failed: {e}")

    def _load_from_disk(self) -> None:
        """Load entries from disk"""
        if not self._data_file.exists():
            return

        try:
            with open(self._data_file, 'r', encoding='utf-8') as f:
                data = json.load(f)

            for eid, entry_data in data.items():
                entry = KnowledgeEntry.from_dict(entry_data)
                self._entries[eid] = entry
                self._domain_index[entry.domain].add(eid)
                self._type_index[entry.knowledge_type].add(eid)

            self._update_stats()
        except Exception as e:
            logger.error(f"[KnowledgeLibrary] Load failed: {e}")

    def _update_stats(self) -> None:
        """Update statistics"""
        self._stats["total_entries"] = len(self._entries)
        type_counts: Dict[str, int] = {}
        domain_counts: Dict[str, int] = {}
        for entry in self._entries.values():
            t = entry.knowledge_type.value
            d = entry.domain.value
            type_counts[t] = type_counts.get(t, 0) + 1
            domain_counts[d] = domain_counts.get(d, 0) + 1
        self._stats["entries_by_type"] = type_counts
        self._stats["entries_by_domain"] = domain_counts

    def get_stats(self) -> Dict:
        """Return a copy of current stats"""
        return self._stats.copy()
