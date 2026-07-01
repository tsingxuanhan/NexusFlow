# -*- coding: utf-8 -*-
"""
铉枢·炉守 Continuous Learning Pipeline — 持续学习管道
XuanHub Continuous Learning Pipeline

Agent每次交互都在进步的核心管道：
1. 交互记录 — 每次交互存入Recall Memory
2. 效果评估 — 自动判断交互效果（positive/negative）
3. Core更新 — 高价值信息自动同步到Core Memory
4. Sleeptime触发 — Agent空闲时自动consolidate
5. 冲突解决 — 规则冲突检测和自动解决
6. 知识扩充 — 盲区自动学习
"""

import json
import re
import time
import logging
from typing import Any, Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger("ContinuousLearning")


class InteractionOutcome(Enum):
    """交互结果类型"""
    POSITIVE = "positive"        # 效果好 → 强化
    NEGATIVE = "negative"        # 效果差 → 标记教训
    NEUTRAL = "neutral"          # 一般 → 正常衰减
    CORRECTED = "corrected"      # 被用户纠正 → 高价值学习


@dataclass
class InteractionRecord:
    """交互记录"""
    query: str
    response: str
    outcome: InteractionOutcome
    feedback: str = ""           # 用户反馈
    domain: str = "general"
    timestamp: float = field(default_factory=time.time)
    tokens_used: int = 0
    model_used: str = ""

    def to_dict(self) -> Dict:
        return {
            "query": self.query,
            "response": self.response[:200],
            "outcome": self.outcome.value,
            "feedback": self.feedback,
            "domain": self.domain,
            "timestamp": self.timestamp,
            "tokens_used": self.tokens_used,
            "model_used": self.model_used,
        }


@dataclass
class LearningResult:
    """学习结果"""
    episodes_stored: int = 0
    rules_extracted: int = 0
    core_updated: bool = False
    conflicts_resolved: int = 0
    knowledge_ingested: int = 0
    consolidation_done: bool = False
    notes: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict:
        return {
            "episodes_stored": self.episodes_stored,
            "rules_extracted": self.rules_extracted,
            "core_updated": self.core_updated,
            "conflicts_resolved": self.conflicts_resolved,
            "knowledge_ingested": self.knowledge_ingested,
            "consolidation_done": self.consolidation_done,
            "notes": self.notes,
        }


class ContinuousLearningPipeline:
    """
    持续学习管道 — 每次交互都在进步

    两条路径：
    1. on_interaction — 每次交互后的即时学习
    2. on_periodic — Sleeptime Engine定期执行的深度学习

    用法：
        pipeline = ContinuousLearningPipeline(memory_manager=mm, sleeptime_engine=se)
        
        # 每次交互后
        pipeline.on_interaction(query, response, outcome=InteractionOutcome.POSITIVE)
        
        # 定期（Agent空闲时）
        pipeline.on_periodic()
    """

    def __init__(
        self,
        memory_manager: Any = None,
        sleeptime_engine: Any = None,
        meta_cognition: Any = None,
        api_endpoint: Optional[str] = None,
        api_key: Optional[str] = None,
        core_update_threshold: float = 0.7,    # 重要性阈值，超过才更新Core
        consolidation_interval: int = 3600,     # 整理间隔（秒）
    ):
        self.memory_manager = memory_manager
        self.sleeptime_engine = sleeptime_engine
        self.meta_cognition = meta_cognition
        self.api_endpoint = api_endpoint
        self.api_key = api_key
        self.core_update_threshold = core_update_threshold
        self.consolidation_interval = consolidation_interval

        # 交互缓冲区（批量处理）
        self._interaction_buffer: List[InteractionRecord] = []
        self._buffer_size = 10  # 满10条触发一次批量学习

        # 上次整理时间
        self._last_consolidation = 0.0

        # 统计
        self._stats = {
            "interactions_processed": 0,
            "positive_interactions": 0,
            "negative_interactions": 0,
            "rules_extracted": 0,
            "core_updates": 0,
            "consolidations": 0,
            "knowledge_gaps_filled": 0,
        }

    # ============ 即时学习路径 ============

    def on_interaction(
        self,
        query: str,
        response: str,
        outcome: InteractionOutcome = InteractionOutcome.NEUTRAL,
        feedback: str = "",
        domain: str = "general",
        tokens_used: int = 0,
        model_used: str = "",
    ) -> LearningResult:
        """
        每次交互后的即时学习

        1. 存入Recall Memory
        2. 评估效果，标记positive/negative
        3. 高价值信息更新Core Memory
        4. 缓冲区满时触发批量学习
        """
        result = LearningResult()

        # 创建交互记录
        record = InteractionRecord(
            query=query,
            response=response,
            outcome=outcome,
            feedback=feedback,
            domain=domain,
            tokens_used=tokens_used,
            model_used=model_used,
        )

        # Step 1: 存入Recall Memory
        if self.memory_manager:
            try:
                importance = self._compute_importance(record)
                episode_type = self._outcome_to_episode_type(outcome)
                lessons = ""
                if outcome == InteractionOutcome.NEGATIVE:
                    lessons = f"失败教训: {feedback or '效果不佳'}"
                elif outcome == InteractionOutcome.CORRECTED:
                    lessons = f"纠正学习: {feedback}"
                elif outcome == InteractionOutcome.POSITIVE:
                    lessons = f"成功经验: {feedback or '策略有效'}"

                self.memory_manager.remember(
                    content=f"Q: {query} A: {response[:200]}",
                    memory_type="recall",
                    episode_type=episode_type,
                    importance=importance,
                    outcome=outcome.value,
                    lessons=lessons,
                    tags=[domain, outcome.value],
                )
                result.episodes_stored = 1
            except Exception as e:
                logger.warning(f"[ContinuousLearning] Failed to store episode: {e}")

        # Step 2: 统计
        self._stats["interactions_processed"] += 1
        if outcome == InteractionOutcome.POSITIVE:
            self._stats["positive_interactions"] += 1
        elif outcome in (InteractionOutcome.NEGATIVE, InteractionOutcome.CORRECTED):
            self._stats["negative_interactions"] += 1

        # Step 3: 被纠正的交互 → 高价值，直接更新Core
        if outcome == InteractionOutcome.CORRECTED and self.memory_manager:
            try:
                self.memory_manager.remember(
                    content=f"用户纠正: {query[:100]} → 正确答案: {feedback[:200]}",
                    memory_type="core",
                    block="active_context",
                )
                result.core_updated = True
                self._stats["core_updates"] += 1
            except Exception:
                pass

        # Step 4: 添加到缓冲区
        self._interaction_buffer.append(record)

        # Step 5: 缓冲区满 → 批量学习
        if len(self._interaction_buffer) >= self._buffer_size:
            batch_result = self._batch_learn()
            result.rules_extracted += batch_result.rules_extracted
            result.core_updated = result.core_updated or batch_result.core_updated

        return result

    # ============ 定期学习路径 ============

    def on_periodic(self, force: bool = False) -> LearningResult:
        """
        Sleeptime Engine定期执行的深度学习

        1. Consolidation: recall episodes → patterns → rules → core/procedural
        2. Decay: D-MEM多巴胺门控 → 低重要性记忆衰减
        3. Conflict resolution: 规则冲突检测和解决
        4. Archival reindex: 新知识重新索引
        5. Knowledge gap filling: 识别并填补盲区
        """
        result = LearningResult()

        # 检查是否到了整理时间
        now = time.time()
        if not force and (now - self._last_consolidation) < self.consolidation_interval:
            result.notes.append("未到整理间隔，跳过")
            return result

        logger.info("[ContinuousLearning] Starting periodic consolidation")
        self._last_consolidation = now

        # Step 1: Sleeptime Consolidation
        if self.sleeptime_engine:
            try:
                dream_result = self.sleeptime_engine.dream(force=force)
                if dream_result:
                    result.consolidation_done = True
                    # 提取统计
                    dream_dict = dream_result.to_dict() if hasattr(dream_result, 'to_dict') else {}
                    result.rules_extracted = dream_dict.get("rules_extracted", 0)
                    result.notes.append(f"Sleeptime: {len(dream_dict)} phases completed")
            except Exception as e:
                result.notes.append(f"Sleeptime failed: {str(e)[:100]}")

        # Step 2: Memory Manager Consolidation
        elif self.memory_manager:
            try:
                consolidate_result = self.memory_manager.sleeptime_consolidate()
                result.consolidation_done = True
                result.rules_extracted = consolidate_result.get("rules_extracted", 0)
                result.conflicts_resolved = consolidate_result.get("conflicts", 0)
                result.core_updated = consolidate_result.get("core_updated", False)
            except Exception as e:
                result.notes.append(f"Consolidation failed: {str(e)[:100]}")

        # Step 3: 冲突解决
        if self.memory_manager:
            try:
                conflicts = self.memory_manager.detect_conflicts()
                if conflicts:
                    resolved = self._resolve_conflicts(conflicts)
                    result.conflicts_resolved = resolved
            except Exception:
                pass

        # Step 4: 知识盲区填补
        if self.meta_cognition:
            try:
                gaps = self.meta_cognition.identify_knowledge_gaps()
                if gaps:
                    # 只自动填补P0级别的盲区
                    p0_gaps = [g for g in gaps if g.priority == "P0"]
                    if p0_gaps:
                        improve_result = self.meta_cognition.self_improve(
                            gaps=[g.description for g in p0_gaps]
                        )
                        result.knowledge_ingested = improve_result.get("knowledge_ingested", 0)
                        self._stats["knowledge_gaps_filled"] += len(p0_gaps)
                        result.notes.append(f"Filled {len(p0_gaps)} P0 knowledge gaps")
            except Exception:
                pass

        self._stats["consolidations"] += 1
        self._stats["rules_extracted"] += result.rules_extracted

        logger.info(
            f"[ContinuousLearning] Consolidation done: "
            f"rules={result.rules_extracted}, conflicts={result.conflicts_resolved}, "
            f"core_updated={result.core_updated}"
        )

        return result

    # ============ 批量学习 ============

    def _batch_learn(self) -> LearningResult:
        """批量学习 — 缓冲区满时触发"""
        result = LearningResult()

        if not self._interaction_buffer:
            return result

        # 分析交互模式
        positive_count = sum(1 for r in self._interaction_buffer if r.outcome == InteractionOutcome.POSITIVE)
        negative_count = sum(1 for r in self._interaction_buffer if r.outcome in (
            InteractionOutcome.NEGATIVE, InteractionOutcome.CORRECTED
        ))

        # 从交互模式提取规则
        if positive_count > negative_count and self.memory_manager:
            try:
                # 收集成功的查询模式
                success_queries = [
                    r.query for r in self._interaction_buffer
                    if r.outcome == InteractionOutcome.POSITIVE
                ]
                if len(success_queries) >= 3:
                    pattern = self._extract_pattern(success_queries)
                    if pattern:
                        self.memory_manager.remember(
                            content=f"批量规则: {pattern}",
                            memory_type="recall",
                            importance=0.6,
                            outcome="positive",
                            lessons=f"从{len(success_queries)}次成功交互中提炼",
                            tags=["batch_rule", "auto_extracted"],
                        )
                        result.rules_extracted = 1
            except Exception:
                pass

        # 更新Core Memory（如果有高频话题）
        if self.memory_manager:
            topic_counts: Dict[str, int] = {}
            for record in self._interaction_buffer:
                # 简单关键词提取
                words = re.findall(r'[\u4e00-\u9fff]{2,4}', record.query)
                for w in words:
                    topic_counts[w] = topic_counts.get(w, 0) + 1

            # 高频话题更新Core
            for topic, count in topic_counts.items():
                if count >= 3:  # 出现3次以上的话题
                    try:
                        self.memory_manager.remember(
                            content=f"高频关注话题: {topic} (近期{count}次交互)",
                            memory_type="core",
                            block="active_context",
                        )
                        result.core_updated = True
                        self._stats["core_updates"] += 1
                    except Exception:
                        pass

        # 清空缓冲区
        self._interaction_buffer.clear()

        return result

    # ============ 冲突解决 ============

    def _resolve_conflicts(self, conflicts: List[Dict]) -> int:
        """解决规则冲突"""
        resolved = 0

        for conflict in conflicts:
            if conflict.get("type") == "rule_conflict":
                # 简单策略：保留置信度更高的规则
                rule_1_id = conflict.get("rule_1", "")
                rule_2_id = conflict.get("rule_2", "")

                if not self.memory_manager:
                    continue

                try:
                    rules = self.memory_manager.recall.rules
                    r1 = rules.get(rule_1_id)
                    r2 = rules.get(rule_2_id)

                    if r1 and r2:
                        # 降低低置信度规则的confidence
                        if r1.confidence >= r2.confidence:
                            r2.confidence *= 0.8  # 降级
                        else:
                            r1.confidence *= 0.8
                        resolved += 1
                except Exception:
                    pass

        return resolved

    # ============ 辅助方法 ============

    def _compute_importance(self, record: InteractionRecord) -> float:
        """计算交互重要性"""
        base = 0.3

        # 被纠正最重要
        if record.outcome == InteractionOutcome.CORRECTED:
            base = 0.9
        elif record.outcome == InteractionOutcome.POSITIVE:
            base = 0.6
        elif record.outcome == InteractionOutcome.NEGATIVE:
            base = 0.7  # 失败经验也很有价值

        # 有反馈加分
        if record.feedback:
            base = min(1.0, base + 0.1)

        return base

    def _outcome_to_episode_type(self, outcome: InteractionOutcome) -> Any:
        """将InteractionOutcome映射到EpisodeType"""
        try:
            from recall_memory import EpisodeType
            mapping = {
                InteractionOutcome.POSITIVE: EpisodeType.INTERACTION,
                InteractionOutcome.NEGATIVE: EpisodeType.ERROR,
                InteractionOutcome.NEUTRAL: EpisodeType.INTERACTION,
                InteractionOutcome.CORRECTED: EpisodeType.LEARNING,
            }
            return mapping.get(outcome, EpisodeType.INTERACTION)
        except ImportError:
            return None

    def _extract_pattern(self, queries: List[str]) -> Optional[str]:
        """从成功查询中提取模式"""
        # 简单共现词分析
        word_counts: Dict[str, int] = {}
        for q in queries:
            words = re.findall(r'[\u4e00-\u9fff]{2,4}', q)
            for w in words:
                word_counts[w] = word_counts.get(w, 0) + 1

        # 出现频率>50%的词
        threshold = len(queries) * 0.5
        common_words = [w for w, c in word_counts.items() if c >= threshold]

        if common_words:
            return f"包含[{', '.join(common_words[:5])}]的查询通常效果较好"

        return None

    # ============ 自动判断交互效果 ============

    def auto_evaluate_outcome(
        self, query: str, response: str, user_feedback: Optional[str] = None
    ) -> InteractionOutcome:
        """
        自动判断交互效果

        启发式规则：
        - 用户说"谢谢"/"很好"/"对了" → POSITIVE
        - 用户说"不对"/"错了"/"不是" → CORRECTED
        - 用户追问同一话题 → NEUTRAL
        - 用户换话题 → NEUTRAL
        - 明确的负面反馈 → NEGATIVE
        """
        if user_feedback:
            fb_lower = user_feedback.lower()
            positive_kw = ["谢谢", "很好", "对了", "正确", "有帮助", "不错", "好的"]
            negative_kw = ["不对", "错了", "不是", "瞎说", "胡说", "不准确"]
            corrected_kw = ["应该是", "其实是", "实际上是", "应该是"]

            if any(kw in fb_lower for kw in corrected_kw):
                return InteractionOutcome.CORRECTED
            if any(kw in fb_lower for kw in positive_kw):
                return InteractionOutcome.POSITIVE
            if any(kw in fb_lower for kw in negative_kw):
                return InteractionOutcome.NEGATIVE

        # 无反馈时基于响应质量启发式判断
        if len(response) < 20:
            return InteractionOutcome.NEGATIVE
        if any(kw in response for kw in ["不确定", "可能", "大概", "也许"]):
            return InteractionOutcome.NEUTRAL

        return InteractionOutcome.NEUTRAL

    def get_stats(self) -> Dict:
        """获取统计信息"""
        return {
            **self._stats,
            "buffer_size": len(self._interaction_buffer),
            "last_consolidation": self._last_consolidation,
        }

    def to_codeact_globals(self) -> Dict[str, Any]:
        """导出为CodeAct全局函数"""
        return {
            "learn_from_interaction": self.on_interaction,
            "periodic_learn": self.on_periodic,
        }
