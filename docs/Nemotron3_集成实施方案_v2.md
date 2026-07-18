# Nemotron-3 Embed 集成实施方案 v2（收敛版）

> 2026-07-18 | 景 | 经两轮自审收敛

## 设计原则（自审后确立）

1. **做加法不做替换**：保留全部现有代码，新模块做增量接入
2. **RRF 优于 α 加权**：代码已有 `reciprocal_rank_fusion()`，直接用，避免"需要语义能力来配置语义模型"的循环论证
3. **双索引并行，不迁移**：旧数据用 TF-IDF 继续检索，新数据双写，RRF 融合两路结果
4. **本地优先**：Phase 1 只用本地 1B-BF16，不混用 API（避免向量空间不一致）
5. **GPU 感知路由**：基于 `TierResource.gpu_memory_gb` 做模型选择，不硬编码架构假设
6. **接口向后兼容**：`EmbeddingProvider` 新增可选方法，现有子类零修改

---

## 一、代码改动清单（6 个文件）

### 1.1 `nexusflow/memory/vector_memory.py` — 激活混合检索 + 接口增强

**改动 A：EmbeddingProvider 增加 query/passage 区分**

```python
class EmbeddingProvider(ABC):
    @abstractmethod
    def embed(self, text: str) -> List[float]:
        pass
    
    @abstractmethod
    def embed_batch(self, texts: List[str]) -> List[List[float]]:
        pass
    
    # --- 新增可选方法（默认实现回退到 embed） ---
    def embed_query(self, text: str) -> List[float]:
        """编码查询文本。子类可覆写添加 query 前缀。"""
        return self.embed(text)
    
    def embed_document(self, text: str) -> List[float]:
        """编码文档文本。子类可覆写添加 passage 前缀。"""
        return self.embed(text)
```

**影响**：SimpleEmbeddingProvider、NGramTFIDFProvider、APIKeywordProvider 全部零修改（继承默认实现）。

**改动 B：VectorMemory.retrieve() 接入 BM25 + RRF**

现有代码（L878）：
```python
# 向量检索
results = self.vector_store.search(query, top_k=top_k * 2)
```

改为：
```python
# 向量检索
results = self.vector_store.search(query, top_k=top_k * 2)

# BM25 检索（激活已有但未接入的代码）
bm25_results = []
if hasattr(self, '_bm25') and self._bm25 is not None:
    bm25_results = self._bm25.search(query, top_k=top_k * 2)

# RRF 融合（复用已有的 reciprocal_rank_fusion 函数）
if bm25_results:
    vector_tuples = [(r.entry.metadata.get('entry_id', ''), r.score) for r in results]
    fused = reciprocal_rank_fusion(vector_tuples, bm25_results)
    # 按融合后的 ID 排序重新组织 results
    id_to_result = {r.entry.metadata.get('entry_id', ''): r for r in results}
    results = [id_to_result[eid] for eid, _ in fused if eid in id_to_result]
```

**改动 C：VectorMemory.__init__() 初始化 BM25 索引**

在 `__init__` 中（L770 附近）添加：
```python
# BM25 混合检索器（延迟初始化，有数据时自动索引）
self._bm25: Optional[BM25Retriever] = None
```

在 `add()` 方法中（L820 附近），同步索引 BM25：
```python
# 同步 BM25
if self._bm25 is None:
    self._bm25 = BM25Retriever()
self._bm25.index(entry.metadata.get('entry_id', str(id(entry))), content)
```

在 `_load()` 或 PersistentVectorStore 加载数据后，从已有 entries 重建 BM25 索引。

### 1.2 `nexusflow/memory/nemotron_provider.py` — 新建

```python
"""
Nemotron-3 Embed 神经语义嵌入提供者

三种接入方式：
- local: 本地 SentenceTransformers 推理（默认）
- nim: NVIDIA NIM API
- openrouter: OpenRouter API
"""

class NemotronEmbeddingProvider(EmbeddingProvider):
    def __init__(
        self,
        model_name: str = "nvidia/Nemotron-3-Embed-1B-BF16",
        mode: str = "local",       # local / nim / openrouter
        dimension: int = 2048,     # Nemotron 1B 输出维度
        device: str = "auto",      # auto / cuda / cpu
    ):
        self.model_name = model_name
        self.mode = mode
        self.dimension = dimension
        self._model = None
        self._device = device
    
    def _ensure_loaded(self):
        """延迟加载模型"""
        if self._model is not None:
            return
        if self.mode == "local":
            from sentence_transformers import SentenceTransformer
            self._model = SentenceTransformer(
                self.model_name,
                device=self._device if self._device != "auto" else None,
            )
    
    def embed(self, text: str) -> List[float]:
        """兼容接口 — 默认作为 document 编码"""
        return self.embed_document(text)
    
    def embed_batch(self, texts: List[str]) -> List[List[float]]:
        return [self.embed(t) for t in texts]
    
    def embed_query(self, text: str) -> List[float]:
        """查询编码 — 添加 query: 前缀"""
        self._ensure_loaded()
        return self._encode(f"query: {text}")
    
    def embed_document(self, text: str) -> List[float]:
        """文档编码 — 添加 passage: 前缀"""
        self._ensure_loaded()
        return self._encode(f"passage: {text}")
    
    def _encode(self, text: str) -> List[float]:
        if self.mode == "local":
            embedding = self._model.encode(text, normalize_embeddings=True)
            return embedding.tolist()
        # nim / openrouter 模式留作扩展
        raise NotImplementedError(f"Mode {self.mode} not implemented")
```

**关键设计**：
- 延迟加载（`_ensure_loaded`）：避免 import 时就占显存
- `embed_query` / `embed_document` 覆写父类默认实现，添加 Nemotron 要求的前缀
- `embed()` 回退到 `embed_document()`，保持与现有调用方的兼容性
- dimension=2048（Nemotron 1B 实际输出维度，需在首次运行后验证）

### 1.3 `nexusflow/memory/nemotron_store.py` — 新建

独立的 Nemotron 向量存储，不与 PersistentVectorStore 混合。

```python
"""
Nemotron 专用向量存储

与 PersistentVectorStore 完全独立：
- 使用 Nemotron 高维语义向量
- 独立持久化文件（data/nemotron_memory.json）
- 通过 RRF 与 BM25 结果融合
"""

class NemotronVectorStore:
    def __init__(
        self,
        embedding_provider: NemotronEmbeddingProvider,
        persist_path: str = "./data/nemotron_memory.json",
    ):
        self.embedding_provider = embedding_provider
        self.persist_path = persist_path
        self.entries: List[dict] = []  # {id, content, embedding, metadata}
        self._load()
    
    def add(self, entry_id: str, content: str, metadata: dict = None):
        """添加文档 — 使用 embed_document()"""
        embedding = self.embedding_provider.embed_document(content)
        self.entries.append({
            "id": entry_id,
            "content": content,
            "embedding": embedding,
            "metadata": metadata or {},
        })
    
    def search(self, query: str, top_k: int = 5) -> List[Tuple[str, float]]:
        """检索 — 使用 embed_query()"""
        query_vec = self.embedding_provider.embed_query(query)
        scored = []
        for entry in self.entries:
            sim = cosine_similarity(query_vec, entry["embedding"])
            scored.append((entry["id"], sim))
        scored.sort(key=lambda x: x[1], reverse=True)
        return scored[:top_k]
```

### 1.4 `nexusflow/memory/archival_memory.py` — 增加 Nemotron 索引分支

ArchivalMemory 已有 `_ngram_index`（TF-IDF）+ `_keyword_index` 双索引 + RRF。

**改动**：新增 `_nemotron_index`，三路 RRF。

```python
class ArchivalMemory:
    def __init__(self, ...):
        # 现有
        self._ngram_index = NGramTFIDFIndex()
        self._keyword_index = KeywordIndex()
        # 新增
        self._nemotron_index = None  # 延迟初始化
    
    def enable_nemotron(self, provider: NemotronEmbeddingProvider):
        """启用 Nemotron 语义索引"""
        from nexusflow.memory.nemotron_store import NemotronIndexAdapter
        self._nemotron_index = NemotronIndexAdapter(provider)
    
    def search(self, query, top_k=None, rrf_k=60):
        top_k = top_k or self.top_k
        ngram_results = self._ngram_index.search(query, top_k=top_k * 2)
        keyword_results = self._keyword_index.search(query, top_k=top_k * 2)
        
        # RRF 融合（现有两路）
        rrf_scores = {}
        for rank, (eid, _) in enumerate(ngram_results):
            rrf_scores[eid] = rrf_scores.get(eid, 0) + 1.0 / (rrf_k + rank + 1)
        for rank, (eid, _) in enumerate(keyword_results):
            rrf_scores[eid] = rrf_scores.get(eid, 0) + 1.0 / (rrf_k + rank + 1)
        
        # 新增第三路（如果启用）
        if self._nemotron_index is not None:
            nemotron_results = self._nemotron_index.search(query, top_k=top_k * 2)
            for rank, (eid, _) in enumerate(nemotron_results):
                rrf_scores[eid] = rrf_scores.get(eid, 0) + 1.0 / (rrf_k + rank + 1)
        
        # ... 后续排序和过滤逻辑不变
```

**`store()` 方法同步**：存储新条目时，如果 `_nemotron_index` 已初始化，同步写入。

**`search_multi_hop()` 自动受益**：因为它调用 `self.search()`，三路 RRF 自动生效，无需额外改动。

### 1.5 `nexusflow/core/edge_cloud_scheduler.py` — GPU 感知 Embedding 路由

```python
class EmbeddingModelRouter:
    """根据部署层资源和任务特征选择 embedding 模型
    
    路由逻辑（二维）：
    1. 查当前 TierResource.gpu_memory_gb → 可用模型集合
    2. 查 TierResource.gpu_architecture（新增字段）→ 排除不兼容量化
    3. 选精度最高的可用模型
    """
    
    # 模型规格表
    MODEL_SPECS = {
        "nemotron-8b-bf16":  {"vram_gb": 16, "arch": None,    "quality": 0.95},
        "nemotron-1b-bf16":  {"vram_gb": 2.3, "arch": None,    "quality": 0.85},
        "nemotron-1b-nvfp4": {"vram_gb": 1.2, "arch": "blackwell", "quality": 0.93},
        "nemotron-api":      {"vram_gb": 0,   "arch": None,    "quality": 0.85},
    }
    
    def select(self, resource: TierResource) -> str:
        """给定资源，返回最优模型名"""
        candidates = []
        for name, spec in self.MODEL_SPECS.items():
            # 显存够不够
            if spec["vram_gb"] > resource.gpu_memory_gb:
                continue
            # 架构兼容（NVFP4 只在 Blackwell 有加速）
            if spec["arch"] and resource.gpu_architecture != spec["arch"]:
                continue
            candidates.append((name, spec["quality"]))
        
        if not candidates:
            return "nemotron-api"  # 无 GPU → API 模式
        
        # 选精度最高的
        candidates.sort(key=lambda x: x[1], reverse=True)
        return candidates[0][0]
```

**TierResource 新增字段**：
```python
@dataclass
class TierResource:
    # ... 现有字段不变
    gpu_architecture: str = ""  # 新增：ampere / ada / blackwell / None
```

**向后兼容**：`gpu_architecture` 默认空字符串，现有代码零影响。

### 1.6 `nexusflow/core/skill_retriever.py` — 语义检索增强

SkillRetriever 当前用场景分类 + 关键词匹配。新增 `semantic_search()` 方法。

```python
class SkillRetriever:
    def __init__(self, ...):
        # ... 现有逻辑不变
        self._nemotron_provider = None
    
    def enable_semantic_search(self, provider: NemotronEmbeddingProvider):
        """启用语义检索"""
        self._nemotron_provider = provider
        # 预计算所有 Skill Card 的语义向量
        self._skill_embeddings = {}
        for skill in self.graph.all_skills():
            text = f"{skill.name} {skill.description} {' '.join(skill.tags)}"
            self._skill_embeddings[skill.name] = provider.embed_document(text)
    
    def retrieve(self, task_description, top_k=3):
        # 现有逻辑：场景匹配 + 关键词匹配
        results = self._rule_based_retrieve(task_description, top_k)
        
        # 新增：如果有语义索引，RRF 融合
        if self._nemotron_provider and self._skill_embeddings:
            query_vec = self._nemotron_provider.embed_query(task_description)
            semantic_scores = {}
            for name, skill_vec in self._skill_embeddings.items():
                sim = cosine_similarity(query_vec, skill_vec)
                semantic_scores[name] = sim
            # 合并到 results 的得分中
            # ...（RRF 融合逻辑）
        
        return results
```

---

## 二、集成架构总览

```
┌─────────────────────────────────────────────────────┐
│                    调用方                             │
│   VectorMemory.retrieve()  ArchivalMemory.search()   │
│   SkillRetriever.retrieve()  MultiHopRAG            │
├─────────────────────────────────────────────────────┤
│              RRF 融合层（已有代码）                    │
│   reciprocal_rank_fusion() ← 三路融合                │
├────────────────┬────────────────┬───────────────────┤
│  Nemotron 索引  │  TF-IDF 索引   │  BM25 / 关键词    │
│  (新增)         │  (现有)        │  (现有)            │
│                │                │                   │
│ NemotronVector │ NGramTFIDF     │ BM25Retriever     │
│ Store          │ Index/Provider │ KeywordIndex       │
│                │                │                   │
│ embed_query()  │ embed()        │ tokenize()        │
│ embed_document │ (TF-IDF向量)   │ (词频统计)         │
├────────────────┴────────────────┴───────────────────┤
│           NemotronEmbeddingProvider                  │
│   local: SentenceTransformer 1B-BF16 (RTX 3080 Ti)  │
│   延迟加载 | query/passage 前缀 | 自动 device 选择    │
└─────────────────────────────────────────────────────┘
```

---

## 三、数据流（关键路径）

### 3.1 VectorMemory 检索路径（改动后）

```
query → VectorMemory.retrieve(query)
  ├─ vector_store.search(query)        → 向量结果（TF-IDF，现有路径）
  ├─ bm25.search(query)               → BM25 结果（新激活）
  └─ reciprocal_rank_fusion(向量, BM25) → 融合结果

  如果启用 Nemotron:
  ├─ nemotron_store.search(query)      → 语义结果（Nemotron，新路径）
  └─ RRF(向量, BM25, Nemotron)        → 三路融合
```

### 3.2 ArchivalMemory 检索路径（改动后）

```
query → ArchivalMemory.search(query)
  ├─ _ngram_index.search(query)       → TF-IDF 结果（现有）
  ├─ _keyword_index.search(query)     → 关键词结果（现有）
  ├─ _nemotron_index.search(query)    → 语义结果（新增，可选）
  └─ RRF(三路)                        → 融合排序
```

### 3.3 数据存储路径

```
新条目写入:
  store() → _ngram_index.add()       (现有，始终执行)
          → _keyword_index.add()      (现有，始终执行)
          → _nemotron_index.add()     (新增，仅当启用)
          → persistent_vector_store   (现有，TF-IDF 向量)

持久化文件:
  data/vector_memory.json      ← 现有，TF-IDF 向量（5000维）
  data/nemotron_memory.json    ← 新增，Nemotron 向量（2048维）
  data/archival_memory.json    ← 现有，纯文本（索引器重建向量）
```

---

## 四、Benchmark 方案（收敛版）

### 4.1 实验设计原则

- **固定随机种子**：所有实验 seed=42
- **固定 LLM 评估器**：用现有 `llm_quality_scorer.py`，固定 model+temperature
- **独立评测集**：评测 query 不由开发者手工编写，采用自动化+对抗生成

### 4.2 评测集构建（消除偏误）

**第一层：自动化抽取（70%）**
- 从知识库 3 个文件中，每个文件按段落随机采样
- 将段落内容交给 LLM 生成 3 种 query（中文直述/英文翻译/同义改写）
- LLM 同时标注正确答案段落 ID
- 全程无人工参与

**第二层：对抗负样本（20%）**
- 构造 TF-IDF 一定能答对但 Nemotron 可能答错的 query（如精确术语匹配、缩写展开）
- 目的：检验 Nemotron 在字面匹配上是否退化
- 由 LLM 生成，确保挑战性

**第三层：人工审核（10%）**
- 仅做最终检查：剔除自动生成的明显错误 QA
- 不修改 query 内容，只做质量门禁

### 4.3 实验矩阵

| 实验 | 对比项 | 指标 | 规模 |
|------|--------|------|------|
| **E1: 检索质量** | TF-IDF-only vs BM25-only vs Nemotron-only vs RRF(TF-IDF+BM25) vs RRF(三路) | Recall@5, MRR, NDCG@10 | ~150 条 query |
| **E2: 延迟** | 1B-BF16 GPU 推理 vs NIM API vs CPU 模式 | 延迟(ms), 吞吐(qps), 显存(GB) | 1000 条 query |
| **E3: Skill 检索** | 规则匹配 vs 规则+语义(RRF) | Top-3 命中率 | 20 种任务类型 |
| **E4: 端到端** | 全链路 TF-IDF vs 全链路三路 RRF | LLM 质量评分 | 10 个完整任务 |

### 4.4 实验脚本目录

```
examples/nemotron_benchmark/
├── eval_dataset/
│   ├── auto_qa.json          # 第一层：LLM 自动生成
│   ├── adversarial.json      # 第二层：对抗负样本
│   └── skill_tasks.json      # E3 任务集
├── e1_retrieval_quality.py   # 实验1
├── e2_latency_benchmark.py   # 实验2
├── e3_skill_retrieval.py     # 实验3
├── e4_e2e_task_quality.py    # 实验4
└── report.md                 # 自动生成
```

---

## 五、实施顺序（依赖关系明确）

```
Step 1: EmbeddingProvider 接口增强（L54-66）
        ↓ 无依赖，纯加法
Step 2: NemotronEmbeddingProvider（新建 nemotron_provider.py）
        ↓ 依赖 Step 1
Step 3: VectorMemory 激活 BM25 + RRF（改动 retrieve + __init__ + add）
        ↓ 无依赖，使用已有 BM25Retriever
Step 4: NemotronVectorStore（新建 nemotron_store.py）
        ↓ 依赖 Step 2
Step 5: ArchivalMemory 三路 RRF（改动 search + store）
        ↓ 依赖 Step 2 + Step 4
Step 6: SkillRetriever 语义增强
        ↓ 依赖 Step 2
Step 7: EdgeCloudScheduler EmbeddingModelRouter
        ↓ 依赖 Step 2，新增 gpu_architecture 字段
Step 8: Benchmark 实验
        ↓ 依赖 Step 3-6 全部完成
```

**可并行的**：Step 3 与 Step 2 可以同时进行；Step 7 与 Step 5 可以并行。

---

## 六、Phase 分阶段交付

| Phase | 内容 | 交付物 | 预计耗时 |
|-------|------|--------|---------|
| **P0** | Step 1-3：接口增强 + NemotronProvider + BM25激活 | 可运行的混合检索（无Nemotron），代码可merge | 0.5天 |
| **P1** | Step 4-6：Nemotron接入 + Archival三路 + Skill语义 | 全链路 Nemotron 生效 | 1天 |
| **P2** | Step 7：端边云路由 + TierResource扩展 | 架构演示代码 | 0.5天 |
| **P3** | Step 8：Benchmark 全部实验 | 数据表 + report.md | 1.5天 |
| **P4** | 技术文档更新（v2.9文档增加§检索层升级章节） | 文档更新 | 0.5天 |
| **总计** | | | **4天** |

---

## 七、风险控制

| 风险 | 概率 | 应对 |
|------|------|------|
| 1B-BF16 本地加载失败（sentence-transformers 兼容问题） | 中 | 回退方案：用 OpenRouter API 的 1B 免费版，但仅做 demo 不入索引 |
| Nemotron 实际维度不是 2048 | 低 | `_encode()` 首次运行打印 `len(embedding)` 验证 |
| RRF 三路融合反而比两路差 | 低 | Benchmark E1 会检测；如果发生，保留两路 RRF，Nemotron 仅作 Skill 检索用 |
| 模型下载耗时过长（~2GB） | 高 | 用 huggingface mirror 或 modelscope 国内镜像 |
| RTX 3080 Ti 被抖音占用显存 | 中 | 运行时检测 `torch.cuda.mem_get_info()`，显存不足时报错提示关闭占用程序 |

---

## 八、不做的事（明确排除）

1. **不迁移旧数据**：旧向量继续用 TF-IDF 检索，不重新编码
2. **不用 α 加权**：RRF 天然不需要权重参数
3. **不做微调**：Nemotron 提供 NeMo AutoModel 微调 recipe，但赛前时间不值得投入
4. **不在 Phase 1 混用 API**：避免向量空间不一致
5. **不修改 multi_hop_rag.py**：它调用 ArchivalMemory.search()，三路 RRF 自动生效
6. **不做运行时动态 α 切换**：需要语义能力来配置语义模型，循环论证
