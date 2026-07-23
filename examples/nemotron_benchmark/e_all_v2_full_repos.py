# -*- coding: utf-8 -*-
"""
E_all v2: 全量 GitHub 仓库语料库 Benchmark (E1 + E3 + E4检索部分)

扫描用户所有 GitHub 仓库 (~555 文件, ~17MB)，构建统一语料库。
执行 E1(检索质量), E3(Skill检索), E4检索(为AI评估器准备数据)。

用法:
  python e_all_v2_full_repos.py --nim_api_key <NIM_KEY>
"""

import argparse
import json
import os
import sys
import time
import math
import re
import random
from typing import List, Dict, Tuple

random.seed(42)

# === 路径配置 ===
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WORKSPACE = os.path.dirname(REPO_ROOT)  # parent of repo root
REPO_DIRS = {
    "NexusFlow": REPO_ROOT,
}
# 动态加载 all-repos 下所有仓库
ALL_REPOS_DIR = os.path.join(WORKSPACE, "all-repos")
if os.path.isdir(ALL_REPOS_DIR):
    for d in os.listdir(ALL_REPOS_DIR):
        full = os.path.join(ALL_REPOS_DIR, d)
        if os.path.isdir(full) and not d.startswith('.'):
            REPO_DIRS[d] = full

BENCH_DIR = os.path.join(REPO_DIRS["NexusFlow"], "examples", "nemotron_benchmark")
RESULTS_DIR = os.path.join(BENCH_DIR, "results")
os.makedirs(RESULTS_DIR, exist_ok=True)

# 添加 NexusFlow 到 sys.path
NX_ROOT = REPO_DIRS["NexusFlow"]
if NX_ROOT not in sys.path:
    sys.path.insert(0, NX_ROOT)

# 排除规则
EXCLUDE_DIRS = {
    '__pycache__', '.git', '.pytest_cache', 'results', 'node_modules',
    '.venv', 'venv', '.github', 'codeact', 'imgs',
}
EXCLUDE_PREFIXES_PER_REPO = {
    "NexusFlow": ["docs/iteration/versions/", "docs/iteration/reports/"],
}
SUPPORTED_EXT = {'.md', '.py', '.yaml', '.yml', '.txt', '.json', '.html', '.css', '.js'}


# ===================== 语料库扫描 =====================

def scan_all_repos() -> List[Dict]:
    """扫描所有仓库，构建统一语料库"""
    all_docs = []
    repo_stats = {}
    
    for repo_name, repo_dir in REPO_DIRS.items():
        if not os.path.isdir(repo_dir):
            print(f"  [SKIP] {repo_name}: 目录不存在")
            continue
        
        exclude_prefixes = EXCLUDE_PREFIXES_PER_REPO.get(repo_name, [])
        docs = []
        total_chars = 0
        
        for root, dirs, files in os.walk(repo_dir):
            dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS]
            rel_root = os.path.relpath(root, repo_dir)
            if rel_root == '.':
                rel_root = ''
            
            skip = False
            for prefix in exclude_prefixes:
                if rel_root.startswith(prefix) or (rel_root + '/').startswith(prefix):
                    skip = True
                    break
            if skip:
                continue
            
            for fname in files:
                ext = os.path.splitext(fname)[1].lower()
                if ext not in SUPPORTED_EXT:
                    continue
                if len(fname) < 3:
                    continue
                
                fpath = os.path.join(root, fname)
                rel_path = os.path.relpath(fpath, repo_dir)
                
                try:
                    with open(fpath, 'r', encoding='utf-8', errors='ignore') as f:
                        content = f.read()
                except Exception:
                    continue
                
                if len(content.strip()) < 80:
                    continue
                
                # 全局 doc_id 格式: repo_name/relative_path
                global_prefix = f"{repo_name}/{rel_path}"
                
                if len(content) > 4000:
                    chunks = split_document(content, max_chunk=3000)
                    for i, chunk in enumerate(chunks):
                        doc_id = f"{global_prefix}#chunk{i}"
                        docs.append({
                            "id": doc_id,
                            "content": chunk,
                            "source_file": global_prefix,
                            "source_repo": repo_name,
                            "chunk_index": i,
                        })
                        total_chars += len(chunk)
                else:
                    doc_id = global_prefix
                    docs.append({
                        "id": doc_id,
                        "content": content,
                        "source_file": global_prefix,
                        "source_repo": repo_name,
                        "chunk_index": 0,
                    })
                    total_chars += len(content)
        
        all_docs.extend(docs)
        repo_stats[repo_name] = {"docs": len(docs), "chars": total_chars}
        print(f"  {repo_name}: {len(docs)} 文档, {total_chars:,} 字符")
    
    return all_docs, repo_stats


def split_document(text: str, max_chunk: int = 3000) -> List[str]:
    chunks = []
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
    
    current_chunk = ""
    for section in sections:
        if len(current_chunk) + len(section) > max_chunk and current_chunk:
            chunks.append(current_chunk.strip())
            current_chunk = section
        else:
            current_chunk += "\n" + section if current_chunk else section
    if current_chunk.strip():
        chunks.append(current_chunk.strip())
    
    if len(chunks) <= 1 and len(text) > max_chunk:
        chunks = [text[i:i+max_chunk] for i in range(0, len(text), max_chunk)]
    
    return chunks if chunks else [text]


# ===================== 分词 & TF-IDF =====================

def simple_tokenize(text: str) -> List[str]:
    tokens = re.findall(r'[a-zA-Z_][a-zA-Z0-9_]*', text.lower())
    cn_chars = re.findall(r'[\u4e00-\u9fff]', text)
    tokens.extend(cn_chars)
    cn_text = ''.join(cn_chars)
    for i in range(len(cn_text) - 1):
        tokens.append(cn_text[i:i+2])
    return tokens


class SimpleTFIDF:
    def __init__(self):
        self.doc_freq = {}
        self.doc_tokens = {}
        self.idf = {}
        self.n_docs = 0
    
    def index(self, doc_id: str, content: str):
        tokens = simple_tokenize(content)
        unique = set(tokens)
        self.doc_tokens[doc_id] = tokens
        self.n_docs += 1
        for t in unique:
            self.doc_freq[t] = self.doc_freq.get(t, 0) + 1
    
    def build_idf(self):
        for t, df in self.doc_freq.items():
            self.idf[t] = math.log((self.n_docs + 1) / (df + 1)) + 1
    
    def search(self, query: str, top_k: int = 5) -> List[tuple]:
        tokens = simple_tokenize(query)
        scores = {}
        for doc_id, doc_toks in self.doc_tokens.items():
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
        return sorted(scores.items(), key=lambda x: -x[1])[:top_k]


# ===================== BM25 =====================

class SimpleBM25:
    def __init__(self, k1=1.5, b=0.75):
        self.k1 = k1
        self.b = b
        self.doc_freq = {}
        self.doc_tokens = {}
        self.doc_lens = {}
        self.avgdl = 0
        self.n_docs = 0
        self.idf = {}
    
    def index(self, doc_id: str, content: str):
        tokens = simple_tokenize(content)
        self.doc_tokens[doc_id] = tokens
        self.doc_lens[doc_id] = len(tokens)
        self.n_docs += 1
        unique = set(tokens)
        for t in unique:
            self.doc_freq[t] = self.doc_freq.get(t, 0) + 1
    
    def build_idf(self):
        total_len = sum(self.doc_lens.values())
        self.avgdl = total_len / self.n_docs if self.n_docs > 0 else 1
        for t, df in self.doc_freq.items():
            self.idf[t] = math.log((self.n_docs - df + 0.5) / (df + 0.5) + 1)
    
    def search(self, query: str, top_k: int = 5) -> List[tuple]:
        tokens = simple_tokenize(query)
        scores = {}
        for doc_id, doc_toks in self.doc_tokens.items():
            dl = self.doc_lens[doc_id]
            tok_counts = {}
            for t in doc_toks:
                tok_counts[t] = tok_counts.get(t, 0) + 1
            score = 0.0
            for t in tokens:
                if t in tok_counts and t in self.idf:
                    f = tok_counts[t]
                    numerator = f * (self.k1 + 1)
                    denominator = f + self.k1 * (1 - self.b + self.b * dl / self.avgdl)
                    score += self.idf[t] * numerator / denominator
            if score > 0:
                scores[doc_id] = score
        return sorted(scores.items(), key=lambda x: -x[1])[:top_k]


# ===================== Nemotron =====================

def create_nemotron_provider(api_key: str):
    from nexusflow.memory.nemotron_provider import NemotronEmbeddingProvider
    return NemotronEmbeddingProvider(
        model_name="nvidia/nemotron-3-embed-1b",
        mode="nim",
        api_key=api_key,
        dimension=2048,
    )


class SimpleNemotronStore:
    def __init__(self, provider):
        self.provider = provider
        self.vectors = {}
        self.doc_ids = []
    
    def add_batch(self, docs: List[Dict], batch_size: int = 10):
        for i in range(0, len(docs), batch_size):
            batch = docs[i:i+batch_size]
            texts = [d["content"] for d in batch]
            try:
                embeddings = self.provider.embed_batch(texts)
                for doc, emb in zip(batch, embeddings):
                    self.vectors[doc["id"]] = emb
                    self.doc_ids.append(doc["id"])
                print(f"    Embedded {min(i+batch_size, len(docs))}/{len(docs)}")
            except Exception as e:
                print(f"    [WARN] Batch failed at {i}: {e}, retrying one-by-one")
                for doc in batch:
                    try:
                        emb = self.provider.embed_document(doc["content"])
                        self.vectors[doc["id"]] = emb
                        self.doc_ids.append(doc["id"])
                    except Exception as e2:
                        print(f"    [ERROR] {doc['id'][:50]}: {e2}")
                    time.sleep(2)
            time.sleep(2)
    
    def search(self, query: str, top_k: int = 5) -> List[tuple]:
        try:
            q_vec = self.provider.embed_query(query)
        except Exception as e:
            print(f"    [ERROR] Query embed: {e}")
            return []
        
        scores = {}
        for doc_id, doc_vec in self.vectors.items():
            sim = cosine_sim(q_vec, doc_vec)
            scores[doc_id] = sim
        return sorted(scores.items(), key=lambda x: -x[1])[:top_k]


def cosine_sim(a, b) -> float:
    if len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(x * x for x in b))
    return dot / (na * nb) if na > 0 and nb > 0 else 0.0


# ===================== RRF 融合 =====================

def rrf_fusion(results_list: List[List[tuple]], k: int = 60) -> List[tuple]:
    scores = {}
    for results in results_list:
        for rank, (doc_id, score) in enumerate(results):
            rrf_score = 1.0 / (k + rank + 1)
            scores[doc_id] = scores.get(doc_id, 0.0) + rrf_score
    return sorted(scores.items(), key=lambda x: -x[1])


# ===================== 指标计算 =====================

def match_doc(retrieved_id: str, relevant_id: str) -> bool:
    """匹配文档（支持 chunk 后缀）"""
    rid_base = retrieved_id.split('#')[0]
    return rid_base == relevant_id or rid_base.startswith(relevant_id) or relevant_id.startswith(rid_base)


def compute_metrics(retrieved_ids: List[str], relevant_id: str) -> Dict:
    recall_5 = 1.0 if any(match_doc(r, relevant_id) for r in retrieved_ids[:5]) else 0.0
    
    mrr = 0.0
    for i, r in enumerate(retrieved_ids):
        if match_doc(r, relevant_id):
            mrr = 1.0 / (i + 1)
            break
    
    dcg = 0.0
    for i, r in enumerate(retrieved_ids[:10]):
        if match_doc(r, relevant_id):
            dcg += 1.0 / math.log2(i + 2)
    ndcg_10 = dcg  # idcg = 1.0 for binary relevance at top
    
    return {"recall@5": recall_5, "mrr": mrr, "ndcg@10": ndcg_10}


# ===================== E1: QA 数据集 =====================

def build_e1_qa_dataset() -> List[Dict]:
    """覆盖全部仓库的 QA 数据集"""
    return [
        # --- NexusFlow 核心架构 ---
        {"query": "NexusOrchestrator如何协调多个Agent协同工作", "relevant_doc_id": "NexusFlow/nexusflow/core/nexus_orchestrator.py"},
        {"query": "CognitiveDivisionEngine认知分工引擎的设计原理", "relevant_doc_id": "NexusFlow/nexusflow/core/cognitive_division_engine.py"},
        {"query": "DynamicRouter动态路由如何选择合适的Agent", "relevant_doc_id": "NexusFlow/nexusflow/core/dynamic_router.py"},
        {"query": "AdaptiveContextManager如何管理token上下文", "relevant_doc_id": "NexusFlow/nexusflow/core/adaptive_context_manager.py"},
        {"query": "EdgeCloudScheduler边缘云调度器如何决策", "relevant_doc_id": "NexusFlow/nexusflow/core/edge_cloud_scheduler.py"},
        {"query": "GoalVerifier如何验证任务目标达成", "relevant_doc_id": "NexusFlow/nexusflow/core/goal_verifier.py"},
        {"query": "SkillRetriever技能检索器如何匹配用户技能", "relevant_doc_id": "NexusFlow/nexusflow/core/skill_retriever.py"},
        # --- Agent系统 ---
        {"query": "Miner Agent的数据挖掘职责", "relevant_doc_id": "NexusFlow/nexusflow/agents/miner.py"},
        {"query": "Artisan Agent在NexusFlow中的角色", "relevant_doc_id": "NexusFlow/nexusflow/agents/artisan.py"},
        {"query": "Assayer Agent质量检测机制", "relevant_doc_id": "NexusFlow/nexusflow/agents/assayer.py"},
        {"query": "Guardrails安全护栏如何防止危险操作", "relevant_doc_id": "NexusFlow/nexusflow/agents/guardrails.py"},
        {"query": "CircuitBreaker熔断器的作用", "relevant_doc_id": "NexusFlow/nexusflow/agents/circuit_breaker.py"},
        {"query": "Coordinator协调器如何处理Agent冲突", "relevant_doc_id": "NexusFlow/nexusflow/agents/coordinator.py"},
        # --- 记忆系统 ---
        {"query": "VectorMemory向量记忆如何实现BM25和语义混合检索", "relevant_doc_id": "NexusFlow/nexusflow/memory/vector_memory.py"},
        {"query": "NemotronVectorStore如何利用Nemotron构建向量存储", "relevant_doc_id": "NexusFlow/nexusflow/memory/nemotron_store.py"},
        {"query": "ArchivalMemory档案记忆的三路RRF融合检索", "relevant_doc_id": "NexusFlow/nexusflow/memory/archival_memory.py"},
        {"query": "MemoryManager如何管理短期和长期记忆转换", "relevant_doc_id": "NexusFlow/nexusflow/memory/memory_manager.py"},
        {"query": "MultiHopRAG多跳检索如何实现跨文档推理", "relevant_doc_id": "NexusFlow/nexusflow/memory/multi_hop_rag.py"},
        {"query": "Sleeptime机制如何在空闲时整理记忆", "relevant_doc_id": "NexusFlow/nexusflow/memory/sleeptime.py"},
        {"query": "NemotronEmbeddingProvider支持哪些运行模式", "relevant_doc_id": "NexusFlow/nexusflow/memory/nemotron_provider.py"},
        # --- 认知系统 ---
        {"query": "MetaCognition元认知如何监控Agent状态", "relevant_doc_id": "NexusFlow/nexusflow/cognition/meta_cognition.py"},
        {"query": "TreeOfThought思维树如何实现多路径探索", "relevant_doc_id": "NexusFlow/nexusflow/cognition/tot.py"},
        {"query": "CrossDomainReflector跨域反思如何促进知识迁移", "relevant_doc_id": "NexusFlow/nexusflow/cognition/cross_domain.py"},
        {"query": "TaskTree任务树如何分解复杂任务", "relevant_doc_id": "NexusFlow/nexusflow/cognition/task_tree.py"},
        # --- 协议层 ---
        {"query": "A2A Protocol如何实现Agent间通信", "relevant_doc_id": "NexusFlow/nexusflow/protocol/a2a_protocol.py"},
        {"query": "MCP Client如何连接外部工具服务", "relevant_doc_id": "NexusFlow/nexusflow/protocol/mcp_client.py"},
        {"query": "A2A Gateway如何管理跨系统通信", "relevant_doc_id": "NexusFlow/nexusflow/protocol/a2a_gateway.py"},
        # --- 技术文档 ---
        {"query": "NexusFlow v2.9核心架构升级内容", "relevant_doc_id": "NexusFlow/docs/NexusFlow技术文档v2.9.md"},
        {"query": "Nemotron-3 Embed集成实施方案", "relevant_doc_id": "NexusFlow/docs/Nemotron3_集成实施方案_v2.md"},
        {"query": "Phase2消融实验设计和结果", "relevant_doc_id": "NexusFlow/docs/Phase2_ablation实验报告.md"},
        {"query": "向量记忆衰减机制设计", "relevant_doc_id": "NexusFlow/docs/vector_memory.md"},
        # --- agent4science ---
        {"query": "agent4science项目包含哪些科研工具", "relevant_doc_id": "agent4science/README.md"},
        {"query": "agent4science的论文知识库如何检索", "relevant_doc_id": "agent4science/README.md"},
        # --- materials-ai-kit ---
        {"query": "materials-ai-kit材料科学AI工具包的功能", "relevant_doc_id": "materials-ai-kit/README.md"},
        # --- xuanshu-knowledge-base ---
        {"query": "铉枢知识库包含哪些AGI认知架构调研", "relevant_doc_id": "xuanshu-knowledge-base/README.md"},
        {"query": "知识库中524篇论文的分类体系", "relevant_doc_id": "xuanshu-knowledge-base/README.md"},
        # --- materials-kb ---
        {"query": "materials-kb材料×ML中文知识库索引了多少篇论文", "relevant_doc_id": "materials-kb/README.md"},
        # --- xuanshu-ui-gallery ---
        {"query": "铉枢UI风格库包含哪些控制面板主题", "relevant_doc_id": "xuanshu-ui-gallery/README.md"},
        # --- NexusFlow 工具 ---
        {"query": "ToolRegistry工具注册中心如何管理工具", "relevant_doc_id": "NexusFlow/tools/tool_registry.py"},
        {"query": "LiteratureSearch学术文献检索工具", "relevant_doc_id": "NexusFlow/tools/literature_search.py"},
        {"query": "ModelRouter模型路由器如何选择最佳模型", "relevant_doc_id": "NexusFlow/tools/model_router.py"},
        # --- NexusFlow 服务端 ---
        {"query": "NexusFlow Server如何提供API服务", "relevant_doc_id": "NexusFlow/server/nexusflow_server.py"},
        # --- NexusFlow 配置 ---
        {"query": "NexusFlow config.yaml包含哪些核心配置项", "relevant_doc_id": "NexusFlow/config/config.yaml"},
        # --- mat-scripts ---
        {"query": "mat-scripts材料科学ML工具包的数据处理流程", "relevant_doc_id": "mat-scripts/README.md"},
        # --- qiu ---
        {"query": "qiu控制面板的液态玻璃风格设计", "relevant_doc_id": "qiu/README.md"},
    ]


# ===================== E3: Skill 数据集 =====================

def build_e3_skill_tasks() -> List[Dict]:
    """覆盖全部仓库功能的 Skill 任务"""
    return [
        {"task": "让多个Agent协同处理一个跨学科科研任务", "target": "NexusFlow/nexusflow/core/nexus_orchestrator.py", "keywords": ["orchestrator", "agent", "协同"]},
        {"task": "管理超长对话的token上下文不超限", "target": "NexusFlow/nexusflow/core/adaptive_context_manager.py", "keywords": ["context", "token", "管理"]},
        {"task": "在边缘设备和云端之间智能调度计算任务", "target": "NexusFlow/nexusflow/core/edge_cloud_scheduler.py", "keywords": ["edge", "cloud", "schedule"]},
        {"task": "用向量记忆检索过去的对话内容", "target": "NexusFlow/nexusflow/memory/vector_memory.py", "keywords": ["vector", "memory", "检索"]},
        {"task": "Agent空闲时自动整理和巩固记忆", "target": "NexusFlow/nexusflow/memory/sleeptime.py", "keywords": ["sleeptime", "memory", "整理"]},
        {"task": "跨文档多跳推理找出隐含关联", "target": "NexusFlow/nexusflow/memory/multi_hop_rag.py", "keywords": ["multi", "hop", "推理"]},
        {"task": "监控Agent的认知负荷并动态调整", "target": "NexusFlow/nexusflow/cognition/meta_cognition.py", "keywords": ["meta", "cognition", "监控"]},
        {"task": "用思维树方法探索多种解题路径", "target": "NexusFlow/nexusflow/cognition/tot.py", "keywords": ["tree", "thought", "探索"]},
        {"task": "跨领域知识迁移找到创新方案", "target": "NexusFlow/nexusflow/cognition/cross_domain.py", "keywords": ["cross", "domain", "迁移"]},
        {"task": "通过A2A协议实现不同系统的Agent通信", "target": "NexusFlow/nexusflow/protocol/a2a_protocol.py", "keywords": ["a2a", "protocol", "通信"]},
        {"task": "连接MCP外部工具服务扩展Agent能力", "target": "NexusFlow/nexusflow/protocol/mcp_client.py", "keywords": ["mcp", "tool", "连接"]},
        {"task": "检索524篇材料科学论文进行文献综述", "target": "agent4science/README.md", "keywords": ["论文", "文献", "检索"]},
        {"task": "用AI工具分析材料的微观结构", "target": "materials-ai-kit/README.md", "keywords": ["materials", "AI", "分析"]},
        {"task": "查询AGI认知架构的最新研究进展", "target": "xuanshu-knowledge-base/README.md", "keywords": ["AGI", "认知", "架构"]},
        {"task": "防止Agent执行未经授权的危险操作", "target": "NexusFlow/nexusflow/agents/guardrails.py", "keywords": ["guardrail", "safety", "安全"]},
        {"task": "当Agent连续失败时触发熔断保护", "target": "NexusFlow/nexusflow/agents/circuit_breaker.py", "keywords": ["circuit", "breaker", "熔断"]},
        {"task": "将复杂任务自动分解为子任务树", "target": "NexusFlow/nexusflow/cognition/task_tree.py", "keywords": ["task", "tree", "分解"]},
        {"task": "为任务选择最适合的AI模型", "target": "NexusFlow/tools/model_router.py", "keywords": ["model", "router", "选择"]},
        {"task": "检索学术论文辅助科研决策", "target": "NexusFlow/tools/literature_search.py", "keywords": ["literature", "search", "学术"]},
        {"task": "在材料×ML知识库中查找特定材料的性能数据", "target": "materials-kb/README.md", "keywords": ["materials", "ML", "知识库"]},
        {"task": "用机器学习处理材料科学实验数据", "target": "mat-scripts/README.md", "keywords": ["ML", "materials", "数据"]},
        {"task": "查看液态玻璃风格的管理控制面板", "target": "qiu/README.md", "keywords": ["控制面板", "液态玻璃", "UI"]},
        {"task": "浏览各种CSS主题风格用于UI设计参考", "target": "xuanshu-ui-gallery/README.md", "keywords": ["CSS", "主题", "UI"]},
        {"task": "注册和管理Agent的技能能力列表", "target": "NexusFlow/nexusflow/core/skill_retriever.py", "keywords": ["skill", "register", "技能"]},
        {"task": "验证Agent是否正确完成了目标", "target": "NexusFlow/nexusflow/core/goal_verifier.py", "keywords": ["goal", "verify", "验证"]},
    ]


# ===================== 主流程 =====================

def run_all(nim_api_key: str):
    print("=" * 70)
    print("E_all v2: 全量 GitHub 仓库 Benchmark")
    print("=" * 70)
    
    # ===== 1. 构建语料库 =====
    print("\n[1/5] 扫描所有 GitHub 仓库...")
    all_docs, repo_stats = scan_all_repos()
    total_chars = sum(len(d["content"]) for d in all_docs)
    print(f"\n  总计: {len(all_docs)} 文档, {total_chars:,} 字符")
    
    doc_map = {d["id"]: d for d in all_docs}
    
    # ===== 2. 构建索引 =====
    print("\n[2/5] 构建检索索引...")
    
    # TF-IDF
    print("  TF-IDF...")
    tfidf = SimpleTFIDF()
    for doc in all_docs:
        tfidf.index(doc["id"], doc["content"])
    tfidf.build_idf()
    print(f"  TF-IDF: {tfidf.n_docs} 文档已索引")
    
    # BM25
    print("  BM25...")
    bm25 = SimpleBM25()
    for doc in all_docs:
        bm25.index(doc["id"], doc["content"])
    bm25.build_idf()
    print(f"  BM25: {bm25.n_docs} 文档已索引")
    
    # Nemotron
    print("  Nemotron (NIM API)...")
    provider = create_nemotron_provider(nim_api_key)
    store = SimpleNemotronStore(provider)
    store.add_batch(all_docs, batch_size=10)
    print(f"  Nemotron: {len(store.vectors)} 文档已嵌入")
    
    # ===== 3. E1: QA 检索质量 =====
    print("\n[3/5] E1: QA 检索质量对比...")
    e1_qa = build_e1_qa_dataset()
    
    methods = {
        "TF-IDF only": lambda q: tfidf.search(q, top_k=10),
        "BM25 only": lambda q: bm25.search(q, top_k=10),
        "Nemotron semantic only": lambda q: store.search(q, top_k=10),
    }
    
    e1_results = {
        "corpus_stats": {
            "total_docs": len(all_docs),
            "total_chars": total_chars,
            "repo_stats": repo_stats,
        },
        "num_queries": len(e1_qa),
    }
    
    for method_name, search_fn in methods.items():
        print(f"\n  {method_name}:")
        per_query = []
        metrics_list = []
        for qa in e1_qa:
            results = search_fn(qa["query"])
            retrieved_ids = [doc_id for doc_id, _ in results[:10]]
            m = compute_metrics(retrieved_ids, qa["relevant_doc_id"])
            metrics_list.append(m)
            per_query.append({
                "query": qa["query"],
                "relevant_doc_id": qa["relevant_doc_id"],
                "retrieved_top5": retrieved_ids[:5],
                "metrics": m,
            })
            time.sleep(0.5) if "Nemotron" in method_name else None
        
        agg = {
            "recall@5": round(sum(m["recall@5"] for m in metrics_list) / len(metrics_list), 4),
            "mrr": round(sum(m["mrr"] for m in metrics_list) / len(metrics_list), 4),
            "ndcg@10": round(sum(m["ndcg@10"] for m in metrics_list) / len(metrics_list), 4),
        }
        e1_results[method_name] = {"aggregate": agg, "per_query": per_query}
        print(f"    Recall@5={agg['recall@5']:.4f}, MRR={agg['mrr']:.4f}, NDCG@10={agg['ndcg@10']:.4f}")
    
    # RRF 融合
    print("\n  RRF(TF-IDF + Nemotron):")
    rrf_tn_per_query = []
    rrf_tn_metrics = []
    for qa in e1_qa:
        t_res = tfidf.search(qa["query"], top_k=10)
        time.sleep(1.5)
        n_res = store.search(qa["query"], top_k=10)
        fused = rrf_fusion([t_res, n_res])
        retrieved_ids = [doc_id for doc_id, _ in fused[:10]]
        m = compute_metrics(retrieved_ids, qa["relevant_doc_id"])
        rrf_tn_metrics.append(m)
        rrf_tn_per_query.append({
            "query": qa["query"],
            "relevant_doc_id": qa["relevant_doc_id"],
            "retrieved_top5": retrieved_ids[:5],
            "metrics": m,
        })
    rrf_tn_agg = {
        "recall@5": round(sum(m["recall@5"] for m in rrf_tn_metrics) / len(rrf_tn_metrics), 4),
        "mrr": round(sum(m["mrr"] for m in rrf_tn_metrics) / len(rrf_tn_metrics), 4),
        "ndcg@10": round(sum(m["ndcg@10"] for m in rrf_tn_metrics) / len(rrf_tn_metrics), 4),
    }
    e1_results["RRF(TF-IDF + Nemotron)"] = {"aggregate": rrf_tn_agg, "per_query": rrf_tn_per_query}
    print(f"    Recall@5={rrf_tn_agg['recall@5']:.4f}, MRR={rrf_tn_agg['mrr']:.4f}, NDCG@10={rrf_tn_agg['ndcg@10']:.4f}")
    
    # 保存 E1
    e1_path = os.path.join(RESULTS_DIR, "e1_v2_retrieval_quality.json")
    with open(e1_path, 'w', encoding='utf-8') as f:
        json.dump(e1_results, f, ensure_ascii=False, indent=2)
    print(f"\n  E1 已保存: {e1_path}")
    
    # ===== 4. E3: Skill 检索 =====
    print("\n[4/5] E3: Skill/功能检索质量...")
    skill_tasks = build_e3_skill_tasks()
    
    # 规则匹配：基于关键词
    def rule_match(task: str, target: str, keywords: List[str]) -> bool:
        """简单规则匹配：检查 target 文件路径中是否包含关键词"""
        target_lower = target.lower()
        for kw in keywords:
            if kw.lower() in target_lower:
                return True
        return False
    
    # 为每个模块构建关键词索引
    module_keywords = {}
    for st in skill_tasks:
        target = st["target"]
        if target not in module_keywords:
            module_keywords[target] = set()
        for kw in st["keywords"]:
            module_keywords[target].add(kw.lower())
    
    def rule_search(task: str) -> List[str]:
        """基于关键词的任务匹配"""
        task_lower = task.lower()
        scores = {}
        for target, kws in module_keywords.items():
            score = 0
            for kw in kws:
                if kw in task_lower:
                    score += 1
            if score > 0:
                scores[target] = score
        return sorted(scores.keys(), key=lambda x: -scores[x])
    
    rule_hits = 0
    semantic_hits = 0
    
    e3_per_task = []
    for st in skill_tasks:
        task = st["task"]
        target = st["target"]
        
        # 规则匹配
        rule_results = rule_search(task)[:3]
        rule_hit = target in rule_results
        if rule_hit:
            rule_hits += 1
        
        # 语义检索
        time.sleep(1.5)
        sem_results = store.search(task, top_k=3)
        sem_ids = [doc_id for doc_id, _ in sem_results]
        sem_hit = any(
            doc_id.split('#')[0] == target or doc_id.startswith(target)
            for doc_id in sem_ids
        )
        if sem_hit:
            semantic_hits += 1
        
        e3_per_task.append({
            "task": task,
            "target": target,
            "rule_top3": rule_results,
            "rule_hit": rule_hit,
            "semantic_top3": sem_ids[:3],
            "semantic_hit": sem_hit,
        })
        
        r_mark = "✓" if rule_hit else "✗"
        s_mark = "✓" if sem_hit else "✗"
        print(f"  {task[:40]:40s} rule:{r_mark} sem:{s_mark}")
    
    n_skill = len(skill_tasks)
    e3_results = {
        "rule_only": {"top3_hit_rate": round(rule_hits / n_skill, 4), "hits": rule_hits, "total": n_skill},
        "rule_plus_semantic": {"top3_hit_rate": round(semantic_hits / n_skill, 4), "hits": semantic_hits, "total": n_skill},
        "improvement": {
            "absolute": round((semantic_hits - rule_hits) / n_skill, 4),
            "relative": round((semantic_hits - rule_hits) / max(rule_hits, 1) * 100, 2),
        },
        "per_task": e3_per_task,
    }
    
    e3_path = os.path.join(RESULTS_DIR, "e3_v2_skill_retrieval.json")
    with open(e3_path, 'w', encoding='utf-8') as f:
        json.dump(e3_results, f, ensure_ascii=False, indent=2)
    print(f"\n  E3 已保存: {e3_path}")
    
    # ===== 5. E4 检索部分 =====
    print("\n[5/5] E4: 准备端到端评估数据...")
    e4_qa = build_e1_qa_dataset()  # 复用 E1 QA
    
    e4_per_query = []
    for i, qa in enumerate(e4_qa):
        query = qa["query"]
        relevant_id = qa["relevant_doc_id"]
        
        # TF-IDF top3
        tfidf_res = tfidf.search(query, top_k=3)
        tfidf_docs = []
        for doc_id, _ in tfidf_res:
            doc = doc_map.get(doc_id, {"content": ""})
            tfidf_docs.append({
                "id": doc_id,
                "source_file": doc.get("source_file", doc_id),
                "content": doc["content"][:800],
            })
        
        # RRF top3
        time.sleep(1.5)
        n_res = store.search(query, top_k=10)
        t_res = tfidf.search(query, top_k=10)
        fused = rrf_fusion([t_res, n_res])
        rrf_docs = []
        for doc_id, _ in fused[:3]:
            doc = doc_map.get(doc_id, {"content": ""})
            rrf_docs.append({
                "id": doc_id,
                "source_file": doc.get("source_file", doc_id),
                "content": doc["content"][:800],
            })
        
        e4_per_query.append({
            "query": query,
            "relevant_doc_id": relevant_id,
            "tfidf_top3_docs": tfidf_docs,
            "rrf_top3_docs": rrf_docs,
            "tfidf_hit": any(match_doc(d["id"], relevant_id) for d in tfidf_docs),
            "rrf_hit": any(match_doc(d["id"], relevant_id) for d in rrf_docs),
        })
        
        tf = "✓" if e4_per_query[-1]["tfidf_hit"] else "✗"
        rf = "✓" if e4_per_query[-1]["rrf_hit"] else "✗"
        print(f"  [{i+1}/{len(e4_qa)}] {query[:40]:40s} tfidf:{tf} rrf:{rf}")
    
    e4_retrieval = {
        "version": "e4_v2",
        "corpus_stats": {"total_docs": len(all_docs), "total_chars": total_chars},
        "num_queries": len(e4_qa),
        "per_query": e4_per_query,
    }
    
    e4_path = os.path.join(RESULTS_DIR, "e4_v2_retrieval_results.json")
    with open(e4_path, 'w', encoding='utf-8') as f:
        json.dump(e4_retrieval, f, ensure_ascii=False, indent=2)
    print(f"\n  E4 检索数据已保存: {e4_path}")
    
    # ===== 汇总 =====
    print("\n" + "=" * 70)
    print("E_all v2 汇总")
    print("=" * 70)
    print(f"  语料库: {len(all_docs)} 文档, {total_chars:,} 字符, {len(REPO_DIRS)} 仓库")
    print(f"\n  E1 QA检索 (Recall@5 / MRR):")
    for method in ["TF-IDF only", "BM25 only", "Nemotron semantic only", "RRF(TF-IDF + Nemotron)"]:
        agg = e1_results[method]["aggregate"]
        print(f"    {method:30s} R@5={agg['recall@5']:.4f} MRR={agg['mrr']:.4f}")
    print(f"\n  E3 Skill检索:")
    print(f"    规则 only:          {rule_hits}/{n_skill} ({rule_hits/n_skill:.1%})")
    print(f"    规则+语义:          {semantic_hits}/{n_skill} ({semantic_hits/n_skill:.1%})")
    print(f"\n  E4 端到端数据: {len(e4_per_query)} queries 已准备")
    print(f"  下一步: 用 AI 评估器对 e4_v2_retrieval_results.json 进行回答生成和质量评分")
    
    return e1_results, e3_results, e4_retrieval


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--nim_api_key", required=True)
    args = parser.parse_args()
    run_all(nim_api_key=args.nim_api_key)
