# -*- coding: utf-8 -*-
"""
铉枢·炉守 Archival Memory — 归档记忆层
XuanHub Archival Memory — Persistent Knowledge with Hybrid Retrieval

Letta三层架构第二层：持久事实与知识库，需要检索
- 容量大(无上限)，需要检索
- 复用NGramTF-IDF + 关键词混合检索(RRF融合)
- 支持文档分块、多跳检索
- 类比：硬盘
"""

import json
import time
import logging
import os
import math
from typing import Any, Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from abc import ABC, abstractmethod

logger = logging.getLogger("ArchivalMemory")


@dataclass
class ArchivalEntry:
    """归档记忆条目"""
    entry_id: str
    content: str                             # 文本内容
    source: str = ""                         # 来源（文件名/URL/Agent生成）
    domain: str = "general"                  # 领域标签
    importance: float = 0.5                  # 重要性
    created_at: float = field(default_factory=time.time)
    accessed_at: float = field(default_factory=time.time)
    access_count: int = 0                    # 访问次数
    metadata: Dict = field(default_factory=dict)
    # 向量由索引器管理，不序列化

    def to_dict(self) -> Dict:
        return {
            "entry_id": self.entry_id,
            "content": self.content,
            "source": self.source,
            "domain": self.domain,
            "importance": self.importance,
            "created_at": self.created_at,
            "accessed_at": self.accessed_at,
            "access_count": self.access_count,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, d: Dict) -> "ArchivalEntry":
        return cls(
            entry_id=d["entry_id"],
            content=d["content"],
            source=d.get("source", ""),
            domain=d.get("domain", "general"),
            importance=d.get("importance", 0.5),
            created_at=d.get("created_at", time.time()),
            accessed_at=d.get("accessed_at", time.time()),
            access_count=d.get("access_count", 0),
            metadata=d.get("metadata", {}),
        )


class ArchivalIndex(ABC):
    """归档索引抽象"""

    @abstractmethod
    def add(self, entry: ArchivalEntry) -> None:
        pass

    @abstractmethod
    def search(self, query: str, top_k: int = 5) -> List[Tuple[str, float]]:
        """返回 [(entry_id, score), ...]"""
        pass

    @abstractmethod
    def remove(self, entry_id: str) -> bool:
        pass

    @abstractmethod
    def count(self) -> int:
        pass


class NGramTFIDFIndex(ArchivalIndex):
    """
    N-gram TF-IDF 索引 — 复用vector_memory的NGramTFIDFProvider

    支持中英文混合、子词匹配
    """

    def __init__(self, dimension: int = 5000):
        self.dimension = dimension
        self.vocab: Dict[str, int] = {}
        self.idf: Dict[str, float] = {}
        self.doc_count: int = 0
        self._next_idx: int = 0
        # entry_id -> 向量
        self._vectors: Dict[str, List[float]] = {}

    def _is_chinese(self, char: str) -> bool:
        return '\u4e00' <= char <= '\u9fff'

    def _tokenize(self, text: str) -> List[str]:
        tokens = []
        for word in text.lower().split():
            clean = ''.join(c for c in word if c.isalnum() or self._is_chinese(c))
            if clean:
                tokens.append(clean)
                if any(self._is_chinese(c) for c in clean):
                    tokens.extend(list(clean))
        return tokens

    def _get_ngrams(self, tokens: List[str]) -> Dict[str, float]:
        ngrams: Dict[str, float] = {}
        for token in tokens:
            ngrams[token] = ngrams.get(token, 0) + 1.0
            if len(token) >= 3:
                for i in range(len(token) - 2):
                    ng = token[i:i+3]
                    ngrams[ng] = ngrams.get(ng, 0) + 0.5
            if len(token) >= 4:
                for i in range(len(token) - 3):
                    ng = token[i:i+4]
                    ngrams[ng] = ngrams.get(ng, 0) + 0.3
        for i in range(len(tokens) - 1):
            bigram = tokens[i] + '_' + tokens[i+1]
            ngrams[bigram] = ngrams.get(bigram, 0) + 1.0
        return ngrams

    def _embed(self, text: str) -> List[float]:
        tokens = self._tokenize(text)
        ngrams = self._get_ngrams(tokens)
        vector = [0.0] * self.dimension

        for ng, tf in ngrams.items():
            if ng in self.vocab:
                idx = self.vocab[ng]
            elif self._next_idx < self.dimension:
                idx = self._next_idx
                self.vocab[ng] = idx
                self._next_idx += 1
            else:
                idx = hash(ng) % self.dimension
            idf_score = self.idf.get(ng, 1.0)
            vector[idx] += tf * idf_score

        norm = sum(v * v for v in vector) ** 0.5
        if norm > 0:
            vector = [v / norm for v in vector]
        return vector

    def _update_idf(self, text: str) -> None:
        self.doc_count += 1
        tokens = self._tokenize(text)
        ngrams = self._get_ngrams(tokens)
        for ng in ngrams:
            self.idf[ng] = self.idf.get(ng, 0) + 1
        for ng in self.idf:
            self.idf[ng] = math.log(self.doc_count / (1 + self.idf[ng]))

    def add(self, entry: ArchivalEntry) -> None:
        self._update_idf(entry.content)
        vector = self._embed(entry.content)
        self._vectors[entry.entry_id] = vector

    def search(self, query: str, top_k: int = 5) -> List[Tuple[str, float]]:
        if not self._vectors:
            return []
        query_vec = self._embed(query)
        scored = []
        for eid, vec in self._vectors.items():
            # 余弦相似度
            dot = sum(a * b for a, b in zip(query_vec, vec))
            na = sum(a * a for a in query_vec) ** 0.5
            nb = sum(b * b for b in vec) ** 0.5
            score = dot / (na * nb) if na > 0 and nb > 0 else 0.0
            scored.append((eid, score))
        scored.sort(key=lambda x: x[1], reverse=True)
        return scored[:top_k]

    def remove(self, entry_id: str) -> bool:
        if entry_id in self._vectors:
            del self._vectors[entry_id]
            return True
        return False

    def count(self) -> int:
        return len(self._vectors)


class KeywordIndex(ArchivalIndex):
    """
    关键词索引 — 精确匹配和前缀匹配
    用于补充向量检索的不足
    """

    def __init__(self):
        # keyword -> set of entry_ids
        self._index: Dict[str, set] = {}

    def _extract_keywords(self, text: str) -> List[str]:
        """提取关键词（简单分词+去停用词）"""
        stopwords = {"的", "了", "是", "在", "和", "与", "或", "a", "an", "the",
                      "is", "are", "was", "were", "in", "on", "at", "of", "and", "or"}
        words = text.lower().split()
        keywords = []
        for w in words:
            clean = ''.join(c for c in w if c.isalnum() or '\u4e00' <= c <= '\u9fff')
            if clean and clean not in stopwords and len(clean) > 1:
                keywords.append(clean)
        return keywords

    def add(self, entry: ArchivalEntry) -> None:
        keywords = self._extract_keywords(entry.content)
        # 同时索引domain和source
        keywords.extend([entry.domain, entry.source])
        for kw in keywords:
            if kw not in self._index:
                self._index[kw] = set()
            self._index[kw].add(entry.entry_id)

    def search(self, query: str, top_k: int = 5) -> List[Tuple[str, float]]:
        query_kws = self._extract_keywords(query)
        scores: Dict[str, float] = {}
        for kw in query_kws:
            # 精确匹配
            if kw in self._index:
                for eid in self._index[kw]:
                    scores[eid] = scores.get(eid, 0) + 1.0
            # 前缀匹配
            for idx_kw, eids in self._index.items():
                if idx_kw.startswith(kw) or kw.startswith(idx_kw):
                    for eid in eids:
                        scores[eid] = scores.get(eid, 0) + 0.5

        scored = list(scores.items())
        scored.sort(key=lambda x: x[1], reverse=True)
        return scored[:top_k]

    def remove(self, entry_id: str) -> bool:
        for kw in list(self._index.keys()):
            self._index[kw].discard(entry_id)
            if not self._index[kw]:
                del self._index[kw]
        return True

    def count(self) -> int:
        all_ids = set()
        for eids in self._index.values():
            all_ids.update(eids)
        return len(all_ids)


class ArchivalMemory:
    """
    归档记忆 — 持久知识，向量+关键词混合检索

    核心能力：
    1. store() — 存储知识条目（自动索引）
    2. search() — RRF融合检索
    3. search_multi_hop() — 多跳检索（自动追踪引用链）
    4. ingest_document() — 文档分块摄入

    用法：
        am = ArchivalMemory()
        am.store("SSC水泥的纳米SiO2改性可显著提升早期强度", domain="materials")
        results = am.search("纳米改性SSC", top_k=5)
    """

    def __init__(
        self,
        persist_path: str = "data/archival_memory.json",
        chunk_size: int = 500,
        chunk_overlap: int = 50,
        top_k: int = 5,
    ):
        self.persist_path = persist_path
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.top_k = top_k

        # 存储层
        self.entries: Dict[str, ArchivalEntry] = {}

        # 双索引
        self._ngram_index = NGramTFIDFIndex()
        self._keyword_index = KeywordIndex()
        
        # Nemotron 语义索引（延迟启用）
        self._nemotron_index = None  # Optional[NemotronIndexAdapter]

        # ID计数器
        self._id_counter = 0

        # 加载
        self._load()

    def store(
        self,
        content: str,
        source: str = "",
        domain: str = "general",
        importance: float = 0.5,
        metadata: Optional[Dict] = None,
    ) -> str:
        """
        存储知识条目

        Returns:
            entry_id
        """
        entry_id = f"arch_{self._id_counter}"
        self._id_counter += 1

        entry = ArchivalEntry(
            entry_id=entry_id,
            content=content,
            source=source,
            domain=domain,
            importance=importance,
            metadata=metadata or {},
        )

        self.entries[entry_id] = entry
        self._ngram_index.add(entry)
        self._keyword_index.add(entry)
        
        # 同步 Nemotron 索引（如果启用）
        if self._nemotron_index is not None:
            self._nemotron_index.add(entry_id, content)

        logger.debug(f"[ArchivalMemory] Stored entry '{entry_id}' ({domain}, {len(content)} chars)")
        self._auto_save()
        return entry_id

    def store_batch(self, items: List[Dict]) -> List[str]:
        """批量存储"""
        ids = []
        for item in items:
            eid = self.store(
                content=item["content"],
                source=item.get("source", ""),
                domain=item.get("domain", "general"),
                importance=item.get("importance", 0.5),
                metadata=item.get("metadata"),
            )
            ids.append(eid)
        return ids

    def enable_nemotron(self, embedding_provider) -> None:
        """
        启用 Nemotron 语义索引
        
        Args:
            embedding_provider: NemotronEmbeddingProvider 实例
        
        启用后，search() 将自动进行三路 RRF 融合检索
        """
        self._nemotron_index = _NemotronIndexAdapter(embedding_provider)
        
        # 对已有条目建立 Nemotron 索引
        for entry in self.entries.values():
            self._nemotron_index.add(entry.entry_id, entry.content)
        
        logger.info(
            f"[ArchivalMemory] Nemotron index enabled, "
            f"indexed {self._nemotron_index.count()} entries"
        )

    def search(
        self,
        query: str,
        top_k: Optional[int] = None,
        domain: Optional[str] = None,
        rrf_k: int = 60,
    ) -> List[ArchivalEntry]:
        """
        RRF融合检索 — 向量检索 + 关键词检索 [+ Nemotron语义检索]

        RRF公式: score = Σ(1 / (k + rank_i))
        两路或三路检索结果融合，比单一检索更鲁棒
        """
        top_k = top_k or self.top_k

        # 向量检索（TF-IDF n-gram）
        ngram_results = self._ngram_index.search(query, top_k=top_k * 2)
        # 关键词检索
        keyword_results = self._keyword_index.search(query, top_k=top_k * 2)

        # RRF融合
        rrf_scores: Dict[str, float] = {}

        for rank, (eid, _) in enumerate(ngram_results):
            rrf_scores[eid] = rrf_scores.get(eid, 0) + 1.0 / (rrf_k + rank + 1)

        for rank, (eid, _) in enumerate(keyword_results):
            rrf_scores[eid] = rrf_scores.get(eid, 0) + 1.0 / (rrf_k + rank + 1)

        # 第三路：Nemotron 语义检索（如果启用）
        if self._nemotron_index is not None:
            nemotron_results = self._nemotron_index.search(query, top_k=top_k * 2)
            for rank, (eid, _) in enumerate(nemotron_results):
                rrf_scores[eid] = rrf_scores.get(eid, 0) + 1.0 / (rrf_k + rank + 1)

        # 排序
        sorted_ids = sorted(rrf_scores.items(), key=lambda x: x[1], reverse=True)

        # 领域过滤
        results = []
        for eid, score in sorted_ids:
            if eid in self.entries:
                entry = self.entries[eid]
                if domain and entry.domain != domain:
                    continue
                entry.accessed_at = time.time()
                entry.access_count += 1
                results.append(entry)
            if len(results) >= top_k:
                break

        logger.debug(f"[ArchivalMemory] Search '{query[:30]}...' → {len(results)} results")
        return results

    def search_multi_hop(
        self,
        query: str,
        max_hops: int = 3,
        top_k_per_hop: int = 3,
        sufficient_context_threshold: float = 0.7,
    ) -> List[ArchivalEntry]:
        """
        多跳检索 — 自动追踪引用链

        借鉴 Google Agentic RAG:
        1. 初始检索
        2. 从结果中提取新查询词
        3. 继续检索直到上下文充分

        Args:
            query: 初始查询
            max_hops: 最大跳数
            top_k_per_hop: 每跳返回数
            sufficient_context_threshold: 充分性阈值(0-1)

        Returns:
            去重后的所有相关条目
        """
        all_results: Dict[str, ArchivalEntry] = {}
        current_query = query
        visited_queries = {query}

        for hop in range(max_hops):
            hop_results = self.search(current_query, top_k=top_k_per_hop)

            if not hop_results:
                break

            new_entries = 0
            for entry in hop_results:
                if entry.entry_id not in all_results:
                    all_results[entry.entry_id] = entry
                    new_entries += 1

            # 充分性检查：新跳没有新发现 → 停止
            if new_entries == 0:
                break

            # 上下文充分性检查（基于检索结果数量和重要性）
            avg_importance = sum(e.importance for e in all_results.values()) / len(all_results)
            if avg_importance >= sufficient_context_threshold and len(all_results) >= top_k_per_hop:
                break

            # 提取下一跳查询词
            # 从结果中抽取高权关键词作为新查询
            combined_text = " ".join(e.content[:200] for e in hop_results)
            next_query = self._extract_next_query(combined_text, query)

            if next_query in visited_queries:
                break
            visited_queries.add(next_query)
            current_query = next_query

            logger.debug(f"[ArchivalMemory] Multi-hop {hop+1}: '{current_query[:30]}...'")

        results = list(all_results.values())
        logger.info(f"[ArchivalMemory] Multi-hop search: {max_hops} hops, {len(results)} results")
        return results

    def _extract_next_query(self, text: str, original_query: str) -> str:
        """从检索结果中提取下一跳查询词"""
        # 简单策略：提取高频词 + 原始查询词组合
        words = text.lower().split()
        freq: Dict[str, int] = {}
        for w in words:
            clean = ''.join(c for c in w if c.isalnum() or '\u4e00' <= c <= '\u9fff')
            if clean and len(clean) > 2:
                freq[clean] = freq.get(clean, 0) + 1

        # 取top-3高频词
        top_words = sorted(freq.items(), key=lambda x: x[1], reverse=True)[:3]
        top_terms = [w for w, _ in top_words]

        # 与原始查询组合
        return original_query.split()[0] + " " + " ".join(top_terms) if top_terms else original_query

    def ingest_document(
        self,
        content: str,
        source: str = "",
        domain: str = "general",
        importance: float = 0.5,
    ) -> List[str]:
        """
        文档分块摄入

        将长文档按chunk_size分块，每块独立索引
        """
        if len(content) <= self.chunk_size:
            eid = self.store(content, source=source, domain=domain, importance=importance)
            return [eid]

        # 分块
        chunks = []
        start = 0
        while start < len(content):
            end = start + self.chunk_size
            chunk = content[start:end]

            # 尝试在句号/换行处切分
            if end < len(content):
                for sep in ['\n\n', '\n', '。', '.', '；', ';']:
                    last_sep = chunk.rfind(sep)
                    if last_sep > self.chunk_size * 0.5:
                        chunk = content[start:start + last_sep + 1]
                        end = start + last_sep + 1
                        break

            chunks.append(chunk.strip())
            start = end - self.chunk_overlap

        # 存储
        entry_ids = []
        for i, chunk in enumerate(chunks):
            if not chunk:
                continue
            eid = self.store(
                content=chunk,
                source=f"{source}#chunk{i}",
                domain=domain,
                importance=importance,
                metadata={"chunk_index": i, "total_chunks": len(chunks), "source": source},
            )
            entry_ids.append(eid)

        logger.info(f"[ArchivalMemory] Ingested '{source}': {len(chunks)} chunks, {len(content)} chars")
        return entry_ids

    def get(self, entry_id: str) -> Optional[ArchivalEntry]:
        """获取单条"""
        return self.entries.get(entry_id)

    def remove(self, entry_id: str) -> bool:
        """删除条目"""
        if entry_id in self.entries:
            del self.entries[entry_id]
            self._ngram_index.remove(entry_id)
            self._keyword_index.remove(entry_id)
            if self._nemotron_index is not None:
                self._nemotron_index.remove(entry_id)
            self._auto_save()
            return True
        return False

    def get_by_domain(self, domain: str) -> List[ArchivalEntry]:
        """按领域获取所有条目"""
        return [e for e in self.entries.values() if e.domain == domain]

    def get_stats(self) -> Dict:
        """统计信息"""
        domain_counts = {}
        for e in self.entries.values():
            domain_counts[e.domain] = domain_counts.get(e.domain, 0) + 1

        return {
            "total_entries": len(self.entries),
            "ngram_index_count": self._ngram_index.count(),
            "keyword_index_count": self._keyword_index.count(),
            "domains": domain_counts,
        }

    def to_dict(self) -> Dict:
        """序列化"""
        return {
            "id_counter": self._id_counter,
            "entries": {k: v.to_dict() for k, v in self.entries.items()},
        }

    @classmethod
    def from_dict(cls, d: Dict, persist_path: str = "data/archival_memory.json") -> "ArchivalMemory":
        """反序列化"""
        am = cls(persist_path=persist_path)
        am._id_counter = d.get("id_counter", 0)
        for k, v in d.get("entries", {}).items():
            entry = ArchivalEntry.from_dict(v)
            am.entries[k] = entry
            am._ngram_index.add(entry)
            am._keyword_index.add(entry)
        return am

    def _auto_save(self) -> None:
        """自动保存"""
        if not self.persist_path:
            return
        try:
            os.makedirs(os.path.dirname(self.persist_path) or '.', exist_ok=True)
            with open(self.persist_path, 'w', encoding='utf-8') as f:
                json.dump(self.to_dict(), f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.warning(f"[ArchivalMemory] Failed to save: {e}")

    def _load(self) -> None:
        """从文件加载（直接反序列化到self，避免from_dict→__init__→_load递归）"""
        if not self.persist_path or not os.path.exists(self.persist_path):
            return
        try:
            with open(self.persist_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            self._id_counter = data.get("id_counter", 0)
            for k, v in data.get("entries", {}).items():
                entry = ArchivalEntry.from_dict(v)
                self.entries[k] = entry
                self._ngram_index.add(entry)
                self._keyword_index.add(entry)
            logger.info(f"[ArchivalMemory] Loaded {len(self.entries)} entries from {self.persist_path}")
        except Exception as e:
            logger.warning(f"[ArchivalMemory] Failed to load: {e}")


class _NemotronIndexAdapter:
    """
    Nemotron 语义索引适配器 — 实现 ArchivalIndex 同等接口

    将 NemotronEmbeddingProvider 包装为 ArchivalMemory 可用的索引组件。
    用于 ArchivalMemory 的三路 RRF 检索。
    """

    def __init__(self, embedding_provider):
        self.embedding_provider = embedding_provider
        self._vectors: Dict[str, List[float]] = {}
        self._contents: Dict[str, str] = {}

    def _cosine(self, a: List[float], b: List[float]) -> float:
        if len(a) != len(b) or not a:
            return 0.0
        dot = sum(x * y for x, y in zip(a, b))
        na = sum(x * x for x in a) ** 0.5
        nb = sum(x * x for x in b) ** 0.5
        if na == 0 or nb == 0:
            return 0.0
        return dot / (na * nb)

    def add(self, entry_id: str, content: str) -> None:
        vec = self.embedding_provider.embed_document(content)
        self._vectors[entry_id] = vec
        self._contents[entry_id] = content

    def search(self, query: str, top_k: int = 5) -> List[Tuple[str, float]]:
        if not self._vectors:
            return []
        query_vec = self.embedding_provider.embed_query(query)
        scored = [
            (eid, self._cosine(query_vec, vec))
            for eid, vec in self._vectors.items()
        ]
        scored.sort(key=lambda x: x[1], reverse=True)
        return scored[:top_k]

    def remove(self, entry_id: str) -> bool:
        self._vectors.pop(entry_id, None)
        self._contents.pop(entry_id, None)
        return True

    def count(self) -> int:
        return len(self._vectors)
