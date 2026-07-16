# -*- coding: utf-8 -*-
"""
铉枢·炉守 向量记忆集成
XuanHub Vector Memory Integration
参考: RankSquire L1/L2/L3架构 + Mem0 Token优化实践 + MemPalace混合检索
"""

import logging
import json
import time
from typing import Any, Dict, List, Optional, Tuple, Callable
from dataclasses import dataclass, field
from enum import Enum
from abc import ABC, abstractmethod

logger = logging.getLogger("VectorMemory")


class MemoryTier(Enum):
    """记忆层级"""
    L1_HOT = "l1_hot"       # 热状态，当前任务上下文 (<1ms延迟)
    L2_SEMANTIC = "l2_semantic"  # 语义存储，向量检索 (20ms延迟)
    L3_EPISODIC = "l3_episodic"  # 情景日志，长期历史


@dataclass
class MemoryEntry:
    """记忆条目"""
    content: str
    role: str = "user"
    importance: float = 1.0
    timestamp: str = field(default_factory=lambda: time.time())
    embedding: Optional[List[float]] = None
    metadata: Dict = field(default_factory=dict)
    
    def to_dict(self) -> Dict:
        return {
            "content": self.content,
            "role": self.role,
            "importance": self.importance,
            "timestamp": self.timestamp,
            "metadata": self.metadata
        }


@dataclass
class SearchResult:
    """搜索结果"""
    entry: MemoryEntry
    score: float
    rank: int


class EmbeddingProvider(ABC):
    """嵌入向量提供者抽象"""
    
    @abstractmethod
    def embed(self, text: str) -> List[float]:
        """将文本转换为嵌入向量"""
        pass
    
    @abstractmethod
    def embed_batch(self, texts: List[str]) -> List[List[float]]:
        """批量转换"""
        pass


class SimpleEmbeddingProvider(EmbeddingProvider):
    """
    简单嵌入提供者
    
    使用简单的词频向量作为嵌入。
    实际生产环境应使用 OpenAI/text-embedding-3-small 或本地模型。
    """
    
    def __init__(self, dimension: int = 384):
        self.dimension = dimension
    
    def embed(self, text: str) -> List[float]:
        """简单的TF-IDF风格嵌入"""
        words = text.lower().split()
        
        # 简单哈希向量
        vector = [0.0] * self.dimension
        for i, word in enumerate(words[:self.dimension]):
            vector[hash(word) % self.dimension] += 1.0
        
        # L2归一化
        norm = sum(v * v for v in vector) ** 0.5
        if norm > 0:
            vector = [v / norm for v in vector]
        
        return vector
    
    def embed_batch(self, texts: List[str]) -> List[List[float]]:
        return [self.embed(t) for t in texts]


class NGramTFIDFProvider(EmbeddingProvider):
    """
    N-gram TF-IDF 语义嵌入提供者
    
    使用 word-level 和 character-level 的 n-gram 组合：
    - Word unigrams/bigrams: ["nano", "sio2", "cement", "nano_sio2", "sio2_cement"]
    - Char 3-grams: ["nan", "ano", "sio", "io2", "cem", "eme", "men", "ent"]
    - Char 4-grams: ["nano", "sio2", "ceme", "emen", "ment"]
    
    优势：
    - n-gram 能捕获子词相似性（"SiO2" 和 "silica" 共享 char n-gram）
    - TF-IDF 加权自动降低常见词影响
    - 支持中英文混合
    """
    
    def __init__(self, dimension: int = 5000, vocab_path: Optional[str] = None):
        self.dimension = dimension
        self.vocab: Dict[str, int] = {}  # n-gram -> index mapping
        self.idf: Dict[str, float] = {}  # n-gram -> IDF score
        self.doc_count: int = 0
        self._next_idx: int = 0
        
        # 加载已有vocab（如果存在）
        if vocab_path:
            try:
                with open(vocab_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.vocab = data.get('vocab', {})
                    self.idf = data.get('idf', {})
                    self.doc_count = data.get('doc_count', 0)
                    self._next_idx = len(self.vocab)
                    logger.info(f"[NGramTFIDF] Loaded vocab from {vocab_path}")
            except Exception as e:
                logger.warning(f"[NGramTFIDF] Failed to load vocab: {e}")
    
    def _is_chinese(self, char: str) -> bool:
        """判断是否为中文字符"""
        return '\u4e00' <= char <= '\u9fff'
    
    def _tokenize(self, text: str) -> List[str]:
        """分词：英文按空格小写化，中文按字切分"""
        tokens = []
        for word in text.lower().split():
            # 保留英文字母数字和中文
            clean = ''.join(c for c in word if c.isalnum() or self._is_chinese(c))
            if clean:
                tokens.append(clean)
                # 中文额外按字切分
                if any(self._is_chinese(c) for c in clean):
                    tokens.extend(list(clean))
        return tokens
    
    def _get_ngrams(self, tokens: List[str]) -> Dict[str, float]:
        """生成 n-grams，返回 n-gram -> TF score 字典"""
        ngrams: Dict[str, float] = {}
        
        for token in tokens:
            # Word unigram
            ngrams[token] = ngrams.get(token, 0) + 1.0
            
            # Char 3-grams (至少3个字符)
            if len(token) >= 3:
                for i in range(len(token) - 2):
                    ng = token[i:i+3]
                    ngrams[ng] = ngrams.get(ng, 0) + 0.5
            
            # Char 4-grams (至少4个字符)
            if len(token) >= 4:
                for i in range(len(token) - 3):
                    ng = token[i:i+4]
                    ngrams[ng] = ngrams.get(ng, 0) + 0.3
        
        # Word bigrams
        for i in range(len(tokens) - 1):
            bigram = tokens[i] + '_' + tokens[i+1]
            ngrams[bigram] = ngrams.get(bigram, 0) + 1.0
        
        return ngrams
    
    def embed(self, text: str) -> List[float]:
        """将文本转换为嵌入向量"""
        tokens = self._tokenize(text)
        ngrams = self._get_ngrams(tokens)
        
        vector = [0.0] * self.dimension
        
        for ng, tf in ngrams.items():
            # 动态扩展 vocab 或用 hash 映射
            if ng in self.vocab:
                idx = self.vocab[ng]
            elif self._next_idx < self.dimension:
                idx = self._next_idx
                self.vocab[ng] = idx
                self._next_idx += 1
            else:
                # vocab 满了，用 hash 映射
                idx = hash(ng) % self.dimension
            
            # 获取 IDF 分数
            idf_score = self.idf.get(ng, 1.0)
            
            # TF-IDF 加权
            vector[idx] += tf * idf_score
        
        # L2 归一化
        norm = sum(v * v for v in vector) ** 0.5
        if norm > 0:
            vector = [v / norm for v in vector]
        
        return vector
    
    def embed_batch(self, texts: List[str]) -> List[List[float]]:
        return [self.embed(t) for t in texts]
    
    def update_idf(self, texts: List[str]) -> None:
        """批量更新 IDF（添加新文档时调用）"""
        import math
        
        self.doc_count += len(texts)
        
        # 统计每个 n-gram 出现在多少文档中
        doc_freq: Dict[str, int] = {}
        
        for text in texts:
            tokens = self._tokenize(text)
            ngrams = self._get_ngrams(tokens)
            
            # 只统计文档频率（每个文档只算一次）
            for ng in ngrams:
                doc_freq[ng] = doc_freq.get(ng, 0) + 1
        
        # 更新 IDF
        for ng, df in doc_freq.items():
            if ng not in self.idf:
                self.idf[ng] = 0
            self.idf[ng] += df
        
        # 重新计算所有 IDF = log(N / (1 + df))
        for ng in self.idf:
            self.idf[ng] = math.log(self.doc_count / (1 + self.idf[ng]))
        
        logger.debug(f"[NGramTFIDF] Updated IDF for {len(doc_freq)} n-grams, doc_count={self.doc_count}")
    
    def save_vocab(self, vocab_path: str) -> None:
        """保存 vocab 和 IDF 到文件"""
        import os
        os.makedirs(os.path.dirname(vocab_path) or '.', exist_ok=True)
        
        data = {
            'vocab': self.vocab,
            'idf': self.idf,
            'doc_count': self.doc_count
        }
        
        with open(vocab_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        
        logger.info(f"[NGramTFIDF] Saved vocab to {vocab_path}")


class APIKeywordProvider(EmbeddingProvider):
    """
    API 增强的关键词嵌入提供者
    
    使用 DeepSeek flash 提取语义关键词，然后降维成向量。
    用于高价值记忆（importance >= 0.7）。
    """
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        endpoint: str = "http://127.0.0.1:8083/v1/chat/completions",
        base_provider: Optional[EmbeddingProvider] = None
    ):
        self.api_key = api_key
        self.endpoint = endpoint
        self.base_provider = base_provider or NGramTFIDFProvider()
        
        # 简单缓存已提取的关键词
        self._keyword_cache: Dict[str, List[str]] = {}
    
    def extract_keywords(self, text: str) -> List[str]:
        """调用 flash 提取语义关键词"""
        if text in self._keyword_cache:
            return self._keyword_cache[text]
        
        import urllib.request
        import urllib.error
        
        prompt = f"""Extract 5-10 semantic keywords from this text, comma separated.
Focus on key concepts, technical terms, and important entities.
Text: {text}
Keywords:"""
        
        payload = {
            "model": "deepseek-chat",
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": 50,
            "temperature": 0.3
        }
        
        try:
            req = urllib.request.Request(
                self.endpoint,
                data=json.dumps(payload).encode('utf-8'),
                headers={
                    'Content-Type': 'application/json',
                    'Authorization': f'Bearer {self.api_key}' if self.api_key else ''
                },
                method='POST'
            )
            
            with urllib.request.urlopen(req, timeout=10) as resp:
                result = json.loads(resp.read().decode('utf-8'))
                keywords_text = result['choices'][0]['message']['content']
                
                # 解析关键词
                keywords = [k.strip().lower() for k in keywords_text.split(',')]
                keywords = [k for k in keywords if k and len(k) > 1]
                
                self._keyword_cache[text] = keywords
                return keywords
                
        except Exception as e:
            logger.warning(f"[APIKeyword] Failed to extract keywords: {e}")
            return []
    
    def embed(self, text: str) -> List[float]:
        """用关键词增强文本后嵌入"""
        keywords = self.extract_keywords(text)
        
        if keywords:
            # 关键词权重加倍（重复3次）
            enhanced_text = text + " " + " ".join(keywords * 3)
            return self.base_provider.embed(enhanced_text)
        else:
            return self.base_provider.embed(text)
    
    def embed_batch(self, texts: List[str]) -> List[List[float]]:
        return [self.embed(t) for t in texts]


def cosine_similarity(a: List[float], b: List[float]) -> float:
    """计算余弦相似度"""
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = sum(x * x for x in a) ** 0.5
    norm_b = sum(x * x for x in b) ** 0.5
    
    if norm_a == 0 or norm_b == 0:
        return 0.0
    
    return dot / (norm_a * norm_b)


class VectorStore(ABC):
    """向量存储抽象"""
    
    @abstractmethod
    def add(self, entries: List[MemoryEntry]) -> None:
        """添加记忆条目"""
        pass
    
    @abstractmethod
    def search(self, query: str, top_k: int = 5) -> List[SearchResult]:
        """向量检索"""
        pass
    
    @abstractmethod
    def delete(self, entry_id: str) -> bool:
        """删除条目"""
        pass


class InMemoryVectorStore(VectorStore):
    """内存向量存储"""
    
    def __init__(self, embedding_provider: Optional[EmbeddingProvider] = None):
        self.embedding_provider = embedding_provider or SimpleEmbeddingProvider()
        self.entries: List[MemoryEntry] = []
        self._entry_id_counter = 0
    
    def _get_entry_id(self, entry: MemoryEntry) -> str:
        """生成entry ID"""
        if not hasattr(entry, 'entry_id'):
            entry.entry_id = f"mem_{self._entry_id_counter}"
            self._entry_id_counter += 1
        return entry.entry_id
    
    def add(self, entries: List[MemoryEntry]) -> None:
        """添加记忆条目"""
        for entry in entries:
            if entry.embedding is None:
                entry.embedding = self.embedding_provider.embed(entry.content)
            
            entry_id = self._get_entry_id(entry)
            entry.metadata['entry_id'] = entry_id
            
            self.entries.append(entry)
        
        logger.debug(f"[VectorStore] Added {len(entries)} entries (total={len(self.entries)})")
    
    def search(self, query: str, top_k: int = 5) -> List[SearchResult]:
        """向量检索"""
        query_embedding = self.embedding_provider.embed(query)
        
        # 计算相似度
        scored = []
        for i, entry in enumerate(self.entries):
            if entry.embedding:
                score = cosine_similarity(query_embedding, entry.embedding)
                scored.append((entry, score, i))
        
        # 排序
        scored.sort(key=lambda x: x[1], reverse=True)
        
        # 返回top_k
        results = []
        for rank, (entry, score, _) in enumerate(scored[:top_k]):
            results.append(SearchResult(entry=entry, score=score, rank=rank))
        
        return results
    
    def delete(self, entry_id: str) -> bool:
        """删除条目"""
        for i, entry in enumerate(self.entries):
            if entry.metadata.get('entry_id') == entry_id:
                self.entries.pop(i)
                return True
        return False
    
    def count(self) -> int:
        """返回条目数量"""
        return len(self.entries)


class PersistentVectorStore(InMemoryVectorStore):
    """
    持久化向量存储
    
    继承 InMemoryVectorStore，添加持久化功能：
    - 保存到 ./NexusFlow/data/vector_memory.json
    - 每 N 次 add 自动保存，也支持手动 save()
    - 启动时自动加载
    - 使用原子写入避免数据损坏
    """
    
    def __init__(
        self,
        embedding_provider: Optional[EmbeddingProvider] = None,
        persist_path: str = "./data/vector_memory.json",
        auto_save_interval: int = 10
    ):
        super().__init__(embedding_provider)
        self.persist_path = persist_path
        self.auto_save_interval = auto_save_interval
        self._add_counter = 0
        
        # 确保目录存在
        import os
        os.makedirs(os.path.dirname(persist_path) or '.', exist_ok=True)
        
        # 尝试加载已有数据
        self._load()
    
    def _load(self) -> None:
        """从文件加载数据"""
        import os
        if not os.path.exists(self.persist_path):
            logger.info(f"[PersistentVectorStore] No existing data at {self.persist_path}")
            return
        
        try:
            with open(self.persist_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            entries_data = data.get('entries', [])
            self._entry_id_counter = data.get('counter', 0)
            
            for entry_dict in entries_data:
                entry = MemoryEntry(
                    content=entry_dict.get('content', ''),
                    role=entry_dict.get('role', 'user'),
                    importance=entry_dict.get('importance', 1.0),
                    timestamp=entry_dict.get('timestamp', time.time()),
                    embedding=entry_dict.get('embedding'),
                    metadata=entry_dict.get('metadata', {})
                )
                self.entries.append(entry)
            
            # 恢复 IDF（如果有）
            if hasattr(self.embedding_provider, 'update_idf'):
                texts = [e.content for e in self.entries]
                if texts:
                    self.embedding_provider.update_idf(texts)
            
            logger.info(f"[PersistentVectorStore] Loaded {len(self.entries)} entries from {self.persist_path}")
            
        except Exception as e:
            logger.warning(f"[PersistentVectorStore] Failed to load data: {e}")
    
    def save(self) -> None:
        """手动保存到文件（原子写入）"""
        import os
        import tempfile
        
        entries_data = []
        for entry in self.entries:
            entries_data.append({
                'content': entry.content,
                'role': entry.role,
                'importance': entry.importance,
                'timestamp': entry.timestamp,
                'embedding': entry.embedding,
                'metadata': entry.metadata
            })
        
        data = {
            'entries': entries_data,
            'counter': self._entry_id_counter
        }
        
        # 原子写入：先写临时文件，再 rename
        dir_path = os.path.dirname(self.persist_path) or '.'
        fd, tmp_path = tempfile.mkstemp(dir=dir_path, suffix='.tmp')
        try:
            with os.fdopen(fd, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False)
            os.replace(tmp_path, self.persist_path)
            logger.debug(f"[PersistentVectorStore] Saved {len(self.entries)} entries to {self.persist_path}")
        except Exception as e:
            # 清理临时文件
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)
            raise e
    
    def add(self, entries: List[MemoryEntry]) -> None:
        """添加记忆条目（自动保存）"""
        super().add(entries)
        
        self._add_counter += 1
        if self._add_counter >= self.auto_save_interval:
            self.save()
            self._add_counter = 0


class ChromaDBVectorStore(VectorStore):
    """
    ChromaDB 向量存储（可选后端）
    
    - try/except 导入 chromadb
    - 不可用时 graceful fallback 到 PersistentVectorStore
    - 可用时自动使用 ChromaDB 的内置 embedding
    """
    
    _available = None
    
    def __init__(
        self,
        embedding_provider: Optional[EmbeddingProvider] = None,
        persist_path: str = "./NexusFlow/data/chroma_db",
        collection_name: str = "nexusflow_memory"
    ):
        # 检查是否可用
        if ChromaDBVectorStore._available is None:
            try:
                import chromadb
                ChromaDBVectorStore._available = True
            except ImportError:
                ChromaDBVectorStore._available = False
                logger.warning("[ChromaDBVectorStore] chromadb not available, falling back to PersistentVectorStore")
        
        if not ChromaDBVectorStore._available:
            # 回退到 PersistentVectorStore
            self._fallback = PersistentVectorStore(embedding_provider)
            return
        
        import chromadb
        from chromadb.config import Settings
        
        self.embedding_provider = embedding_provider
        self.persist_path = persist_path
        self.collection_name = collection_name
        
        # 初始化 ChromaDB
        self.client = chromadb.PersistentClient(
            path=persist_path,
            settings=Settings(anonymized_telemetry=False)
        )
        
        self.collection = self.client.get_or_create_collection(
            name=collection_name,
            metadata={"hnsw:space": "cosine"}
        )
        
        logger.info(f"[ChromaDBVectorStore] Initialized collection '{collection_name}' at {persist_path}")
    
    def _is_fallback(self) -> bool:
        """是否使用回退存储"""
        return hasattr(self, '_fallback')
    
    def add(self, entries: List[MemoryEntry]) -> None:
        """添加记忆条目"""
        if self._is_fallback():
            return self._fallback.add(entries)
        
        import chromadb.errors
        
        ids = []
        documents = []
        embeddings = []
        metadatas = []
        
        for entry in entries:
            if entry.embedding is None:
                entry.embedding = self.embedding_provider.embed(entry.content)
            
            entry_id = entry.metadata.get('entry_id') or f"mem_{len(self.collection.peek()['ids']) + len(ids)}"
            entry.metadata['entry_id'] = entry_id
            
            ids.append(entry_id)
            documents.append(entry.content)
            embeddings.append(entry.embedding)
            metadatas.append({
                'role': entry.role,
                'importance': entry.importance,
                'timestamp': str(entry.timestamp),
                **entry.metadata
            })
        
        try:
            self.collection.add(
                ids=ids,
                documents=documents,
                embeddings=embeddings,
                metadatas=metadatas
            )
            logger.debug(f"[ChromaDBVectorStore] Added {len(entries)} entries (total={self.collection.count()})")
        except chromadb.errors.IDAlreadyExistsError:
            # 忽略已存在的 ID
            logger.debug(f"[ChromaDBVectorStore] Some entries already exist")
    
    def search(self, query: str, top_k: int = 5) -> List[SearchResult]:
        """向量检索"""
        if self._is_fallback():
            return self._fallback.search(query, top_k)
        
        query_embedding = self.embedding_provider.embed(query)
        
        results = self.collection.query(
            query_embeddings=[query_embedding],
            n_results=top_k
        )
        
        search_results = []
        if results['ids'] and results['ids'][0]:
            for rank, (entry_id, distance, document, metadata) in enumerate(zip(
                results['ids'][0],
                results['distances'][0] if results['distances'] else [0] * len(results['ids'][0]),
                results['documents'][0] if results['documents'] else [],
                results['metadatas'][0] if results['metadatas'] else []
            )):
                # 距离转相似度（cosine distance）
                score = 1.0 - distance if distance is not None else 0.0
                
                entry = MemoryEntry(
                    content=document,
                    role=metadata.get('role', 'user'),
                    importance=metadata.get('importance', 1.0),
                    timestamp=float(metadata.get('timestamp', 0)),
                    metadata={k: v for k, v in metadata.items() if k not in ['role', 'importance', 'timestamp']}
                )
                entry.metadata['entry_id'] = entry_id
                
                search_results.append(SearchResult(entry=entry, score=score, rank=rank))
        
        return search_results
    
    def delete(self, entry_id: str) -> bool:
        """删除条目"""
        if self._is_fallback():
            return self._fallback.delete(entry_id)
        
        try:
            self.collection.delete(ids=[entry_id])
            return True
        except Exception:
            return False
    
    def count(self) -> int:
        """返回条目数量"""
        if self._is_fallback():
            return self._fallback.count()
        
        return self.collection.count()


class VectorMemory:
    """
    三层向量记忆系统
    
    L1 (Hot): 短期记忆，KV缓存，用于当前任务
    L2 (Semantic): 语义存储，向量检索
    L3 (Episodic): 情景日志，长期历史
    
    优势:
    - 检索型注入比全量注入节省51-72% Token (据Mem0 2026实践)
    - 语义相似检索提高答案质量
    - 分层管理避免上下文溢出
    
    用法:
        vm = VectorMemory()
        
        # 添加记忆
        vm.add("用户偏好: 喜欢详细的答案", role="system", importance=0.8)
        
        # 检索
        context = vm.retrieve("用户的答案偏好是什么", top_k=5)
        
        # 注入到Agent
        agent.inject_context(context)
    """
    
    def __init__(
        self,
        embedding_provider: Optional[EmbeddingProvider] = None,
        vector_store: Optional[VectorStore] = None,
        # L1 配置
        l1_max_size: int = 20,
        # L2 配置
        l2_max_size: int = 500,
        # L3 配置
        l3_max_size: int = 2000,
        # 重要性阈值
        importance_threshold: float = 0.3,
        # 压缩配置
        compress_similarity_threshold: float = 0.85,
        compress_min_age_seconds: float = 3600.0,
        decay_rate: float = 0.95,
        auto_maintain_interval: int = 50
    ):
        self.embedding_provider = embedding_provider or NGramTFIDFProvider()
        self.vector_store = vector_store or PersistentVectorStore(self.embedding_provider)
        
        # 各层存储
        self.l1_hot: List[MemoryEntry] = []  # 短期记忆
        self.l2_semantic: List[MemoryEntry] = []  # 语义存储
        self.l3_episodic: List[MemoryEntry] = []  # 情景日志
        
        # 配置
        self.l1_max_size = l1_max_size
        self.l2_max_size = l2_max_size
        self.l3_max_size = l3_max_size
        self.importance_threshold = importance_threshold
        
        # 压缩配置
        self.compress_similarity_threshold = compress_similarity_threshold
        self.compress_min_age_seconds = compress_min_age_seconds
        self.decay_rate = decay_rate
        self.auto_maintain_interval = auto_maintain_interval
        self._add_count = 0
        
        # 统计
        self._stats = {
            "total_adds": 0,
            "total_retrieves": 0,
            "token_savings": 0,
            "compressions": 0,
            "decays": 0,
            "cleanups": 0
        }
        
        logger.info(
            f"[VectorMemory] Initialized: "
            f"L1={l1_max_size}, L2={l2_max_size}, L3={l3_max_size}, "
            f"compress_sim={compress_similarity_threshold}, decay_rate={decay_rate}"
        )
    
    def add(
        self,
        content: str,
        role: str = "user",
        importance: float = 1.0,
        tier: Optional[MemoryTier] = None,
        metadata: Optional[Dict] = None
    ) -> MemoryEntry:
        """
        添加记忆
        
        Args:
            content: 记忆内容
            role: 角色 (user/assistant/system)
            importance: 重要性 0-1
            tier: 指定层级，默认自动判断
            metadata: 附加元数据
            
        Returns:
            MemoryEntry
        """
        entry = MemoryEntry(
            content=content,
            role=role,
            importance=importance,
            metadata=metadata or {}
        )
        
        # 生成嵌入
        entry.embedding = self.embedding_provider.embed(content)
        
        # 确定层级
        if tier is None:
            tier = self._get_tier(importance)
        
        # 添加到对应层级
        if tier == MemoryTier.L1_HOT:
            self.l1_hot.append(entry)
            if len(self.l1_hot) > self.l1_max_size:
                # LRU: 移到L2
                old = self.l1_hot.pop(0)
                self._promote_to_l2(old)
        elif tier == MemoryTier.L2_SEMANTIC:
            self.l2_semantic.append(entry)
            if len(self.l2_semantic) > self.l2_max_size:
                self.l2_semantic.pop(0)
        elif tier == MemoryTier.L3_EPISODIC:
            self.l3_episodic.append(entry)
            if len(self.l3_episodic) > self.l3_max_size:
                self.l3_episodic.pop(0)
        
        # 同步到向量存储
        self.vector_store.add([entry])
        
        self._stats["total_adds"] += 1
        self._add_count += 1
        
        # 自动维护
        if self._add_count >= self.auto_maintain_interval:
            self.auto_maintain()
            self._add_count = 0
        
        return entry
    
    def _get_tier(self, importance: float) -> MemoryTier:
        """根据重要性确定层级"""
        if importance >= 0.7:
            return MemoryTier.L1_HOT
        elif importance >= 0.3:
            return MemoryTier.L2_SEMANTIC
        else:
            return MemoryTier.L3_EPISODIC
    
    def _promote_to_l2(self, entry: MemoryEntry) -> None:
        """将L1条目提升到L2"""
        entry.importance = max(entry.importance, 0.3)
        self.l2_semantic.append(entry)
    
    def retrieve(
        self,
        query: str,
        top_k: int = 5,
        include_tiers: Optional[List[MemoryTier]] = None
    ) -> List[MemoryEntry]:
        """
        检索相关记忆
        
        Args:
            query: 查询文本
            top_k: 返回数量
            include_tiers: 指定检索层级，默认全部
            
        Returns:
            相关记忆列表
        """
        include_tiers = include_tiers or [
            MemoryTier.L1_HOT,
            MemoryTier.L2_SEMANTIC,
            MemoryTier.L3_EPISODIC
        ]
        
        # 向量检索
        results = self.vector_store.search(query, top_k=top_k * 2)
        
        # 过滤层级
        filtered = []
        for result in results:
            tier = self._get_tier(result.entry.importance)
            if tier in include_tiers:
                filtered.append(result.entry)
            
            if len(filtered) >= top_k:
                break
        
        # 如果向量检索结果不够，从各层补充
        if len(filtered) < top_k:
            needed = top_k - len(filtered)
            
            if MemoryTier.L1_HOT in include_tiers:
                for entry in reversed(self.l1_hot):
                    if entry not in filtered:
                        filtered.append(entry)
                        if len(filtered) >= top_k:
                            break
            
            if len(filtered) < top_k and MemoryTier.L2_SEMANTIC in include_tiers:
                for entry in reversed(self.l2_semantic):
                    if entry not in filtered:
                        filtered.append(entry)
                        if len(filtered) >= top_k:
                            break
        
        self._stats["total_retrieves"] += 1
        
        # 估算Token节省
        naive_count = len(self.l1_hot) + len(self.l2_semantic)
        retrieval_count = len(filtered)
        if naive_count > 0:
            savings = (naive_count - retrieval_count) / naive_count
            self._stats["token_savings"] += int(savings * 100)
        
        return filtered[:top_k]
    
    def inject_context(
        self,
        agent,
        query: str,
        top_k: int = 5,
        system_prefix: str = "【相关记忆】\n"
    ) -> str:
        """
        检索并注入上下文到Agent
        
        Args:
            agent: Agent实例
            query: 查询文本
            top_k: 检索数量
            system_prefix: 前缀文本
            
        Returns:
            注入的上下文字符串
        """
        entries = self.retrieve(query, top_k=top_k)
        
        if not entries:
            return ""
        
        context_parts = [system_prefix]
        
        for entry in entries:
            role_emoji = {"user": "👤", "assistant": "🤖", "system": "⚙️"}.get(entry.role, "📝")
            context_parts.append(f"{role_emoji} {entry.content}")
        
        context = "\n".join(context_parts)
        
        logger.debug(
            f"[VectorMemory] Injected {len(entries)} entries "
            f"(L1={sum(1 for e in entries if e in self.l1_hot)}, "
            f"L2={sum(1 for e in entries if e in self.l2_semantic)})"
        )
        
        return context
    
    def get_context_for_llm(
        self,
        query: str,
        top_k: int = 5,
        max_tokens: int = 2000
    ) -> str:
        """
        获取适合注入LLM的上下文字符串
        
        带Token限制，适合直接拼接进system prompt
        """
        entries = self.retrieve(query, top_k=top_k)
        
        if not entries:
            return ""
        
        parts = ["【相关记忆】"]
        current_tokens = 0
        
        for entry in entries:
            entry_text = f"- {entry.content}"
            entry_tokens = len(entry_text) // 4  # 粗略估算
            
            if current_tokens + entry_tokens > max_tokens:
                break
            
            parts.append(entry_text)
            current_tokens += entry_tokens
        
        if len(parts) == 1:
            return ""
        
        return "\n".join(parts)
    
    def get_stats(self) -> Dict:
        """获取统计信息"""
        return {
            "tiers": {
                "l1_hot": len(self.l1_hot),
                "l2_semantic": len(self.l2_semantic),
                "l3_episodic": len(self.l3_episodic)
            },
            "vector_store_count": self.vector_store.count(),
            **self._stats
        }
    
    def clear(self, tier: Optional[MemoryTier] = None) -> None:
        """清空记忆"""
        if tier is None:
            self.l1_hot.clear()
            self.l2_semantic.clear()
            self.l3_episodic.clear()
            logger.info("[VectorMemory] All tiers cleared")
        elif tier == MemoryTier.L1_HOT:
            self.l1_hot.clear()
        elif tier == MemoryTier.L2_SEMANTIC:
            self.l2_semantic.clear()
        elif tier == MemoryTier.L3_EPISODIC:
            self.l3_episodic.clear()
    
    # ============ 记忆压缩与维护 ============
    
    def _compress_l2(self) -> int:
        """压缩L2层：合并语义相似的条目
        
        扫描L2中超过 min_age 的条目，如果两个条目的向量相似度
        超过 threshold，则合并为一条（保留内容更长的，标记合并来源）。
        
        Returns:
            合并/移除的条目数
        """
        now = time.time()
        min_age = self.compress_min_age_seconds
        
        # 筛选可压缩条目（足够老的）
        compressible = [
            (i, e) for i, e in enumerate(self.l2_semantic)
            if (now - float(e.timestamp)) > min_age and e.embedding is not None
        ]
        
        if len(compressible) < 2:
            return 0
        
        removed_indices = set()
        merge_count = 0
        
        for a_idx in range(len(compressible)):
            i, entry_a = compressible[a_idx]
            if i in removed_indices:
                continue
            
            for b_idx in range(a_idx + 1, len(compressible)):
                j, entry_b = compressible[b_idx]
                if j in removed_indices:
                    continue
                
                sim = cosine_similarity(entry_a.embedding, entry_b.embedding)
                
                if sim >= self.compress_similarity_threshold:
                    # 保留内容更长的，合并元数据
                    if len(entry_a.content) >= len(entry_b.content):
                        keeper, loser_idx = entry_a, j
                    else:
                        keeper, loser_idx = entry_b, i
                    
                    keeper.metadata.setdefault("merged_from", [])
                    keeper.metadata["merged_from"].append(
                        {"content": entry_a.content if loser_idx == i else entry_b.content, "sim": round(sim, 3)}
                    )
                    keeper.importance = max(entry_a.importance, entry_b.importance)
                    
                    removed_indices.add(loser_idx)
                    merge_count += 1
        
        # 从L2移除被合并的条目
        if removed_indices:
            self.l2_semantic = [
                e for i, e in enumerate(self.l2_semantic)
                if i not in removed_indices
            ]
            self._stats["compressions"] += merge_count
            logger.info(f"[VectorMemory] L2 compressed: {merge_count} entries merged")
        
        return merge_count
    
    def _decay_importance(self) -> int:
        """衰减重要性：随时间降低条目的 importance 分数
        
        对L2和L3中的条目，每次调用将 importance 乘以 decay_rate。
        低于 importance_threshold 的条目会被降级（L2→L3，L3→删除）。
        
        Returns:
            衰减的条目数
        """
        decayed = 0
        now = time.time()
        
        # L2 衰减
        demoted_to_l3 = []
        surviving_l2 = []
        
        for entry in self.l2_semantic:
            entry.importance *= self.decay_rate
            decayed += 1
            
            if entry.importance < self.importance_threshold:
                # 降级到L3
                demoted_to_l3.append(entry)
            else:
                surviving_l2.append(entry)
        
        if demoted_to_l3:
            self.l2_semantic = surviving_l2
            self.l3_episodic.extend(demoted_to_l3)
            logger.debug(f"[VectorMemory] L2→L3 demoted: {len(demoted_to_l3)} entries")
        
        # L3 衰减 + 清理
        surviving_l3 = []
        for entry in self.l3_episodic:
            entry.importance *= self.decay_rate
            decayed += 1
            
            # importance 极低的直接淘汰
            if entry.importance >= 0.05:
                surviving_l3.append(entry)
        
        removed = len(self.l3_episodic) - len(surviving_l3)
        if removed > 0:
            self.l3_episodic = surviving_l3
            logger.debug(f"[VectorMemory] L3 purged: {removed} entries (importance < 0.05)")
        
        self._stats["decays"] += decayed
        return decayed
    
    def _cleanup_expired(self) -> int:
        """清理过期条目：移除 metadata 中标记了 expires_at 且已过期的条目
        
        Returns:
            清理的条目数
        """
        now = time.time()
        cleaned = 0
        
        for tier_list in [self.l1_hot, self.l2_semantic, self.l3_episodic]:
            before = len(tier_list)
            tier_list[:] = [
                e for e in tier_list
                if not (
                    e.metadata.get("expires_at")
                    and float(e.metadata["expires_at"]) < now
                )
            ]
            cleaned += before - len(tier_list)
        
        # 同步清理向量存储
        if cleaned > 0:
            # 从 vector_store 中也移除对应的 entry
            for entry_id_to_remove in [
                e.metadata.get("entry_id")
                for tier_list in [self.l1_hot, self.l2_semantic, self.l3_episodic]
                for e in tier_list
                if e.metadata.get("expires_at") and float(e.metadata["expires_at"]) < now
            ]:
                if entry_id_to_remove:
                    self.vector_store.delete(entry_id_to_remove)
            
            self._stats["cleanups"] += cleaned
            logger.info(f"[VectorMemory] Cleaned up {cleaned} expired entries")
        
        return cleaned
    
    def auto_maintain(self) -> Dict[str, int]:
        """自动维护：执行压缩→衰减→清理
        
        每隔 auto_maintain_interval 次 add 自动触发，
        也可手动调用。
        
        Returns:
            各步骤处理的条目数
        """
        logger.info("[VectorMemory] Running auto_maintain...")
        
        result = {
            "compressed": self._compress_l2(),
            "decayed": self._decay_importance(),
            "cleaned": self._cleanup_expired()
        }
        
        # L3 容量控制
        if len(self.l3_episodic) > self.l3_max_size:
            # 按 importance 排序，保留最高的
            self.l3_episodic.sort(key=lambda e: e.importance, reverse=True)
            removed = len(self.l3_episodic) - self.l3_max_size
            self.l3_episodic = self.l3_episodic[:self.l3_max_size]
            result["l3_trimmed"] = removed
        
        # 持久化
        if hasattr(self.vector_store, 'save'):
            self.vector_store.save()
        
        logger.info(
            f"[VectorMemory] auto_maintain done: "
            f"compressed={result['compressed']}, decayed={result['decayed']}, "
            f"cleaned={result['cleaned']}"
        )
        
        return result


# ============ BM25 混合检索 ============

class BM25Retriever:
    """BM25关键词检索器
    
    参考: MemPalace + mem0的多信号检索
    实现Okapi BM25算法，与向量检索结果进行RRF融合。
    轻量级纯Python实现，无需外部依赖。
    """

    def __init__(self, k1: float = 1.5, b: float = 0.75):
        self.k1 = k1
        self.b = b
        self._doc_freq: Dict[str, int] = {}  # 词项文档频率
        self._doc_count: int = 0
        self._doc_lengths: Dict[str, int] = {}  # doc_id -> 词数
        self._doc_tokens: Dict[str, List[str]] = {}  # doc_id -> tokens
        self._avg_dl: float = 0.0

    def _tokenize(self, text: str) -> List[str]:
        """简单分词"""
        return [w for w in re.split(r'[\s,.\-!?;:，。！？；：\n\r\t]+', text.lower()) if w]

    def index(self, doc_id: str, text: str) -> None:
        """索引文档"""
        tokens = self._tokenize(text)
        self._doc_tokens[doc_id] = tokens
        self._doc_lengths[doc_id] = len(tokens)
        self._doc_count += 1

        # 更新文档频率
        seen = set()
        for token in tokens:
            if token not in seen:
                self._doc_freq[token] = self._doc_freq.get(token, 0) + 1
                seen.add(token)

        # 更新平均文档长度
        total = sum(self._doc_lengths.values())
        self._avg_dl = total / self._doc_count if self._doc_count > 0 else 0

    def remove(self, doc_id: str) -> None:
        """移除文档"""
        if doc_id not in self._doc_tokens:
            return
        tokens = self._doc_tokens.pop(doc_id)
        self._doc_lengths.pop(doc_id, None)
        self._doc_count -= 1

        seen = set()
        for token in tokens:
            if token not in seen:
                self._doc_freq[token] = max(0, self._doc_freq.get(token, 0) - 1)
                seen.add(token)

    def search(self, query: str, top_k: int = 5) -> List[Tuple[str, float]]:
        """BM25搜索，返回 (doc_id, score) 列表"""
        query_tokens = self._tokenize(query)
        scores: Dict[str, float] = {}

        for token in query_tokens:
            if token not in self._doc_freq:
                continue
            df = self._doc_freq[token]
            idf = math.log((self._doc_count - df + 0.5) / (df + 0.5) + 1)

            for doc_id, tokens in self._doc_tokens.items():
                tf = tokens.count(token)
                dl = self._doc_lengths.get(doc_id, 0)
                numerator = tf * (self.k1 + 1)
                denominator = tf + self.k1 * (1 - self.b + self.b * dl / max(self._avg_dl, 1))
                score = idf * numerator / denominator
                scores[doc_id] = scores.get(doc_id, 0) + score

        ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        return ranked[:top_k]


def reciprocal_rank_fusion(
    vector_results: List[Tuple[str, float]],
    bm25_results: List[Tuple[str, float]],
    k: int = 60
) -> List[Tuple[str, float]]:
    """RRF融合向量检索和BM25结果
    
    参考: Mem0多信号检索 + MemPalace混合检索
    RRF公式: score = 1 / (k + rank)
    
    Args:
        vector_results: [(doc_id, score), ...] 向量检索结果
        bm25_results: [(doc_id, score), ...] BM25检索结果
        k: RRF常数，默认60
    
    Returns:
        [(doc_id, fused_score), ...] 融合后的结果
    """
    fused: Dict[str, float] = {}

    for rank, (doc_id, _) in enumerate(vector_results):
        fused[doc_id] = fused.get(doc_id, 0) + 1.0 / (k + rank + 1)

    for rank, (doc_id, _) in enumerate(bm25_results):
        fused[doc_id] = fused.get(doc_id, 0) + 1.0 / (k + rank + 1)

    return sorted(fused.items(), key=lambda x: x[1], reverse=True)


# ============ 结构化记忆槽 ============

@dataclass
class MemorySlot:
    """结构化记忆槽
    
    用于存储键值对形式的事实性信息，区别于语义块记忆。
    参考: Mem0 multi-scope + Oracle structured memory
    
    典型用途:
    - 用户偏好: {"偏好": "DeepSeek API优先"}
    - 项目状态: {"xuan-hub版本": "v3.3"}
    - 决策记录: {"向量数据库": "暂用NGramTFIDF，环境改善后升级ChromaDB"}
    """
    key: str
    value: str
    scope: str = "user"  # user | agent | session | app
    confidence: float = 1.0
    source: str = ""     # 来源（对话/文档/API）
    updated_at: str = field(default_factory=lambda: time.time())
    previous_value: Optional[str] = None  # 上次值（用于冲突追踪）


class StructuredSlotMemory:
    """结构化记忆槽管理
    
    区别于语义块记忆(L1/L2/L3)，这是kv形式的事实性记忆。
    精确召回，不做模糊匹配。
    """

    def __init__(self):
        self._slots: Dict[str, MemorySlot] = {}  # key -> slot
        self._scope_index: Dict[str, List[str]] = {}  # scope -> [keys]
        logger.info("[SlotMemory] Initialized")

    def set(
        self,
        key: str,
        value: str,
        scope: str = "user",
        confidence: float = 1.0,
        source: str = ""
    ) -> Optional[str]:
        """设置槽值，返回旧值（如果有冲突）"""
        old_value = None

        if key in self._slots:
            existing = self._slots[key]
            old_value = existing.value

            # 冲突检测：值发生变化
            if existing.value != value:
                existing.previous_value = old_value
                existing.value = value
                existing.confidence = confidence
                existing.source = source
                existing.updated_at = time.time()
                logger.info(
                    f"[SlotMemory] Updated '{key}': '{old_value}' -> '{value}'"
                )
            # 值没变，可能更新confidence
            else:
                existing.confidence = max(existing.confidence, confidence)
        else:
            slot = MemorySlot(
                key=key, value=value, scope=scope,
                confidence=confidence, source=source
            )
            self._slots[key] = slot
            self._scope_index.setdefault(scope, []).append(key)
            logger.debug(f"[SlotMemory] Set '{key}' = '{value}' (scope={scope})")

        return old_value

    def get(self, key: str, default: Optional[str] = None) -> Optional[str]:
        """获取槽值"""
        slot = self._slots.get(key)
        return slot.value if slot else default

    def get_slot(self, key: str) -> Optional[MemorySlot]:
        """获取完整槽对象"""
        return self._slots.get(key)

    def delete(self, key: str) -> bool:
        """删除槽"""
        if key in self._slots:
            slot = self._slots.pop(key)
            if slot.scope in self._scope_index:
                self._scope_index[slot.scope] = [
                    k for k in self._scope_index[slot.scope] if k != key
                ]
            return True
        return False

    def list_by_scope(self, scope: str) -> Dict[str, str]:
        """列出某个scope下的所有槽"""
        keys = self._scope_index.get(scope, [])
        return {k: self._slots[k].value for k in keys if k in self._slots}

    def get_conflicts(self) -> List[Dict]:
        """获取所有有过冲突（值变更）的槽"""
        conflicts = []
        for slot in self._slots.values():
            if slot.previous_value is not None:
                conflicts.append({
                    "key": slot.key,
                    "old_value": slot.previous_value,
                    "new_value": slot.value,
                    "source": slot.source,
                    "updated_at": slot.updated_at
                })
        return conflicts

    def search(self, query: str) -> List[Tuple[str, str, float]]:
        """简单关键词搜索槽"""
        query_lower = query.lower()
        results = []
        for slot in self._slots.values():
            if query_lower in slot.key.lower() or query_lower in slot.value.lower():
                results.append((slot.key, slot.value, slot.confidence))
        results.sort(key=lambda x: x[2], reverse=True)
        return results

    def get_all(self) -> Dict[str, str]:
        """获取所有槽的kv映射"""
        return {k: v.value for k, v in self._slots.items()}

    def count(self) -> int:
        return len(self._slots)

    def to_dict(self) -> Dict:
        """导出为字典"""
        return {
            key: {
                "value": slot.value,
                "scope": slot.scope,
                "confidence": slot.confidence,
                "source": slot.source,
                "previous_value": slot.previous_value
            }
            for key, slot in self._slots.items()
        }

    def from_dict(self, data: Dict) -> None:
        """从字典恢复"""
        for key, info in data.items():
            self._slots[key] = MemorySlot(
                key=key,
                value=info["value"],
                scope=info.get("scope", "user"),
                confidence=info.get("confidence", 1.0),
                source=info.get("source", ""),
                previous_value=info.get("previous_value")
            )
            self._scope_index.setdefault(info.get("scope", "user"), []).append(key)


# ============ 增强版 VectorMemory (混合检索 + 槽记忆) ============

import re
import math

class EnhancedVectorMemory(VectorMemory):
    """增强版向量记忆
    
    在VectorMemory基础上增加：
    1. BM25混合检索 (RRF融合)
    2. 结构化记忆槽 (精确kv事实)
    3. 冲突检测 (新增记忆与已有记忆矛盾)
    
    用法:
        evm = EnhancedVectorMemory()
        
        # 设置事实槽
        evm.set_slot("用户偏好", "DeepSeek API优先")
        
        # 添加语义记忆
        evm.add("SSC的主要成分是矿渣", importance=0.7)
        
        # 混合检索
        results = evm.hybrid_retrieve("SSC成分", top_k=5)
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.bm25 = BM25Retriever()
        self.slots = StructuredSlotMemory()
        self._bm25_indexed: set = set()  # 已索引BM25的entry_id

        logger.info("[EnhancedVectorMemory] BM25 + Slots initialized")

    def add(
        self,
        content: str,
        role: str = "user",
        importance: float = 1.0,
        tier: Optional[MemoryTier] = None,
        metadata: Optional[Dict] = None,
        is_fact: bool = False,
        fact_key: Optional[str] = None
    ) -> MemoryEntry:
        """添加记忆（增强版）
        
        Args:
            is_fact: 是否为事实性信息（存入slot）
            fact_key: 事实的key（is_fact=True时必填）
        """
        entry = super().add(content, role, importance, tier, metadata)

        # BM25索引
        entry_id = entry.metadata.get("entry_id", "")
        if entry_id and entry_id not in self._bm25_indexed:
            self.bm25.index(entry_id, content)
            self._bm25_indexed.add(entry_id)

        # 事实性信息同步到slot
        if is_fact and fact_key:
            self.slots.set(fact_key, content, source="auto_extract")

        # 冲突检测
        self._check_conflict(entry)

        return entry

    def set_slot(self, key: str, value: str, **kwargs) -> Optional[str]:
        """设置结构化记忆槽"""
        return self.slots.set(key, value, **kwargs)

    def get_slot(self, key: str, default: Optional[str] = None) -> Optional[str]:
        """获取结构化记忆槽"""
        return self.slots.get(key, default)

    def hybrid_retrieve(
        self,
        query: str,
        top_k: int = 5,
        vector_weight: float = 0.7,
        bm25_weight: float = 0.3
    ) -> List[MemoryEntry]:
        """混合检索：BM25 + 向量 + RRF融合
        
        Args:
            query: 查询文本
            top_k: 返回数量
            vector_weight: 向量检索权重
            bm25_weight: BM25检索权重
        """
        # 1. 向量检索
        vector_results = self.vector_store.search(query, top_k=top_k * 2)
        vector_ranking = [
            (r.entry.metadata.get("entry_id", f"v_{i}"), r.score)
            for i, r in enumerate(vector_results)
        ]

        # 2. BM25检索
        bm25_ranking = self.bm25.search(query, top_k=top_k * 2)

        # 3. RRF融合
        fused = reciprocal_rank_fusion(vector_ranking, bm25_ranking)

        # 4. 回查entry
        entry_map = {}
        for entry in self.l1_hot + self.l2_semantic + self.l3_episodic:
            eid = entry.metadata.get("entry_id", "")
            if eid:
                entry_map[eid] = entry

        results = []
        seen = set()
        for doc_id, score in fused:
            entry = entry_map.get(doc_id)
            if entry and doc_id not in seen:
                results.append(entry)
                seen.add(doc_id)
            if len(results) >= top_k:
                break

        # 补充：从slot精确匹配
        slot_results = self.slots.search(query)
        if slot_results:
            slot_content = " | ".join(f"{k}={v}" for k, v, _ in slot_results[:3])
            slot_entry = MemoryEntry(
                content=f"[事实] {slot_content}",
                role="system",
                importance=0.9
            )
            results.insert(0, slot_entry)

        self._stats["total_retrieves"] += 1
        return results[:top_k]

    def _check_conflict(self, new_entry: MemoryEntry) -> None:
        """检查新增记忆与已有记忆的冲突
        
        如果新记忆与L1/L2中某条记忆的语义高度相似但内容不同，
        则标记为潜在冲突。
        """
        if not new_entry.embedding:
            return

        threshold = self.compress_similarity_threshold + 0.05  # 略高于压缩阈值

        for entry in self.l1_hot + self.l2_semantic:
            if entry is new_entry or not entry.embedding:
                continue
            if entry.metadata.get("entry_id") == new_entry.metadata.get("entry_id"):
                continue

            sim = cosine_similarity(new_entry.embedding, entry.embedding)

            if sim >= threshold and entry.content != new_entry.content:
                # 高相似但内容不同 = 潜在冲突
                new_entry.metadata["conflict_with"] = entry.metadata.get("entry_id", "")
                new_entry.metadata["conflict_similarity"] = round(sim, 3)
                logger.warning(
                    f"[EnhancedVectorMemory] Potential conflict: "
                    f"'{new_entry.content[:50]}...' vs '{entry.content[:50]}...' "
                    f"(sim={sim:.3f})"
                )
                break

    def get_conflicts(self) -> List[Dict]:
        """获取所有检测到的冲突"""
        conflicts = []

        # 来自记忆的冲突
        for entry in self.l1_hot + self.l2_semantic:
            if "conflict_with" in entry.metadata:
                conflicts.append({
                    "type": "semantic_conflict",
                    "entry_id": entry.metadata.get("entry_id", ""),
                    "content": entry.content[:100],
                    "conflict_with": entry.metadata["conflict_with"],
                    "similarity": entry.metadata.get("conflict_similarity", 0)
                })

        # 来自槽的冲突
        conflicts.extend(self.slots.get_conflicts())

        return conflicts

    def get_stats(self) -> Dict:
        """获取统计信息（增强版）"""
        base_stats = super().get_stats()
        base_stats["slots"] = self.slots.count()
        base_stats["slot_conflicts"] = len(self.slots.get_conflicts())
        base_stats["bm25_indexed"] = len(self._bm25_indexed)
        return base_stats


# 全局实例
_vector_memory_instance: Optional[VectorMemory] = None


def get_vector_memory() -> VectorMemory:
    """获取全局向量记忆实例
    
    默认使用 NGramTFIDFProvider + PersistentVectorStore
    """
    global _vector_memory_instance
    if _vector_memory_instance is None:
        # 默认使用语义 n-gram 嵌入 + 持久化存储
        provider = NGramTFIDFProvider()
        store = PersistentVectorStore(provider)
        _vector_memory_instance = VectorMemory(
            embedding_provider=provider,
            vector_store=store
        )
    return _vector_memory_instance
