# -*- coding: utf-8 -*-
"""
E_nemotron: materials-kb 论文库 Nemotron 语义向量专项 Benchmark

语料库: materials-kb（材料科学知识库，14文件, ~90文档, ~225KB）
方法: TF-IDF / BM25 / Nemotron Semantic / RRF(TF-IDF+Nemotron) / RRF(BM25+Nemotron) / RRF(All)
评估: Recall@5, MRR

用法: python3 e_nemotron_materials_kb.py --nim_api_key <KEY>
"""

import json
import os
import sys
import math
import re
import time
import random
from collections import Counter, defaultdict
from typing import List, Dict, Tuple

random.seed(42)

# === 路径 ===
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WORKSPACE = os.path.dirname(REPO_ROOT)  # parent of repo root
MATERIALS_KB = os.path.join(WORKSPACE, "all-repos", "materials-kb")
BENCH_DIR = os.path.join(REPO_ROOT, "examples", "nemotron_benchmark")
RESULTS_DIR = os.path.join(BENCH_DIR, "results")
os.makedirs(RESULTS_DIR, exist_ok=True)

NX_ROOT = os.path.join(WORKSPACE, "NexusFlow-repo")
if NX_ROOT not in sys.path:
    sys.path.insert(0, NX_ROOT)

SUPPORTED_EXT = {'.md', '.txt'}
MAX_CHUNK_CHARS = 2500


# ===================== 语料库扫描 =====================

def scan_materials_kb() -> List[Dict]:
    docs = []
    for root, dirs, files in os.walk(MATERIALS_KB):
        dirs[:] = [d for d in dirs if d not in {'__pycache__', '.git', 'node_modules'}]
        for fname in files:
            ext = os.path.splitext(fname)[1].lower()
            if ext not in SUPPORTED_EXT:
                continue
            fpath = os.path.join(root, fname)
            rel_path = os.path.relpath(fpath, MATERIALS_KB)
            try:
                with open(fpath, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
            except:
                continue
            if len(content) < 100:
                continue
            if len(content) <= MAX_CHUNK_CHARS:
                docs.append({"id": f"materials-kb/{rel_path}", "content": content, "source": rel_path})
            else:
                chunks = split_by_heading(content, MAX_CHUNK_CHARS)
                for i, chunk in enumerate(chunks):
                    docs.append({"id": f"materials-kb/{rel_path}#chunk{i}", "content": chunk, "source": rel_path})
    return docs


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


# ===================== 分词 =====================

def tokenize(text: str) -> List[str]:
    text = text.lower()
    tokens = []
    chinese_chars = re.findall(r'[\u4e00-\u9fff]', text)
    for i in range(len(chinese_chars) - 1):
        tokens.append(chinese_chars[i] + chinese_chars[i+1])
    if chinese_chars:
        tokens.append(chinese_chars[-1])
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
        for t in set(tokens):
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


# ===================== Nemotron Semantic Search =====================

class NemotronSemanticIndex:
    def __init__(self, provider):
        self.provider = provider
        self.doc_embeddings = {}  # doc_id -> embedding vector
        self.doc_ids = []

    def build(self, docs: List[Dict], batch_size: int = 5):
        """Build index by embedding all documents"""
        total = len(docs)
        for i in range(0, total, batch_size):
            batch = docs[i:i+batch_size]
            for doc in batch:
                try:
                    emb = self.provider.embed_document(doc["content"][:2000])  # truncate to avoid API limits
                    self.doc_embeddings[doc["id"]] = emb
                    self.doc_ids.append(doc["id"])
                except Exception as e:
                    print(f"    [ERROR] {doc['id'][:50]}: {e}")
                time.sleep(1.5)  # rate limit protection
            print(f"    Embedded {min(i+batch_size, total)}/{total}")
        print(f"  Nemotron: {len(self.doc_embeddings)} docs embedded")

    def search(self, query: str, top_k: int = 5) -> List[Tuple[str, float]]:
        try:
            q_vec = self.provider.embed_query(query)
        except Exception as e:
            print(f"    [ERROR] Query embed: {e}")
            return []
        
        scores = {}
        for doc_id, doc_vec in self.doc_embeddings.items():
            sim = cosine_sim(q_vec, doc_vec)
            scores[doc_id] = sim
        time.sleep(1.5)  # rate limit between queries
        return sorted(scores.items(), key=lambda x: -x[1])[:top_k]


def cosine_sim(a, b) -> float:
    if len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(x * x for x in b))
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)


# ===================== RRF 融合 =====================

def rrf_fusion(results_list: List[List[Tuple[str, float]]], k=60, top_k=5) -> List[Tuple[str, float]]:
    scores = defaultdict(float)
    for results in results_list:
        for rank, (doc_id, _) in enumerate(results):
            scores[doc_id] += 1.0 / (k + rank + 1)
    return sorted(scores.items(), key=lambda x: -x[1])[:top_k]


# ===================== QA 数据集（材料科学领域） =====================

def build_qa_dataset() -> List[Dict]:
    """基于 materials-kb 内容的 QA 数据集"""
    return [
        {"query": "AGI深度文献调研覆盖了哪些关键方向", "relevant_prefix": "materials-kb/reports/AGI"},
        {"query": "材料科学前沿论文2024-2026有哪些重要发现", "relevant_prefix": "materials-kb/reports/材料科学"},
        {"query": "认知架构开源项目有哪些代表性工作", "relevant_prefix": "materials-kb/reports/认知架构"},
        {"query": "AGI进化路径的调研报告核心结论", "relevant_prefix": "materials-kb/reports/AGI进化"},
        {"query": "材料知识库的索引结构如何组织", "relevant_prefix": "materials-kb/知识库_v2/"},
        {"query": "知识库全量索引包含哪些材料类别", "relevant_prefix": "materials-kb/知识库_v2/全量索引"},
        {"query": "fine-tune数据集的QA提取方法是什么", "relevant_prefix": "materials-kb/fine-tune/qa-extraction"},
        {"query": "SFT数据格式的具体规范", "relevant_prefix": "materials-kb/fine-tune/sft-dataset"},
        {"query": "AGI深度索引的关键技术领域", "relevant_prefix": "materials-kb/知识库_v2/AGI深度索引"},
        {"query": "前沿补充索引新增了哪些研究方向", "relevant_prefix": "materials-kb/知识库_v2/前沿补充"},
        {"query": "材料科学中的机器学习应用有哪些进展", "relevant_prefix": "materials-kb/reports/材料科学"},
        {"query": "认知智能与AGI的关联性分析", "relevant_prefix": "materials-kb/reports/认知架构"},
        {"query": "知识库v2相比v1有哪些改进", "relevant_prefix": "materials-kb/知识库_v2/"},
        {"query": "AGI领域中语言模型Scaling Law的研究现状", "relevant_prefix": "materials-kb/reports/AGI"},
        {"query": "材料信息学中高通量筛选方法综述", "relevant_prefix": "materials-kb/reports/材料科学"},
    ]


# ===================== 评估 =====================

def evaluate(results: List[Tuple[str, float]], relevant_prefix: str, k=5) -> Dict:
    top_k_ids = [did for did, _ in results[:k]]
    hit = any(did.startswith(relevant_prefix) for did in top_k_ids)
    rr = 0.0
    for rank, did in enumerate(top_k_ids):
        if did.startswith(relevant_prefix):
            rr = 1.0 / (rank + 1)
            break
    return {"hit": hit, "rr": rr, "top_k_ids": top_k_ids}


# ===================== 主流程 =====================

def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--nim_api_key", required=True)
    args = parser.parse_args()

    print("=" * 70)
    print("E_nemotron: materials-kb 论文库 Nemotron 语义向量 Benchmark")
    print("=" * 70)

    # 1. 扫描
    print("\n[1/5] 扫描 materials-kb...")
    docs = scan_materials_kb()
    total_chars = sum(len(d["content"]) for d in docs)
    sources = set(d["source"] for d in docs)
    print(f"  {len(sources)} 文件 → {len(docs)} 文档块, {total_chars:,} 字符")

    # 2. 构建 TF-IDF + BM25
    print("\n[2/5] 构建 TF-IDF + BM25 索引...")
    tfidf = TFIDFIndex()
    for d in docs:
        tfidf.add(d["id"], d["content"])
    print(f"  TF-IDF: {tfidf.N} docs")

    bm25 = BM25Index()
    for d in docs:
        bm25.add(d["id"], d["content"])
    bm25.build()
    print(f"  BM25: {bm25.N} docs")

    # 3. 构建 Nemotron 语义索引
    print("\n[3/5] 构建 Nemotron 语义向量索引...")
    from nexusflow.memory.nemotron_provider import NemotronEmbeddingProvider
    provider = NemotronEmbeddingProvider(
        api_key=args.nim_api_key,
        model_name="nvidia/nemotron-3-embed-1b",
        mode="nim"
    )
    nemotron_idx = NemotronSemanticIndex(provider)
    nemotron_idx.build(docs, batch_size=5)

    # 4. E1: 检索质量
    print("\n[4/5] E1: 检索质量评估...")
    qa = build_qa_dataset()
    methods = {}

    # TF-IDF
    tfidf_pq = []
    for q in qa:
        res = tfidf.search(q["query"], top_k=5)
        ev = evaluate(res, q["relevant_prefix"])
        tfidf_pq.append({"query": q["query"], "relevant": q["relevant_prefix"], "hit": ev["hit"], "rr": ev["rr"], "top5": ev["top_k_ids"]})
    methods["TF-IDF"] = {
        "aggregate": {"recall@5": round(sum(p["hit"] for p in tfidf_pq)/len(qa), 4), "mrr": round(sum(p["rr"] for p in tfidf_pq)/len(qa), 4)},
        "per_query": tfidf_pq
    }

    # BM25
    bm25_pq = []
    for q in qa:
        res = bm25.search(q["query"], top_k=5)
        ev = evaluate(res, q["relevant_prefix"])
        bm25_pq.append({"query": q["query"], "relevant": q["relevant_prefix"], "hit": ev["hit"], "rr": ev["rr"], "top5": ev["top_k_ids"]})
    methods["BM25"] = {
        "aggregate": {"recall@5": round(sum(p["hit"] for p in bm25_pq)/len(qa), 4), "mrr": round(sum(p["rr"] for p in bm25_pq)/len(qa), 4)},
        "per_query": bm25_pq
    }

    # Nemotron Semantic
    print("  Nemotron 语义搜索中...")
    nem_pq = []
    for i, q in enumerate(qa):
        res = nemotron_idx.search(q["query"], top_k=5)
        ev = evaluate(res, q["relevant_prefix"])
        nem_pq.append({"query": q["query"], "relevant": q["relevant_prefix"], "hit": ev["hit"], "rr": ev["rr"], "top5": ev["top_k_ids"]})
        print(f"    [{i+1}/{len(qa)}] {'✓' if ev['hit'] else '✗'} {q['query'][:40]}")
    methods["Nemotron Semantic"] = {
        "aggregate": {"recall@5": round(sum(p["hit"] for p in nem_pq)/len(qa), 4), "mrr": round(sum(p["rr"] for p in nem_pq)/len(qa), 4)},
        "per_query": nem_pq
    }

    # RRF(TF-IDF + Nemotron)
    rrf_tn_pq = []
    for i, q in enumerate(qa):
        tfidf_res = tfidf.search(q["query"], top_k=10)
        nem_res = nemotron_idx.search(q["query"], top_k=10)
        fused = rrf_fusion([tfidf_res, nem_res], top_k=5)
        ev = evaluate(fused, q["relevant_prefix"])
        rrf_tn_pq.append({"query": q["query"], "relevant": q["relevant_prefix"], "hit": ev["hit"], "rr": ev["rr"], "top5": ev["top_k_ids"]})
    methods["RRF(TF-IDF+Nemotron)"] = {
        "aggregate": {"recall@5": round(sum(p["hit"] for p in rrf_tn_pq)/len(qa), 4), "mrr": round(sum(p["rr"] for p in rrf_tn_pq)/len(qa), 4)},
        "per_query": rrf_tn_pq
    }

    # RRF(BM25 + Nemotron)
    rrf_bn_pq = []
    for i, q in enumerate(qa):
        bm25_res = bm25.search(q["query"], top_k=10)
        nem_res = nemotron_idx.search(q["query"], top_k=10)
        fused = rrf_fusion([bm25_res, nem_res], top_k=5)
        ev = evaluate(fused, q["relevant_prefix"])
        rrf_bn_pq.append({"query": q["query"], "relevant": q["relevant_prefix"], "hit": ev["hit"], "rr": ev["rr"], "top5": ev["top_k_ids"]})
    methods["RRF(BM25+Nemotron)"] = {
        "aggregate": {"recall@5": round(sum(p["hit"] for p in rrf_bn_pq)/len(qa), 4), "mrr": round(sum(p["rr"] for p in rrf_bn_pq)/len(qa), 4)},
        "per_query": rrf_bn_pq
    }

    # RRF(All three)
    rrf_all_pq = []
    for i, q in enumerate(qa):
        tfidf_res = tfidf.search(q["query"], top_k=10)
        bm25_res = bm25.search(q["query"], top_k=10)
        nem_res = nemotron_idx.search(q["query"], top_k=10)
        fused = rrf_fusion([tfidf_res, bm25_res, nem_res], top_k=5)
        ev = evaluate(fused, q["relevant_prefix"])
        rrf_all_pq.append({"query": q["query"], "relevant": q["relevant_prefix"], "hit": ev["hit"], "rr": ev["rr"], "top5": ev["top_k_ids"]})
    methods["RRF(TF-IDF+BM25+Nemotron)"] = {
        "aggregate": {"recall@5": round(sum(p["hit"] for p in rrf_all_pq)/len(qa), 4), "mrr": round(sum(p["rr"] for p in rrf_all_pq)/len(qa), 4)},
        "per_query": rrf_all_pq
    }

    # 打印结果
    print(f"\n{'方法':<30s} {'Recall@5':>10s} {'MRR':>10s}")
    print("-" * 52)
    for name, data in methods.items():
        agg = data["aggregate"]
        print(f"  {name:<28s} {agg['recall@5']:>10.4f} {agg['mrr']:>10.4f}")

    # 保存结果
    result = {
        "version": "e_nemotron_materials_kb",
        "corpus": "materials-kb (论文库)",
        "corpus_stats": {"files": len(sources), "docs": len(docs), "chars": total_chars},
        "num_queries": len(qa),
        "methods": methods
    }
    out_path = os.path.join(RESULTS_DIR, "e_nemotron_materials_kb.json")
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print(f"\n结果已保存: {out_path}")

    # === E4: 准备 AI 评估数据 ===
    print("\n[5/5] E4: 准备 AI 评估数据...")
    doc_map = {d["id"]: d["content"] for d in docs}
    e4_queries = []
    for q in qa:
        tfidf_res = tfidf.search(q["query"], top_k=3)
        nem_res = nemotron_idx.search(q["query"], top_k=3)
        
        tfidf_docs = [{"id": did, "content": doc_map.get(did, "")[:800]} for did, _ in tfidf_res[:3]]
        nem_docs = [{"id": did, "content": doc_map.get(did, "")[:800]} for did, _ in nem_res[:3]]
        
        e4_queries.append({
            "query": q["query"],
            "relevant_prefix": q["relevant_prefix"],
            "tfidf_top3_docs": tfidf_docs,
            "nemotron_top3_docs": nem_docs
        })

    e4_path = os.path.join(RESULTS_DIR, "e4_nemotron_evaluation_data.json")
    with open(e4_path, 'w', encoding='utf-8') as f:
        json.dump({"queries": e4_queries}, f, ensure_ascii=False, indent=2)
    print(f"E4 评估数据已保存: {e4_path}")

    print("\n" + "=" * 70)
    print("Benchmark 完成!")
    print("=" * 70)


if __name__ == "__main__":
    main()
