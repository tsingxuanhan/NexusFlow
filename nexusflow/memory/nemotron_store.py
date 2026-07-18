# -*- coding: utf-8 -*-
"""
Nemotron 专用向量存储

与 PersistentVectorStore 完全独立：
- 使用 NemotronEmbeddingProvider 生成高维语义向量
- 独立持久化文件（data/nemotron_memory.json）
- 通过 RRF 与 BM25/TF-IDF 结果融合，不直接拼接向量维度

用法:
    from nexusflow.memory.nemotron_provider import NemotronEmbeddingProvider
    from nexusflow.memory.nemotron_store import NemotronVectorStore

    provider = NemotronEmbeddingProvider()
    store = NemotronVectorStore(provider)
    store.add("doc_1", "纳米SiO2对混凝土耐久性的影响...")
    results = store.search("SiO2 混凝土", top_k=5)
"""

import json
import logging
import math
import os
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger("NemotronStore")


def _cosine_similarity(a: List[float], b: List[float]) -> float:
    """余弦相似度"""
    if len(a) != len(b) or not a:
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(x * x for x in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


class NemotronVectorStore:
    """
    Nemotron 语义向量存储

    设计决策：
    - 独立于 PersistentVectorStore（维度不同，向量空间不兼容）
    - 使用 embed_query() 编码查询，embed_document() 编码文档
    - 独立持久化，不与 TF-IDF 向量混存
    """

    def __init__(
        self,
        embedding_provider,  # NemotronEmbeddingProvider
        persist_path: str = "./data/nemotron_memory.json",
        auto_save_interval: int = 10,
    ):
        self.embedding_provider = embedding_provider
        self.persist_path = persist_path
        self.auto_save_interval = auto_save_interval
        self._add_counter = 0

        # 存储: [{id, content, embedding, metadata}]
        self.entries: List[Dict] = []
        # ID 索引: id -> entry dict
        self._id_index: Dict[str, Dict] = {}

        # 确保持久化目录存在
        os.makedirs(os.path.dirname(persist_path) or '.', exist_ok=True)

        # 加载已有数据
        self._load()

    def add(
        self,
        entry_id: str,
        content: str,
        metadata: Optional[Dict] = None,
    ) -> None:
        """添加文档条目 — 使用 embed_document() 编码"""
        embedding = self.embedding_provider.embed_document(content)

        entry = {
            "id": entry_id,
            "content": content,
            "embedding": embedding,
            "metadata": metadata or {},
        }
        self.entries.append(entry)
        self._id_index[entry_id] = entry

        self._add_counter += 1
        if self._add_counter >= self.auto_save_interval:
            self.save()
            self._add_counter = 0

    def add_batch(
        self,
        items: List[Dict],
    ) -> None:
        """
        批量添加

        items: [{"id": str, "content": str, "metadata": dict}, ...]
        """
        contents = [item["content"] for item in items]
        embeddings = self.embedding_provider.embed_batch(contents)

        for item, embedding in zip(items, embeddings):
            entry = {
                "id": item["id"],
                "content": item["content"],
                "embedding": embedding,
                "metadata": item.get("metadata", {}),
            }
            self.entries.append(entry)
            self._id_index[item["id"]] = entry

        self.save()
        logger.info(f"[NemotronStore] Batch added {len(items)} entries")

    def search(self, query: str, top_k: int = 5) -> List[Tuple[str, float]]:
        """
        语义检索 — 使用 embed_query() 编码查询

        Returns:
            [(entry_id, cosine_similarity), ...] 按相似度降序
        """
        if not self.entries:
            return []

        query_vec = self.embedding_provider.embed_query(query)

        scored = []
        for entry in self.entries:
            sim = _cosine_similarity(query_vec, entry["embedding"])
            scored.append((entry["id"], sim))

        scored.sort(key=lambda x: x[1], reverse=True)
        return scored[:top_k]

    def remove(self, entry_id: str) -> bool:
        """移除条目"""
        if entry_id not in self._id_index:
            return False
        entry = self._id_index.pop(entry_id)
        self.entries.remove(entry)
        return True

    def count(self) -> int:
        """返回条目数量"""
        return len(self.entries)

    def get_content(self, entry_id: str) -> Optional[str]:
        """根据 ID 获取内容"""
        entry = self._id_index.get(entry_id)
        return entry["content"] if entry else None

    # ============ 持久化 ============

    def _load(self) -> None:
        """从文件加载"""
        if not os.path.exists(self.persist_path):
            return

        try:
            with open(self.persist_path, 'r', encoding='utf-8') as f:
                data = json.load(f)

            for entry_dict in data.get("entries", []):
                self.entries.append(entry_dict)
                self._id_index[entry_dict["id"]] = entry_dict

            logger.info(f"[NemotronStore] Loaded {len(self.entries)} entries")

        except Exception as e:
            logger.warning(f"[NemotronStore] Failed to load: {e}")

    def save(self) -> None:
        """保存到文件（原子写入）"""
        import tempfile

        data = {"entries": self.entries}

        dir_path = os.path.dirname(self.persist_path) or '.'
        fd, tmp_path = tempfile.mkstemp(dir=dir_path, suffix='.tmp')
        try:
            with os.fdopen(fd, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False)
            os.replace(tmp_path, self.persist_path)
        except Exception as e:
            logger.warning(f"[NemotronStore] Failed to save: {e}")
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
