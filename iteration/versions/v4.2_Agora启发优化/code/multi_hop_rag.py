# -*- coding: utf-8 -*-
"""
铉枢·炉守 Multi-Hop RAG — 多跳检索引擎
XuanHub Multi-Hop RAG — Agentic Retrieval with Reference Chain Tracking

借鉴 Google Agentic RAG，支持跨文档/跨领域推理：
- 自动追踪引用链（最多N跳）
- 充分性检查（不充分→继续检索，充分→停止）
- 与Archival Memory深度集成
- CodeAct兼容：可作为工具被CodeAct调用
"""

import json
import time
import logging
import os
from typing import Any, Dict, List, Optional, Tuple
from dataclasses import dataclass, field

logger = logging.getLogger("MultiHopRAG")


@dataclass
class HopResult:
    """单跳检索结果"""
    hop_index: int                           # 第几跳
    query: str                               # 本跳查询
    entries: List[Dict] = field(default_factory=list)  # 检索到的条目摘要
    entry_count: int = 0                     # 条目数
    new_discoveries: int = 0                 # 新发现数
    sufficient: bool = False                 # 上下文是否充分

    def to_dict(self) -> Dict:
        return {
            "hop_index": self.hop_index,
            "query": self.query,
            "entry_count": self.entry_count,
            "new_discoveries": self.new_discoveries,
            "sufficient": self.sufficient,
        }


@dataclass
class MultiHopResult:
    """多跳检索完整结果"""
    original_query: str
    total_hops: int
    total_entries: int
    sufficient: bool                        # 最终充分性判断
    hop_details: List[HopResult] = field(default_factory=list)
    all_entries: List[Dict] = field(default_factory=list)  # 所有去重条目
    elapsed_time: float = 0

    def to_dict(self) -> Dict:
        return {
            "original_query": self.original_query,
            "total_hops": self.total_hops,
            "total_entries": self.total_entries,
            "sufficient": self.sufficient,
            "hop_details": [h.to_dict() for h in self.hop_details],
            "elapsed_time": self.elapsed_time,
        }

    def to_context_string(self, max_tokens: int = 2000) -> str:
        """转为可注入prompt的上下文字符串"""
        parts = []
        for entry in self.all_entries:
            domain = entry.get("domain", "")
            content = entry.get("content", "")
            source = entry.get("source", "")
            line = f"- [{domain}] {content[:300]}"
            if source:
                line += f" (来源: {source})"
            parts.append(line)

        context = "\n".join(parts)
        # Token截断
        if len(context) > max_tokens * 3:
            context = context[:max_tokens * 3] + "\n...(截断)"
        return context


class MultiHopRAG:
    """
    多跳检索 — Agentic RAG

    核心创新（借鉴Google Agentic RAG）：
    1. 每跳检索后评估"上下文充分性"
    2. 不充分 → 自动生成新查询词继续检索
    3. 充分 → 停止，返回结果
    4. 引用链追踪：记录每一跳的查询和发现

    示例：
        Q: "SSC的纳米改性对混凝土耐久性的影响"
        Hop1: 检索"SSC纳米改性" → 发现"孔结构优化"
        Hop2: 检索"孔结构优化+耐久性" → 发现"碳化深度降低30%"
        Hop3: 充分性检查通过 → 返回

    用法：
        rag = MultiHopRAG(archival_memory)
        result = rag.retrieve("SSC的纳米改性对混凝土耐久性的影响", max_hops=3)
        context = result.to_context_string()
    """

    def __init__(
        self,
        archival_memory=None,
        max_hops: int = 3,
        top_k_per_hop: int = 5,
        sufficient_threshold: float = 0.7,
        min_new_discoveries: int = 1,
        api_endpoint: Optional[str] = None,
        api_key: Optional[str] = None,
    ):
        self.archival = archival_memory
        self.max_hops = max_hops
        self.top_k_per_hop = top_k_per_hop
        self.sufficient_threshold = sufficient_threshold
        self.min_new_discoveries = min_new_discoveries
        self.api_endpoint = api_endpoint
        self.api_key = api_key

    def retrieve(
        self,
        query: str,
        max_hops: Optional[int] = None,
        domain: Optional[str] = None,
    ) -> MultiHopResult:
        """
        执行多跳检索

        Args:
            query: 初始查询
            max_hops: 最大跳数
            domain: 领域过滤

        Returns:
            MultiHopResult
        """
        start_time = time.time()
        max_hops = max_hops or self.max_hops

        all_entry_ids: set = set()
        all_entries: List[Dict] = []
        hop_details: List[HopResult] = []
        current_query = query
        sufficient = False

        for hop_idx in range(max_hops):
            # 执行本跳检索
            if self.archival:
                results = self.archival.search(
                    current_query, top_k=self.top_k_per_hop, domain=domain
                )
                hop_entries = [
                    {
                        "entry_id": e.entry_id,
                        "content": e.content,
                        "domain": e.domain,
                        "source": e.source,
                        "importance": e.importance,
                    }
                    for e in results
                ]
            else:
                hop_entries = []

            # 去重 + 统计新发现
            new_discoveries = 0
            for entry in hop_entries:
                eid = entry["entry_id"]
                if eid not in all_entry_ids:
                    all_entry_ids.add(eid)
                    all_entries.append(entry)
                    new_discoveries += 1

            # 充分性检查
            sufficient = self._check_sufficiency(
                query=query,
                all_entries=all_entries,
                hop_idx=hop_idx,
                new_discoveries=new_discoveries,
            )

            hop_result = HopResult(
                hop_index=hop_idx,
                query=current_query,
                entries=hop_entries,
                entry_count=len(hop_entries),
                new_discoveries=new_discoveries,
                sufficient=sufficient,
            )
            hop_details.append(hop_result)

            logger.debug(
                f"[MultiHopRAG] Hop {hop_idx}: query='{current_query[:30]}...', "
                f"found={len(hop_entries)}, new={new_discoveries}, sufficient={sufficient}"
            )

            # 充分 → 停止
            if sufficient:
                break

            # 无新发现 → 停止
            if new_discoveries == 0:
                break

            # 生成下一跳查询
            next_query = self._generate_next_query(
                original_query=query,
                current_query=current_query,
                hop_entries=hop_entries,
            )

            if next_query == current_query:
                break  # 查询没变化，停止

            current_query = next_query

        elapsed = time.time() - start_time

        result = MultiHopResult(
            original_query=query,
            total_hops=len(hop_details),
            total_entries=len(all_entries),
            sufficient=sufficient,
            hop_details=hop_details,
            all_entries=all_entries,
            elapsed_time=elapsed,
        )

        logger.info(
            f"[MultiHopRAG] Query: '{query[:30]}...' → "
            f"{result.total_hops} hops, {result.total_entries} entries, "
            f"sufficient={sufficient}, {elapsed:.2f}s"
        )
        return result

    def _check_sufficiency(
        self,
        query: str,
        all_entries: List[Dict],
        hop_idx: int,
        new_discoveries: int,
    ) -> bool:
        """
        充分性检查 — Google Agentic RAG关键创新

        判断标准：
        1. 至少3条相关结果
        2. 平均重要性 >= 阈值
        3. 最近2跳没有新发现（说明已收敛）
        4. 已到最大跳数
        """
        if len(all_entries) < 3:
            return False

        # 平均重要性
        if all_entries:
            avg_importance = sum(e.get("importance", 0.5) for e in all_entries) / len(all_entries)
            if avg_importance >= self.sufficient_threshold:
                return True

        # 收敛：最近一跳没有新发现
        if hop_idx > 0 and new_discoveries == 0:
            return True

        # 已到最大跳数
        if hop_idx >= self.max_hops - 1:
            return True

        return False

    def _generate_next_query(
        self,
        original_query: str,
        current_query: str,
        hop_entries: List[Dict],
    ) -> str:
        """
        生成下一跳查询

        策略：
        1. 从本跳结果中提取高频关键词
        2. 与原始查询组合
        3. 尝试用LLM生成更精确的查询（如果API可用）
        """
        if not hop_entries:
            return current_query

        # 提取关键词
        combined_text = " ".join(e.get("content", "")[:200] for e in hop_entries)
        keywords = self._extract_keywords(combined_text)

        if not keywords:
            return current_query

        # 组合新查询：原始查询 + 高频关键词
        top_keywords = keywords[:3]
        new_query = original_query.split()[0] if original_query.split() else original_query
        new_query += " " + " ".join(top_keywords)

        # 尝试用LLM生成更精确查询
        if self.api_endpoint and len(hop_entries) >= 2:
            llm_query = self._llm_generate_query(original_query, hop_entries)
            if llm_query:
                new_query = llm_query

        return new_query

    def _extract_keywords(self, text: str) -> List[str]:
        """从文本中提取高频关键词"""
        stopwords = {"的", "了", "是", "在", "和", "与", "或", "a", "an", "the",
                      "is", "are", "was", "were", "in", "on", "at", "of", "and", "or",
                      "for", "to", "that", "this", "with", "from", "by", "as"}

        word_freq: Dict[str, int] = {}
        for word in text.lower().split():
            clean = ''.join(c for c in word if c.isalnum() or '\u4e00' <= c <= '\u9fff')
            if clean and len(clean) > 2 and clean not in stopwords:
                word_freq[clean] = word_freq.get(clean, 0) + 1

        sorted_words = sorted(word_freq.items(), key=lambda x: x[1], reverse=True)
        return [w for w, _ in sorted_words[:5]]

    def _llm_generate_query(self, original_query: str, entries: List[Dict]) -> Optional[str]:
        """用LLM生成更精确的下一跳查询"""
        try:
            import urllib.request

            entry_summaries = "\n".join(
                f"- {e.get('content', '')[:150]}" for e in entries[:5]
            )

            prompt = f"""基于以下检索结果，生成一个更精确的搜索查询来找到更多相关信息。
只输出查询文本，不要解释。

原始查询: {original_query}

当前检索结果:
{entry_summaries}

更精确的查询:"""

            payload = {
                "model": "deepseek-chat",
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": 50,
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

            with urllib.request.urlopen(req, timeout=10) as resp:
                result = json.loads(resp.read().decode('utf-8'))
                query = result['choices'][0]['message']['content'].strip()
                if query and len(query) > 3:
                    return query

        except Exception as e:
            logger.debug(f"[MultiHopRAG] LLM query generation failed: {e}")

        return None

    def to_codeact_globals(self) -> Dict:
        """导出为CodeAct全局函数"""
        return {
            "multi_hop_search": self._codeact_search,
        }

    def _codeact_search(self, query: str, max_hops: int = 3) -> str:
        """CodeAct兼容的多跳搜索"""
        result = self.retrieve(query, max_hops=max_hops)
        return result.to_context_string()

    def get_stats(self) -> Dict:
        """统计信息"""
        return {
            "max_hops": self.max_hops,
            "top_k_per_hop": self.top_k_per_hop,
            "sufficient_threshold": self.sufficient_threshold,
            "archival_entries": len(self.archival.entries) if self.archival else 0,
        }
