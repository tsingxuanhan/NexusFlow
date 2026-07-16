# -*- coding: utf-8 -*-
"""
铉枢·炉守 Sleeptime Engine — 离线"做梦"引擎
XuanHub Sleeptime Engine — Offline Memory Consolidation

Agent空闲时自动整理记忆、提取规则、修剪冗余：
- Phase 1: 回忆整理 — 从Recent Episodes提取重复模式
- Phase 2: 规则提炼 — 将模式泛化为可复用规则
- Phase 3: 记忆修剪 — D-MEM多巴胺门控衰减
- Phase 4: Core更新 — 高置信规则同步到Core Memory

用Flash模型执行，成本低
"""

import json
import time
import logging
import os
from typing import Any, Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger("SleeptimeEngine")


class DreamPhase(Enum):
    """做梦阶段"""
    RECALL = "recall"         # 回忆整理
    GENERALIZE = "generalize"  # 规则提炼
    PRUNE = "prune"           # 记忆修剪
    SYNC = "sync"             # Core同步
    WIKI = "wiki"             # WIKI渲染（Mira-inspired 知识文档化输出）


@dataclass
class DreamLog:
    """做梦日志"""
    dream_id: str
    started_at: float
    finished_at: float = 0
    phases_completed: List[str] = field(default_factory=list)
    patterns_found: int = 0
    rules_created: int = 0
    rules_updated: int = 0
    memories_decayed: int = 0
    memories_forgotten: int = 0
    core_updated: bool = False
    conflicts_resolved: int = 0
    wiki_pages: int = 0          # WIKI渲染页数
    error: str = ""

    def to_dict(self) -> Dict:
        return {
            "dream_id": self.dream_id,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "phases_completed": self.phases_completed,
            "patterns_found": self.patterns_found,
            "rules_created": self.rules_created,
            "rules_updated": self.rules_updated,
            "memories_decayed": self.memories_decayed,
            "memories_forgotten": self.memories_forgotten,
            "core_updated": self.core_updated,
            "conflicts_resolved": self.conflicts_resolved,
            "wiki_pages": self.wiki_pages,
            "error": self.error,
        }


@dataclass
class Pattern:
    """从情节中提取的重复模式"""
    pattern_id: str
    description: str                 # 模式描述
    frequency: int = 1               # 出现频率
    episode_ids: List[str] = field(default_factory=list)
    confidence: float = 0.5

    def to_dict(self) -> Dict:
        return {
            "pattern_id": self.pattern_id,
            "description": self.description,
            "frequency": self.frequency,
            "episode_ids": self.episode_ids,
            "confidence": self.confidence,
        }


class SleeptimeEngine:
    """
    Sleeptime Engine — Agent空闲时的离线整理

    让记忆持续进化，而非只增不减：
    1. 从Recent Episodes提取重复模式
    2. 将模式泛化为可复用规则
    3. D-MEM多巴胺门控修剪
    4. 高置信规则同步到Core Memory

    用法：
        engine = SleeptimeEngine(memory_manager)
        result = engine.dream()  # 执行一次完整"做梦"周期
    """

    def __init__(
        self,
        memory_manager=None,
        api_endpoint: Optional[str] = None,
        api_key: Optional[str] = None,
        model: str = "flash",
        dream_interval: int = 3600,     # 默认每小时做梦一次
        dopamine_threshold: float = 0.3,
        decay_rate: float = 0.01,
        pattern_min_frequency: int = 2,  # 模式最少出现次数
        rule_min_confidence: float = 0.5,
        wiki_output_dir: Optional[str] = None,  # WIKI输出目录（Mira-inspired）
    ):
        self.memory_manager = memory_manager
        self.api_endpoint = api_endpoint
        self.api_key = api_key
        self.model = model
        self.dream_interval = dream_interval
        self.dopamine_threshold = dopamine_threshold
        self.decay_rate = decay_rate
        self.pattern_min_frequency = pattern_min_frequency
        self.rule_min_confidence = rule_min_confidence
        self.wiki_output_dir = wiki_output_dir

        # 做梦历史
        self._dream_log: List[DreamLog] = []
        self._last_dream_time: float = 0
        self._dream_counter = 0

        # 模式缓存
        self._patterns: Dict[str, Pattern] = {}

    def dream(self, force: bool = False) -> DreamLog:
        """
        执行一次完整"做梦"周期

        Args:
            force: 是否强制执行（忽略间隔限制）

        Returns:
            DreamLog
        """
        # 间隔检查
        now = time.time()
        if not force and (now - self._last_dream_time) < self.dream_interval:
            logger.debug("[Sleeptime] Not time to dream yet, skip")
            return DreamLog(dream_id="skip", started_at=now)

        self._dream_counter += 1
        log = DreamLog(
            dream_id=f"dream_{self._dream_counter}",
            started_at=now,
        )

        logger.info(f"[Sleeptime] 🌙 Starting dream #{self._dream_counter}...")

        try:
            # Phase 1: 回忆整理
            patterns = self._phase_recall(log)
            log.patterns_found = len(patterns)
            log.phases_completed.append(DreamPhase.RECALL.value)

            # Phase 2: 规则提炼
            rules_result = self._phase_generalize(patterns, log)
            log.rules_created = rules_result.get("created", 0)
            log.rules_updated = rules_result.get("updated", 0)
            log.phases_completed.append(DreamPhase.GENERALIZE.value)

            # Phase 3: 记忆修剪
            prune_result = self._phase_prune(log)
            log.memories_decayed = prune_result.get("decayed", 0)
            log.memories_forgotten = prune_result.get("forgotten", 0)
            log.phases_completed.append(DreamPhase.PRUNE.value)

            # Phase 4: Core同步
            sync_result = self._phase_sync(log)
            log.core_updated = sync_result.get("updated", False)
            log.conflicts_resolved = sync_result.get("conflicts_resolved", 0)
            log.phases_completed.append(DreamPhase.SYNC.value)

            # Phase 5: WIKI渲染（Mira-inspired 知识文档化输出）
            wiki_result = self._phase_wiki(patterns, log)
            log.wiki_pages = wiki_result.get("pages_rendered", 0)
            log.phases_completed.append(DreamPhase.WIKI.value)

        except Exception as e:
            log.error = str(e)
            logger.error(f"[Sleeptime] Dream error: {e}")

        log.finished_at = time.time()
        self._last_dream_time = now
        self._dream_log.append(log)

        duration = log.finished_at - log.started_at
        logger.info(
            f"[Sleeptime] 🌙 Dream #{self._dream_counter} complete: "
            f"patterns={log.patterns_found}, rules={log.rules_created}, "
            f"decayed={log.memories_decayed}, forgotten={log.memories_forgotten}, "
            f"duration={duration:.1f}s"
        )

        return log

    def should_dream(self) -> bool:
        """是否应该做梦"""
        if not self.memory_manager:
            return False
        now = time.time()
        return (now - self._last_dream_time) >= self.dream_interval

    # ============ Phase 1: 回忆整理 ============

    def _phase_recall(self, log: DreamLog) -> List[Pattern]:
        """
        Phase 1: 从Recent Episodes提取重复模式

        策略：
        1. 获取最近24小时的情节
        2. 按标签/类型分组
        3. 发现重复模式
        """
        if not self.memory_manager:
            return []

        # 获取最近24小时情节
        recent = self.memory_manager.recall.recall_recent(hours=24, top_k=50)

        if not recent:
            logger.debug("[Sleeptime] No recent episodes to analyze")
            return []

        # 按标签分组找模式
        tag_groups: Dict[str, List] = {}
        for ep in recent:
            for tag in ep.tags:
                tag_groups.setdefault(tag, []).append(ep)

        # 按类型分组
        type_groups: Dict[str, List] = {}
        for ep in recent:
            type_groups.setdefault(ep.episode_type.value, []).append(ep)

        patterns = []

        # 从标签组提取模式
        for tag, episodes in tag_groups.items():
            if len(episodes) >= self.pattern_min_frequency:
                pattern = Pattern(
                    pattern_id=f"pat_{len(patterns)}",
                    description=f"标签'{tag}'相关事件重复出现{len(episodes)}次",
                    frequency=len(episodes),
                    episode_ids=[e.episode_id for e in episodes],
                    confidence=min(1.0, len(episodes) / 10),
                )
                patterns.append(pattern)
                self._patterns[pattern.pattern_id] = pattern

        # 从错误类型提取模式
        error_episodes = type_groups.get("error", [])
        if len(error_episodes) >= self.pattern_min_frequency:
            # 提取共同错误模式
            error_contents = [e.content[:100] for e in error_episodes]
            common_words = self._find_common_words(error_contents)

            if common_words:
                pattern = Pattern(
                    pattern_id=f"pat_{len(patterns)}",
                    description=f"重复错误模式: {', '.join(common_words[:5])}",
                    frequency=len(error_episodes),
                    episode_ids=[e.episode_id for e in error_episodes],
                    confidence=0.7,
                )
                patterns.append(pattern)
                self._patterns[pattern.pattern_id] = pattern

        # 尝试用LLM提取更深层模式
        if self.api_endpoint and len(recent) >= 5:
            llm_patterns = self._llm_extract_patterns(recent)
            patterns.extend(llm_patterns)

        logger.info(f"[Sleeptime] Phase 1 (Recall): Found {len(patterns)} patterns from {len(recent)} episodes")
        return patterns

    def _llm_extract_patterns(self, episodes: List) -> List[Pattern]:
        """用Flash模型提取更深层模式"""
        try:
            import urllib.request

            ep_summaries = "\n".join(
                f"- [{e.episode_type.value}] {e.content[:150]} (结果:{e.outcome[:50]})"
                for e in episodes[:20]
            )

            prompt = f"""从以下Agent交互记录中，提取2-3个重复出现的模式或规律。
每个模式一行，格式：条件 | 行为 | 结果

交互记录:
{ep_summaries}

模式:"""

            payload = {
                "model": "deepseek-chat",
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": 200,
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

            with urllib.request.urlopen(req, timeout=15) as resp:
                result = json.loads(resp.read().decode('utf-8'))
                text = result['choices'][0]['message']['content']

            patterns = []
            for line in text.strip().split('\n'):
                line = line.strip().lstrip('0123456789.-) ')
                if '|' in line:
                    parts = [p.strip() for p in line.split('|')]
                    if len(parts) >= 2:
                        pattern = Pattern(
                            pattern_id=f"pat_llm_{len(patterns)}",
                            description=line,
                            frequency=1,
                            confidence=0.5,
                        )
                        patterns.append(pattern)

            return patterns

        except Exception as e:
            logger.warning(f"[Sleeptime] LLM pattern extraction failed: {e}")
            return []

    # ============ Phase 2: 规则提炼 ============

    def _phase_generalize(self, patterns: List[Pattern], log: DreamLog) -> Dict:
        """
        Phase 2: 将模式泛化为可复用规则

        策略：
        1. 高频模式 → 条件-动作规则
        2. 检查与已有规则冲突
        3. 冲突解决（高置信度优先）
        """
        if not self.memory_manager:
            return {"created": 0, "updated": 0}

        created = 0
        updated = 0

        for pattern in patterns:
            if pattern.confidence < self.rule_min_confidence:
                continue

            # 从模式描述中提取条件和动作
            condition, action = self._pattern_to_rule(pattern.description)

            if not condition or not action:
                continue

            # 检查是否已有相似规则
            existing_rules = self.memory_manager.recall.get_rules(condition=condition)

            if existing_rules:
                # 更新已有规则的置信度
                for rule in existing_rules:
                    rule.confidence = min(1.0, rule.confidence + 0.05)
                    rule.source_episodes.extend(pattern.episode_ids[:3])
                    updated += 1
            else:
                # 创建新规则
                self.memory_manager.recall.add_rule(
                    condition=condition,
                    action=action,
                    source_episodes=pattern.episode_ids[:5],
                    confidence=pattern.confidence,
                )
                created += 1

        logger.info(f"[Sleeptime] Phase 2 (Generalize): Created {created} rules, updated {updated}")
        return {"created": created, "updated": updated}

    def _pattern_to_rule(self, pattern_desc: str) -> Tuple[str, str]:
        """将模式描述转化为条件-动作规则"""
        # 尝试用分隔符拆分
        for sep in ['|', '→', '->', '：', ':', '，则', '则']:
            if sep in pattern_desc:
                parts = pattern_desc.split(sep, 1)
                condition = parts[0].strip()
                action = parts[1].strip()
                if condition and action:
                    return condition, action

        # 默认：整个描述作为条件，建议"注意此模式"
        return pattern_desc, "注意此重复模式"

    # ============ Phase 3: 记忆修剪 ============

    def _phase_prune(self, log: DreamLog) -> Dict:
        """
        Phase 3: D-MEM多巴胺门控衰减 + 清理

        仿生遗忘：
        - 高重要性(>0.7) → 永久保留
        - 中重要性(0.3-0.7) → 保留但降权
        - 低重要性(<0.3) → 标记可遗忘，定期清理
        """
        if not self.memory_manager:
            return {"decayed": 0, "forgotten": 0}

        # 触发衰减
        decay_result = self.memory_manager.recall.decay(force=True)

        # 清理可遗忘情节
        forgotten = self.memory_manager.recall._cleanup_forgettable()

        # Archival: 合并相似条目
        archival_merged = 0
        entries = list(self.memory_manager.archival.entries.values())
        if len(entries) > 100:
            # 简单去重：内容前50字符相同的合并
            seen_prefixes: Dict[str, str] = {}
            to_remove = []
            for entry in entries:
                prefix = entry.content[:50].lower().strip()
                if prefix in seen_prefixes:
                    to_remove.append(entry.entry_id)
                    archival_merged += 1
                else:
                    seen_prefixes[prefix] = entry.entry_id

            for eid in to_remove:
                self.memory_manager.archival.remove(eid)

        logger.info(
            f"[Sleeptime] Phase 3 (Prune): "
            f"decayed={decay_result['decayed']}, forgotten={forgotten}, "
            f"archival_merged={archival_merged}"
        )
        return {
            "decayed": decay_result["decayed"],
            "forgotten": forgotten,
            "archival_merged": archival_merged,
        }

    # ============ Phase 4: Core同步 ============

    def _phase_sync(self, log: DreamLog) -> Dict:
        """
        Phase 4: 高置信规则同步到Core Memory + 冲突解决
        """
        if not self.memory_manager:
            return {"updated": False, "conflicts_resolved": 0}

        core_updated = False

        # 同步高置信规则
        reliable_rules = self.memory_manager.recall.get_rules(min_confidence=0.6)
        if reliable_rules:
            rules_text = "\n".join(
                f"- {r.condition} → {r.action} (✓{r.confidence:.0%})"
                for r in reliable_rules[:10]
            )
            self.memory_manager.core.update("procedural", rules_text)
            core_updated = True

        # 冲突检测与解决
        conflicts = self.memory_manager.detect_conflicts()
        conflicts_resolved = 0

        for conflict in conflicts:
            if conflict["type"] == "rule_conflict":
                # 解决策略：保留成功率更高的规则
                r1_id = conflict["rule_1"]
                r2_id = conflict["rule_2"]
                r1 = self.memory_manager.recall.rules.get(r1_id)
                r2 = self.memory_manager.recall.rules.get(r2_id)

                if r1 and r2:
                    if r1.success_rate >= r2.success_rate:
                        r2.confidence *= 0.8  # 降权
                    else:
                        r1.confidence *= 0.8
                    conflicts_resolved += 1

        logger.info(f"[Sleeptime] Phase 4 (Sync): core_updated={core_updated}, conflicts_resolved={conflicts_resolved}")
        return {"updated": core_updated, "conflicts_resolved": conflicts_resolved}

    # ============ 辅助 ============

    def _find_common_words(self, texts: List[str]) -> List[str]:
        """找出多个文本中的共同高频词"""
        word_freq: Dict[str, int] = {}
        for text in texts:
            seen = set()
            for word in text.lower().split():
                clean = ''.join(c for c in word if c.isalnum() or '\u4e00' <= c <= '\u9fff')
                if clean and len(clean) > 1 and clean not in seen:
                    word_freq[clean] = word_freq.get(clean, 0) + 1
                    seen.add(clean)

        # 至少出现2次的词
        common = [(w, f) for w, f in word_freq.items() if f >= 2]
        common.sort(key=lambda x: x[1], reverse=True)
        return [w for w, _ in common[:10]]

    # ============ Phase 5: WIKI渲染（Mira-inspired）============

    def _phase_wiki(self, patterns: List[Pattern], log: DreamLog) -> Dict:
        """
        Phase 5: 将巩固的知识渲染为人类可导航的Markdown WIKI文档
        
        借鉴Mira的LLM WIKI思路：夜间自动运行，输出结构化知识文档。
        与Mira的区别：Mira从对话中沉淀，我们从Sleeptime的模式和规则中沉淀。
        
        渲染策略：
        1. 索引页 — 所有WIKI的导航入口
        2. 模式页 — 按领域分类的重复模式文档
        3. 规则页 — 提炼的可复用规则手册
        4. 变更日志 — 每次dream的增量更新记录
        """
        if not self.wiki_output_dir:
            logger.debug("[Sleeptime] No wiki_output_dir configured, skip WIKI phase")
            return {"pages_rendered": 0}
        
        if not self.memory_manager:
            return {"pages_rendered": 0}
        
        # 确保输出目录存在
        wiki_dir = self.wiki_output_dir
        os.makedirs(wiki_dir, exist_ok=True)
        
        pages_rendered = 0
        timestamp = time.strftime("%Y-%m-%d %H:%M")
        
        # 1. 渲染模式页
        if patterns:
            patterns_page = self._render_patterns_page(patterns, timestamp)
            path = os.path.join(wiki_dir, "patterns.md")
            self._write_wiki_page(path, patterns_page)
            pages_rendered += 1
        
        # 2. 渲染规则手册页
        rules = self.memory_manager.recall.get_rules(min_confidence=0.3) if self.memory_manager.recall else []
        if rules:
            rules_page = self._render_rules_page(rules, timestamp)
            path = os.path.join(wiki_dir, "rules-manual.md")
            self._write_wiki_page(path, rules_page)
            pages_rendered += 1
        
        # 3. 渲染Core Memory快照页
        core_data = self.memory_manager.core.to_dict() if self.memory_manager.core else {}
        if core_data:
            core_page = self._render_core_page(core_data, timestamp)
            path = os.path.join(wiki_dir, "core-memory.md")
            self._write_wiki_page(path, core_page)
            pages_rendered += 1
        
        # 4. 渲染索引页（始终渲染）
        index_page = self._render_index_page(patterns, rules, timestamp, pages_rendered)
        path = os.path.join(wiki_dir, "README.md")
        self._write_wiki_page(path, index_page)
        pages_rendered += 1
        
        # 5. 增量变更日志
        changelog_path = os.path.join(wiki_dir, "changelog.md")
        self._append_changelog(changelog_path, log, patterns, rules, timestamp)
        pages_rendered += 1
        
        logger.info(f"[Sleeptime] Phase 5 (WIKI): Rendered {pages_rendered} pages to {wiki_dir}")
        return {"pages_rendered": pages_rendered}
    
    def _render_index_page(self, patterns, rules, timestamp, pages_count) -> str:
        """渲染WIKI索引页"""
        pattern_count = len(patterns) if patterns else 0
        rule_count = len(rules) if rules else 0
        
        return f"""# 🌙 Sleeptime WIKI

> 自动沉淀的知识文档 — 每次"做梦"后增量更新  
> 最后更新: {timestamp} | 本轮渲染: {pages_count}页

## 📑 导航

| 页面 | 内容 | 条目数 |
|------|------|--------|
| [模式发现](patterns.md) | 从交互中提取的重复模式 | {pattern_count} |
| [规则手册](rules-manual.md) | 沉淀的可复用规则 | {rule_count} |
| [Core Memory](core-memory.md) | 当前活跃知识快照 | — |
| [变更日志](changelog.md) | 每次dream的增量记录 | — |

## 统计

- 累计做梦: {len(self._dream_log) + 1}次
- 累计模式: {len(self._patterns)}个
- 累计规则: {rule_count}条

---

*此WIKI由Sleeptime Engine自动生成，借鉴Mira LLM WIKI的"夜间知识沉淀"思路*
"""
    
    def _render_patterns_page(self, patterns: List[Pattern], timestamp: str) -> str:
        """渲染模式发现页"""
        lines = [
            f"# 🔍 模式发现",
            f"",
            f"> 每次'做梦'从交互中提取的重复模式",
            f"> 最后更新: {timestamp}",
            f"",
        ]
        
        for p in patterns:
            confidence_bar = "█" * int(p.confidence * 10) + "░" * (10 - int(p.confidence * 10))
            lines.append(f"### {p.pattern_id}: {p.description}")
            lines.append(f"")
            lines.append(f"- 频率: {p.frequency}次")
            lines.append(f"- 置信度: {confidence_bar} {p.confidence:.0%}")
            if p.episode_ids:
                lines.append(f"- 来源情节: {', '.join(p.episode_ids[:5])}")
            lines.append(f"")
        
        return "\n".join(lines)
    
    def _render_rules_page(self, rules, timestamp: str) -> str:
        """渲染规则手册页"""
        lines = [
            f"# 📏 规则手册",
            f"",
            f"> 从模式中提炼的可复用规则，按置信度排序",
            f"> 最后更新: {timestamp}",
            f"",
        ]
        
        # 按置信度排序
        sorted_rules = sorted(rules, key=lambda r: getattr(r, 'confidence', 0), reverse=True)
        
        for r in sorted_rules:
            confidence = getattr(r, 'confidence', 0.5)
            condition = getattr(r, 'condition', '—')
            action = getattr(r, 'action', '—')
            success_rate = getattr(r, 'success_rate', None)
            
            confidence_emoji = "🟢" if confidence >= 0.7 else "🟡" if confidence >= 0.5 else "🔴"
            lines.append(f"### {confidence_emoji} {condition}")
            lines.append(f"")
            lines.append(f"→ {action}")
            lines.append(f"- 置信度: {confidence:.0%}")
            if success_rate is not None:
                lines.append(f"- 成功率: {success_rate:.0%}")
            lines.append(f"")
        
        return "\n".join(lines)
    
    def _render_core_page(self, core_data: Dict, timestamp: str) -> str:
        """渲染Core Memory快照页"""
        lines = [
            f"# 🧠 Core Memory 快照",
            f"",
            f"> Agent当前活跃知识的实时快照",
            f"> 最后更新: {timestamp}",
            f"",
        ]
        
        for section, content in core_data.items():
            if isinstance(content, str) and content.strip():
                lines.append(f"## {section}")
                lines.append(f"")
                lines.append(content)
                lines.append(f"")
        
        return "\n".join(lines)
    
    def _write_wiki_page(self, path: str, content: str):
        """写入WIKI页面"""
        try:
            with open(path, 'w', encoding='utf-8') as f:
                f.write(content)
        except Exception as e:
            logger.warning(f"[Sleeptime] Failed to write WIKI page {path}: {e}")
    
    def _append_changelog(self, path: str, log: DreamLog, patterns, rules, timestamp: str):
        """追加变更日志"""
        try:
            # 如果文件不存在，先写header
            if not os.path.exists(path):
                header = "# 📋 变更日志\n\n> 每次'做梦'后的增量更新记录\n\n---\n\n"
                with open(path, 'w', encoding='utf-8') as f:
                    f.write(header)
            
            entry = f"""### {log.dream_id} — {timestamp}

- 模式发现: {len(patterns) if patterns else 0}个
- 规则创建: {log.rules_created} / 更新: {log.rules_updated}
- 记忆衰减: {log.memories_decayed} / 遗忘: {log.memories_forgotten}
- Core同步: {'✅' if log.core_updated else '⏭️'}
- 冲突解决: {log.conflicts_resolved}个

---

"""
            with open(path, 'a', encoding='utf-8') as f:
                f.write(entry)
        except Exception as e:
            logger.warning(f"[Sleeptime] Failed to append changelog: {e}")

    def get_dream_history(self, limit: int = 10) -> List[Dict]:
        """获取做梦历史"""
        return [d.to_dict() for d in self._dream_log[-limit:]]

    def get_stats(self) -> Dict:
        """统计信息"""
        return {
            "total_dreams": len(self._dream_log),
            "last_dream_time": self._last_dream_time,
            "patterns_cached": len(self._patterns),
            "dream_interval": self.dream_interval,
            "should_dream": self.should_dream(),
        }
