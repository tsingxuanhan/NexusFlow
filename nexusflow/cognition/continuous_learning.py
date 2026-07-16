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
from typing import Any, Dict, List, Optional, Tuple, Set
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path

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
            from nexusflow.memory.recall_memory import EpisodeType
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



# ============================================================================
# v4.1 新增: Dream Cycle 和 Distill 相关类
# ============================================================================

class DistillPhase(Enum):
    """经验沉淀阶段"""
    DISCOVER = "discover"           # 发现重复模式
    EXTRACT = "extract"            # 提炼可复用规则
    FORMALIZE = "formalize"        # 固化为SOP/Skill
    VALIDATE = "validate"          # 验证有效性
    ARCHIVE = "archive"            # 归档


@dataclass
class DistillResult:
    """经验沉淀结果"""
    phase: DistillPhase
    patterns_found: int = 0
    rules_extracted: int = 0
    skills_created: int = 0
    sops_created: int = 0
    archived_entries: int = 0
    insights: List[str] = field(default_factory=list)
    artifacts: List[Dict[str, str]] = field(default_factory=list)  # {type, name, path}
    
    def to_dict(self) -> Dict:
        return {
            "phase": self.phase.value,
            "patterns_found": self.patterns_found,
            "rules_extracted": self.rules_extracted,
            "skills_created": self.skills_created,
            "sops_created": self.sops_created,
            "archived_entries": self.archived_entries,
            "insights": self.insights,
            "artifacts": self.artifacts,
        }


@dataclass
class DreamCycleResult:
    """Dream Cycle结果"""
    phases_completed: List[str] = field(default_factory=list)
    paths_validated: int = 0
    paths_invalid: List[str] = field(default_factory=list)
    duplicates_merged: int = 0
    entries_pruned: int = 0
    importance_adjusted: int = 0
    insights: List[str] = field(default_factory=list)
    duration_seconds: float = 0.0
    
    def to_dict(self) -> Dict:
        return {
            "phases_completed": self.phases_completed,
            "paths_validated": self.paths_validated,
            "paths_invalid": self.paths_invalid,
            "duplicates_merged": self.duplicates_merged,
            "entries_pruned": self.entries_pruned,
            "importance_adjusted": self.importance_adjusted,
            "insights": self.insights,
            "duration_seconds": self.duration_seconds,
        }


class ContinuousLearningPipelineV41(ContinuousLearningPipeline):
    """
    v4.1 增强版持续学习管道
    
    新增功能：
    1. Dream Cycle — 7天周期深度整合
    2. Distill — 30天经验沉淀
    3. 路径有效性验证
    4. 去重压缩
    5. 重要性衰减加速
    
    用法：
        pipeline = ContinuousLearningPipelineV41(memory_manager=mm)
        
        # 7天周期触发
        pipeline.dream_cycle(force=True)
        
        # 30天周期触发
        pipeline.distill(force=True)
    """
    
    # Dream Cycle周期（秒）- 7天
    DREAM_CYCLE_INTERVAL = 7 * 24 * 3600
    
    # Distill周期（秒）- 30天
    DISTILL_INTERVAL = 30 * 24 * 3600
    
    # 路径衰减因子
    PATH_DECAY_FACTOR = 0.5
    
    # 去重阈值（前N字符相同则合并）
    DEDUP_PREFIX_LENGTH = 50
    
    def __init__(
        self,
        memory_manager: Any = None,
        sleeptime_engine: Any = None,
        meta_cognition: Any = None,
        api_endpoint: Optional[str] = None,
        api_key: Optional[str] = None,
        core_update_threshold: float = 0.7,
        consolidation_interval: int = 3600,
        # v4.1新增参数
        dream_cycle_interval: int = DREAM_CYCLE_INTERVAL,
        distill_interval: int = DISTILL_INTERVAL,
        workspace_dir: Optional[str] = None,
    ):
        super().__init__(
            memory_manager=memory_manager,
            sleeptime_engine=sleeptime_engine,
            meta_cognition=meta_cognition,
            api_endpoint=api_endpoint,
            api_key=api_key,
            core_update_threshold=core_update_threshold,
            consolidation_interval=consolidation_interval,
        )
        
        # v4.1新增配置
        self.dream_cycle_interval = dream_cycle_interval
        self.distill_interval = distill_interval
        self.workspace_dir = workspace_dir or "."
        
        # 上次执行时间
        self._last_dream_cycle = 0.0
        self._last_distill = 0.0
        
        # Distill输出目录
        self.distill_output_dir = Path(self.workspace_dir) / "distillations"
        self.distill_output_dir.mkdir(parents=True, exist_ok=True)
        
        # 统计
        self._stats_v41 = {
            "dream_cycles": 0,
            "distills": 0,
            "paths_validated": 0,
            "paths_invalid": 0,
            "duplicates_merged": 0,
            "entries_pruned": 0,
            "skills_created": 0,
            "sops_created": 0,
        }
    
    # ============ v4.1: Dream Cycle（7天周期） ============
    
    def dream_cycle(self, force: bool = False) -> DreamCycleResult:
        """
        Dream Cycle — 7天周期深度整合
        
        区别于on_periodic（按小时执行），dream_cycle是深度整合：
        1. 路径有效性验证
        2. 去重压缩
        3. 重要性衰减调整
        4. 深度模式提炼
        
        Args:
            force: 是否强制执行
        
        Returns:
            DreamCycleResult
        """
        start_time = time.time()
        result = DreamCycleResult()
        
        # 间隔检查
        now = time.time()
        if not force and (now - self._last_dream_cycle) < self.dream_cycle_interval:
            result.phases_completed.append("skipped")
            result.insights.append(f"未到dream cycle间隔（{self.dream_cycle_interval}s）")
            return result
        
        logger.info("[ContinuousLearning] Starting Dream Cycle...")
        self._last_dream_cycle = now
        
        try:
            # Phase 1: 路径有效性验证
            path_result = self._validate_memory_paths()
            result.paths_validated = path_result["validated"]
            result.paths_invalid = path_result["invalid"]
            result.phases_completed.append("path_validation")
            
            if result.paths_invalid:
                result.insights.append(f"发现{len(result.paths_invalid)}个无效路径，已标记过时")
            
            # Phase 2: 去重压缩
            dedup_result = self._deduplicate_and_compress()
            result.duplicates_merged = dedup_result["merged"]
            result.entries_pruned = dedup_result["pruned"]
            result.phases_completed.append("deduplication")
            
            if result.duplicates_merged > 0:
                result.insights.append(f"合并{result.duplicates_merged}个重复条目")
            
            # Phase 3: 重要性衰减加速（对过时路径的条目）
            decay_result = self._accelerated_decay_for_invalid_paths()
            result.importance_adjusted = decay_result["adjusted"]
            result.phases_completed.append("decay_acceleration")
            
            if result.importance_adjusted > 0:
                result.insights.append(f"对{result.importance_adjusted}个过时路径条目加速衰减")
            
            # Phase 4: 深度模式提炼（调用LLM）
            pattern_result = self._deep_pattern_extraction()
            if pattern_result.get("patterns"):
                result.insights.append(f"提炼{len(pattern_result['patterns'])}个深度模式")
            result.phases_completed.append("deep_patterns")
            
            # Phase 5: Core Memory同步
            if self.memory_manager:
                self._sync_core_memory_from_dream()
                result.phases_completed.append("core_sync")
            
        except Exception as e:
            logger.error(f"[ContinuousLearning] Dream cycle error: {e}")
            result.insights.append(f"错误: {str(e)[:100]}")
        
        result.duration_seconds = time.time() - start_time
        self._stats_v41["dream_cycles"] += 1
        self._stats_v41["paths_validated"] += result.paths_validated
        self._stats_v41["paths_invalid"] += len(result.paths_invalid)
        self._stats_v41["duplicates_merged"] += result.duplicates_merged
        self._stats_v41["entries_pruned"] += result.entries_pruned
        
        logger.info(
            f"[ContinuousLearning] Dream Cycle complete: "
            f"paths_validated={result.paths_validated}, "
            f"paths_invalid={len(result.paths_invalid)}, "
            f"duplicates_merged={result.duplicates_merged}, "
            f"duration={result.duration_seconds:.1f}s"
        )
        
        return result
    
    # ============ v4.1: Distill（30天经验沉淀） ============
    
    def distill(self, force: bool = False) -> DistillResult:
        """
        Distill — 30天经验沉淀
        
        识别重复工作模式，固化成可复用的skill/规则/SOP。
        
        Args:
            force: 是否强制执行
        
        Returns:
            DistillResult
        """
        result = DistillResult(phase=DistillPhase.DISCOVER)
        
        # 间隔检查
        now = time.time()
        if not force and (now - self._last_distill) < self.distill_interval:
            result.insights.append(f"未到distill间隔（{self.distill_interval}s）")
            return result
        
        logger.info("[ContinuousLearning] Starting Distill...")
        self._last_distill = now
        
        try:
            # Phase 1: 发现重复模式
            patterns = self._discover_work_patterns()
            result.patterns_found = len(patterns)
            result.phase = DistillPhase.DISCOVER
            
            if not patterns:
                result.insights.append("未发现明显的重复工作模式")
                return result
            
            # Phase 2: 提炼可复用规则
            rules = self._extract_reusable_rules(patterns)
            result.rules_extracted = len(rules)
            result.phase = DistillPhase.EXTRACT
            
            # Phase 3: 固化为SOP/Skill
            artifacts = self._formalize_to_artifacts(patterns, rules)
            result.skills_created = artifacts["skills"]
            result.sops_created = artifacts["sops"]
            result.artifacts = artifacts["list"]
            result.phase = DistillPhase.FORMALIZE
            
            # Phase 4: 归档
            self._archive_distill_artifacts(result)
            result.archived_entries = len(result.artifacts)
            result.phase = DistillPhase.ARCHIVE
            
            result.insights.append(f"发现{result.patterns_found}个模式，提炼{result.rules_extracted}条规则")
            result.insights.append(f"创建{result.skills_created}个skill，{result.sops_created}个SOP")
            
        except Exception as e:
            logger.error(f"[ContinuousLearning] Distill error: {e}")
            result.insights.append(f"错误: {str(e)[:100]}")
        
        self._stats_v41["distills"] += 1
        self._stats_v41["skills_created"] += result.skills_created
        self._stats_v41["sops_created"] += result.sops_created
        
        logger.info(
            f"[ContinuousLearning] Distill complete: "
            f"patterns={result.patterns_found}, "
            f"rules={result.rules_extracted}, "
            f"skills={result.skills_created}, "
            f"sops={result.sops_created}"
        )
        
        return result
    
    # ============ 路径有效性验证 ============
    
    def _validate_memory_paths(self) -> Dict:
        """验证记忆中引用的文件路径是否有效"""
        result = {"validated": 0, "invalid": []}
        
        if not self.memory_manager:
            return result
        
        try:
            # 获取所有记忆条目中的文件路径
            paths_to_check: Set[str] = set()
            
            # 从Recall Memory获取
            if hasattr(self.memory_manager, 'recall'):
                recall_entries = self.memory_manager.recall.recall_recent(hours=24*30, top_k=1000)
                for entry in recall_entries:
                    # 简单提取文件路径
                    paths = self._extract_paths_from_text(entry.content)
                    paths_to_check.update(paths)
            
            # 从Core Memory获取
            if hasattr(self.memory_manager, 'core'):
                core_data = self.memory_manager.core.to_dict() if hasattr(self.memory_manager.core, 'to_dict') else {}
                for section, content in core_data.items():
                    if isinstance(content, str):
                        paths = self._extract_paths_from_text(content)
                        paths_to_check.update(paths)
            
            # 验证每个路径
            for path_str in paths_to_check:
                result["validated"] += 1
                
                try:
                    path = Path(path_str)
                    if not path.is_absolute():
                        path = Path(self.workspace_dir) / path
                    
                    if not path.exists():
                        result["invalid"].append(path_str)
                        logger.debug(f"[ContinuousLearning] Invalid path: {path_str}")
                except Exception:
                    result["invalid"].append(path_str)
            
        except Exception as e:
            logger.warning(f"[ContinuousLearning] Path validation failed: {e}")
        
        return result
    
    def _extract_paths_from_text(self, text: str) -> List[str]:
        """从文本中提取文件路径"""
        paths = []
        
        # 匹配常见路径格式
        # Unix路径: /xxx/yyy 或 ./xxx/yyy
        unix_pattern = r'(?:^|[/\s])([./]?(?:/[a-zA-Z0-9._-]+)+)'
        # Windows路径: C:\xxx\yyy
        win_pattern = r'([A-Za-z]:\\(?:[^\\/:*?"<>|\r\n]+\\)*[^\\/:*?"<>|\r\n]*)'
        
        for match in re.finditer(unix_pattern, text):
            path = match.group(1)
            if len(path) > 3 and '.' in path:
                paths.append(path)
        
        for match in re.finditer(win_pattern, text):
            paths.append(match.group(1))
        
        return paths
    
    # ============ 去重压缩 ============
    
    def _deduplicate_and_compress(self) -> Dict:
        """对记忆条目做语义去重"""
        result = {"merged": 0, "pruned": 0}
        
        if not self.memory_manager:
            return result
        
        try:
            # 获取最近记忆条目
            if hasattr(self.memory_manager, 'recall'):
                entries = self.memory_manager.recall.recall_recent(hours=24*30, top_k=500)
                
                # 按前缀分组
                prefix_groups: Dict[str, List] = {}
                for entry in entries:
                    content = entry.content if hasattr(entry, 'content') else str(entry)
                    prefix = content[:self.DEDUP_PREFIX_LENGTH].lower().strip()
                    
                    if prefix not in prefix_groups:
                        prefix_groups[prefix] = []
                    prefix_groups[prefix].append(entry)
                
                # 合并重复条目
                for prefix, group in prefix_groups.items():
                    if len(group) > 1:
                        # 保留重要性最高的，删除其他的
                        group.sort(key=lambda e: getattr(e, 'importance', 0.5), reverse=True)
                        keep = group[0]
                        to_remove = group[1:]
                        
                        for entry in to_remove:
                            try:
                                if hasattr(entry, 'entry_id'):
                                    self.memory_manager.recall.forget(entry.entry_id)
                                    result["merged"] += 1
                            except Exception:
                                pass
                
                # 压缩超长条目
                if hasattr(self.memory_manager, 'archival'):
                    self._compress_archival_entries()
                    result["pruned"] = 1
                
        except Exception as e:
            logger.warning(f"[ContinuousLearning] Deduplication failed: {e}")
        
        return result
    
    def _compress_archival_entries(self) -> int:
        """压缩归档中的超长条目"""
        if not hasattr(self.memory_manager, 'archival'):
            return 0
        
        compressed = 0
        
        try:
            entries = list(self.memory_manager.archival.entries.values())
            
            for entry in entries:
                content = entry.content if hasattr(entry, 'content') else str(entry)
                
                # 如果超过10000字符，截断并添加摘要标记
                if len(content) > 10000:
                    summarized = content[:5000] + f"\n\n[... 摘要 ...]\n\n{content[-2000:]}"
                    
                    try:
                        self.memory_manager.archival.update(entry.entry_id, summarized)
                        compressed += 1
                    except Exception:
                        pass
                        
        except Exception as e:
            logger.warning(f"[ContinuousLearning] Compression failed: {e}")
        
        return compressed
    
    # ============ 重要性衰减加速 ============
    
    def _accelerated_decay_for_invalid_paths(self) -> Dict:
        """对过时路径的记忆条目加速重要性衰减"""
        result = {"adjusted": 0}
        
        if not self.memory_manager:
            return result
        
        # 获取无效路径
        path_validation = self._validate_memory_paths()
        invalid_paths = set(path_validation.get("invalid", []))
        
        if not invalid_paths:
            return result
        
        try:
            entries = self.memory_manager.recall.recall_recent(hours=24*30, top_k=500)
            
            for entry in entries:
                content = entry.content if hasattr(entry, 'content') else str(entry)
                paths_in_entry = self._extract_paths_from_text(content)
                
                # 检查是否有无效路径
                has_invalid = any(p in invalid_paths for p in paths_in_entry)
                
                if has_invalid and hasattr(entry, 'importance'):
                    # 加速衰减
                    old_importance = entry.importance
                    entry.importance = max(0.1, old_importance * self.PATH_DECAY_FACTOR)
                    result["adjusted"] += 1
                    
                    logger.debug(
                        f"[ContinuousLearning] Decayed entry importance: "
                        f"{old_importance:.2f} -> {entry.importance:.2f}"
                    )
                    
        except Exception as e:
            logger.warning(f"[ContinuousLearning] Accelerated decay failed: {e}")
        
        return result
    
    # ============ 深度模式提炼 ============
    
    def _deep_pattern_extraction(self) -> Dict:
        """使用LLM进行深度模式提炼"""
        result = {"patterns": []}
        
        if not self.memory_manager or not self.api_endpoint:
            return result
        
        try:
            # 获取最近的记忆
            entries = self.memory_manager.recall.recall_recent(hours=24*7, top_k=50)
            
            if len(entries) < 5:
                return result
            
            # 构建摘要文本
            summary_text = "\n".join(
                f"- {e.content[:200]}" 
                for e in entries[:20]
            )
            
            # 调用LLM提取模式
            import urllib.request
            
            prompt = f"""从以下记忆条目中，识别2-3个重复的工作模式或规律。
每个模式用一行描述，格式：模式名称 | 描述 | 出现频率

记忆条目:
{summary_text}

模式:"""
            
            payload = {
                "model": "deepseek-chat",
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": 300,
                "temperature": 0.3,
            }
            
            req = urllib.request.Request(
                self.api_endpoint,
                data=json.dumps(payload).encode('utf-8'),
                headers={
                    'Content-Type': 'application/json',
                    'Authorization': f'Bearer {self.api_key}' if self.api_key else '',
                },
                method='POST',
            )
            
            with urllib.request.urlopen(req, timeout=30) as resp:
                response = json.loads(resp.read().decode('utf-8'))
                patterns_text = response['choices'][0]['message']['content']
            
            # 解析模式
            for line in patterns_text.strip().split('\n'):
                line = line.strip()
                if '|' in line:
                    parts = [p.strip() for p in line.split('|')]
                    if len(parts) >= 2:
                        result["patterns"].append({
                            "name": parts[0],
                            "description": parts[1],
                            "frequency": parts[2] if len(parts) > 2 else "1",
                        })
                        
        except Exception as e:
            logger.warning(f"[ContinuousLearning] Deep pattern extraction failed: {e}")
        
        return result
    
    # ============ Core Memory同步 ============
    
    def _sync_core_memory_from_dream(self) -> None:
        """从Dream Cycle结果同步到Core Memory"""
        if not self.memory_manager or not hasattr(self.memory_manager, 'core'):
            return
        
        try:
            # 生成Dream Cycle摘要
            summary_parts = []
            
            # 路径状态
            if self._stats_v41["paths_invalid"] > 0:
                summary_parts.append(
                    f"近期发现{self._stats_v41['paths_invalid']}个无效文件路径，已标记过时"
                )
            
            # 去重状态
            if self._stats_v41["duplicates_merged"] > 0:
                summary_parts.append(
                    f"近期合并{self._stats_v41['duplicates_merged']}个重复记忆条目"
                )
            
            if summary_parts:
                summary = " | ".join(summary_parts)
                self.memory_manager.core.update("dream_insights", summary)
                
        except Exception as e:
            logger.warning(f"[ContinuousLearning] Core sync failed: {e}")
    
    # ============ Distill 辅助方法 ============
    
    def _discover_work_patterns(self) -> List[Dict]:
        """发现重复工作模式"""
        patterns = []
        
        if not self.memory_manager:
            return patterns
        
        try:
            # 获取30天内的记忆
            entries = self.memory_manager.recall.recall_recent(hours=24*30, top_k=200)
            
            # 按标签/类型分组
            tag_groups: Dict[str, List] = {}
            type_groups: Dict[str, List] = {}
            
            for entry in entries:
                for tag in getattr(entry, 'tags', []):
                    tag_groups.setdefault(tag, []).append(entry)
                type_groups.setdefault(getattr(entry, 'episode_type', 'unknown'), []).append(entry)
            
            # 发现高频率模式
            for tag, group in tag_groups.items():
                if len(group) >= 3:
                    patterns.append({
                        "type": "tag_frequency",
                        "tag": tag,
                        "count": len(group),
                        "description": f"'{tag}'相关事件重复{len(group)}次",
                    })
            
            # 发现连续失败模式
            error_count = len(type_groups.get("error", []))
            if error_count >= 3:
                patterns.append({
                    "type": "error_frequency",
                    "error_count": error_count,
                    "description": f"连续出现{error_count}个错误",
                })
                
        except Exception as e:
            logger.warning(f"[ContinuousLearning] Pattern discovery failed: {e}")
        
        return patterns
    
    def _extract_reusable_rules(self, patterns: List[Dict]) -> List[str]:
        """从模式中提炼可复用规则"""
        rules = []
        
        for pattern in patterns:
            if pattern.get("type") == "tag_frequency":
                tag = pattern.get("tag", "")
                count = pattern.get("count", 0)
                
                if count >= 5:
                    rule = f"针对'{tag}'任务，建立专用处理流程（近{count}次重复）"
                    rules.append(rule)
                    
            elif pattern.get("type") == "error_frequency":
                error_count = pattern.get("error_count", 0)
                if error_count >= 3:
                    rule = f"建立错误恢复机制（近期{error_count}个错误需系统性解决）"
                    rules.append(rule)
        
        return rules
    
    def _formalize_to_artifacts(self, patterns: List[Dict], rules: List[str]) -> Dict:
        """将模式和规则固化为Skill/SOP"""
        artifacts = {"skills": 0, "sops": 0, "list": []}
        
        if not patterns and not rules:
            return artifacts
        
        # 生成时间戳
        timestamp = datetime.now().strftime("%Y%m%d_%H%M")
        
        # 生成规则文档
        if rules:
            rules_content = "# 提炼规则\n\n"
            rules_content += f"生成时间: {datetime.now().isoformat()}\n\n"
            rules_content += "## 规则列表\n\n"
            
            for i, rule in enumerate(rules, 1):
                rules_content += f"{i}. {rule}\n"
            
            if patterns:
                rules_content += "\n## 模式分析\n\n"
                for p in patterns:
                    rules_content += f"- {p.get('description', str(p))}\n"
            
            # 写入文件
            rules_file = self.distill_output_dir / f"rules_{timestamp}.md"
            try:
                with open(rules_file, 'w', encoding='utf-8') as f:
                    f.write(rules_content)
                artifacts["list"].append({
                    "type": "rules",
                    "name": f"rules_{timestamp}",
                    "path": str(rules_file),
                })
                artifacts["sops"] = 1
            except Exception as e:
                logger.warning(f"[ContinuousLearning] Failed to write rules: {e}")
        
        # 生成SOP（标准操作流程）
        if patterns:
            sops_content = "# 标准操作流程 (SOP)\n\n"
            sops_content += f"生成时间: {datetime.now().isoformat()}\n\n"
            
            for i, pattern in enumerate(patterns, 1):
                if pattern.get("type") == "tag_frequency":
                    tag = pattern.get("tag", "")
                    sops_content += f"## SOP-{i}: 处理'{tag}'任务\n\n"
                    sops_content += f"### 触发条件\n"
                    sops_content += f"当检测到与'{tag}'相关的任务时触发。\n\n"
                    sops_content += f"### 标准流程\n"
                    sops_content += f"1. 识别任务类型\n"
                    sops_content += f"2. 应用相关规则\n"
                    sops_content += f"3. 验证输出\n"
                    sops_content += f"4. 记录结果\n\n"
            
            sop_file = self.distill_output_dir / f"sop_{timestamp}.md"
            try:
                with open(sop_file, 'w', encoding='utf-8') as f:
                    f.write(sops_content)
                artifacts["list"].append({
                    "type": "sop",
                    "name": f"sop_{timestamp}",
                    "path": str(sop_file),
                })
                artifacts["skills"] = 1
            except Exception as e:
                logger.warning(f"[ContinuousLearning] Failed to write SOP: {e}")
        
        return artifacts
    
    def _archive_distill_artifacts(self, result: DistillResult) -> None:
        """归档Distill产物"""
        try:
            # 记录到归档
            archive_content = f"""# Distill归档

时间: {datetime.now().isoformat()}
阶段: {result.phase.value}

## 统计
- 发现模式: {result.patterns_found}
- 提炼规则: {result.rules_extracted}
- 创建Skill: {result.skills_created}
- 创建SOP: {result.sops_created}

## 洞察
"""
            for insight in result.insights:
                archive_content += f"- {insight}\n"
            
            archive_content += "\n## 产物\n"
            for artifact in result.artifacts:
                archive_content += f"- [{artifact['type']}] {artifact['name']}: {artifact['path']}\n"
            
            archive_file = self.distill_output_dir / "archive.md"
            with open(archive_file, 'a', encoding='utf-8') as f:
                f.write("\n---\n")
                f.write(archive_content)
                
        except Exception as e:
            logger.warning(f"[ContinuousLearning] Archive failed: {e}")
    
    # ============ 统计方法覆盖 ============
    
    def get_stats(self) -> Dict:
        """获取统计信息（覆盖父类，添加v4.1统计）"""
        base_stats = super().get_stats()
        return {
            **base_stats,
            "v41_stats": self._stats_v41,
            "last_dream_cycle": self._last_dream_cycle,
            "last_distill": self._last_distill,
            "dream_cycle_due": time.time() - self._last_dream_cycle >= self.dream_cycle_interval if self._last_dream_cycle else True,
            "distill_due": time.time() - self._last_distill >= self.distill_interval if self._last_distill else True,
        }
    
    def to_dict(self) -> Dict:
        """导出为字典"""
        return {
            "stats": self.get_stats(),
            "dream_cycle_interval": self.dream_cycle_interval,
            "distill_interval": self.distill_interval,
            "distill_output_dir": str(self.distill_output_dir),
        }


# 保持向后兼容
ContinuousLearning = ContinuousLearningPipelineV41