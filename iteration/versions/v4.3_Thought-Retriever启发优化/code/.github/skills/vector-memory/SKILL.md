---
name: vector-memory
description: >
  增强向量记忆系统。支持NGramTFIDF+RRF混合检索、结构化Slot记忆、语义冲突检测、
  L1/L2压缩、重要性衰减和自动清理。当需要Agent持久记忆、知识检索、
  事实管理或记忆优化时使用。
license: MIT
compatibility: Python 3.9+, default NGramTFIDFProvider (no external deps); ChromaDB optional
metadata:
  version: "3.3.0"
  module: vector_memory.py
  lines: ~1683
---

# Vector Memory

xuanshu-agents 的增强记忆系统，三层架构：

## 架构

```
L0: 原始记忆 (全量存储)
L1: 压缩摘要 (语义聚类合并)
L2: 核心索引 (关键词+元数据)
```

## 核心类

| 类 | 说明 |
|----|------|
| `VectorMemory` | 基础向量记忆（TF-IDF + 余弦相似度） |
| `EnhancedVectorMemory` | 增强版：NGramTFIDF+RRF混合检索 + 压缩 + 冲突检测 |
| `StructuredSlotMemory` | 结构化槽位记忆（kv事实精确召回） |
| `NGramTFIDFProvider` | 默认嵌入提供者：N-gram + TF-IDF，零外部依赖 |
| `APIKeywordProvider` | 通过API调用提取关键词的嵌入提供者 |
| `PersistentVectorStore` | 持久化存储（JSON序列化） |
| `SearchResult` | 检索结果数据类 |

## 检索方法

| 方法 | 说明 |
|------|------|
| `retrieve(query, top_k)` | 基础向量检索（余弦相似度） |
| `hybrid_retrieve(query, top_k)` | RRF融合检索（NGramTFIDF + 向量），核心方法 |
| `search(query, top_k)` | 语义搜索入口 |
| `set_slot(key, value, scope)` | 设置结构化槽位 |
| `get_slot(key, scope)` | 精确获取槽位值 |

## 检索策略

- **默认**: 余弦相似度 (NGramTFIDF)
- **增强**: `hybrid_retrieve()` RRF融合（稀疏+向量），不依赖分数归一化
- **Slot**: 精确 key 匹配，支持类型化槽值和 scope 隔离

## 冲突检测

`get_conflicts()` — 当新记忆与已有记忆语义相似度 > 0.90 时触发：
- 同义重复 → 跳过
- 矛盾更新 → 槽值变更追踪

## 压缩机制

- `_compress_l2()`: 语义聚类 → 生成摘要 → 降级到 L2
- `_decay_importance()`: 时间衰减重要性分数
- `_cleanup_expired()`: 清理过期低重要性记忆
- `auto_maintain()`: 自动触发 (每次 add 后检查)

## 向量数据库升级路径

当前默认 `NGramTFIDFProvider`（零依赖）。环境改善后可切换到：
```python
from vector_memory import EnhancedVectorMemory
memory = EnhancedVectorMemory(provider="chromadb")  # 需要 chromadb + sentence-transformers
```

## 注意事项

- ChromaDB/Qdrant 需要 RAM > 4GB + HuggingFace 可达
- Slot Memory 的 key 建议用 `domain.entity.attribute` 格式
- 压缩阈值 `compress_similarity_threshold` 默认 0.85
