# -*- coding: utf-8 -*-
"""
E2: 延迟基准测试

测试 NIM API 模式的:
  - 单条查询延迟 (P50, P95, P99)
  - 批量查询吞吐
  - 与 TF-IDF / BM25 本地计算延迟对比

用法:
  python e2_latency_benchmark.py --api_key <NIM_API_KEY> [--model_name nvidia/nemotron-3-embed-1b] [--num_queries 30]
"""

import argparse
import json
import os
import sys
import time
import statistics
from typing import List, Dict

from bench_utils import (
    load_corpus, load_auto_qa,
    SimpleTFIDF, ensure_results_dir, save_json, RESULTS_DIR, SEED
)


def percentile(data: List[float], p: float) -> float:
    """计算百分位数"""
    if not data:
        return 0.0
    sorted_data = sorted(data)
    k = (len(sorted_data) - 1) * p / 100
    f = int(k)
    c = min(f + 1, len(sorted_data) - 1)
    if f == c:
        return sorted_data[f]
    return sorted_data[f] + (sorted_data[c] - sorted_data[f]) * (k - f)


def run_e2(api_key: str, model_name: str = "nvidia/nemotron-3-embed-1b", num_queries: int = 30) -> Dict:
    print("=" * 70)
    print("E2: 延迟基准测试")
    print("=" * 70)

    corpus = load_corpus()
    auto_qa = load_auto_qa()

    # 选择指定数量的 query
    queries = [q["query"] for q in auto_qa[:num_queries]]
    print(f"语料库: {len(corpus)} 条文档")
    print(f"测试查询数: {len(queries)}")
    print()

    results = {}

    # ---------- 1. TF-IDF 本地延迟 ----------
    print("[1/5] TF-IDF 本地检索延迟...")
    tfidf = SimpleTFIDF()
    for doc in corpus:
        tfidf.index(doc["id"], doc["content"])
    tfidf.build_idf()

    tfidf_latencies = []
    for q in queries:
        t0 = time.perf_counter()
        tfidf.search(q, top_k=10)
        tfidf_latencies.append((time.perf_counter() - t0) * 1000)  # ms

    results["TF-IDF (local)"] = {
        "p50_ms": round(percentile(tfidf_latencies, 50), 3),
        "p95_ms": round(percentile(tfidf_latencies, 95), 3),
        "p99_ms": round(percentile(tfidf_latencies, 99), 3),
        "mean_ms": round(statistics.mean(tfidf_latencies), 3),
        "min_ms": round(min(tfidf_latencies), 3),
        "max_ms": round(max(tfidf_latencies), 3),
    }
    print(f"  P50={results['TF-IDF (local)']['p50_ms']:.3f}ms  P95={results['TF-IDF (local)']['p95_ms']:.3f}ms  P99={results['TF-IDF (local)']['p99_ms']:.3f}ms")

    # ---------- 2. BM25 本地延迟 ----------
    print("[2/5] BM25 本地检索延迟...")
    from nexusflow.memory.vector_memory import BM25Retriever
    bm25 = BM25Retriever(k1=1.5, b=0.75)
    for doc in corpus:
        bm25.index(doc["id"], doc["content"])

    bm25_latencies = []
    for q in queries:
        t0 = time.perf_counter()
        bm25.search(q, top_k=10)
        bm25_latencies.append((time.perf_counter() - t0) * 1000)

    results["BM25 (local)"] = {
        "p50_ms": round(percentile(bm25_latencies, 50), 3),
        "p95_ms": round(percentile(bm25_latencies, 95), 3),
        "p99_ms": round(percentile(bm25_latencies, 99), 3),
        "mean_ms": round(statistics.mean(bm25_latencies), 3),
        "min_ms": round(min(bm25_latencies), 3),
        "max_ms": round(max(bm25_latencies), 3),
    }
    print(f"  P50={results['BM25 (local)']['p50_ms']:.3f}ms  P95={results['BM25 (local)']['p95_ms']:.3f}ms  P99={results['BM25 (local)']['p99_ms']:.3f}ms")

    # ---------- 3. Nemotron NIM 单条查询延迟 ----------
    print("[3/5] Nemotron NIM 单条查询延迟...")
    from bench_utils import create_nemotron_provider, RateLimiter
    provider = create_nemotron_provider(api_key=api_key, model_name=model_name)

    nemotron_single_latencies = []
    rate_limiter = RateLimiter(rpm=40)

    for i, q in enumerate(queries):
        rate_limiter.wait()
        t0 = time.perf_counter()
        provider.embed_query(q)
        latency = (time.perf_counter() - t0) * 1000
        nemotron_single_latencies.append(latency)
        if (i + 1) % 5 == 0:
            print(f"  进度: {i+1}/{len(queries)}  最近延迟: {latency:.1f}ms")

    results["Nemotron NIM (single)"] = {
        "p50_ms": round(percentile(nemotron_single_latencies, 50), 3),
        "p95_ms": round(percentile(nemotron_single_latencies, 95), 3),
        "p99_ms": round(percentile(nemotron_single_latencies, 99), 3),
        "mean_ms": round(statistics.mean(nemotron_single_latencies), 3),
        "min_ms": round(min(nemotron_single_latencies), 3),
        "max_ms": round(max(nemotron_single_latencies), 3),
    }
    print(f"  P50={results['Nemotron NIM (single)']['p50_ms']:.3f}ms  P95={results['Nemotron NIM (single)']['p95_ms']:.3f}ms  P99={results['Nemotron NIM (single)']['p99_ms']:.3f}ms")

    # ---------- 4. Nemotron NIM 批量查询吞吐 ----------
    print("[4/5] Nemotron NIM 批量查询吞吐测试...")

    # 分批测试 (每批5条，适应限速)
    batch_size = 5
    batch_latencies = []
    batch_throughputs = []

    for batch_start in range(0, len(queries), batch_size):
        batch = queries[batch_start:batch_start + batch_size]
        if not batch:
            break
        rate_limiter.wait()
        t0 = time.perf_counter()
        provider.embed_batch(batch)
        elapsed = time.perf_counter() - t0
        batch_latencies.append(elapsed * 1000)
        throughput = len(batch) / elapsed if elapsed > 0 else 0
        batch_throughputs.append(throughput)
        print(f"  批次 {batch_start//batch_size + 1}: {len(batch)} 条, {elapsed*1000:.1f}ms, {throughput:.1f} qps")

    results["Nemotron NIM (batch)"] = {
        "batch_size": batch_size,
        "batch_count": len(batch_latencies),
        "avg_batch_latency_ms": round(statistics.mean(batch_latencies), 3) if batch_latencies else 0,
        "avg_throughput_qps": round(statistics.mean(batch_throughputs), 3) if batch_throughputs else 0,
        "p50_batch_latency_ms": round(percentile(batch_latencies, 50), 3) if batch_latencies else 0,
        "p95_batch_latency_ms": round(percentile(batch_latencies, 95), 3) if batch_latencies else 0,
    }
    print(f"  平均批量延迟: {results['Nemotron NIM (batch)']['avg_batch_latency_ms']:.3f}ms  平均吞吐: {results['Nemotron NIM (batch)']['avg_throughput_qps']:.3f} qps")

    # ---------- 5. 端到端检索延迟对比 ----------
    print("[5/5] 端到端检索延迟对比 (查询编码 + 相似度计算)...")

    # 构建 Nemotron 向量存储
    from nexusflow.memory.nemotron_store import NemotronVectorStore
    store = NemotronVectorStore(provider, persist_path=os.path.join(RESULTS_DIR, "e2_nemotron_store.json"))
    items = [{"id": doc["id"], "content": doc["content"]} for doc in corpus]
    store.add_batch(items)

    e2e_nemotron_latencies = []
    for q in queries[:10]:  # 只测前10条，避免过多API调用
        rate_limiter.wait()
        t0 = time.perf_counter()
        store.search(q, top_k=10)
        e2e_nemotron_latencies.append((time.perf_counter() - t0) * 1000)

    # TF-IDF 端到端
    e2e_tfidf_latencies = []
    for q in queries[:10]:
        t0 = time.perf_counter()
        tfidf.search(q, top_k=10)
        e2e_tfidf_latencies.append((time.perf_counter() - t0) * 1000)

    # BM25 端到端
    e2e_bm25_latencies = []
    for q in queries[:10]:
        t0 = time.perf_counter()
        bm25.search(q, top_k=10)
        e2e_bm25_latencies.append((time.perf_counter() - t0) * 1000)

    results["E2E: TF-IDF (local)"] = {
        "p50_ms": round(percentile(e2e_tfidf_latencies, 50), 3),
        "mean_ms": round(statistics.mean(e2e_tfidf_latencies), 3),
    }
    results["E2E: BM25 (local)"] = {
        "p50_ms": round(percentile(e2e_bm25_latencies, 50), 3),
        "mean_ms": round(statistics.mean(e2e_bm25_latencies), 3),
    }
    results["E2E: Nemotron (NIM)"] = {
        "p50_ms": round(percentile(e2e_nemotron_latencies, 50), 3),
        "mean_ms": round(statistics.mean(e2e_nemotron_latencies), 3),
    }
    print(f"  TF-IDF P50: {results['E2E: TF-IDF (local)']['p50_ms']:.3f}ms")
    print(f"  BM25 P50:   {results['E2E: BM25 (local)']['p50_ms']:.3f}ms")
    print(f"  Nemotron P50: {results['E2E: Nemotron (NIM)']['p50_ms']:.3f}ms")

    # 保存结果
    ensure_results_dir()
    output_path = os.path.join(RESULTS_DIR, "e2_latency_benchmark.json")
    save_json(output_path, results)
    print(f"\n结果已保存: {output_path}")

    # 汇总
    print("\n" + "=" * 70)
    print("E2 汇总")
    print("=" * 70)
    for name, metrics in results.items():
        print(f"  {name}: {metrics}")

    return results


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="E2: 延迟基准测试")
    parser.add_argument("--api_key", required=True, help="NIM API Key")
    parser.add_argument("--model_name", default="nvidia/nemotron-3-embed-1b", help="Nemotron 模型ID")
    parser.add_argument("--num_queries", type=int, default=30, help="测试查询数")
    args = parser.parse_args()

    run_e2(api_key=args.api_key, model_name=args.model_name, num_queries=args.num_queries)
