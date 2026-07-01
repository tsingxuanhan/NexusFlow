# -*- coding: utf-8 -*-
"""
铉枢·炉守 Confidence Filter — 置信度门控
XuanHub Confidence Filter v4.3

基于 Thought-Retriever (TMLR 2026) 的 Dual Filtering 设计。

核心功能：
1. 新思想写入记忆前，进行逻辑一致性校验
2. 与已有记忆对比，检测矛盾
3. 低置信度思想拒绝入库或标记待验证
4. 高相似度思想合并更新（去冗余）
5. 4 维加权评分：逻辑一致性 / 事实验证 / 来源可信度 / 内部一致性

阈值设计：
- ACCEPT:             confidence >= 0.7  → 直接入库
- ACCEPT_WITH_FLAG:   0.5 <= conf < 0.7  → 入库但标记"待验证"
- REJECT:             confidence < 0.5   → 拒绝入库
- MERGE:              相似度 > 0.9       → 合并到已有条目
"""

import logging
import re
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger("ConfidenceFilter")


# ============================================================================
# 枚举与数据结构
# ============================================================================

class FilterDecision(Enum):
    """过滤决策类型"""
    ACCEPT = "accept"              # 置信度 >= 0.7，直接入库
    ACCEPT_WITH_FLAG = "flag"      # 置信度 0.5-0.7，入库但标记"待验证"
    REJECT = "reject"              # 置信度 < 0.5，拒绝入库
    MERGE = "merge"                # 与已有思想高度相似，合并更新


@dataclass
class FilterResult:
    """过滤结果"""
    decision: FilterDecision
    confidence_score: float        # 综合置信度得分
    reason: str                    # 决策理由
    merge_target_id: Optional[str] = None  # MERGE 时的合并目标 ID

    def to_dict(self) -> Dict[str, Any]:
        return {
            "decision": self.decision.value,
            "confidence_score": round(self.confidence_score, 4),
            "reason": self.reason,
            "merge_target_id": self.merge_target_id,
        }


# ============================================================================
# 评分权重配置
# ============================================================================

# 4 维加权评分的权重分配
WEIGHT_LOGICAL_CONSISTENCY: float = 0.35    # 与已有记忆的逻辑一致性
WEIGHT_FACTUAL_VERIFICATION: float = 0.30   # 与知识库的事实校验
WEIGHT_SOURCE_CREDIBILITY: float = 0.20     # 来源 Agent 可信度
WEIGHT_INTERNAL_CONSISTENCY: float = 0.15   # 推理链内部自洽性

# 决策阈值
THRESHOLD_ACCEPT: float = 0.7
THRESHOLD_FLAG: float = 0.5
THRESHOLD_MERGE_SIMILARITY: float = 0.9     # 合并相似度阈值

# Agent 角色可信度基础分
_AGENT_CREDIBILITY: Dict[str, float] = {
    "artisan": 0.85,    # 匠人：整合验证，最高可信度
    "caster": 0.80,     # 铸师：方案生成
    "assayer": 0.75,    # 试金：数据验证
    "miner": 0.70,      # 矿工：文献挖掘，相对低
    "unknown": 0.50,
}

# 矛盾指示词
_CONTRADICTION_MARKERS: List[str] = [
    "矛盾", "不一致", "冲突", "违反", "相反", "否定",
    "contradict", "inconsistent", "conflict", "violate",
    "opposite", "negate", "opposite of",
]


# ============================================================================
# ConfidenceFilter — 置信度门控器
# ============================================================================

class ConfidenceFilter:
    """
    置信度门控器

    职责：
    1. filter()：综合过滤（置信度 + 冗余检测）
    2. calculate_confidence()：4 维加权评分
    3. 与 StructuredPatternMemory 集成（MERGE 时更新已有条目）
    """

    def __init__(
        self,
        accept_threshold: float = THRESHOLD_ACCEPT,
        flag_threshold: float = THRESHOLD_FLAG,
        merge_threshold: float = THRESHOLD_MERGE_SIMILARITY,
    ):
        """
        初始化置信度门控器

        Args:
            accept_threshold: 直接接受阈值（默认 0.7）
            flag_threshold: 标记接受阈值（默认 0.5）
            merge_threshold: 合并相似度阈值（默认 0.9）
        """
        self.accept_threshold = accept_threshold
        self.flag_threshold = flag_threshold
        self.merge_threshold = merge_threshold

        self._stats: Dict[str, Any] = {
            "total_filtered": 0,
            "accepted": 0,
            "accepted_with_flag": 0,
            "rejected": 0,
            "merged": 0,
            "avg_confidence": 0.0,
        }
        self._confidence_sum: float = 0.0

        logger.info(
            f"[ConfidenceFilter] Initialized "
            f"(accept>={accept_threshold}, flag>={flag_threshold}, merge>{merge_threshold})"
        )

    # ====================================================================
    # 核心 API：综合过滤
    # ====================================================================

    def filter(
        self,
        thought: Any,
        memory_provider: Any = None,
        knowledge_library: Any = None,
    ) -> FilterResult:
        """
        综合过滤：置信度评分 + 冗余检测

        流程：
        1. 先检测冗余（如果高度相似 → MERGE）
        2. 再计算置信度 → ACCEPT / FLAG / REJECT

        Args:
            thought: ThoughtDiamond 对象
            memory_provider: 记忆提供者（用于一致性检查和冗余检测）
            knowledge_library: KnowledgeLibrary 实例（用于事实校验）

        Returns:
            FilterResult 过滤结果
        """
        self._stats["total_filtered"] += 1

        # ── Step 1: 冗余检测 ──
        is_redundant, merge_target_id = self._check_redundancy(thought, memory_provider)
        if is_redundant and merge_target_id:
            self._stats["merged"] += 1
            self._update_avg(0.9)
            return FilterResult(
                decision=FilterDecision.MERGE,
                confidence_score=0.9,
                reason=f"与已有思想高度相似，建议合并到 {merge_target_id[:16]}...",
                merge_target_id=merge_target_id,
            )

        # ── Step 2: 4 维置信度评分 ──
        confidence = self.calculate_confidence(thought, memory_provider, knowledge_library)
        self._update_avg(confidence)

        # ── Step 3: 根据阈值做出决策 ──
        if confidence >= self.accept_threshold:
            self._stats["accepted"] += 1
            return FilterResult(
                decision=FilterDecision.ACCEPT,
                confidence_score=confidence,
                reason=f"置信度 {confidence:.2f} >= {self.accept_threshold}，直接入库",
            )
        elif confidence >= self.flag_threshold:
            self._stats["accepted_with_flag"] += 1
            return FilterResult(
                decision=FilterDecision.ACCEPT_WITH_FLAG,
                confidence_score=confidence,
                reason=f"置信度 {confidence:.2f} 在 [{self.flag_threshold}, {self.accept_threshold}) 之间，入库但标记待验证",
            )
        else:
            self._stats["rejected"] += 1
            return FilterResult(
                decision=FilterDecision.REJECT,
                confidence_score=confidence,
                reason=f"置信度 {confidence:.2f} < {self.flag_threshold}，拒绝入库",
            )

    # ====================================================================
    # 4 维置信度评分
    # ====================================================================

    def calculate_confidence(
        self,
        thought: Any,
        memory_provider: Any = None,
        knowledge_library: Any = None,
    ) -> float:
        """
        4 维加权置信度评分

        维度：
        1. 逻辑一致性 (35%)：与已有记忆的逻辑一致性
        2. 事实验证   (30%)：与知识库的事实校验
        3. 来源可信度 (20%)：来源 Agent 角色可信度
        4. 内部一致性 (15%)：推理链内部自洽性

        Returns:
            0.0 - 1.0 的综合得分
        """
        scores: List[float] = []

        # 维度 1：逻辑一致性
        logical = self._check_logical_consistency(thought, memory_provider)
        scores.append(logical * WEIGHT_LOGICAL_CONSISTENCY)

        # 维度 2：事实验证
        factual = self._verify_against_knowledge(thought, knowledge_library)
        scores.append(factual * WEIGHT_FACTUAL_VERIFICATION)

        # 维度 3：来源可信度
        source = self._assess_source_credibility(thought)
        scores.append(source * WEIGHT_SOURCE_CREDIBILITY)

        # 维度 4：内部一致性
        internal = self._check_internal_consistency(thought)
        scores.append(internal * WEIGHT_INTERNAL_CONSISTENCY)

        total = sum(scores)
        return min(1.0, max(0.0, total))

    # ====================================================================
    # 维度 1：逻辑一致性
    # ====================================================================

    def _check_logical_consistency(
        self,
        thought: Any,
        memory_provider: Any = None,
    ) -> float:
        """
        检查与已有记忆的逻辑一致性

        策略：
        1. 获取最近的相关思想
        2. 检测是否存在矛盾指示词
        3. 用关键词重叠估算一致性

        Returns:
            0.0 - 1.0 的一致性分数
        """
        if memory_provider is None:
            return 0.7  # 无记忆可比较时给中等偏上分数

        # 获取最近的思想结晶
        recent_thoughts: List[Any] = []
        if hasattr(memory_provider, "get_recent_thoughts"):
            recent_thoughts = memory_provider.get_recent_thoughts(n=20)

        if not recent_thoughts:
            return 0.7

        thought_text = self._get_thought_text(thought)
        thought_words = set(thought_text.lower().split())

        consistency_scores: List[float] = []

        for existing in recent_thoughts:
            existing_text = self._get_thought_text(existing)
            existing_words = set(existing_text.lower().split())

            # 计算关键词重叠（作为"话题相关度"的代理）
            if not thought_words or not existing_words:
                continue

            overlap = len(thought_words & existing_words)
            relevance = overlap / max(1, min(len(thought_words), len(existing_words)))

            if relevance > 0.3:
                # 话题相关的思想：检查是否有矛盾
                contradiction_score = self._detect_contradiction(thought_text, existing_text)
                consistency_scores.append(contradiction_score)

        if not consistency_scores:
            return 0.75  # 没有相关记忆可比较

        # 取最低一致性作为保守估计
        return min(consistency_scores) if consistency_scores else 0.75

    def _detect_contradiction(self, text_a: str, text_b: str) -> float:
        """
        检测两段文本之间是否存在矛盾

        Returns:
            0.0 = 完全矛盾, 1.0 = 完全一致
        """
        combined = f"{text_a} {text_b}".lower()

        # 统计矛盾指示词出现次数
        contradiction_count = 0
        for marker in _CONTRADICTION_MARKERS:
            if marker in combined:
                contradiction_count += 1

        # 矛盾词越多，一致性越低
        if contradiction_count >= 3:
            return 0.3
        elif contradiction_count >= 2:
            return 0.5
        elif contradiction_count >= 1:
            return 0.7

        # 没有矛盾指示词，计算正向重叠
        words_a = set(text_a.lower().split())
        words_b = set(text_b.lower().split())
        if not words_a or not words_b:
            return 0.7

        overlap = len(words_a & words_b) / max(1, min(len(words_a), len(words_b)))

        # 高重叠 = 高一致性
        return min(1.0, 0.6 + overlap * 0.4)

    # ====================================================================
    # 维度 2：事实验证
    # ====================================================================

    def _verify_against_knowledge(
        self,
        thought: Any,
        knowledge_library: Any = None,
    ) -> float:
        """
        与 KnowledgeLibrary 进行事实校验

        策略：
        1. 如果 knowledge_library 不可用，给默认分数
        2. 提取思想的关键词，在知识库中检索
        3. 如果找到支持性知识 → 加分
        4. 如果找到矛盾知识 → 减分

        Returns:
            0.0 - 1.0 的事实验证分数
        """
        if knowledge_library is None:
            return 0.6  # 无知识库时给默认分

        thought_text = self._get_thought_text(thought)

        try:
            # 尝试使用 KnowledgeLibrary 的 query 方法
            if hasattr(knowledge_library, "query"):
                # 构建简单查询
                try:
                    from knowledge_library import KnowledgeQuery
                    query = KnowledgeQuery(
                        search_text=thought_text[:200],
                        max_results=10,
                        min_confidence=0.5,
                    )
                    results = knowledge_library.query(query)

                    if results:
                        # 找到相关知识 → 事实验证分提高
                        avg_confidence = sum(r.confidence for r in results) / len(results)
                        return min(1.0, 0.5 + avg_confidence * 0.4)
                    else:
                        return 0.55  # 无相关知识，不加分也不减分

                except ImportError:
                    return 0.6

            return 0.6

        except Exception as e:
            logger.warning(f"[ConfidenceFilter] Knowledge verification failed: {e}")
            return 0.6

    # ====================================================================
    # 维度 3：来源可信度
    # ====================================================================

    def _assess_source_credibility(self, thought: Any) -> float:
        """
        评估来源 Agent 的可信度

        基于 Agent 角色和验证状态：
        - 已验证 (verified) → +0.15
        - artisan (匠人) → 最高基础分
        - miner (矿工) → 较低基础分

        Returns:
            0.0 - 1.0 的可信度分数
        """
        # 获取来源 Agent 角色
        agent_role = getattr(thought, "source_agent", "unknown")
        base_credibility = _AGENT_CREDIBILITY.get(agent_role, 0.5)

        # 验证状态加成
        verification_status = getattr(thought, "verification_status", "pending")
        if verification_status == "verified":
            credibility = min(1.0, base_credibility + 0.15)
        elif verification_status == "rejected":
            credibility = max(0.0, base_credibility - 0.3)
        else:
            credibility = base_credibility

        return credibility

    # ====================================================================
    # 维度 4：内部一致性
    # ====================================================================

    def _check_internal_consistency(self, thought: Any) -> float:
        """
        检查推理链内部的自洽性

        策略：
        1. 推理步骤数量是否合理（至少 2 步）
        2. 推理步骤之间是否有明显矛盾
        3. 结论是否与推理步骤方向一致

        Returns:
            0.0 - 1.0 的自洽性分数
        """
        reasoning_chain: List[str] = getattr(thought, "reasoning_chain", [])
        conclusion: str = getattr(thought, "conclusion", "")

        # 推理步骤太少 → 自洽性无法评判，给默认分
        if len(reasoning_chain) < 2:
            return 0.6

        score = 0.7  # 基础分

        # 检查步骤数量的合理性
        if 3 <= len(reasoning_chain) <= 10:
            score += 0.1  # 合理范围加分
        elif len(reasoning_chain) > 15:
            score -= 0.05  # 步骤过多可能有问题

        # 检查步骤之间的连贯性（相邻步骤应有关键词重叠）
        coherence_count = 0
        for i in range(len(reasoning_chain) - 1):
            step_a_words = set(reasoning_chain[i].lower().split())
            step_b_words = set(reasoning_chain[i + 1].lower().split())

            if step_a_words and step_b_words:
                overlap = len(step_a_words & step_b_words)
                if overlap >= 1:
                    coherence_count += 1

        if len(reasoning_chain) > 1:
            coherence_ratio = coherence_count / (len(reasoning_chain) - 1)
            score += coherence_ratio * 0.15  # 连贯性加成

        # 检查结论与推理链的关联
        if conclusion and reasoning_chain:
            conclusion_words = set(conclusion.lower().split())
            chain_text = " ".join(reasoning_chain).lower()
            chain_words = set(chain_text.split())

            if conclusion_words and chain_words:
                overlap = len(conclusion_words & chain_words)
                relevance = overlap / max(1, min(len(conclusion_words), len(chain_words)))
                if relevance > 0.1:
                    score += 0.05  # 结论与推理链有关联

        return min(1.0, max(0.0, score))

    # ====================================================================
    # 冗余检测
    # ====================================================================

    def _check_redundancy(
        self,
        thought: Any,
        memory_provider: Any = None,
    ) -> Tuple[bool, Optional[str]]:
        """
        检测冗余：与已有思想的高度相似性

        使用关键词重叠作为相似度代理（不依赖 embedding）

        Returns:
            (is_redundant, merge_target_id)
            - is_redundant: 是否冗余
            - merge_target_id: 应合并到的目标 ID
        """
        if memory_provider is None:
            return False, None

        thought_text = self._get_thought_text(thought)
        thought_words = set(thought_text.lower().split())

        if not thought_words or len(thought_words) < 3:
            return False, None

        # 获取最近的思想结晶
        recent_thoughts: List[Any] = []
        if hasattr(memory_provider, "get_recent_thoughts"):
            recent_thoughts = memory_provider.get_recent_thoughts(n=30)

        best_similarity = 0.0
        best_target_id: Optional[str] = None

        for existing in recent_thoughts:
            existing_text = self._get_thought_text(existing)
            existing_words = set(existing_text.lower().split())

            if not existing_words:
                continue

            # 计算 Jaccard-like 相似度
            overlap = len(thought_words & existing_words)
            union = len(thought_words | existing_words)

            if union == 0:
                continue

            # 使用 min-based 相似度（更严格）
            similarity = overlap / min(len(thought_words), len(existing_words))

            if similarity > best_similarity:
                best_similarity = similarity
                best_target_id = getattr(existing, "thought_id", None)

        # 超过合并阈值 → 标记为冗余
        if best_similarity >= self.merge_threshold and best_target_id:
            logger.info(
                f"[ConfidenceFilter] Redundant: similarity={best_similarity:.2f}, "
                f"merge_target={best_target_id[:16]}..."
            )
            return True, best_target_id

        return False, None

    # ====================================================================
    # MERGE 操作
    # ====================================================================

    def merge_into_existing(
        self,
        new_thought: Any,
        target_id: str,
        memory_provider: Any = None,
    ) -> bool:
        """
        将新思想合并到已有条目

        合并策略：
        - 更新已有条目的 occurrence_count
        - 如果新思想置信度更高，更新结论
        - 追加新的推理步骤（如果有独特的）

        Args:
            new_thought: 新的 ThoughtDiamond
            target_id: 合并目标 ID
            memory_provider: 记忆提供者

        Returns:
            是否合并成功
        """
        if memory_provider is None:
            return False

        try:
            # 从 ThoughtCrystallizer 获取目标
            target = None
            if hasattr(memory_provider, "get_thought_by_id"):
                target = memory_provider.get_thought_by_id(target_id)

            if target is None:
                logger.warning(f"[ConfidenceFilter] Merge target not found: {target_id[:16]}...")
                return False

            # 更新 occurrence_count（如果有）
            if hasattr(target, "occurrence_count"):
                target.occurrence_count = getattr(target, "occurrence_count", 1) + 1

            # 如果新思想置信度更高，更新结论
            new_conf = getattr(new_thought, "confidence", 0)
            old_conf = getattr(target, "confidence", 0)
            if new_conf > old_conf + 0.05:
                target.conclusion = getattr(new_thought, "conclusion", target.conclusion)
                target.confidence = new_conf

            # 追加新的推理步骤（去重）
            existing_steps = set(getattr(target, "reasoning_chain", []))
            new_steps = getattr(new_thought, "reasoning_chain", [])
            for step in new_steps:
                if step not in existing_steps:
                    target.reasoning_chain.append(step)

            # 关联新思想的 ID
            new_id = getattr(new_thought, "thought_id", "")
            if new_id and hasattr(target, "related_thoughts"):
                if new_id not in target.related_thoughts:
                    target.related_thoughts.append(new_id)

            logger.info(
                f"[ConfidenceFilter] Merged {new_id[:16]}... into {target_id[:16]}..."
            )
            return True

        except Exception as e:
            logger.error(f"[ConfidenceFilter] Merge failed: {e}")
            return False

    # ====================================================================
    # 工具方法
    # ====================================================================

    @staticmethod
    def _get_thought_text(thought: Any) -> str:
        """提取思想的文本表示"""
        if hasattr(thought, "text_repr"):
            return thought.text_repr

        parts: List[str] = []

        # ThoughtDiamond 属性
        for attr in ["conclusion", "problem_type"]:
            val = getattr(thought, attr, "")
            if val:
                parts.append(str(val))

        chain = getattr(thought, "reasoning_chain", [])
        if chain:
            parts.extend(chain)

        decisions = getattr(thought, "key_decisions", [])
        if decisions:
            parts.extend(decisions)

        # Pattern 属性
        if hasattr(thought, "description"):
            parts.append(getattr(thought, "description", ""))
        if hasattr(thought, "title"):
            parts.append(getattr(thought, "title", ""))

        # 字符串
        if isinstance(thought, str):
            return thought

        return " ".join(parts)

    def _update_avg(self, confidence: float) -> None:
        """更新平均置信度"""
        self._confidence_sum += confidence
        total = (
            self._stats["accepted"]
            + self._stats["accepted_with_flag"]
            + self._stats["rejected"]
            + self._stats["merged"]
        )
        if total > 0:
            self._stats["avg_confidence"] = round(
                self._confidence_sum / total, 4
            )

    def get_stats(self) -> Dict[str, Any]:
        """返回统计信息"""
        return self._stats.copy()
