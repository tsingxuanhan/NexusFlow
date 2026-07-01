# -*- coding: utf-8 -*-
"""
铉枢·炉守 Structured Pattern Memory — 结构化模式记忆
XuanHub Structured Pattern Memory v4.2

基于 Agora (ICML 2026) Pattern Memory 设计，适配 AI4Science。

核心功能：
1. 5类模式：EXPERIMENT_DESIGN / LITERATURE_ANALYSIS / DATA_VALIDATION / ERROR_RECOVERY / CROSS_DOMAIN
2. 4级置信度：OBSERVED(1次) → REPEATED(2-3次) → VALIDATED(4+次) → DISTILLED(由Distill周期形式化)
3. 跨域迁移：当源域 pattern 与目标域相似度 > 0.7 时触发迁移建议
4. 与 Dream/Distill 周期集成
5. 按领域/任务类型分离存储（类似 Agora 的 CFT/BFT 分离）

与 KnowledgeLibrary 的区别：
- KnowledgeLibrary = 领域专家知识（手动+自动构建的权威知识）
- PatternMemory = Agent 执行中积累的经验模式（自动提炼的可复用模式）
"""

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

logger = logging.getLogger("PatternMemory")


# ============================================================================
# 枚举与数据结构
# ============================================================================

class PatternCategory(Enum):
    """
    Pattern categories — 5 types.
    Analogous to Agora's CFT/BFT separation.
    """
    EXPERIMENT_DESIGN = "experiment_design"
    LITERATURE_ANALYSIS = "literature_analysis"
    DATA_VALIDATION = "data_validation"
    ERROR_RECOVERY = "error_recovery"
    CROSS_DOMAIN = "cross_domain"


class PatternConfidence(Enum):
    """Pattern confidence levels — 4 levels"""
    OBSERVED = "observed"       # Seen once, not validated
    REPEATED = "repeated"       # Seen 2-3 times
    CONFIRMED = "confirmed"     # Confirmed by 4-5 successful executions
    ESTABLISHED = "established" # Formalized by Distill cycle (6+ occurrences)
    ARCHIVED = "archived"       # Long-term archived


@dataclass
class Pattern:
    """A structured pattern extracted from agent experience"""
    pattern_id: str
    category: PatternCategory
    domain: str

    # Pattern content
    title: str
    description: str
    trigger_conditions: List[str]
    solution_template: str
    anti_patterns: List[str]

    # Lifecycle
    confidence: PatternConfidence = PatternConfidence.OBSERVED
    occurrence_count: int = 1
    first_seen: str = field(default_factory=lambda: datetime.now().isoformat())
    last_seen: str = field(default_factory=lambda: datetime.now().isoformat())

    # Cross-domain transfer
    transfer_source_domain: str = ""
    transfer_target_domains: List[str] = field(default_factory=list)

    # Linkage
    source_episode_ids: List[str] = field(default_factory=list)
    related_knowledge_ids: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict:
        """Serialize to dictionary"""
        return {
            "pattern_id": self.pattern_id,
            "category": self.category.value,
            "domain": self.domain,
            "title": self.title,
            "description": self.description,
            "trigger_conditions": self.trigger_conditions,
            "solution_template": self.solution_template,
            "anti_patterns": self.anti_patterns,
            "confidence": self.confidence.value,
            "occurrence_count": self.occurrence_count,
            "first_seen": self.first_seen,
            "last_seen": self.last_seen,
            "transfer_source_domain": self.transfer_source_domain,
            "transfer_target_domains": self.transfer_target_domains,
            "source_episode_ids": self.source_episode_ids,
            "related_knowledge_ids": self.related_knowledge_ids,
        }

    @classmethod
    def from_dict(cls, data: Dict) -> "Pattern":
        """Deserialize from dictionary"""
        # Ensure enums are properly constructed
        data = dict(data)
        if isinstance(data.get("category"), str):
            data["category"] = PatternCategory(data["category"])
        if isinstance(data.get("confidence"), str):
            data["confidence"] = PatternConfidence(data["confidence"])
        return cls(**data)


# ============================================================================
# StructuredPatternMemory 主类
# ============================================================================

class StructuredPatternMemory:
    """
    Structured Pattern Memory — experience-based pattern storage.

    Key differences from KnowledgeLibrary:
    - KnowledgeLibrary: Expert knowledge (invariants, constraints)
    - PatternMemory: Agent-learned patterns (what works, what doesn't)

    Integration with existing system:
    - Dream Cycle extracts patterns from recent episodes
    - Distill formalizes patterns into SOPs/Skills
    - KnowledgeLibrary references pattern IDs for cross-linking
    - Agents query patterns during task execution

    Storage organization (per domain/category separation):
    ./pattern_memory/
    ├── materials_science/
    │   ├── experiment_design.json
    │   ├── literature_analysis.json
    │   └── data_validation.json
    ├── cement_chemistry/
    │   └── ...
    └── cross_domain/
        └── error_recovery.json
    """

    # Confidence upgrade thresholds
    CONFIDENCE_ORDER = [
        PatternConfidence.OBSERVED,
        PatternConfidence.REPEATED,
        PatternConfidence.CONFIRMED,
        PatternConfidence.ESTABLISHED,
        PatternConfidence.ARCHIVED,
    ]

    # Cross-domain transfer similarity threshold
    TRANSFER_SIMILARITY_THRESHOLD: float = 0.7

    def __init__(self, storage_dir: str = "./pattern_memory"):
        self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(parents=True, exist_ok=True)

        self._patterns: Dict[str, Pattern] = {}
        self._category_index: Dict[PatternCategory, Set[str]] = {
            c: set() for c in PatternCategory
        }
        self._domain_index: Dict[str, Set[str]] = {}

        self._load_from_disk()

        self._stats: Dict[str, Any] = {
            "total_patterns": len(self._patterns),
            "by_category": {c.value: len(ids) for c, ids in self._category_index.items()},
            "total_transfers": 0,
        }

    # ============ Core API ============

    def store_pattern(self, pattern: Pattern) -> str:
        """Store a new pattern"""
        self._patterns[pattern.pattern_id] = pattern
        self._category_index[pattern.category].add(pattern.pattern_id)
        self._domain_index.setdefault(pattern.domain, set()).add(pattern.pattern_id)
        self._persist()
        self._stats["total_patterns"] = len(self._patterns)
        return pattern.pattern_id

    def retrieve_similar(
        self,
        domain: str = "",
        category: Optional[PatternCategory] = None,
        min_confidence: PatternConfidence = PatternConfidence.OBSERVED,
        max_results: int = 20,
    ) -> List[Pattern]:
        """
        Query patterns by domain and category.

        Primary API per spec: retrieve_similar()
        """
        results = self.query_patterns(
            domain=domain,
            category=category,
            min_confidence=min_confidence,
        )
        return results[:max_results]

    def record_occurrence(self, pattern_id: str) -> None:
        """Record that a pattern was observed again, potentially upgrading confidence"""
        if pattern_id not in self._patterns:
            return

        p = self._patterns[pattern_id]
        p.occurrence_count += 1
        p.last_seen = datetime.now().isoformat()

        # Upgrade confidence based on occurrence count
        # OBSERVED(1) → REPEATED(2-3) → CONFIRMED(4-5) → ESTABLISHED(6+)
        if p.occurrence_count >= 6 and p.confidence == PatternConfidence.CONFIRMED:
            p.confidence = PatternConfidence.ESTABLISHED
        elif p.occurrence_count >= 4 and p.confidence == PatternConfidence.REPEATED:
            p.confidence = PatternConfidence.CONFIRMED
        elif p.occurrence_count >= 2 and p.confidence == PatternConfidence.OBSERVED:
            p.confidence = PatternConfidence.REPEATED

        self._persist()

    def trigger_migration(
        self,
        source_domain: str,
        target_domain: str,
    ) -> List[Pattern]:
        """
        Find and apply patterns that can transfer from one domain to another.

        Primary API per spec: trigger_migration()
        Triggers when source domain pattern similarity to target domain > 0.7.
        """
        transferable = self.find_transferable_patterns(source_domain, target_domain)
        transferred: List[Pattern] = []

        for p in transferable:
            result = self.apply_transfer(p.pattern_id, target_domain)
            if result:
                transferred.append(result)
                self._stats["total_transfers"] += 1

        return transferred

    def find_transferable_patterns(
        self,
        source_domain: str,
        target_domain: str,
    ) -> List[Pattern]:
        """
        Find patterns that can transfer from one domain to another.
        Uses keyword-based similarity as a proxy for semantic similarity.
        """
        source_patterns = self.query_patterns(
            domain=source_domain,
            min_confidence=PatternConfidence.CONFIRMED,
        )

        transferable: List[Pattern] = []
        for p in source_patterns:
            # Skip already transferred
            if target_domain in p.transfer_target_domains:
                continue

            # Cross-domain and error-recovery patterns are always transferable
            if p.category in (PatternCategory.CROSS_DOMAIN, PatternCategory.ERROR_RECOVERY):
                transferable.append(p)
            # Check keyword overlap as similarity proxy
            elif self._estimate_similarity(p, target_domain) >= self.TRANSFER_SIMILARITY_THRESHOLD:
                transferable.append(p)

        return transferable

    def apply_transfer(self, pattern_id: str, target_domain: str) -> Optional[Pattern]:
        """Apply a pattern transfer to a new domain"""
        if pattern_id not in self._patterns:
            return None

        source = self._patterns[pattern_id]

        transferred = Pattern(
            pattern_id=f"{pattern_id}_xfer_{target_domain}",
            category=source.category,
            domain=target_domain,
            title=f"[Transferred] {source.title}",
            description=source.description,
            trigger_conditions=source.trigger_conditions,
            solution_template=source.solution_template,
            anti_patterns=source.anti_patterns,
            confidence=PatternConfidence.OBSERVED,  # Reset for new domain
            occurrence_count=1,
            transfer_source_domain=source.domain,
        )
        transferred.transfer_target_domains = source.transfer_target_domains + [target_domain]

        self.store_pattern(transferred)
        return transferred

    def query_patterns(
        self,
        domain: str = "",
        category: Optional[PatternCategory] = None,
        min_confidence: PatternConfidence = PatternConfidence.OBSERVED,
    ) -> List[Pattern]:
        """Query patterns by domain and category"""
        min_idx = self.CONFIDENCE_ORDER.index(min_confidence)

        candidates = (
            self._domain_index.get(domain, set())
            if domain
            else set(self._patterns.keys())
        )

        if category:
            candidates &= self._category_index.get(category, set())

        results: List[Pattern] = []
        for pid in candidates:
            p = self._patterns.get(pid)
            if p and self.CONFIDENCE_ORDER.index(p.confidence) >= min_idx:
                results.append(p)

        return sorted(
            results,
            key=lambda p: (
                -self.CONFIDENCE_ORDER.index(p.confidence),
                -p.occurrence_count,
            ),
        )

    # ============ Integration with Dream/Distill ============

    def ingest_from_dream(self, episodes: List[Dict]) -> int:
        """
        Ingest patterns from Dream Cycle output.
        Integration point: ContinuousLearningPipelineV41.dream_cycle()
        """
        added = 0
        for ep in episodes:
            try:
                cat_value = ep.get("category", "cross_domain")
                try:
                    cat = PatternCategory(cat_value)
                except ValueError:
                    cat = PatternCategory.CROSS_DOMAIN

                pattern = Pattern(
                    pattern_id=f"dream_pat_{len(self._patterns)}_{int(datetime.now().timestamp())}",
                    category=cat,
                    domain=ep.get("domain", "general_science"),
                    title=ep.get("title", "Dream Pattern"),
                    description=ep.get("description", ""),
                    trigger_conditions=ep.get("triggers", []),
                    solution_template=ep.get("solution", ""),
                    anti_patterns=ep.get("anti_patterns", []),
                    confidence=PatternConfidence.OBSERVED,
                    source_episode_ids=ep.get("episode_ids", []),
                )
                self.store_pattern(pattern)
                added += 1
            except Exception as e:
                logger.warning(f"[PatternMemory] Failed to ingest dream episode: {e}")

        return added

    def distill_to_sops(self) -> List[Dict]:
        """
        Distill validated/established patterns into SOPs.
        Integration point: ContinuousLearningPipelineV41.distill()
        """
        sops: List[Dict] = []
        for p in self._patterns.values():
            if p.confidence in (PatternConfidence.CONFIRMED, PatternConfidence.ESTABLISHED):
                sops.append({
                    "pattern_id": p.pattern_id,
                    "title": p.title,
                    "description": p.description,
                    "solution": p.solution_template,
                    "triggers": p.trigger_conditions,
                    "anti_patterns": p.anti_patterns,
                })
                # Upgrade to DISTILLED/ESTABLISHED if not already
                if p.confidence == PatternConfidence.CONFIRMED:
                    p.confidence = PatternConfidence.ESTABLISHED

        return sops

    # ============ Internal Methods ============

    def _estimate_similarity(self, pattern: Pattern, target_domain: str) -> float:
        """
        Estimate similarity between a pattern's domain and a target domain.
        Simple keyword-based proxy. In production, could use embedding similarity.
        """
        # Extract keywords from pattern description and title
        pattern_text = f"{pattern.title} {pattern.description} {' '.join(pattern.trigger_conditions)}".lower()
        domain_text = target_domain.lower().replace("_", " ")

        # Token overlap
        pattern_words = set(pattern_text.split())
        domain_words = set(domain_text.split())

        if not pattern_words or not domain_words:
            return 0.0

        overlap = len(pattern_words & domain_words)
        similarity = overlap / max(1, min(len(pattern_words), len(domain_words)))

        # Boost for generic patterns
        generic_indicators = ["通用", "general", "常见", "common", "标准", "standard"]
        if any(ind in pattern_text for ind in generic_indicators):
            similarity = min(1.0, similarity + 0.3)

        return similarity

    def _persist(self) -> None:
        """Persist patterns to disk, organized by domain"""
        try:
            by_domain: Dict[str, List] = {}
            for p in self._patterns.values():
                by_domain.setdefault(p.domain, []).append(p.to_dict())

            for domain, patterns in by_domain.items():
                domain_dir = self.storage_dir / domain
                domain_dir.mkdir(parents=True, exist_ok=True)

                with open(domain_dir / "patterns.json", 'w', encoding='utf-8') as f:
                    json.dump(patterns, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"[PatternMemory] Persist failed: {e}")

    def _load_from_disk(self) -> None:
        """Load patterns from disk"""
        try:
            for domain_dir in self.storage_dir.iterdir():
                if not domain_dir.is_dir():
                    continue
                patterns_file = domain_dir / "patterns.json"
                if not patterns_file.exists():
                    continue

                with open(patterns_file, 'r', encoding='utf-8') as f:
                    patterns_data = json.load(f)

                for pdata in patterns_data:
                    try:
                        p = Pattern.from_dict(pdata)
                        self._patterns[p.pattern_id] = p
                        self._category_index[p.category].add(p.pattern_id)
                        self._domain_index.setdefault(p.domain, set()).add(p.pattern_id)
                    except Exception as e:
                        logger.warning(f"[PatternMemory] Failed to load pattern: {e}")
        except Exception as e:
            logger.error(f"[PatternMemory] Load failed: {e}")

    def get_stats(self) -> Dict:
        """Return a copy of current stats"""
        return self._stats.copy()
