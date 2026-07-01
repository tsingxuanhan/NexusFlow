# -*- coding: utf-8 -*-
"""
铉枢·炉守 Recall Memory — 回忆记忆层
XuanHub Recall Memory — Episodic Memory with D-MEM Dopamine Decay

Letta三层架构第三层：时序经验+行为规则+可遗忘
- 时间戳事件、交互记录、经验情节
- 时序+相关性检索
- D-MEM多巴胺门控衰减：高重要性→永久保留，低重要性→逐渐遗忘
- 类比：情景记忆
"""

import json
import time
import logging
import os
import math
from typing import Any, Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger("RecallMemory")


class EpisodeType(Enum):
    """情节类型"""
    INTERACTION = "interaction"    # 用户交互
    TASK = "task"                  # 任务执行
    REFLECTION = "reflection"      # 反思
    ERROR = "error"                # 错误/失败
    DISCOVERY = "discovery"        # 新发现
    DECISION = "decision"          # 决策
    LEARNING = "learning"            # 学习/纠正


@dataclass
class Episode:
    """
    经验情节 — 一次完整的经历片段

    类似人脑的情景记忆：有场景、有结果、可回忆
    """
    episode_id: str
    content: str                               # 情节描述
    episode_type: EpisodeType = EpisodeType.INTERACTION
    importance: float = 0.5                    # 重要性(0-1)
    dopamine: float = 0.5                      # 多巴胺信号(0-1)，控制保留/遗忘
    created_at: float = field(default_factory=time.time)
    last_accessed: float = field(default_factory=time.time)
    access_count: int = 0
    tags: List[str] = field(default_factory=list)
    outcome: str = ""                          # 结果描述
    lessons: str = ""                          # 经验教训
    metadata: Dict = field(default_factory=dict)

    # D-MEM衰减状态
    _decayed_importance: Optional[float] = None

    @property
    def effective_importance(self) -> float:
        """衰减后的有效重要性"""
        if self._decayed_importance is not None:
            return self._decayed_importance
        return self.importance

    def apply_decay(self, decay_rate: float = 0.01) -> None:
        """
        D-MEM多巴胺门控衰减

        多巴胺信号决定衰减速度：
        - dopamine > 0.7 → 慢衰减（重要记忆）
        - dopamine 0.3-0.7 → 中等衰减
        - dopamine < 0.3 → 快衰减（可遗忘）
        """
        if self.dopamine > 0.7:
            effective_decay = decay_rate * 0.3   # 慢衰减
        elif self.dopamine > 0.3:
            effective_decay = decay_rate * 0.7   # 中等衰减
        else:
            effective_decay = decay_rate * 1.5   # 快衰减

        self._decayed_importance = self.effective_importance * (1 - effective_decay)

    def reinforce(self, amount: float = 0.1) -> None:
        """强化记忆（被回忆/引用时调用）"""
        self.dopamine = min(1.0, self.dopamine + amount * 0.3)
        self.importance = min(1.0, self.importance + amount * 0.1)
        self.access_count += 1
        self.last_accessed = time.time()

    def is_forgettable(self, threshold: float = 0.3) -> bool:
        """是否可遗忘"""
        return self.effective_importance < threshold and self.dopamine < threshold

    def to_dict(self) -> Dict:
        return {
            "episode_id": self.episode_id,
            "content": self.content,
            "episode_type": self.episode_type.value,
            "importance": self.importance,
            "dopamine": self.dopamine,
            "created_at": self.created_at,
            "last_accessed": self.last_accessed,
            "access_count": self.access_count,
            "tags": self.tags,
            "outcome": self.outcome,
            "lessons": self.lessons,
            "metadata": self.metadata,
            "decayed_importance": self._decayed_importance,
        }

    @classmethod
    def from_dict(cls, d: Dict) -> "Episode":
        ep = cls(
            episode_id=d["episode_id"],
            content=d["content"],
            episode_type=EpisodeType(d.get("episode_type", "interaction")),
            importance=d.get("importance", 0.5),
            dopamine=d.get("dopamine", 0.5),
            created_at=d.get("created_at", time.time()),
            last_accessed=d.get("last_accessed", time.time()),
            access_count=d.get("access_count", 0),
            tags=d.get("tags", []),
            outcome=d.get("outcome", ""),
            lessons=d.get("lessons", ""),
            metadata=d.get("metadata", {}),
        )
        ep._decayed_importance = d.get("decayed_importance")
        return ep


@dataclass
class ProceduralRule:
    """
    行为规则 — 从经验中提炼的可复用规则

    类似程序性记忆：知道"怎么做"而非"发生了什么"
    """
    rule_id: str
    condition: str            # 触发条件
    action: str               # 执行动作
    confidence: float = 0.6   # 置信度
    success_count: int = 0    # 成功次数
    failure_count: int = 0    # 失败次数
    source_episodes: List[str] = field(default_factory=list)  # 来源情节ID
    created_at: float = field(default_factory=time.time)
    last_applied: float = field(default_factory=time.time)

    @property
    def success_rate(self) -> float:
        total = self.success_count + self.failure_count
        return self.success_count / total if total > 0 else 0.0

    def apply_feedback(self, success: bool) -> None:
        """应用后反馈更新"""
        if success:
            self.success_count += 1
            self.confidence = min(1.0, self.confidence + 0.05)
        else:
            self.failure_count += 1
            self.confidence = max(0.0, self.confidence - 0.1)
        self.last_applied = time.time()

    def is_reliable(self, min_confidence: float = 0.4, min_uses: int = 2) -> bool:
        """是否可靠"""
        return self.confidence >= min_confidence and (self.success_count + self.failure_count) >= min_uses

    def to_dict(self) -> Dict:
        return {
            "rule_id": self.rule_id,
            "condition": self.condition,
            "action": self.action,
            "confidence": self.confidence,
            "success_count": self.success_count,
            "failure_count": self.failure_count,
            "source_episodes": self.source_episodes,
            "created_at": self.created_at,
            "last_applied": self.last_applied,
        }

    @classmethod
    def from_dict(cls, d: Dict) -> "ProceduralRule":
        return cls(
            rule_id=d["rule_id"],
            condition=d["condition"],
            action=d["action"],
            confidence=d.get("confidence", 0.6),
            success_count=d.get("success_count", 0),
            failure_count=d.get("failure_count", 0),
            source_episodes=d.get("source_episodes", []),
            created_at=d.get("created_at", time.time()),
            last_applied=d.get("last_applied", time.time()),
        )


class RecallMemory:
    """
    回忆记忆 — 时序经验 + 可遗忘

    核心能力：
    1. record() — 记录经验情节
    2. recall() — 时序+相关性回忆
    3. get_rules() — 获取行为规则
    4. decay() — D-MEM多巴胺门控衰减
    5. extract_rules() — 从情节提炼规则

    用法：
        rm = RecallMemory()
        ep_id = rm.record("尝试用PRO模型做数据清洗，结果超出Token限制",
                          episode_type=EpisodeType.ERROR, outcome="失败", lessons="数据清洗用Flash")
        rm.decay()  # 定期衰减
        rules = rm.extract_rules()  # 从经验提炼规则
    """

    def __init__(
        self,
        persist_path: str = "data/recall_memory.json",
        rules_path: str = "data/procedural_rules.json",
        max_episodes: int = 1000,
        decay_rate: float = 0.01,
        dopamine_threshold: float = 0.3,
        api_endpoint: Optional[str] = None,
        api_key: Optional[str] = None,
    ):
        self.persist_path = persist_path
        self.rules_path = rules_path
        self.max_episodes = max_episodes
        self.decay_rate = decay_rate
        self.dopamine_threshold = dopamine_threshold
        self.api_endpoint = api_endpoint
        self.api_key = api_key

        # 存储
        self.episodes: Dict[str, Episode] = {}
        self.rules: Dict[str, ProceduralRule] = {}
        self._ep_counter = 0
        self._rule_counter = 0
        self._last_decay_time: float = 0

        # 加载
        self._load()

    def record(
        self,
        content: str,
        episode_type: EpisodeType = EpisodeType.INTERACTION,
        importance: float = 0.5,
        dopamine: Optional[float] = None,
        tags: Optional[List[str]] = None,
        outcome: str = "",
        lessons: str = "",
        metadata: Optional[Dict] = None,
    ) -> str:
        """
        记录经验情节

        Args:
            content: 情节描述
            episode_type: 情节类型
            importance: 重要性(0-1)
            dopamine: 多巴胺信号(默认=importance)
            tags: 标签
            outcome: 结果
            lessons: 经验教训
            metadata: 附加元数据

        Returns:
            episode_id
        """
        episode_id = f"ep_{self._ep_counter}"
        self._ep_counter += 1

        # 默认多巴胺=重要性
        if dopamine is None:
            dopamine = importance
            # 错误和发现类情节额外加多巴胺（更值得记住）
            if episode_type in (EpisodeType.ERROR, EpisodeType.DISCOVERY, EpisodeType.DECISION):
                dopamine = min(1.0, importance + 0.2)

        episode = Episode(
            episode_id=episode_id,
            content=content,
            episode_type=episode_type,
            importance=importance,
            dopamine=dopamine,
            tags=tags or [],
            outcome=outcome,
            lessons=lessons,
            metadata=metadata or {},
        )

        self.episodes[episode_id] = episode

        # 超出容量时触发衰减和清理
        if len(self.episodes) > self.max_episodes:
            self.decay()
            self._cleanup_forgettable()

        self._auto_save()
        logger.debug(f"[RecallMemory] Recorded episode '{episode_id}' ({episode_type.value})")
        return episode_id

    def recall(
        self,
        query: str,
        top_k: int = 5,
        time_window: Optional[float] = None,
        episode_type: Optional[EpisodeType] = None,
        min_importance: float = 0.0,
    ) -> List[Episode]:
        """
        回忆 — 时序+相关性检索

        Args:
            query: 查询描述
            top_k: 返回数量
            time_window: 时间窗口(秒)，如3600=最近1小时
            episode_type: 情节类型过滤
            min_importance: 最低重要性过滤
        """
        now = time.time()
        candidates = []

        for ep in self.episodes.values():
            # 时间过滤
            if time_window and (now - ep.created_at) > time_window:
                continue
            # 类型过滤
            if episode_type and ep.episode_type != episode_type:
                continue
            # 重要性过滤
            if ep.effective_importance < min_importance:
                continue

            # 简单相关性评分：关键词匹配
            relevance = self._compute_relevance(query, ep)
            # 时间新鲜度加成
            freshness = max(0, 1.0 - (now - ep.created_at) / (7 * 86400))  # 7天衰减
            # 综合分
            score = relevance * 0.6 + ep.effective_importance * 0.25 + freshness * 0.15

            candidates.append((ep, score))

        candidates.sort(key=lambda x: x[1], reverse=True)

        results = []
        for ep, score in candidates[:top_k]:
            ep.reinforce(amount=0.05)  # 被回忆时强化
            results.append(ep)

        logger.debug(f"[RecallMemory] Recall '{query[:30]}...' → {len(results)} episodes")
        return results

    def recall_recent(self, hours: int = 24, top_k: int = 10) -> List[Episode]:
        """回忆最近N小时的情节"""
        return self.recall("", top_k=top_k, time_window=hours * 3600)

    def get_rules(
        self,
        condition: Optional[str] = None,
        min_confidence: float = 0.4,
    ) -> List[ProceduralRule]:
        """
        获取行为规则

        Args:
            condition: 匹配条件关键词
            min_confidence: 最低置信度
        """
        rules = []
        for rule in self.rules.values():
            if rule.confidence < min_confidence:
                continue
            if condition and condition.lower() not in rule.condition.lower():
                continue
            rules.append(rule)

        rules.sort(key=lambda r: r.confidence, reverse=True)
        return rules

    def add_rule(
        self,
        condition: str,
        action: str,
        source_episodes: Optional[List[str]] = None,
        confidence: float = 0.6,
    ) -> str:
        """添加行为规则"""
        rule_id = f"rule_{self._rule_counter}"
        self._rule_counter += 1

        # 检查是否已有相似规则
        for existing in self.rules.values():
            if self._rule_similarity(existing, condition, action) > 0.8:
                # 合并：提高置信度
                existing.confidence = min(1.0, existing.confidence + 0.05)
                existing.source_episodes.extend(source_episodes or [])
                logger.debug(f"[RecallMemory] Merged similar rule: {existing.rule_id}")
                return existing.rule_id

        rule = ProceduralRule(
            rule_id=rule_id,
            condition=condition,
            action=action,
            confidence=confidence,
            source_episodes=source_episodes or [],
        )
        self.rules[rule_id] = rule
        self._auto_save_rules()
        logger.debug(f"[RecallMemory] Added rule '{rule_id}': {condition} → {action}")
        return rule_id

    def decay(self, force: bool = False) -> Dict[str, int]:
        """
        D-MEM多巴胺门控衰减

        Returns:
            {"decayed": N, "forgettable": M}
        """
        # 至少间隔1小时才衰减
        now = time.time()
        if not force and (now - self._last_decay_time) < 3600:
            return {"decayed": 0, "forgettable": 0}

        self._last_decay_time = now
        decayed = 0
        forgettable = 0

        for ep in self.episodes.values():
            ep.apply_decay(self.decay_rate)
            decayed += 1
            if ep.is_forgettable(self.dopamine_threshold):
                forgettable += 1

        logger.info(f"[RecallMemory] Decay: {decayed} episodes, {forgettable} forgettable")
        return {"decayed": decayed, "forgettable": forgettable}

    def extract_rules_from_episodes(self, episode_ids: Optional[List[str]] = None) -> List[str]:
        """
        从情节中提炼行为规则（规则化方法，无需LLM）

        策略：
        1. 找出同类型情节中的成功/失败模式
        2. 将模式转化为条件→动作规则
        """
        if episode_ids:
            target_episodes = [self.episodes[eid] for eid in episode_ids if eid in self.episodes]
        else:
            target_episodes = list(self.episodes.values())

        new_rules = []

        # 按类型分组
        by_type: Dict[EpisodeType, List[Episode]] = {}
        for ep in target_episodes:
            if ep.lessons:  # 只处理有教训的情节
                by_type.setdefault(ep.episode_type, []).append(ep)

        for ep_type, episodes in by_type.items():
            # 找出成功和失败的模式
            successes = [e for e in episodes if "成功" in e.outcome or "完成" in e.outcome or e.outcome == "成功"]
            failures = [e for e in episodes if "失败" in e.outcome or "错误" in e.outcome or e.outcome == "失败"]

            # 从教训中提取规则
            for ep in episodes:
                if ep.lessons and ep.lessons not in [r.action for r in self.rules.values()]:
                    condition = f"遇到{ep.episode_type.value}类场景"
                    if ep.tags:
                        condition += f"({', '.join(ep.tags[:3])})"

                    rule_id = self.add_rule(
                        condition=condition,
                        action=ep.lessons,
                        source_episodes=[ep.episode_id],
                        confidence=0.5 if ep.outcome == "失败" else 0.4,
                    )
                    new_rules.append(rule_id)

        logger.info(f"[RecallMemory] Extracted {len(new_rules)} rules from episodes")
        return new_rules

    def _cleanup_forgettable(self) -> int:
        """清理可遗忘的情节"""
        forgettable = [eid for eid, ep in self.episodes.items()
                       if ep.is_forgettable(self.dopamine_threshold)]

        # 保留最近的可遗忘情节（给一次机会）
        now = time.time()
        to_remove = []
        for eid in forgettable:
            ep = self.episodes[eid]
            # 最近1小时内创建的不删
            if (now - ep.created_at) < 3600:
                continue
            to_remove.append(eid)

        for eid in to_remove:
            del self.episodes[eid]

        if to_remove:
            logger.info(f"[RecallMemory] Cleaned up {len(to_remove)} forgettable episodes")
            self._auto_save()

        return len(to_remove)

    def _compute_relevance(self, query: str, episode: Episode) -> float:
        """简单关键词匹配相关性"""
        query_words = set(query.lower().split())
        ep_words = set(episode.content.lower().split())
        ep_words.update(set(w.lower() for w in episode.tags))
        ep_words.update(set(episode.outcome.lower().split()))
        ep_words.update(set(episode.lessons.lower().split()))

        if not query_words or not ep_words:
            return 0.0

        overlap = len(query_words & ep_words)
        return min(1.0, overlap / max(len(query_words), 1))

    def _rule_similarity(self, existing: ProceduralRule, condition: str, action: str) -> float:
        """规则相似度"""
        cond_words = set(existing.condition.lower().split()) & set(condition.lower().split())
        act_words = set(existing.action.lower().split()) & set(action.lower().split())

        total_cond = len(set(existing.condition.lower().split()) | set(condition.lower().split()))
        total_act = len(set(existing.action.lower().split()) | set(action.lower().split()))

        if total_cond == 0 or total_act == 0:
            return 0.0

        return (len(cond_words) / total_cond + len(act_words) / total_act) / 2

    def get_stats(self) -> Dict:
        """统计信息"""
        type_counts = {}
        for ep in self.episodes.values():
            type_counts[ep.episode_type.value] = type_counts.get(ep.episode_type.value, 0) + 1

        avg_importance = sum(ep.importance for ep in self.episodes.values()) / max(len(self.episodes), 1)
        avg_dopamine = sum(ep.dopamine for ep in self.episodes.values()) / max(len(self.episodes), 1)
        forgettable = sum(1 for ep in self.episodes.values() if ep.is_forgettable(self.dopamine_threshold))

        return {
            "total_episodes": len(self.episodes),
            "total_rules": len(self.rules),
            "reliable_rules": sum(1 for r in self.rules.values() if r.is_reliable()),
            "avg_importance": round(avg_importance, 3),
            "avg_dopamine": round(avg_dopamine, 3),
            "forgettable": forgettable,
            "episode_types": type_counts,
        }

    def _auto_save(self) -> None:
        """自动保存"""
        if not self.persist_path:
            return
        try:
            os.makedirs(os.path.dirname(self.persist_path) or '.', exist_ok=True)
            data = {
                "ep_counter": self._ep_counter,
                "rule_counter": self._rule_counter,
                "last_decay_time": self._last_decay_time,
                "episodes": {k: v.to_dict() for k, v in self.episodes.items()},
            }
            with open(self.persist_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.warning(f"[RecallMemory] Failed to save: {e}")

    def _auto_save_rules(self) -> None:
        """保存规则"""
        if not self.rules_path:
            return
        try:
            os.makedirs(os.path.dirname(self.rules_path) or '.', exist_ok=True)
            data = {k: v.to_dict() for k, v in self.rules.items()}
            with open(self.rules_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.warning(f"[RecallMemory] Failed to save rules: {e}")

    def _load(self) -> None:
        """加载"""
        # 加载情节
        if self.persist_path and os.path.exists(self.persist_path):
            try:
                with open(self.persist_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                self._ep_counter = data.get("ep_counter", 0)
                self._rule_counter = data.get("rule_counter", 0)
                self._last_decay_time = data.get("last_decay_time", 0)
                for k, v in data.get("episodes", {}).items():
                    self.episodes[k] = Episode.from_dict(v)
                logger.info(f"[RecallMemory] Loaded {len(self.episodes)} episodes")
            except Exception as e:
                logger.warning(f"[RecallMemory] Failed to load episodes: {e}")

        # 加载规则
        if self.rules_path and os.path.exists(self.rules_path):
            try:
                with open(self.rules_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                for k, v in data.items():
                    self.rules[k] = ProceduralRule.from_dict(v)
                logger.info(f"[RecallMemory] Loaded {len(self.rules)} rules")
            except Exception as e:
                logger.warning(f"[RecallMemory] Failed to load rules: {e}")
