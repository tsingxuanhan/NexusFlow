# Nemotron-3 Embed 集成实施方案

> 2026-07-18 | v1.0 | 景

## 一、NexusFlow 框架层集成

### 1.1 核心改动：新增 NemotronEmbeddingProvider

**文件**：`nexusflow/memory/nemotron_provider.py`（新建）

```python
class NemotronEmbeddingProvider(EmbeddingProvider):
    """
    Nemotron-3 Embed 神经语义嵌入提供者
    
    实现 EmbeddingProvider 抽象接口，无缝替换现有 Provider。
    
    三种模型自动适配：
    - 8B-BF16: 云端高精度（RTEB #1, 78.5%）
    - 1B-BF16: 边缘低延迟（RTEB 72.4%）
    - 1B-NVFP4: Blackwell高吞吐（2x throughput）
    
    三种接入方式：
    - local: 本地 vLLM/SentenceTransformers 推理
    - nim: NVIDIA NIM API (build.nvidia.com)
    - openrouter: OpenRouter API (1B免费)
    """
    
    def embed(self, text: str) -> List[float]:
        """
        核心接口 — 必须兼容现有 EmbeddingProvider.embed()
        自动添加 "query: " / "passage: " 前缀
        """
    
    def embed_batch(self, texts: List[str]) -> List[List[float]]:
        """批量编码 — 兼容现有接口"""
```

**设计原则**：
- 继承 `EmbeddingProvider`，实现 `embed()` + `embed_batch()` 两个方法
- 所有下游模块**零修改**即可切换——只需把构造函数参数从 `NGramTFIDFProvider()` 换成 `NemotronEmbeddingProvider()`
- 保留现有 TF-IDF Provider 作为 fallback（离线/无API时）

### 1.2 改动清单（4个文件）

| 文件 | 改动 | 影响范围 |
|------|------|---------|
| `memory/nemotron_provider.py` | **新建**：NemotronEmbeddingProvider | 核心新模块 |
| `memory/vector_memory.py` | **修改**：VectorMemory.__init__() 的 default_provider 参数化 | L739: `NGramTFIDFProvider()` → 可配置 |
| `memory/archival_memory.py` | **修改**：ArchivalMemory 支持向量索引分支 | NGramTFIDFIndex 旁路 Nemotron 向量索引 |
| `core/skill_retriever.py` | **修改**：SkillGraph 增加语义检索方法 | 新增 `semantic_search()` 方法 |
| `core/edge_cloud_scheduler.py` | **修改**：TierResource 增加 embedding_model 字段 | 调度器感知 embedding 模型版本 |

### 1.3 端边云自适应逻辑

在 `EdgeCloudScheduler` 中新增 EmbeddingModelRouter：

```python
class EmbeddingModelRouter:
    """根据部署层自动选择 Nemotron 模型版本"""
    
    ROUTING = {
        DeployTier.EDGE:  "1B-BF16",    # 本地设备 → 轻量模型
        DeployTier.FOG:   "1B-NVFP4",   # 边缘服务器 → 量化高吞吐
        DeployTier.CLOUD: "8B-BF16",    # GPU集群 → 全精度
    }
    
    def select_model(self, tier: DeployTier, task: Dict) -> str:
        """
        调度逻辑：
        1. 查当前部署层 → 默认模型
        2. 如果任务要求高精度（如论文检索）→ 上抛到Cloud用8B
        3. 如果要求低延迟（如实时Skill匹配）→ 留在Edge用1B
        """
```

**关键设计**：这个路由逻辑是 NexusFlow 独有的架构创新。CrewAI/LangGraph 根本没有端边云调度器，所以无法做 embedding 模型的自适应选择。

### 1.4 混合检索策略（Hybrid Retrieval）

不直接抛弃 TF-IDF，而是用 RRF（Reciprocal Rank Fusion）融合：

```
最终得分 = α × rank(Nemotron向量检索) + (1-α) × rank(TF-IDF检索)
```

- α 默认 0.7（偏重语义）
- 对于代码检索、精确关键词查询 → 自动降低 α（偏重字面匹配）
- 这个混合策略在学术检索领域被证明优于任何单一方法

---

## 二、AI4S 应用层集成

### 2.1 知识库重建

现有知识库文件：
- `knowledge/building-materials-fundamentals.md`
- `knowledge/ai-building-materials-papers.md`
- `knowledge/co2-capture-materials.md`

操作：
1. 对每个文件做分块（chunk_size=512 tokens, overlap=64）
2. 用 Nemotron 1B-BF16 生成向量
3. 建立向量索引 + 保留原 TF-IDF 索引（用于对比实验）

### 2.2 评测集构建

从知识库内容中人工构建 30-50 条评测 QA 对：

```python
eval_set = [
    {
        "query": "纳米SiO2如何提高混凝土耐久性？",
        "relevant_chunks": ["chunk_003", "chunk_017"],  # 标准答案
        "difficulty": "hard",  # 需要同义理解（SiO2=纳米二氧化硅）
    },
    {
        "query": "What is the carbon footprint of LC3 cement?",
        "relevant_chunks": ["chunk_022", "chunk_045"],
        "difficulty": "cross_lingual",  # 英文query检索中文知识库
    },
    # ...
]
```

### 2.3 评测指标

| 指标 | 含义 | 目标 |
|------|------|------|
| Recall@5 | top-5结果中包含正确答案的比例 | TF-IDF → Nemotron 提升 ≥15% |
| MRR | 第一个正确结果的平均排名倒数 | 提升 ≥10% |
| NDCG@10 | 排序质量 | 提升 ≥8% |
| 跨语言Recall | 英文query检索中文文档 | 从 ~0% → ≥60% |
| 延迟 | 单次检索耗时 | 1B版 < 50ms（GPU） |

---

## 三、Benchmark 实施方案

### 3.1 必须做 Benchmark

理由：
1. **比赛评审必需**：没有量化数据就是空口说"提升了"，评委不会认可
2. **论文级严谨性**：ablation study 是 AGI 框架评审的标准要求
3. **叙事闭环**：框架升级 → 实验验证 → 量化结论 → 比赛展示

### 3.2 Benchmark 设计

**实验1：检索质量对比（Before vs After）**

```
输入：50条评测query（覆盖中文/英文/跨语言/同义词/精确匹配）
对比：
  - Baseline: NGramTFIDFProvider (现有)
  - Variant A: NemotronEmbeddingProvider (纯语义)
  - Variant B: Hybrid(α=0.7) (混合检索)
  - Variant C: Hybrid(α=0.5)
输出：Recall@5, MRR, NDCG@10 对比表
```

**实验2：端边云延迟对比**

```
输入：1000条query
对比：
  - 8B-BF16 (模拟云端，RTX 3080 Ti)
  - 1B-BF16 (边缘，RTX 3080 Ti)
  - 1B-NVFP4 (模拟Blackwell，用INT4量化近似)
输出：延迟(ms)、吞吐量(qps)、显存占用(GB)
```

**实验3：Skill检索准确率**

```
输入：20种不同类型的任务描述
对比：
  - SkillGraph 规则匹配 (现有)
  - SkillGraph + Nemotron 语义匹配 (新增)
输出：Top-3命中率
```

**实验4：下游任务质量（端到端）**

```
输入：10个完整的科研任务（含文献综述、配方优化等）
对比：
  - 全链路用 TF-IDF 检索
  - 全链路用 Nemotron 检索
输出：LLM质量评分（用现有的 llm_quality_scorer.py）
```

### 3.3 实验脚本

新建：`examples/nemotron_benchmark/`

```
examples/nemotron_benchmark/
├── retrieval_quality_benchmark.py    # 实验1
├── edge_cloud_latency_benchmark.py   # 实验2
├── skill_retrieval_benchmark.py      # 实验3
├── e2e_task_quality_benchmark.py     # 实验4
├── eval_dataset/                     # 评测集
│   ├── retrieval_qa.json             # 50条QA对
│   └── skill_tasks.json              # 20种任务
└── report.md                         # 自动生成报告
```

### 3.4 预期结果叙事

比赛答辩时的展示逻辑：

> "我们将检索基础设施从传统 TF-IDF 升级为 NVIDIA Nemotron-3 Embed（RTEB 榜首，78.5%），
> 实验表明检索 Recall@5 提升了 XX%，跨语言检索从 0% 提升到 XX%。
> 更重要的是，NexusFlow 的端边云调度器可以根据部署层自动选择 8B/1B/1B-NVFP4 三种模型，
> 在保持 XX% 精度的同时将边缘节点延迟控制在 XXms 以内。
> 这是 CrewAI、LangGraph 等框架无法实现的——因为它们没有端边云调度能力。"

---

## 四、实施时间线

| 阶段 | 内容 | 预计耗时 |
|------|------|---------|
| **P0** | NemotronEmbeddingProvider + 基础集成 | 1天 |
| **P1** | AI4S 知识库重建 + 评测集构建 | 1天 |
| **P2** | 4组 Benchmark 实验 | 1-2天 |
| **P3** | 报告生成 + 技术文档更新 | 0.5天 |
| **P4** | 端边云模型路由 + 自适应演示 | 1天 |
| **总计** | | **4.5-5.5天** |

以9月15日截止算，还有近2个月，时间充裕。

---

## 五、与炉守讨论的关键问题

1. **Benchmark 的评测集规模**：50条够不够？还是需要更大规模才有统计显著性？
2. **混合检索的α值**：0.7 是否合适？是否需要自适应α？
3. **比赛叙事优先级**：先讲"检索质量提升"还是先讲"端边云自适应架构"？
4. **是否需要微调**：Nemotron 提供 NeMo AutoModel 微调 recipe，要不要用建材文献做 domain adaptation？

---

## 六、方案自审与修复（2026-07-18 补充）

### 自审发现 8 个问题

#### 🔴 严重（3个）

**问题1：向量维度不兼容**
Nemotron 输出 ~2048-4096 维，现有 TF-IDF 用 5000 维。`PersistentVectorStore` 已存数据在维度上完全不兼容，两个向量空间不可比。RRF 混合检索在 rank 层面操作可以规避直接拼接，但底层索引必须重建。

**问题2：端边云路由逻辑太天真**
`EmbeddingModelRouter` 仅按 `DeployTier` 硬映射，存在三个严重缺陷：
- ① NVFP4 只在 Blackwell 架构有硬件加速，Ampere（3080 Ti）跑 NVFP4 无加速意义
- ② 缺少任务复杂度维度——同设备上的简单匹配 vs 复杂跨语言检索应选不同模型
- ③ 无冷启动延迟处理——本地模型首次加载需数十秒

**问题3：评测集自建偏误**
50 条 QA 由开发者本人从知识库构建，存在 experimenter bias——会无意识构造"TF-IDF 答错但 Nemotron 答对"的题目。

#### 🟡 中等（3个）

**问题4：混合检索 α 自适应逻辑缺失**
方案称"代码检索自动降低 α"，但无具体判断标准和分类特征。

**问题5：分块参数未验证**
`chunk_size=512, overlap=64` 未根据知识库实际内容验证。建材文献中完整实验结论约 200 token，512 分块会切断上下文。

**问题6：现有数据迁移路径未说明**
未说明 PersistentVectorStore 已有向量数据的处理方式（丢弃/双索引/迁移脚本）。

#### 🟢 轻微（2个）

**问题7：OpenRouter 免费 API 稳定性**
免费版 RPM 限制低，大规模知识库嵌入可能被 rate limit。

**问题8：Benchmark 实验2 硬件代表性**
单卡 3080 Ti 模拟三层部署，无法反映真实网络延迟和 CPU-only 边缘设备。

---

### 修复方案

| # | 修复措施 | 具体做法 |
|---|---------|---------|
| 1 | 新建独立向量存储 | 新建 `NemotronVectorStore`，独立于 `PersistentVectorStore`；RRF 在 rank 层融合；旧数据保留不迁移，新数据双写 |
| 2 | 二维路由 + 架构感知 | 路由维度改为 `(DeployTier, TaskComplexity)`；Ampere 强制跳过 NVFP4 选 BF16；加冷启动预热队列 |
| 3 | 三层评测集构建 | ① 论文摘要自动抽取 QA（无人为偏误）② LLM 对抗生成负样本 ③ 人工审核仅占 30% |
| 4 | Query 特征自动选 α | query < 10字 + 含英文术语 → α=0.4；含跨语言/同义词线索 → α=0.8；其余默认 0.6 |
| 5 | 知识库长度分布驱动分块 | 先统计 3 个知识库 P50/P90 长度分布，建材文献预计 P50≈300 token → chunk_size=400 |
| 6 | 迁移脚本 | 写 `migrate_to_nemotron.py`：读旧向量→Nemotron 重新编码→写入新 store；支持 `--dry-run` + 进度条 |
| 7 | 本地优先 + fallback | 本地 1B-BF16 嵌入为主，OpenRouter 仅作备用；加 retry + rate limit handler |
| 8 | 真实延迟分层测试 | ① 本地 3080 Ti 测 GPU 推理延迟（模型间对比）② NIM API 测真实云端网络延迟 ③ CPU 模式模拟资源受限边缘 |
