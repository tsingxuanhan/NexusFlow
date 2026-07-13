# -*- coding: utf-8 -*-
"""
铉枢·炉守 Memory Manager — Letta三层记忆统一管理
XuanHub Memory Manager — Unified 3-Layer Memory Orchestration

核心调度器，统一管理Core/Archival/Recall三层记忆：
- Agent交互自动路由到对应记忆层
- 对话结束/Agent空闲时触发Sleeptime整理
- 记忆冲突检测与解决
- 对外提供统一接口：remember/recall/think
"""

import json
import time
import logging
import os
from typing import Any, Dict, List, Optional, Tuple
from dataclasses import dataclass, field

from core_memory import CoreMemory, CoreBlock, create_core_memory_with_defaults
from archival_memory import ArchivalMemory, ArchivalEntry
from recall_memory import RecallMemory, Episode, ProceduralRule, EpisodeType

logger = logging.getLogger("MemoryManager")


class MemoryManager:
    """
    Letta三层记忆统一管理器

    三层分工：
    - Core: 直接注入prompt（用户画像/Agent状态/行为规则）— 延迟0
    - Archival: 持久知识检索（文档/事实/概念）— 延迟~20ms
    - Recall: 时序经验回忆（交互记录/经验/可遗忘）— 延迟~5ms

    用法：
        mm = MemoryManager()
        mm.remember("用户偏好DeepSeek API优先", memory_type="core", block="user_profile")
        mm.remember("SSC水泥的纳米SiO2改性可提升强度", memory_type="archival", domain="materials")
        mm.remember("数据清洗任务失败，Flash更适合", memory_type="recall", episode_type=EpisodeType.ERROR)

        # 检索
        context = mm.recall("纳米改性SSC")
        prompt = mm.get_core_prompt()
    """

    def __init__(
        self,
        data_dir: str = "data",
        core_max_tokens: int = 4000,
        archival_chunk_size: int = 500,
        recall_max_episodes: int = 1000,
        api_endpoint: Optional[str] = None,
        api_key: Optional[str] = None,
    ):
        self.data_dir = data_dir
        os.makedirs(data_dir, exist_ok=True)

        # 三层记忆
        self.core = create_core_memory_with_defaults(
            persist_path=os.path.join(data_dir, "core_memory.json"),
        )
        self.core.max_total_tokens = core_max_tokens

        self.archival = ArchivalMemory(
            persist_path=os.path.join(data_dir, "archival_memory.json"),
            chunk_size=archival_chunk_size,
        )

        self.recall = RecallMemory(
            persist_path=os.path.join(data_dir, "recall_memory.json"),
            rules_path=os.path.join(data_dir, "procedural_rules.json"),
            max_episodes=recall_max_episodes,
            api_endpoint=api_endpoint,
            api_key=api_key,
        )

        # Phase 7: 第四层 — Global Memory Pool（跨Agent推理产物汇聚）
        self.global_pool = None
        try:
            from adaptive_context_manager import GlobalMemoryPool
            self.global_pool = GlobalMemoryPool(backing_store=self.archival)
        except ImportError:
            logger.warning("[MemoryManager] adaptive_context_manager not available, global_pool disabled")

        # 冲突检测缓存
        self._conflict_cache: List[Dict] = []

        logger.info(
            f"[MemoryManager] Initialized: "
            f"Core({self.core.estimate_total_tokens()}tokens), "
            f"Archival({len(self.archival.entries)}entries), "
            f"Recall({len(self.recall.episodes)}episodes, {len(self.recall.rules)}rules)"
        )

    # ============ 统一写入接口 ============

    def remember(
        self,
        content: str,
        memory_type: str = "auto",
        # Core参数
        block: Optional[str] = None,
        # Archival参数
        domain: str = "general",
        source: str = "",
        importance: float = 0.5,
        # Recall参数
        episode_type: EpisodeType = EpisodeType.INTERACTION,
        outcome: str = "",
        lessons: str = "",
        tags: Optional[List[str]] = None,
    ) -> str:
        """
        统一记忆写入接口

        memory_type:
        - "core": 写入Core Memory（直接注入prompt）
        - "archival": 写入Archival Memory（持久知识）
        - "recall": 写入Recall Memory（时序经验）
        - "auto": 自动判断（默认）
        """
        if memory_type == "auto":
            memory_type = self._classify_memory(content, importance)

        if memory_type == "core":
            target_block = block or "active_context"
            self.core.update(target_block, content)
            return f"core:{target_block}"

        elif memory_type == "archival":
            eid = self.archival.store(
                content=content,
                source=source,
                domain=domain,
                importance=importance,
            )
            return f"archival:{eid}"

        elif memory_type == "recall":
            ep_id = self.recall.record(
                content=content,
                episode_type=episode_type,
                importance=importance,
                tags=tags,
                outcome=outcome,
                lessons=lessons,
            )
            return f"recall:{ep_id}"

        else:
            logger.warning(f"[MemoryManager] Unknown memory_type: {memory_type}")
            return ""

    def remember_batch(self, items: List[Dict]) -> List[str]:
        """批量写入"""
        return [self.remember(**item) for item in items]

    def remember_global(self, agent_id: str, conclusion: Any, memory_type: str = "conclusion") -> str:
        """Phase 7: Agent提交推理产物到全局记忆"""
        if not self.global_pool:
            return ""
        self.global_pool.add_conclusion(agent_id, conclusion)
        content = conclusion if isinstance(conclusion, str) else getattr(conclusion, 'conclusion', str(conclusion))
        self.archival.store(content=content, source=f"global_pool:{agent_id}", domain="global_memory", importance=0.5)
        return f"global:{memory_type}:{agent_id}"
    
    def recall_global(self, query: str, top_k: int = 5) -> List[Any]:
        """Phase 7: 从全局记忆中检索"""
        if not self.global_pool:
            return []
        return self.global_pool.semantic_search(query, top_k)

    # ============ 统一检索接口 ============

    def recall_memory(
        self,
        query: str,
        top_k: int = 5,
        include_core: bool = True,
        include_archival: bool = True,
        include_recall: bool = True,
        domain: Optional[str] = None,
        multi_hop: bool = False,
        max_hops: int = 3,
    ) -> Dict[str, List]:
        """
        统一检索接口 — 跨三层检索

        Returns:
            {
                "core": [str, ...],       # Core Memory匹配块
                "archival": [ArchivalEntry, ...],
                "recall": [Episode, ...],
            }
        """
        results = {
            "core": [],
            "archival": [],
            "recall": [],
        }

        # Core: 总是返回全部（直接注入）
        if include_core:
            results["core"] = self.core.to_system_prompt()

        # Archival: RRF检索或Multi-hop
        if include_archival:
            if multi_hop:
                results["archival"] = self.archival.search_multi_hop(
                    query, max_hops=max_hops, top_k_per_hop=top_k
                )
            else:
                results["archival"] = self.archival.search(query, top_k=top_k, domain=domain)

        # Recall: 时序+相关性检索
        if include_recall:
            results["recall"] = self.recall.recall(query, top_k=top_k)

        return results

    def get_context_for_prompt(
        self,
        query: str,
        max_tokens: int = 2000,
        include_archival: bool = True,
        include_recall: bool = True,
    ) -> str:
        """
        获取适合注入LLM的上下文字符串

        三层结果合并为一个prompt片段，带token限制
        """
        parts = []

        # Core Memory（最高优先级）
        core_prompt = self.core.to_system_prompt()
        if core_prompt:
            parts.append(core_prompt)

        # Archival Memory
        if include_archival:
            archival_results = self.archival.search(query, top_k=3)
            if archival_results:
                archival_text = "## 相关知识\n"
                for entry in archival_results:
                    archival_text += f"- [{entry.domain}] {entry.content[:200]}\n"
                parts.append(archival_text)

        # Recall Memory
        if include_recall:
            recall_results = self.recall.recall(query, top_k=3)
            if recall_results:
                recall_text = "## 相关经验\n"
                for ep in recall_results:
                    recall_text += f"- {ep.content[:150]}"
                    if ep.lessons:
                        recall_text += f" → 教训: {ep.lessons[:80]}"
                    recall_text += "\n"
                parts.append(recall_text)

        context = "\n\n".join(parts)

        # Token截断
        estimated_tokens = len(context) // 3
        if estimated_tokens > max_tokens:
            max_chars = max_tokens * 3
            context = context[:max_chars] + "\n..."

        return context

    # ============ Sleeptime集成 ============

    def sleeptime_consolidate(self) -> Dict:
        """
        Sleeptime整理 — Agent空闲时调用

        流程：
        1. Recall衰减（D-MEM）
        2. 从情节提炼规则
        3. 规则同步到Core Memory
        4. 冲突检测与解决
        """
        result = {
            "decayed": 0,
            "forgettable": 0,
            "rules_extracted": 0,
            "core_updated": False,
            "conflicts": 0,
        }

        # Step 1: Recall衰减
        decay_result = self.recall.decay(force=True)
        result["decayed"] = decay_result["decayed"]
        result["forgettable"] = decay_result["forgettable"]

        # Step 2: 提炼规则
        new_rules = self.recall.extract_rules_from_episodes()
        result["rules_extracted"] = len(new_rules)

        # Step 3: 同步高置信规则到Core Memory
        reliable_rules = self.recall.get_rules(min_confidence=0.6)
        if reliable_rules:
            rules_text = "\n".join(
                f"- {r.condition} → {r.action} (置信度:{r.confidence:.0%})"
                for r in reliable_rules[:10]  # 最多10条
            )
            self.core.update("procedural", rules_text)
            result["core_updated"] = True

        # Step 4: 冲突检测
        conflicts = self.detect_conflicts()
        result["conflicts"] = len(conflicts)
        self._conflict_cache = conflicts

        logger.info(
            f"[MemoryManager] Sleeptime consolidate: "
            f"decayed={result['decayed']}, rules={result['rules_extracted']}, "
            f"conflicts={result['conflicts']}"
        )
        return result

    # ============ 冲突检测 ============

    def detect_conflicts(self) -> List[Dict]:
        """
        检测记忆冲突

        冲突类型：
        1. Core和Archival矛盾
        2. Recall中的对立经验
        3. 规则间矛盾
        """
        conflicts = []

        # 规则间矛盾：条件相似但动作相反
        rules = list(self.recall.rules.values())
        for i, r1 in enumerate(rules):
            for r2 in rules[i+1:]:
                # 条件相似度
                cond_overlap = len(
                    set(r1.condition.lower().split()) & set(r2.condition.lower().split())
                ) / max(len(set(r1.condition.lower().split()) | set(r2.condition.lower().split())), 1)

                if cond_overlap > 0.5:
                    # 动作是否矛盾
                    act_overlap = len(
                        set(r1.action.lower().split()) & set(r2.action.lower().split())
                    ) / max(len(set(r1.action.lower().split()) | set(r2.action.lower().split())), 1)

                    if act_overlap < 0.3:  # 条件相似但动作不同
                        conflicts.append({
                            "type": "rule_conflict",
                            "rule_1": r1.rule_id,
                            "rule_2": r2.rule_id,
                            "condition_similarity": round(cond_overlap, 2),
                            "action_similarity": round(act_overlap, 2),
                        })

        return conflicts

    # ============ 知识库管理 ============

    def ingest_knowledge_file(
        self,
        file_path: str,
        domain: str = "general",
        importance: float = 0.5,
    ) -> List[str]:
        """摄入知识文件"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
        except Exception as e:
            logger.error(f"[MemoryManager] Failed to read {file_path}: {e}")
            return []

        source = os.path.basename(file_path)
        return self.archival.ingest_document(
            content=content,
            source=source,
            domain=domain,
            importance=importance,
        )

    def ingest_knowledge_dir(
        self,
        dir_path: str,
        domain: str = "general",
        importance: float = 0.5,
    ) -> Dict[str, List[str]]:
        """批量摄入知识目录"""
        results = {}
        for fname in os.listdir(dir_path):
            if fname.endswith(('.md', '.txt', '.json')):
                fpath = os.path.join(dir_path, fname)
                entry_ids = self.ingest_knowledge_file(fpath, domain=domain, importance=importance)
                results[fname] = entry_ids
                logger.info(f"[MemoryManager] Ingested {fname}: {len(entry_ids)} entries")
        return results

    # ============ 自动分类 ============

    def _classify_memory(self, content: str, importance: float = 0.5) -> str:
        """
        自动判断记忆应存储到哪一层

        启发式规则：
        - 包含"偏好"/"规则"/"画像" → Core
        - 包含事实/定义/概念 → Archival
        - 包含经验/错误/交互 → Recall
        - 高重要性(>0.8) → Core候选
        """
        core_keywords = ["偏好", "规则", "画像", "设定", "配置", "身份", "名字"]
        archival_keywords = ["定义", "概念", "原理", "公式", "方法", "理论", "研究", "发现"]
        recall_keywords = ["经验", "错误", "失败", "尝试", "交互", "遇到", "发现"]

        content_lower = content.lower()

        core_score = sum(1 for kw in core_keywords if kw in content_lower)
        archival_score = sum(1 for kw in archival_keywords if kw in content_lower)
        recall_score = sum(1 for kw in recall_keywords if kw in content_lower)

        if core_score > archival_score and core_score > recall_score:
            return "core"
        if archival_score > recall_score:
            return "archival"
        if recall_score > 0:
            return "recall"

        # 默认：高重要性→Core，否则→Archival
        if importance >= 0.8:
            return "core"
        return "archival"

    # ============ 统计 ============

    def get_stats(self) -> Dict:
        """三层记忆综合统计"""
        core_stats = self.core.get_stats()
        archival_stats = self.archival.get_stats()
        recall_stats = self.recall.get_stats()

        return {
            "core": core_stats,
            "archival": archival_stats,
            "recall": recall_stats,
            "total_entries": (
                core_stats.get("active_blocks", 0)
                + archival_stats.get("total_entries", 0)
                + recall_stats.get("total_episodes", 0)
            ),
            "total_rules": recall_stats.get("total_rules", 0),
        }

    def get_summary(self) -> str:
        """人类可读的三层记忆摘要"""
        stats = self.get_stats()
        return (
            f"🧠 记忆系统状态:\n"
            f"  Core: {stats['core']['active_blocks']}块, {stats['core']['total_tokens']}tokens\n"
            f"  Archival: {stats['archival']['total_entries']}条知识, 领域{stats['archival']['domains']}\n"
            f"  Recall: {stats['recall']['total_episodes']}段经验, {stats['recall']['total_rules']}条规则, "
            f"{stats['recall']['forgettable']}可遗忘"
        )


def create_memory_manager(
    data_dir: str = "data",
    api_endpoint: Optional[str] = None,
    api_key: Optional[str] = None,
) -> MemoryManager:
    """工厂函数"""
    return MemoryManager(
        data_dir=data_dir,
        api_endpoint=api_endpoint,
        api_key=api_key,
    )
