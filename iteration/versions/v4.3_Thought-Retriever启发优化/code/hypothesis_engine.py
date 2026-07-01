# -*- coding: utf-8 -*-
"""
铉枢·炉守 Hypothesis Engine — 假说驱动引擎
XuanHub Hypothesis Engine v4.2

基于 Agora (ICML 2026) H=(C,A,E,O) 四元组设计，适配 AI4Science 科学假说场景。

核心功能：
1. Miner 生成假说（从文献中发现规律 → 形式化为四元组）
2. Assayer 验证假说（设计验证方案，执行交叉验证）
3. Caster/Artisan 评估假说可行性
4. GoalVerifier 对照假说判定是否完成
5. CheckpointWriter 追踪假说状态

假说生命周期（7种状态）：
PROPOSED → UNDER_REVIEW → VALIDATING → CONFIRMED / REFUTED / INCONCLUSIVE / SUPERSEDED
                                                                    → EXPLOITING
"""

import json
import logging
import re
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger("HypothesisEngine")


# ============================================================================
# 枚举与数据结构
# ============================================================================

class HypothesisStatus(Enum):
    """Hypothesis lifecycle states — 7 states"""
    PROPOSED = "proposed"
    UNDER_REVIEW = "under_review"
    VALIDATING = "validating"
    CONFIRMED = "confirmed"
    REFUTED = "refuted"
    INCONCLUSIVE = "inconclusive"
    SUPERSEDED = "superseded"
    EXPLOITING = "exploiting"


@dataclass
class Hypothesis:
    """
    Scientific Hypothesis — the core unit of HDT.

    H = (Conditions, Actions, Expected, Oracle)

    Example (Materials Science):
    - Conditions: "SSC with 40% GGBS, curing at 50°C for 28 days"
    - Actions: "Test compressive strength with standard procedure"
    - Expected: "Compressive strength >= 40 MPa"
    - Oracle: "Measured strength / 40 MPa >= 1.0"
    """
    hypothesis_id: str = field(default_factory=lambda: f"H-{uuid.uuid4().hex[:8]}")

    # The Four-Tuple (core structure)
    conditions: str = ""
    actions: str = ""
    expected: str = ""
    oracle: str = ""

    # Metadata
    title: str = ""
    description: str = ""
    domain: str = ""
    source_agent: str = ""

    # Lifecycle
    status: HypothesisStatus = HypothesisStatus.PROPOSED
    confidence: float = 0.5
    parent_id: str = ""
    child_ids: List[str] = field(default_factory=list)

    # Execution tracking
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat())
    validation_attempts: List[Dict] = field(default_factory=list)
    final_verdict: str = ""

    # Knowledge library linkage
    related_knowledge: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict:
        """Serialize to dictionary"""
        return {
            "hypothesis_id": self.hypothesis_id,
            "conditions": self.conditions,
            "actions": self.actions,
            "expected": self.expected,
            "oracle": self.oracle,
            "title": self.title,
            "description": self.description,
            "domain": self.domain,
            "source_agent": self.source_agent,
            "status": self.status.value,
            "confidence": self.confidence,
            "parent_id": self.parent_id,
            "child_ids": self.child_ids,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "validation_attempts": self.validation_attempts,
            "final_verdict": self.final_verdict,
            "related_knowledge": self.related_knowledge,
        }

    @classmethod
    def from_dict(cls, data: Dict) -> "Hypothesis":
        """Deserialize from dictionary"""
        h = cls()
        for k, v in data.items():
            if k == "status":
                h.status = HypothesisStatus(v)
            elif hasattr(h, k):
                setattr(h, k, v)
        return h

    def to_four_tuple_str(self) -> str:
        """Format as structured four-tuple string for prompt injection"""
        return (
            f"假说 [{self.hypothesis_id}]: {self.title}\n"
            f"状态: {self.status.value} | 置信度: {self.confidence:.2f}\n\n"
            f"┌─ Conditions (前提条件):\n│  {self.conditions}\n"
            f"├─ Actions (验证动作):\n│  {self.actions}\n"
            f"├─ Expected (预期结果):\n│  {self.expected}\n"
            f"└─ Oracle (判定准则):\n   {self.oracle}"
        )


@dataclass
class HypothesisTestResult:
    """Result of a single hypothesis validation attempt"""
    hypothesis_id: str
    attempt_number: int
    passed: bool
    evidence: str = ""
    oracle_score: float = 0.0
    notes: str = ""
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self) -> Dict:
        return {
            "hypothesis_id": self.hypothesis_id,
            "attempt_number": self.attempt_number,
            "passed": self.passed,
            "evidence": self.evidence,
            "oracle_score": self.oracle_score,
            "notes": self.notes,
            "timestamp": self.timestamp,
        }


# ============================================================================
# HypothesisEngine 主类
# ============================================================================

class HypothesisEngine:
    """
    Manages the lifecycle of scientific hypotheses.

    Key workflows:
    1. Miner proposes → engine.create_hypothesis()
    2. Assayer reviews → engine.update_status(h, UNDER_REVIEW)
    3. Assayer validates → engine.record_test_result(h, result)
    4. Engine evaluates → engine.evaluate_hypothesis(h)
    5. GoalVerifier checks → engine.get_active_hypotheses()
    6. CheckpointWriter tracks → engine.get_hypothesis_snapshot()

    Integration points:
    - MinerAgent.search_papers(): Generates hypotheses from literature
    - AssayerAgent.verify_entry(): Validates hypotheses
    - GoalVerifier.verify(): Checks hypothesis oracle criteria
    - CheckpointWriter: Stores hypothesis state in checkpoint
    - DiscoveryExploitation: Creates child hypotheses from confirmed ones
    """

    # Configuration
    MAX_VALIDATION_ATTEMPTS: int = 5
    CONFIDENCE_CONFIRM_THRESHOLD: float = 0.7
    CONFIDENCE_REFUTE_THRESHOLD: float = 0.3

    def __init__(
        self,
        storage_dir: str = "./hypotheses",
        knowledge_library: Any = None,
    ):
        self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(parents=True, exist_ok=True)

        # Knowledge library reference
        self.knowledge_library = knowledge_library

        # Active hypotheses
        self._hypotheses: Dict[str, Hypothesis] = {}

        # Hypothesis chains (parent → children)
        self._chains: Dict[str, List[str]] = {}

        # Persistence
        self._data_file = self.storage_dir / "hypotheses.json"
        self._load_from_disk()

        # Stats
        self._stats: Dict[str, Any] = {
            "total_created": len(self._hypotheses),
            "confirmed": sum(
                1 for h in self._hypotheses.values()
                if h.status == HypothesisStatus.CONFIRMED
            ),
            "refuted": sum(
                1 for h in self._hypotheses.values()
                if h.status == HypothesisStatus.REFUTED
            ),
            "active": sum(
                1 for h in self._hypotheses.values()
                if h.status in (
                    HypothesisStatus.PROPOSED,
                    HypothesisStatus.UNDER_REVIEW,
                    HypothesisStatus.VALIDATING,
                    HypothesisStatus.EXPLOITING,
                )
            ),
        }

        logger.info(f"[HypothesisEngine] Initialized with {len(self._hypotheses)} hypotheses")

    # ============ Core API ============

    def create_hypothesis(
        self,
        conditions: str,
        actions: str,
        expected: str,
        oracle: str,
        title: str = "",
        source_agent: str = "",
        domain: str = "",
        parent_id: str = "",
        related_knowledge: Optional[List[str]] = None,
    ) -> Hypothesis:
        """
        Create a new hypothesis.

        Called by MinerAgent after literature analysis.
        If parent_id provided, creates a refinement chain.
        """
        h = Hypothesis(
            conditions=conditions,
            actions=actions,
            expected=expected,
            oracle=oracle,
            title=title,
            source_agent=source_agent,
            domain=domain,
            parent_id=parent_id,
            related_knowledge=related_knowledge or [],
        )

        self._hypotheses[h.hypothesis_id] = h

        # Link to parent if applicable
        if parent_id and parent_id in self._hypotheses:
            parent = self._hypotheses[parent_id]
            parent.child_ids.append(h.hypothesis_id)
            self._chains.setdefault(parent_id, []).append(h.hypothesis_id)

        self._persist()
        self._stats["total_created"] += 1
        self._stats["active"] += 1

        logger.info(f"[HypothesisEngine] Created: {h.hypothesis_id} - {title}")
        return h

    def update_status(self, hypothesis_id: str, new_status: HypothesisStatus) -> None:
        """Update hypothesis status with logging"""
        if hypothesis_id in self._hypotheses:
            old_status = self._hypotheses[hypothesis_id].status
            self._hypotheses[hypothesis_id].status = new_status
            self._hypotheses[hypothesis_id].updated_at = datetime.now().isoformat()
            self._persist()
            logger.info(
                f"[HypothesisEngine] {hypothesis_id}: {old_status.value} → {new_status.value}"
            )

    def record_test_result(
        self,
        hypothesis_id: str,
        passed: bool,
        evidence: str = "",
        oracle_score: float = 0.0,
        notes: str = "",
    ) -> HypothesisTestResult:
        """
        Record a validation attempt result.

        Called by AssayerAgent after verification.
        Automatically evaluates hypothesis after each attempt.
        """
        if hypothesis_id not in self._hypotheses:
            raise ValueError(f"Unknown hypothesis: {hypothesis_id}")

        h = self._hypotheses[hypothesis_id]
        attempt_num = len(h.validation_attempts) + 1

        result = HypothesisTestResult(
            hypothesis_id=hypothesis_id,
            attempt_number=attempt_num,
            passed=passed,
            evidence=evidence,
            oracle_score=oracle_score,
            notes=notes,
        )

        h.validation_attempts.append(result.to_dict())
        h.updated_at = datetime.now().isoformat()

        # Update confidence based on result
        if passed:
            h.confidence = min(1.0, h.confidence + 0.15)
        else:
            h.confidence = max(0.0, h.confidence - 0.15)

        # Auto-evaluate
        self._auto_evaluate(h)

        self._persist()
        return result

    def evaluate_hypothesis(self, hypothesis_id: str) -> Dict:
        """Manual evaluation of a hypothesis. Returns evaluation summary with recommendation."""
        if hypothesis_id not in self._hypotheses:
            return {"error": "Unknown hypothesis"}

        h = self._hypotheses[hypothesis_id]
        passed_count = sum(1 for a in h.validation_attempts if a.get("passed"))
        total_count = len(h.validation_attempts)

        evaluation = {
            "hypothesis_id": hypothesis_id,
            "status": h.status.value,
            "confidence": h.confidence,
            "attempts": total_count,
            "passed": passed_count,
            "pass_rate": passed_count / max(1, total_count),
            "recommendation": self._get_recommendation(h),
        }

        return evaluation

    def get_active_hypotheses(self, domain: str = "") -> List[Dict]:
        """Get all active (non-terminal) hypotheses"""
        active_statuses = {
            HypothesisStatus.PROPOSED,
            HypothesisStatus.UNDER_REVIEW,
            HypothesisStatus.VALIDATING,
            HypothesisStatus.EXPLOITING,
        }

        results = []
        for h in self._hypotheses.values():
            if h.status in active_statuses:
                if domain and h.domain != domain:
                    continue
                results.append(h.to_dict())

        return results

    def get_hypothesis_snapshot(self) -> Dict:
        """
        Get a snapshot of all hypotheses for CheckpointWriter.
        Integration point: CheckpointWriter stores this in runtime_state.
        """
        return {
            "total": len(self._hypotheses),
            "active": self._stats["active"],
            "confirmed": self._stats["confirmed"],
            "refuted": self._stats["refuted"],
            "hypotheses": {
                hid: {
                    "title": h.title,
                    "status": h.status.value,
                    "confidence": h.confidence,
                    "attempts": len(h.validation_attempts),
                }
                for hid, h in self._hypotheses.items()
            },
        }

    def get_confirmed_hypotheses(self, domain: str = "") -> List[Hypothesis]:
        """Get all confirmed hypotheses (for Discovery Exploitation)"""
        return [
            h for h in self._hypotheses.values()
            if h.status == HypothesisStatus.CONFIRMED
            and (not domain or h.domain == domain)
        ]

    def create_refinement(
        self,
        parent_id: str,
        new_conditions: str = "",
        new_actions: str = "",
        new_expected: str = "",
        new_oracle: str = "",
    ) -> Optional[Hypothesis]:
        """
        Create a refined hypothesis from a parent.
        Used by Discovery Exploitation to create variant hypotheses.
        """
        if parent_id not in self._hypotheses:
            return None

        parent = self._hypotheses[parent_id]

        child = self.create_hypothesis(
            conditions=new_conditions or parent.conditions,
            actions=new_actions or parent.actions,
            expected=new_expected or parent.expected,
            oracle=new_oracle or parent.oracle,
            title=f"Refinement of {parent.hypothesis_id}",
            source_agent=parent.source_agent,
            domain=parent.domain,
            parent_id=parent_id,
            related_knowledge=parent.related_knowledge.copy(),
        )

        return child

    # ============ Integration: GoalVerifier ============

    def check_hypotheses_satisfaction(self) -> Dict:
        """
        Check if all active hypotheses have been resolved.
        Integration point: GoalVerifier calls this during verify().
        """
        active = self.get_active_hypotheses()
        confirmed = [
            h for h in self._hypotheses.values()
            if h.status == HypothesisStatus.CONFIRMED
        ]
        refuted = [
            h for h in self._hypotheses.values()
            if h.status == HypothesisStatus.REFUTED
        ]

        return {
            "total_hypotheses": len(self._hypotheses),
            "active_count": len(active),
            "confirmed_count": len(confirmed),
            "refuted_count": len(refuted),
            "all_resolved": len(active) == 0,
            "confirmed_titles": [h.title for h in confirmed],
            "active_titles": [h["title"] for h in active],
        }

    # ============ Internal Methods ============

    def _auto_evaluate(self, h: Hypothesis) -> None:
        """Auto-evaluate hypothesis after test result"""
        attempts = len(h.validation_attempts)

        if attempts >= self.MAX_VALIDATION_ATTEMPTS:
            passed = sum(1 for a in h.validation_attempts if a.get("passed"))
            rate = passed / attempts

            if h.confidence >= self.CONFIDENCE_CONFIRM_THRESHOLD:
                h.status = HypothesisStatus.CONFIRMED
                h.final_verdict = f"Confirmed after {attempts} attempts (pass_rate={rate:.0%})"
                self._stats["confirmed"] += 1
                self._stats["active"] = max(0, self._stats["active"] - 1)
            elif h.confidence <= self.CONFIDENCE_REFUTE_THRESHOLD:
                h.status = HypothesisStatus.REFUTED
                h.final_verdict = f"Refuted after {attempts} attempts (pass_rate={rate:.0%})"
                self._stats["refuted"] += 1
                self._stats["active"] = max(0, self._stats["active"] - 1)
            else:
                h.status = HypothesisStatus.INCONCLUSIVE
                h.final_verdict = f"Inconclusive after {attempts} attempts (pass_rate={rate:.0%})"
                self._stats["active"] = max(0, self._stats["active"] - 1)

            logger.info(f"[HypothesisEngine] {h.hypothesis_id} → {h.status.value}: {h.final_verdict}")

    def _get_recommendation(self, h: Hypothesis) -> str:
        """Get recommendation based on current state"""
        if h.status == HypothesisStatus.CONFIRMED:
            return "Hypothesis confirmed. Consider triggering Discovery Exploitation."
        elif h.status == HypothesisStatus.REFUTED:
            return "Hypothesis refuted. Record failure mode in KnowledgeLibrary."
        elif h.status == HypothesisStatus.INCONCLUSIVE:
            return "Insufficient evidence. Consider refining hypothesis or gathering more data."
        elif len(h.validation_attempts) >= self.MAX_VALIDATION_ATTEMPTS:
            return "Max attempts reached. Manual review needed."
        else:
            remaining = self.MAX_VALIDATION_ATTEMPTS - len(h.validation_attempts)
            return f"Continue validation. {remaining} attempts remaining."

    def _persist(self) -> None:
        """Persist hypotheses to disk"""
        try:
            data = {hid: h.to_dict() for hid, h in self._hypotheses.items()}
            with open(self._data_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"[HypothesisEngine] Persist failed: {e}")

    def _load_from_disk(self) -> None:
        """Load hypotheses from disk"""
        if not self._data_file.exists():
            return

        try:
            with open(self._data_file, 'r', encoding='utf-8') as f:
                data = json.load(f)

            for hid, h_data in data.items():
                self._hypotheses[hid] = Hypothesis.from_dict(h_data)
        except Exception as e:
            logger.error(f"[HypothesisEngine] Load failed: {e}")

    def get_stats(self) -> Dict:
        """Return a copy of current stats"""
        return self._stats.copy()
