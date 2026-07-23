# -*- coding: utf-8 -*-
"""
E_all v3: 全仓库 Benchmark — 纯本地版（无需 NIM API）

用 TF-IDF + BM25 + 混合检索，不需要 Nemotron embedding。
E1: 检索质量对比 (TF-IDF / BM25 / TF-IDF+BM25 混合)
E3: Skill 检索
E4: 为 AI 评估器准备检索数据

用法: python3 e_all_v3_local.py
"""

import json
import os
import sys
import math
import re
import random
from collections import Counter, defaultdict
from typing import List, Dict, Tuple

random.seed(42)

# === 路径配置 ===
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WORKSPACE = os.path.dirname(REPO_ROOT)  # parent of repo root
REPO_DIRS = {"NexusFlow": REPO_ROOT}
ALL_REPOS_DIR = os.path.join(WORKSPACE, "all-repos")
if os.path.isdir(ALL_REPOS_DIR):
    for d in os.listdir(ALL_REPOS_DIR):
        full = os.path.join(ALL_REPOS_DIR, d)
        if os.path.isdir(full) and not d.startswith('.'):
            REPO_DIRS[d] = full

BENCH_DIR = os.path.join(REPO_DIRS["NexusFlow"], "examples", "nemotron_benchmark")
RESULTS_DIR = os.path.join(BENCH_DIR, "results")
os.makedirs(RESULTS_DIR, exist_ok=True)

EXCLUDE_DIRS = {
    '__pycache__', '.git', '.pytest_cache', 'results', 'node_modules',
    '.venv', 'venv', '.github', 'codeact', 'imgs',
}
EXCLUDE_PREFIXES = {
    "NexusFlow": ["docs/iteration/versions/", "docs/iteration/reports/"],
}
SUPPORTED_EXT = {'.md', '.py', '.yaml', '.yml', '.txt', '.json', '.html', '.css', '.js'}
MAX_CHUNK_CHARS = 3000


# ===================== 语料库扫描 =====================

def scan_all_repos() -> List[Dict]:
    all_docs = []
    repo_stats = {}
    for repo_name, repo_dir in REPO_DIRS.items():
        if not os.path.isdir(repo_dir):
            continue
        exclude = EXCLUDE_PREFIXES.get(repo_name, [])
        docs = []
        for root, dirs, files in os.walk(repo_dir):
            dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS]
            rel_root = os.path.relpath(root, repo_dir)
            if rel_root == '.':
                rel_root = ''
            if any(rel_root.startswith(p) for p in exclude if rel_root):
                continue
            for fname in files:
                ext = os.path.splitext(fname)[1].lower()
                if ext not in SUPPORTED_EXT:
                    continue
                fpath = os.path.join(root, fname)
                rel_path = os.path.join(rel_root, fname) if rel_root else fname
                try:
                    with open(fpath, 'r', encoding='utf-8', errors='ignore') as f:
                        content = f.read()
                except:
                    continue
                if len(content) < 50:
                    continue
                global_prefix = f"{repo_name}/{rel_path}"
                if len(content) <= MAX_CHUNK_CHARS:
                    docs.append({"id": global_prefix, "content": content, "source": global_prefix})
                else:
                    chunks = split_by_heading(content, MAX_CHUNK_CHARS)
                    for i, chunk in enumerate(chunks):
                        docs.append({"id": f"{global_prefix}#chunk{i}", "content": chunk, "source": global_prefix})
        repo_stats[repo_name] = {"files": len(set(d["source"] for d in docs)), "docs": len(docs), "chars": sum(len(d["content"]) for d in docs)}
        all_docs.extend(docs)
    return all_docs, repo_stats


def split_by_heading(content: str, max_chars: int) -> List[str]:
    chunks = []
    sections = re.split(r'\n(?=#{1,4}\s)', content)
    current = ""
    for sec in sections:
        if len(current) + len(sec) > max_chars and current:
            chunks.append(current[:max_chars])
            current = sec
        else:
            current += sec
    if current:
        chunks.append(current[:max_chars])
    return chunks if chunks else [content[:max_chars]]


# ===================== 中文分词 =====================

def tokenize(text: str) -> List[str]:
    text = text.lower()
    tokens = []
    # Chinese: character bigrams
    chinese_chars = re.findall(r'[\u4e00-\u9fff]', text)
    for i in range(len(chinese_chars) - 1):
        tokens.append(chinese_chars[i] + chinese_chars[i+1])
    if chinese_chars:
        tokens.append(chinese_chars[-1])
    # English/code: word tokens
    english_words = re.findall(r'[a-z_][a-z0-9_]{1,40}', text)
    tokens.extend(english_words)
    return tokens


# ===================== TF-IDF =====================

class TFIDFIndex:
    def __init__(self):
        self.doc_tokens = {}
        self.df = Counter()
        self.N = 0

    def add(self, doc_id: str, content: str):
        tokens = tokenize(content)
        self.doc_tokens[doc_id] = tokens
        unique = set(tokens)
        for t in unique:
            self.df[t] += 1
        self.N += 1

    def search(self, query: str, top_k: int = 5) -> List[Tuple[str, float]]:
        q_tokens = tokenize(query)
        if not q_tokens:
            return []
        scores = {}
        for doc_id, doc_toks in self.doc_tokens.items():
            tf = Counter(doc_toks)
            score = 0.0
            for qt in q_tokens:
                if qt in tf and qt in self.df:
                    tf_val = tf[qt] / len(doc_toks)
                    idf = math.log(self.N / (1 + self.df[qt]))
                    score += tf_val * idf
            if score > 0:
                scores[doc_id] = score
        return sorted(scores.items(), key=lambda x: -x[1])[:top_k]

    def batch_index(self, docs: List[Dict]):
        for d in docs:
            self.add(d["id"], d["content"])


# ===================== BM25 =====================

class BM25Index:
    def __init__(self, k1=1.5, b=0.75):
        self.k1 = k1
        self.b = b
        self.doc_tokens = {}
        self.doc_lens = {}
        self.df = Counter()
        self.N = 0
        self.avgdl = 0

    def add(self, doc_id: str, content: str):
        tokens = tokenize(content)
        self.doc_tokens[doc_id] = tokens
        self.doc_lens[doc_id] = len(tokens)
        for t in set(tokens):
            self.df[t] += 1
        self.N += 1

    def build(self):
        self.avgdl = sum(self.doc_lens.values()) / max(1, self.N)

    def search(self, query: str, top_k: int = 5) -> List[Tuple[str, float]]:
        q_tokens = tokenize(query)
        if not q_tokens:
            return []
        scores = {}
        for doc_id, doc_toks in self.doc_tokens.items():
            tf = Counter(doc_toks)
            dl = self.doc_lens[doc_id]
            score = 0.0
            for qt in q_tokens:
                if qt in tf and qt in self.df:
                    f = tf[qt]
                    idf = math.log((self.N - self.df[qt] + 0.5) / (self.df[qt] + 0.5) + 1)
                    numerator = f * (self.k1 + 1)
                    denominator = f + self.k1 * (1 - self.b + self.b * dl / self.avgdl)
                    score += idf * numerator / denominator
            if score > 0:
                scores[doc_id] = score
        return sorted(scores.items(), key=lambda x: -x[1])[:top_k]

    def batch_index(self, docs: List[Dict]):
        for d in docs:
            self.add(d["id"], d["content"])
        self.build()


# ===================== RRF 融合 =====================

def rrf_fusion(results_list: List[List[Tuple[str, float]]], k=60, top_k=5) -> List[Tuple[str, float]]:
    scores = defaultdict(float)
    for results in results_list:
        for rank, (doc_id, _) in enumerate(results):
            scores[doc_id] += 1.0 / (k + rank + 1)
    return sorted(scores.items(), key=lambda x: -x[1])[:top_k]


# ===================== QA 数据集 =====================

def build_e1_qa_dataset() -> List[Dict]:
    return [
        # NexusFlow 核心架构
        {"query": "NexusOrchestrator如何协调多个Agent协同工作", "relevant_doc_id": "NexusFlow/nexusflow/core/nexus_orchestrator.py"},
        {"query": "CognitiveDivisionEngine认知分工引擎的设计原理", "relevant_doc_id": "NexusFlow/nexusflow/core/cognitive_division_engine.py"},
        {"query": "DynamicRouter动态路由如何选择合适的Agent", "relevant_doc_id": "NexusFlow/nexusflow/core/dynamic_router.py"},
        {"query": "AdaptiveContextManager如何管理token上下文", "relevant_doc_id": "NexusFlow/nexusflow/core/adaptive_context_manager.py"},
        {"query": "EdgeCloudScheduler边缘云调度器如何决策", "relevant_doc_id": "NexusFlow/nexusflow/core/edge_cloud_scheduler.py"},
        {"query": "GoalVerifier如何验证任务目标达成", "relevant_doc_id": "NexusFlow/nexusflow/core/goal_verifier.py"},
        {"query": "SkillRetriever技能检索器如何匹配用户技能", "relevant_doc_id": "NexusFlow/nexusflow/core/skill_retriever.py"},
        # Agent 子系统
        {"query": "Miner Agent的数据挖掘职责", "relevant_doc_id": "NexusFlow/nexusflow/agents/miner.py"},
        {"query": "Artisan Agent在NexusFlow中的角色", "relevant_doc_id": "NexusFlow/nexusflow/agents/artisan.py"},
        {"query": "Assayer Agent质量检测机制", "relevant_doc_id": "NexusFlow/nexusflow/agents/assayer.py"},
        {"query": "Sentinel Agent安全监控功能", "relevant_doc_id": "NexusFlow/nexusflow/agents/sentinel.py"},
        # 记忆系统
        {"query": "VectorMemory向量记忆存储与检索机制", "relevant_doc_id": "NexusFlow/nexusflow/memory/vector_memory.py"},
        {"query": "ArchivalMemory归档记忆如何管理长期知识", "relevant_doc_id": "NexusFlow/nexusflow/memory/archival_memory.py"},
        {"query": "NemotronEmbeddingProvider嵌入向量提供者", "relevant_doc_id": "NexusFlow/nexusflow/memory/nemotron_provider.py"},
        # 协议层
        {"query": "NexusProtocol消息协议规范定义", "relevant_doc_id": "NexusFlow/nexusflow/protocol/nexus_protocol.py"},
        # 工具/配置
        {"query": "NexusFlow的配置文件config.yaml包含哪些配置项", "relevant_doc_id_prefix": "NexusFlow/config/config.yaml"},
        {"query": "NexusFlow的pyproject.toml项目依赖管理", "relevant_doc_id_prefix": "NexusFlow/pyproject.toml"},
        # agent4science
        {"query": "agent4science项目的科学发现工作流设计", "relevant_doc_id_prefix": "agent4science/"},
        {"query": "agent4science中Agent如何协作完成科学研究任务", "relevant_doc_id_prefix": "agent4science/"},
        # materials
        {"query": "materials-kb材料知识库包含哪些内容", "relevant_doc_id_prefix": "materials-kb/"},
        {"query": "materials-ai-kit材料AI工具包的功能模块", "relevant_doc_id_prefix": "materials-ai-kit/"},
        # xuanshu
        {"query": "xuanshu-knowledge-base知识库的组织结构", "relevant_doc_id_prefix": "xuanshu-knowledge-base/"},
        {"query": "xuanshu-ui-gallery界面设计画廊的组件", "relevant_doc_id_prefix": "xuanshu-ui-gallery/"},
    ]


def build_e3_skill_tasks() -> List[Dict]:
    return [
        {"task": "了解NexusFlow的Agent调度机制", "keywords": ["orchestrator", "调度", "agent"], "relevant_prefix": "NexusFlow/nexusflow/core/"},
        {"task": "查看NexusFlow的记忆系统设计", "keywords": ["memory", "vector", "archival"], "relevant_prefix": "NexusFlow/nexusflow/memory/"},
        {"task": "了解NexusFlow的认知分工架构", "keywords": ["cognitive", "division", "engine"], "relevant_prefix": "NexusFlow/nexusflow/core/"},
        {"task": "查看NexusFlow的协议定义", "keywords": ["protocol", "message", "nexus"], "relevant_prefix": "NexusFlow/nexusflow/protocol/"},
        {"task": "了解NexusFlow的Agent角色定义", "keywords": ["agent", "miner", "artisan", "assayer"], "relevant_prefix": "NexusFlow/nexusflow/agents/"},
        {"task": "查看NexusFlow的边缘云调度", "keywords": ["edge", "cloud", "scheduler"], "relevant_prefix": "NexusFlow/nexusflow/core/"},
        {"task": "了解NexusFlow的技能检索系统", "keywords": ["skill", "retriever", "match"], "relevant_prefix": "NexusFlow/nexusflow/core/"},
        {"task": "查看agent4science的README文档", "keywords": ["science", "agent", "discovery"], "relevant_prefix": "agent4science/"},
        {"task": "了解材料知识库的内容分类", "keywords": ["材料", "知识库", "knowledge"], "relevant_prefix": "materials-kb/"},
        {"task": "查看UI画廊的设计组件", "keywords": ["ui", "gallery", "component", "设计"], "relevant_prefix": "xuanshu-ui-gallery/"},
        {"task": "了解NexusFlow的Nemotron集成方案", "keywords": ["nemotron", "embedding", "provider"], "relevant_prefix": "NexusFlow/nexusflow/memory/"},
        {"task": "查看NexusFlow的配置文件", "keywords": ["config", "yaml", "配置"], "relevant_prefix": "NexusFlow/config/"},
        {"task": "了解材料AI工具包的功能", "keywords": ["materials", "ai", "kit", "工具"], "relevant_prefix": "materials-ai-kit/"},
        {"task": "查看玄枢知识库的文档组织", "keywords": ["知识", "文档", "xuanshu"], "relevant_prefix": "xuanshu-knowledge-base/"},
        {"task": "了解NexusFlow的动态路由算法", "keywords": ["router", "dynamic", "route"], "relevant_prefix": "NexusFlow/nexusflow/core/"},
    ]


# ===================== 评估函数 =====================

def evaluate_retrieval(results: List[Tuple[str, float]], relevant_id: str, relevant_prefix: str = None, k=5) -> Dict:
    top_k = results[:k]
    top_k_ids = [doc_id for doc_id, _ in top_k]
    hit = False
    if relevant_id:
        hit = any(relevant_id in doc_id or doc_id in relevant_id for doc_id in top_k_ids)
    if not hit and relevant_prefix:
        hit = any(doc_id.startswith(relevant_prefix) for doc_id in top_k_ids)
    rr = 0.0
    for rank, doc_id in enumerate(top_k_ids):
        if relevant_id and (relevant_id in doc_id or doc_id in relevant_id):
            rr = 1.0 / (rank + 1)
            break
        if relevant_prefix and doc_id.startswith(relevant_prefix):
            rr = 1.0 / (rank + 1)
            break
    return {"hit": hit, "rr": rr, "top_k_ids": top_k_ids}


# ===================== 主流程 =====================

def main():
    print("=" * 70)
    print("E_all v3: 全仓库 Benchmark (纯本地版)")
    print("=" * 70)

    # 1. 扫描语料库
    print("\n[1/4] 扫描所有 GitHub 仓库...")
    all_docs, repo_stats = scan_all_repos()
    print(f"  总计: {len(all_docs)} 文档, {sum(len(d['content']) for d in all_docs):,} 字符")
    for rn, rs in repo_stats.items():
        print(f"    {rn}: {rs['files']}文件, {rs['docs']}文档, {rs['chars']:,}字符")

    # 2. 构建索引
    print("\n[2/4] 构建检索索引...")
    print("  TF-IDF...")
    tfidf = TFIDFIndex()
    tfidf.batch_index(all_docs)
    print(f"  TF-IDF: {tfidf.N} 文档已索引")

    print("  BM25...")
    bm25 = BM25Index()
    bm25.batch_index(all_docs)
    print(f"  BM25: {bm25.N} 文档已索引")

    # 3. E1: 检索质量评估
    print("\n[3/4] E1: 检索质量评估...")
    e1_qa = build_e1_qa_dataset()
    e1_results = {
        "version": "e1_v3_local",
        "corpus_stats": {"total_docs": len(all_docs), "total_chars": sum(len(d["content"]) for d in all_docs), "repos": repo_stats},
        "num_queries": len(e1_qa),
        "methods": {}
    }

    for method_name, index in [("TF-IDF", tfidf), ("BM25", bm25)]:
        per_query = []
        for qa in e1_qa:
            results = index.search(qa["query"], top_k=5)
            rel_id = qa.get("relevant_doc_id", "")
            rel_prefix = qa.get("relevant_doc_id_prefix")
            ev = evaluate_retrieval(results, rel_id, rel_prefix)
            per_query.append({
                "query": qa["query"],
                "relevant": rel_id or rel_prefix,
                "hit": ev["hit"],
                "rr": ev["rr"],
                "top5": ev["top_k_ids"]
            })
        hits = sum(1 for pq in per_query if pq["hit"])
        recall = hits / len(per_query)
        mrr = sum(pq["rr"] for pq in per_query) / len(per_query)
        agg = {"recall@5": round(recall, 4), "mrr": round(mrr, 4), "hits": hits, "total": len(per_query)}
        e1_results["methods"][method_name] = {"aggregate": agg, "per_query": per_query}
        print(f"  {method_name}: Recall@5={recall:.3f}, MRR={mrr:.3f}")

    # RRF 融合
    rrf_per_query = []
    for i, qa in enumerate(e1_qa):
        tfidf_res = tfidf.search(qa["query"], top_k=10)
        bm25_res = bm25.search(qa["query"], top_k=10)
        fused = rrf_fusion([tfidf_res, bm25_res], top_k=5)
        rel_id = qa.get("relevant_doc_id", "")
        rel_prefix = qa.get("relevant_doc_id_prefix")
        ev = evaluate_retrieval(fused, rel_id, rel_prefix)
        rrf_per_query.append({
            "query": qa["query"],
            "relevant": rel_id or rel_prefix,
            "hit": ev["hit"],
            "rr": ev["rr"],
            "top5": ev["top_k_ids"]
        })
    rrf_hits = sum(1 for pq in rrf_per_query if pq["hit"])
    rrf_recall = rrf_hits / len(rrf_per_query)
    rrf_mrr = sum(pq["rr"] for pq in rrf_per_query) / len(rrf_per_query)
    e1_results["methods"]["RRF(TF-IDF + BM25)"] = {
        "aggregate": {"recall@5": round(rrf_recall, 4), "mrr": round(rrf_mrr, 4), "hits": rrf_hits, "total": len(rrf_per_query)},
        "per_query": rrf_per_query
    }
    print(f"  RRF(TF-IDF+BM25): Recall@5={rrf_recall:.3f}, MRR={rrf_mrr:.3f}")

    e1_path = os.path.join(RESULTS_DIR, "e1_v2_retrieval_quality.json")
    with open(e1_path, 'w', encoding='utf-8') as f:
        json.dump(e1_results, f, ensure_ascii=False, indent=2)
    print(f"\n  E1 已保存: {e1_path}")

    # 4. E3: Skill 检索
    print("\n[4/4] E3: Skill 检索评估...")
    skill_tasks = build_e3_skill_tasks()
    e3_per_task = []
    for task in skill_tasks:
        tfidf_res = tfidf.search(task["task"], top_k=5)
        bm25_res = bm25.search(task["task"], top_k=5)
        fused = rrf_fusion([tfidf_res, bm25_res], top_k=5)
        top3_ids = [doc_id for doc_id, _ in fused[:3]]
        top5_ids = [doc_id for doc_id, _ in fused]
        hit3 = any(did.startswith(task["relevant_prefix"]) for did in top3_ids)
        hit5 = any(did.startswith(task["relevant_prefix"]) for did in top5_ids)
        e3_per_task.append({
            "task": task["task"],
            "keywords": task["keywords"],
            "relevant_prefix": task["relevant_prefix"],
            "top3_hit": hit3,
            "top5_hit": hit5,
            "top5": top5_ids
        })
    e3_hit3 = sum(1 for t in e3_per_task if t["top3_hit"])
    e3_hit5 = sum(1 for t in e3_per_task if t["top5_hit"])
    e3_results = {
        "version": "e3_v3_local",
        "num_tasks": len(skill_tasks),
        "aggregate": {"top3_hit_rate": round(e3_hit3 / len(skill_tasks), 4), "top5_hit_rate": round(e3_hit5 / len(skill_tasks), 4)},
        "per_task": e3_per_task
    }
    print(f"  Skill Top3命中率: {e3_hit3}/{len(skill_tasks)} = {e3_hit3/len(skill_tasks):.1%}")
    print(f"  Skill Top5命中率: {e3_hit5}/{len(skill_tasks)} = {e3_hit5/len(skill_tasks):.1%}")

    e3_path = os.path.join(RESULTS_DIR, "e3_v2_skill_retrieval.json")
    with open(e3_path, 'w', encoding='utf-8') as f:
        json.dump(e3_results, f, ensure_ascii=False, indent=2)
    print(f"\n  E3 已保存: {e3_path}")

    # === E4: 准备检索数据供 AI 评估 ===
    print("\n[补充] E4: 准备检索数据供 AI 评估器...")
    e4_per_query = []
    for i, qa in enumerate(e1_qa):
        tfidf_res = tfidf.search(qa["query"], top_k=3)
        bm25_res = bm25.search(qa["query"], top_k=3)
        fused = rrf_fusion([tfidf_res, bm25_res], top_k=3)

        # 获取文档内容
        doc_map = {d["id"]: d["content"] for d in all_docs}
        tfidf_docs = [{"id": did, "content": doc_map.get(did, "")[:800]} for did, _ in tfidf_res[:3]]
        rrf_docs = [{"id": did, "content": doc_map.get(did, "")[:800]} for did, _ in fused[:3]]

        e4_per_query.append({
            "query": qa["query"],
            "relevant_doc_id": qa.get("relevant_doc_id", qa.get("relevant_doc_id_prefix", "")),
            "tfidf_top3": [did for did, _ in tfidf_res[:3]],
            "tfidf_top3_docs": tfidf_docs,
            "rrf_top3": [did for did, _ in fused[:3]],
            "rrf_top3_docs": rrf_docs
        })
        if (i + 1) % 5 == 0:
            print(f"  [{i+1}/{len(e1_qa)}] 已完成")

    e4_retrieval = {
        "version": "e4_v3_local",
        "corpus_stats": {"total_docs": len(all_docs), "total_chars": sum(len(d["content"]) for d in all_docs)},
        "num_queries": len(e4_per_query),
        "per_query": e4_per_query
    }
    e4_path = os.path.join(RESULTS_DIR, "e4_v2_retrieval_results.json")
    with open(e4_path, 'w', encoding='utf-8') as f:
        json.dump(e4_retrieval, f, ensure_ascii=False, indent=2)
    print(f"\n  E4 检索数据已保存: {e4_path}")

    # 汇总
    print("\n" + "=" * 70)
    print("Benchmark 完成!")
    print("=" * 70)
    print(f"\nE1 检索质量:")
    for method, data in e1_results["methods"].items():
        agg = data["aggregate"]
        print(f"  {method:25s} Recall@5={agg['recall@5']:.4f}  MRR={agg['mrr']:.4f}")
    print(f"\nE3 Skill检索:")
    print(f"  Top3命中率: {e3_results['aggregate']['top3_hit_rate']:.1%}")
    print(f"  Top5命中率: {e3_results['aggregate']['top5_hit_rate']:.1%}")
    print(f"\n输出文件:")
    print(f"  {e1_path}")
    print(f"  {e3_path}")
    print(f"  {e4_path}")


if __name__ == "__main__":
    main()
