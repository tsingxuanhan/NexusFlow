# -*- coding: utf-8 -*-
"""
E1: 检索质量对比实验

对比以下检索方式在相同 corpus + queries 上的表现：
  1. TF-IDF only
  2. BM25 only (NexusFlow BM25Retriever)
  3. Nemotron semantic only (NIM API)
  4. RRF(TF-IDF + Nemotron)
  5. RRF(BM25 + Nemotron)
  6. RRF(TF-IDF + BM25 + Nemotron)

指标：Recall@5, MRR, NDCG@10

用法:
  python e1_retrieval_quality.py --api_key <NIM_API_KEY> [--model_name nvidia/nemotron-3-embed-1b]
"""

import argparse
import json
import os
import sys
import time
import math
from typing import List, Dict, Tuple

from bench_utils import (
    load_corpus, load_auto_qa, load_adversarial,
    SimpleTFIDF, rrf_fusion_nexusflow,
    compute_metrics, aggregate_metrics, format_metrics_table,
    ensure_results_dir, save_json, RESULTS_DIR, SEED
)


def build_bm25_index(corpus: List[Dict]):
    """构建 NexusFlow BM25Retriever 索引"""
    from nexusflow.memory.vector_memory import BM25Retriever
    bm25 = BM25Retriever(k1=1.5, b=0.75)
    for doc in corpus:
        bm25.index(doc["id"], doc["content"])
    return bm25


def build_tfidf_index(corpus: List[Dict]) -> SimpleTFIDF:
    tfidf = SimpleTFIDF()
    for doc in corpus:
        tfidf.index(doc["id"], doc["content"])
    tfidf.build_idf()
    return tfidf


def build_nemotron_store(corpus: List[Dict], provider):
    """使用 Nemotron provider 构建 embedding 缓存"""
    from nexusflow.memory.nemotron_store import NemotronVectorStore
    store_path = os.path.join(RESULTS_DIR, "e1_nemotron_store.json")
    if os.path.exists(store_path):
        os.remove(store_path)  # 避免重复加载
    store = NemotronVectorStore(provider, persist_path=store_path)
    # 批量添加
    items = [{"id": doc["id"], "content": doc["content"], "metadata": doc.get("metadata", {})} for doc in corpus]
    store.add_batch(items)
    return store


def run_single_method(method_name: str, queries: List[Dict], search_fn, top_k: int = 10) -> Dict:
    """运行单一检索方法并返回指标"""
    per_query = []
    for q in queries:
        retrieved = search_fn(q["query"], top_k=top_k)
        retrieved_ids = [doc_id for doc_id, _ in retrieved]
        metrics = compute_metrics(retrieved_ids, q["relevant_doc_id"])
        per_query.append(metrics)

    agg = aggregate_metrics(per_query)
    return {"method": method_name, "aggregate": agg, "per_query": per_query}


def run_e1(api_key: str, model_name: str = "nvidia/nemotron-3-embed-1b", top_k: int = 10) -> Dict:
    print("=" * 70)
    print("E1: 检索质量对比实验")
    print("=" * 70)

    corpus = load_corpus()
    auto_qa = load_auto_qa()
    adversarial = load_adversarial()
    all_queries = auto_qa + adversarial

    print(f"语料库: {len(corpus)} 条文档")
    print(f"QA 查询: {len(auto_qa)} 条")
    print(f"对抗查询: {len(adversarial)} 条")
    print(f"总查询数: {len(all_queries)}")
    print()

    # ---------- 1. 构建 TF-IDF ----------
    print("[1/6] 构建 TF-IDF 索引...")
    tfidf = build_tfidf_index(corpus)
    print(f"  TF-IDF 词汇量: {len(tfidf.idf)}")

    # ---------- 2. 构建 BM25 ----------
    print("[2/6] 构建 BM25 索引 (NexusFlow)...")
    bm25 = build_bm25_index(corpus)
    print(f"  BM25 文档数: {bm25._doc_count}")

    # ---------- 3. 构建 Nemotron 语义存储 ----------
    print("[3/6] 构建 Nemotron 语义向量 (NIM API)...")
    from bench_utils import create_nemotron_provider, RateLimiter
    provider = create_nemotron_provider(api_key=api_key, model_name=model_name)
    store = build_nemotron_store(corpus, provider)
    print(f"  Nemotron 向量数: {store.count()}")

    # ---------- 4. 定义各方法的 search 函数 ----------
    def tfidf_search(query, top_k=10):
        return tfidf.search(query, top_k=top_k)

    def bm25_search(query, top_k=10):
        return bm25.search(query, top_k=top_k)

    def nemotron_search(query, top_k=10):
        return store.search(query, top_k=top_k)

    def rrf_tfidf_nemotron(query, top_k=10):
        t_results = tfidf.search(query, top_k=top_k)
        n_results = store.search(query, top_k=top_k)
        fused = rrf_fusion_nexusflow(t_results, n_results)
        return fused[:top_k]

    def rrf_bm25_nemotron(query, top_k=10):
        b_results = bm25.search(query, top_k=top_k)
        n_results = store.search(query, top_k=top_k)
        fused = rrf_fusion_nexusflow(b_results, n_results)
        return fused[:top_k]

    def rrf_three_way(query, top_k=10):
        t_results = tfidf.search(query, top_k=top_k)
        b_results = bm25.search(query, top_k=top_k)
        n_results = store.search(query, top_k=top_k)
        fused = rrf_fusion_nexusflow(t_results, b_results, n_results)
        return fused[:top_k]

    methods = [
        ("TF-IDF only", tfidf_search),
        ("BM25 only", bm25_search),
        ("Nemotron semantic only", nemotron_search),
        ("RRF(TF-IDF + Nemotron)", rrf_tfidf_nemotron),
        ("RRF(BM25 + Nemotron)", rrf_bm25_nemotron),
        ("RRF(三路: TF-IDF+BM25+Nemotron)", rrf_three_way),
    ]

    # ---------- 5. 运行所有方法 ----------
    all_results = {}
    rate_limiter = RateLimiter(rpm=40)

    for i, (name, search_fn) in enumerate(methods):
        print(f"[{i+1+len(methods)*0}/{len(methods)}] 运行: {name} ...")
        # Nemotron 相关方法需要限速
        if "Nemotron" in name:
            # 对每个 query 限速
            per_query = []
            for q in all_queries:
                rate_limiter.wait()
                retrieved = search_fn(q["query"], top_k=top_k)
                retrieved_ids = [doc_id for doc_id, _ in retrieved]
                metrics = compute_metrics(retrieved_ids, q["relevant_doc_id"])
                per_query.append(metrics)
            agg = aggregate_metrics(per_query)
            all_results[name] = {"aggregate": agg, "per_query": per_query}
        else:
            result = run_single_method(name, all_queries, search_fn, top_k=top_k)
            all_results[name] = {"aggregate": result["aggregate"], "per_query": result["per_query"]}

        agg = all_results[name]["aggregate"]
        print(f"  Recall@5={agg.get('recall@5', 0):.4f}  MRR={agg.get('mrr', 0):.4f}  NDCG@10={agg.get('ndcg@10', 0):.4f}")

    # ---------- 6. 分别统计 auto_qa 和 adversarial ----------
    print("\n--- 分组统计 ---")
    for group_name, group_queries in [("auto_qa", auto_qa), ("adversarial", adversarial)]:
        print(f"\n[{group_name}] ({len(group_queries)} 条)")
        for method_name in all_results:
            # 从 per_query 中按索引提取
            start_idx = 0 if group_name == "auto_qa" else len(auto_qa)
            group_per_query = all_results[method_name]["per_query"][start_idx:start_idx + len(group_queries)]
            group_agg = aggregate_metrics(group_per_query)
            print(f"  {method_name}: Recall@5={group_agg.get('recall@5', 0):.4f}  MRR={group_agg.get('mrr', 0):.4f}  NDCG@10={group_agg.get('ndcg@10', 0):.4f}")

    # 保存结果
    ensure_results_dir()
    output_path = os.path.join(RESULTS_DIR, "e1_retrieval_quality.json")
    save_json(output_path, all_results)
    print(f"\n结果已保存: {output_path}")

    # 打印汇总表
    print("\n" + "=" * 70)
    print("E1 汇总（全部查询）")
    print("=" * 70)
    agg_only = {k: v["aggregate"] for k, v in all_results.items()}
    print(format_metrics_table(agg_only))

    return all_results


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="E1: 检索质量对比实验")
    parser.add_argument("--api_key", required=True, help="NIM API Key")
    parser.add_argument("--model_name", default="nvidia/nemotron-3-embed-1b", help="Nemotron 模型ID")
    parser.add_argument("--top_k", type=int, default=10, help="检索 top_k")
    args = parser.parse_args()

    run_e1(api_key=args.api_key, model_name=args.model_name, top_k=args.top_k)
