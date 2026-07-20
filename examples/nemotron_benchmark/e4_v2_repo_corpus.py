# -*- coding: utf-8 -*-
"""
E4 v2: 端到端任务质量评测（全仓库语料库 + 自带模型评估）

流程:
  1. 扫描仓库所有 .md/.py/.yaml 文件，构建真实语料库
  2. 设计覆盖仓库各方面的 QA 数据集
  3. 分别用 TF-IDF only 和 Nemotron+RRF 检索 top-3 文档
  4. 输出检索结果到 JSON，由 AI 评估器完成回答生成和质量评分

用法:
  python e4_v2_repo_corpus.py --nim_api_key <NIM_KEY>
"""

import argparse
import json
import os
import sys
import time
import hashlib
from typing import List, Dict

# 路径设置
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

BENCH_DIR = os.path.dirname(os.path.abspath(__file__))
RESULTS_DIR = os.path.join(BENCH_DIR, "results")
os.makedirs(RESULTS_DIR, exist_ok=True)

# 排除目录
EXCLUDE_DIRS = {
    '__pycache__', '.git', '.pytest_cache', 'results',
    'codeact', 'node_modules', '.venv', 'venv',
}
EXCLUDE_FILES = {
    'nemotron_store.json', 'e4_nemotron_store.json',
    'e2_nemotron_store.json',
}
# 排除 iteration/versions/ 下的重复内容（只保留最新版本的设计文档）
EXCLUDE_PREFIXES = [
    'docs/iteration/versions/',
]


def scan_repo_files(repo_root: str) -> List[Dict]:
    """扫描仓库文件，构建语料库"""
    docs = []
    supported_ext = {'.md', '.py', '.yaml', '.yml', '.txt'}
    
    for root, dirs, files in os.walk(repo_root):
        # 过滤排除目录
        dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS]
        
        rel_root = os.path.relpath(root, repo_root)
        if rel_root == '.':
            rel_root = ''
        
        # 检查排除前缀
        skip = False
        for prefix in EXCLUDE_PREFIXES:
            if (rel_root + '/').startswith(prefix) or rel_root.startswith(prefix):
                skip = True
                break
        if skip:
            continue
        
        for fname in files:
            ext = os.path.splitext(fname)[1].lower()
            if ext not in supported_ext:
                continue
            if fname in EXCLUDE_FILES:
                continue
            
            fpath = os.path.join(root, fname)
            rel_path = os.path.relpath(fpath, repo_root)
            
            try:
                with open(fpath, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
            except Exception:
                continue
            
            # 跳过太小的文件（< 100 字节）
            if len(content.strip()) < 100:
                continue
            
            # 对大文件做分段（每段最多 3000 字符，按段落分割）
            if len(content) > 4000:
                chunks = split_document(content, max_chunk=3000)
                for i, chunk in enumerate(chunks):
                    doc_id = f"{rel_path}#chunk{i}"
                    docs.append({
                        "id": doc_id,
                        "content": chunk,
                        "source_file": rel_path,
                        "chunk_index": i,
                    })
            else:
                doc_id = rel_path
                docs.append({
                    "id": doc_id,
                    "content": content,
                    "source_file": rel_path,
                    "chunk_index": 0,
                })
    
    return docs


def split_document(text: str, max_chunk: int = 3000) -> List[str]:
    """将长文档按段落/章节分割"""
    chunks = []
    # 优先按 Markdown 标题分割
    sections = []
    current = []
    for line in text.split('\n'):
        if line.startswith('#') and current:
            sections.append('\n'.join(current))
            current = [line]
        else:
            current.append(line)
    if current:
        sections.append('\n'.join(current))
    
    # 合并小 section 到 chunk
    current_chunk = ""
    for section in sections:
        if len(current_chunk) + len(section) > max_chunk and current_chunk:
            chunks.append(current_chunk.strip())
            current_chunk = section
        else:
            current_chunk += "\n" + section if current_chunk else section
    
    if current_chunk.strip():
        chunks.append(current_chunk.strip())
    
    # 如果只有一个 chunk 或分割不理想，按固定长度切
    if len(chunks) <= 1 and len(text) > max_chunk:
        chunks = []
        for i in range(0, len(text), max_chunk):
            chunks.append(text[i:i+max_chunk])
    
    return chunks if chunks else [text]


def build_qa_dataset() -> List[Dict]:
    """构建覆盖仓库各方面的 QA 数据集"""
    return [
        # ===== 架构核心 =====
        {
            "query": "NexusFlow的NexusOrchestrator如何协调多个Agent协同工作？",
            "relevant_doc_id": "nexusflow/core/nexus_orchestrator.py",
            "keywords": ["orchestrator", "agent", "协调", "dispatch"],
        },
        {
            "query": "CognitiveDivisionEngine认知分工引擎的设计原理是什么？",
            "relevant_doc_id": "nexusflow/core/cognitive_division_engine.py",
            "keywords": ["cognitive", "division", "任务分解"],
        },
        {
            "query": "DynamicRouter动态路由如何根据任务特征选择合适的Agent？",
            "relevant_doc_id": "nexusflow/core/dynamic_router.py",
            "keywords": ["router", "dynamic", "selection", "routing"],
        },
        {
            "query": "AdaptiveContextManager自适应上下文管理器的作用是什么？",
            "relevant_doc_id": "nexusflow/core/adaptive_context_manager.py",
            "keywords": ["context", "adaptive", "token", "管理"],
        },
        {
            "query": "EdgeCloudScheduler边缘云调度器如何决策任务在边缘还是云端执行？",
            "relevant_doc_id": "nexusflow/core/edge_cloud_scheduler.py",
            "keywords": ["edge", "cloud", "schedule", "latency"],
        },
        {
            "query": "GoalVerifier如何验证任务目标是否达成？",
            "relevant_doc_id": "nexusflow/core/goal_verifier.py",
            "keywords": ["goal", "verify", "completion", "criteria"],
        },
        {
            "query": "AgentInformationPolicy信息策略如何控制Agent之间的信息流通？",
            "relevant_doc_id": "nexusflow/core/agent_information_policy.py",
            "keywords": ["information", "policy", "filter", "access"],
        },
        # ===== Agent系统 =====
        {
            "query": "NexusFlow中Miner Agent的职责是什么？",
            "relevant_doc_id": "nexusflow/agents/miner.py",
            "keywords": ["miner", "data", "collect", "挖掘"],
        },
        {
            "query": "Artisan Agent在NexusFlow中扮演什么角色？",
            "relevant_doc_id": "nexusflow/agents/artisan.py",
            "keywords": ["artisan", "craft", "generate", "制作"],
        },
        {
            "query": "Assayer Agent的质量检测机制是怎样的？",
            "relevant_doc_id": "nexusflow/agents/assayer.py",
            "keywords": ["assayer", "quality", "check", "检测"],
        },
        {
            "query": "Caster Agent如何将任务分发到不同领域？",
            "relevant_doc_id": "nexusflow/agents/caster.py",
            "keywords": ["caster", "broadcast", "domain", "分发"],
        },
        {
            "query": "Coordinator协调器如何处理Agent间的冲突和死锁？",
            "relevant_doc_id": "nexusflow/agents/coordinator.py",
            "keywords": ["coordinator", "conflict", "deadlock", "协调"],
        },
        {
            "query": "Guardrails安全护栏如何防止Agent执行危险操作？",
            "relevant_doc_id": "nexusflow/agents/guardrails.py",
            "keywords": ["guardrail", "safety", "restrict", "安全"],
        },
        {
            "query": "CircuitBreaker熔断器在Agent系统中起什么作用？",
            "relevant_doc_id": "nexusflow/agents/circuit_breaker.py",
            "keywords": ["circuit", "breaker", "failure", "熔断"],
        },
        # ===== 记忆系统 =====
        {
            "query": "VectorMemory向量记忆如何实现BM25和语义检索的混合？",
            "relevant_doc_id": "nexusflow/memory/vector_memory.py",
            "keywords": ["vector", "bm25", "semantic", "hybrid", "rrf"],
        },
        {
            "query": "NemotronVectorStore如何利用NVIDIA Nemotron模型构建向量存储？",
            "relevant_doc_id": "nexusflow/memory/nemotron_store.py",
            "keywords": ["nemotron", "vector", "store", "embedding"],
        },
        {
            "query": "ArchivalMemory档案记忆如何实现三路RRF融合检索？",
            "relevant_doc_id": "nexusflow/memory/archival_memory.py",
            "keywords": ["archival", "rrf", "fusion", "三路"],
        },
        {
            "query": "MemoryManager如何管理短期记忆和长期记忆的转换？",
            "relevant_doc_id": "nexusflow/memory/memory_manager.py",
            "keywords": ["memory", "manager", "short", "long", "转换"],
        },
        {
            "query": "MultiHopRAG多跳检索如何实现跨文档推理？",
            "relevant_doc_id": "nexusflow/memory/multi_hop_rag.py",
            "keywords": ["multi", "hop", "rag", "推理"],
        },
        {
            "query": "Sleeptime机制如何在Agent空闲时进行记忆整理？",
            "relevant_doc_id": "nexusflow/memory/sleeptime.py",
            "keywords": ["sleeptime", "idle", "consolidate", "整理"],
        },
        {
            "query": "NemotronEmbeddingProvider支持哪些运行模式？",
            "relevant_doc_id": "nexusflow/memory/nemotron_provider.py",
            "keywords": ["nemotron", "provider", "nim", "mode", "embedding"],
        },
        # ===== 认知系统 =====
        {
            "query": "MetaCognition元认知模块如何监控Agent的认知状态？",
            "relevant_doc_id": "nexusflow/cognition/meta_cognition.py",
            "keywords": ["meta", "cognition", "monitor", "监控"],
        },
        {
            "query": "TreeOfThought思维树如何实现多路径探索？",
            "relevant_doc_id": "nexusflow/cognition/tot.py",
            "keywords": ["tree", "thought", "explore", "路径"],
        },
        {
            "query": "CrossDomainReflector跨域反思器如何促进知识迁移？",
            "relevant_doc_id": "nexusflow/cognition/cross_domain.py",
            "keywords": ["cross", "domain", "reflect", "迁移"],
        },
        {
            "query": "TaskTree任务树如何分解和组织复杂任务？",
            "relevant_doc_id": "nexusflow/cognition/task_tree.py",
            "keywords": ["task", "tree", "decompose", "分解"],
        },
        # ===== 协议层 =====
        {
            "query": "A2A Protocol如何实现Agent间的通信协议？",
            "relevant_doc_id": "nexusflow/protocol/a2a_protocol.py",
            "keywords": ["a2a", "protocol", "message", "通信"],
        },
        {
            "query": "MCP Client如何连接外部工具服务？",
            "relevant_doc_id": "nexusflow/protocol/mcp_client.py",
            "keywords": ["mcp", "client", "tool", "连接"],
        },
        {
            "query": "A2A Gateway网关如何管理跨系统的Agent通信？",
            "relevant_doc_id": "nexusflow/protocol/a2a_gateway.py",
            "keywords": ["gateway", "a2a", "cross", "system"],
        },
        # ===== 工具系统 =====
        {
            "query": "ToolRegistry工具注册中心如何管理和发现可用工具？",
            "relevant_doc_id": "tools/tool_registry.py",
            "keywords": ["tool", "registry", "register", "discover"],
        },
        {
            "query": "LiteratureSearch工具如何检索学术文献？",
            "relevant_doc_id": "tools/literature_search.py",
            "keywords": ["literature", "search", "paper", "学术"],
        },
        {
            "query": "ModelRouter模型路由器如何为任务选择最佳模型？",
            "relevant_doc_id": "tools/model_router.py",
            "keywords": ["model", "router", "select", "路由"],
        },
        # ===== 技术文档 =====
        {
            "query": "NexusFlow v2.9的核心架构升级包括哪些内容？",
            "relevant_doc_id": "docs/NexusFlow技术文档v2.9.md",
            "keywords": ["v2.9", "架构", "升级", "核心"],
        },
        {
            "query": "Nemotron-3 Embed集成到NexusFlow的实施方案是什么？",
            "relevant_doc_id": "docs/Nemotron3_集成实施方案_v2.md",
            "keywords": ["nemotron", "embed", "集成", "方案"],
        },
        {
            "query": "Phase2消融实验的设计和结果是什么？",
            "relevant_doc_id": "docs/Phase2_ablation实验报告.md",
            "keywords": ["ablation", "phase2", "实验", "消融"],
        },
        {
            "query": "NexusFlow的精华版设计有哪些核心亮点？",
            "relevant_doc_id": "docs/NexusFlow精华版v2.9.md",
            "keywords": ["精华", "亮点", "核心", "设计"],
        },
        {
            "query": "向量记忆的衰减机制是如何设计的？",
            "relevant_doc_id": "docs/vector_memory.md",
            "keywords": ["vector", "memory", "decay", "衰减"],
        },
        # ===== 配置文件 =====
        {
            "query": "NexusFlow的config.yaml包含哪些核心配置项？",
            "relevant_doc_id": "config/config.yaml",
            "keywords": ["config", "yaml", "配置", "setting"],
        },
        # ===== 服务端 =====
        {
            "query": "NexusFlow Server如何提供API服务？",
            "relevant_doc_id": "server/nexusflow_server.py",
            "keywords": ["server", "api", "endpoint", "服务"],
        },
        {
            "query": "SkillRetriever如何检索和匹配用户技能？",
            "relevant_doc_id": "nexusflow/core/skill_retriever.py",
            "keywords": ["skill", "retriever", "match", "匹配"],
        },
    ]


def simple_chinese_tokenize(text: str) -> List[str]:
    """简易中文分词（用于TF-IDF）"""
    import re
    # 英文单词 + 中文单字/双字组合
    tokens = re.findall(r'[a-zA-Z_][a-zA-Z0-9_]*', text.lower())
    # 中文按字切分
    cn_chars = re.findall(r'[\u4e00-\u9fff]', text)
    tokens.extend(cn_chars)
    # 中文双字
    cn_text = ''.join(cn_chars)
    for i in range(len(cn_text) - 1):
        tokens.append(cn_text[i:i+2])
    return tokens


class SimpleTFIDF:
    """简易 TF-IDF 检索器"""
    def __init__(self):
        self.doc_freq = {}
        self.doc_tokens = {}
        self.idf = {}
        self.n_docs = 0
    
    def index(self, doc_id: str, content: str):
        tokens = simple_chinese_tokenize(content)
        unique = set(tokens)
        self.doc_tokens[doc_id] = tokens
        self.n_docs += 1
        for t in unique:
            self.doc_freq[t] = self.doc_freq.get(t, 0) + 1
    
    def build_idf(self):
        import math
        for t, df in self.doc_freq.items():
            self.idf[t] = math.log((self.n_docs + 1) / (df + 1)) + 1
    
    def search(self, query: str, top_k: int = 3) -> List[tuple]:
        import math
        tokens = simple_chinese_tokenize(query)
        scores = {}
        for doc_id, doc_toks in self.doc_tokens.items():
            doc_len = len(doc_toks)
            if doc_len == 0:
                continue
            tok_counts = {}
            for t in doc_toks:
                tok_counts[t] = tok_counts.get(t, 0) + 1
            score = 0.0
            for t in tokens:
                if t in tok_counts and t in self.idf:
                    tf = 1 + math.log(tok_counts[t]) if tok_counts[t] > 0 else 0
                    score += tf * self.idf[t]
            if score > 0:
                scores[doc_id] = score
        sorted_docs = sorted(scores.items(), key=lambda x: -x[1])
        return sorted_docs[:top_k]


def create_nemotron_provider(api_key: str):
    """创建 Nemotron NIM embedding provider"""
    from nexusflow.memory.nemotron_provider import NemotronEmbeddingProvider
    return NemotronEmbeddingProvider(
        model_name="nvidia/nemotron-3-embed-1b",
        mode="nim",
        api_key=api_key,
        dimension=2048,
    )


class SimpleNemotronStore:
    """简易 Nemotron 向量存储（不依赖 NexusFlow 内部类，避免导入问题）"""
    def __init__(self, provider):
        self.provider = provider
        self.vectors = {}  # doc_id -> embedding
        self.contents = {}  # doc_id -> content
    
    def add_batch(self, docs: List[Dict], batch_size: int = 10):
        """批量添加文档"""
        for i in range(0, len(docs), batch_size):
            batch = docs[i:i+batch_size]
            texts = [d["content"] for d in batch]
            try:
                embeddings = self.provider.encode_documents(texts)
                for doc, emb in zip(batch, embeddings):
                    self.vectors[doc["id"]] = emb
                    self.contents[doc["id"]] = doc["content"]
                print(f"    Embedded {min(i+batch_size, len(docs))}/{len(docs)} docs")
            except Exception as e:
                print(f"    [WARN] Batch embedding failed at {i}: {e}")
                # 逐条重试
                for doc in batch:
                    try:
                        emb = self.provider.encode_documents([doc["content"]])
                        if isinstance(emb, list) and len(emb) > 0:
                            emb = emb[0]
                        self.vectors[doc["id"]] = emb
                        self.contents[doc["id"]] = doc["content"]
                    except Exception as e2:
                        print(f"    [ERROR] Failed to embed {doc['id'][:50]}: {e2}")
                    time.sleep(1.5)  # 限流保护
            time.sleep(1.5)  # 批间等待
    
    def search(self, query: str, top_k: int = 3) -> List[tuple]:
        """语义检索"""
        try:
            q_vec = self.provider.encode_query(query)
        except Exception as e:
            print(f"    [ERROR] Query embedding failed: {e}")
            return []
        
        scores = {}
        for doc_id, doc_vec in self.vectors.items():
            sim = cosine_similarity(q_vec, doc_vec)
            scores[doc_id] = sim
        
        sorted_docs = sorted(scores.items(), key=lambda x: -x[1])
        return sorted_docs[:top_k]


def cosine_similarity(a, b) -> float:
    """计算余弦相似度"""
    import math
    if len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(x * x for x in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


def rrf_fusion(results_list: List[List[tuple]], k: int = 60) -> List[tuple]:
    """RRF 融合多路检索结果"""
    scores = {}
    for results in results_list:
        for rank, (doc_id, score) in enumerate(results):
            rrf_score = 1.0 / (k + rank + 1)
            scores[doc_id] = scores.get(doc_id, 0.0) + rrf_score
    sorted_docs = sorted(scores.items(), key=lambda x: -x[1])
    return sorted_docs


def run_e4_v2(nim_api_key: str, num_queries: int = 50):
    print("=" * 70)
    print("E4 v2: 全仓库语料库 + 检索对比")
    print("=" * 70)
    
    # ===== 1. 构建语料库 =====
    print("\n[1/4] 扫描仓库文件，构建语料库...")
    docs = scan_repo_files(REPO_ROOT)
    print(f"  语料库大小: {len(docs)} 个文档（来自 {REPO_ROOT}）")
    
    # 统计
    source_files = set(d["source_file"] for d in docs)
    print(f"  源文件数: {len(source_files)}")
    total_chars = sum(len(d["content"]) for d in docs)
    print(f"  总字符数: {total_chars:,}")
    
    # ===== 2. QA 数据集 =====
    qa_data = build_qa_dataset()
    if num_queries < len(qa_data):
        import random
        random.seed(42)
        qa_data = qa_data[:num_queries]
    print(f"\n[2/4] QA 数据集: {len(qa_data)} 个问题")
    
    # ===== 3. 构建索引 =====
    print("\n[3/4] 构建检索索引...")
    
    # 3a. TF-IDF
    print("  构建 TF-IDF 索引...")
    tfidf = SimpleTFIDF()
    for doc in docs:
        tfidf.index(doc["id"], doc["content"])
    tfidf.build_idf()
    print(f"  TF-IDF: {tfidf.n_docs} 文档已索引")
    
    # 3b. Nemotron
    print("  构建 Nemotron 语义索引（NIM API）...")
    provider = create_nemotron_provider(nim_api_key)
    store = SimpleNemotronStore(provider)
    store.add_batch(docs, batch_size=10)
    print(f"  Nemotron: {len(store.vectors)} 文档已嵌入")
    
    # 文档内容映射
    doc_map = {d["id"]: d for d in docs}
    
    # ===== 4. 检索对比 =====
    print(f"\n[4/4] 执行检索对比 ({len(qa_data)} queries)...")
    
    per_query_results = []
    tfidf_correct = 0
    rrf_correct = 0
    
    for i, qa in enumerate(qa_data):
        query = qa["query"]
        relevant_id = qa["relevant_doc_id"]
        keywords = qa.get("keywords", [])
        
        print(f"  [{i+1}/{len(qa_data)}] {query[:50]}...")
        
        # TF-IDF only
        tfidf_results = tfidf.search(query, top_k=5)
        tfidf_top3 = [doc_id for doc_id, _ in tfidf_results[:3]]
        tfidf_top3_docs = []
        for doc_id in tfidf_top3:
            doc = doc_map.get(doc_id, {"id": doc_id, "content": ""})
            tfidf_top3_docs.append({
                "id": doc_id,
                "source_file": doc.get("source_file", doc_id),
                "content": doc["content"][:800],
            })
        
        # Check if relevant doc found (match source_file prefix)
        tfidf_hit = any(
            r.split('#')[0] == relevant_id or r.startswith(relevant_id)
            for r in tfidf_top3
        )
        if tfidf_hit:
            tfidf_correct += 1
        
        # Nemotron semantic
        try:
            nemotron_results = store.search(query, top_k=5)
        except Exception as e:
            print(f"    [WARN] Nemotron search failed: {e}")
            nemotron_results = []
        time.sleep(1.5)  # NIM 限流保护
        
        nemotron_top3 = [doc_id for doc_id, _ in nemotron_results[:3]]
        nemotron_top3_docs = []
        for doc_id in nemotron_top3:
            doc = doc_map.get(doc_id, {"id": doc_id, "content": ""})
            nemotron_top3_docs.append({
                "id": doc_id,
                "source_file": doc.get("source_file", doc_id),
                "content": doc["content"][:800],
            })
        
        nemotron_hit = any(
            r.split('#')[0] == relevant_id or r.startswith(relevant_id)
            for r in nemotron_top3
        )
        if nemotron_hit:
            rrf_correct += 1
        
        # RRF 融合 (TF-IDF + Nemotron)
        fused = rrf_fusion([tfidf_results, nemotron_results])
        rrf_top3 = [doc_id for doc_id, _ in fused[:3]]
        rrf_top3_docs = []
        for doc_id in rrf_top3:
            doc = doc_map.get(doc_id, {"id": doc_id, "content": ""})
            rrf_top3_docs.append({
                "id": doc_id,
                "source_file": doc.get("source_file", doc_id),
                "content": doc["content"][:800],
            })
        
        rrf_hit = any(
            r.split('#')[0] == relevant_id or r.startswith(relevant_id)
            for r in rrf_top3
        )
        
        per_query_results.append({
            "query": query,
            "relevant_doc_id": relevant_id,
            "keywords": keywords,
            "tfidf_top3": tfidf_top3,
            "tfidf_top3_docs": tfidf_top3_docs,
            "nemotron_top3": nemotron_top3,
            "nemotron_top3_docs": nemotron_top3_docs,
            "rrf_top3": rrf_top3,
            "rrf_top3_docs": rrf_top3_docs,
            "tfidf_hit": tfidf_hit,
            "nemotron_hit": nemotron_hit,
            "rrf_hit": rrf_hit,
        })
        
        tfidf_mark = "✓" if tfidf_hit else "✗"
        rrf_mark = "✓" if rrf_hit else "✗"
        print(f"    TF-IDF:{tfidf_mark} RRF:{rrf_mark}")
    
    # ===== 汇总 =====
    n = len(qa_data)
    results = {
        "version": "e4_v2",
        "corpus_stats": {
            "total_docs": len(docs),
            "source_files": len(source_files),
            "total_chars": total_chars,
        },
        "num_queries": n,
        "retrieval_hits": {
            "tfidf_top3_hit": tfidf_correct,
            "rrf_top3_hit": rrf_correct,
            "tfidf_hit_rate": round(tfidf_correct / n, 4),
            "rrf_hit_rate": round(rrf_correct / n, 4),
        },
        "per_query": per_query_results,
    }
    
    output_path = os.path.join(RESULTS_DIR, "e4_v2_retrieval_results.json")
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    
    print("\n" + "=" * 70)
    print("E4 v2 检索对比汇总")
    print("=" * 70)
    print(f"  语料库: {len(docs)} 文档, {len(source_files)} 源文件, {total_chars:,} 字符")
    print(f"  QA数量: {n}")
    print(f"  TF-IDF Top3 命中率: {tfidf_correct}/{n} ({tfidf_correct/n:.1%})")
    print(f"  RRF Top3 命中率:   {rrf_correct}/{n} ({rrf_correct/n:.1%})")
    print(f"\n  结果已保存: {output_path}")
    print(f"  下一步: 用 AI 评估器对检索结果进行回答生成和质量评分")
    
    return results


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--nim_api_key", required=True)
    parser.add_argument("--num_queries", type=int, default=50)
    args = parser.parse_args()
    
    run_e4_v2(nim_api_key=args.nim_api_key, num_queries=args.num_queries)
