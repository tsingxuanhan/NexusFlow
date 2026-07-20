# -*- coding: utf-8 -*-
"""
E4: 端到端任务质量评测

使用 GLM-5.2 API 作为 LLM 评估器，对比有无 Nemotron 语义增强的检索增强回答质量。

流程:
  1. 对每个 QA query，分别用 TF-IDF-only 和 Nemotron-RRF 检索 top-3 文档
  2. 基于检索结果，用 Qwen3.5-397B 生成回答
  3. 用 Qwen3.5-397B 作为评估器，对回答进行 1-5 分打分
  4. 对比两组评分差异

用法:
  python e4_e2e_task_quality.py --nim_api_key <NIM_KEY> --llm_api_key <GLM_KEY>
"""

import argparse
import json
import os
import sys
import time
import requests
from typing import List, Dict, Tuple

from bench_utils import (
    load_corpus, load_auto_qa,
    SimpleTFIDF, rrf_fusion_nexusflow,
    ensure_results_dir, save_json, RESULTS_DIR, SEED
)

LLM_ENDPOINT = "https://integrate.api.nvidia.com/v1/chat/completions"


def llm_chat(api_key: str, messages: List[Dict], max_tokens: int = 800, temperature: float = 0.3) -> str:
    """调用 GLM-5.2 API 进行对话"""
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": "qwen/qwen3.5-397b-a17b",
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": temperature,
    }
    for attempt in range(5):
        try:
            resp = requests.post(LLM_ENDPOINT, headers=headers, json=payload, timeout=300)
            resp.raise_for_status()
            data = resp.json()
            return data["choices"][0]["message"]["content"].strip()
        except Exception as e:
            if attempt < 4:
                wait_time = 30 * (attempt + 1)  # 30s, 60s, 90s, 120s
                print(f"  LLM API 重试 ({attempt+1}/5), 等待{wait_time}s: {e}")
                time.sleep(wait_time)
            else:
                raise


def generate_answer(llm_api_key: str, query: str, retrieved_docs: List[Dict]) -> str:
    """基于检索到的文档生成回答"""
    context = "\n\n".join([
        f"[文档{d['id']}] {d['content'][:500]}"
        for d in retrieved_docs
    ])

    prompt = f"""你是一个混凝土材料科学领域的专业问答助手。请根据以下检索到的参考文档，回答用户的问题。

参考文档：
{context}

用户问题：{query}

要求：
1. 只基于参考文档内容回答，不要编造
2. 如果参考文档中没有相关信息，请说明"根据现有参考资料，无法回答该问题"
3. 回答简洁准确，不超过200字

回答："""

    return llm_chat(llm_api_key, [{"role": "user", "content": prompt}], max_tokens=400, temperature=0.3)


def evaluate_answer(llm_api_key: str, query: str, answer: str, ground_truth_doc: Dict) -> Tuple[int, str]:
    """使用 Qwen3.5-397B 评估回答质量，返回 (分数, 评语)"""
    eval_prompt = f"""请评估以下问答对的质量，给出 1-5 分的评分。

评分标准：
- 5分：回答完全正确，准确覆盖了关键信息，表述专业
- 4分：回答基本正确，覆盖了主要信息，有小瑕疵
- 3分：回答部分正确，遗漏了一些重要信息
- 2分：回答有明显错误或严重遗漏
- 1分：回答完全错误或未回答问题

用户问题：{query}

待评估回答：{answer}

参考标准答案（来自正确文档）：
{ground_truth_doc['content'][:500]}

请严格按以下格式输出：
分数：X
评语：简短说明评分理由（不超过50字）"""

    result = llm_chat(llm_api_key, [{"role": "user", "content": eval_prompt}], max_tokens=200, temperature=0.1)

    # 解析分数
    score = 3
    comment = result
    for line in result.split("\n"):
        line = line.strip()
        if line.startswith("分数") or line.startswith("分数："):
            try:
                score_str = line.split("：")[-1].split(":")[-1].strip()
                # 提取数字
                import re
                nums = re.findall(r'\d+', score_str)
                if nums:
                    score = int(nums[0])
                    score = max(1, min(5, score))
            except:
                pass
        elif line.startswith("评语"):
            comment = line.split("：", 1)[-1].strip() if "：" in line else line.split(":", 1)[-1].strip()

    return score, comment


def run_e4(nim_api_key: str, llm_api_key: str, model_name: str = "nvidia/nemotron-3-embed-1b", num_queries: int = 20) -> Dict:
    print("=" * 70)
    print("E4: 端到端任务质量评测 (GLM-5.2 评估器)")
    print("=" * 70)

    corpus = load_corpus()
    auto_qa = load_auto_qa()
    queries = auto_qa[:num_queries]

    print(f"语料库: {len(corpus)} 条文档")
    print(f"评测查询数: {len(queries)}")
    print()

    # ---------- 1. 构建索引 ----------
    print("[1/5] 构建 TF-IDF 索引...")
    tfidf = SimpleTFIDF()
    for doc in corpus:
        tfidf.index(doc["id"], doc["content"])
    tfidf.build_idf()

    print("[2/5] 构建 BM25 索引...")
    from nexusflow.memory.vector_memory import BM25Retriever
    bm25 = BM25Retriever(k1=1.5, b=0.75)
    for doc in corpus:
        bm25.index(doc["id"], doc["content"])

    print("[3/5] 构建 Nemotron 语义存储...")
    from bench_utils import create_nemotron_provider, RateLimiter
    provider = create_nemotron_provider(api_key=nim_api_key, model_name=model_name)
    from nexusflow.memory.nemotron_store import NemotronVectorStore
    store_path = os.path.join(RESULTS_DIR, "e4_nemotron_store.json")
    if os.path.exists(store_path):
        os.remove(store_path)  # 避免重复加载
    store = NemotronVectorStore(provider, persist_path=store_path)
    items = [{"id": doc["id"], "content": doc["content"]} for doc in corpus]
    store.add_batch(items)

    # 文档 ID -> 文档内容的映射
    doc_map = {doc["id"]: doc for doc in corpus}

    rate_limiter = RateLimiter(rpm=20)  # 更保守的速率限制，避免429

    # ---------- 2. 生成回答 ----------
    print(f"\n[4/5] 生成回答并评估 ({len(queries)} 个查询)...")

    tfidf_scores = []
    nemotron_scores = []
    per_query_results = []

    for i, qa in enumerate(queries):
        query = qa["query"]
        relevant_id = qa["relevant_doc_id"]
        ground_truth = doc_map.get(relevant_id, {"id": relevant_id, "content": "未知"})

        print(f"\n  [{i+1}/{len(queries)}] Q: {query[:60]}...")

        try:
            # --- TF-IDF only 检索 ---
            tfidf_results = tfidf.search(query, top_k=3)
            tfidf_docs = [doc_map.get(doc_id, {"id": doc_id, "content": ""}) for doc_id, _ in tfidf_results]

            # --- Nemotron RRF 检索 (TF-IDF + BM25 + Nemotron 三路融合) ---
            rate_limiter.wait()
            t_results = tfidf.search(query, top_k=10)
            b_results = bm25.search(query, top_k=10)
            n_results = store.search(query, top_k=10)
            fused = rrf_fusion_nexusflow(t_results, b_results, n_results)
            nemotron_docs = [doc_map.get(doc_id, {"id": doc_id, "content": ""}) for doc_id, _ in fused[:3]]

            # --- 生成回答 ---
            rate_limiter.wait()  # 控制 LLM 调用频率
            tfidf_answer = generate_answer(llm_api_key, query, tfidf_docs)
            print(f"    TF-IDF 回答: {tfidf_answer[:80]}...")

            rate_limiter.wait()
            nemotron_answer = generate_answer(llm_api_key, query, nemotron_docs)
            print(f"    Nemotron 回答: {nemotron_answer[:80]}...")

            # --- 评估回答 ---
            rate_limiter.wait()
            tfidf_score, tfidf_comment = evaluate_answer(llm_api_key, query, tfidf_answer, ground_truth)
            print(f"    TF-IDF 评分: {tfidf_score}/5 ({tfidf_comment[:40]})")

            rate_limiter.wait()
            nemotron_score, nemotron_comment = evaluate_answer(llm_api_key, query, nemotron_answer, ground_truth)
            print(f"    Nemotron 评分: {nemotron_score}/5 ({nemotron_comment[:40]})")

            tfidf_scores.append(tfidf_score)
            nemotron_scores.append(nemotron_score)

            per_query_results.append({
                "query": query,
                "relevant_doc_id": relevant_id,
                "tfidf_retrieved": [doc_id for doc_id, _ in tfidf_results[:3]],
                "nemotron_retrieved": [doc_id for doc_id, _ in fused[:3]],
                "tfidf_answer": tfidf_answer,
                "nemotron_answer": nemotron_answer,
                "tfidf_score": tfidf_score,
                "nemotron_score": nemotron_score,
                "tfidf_comment": tfidf_comment,
                "nemotron_comment": nemotron_comment,
                "score_diff": nemotron_score - tfidf_score,
            })
        except Exception as e:
            print(f"    [ERROR] 查询处理失败: {e}")
            per_query_results.append({
                "query": query,
                "relevant_doc_id": relevant_id,
                "error": str(e),
                "tfidf_score": 0,
                "nemotron_score": 0,
                "score_diff": 0,
            })

    # ---------- 3. 汇总统计 ----------
    print(f"\n[5/5] 汇总统计...")

    import statistics
    tfidf_avg = statistics.mean(tfidf_scores)
    nemotron_avg = statistics.mean(nemotron_scores)
    tfidf_std = statistics.stdev(tfidf_scores) if len(tfidf_scores) > 1 else 0
    nemotron_std = statistics.stdev(nemotron_scores) if len(nemotron_scores) > 1 else 0

    # 分数分布
    score_dist_tfidf = {str(i): tfidf_scores.count(i) for i in range(1, 6)}
    score_dist_nemotron = {str(i): nemotron_scores.count(i) for i in range(1, 6)}

    # 提升/下降/持平统计
    improved = sum(1 for r in per_query_results if r["score_diff"] > 0)
    decreased = sum(1 for r in per_query_results if r["score_diff"] < 0)
    unchanged = sum(1 for r in per_query_results if r["score_diff"] == 0)

    results = {
        "num_queries": len(queries),
        "tfidf_only": {
            "avg_score": round(tfidf_avg, 3),
            "std_score": round(tfidf_std, 3),
            "score_distribution": score_dist_tfidf,
            "scores": tfidf_scores,
        },
        "nemotron_rrf": {
            "avg_score": round(nemotron_avg, 3),
            "std_score": round(nemotron_std, 3),
            "score_distribution": score_dist_nemotron,
            "scores": nemotron_scores,
        },
        "improvement": {
            "avg_score_diff": round(nemotron_avg - tfidf_avg, 3),
            "improved_count": improved,
            "decreased_count": decreased,
            "unchanged_count": unchanged,
            "improvement_rate": round(improved / len(queries), 4) if queries else 0,
        },
        "per_query": per_query_results,
    }

    # 保存结果
    ensure_results_dir()
    output_path = os.path.join(RESULTS_DIR, "e4_e2e_task_quality.json")
    save_json(output_path, results)
    print(f"\n结果已保存: {output_path}")

    # 汇总
    print("\n" + "=" * 70)
    print("E4 汇总")
    print("=" * 70)
    print(f"  TF-IDF only 平均分:      {tfidf_avg:.3f} ± {tfidf_std:.3f}")
    print(f"  Nemotron RRF 平均分:     {nemotron_avg:.3f} ± {nemotron_std:.3f}")
    print(f"  平均分差: {results['improvement']['avg_score_diff']:+.3f}")
    print(f"  提升: {improved}  下降: {decreased}  持平: {unchanged}")
    print(f"  提升率: {results['improvement']['improvement_rate']:.2%}")
    print(f"\n  分数分布:")
    print(f"    {'分数':<8} {'TF-IDF':<10} {'Nemotron':<10}")
    for s in range(1, 6):
        print(f"    {s}分     {score_dist_tfidf[str(s)]:<10} {score_dist_nemotron[str(s)]:<10}")

    return results


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="E4: 端到端任务质量评测")
    parser.add_argument("--nim_api_key", required=True, help="NIM API Key (Nemotron embeddings)")
    parser.add_argument("--llm_api_key", required=True, help="GLM-5.2 API Key (LLM 评估器)")
    parser.add_argument("--model_name", default="nvidia/nemotron-3-embed-1b", help="Nemotron 模型ID")
    parser.add_argument("--num_queries", type=int, default=20, help="评测查询数")
    args = parser.parse_args()

    run_e4(
        nim_api_key=args.nim_api_key,
        llm_api_key=args.llm_api_key,
        model_name=args.model_name,
        num_queries=args.num_queries,
    )
