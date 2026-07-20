# -*- coding: utf-8 -*-
"""E4 续跑脚本：从上次失败的地方继续，更保守的速率控制"""

import sys, os, json, time, re, statistics, requests
sys.path.insert(0, '.')

from bench_utils import (
    load_corpus, load_auto_qa, SimpleTFIDF, rrf_fusion_nexusflow,
    ensure_results_dir, save_json, RESULTS_DIR, create_nemotron_provider, RateLimiter
)
from e4_e2e_task_quality import generate_answer, evaluate_answer

NIM_API_KEY = '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'
LLM_API_KEY = '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'

def main():
    # Load existing results
    existing_path = os.path.join(RESULTS_DIR, "e4_e2e_task_quality.json")
    with open(existing_path, 'r') as f:
        existing = json.load(f)
    
    corpus = load_corpus()
    auto_qa = load_auto_qa()[:15]
    doc_map = {doc["id"]: doc for doc in corpus}
    
    # Find failed queries
    failed_indices = []
    for i, pq in enumerate(existing["per_query"]):
        if "error" in pq or pq["tfidf_score"] == 0:
            failed_indices.append(i)
    
    print(f"Failed queries: {len(failed_indices)} out of 15")
    print(f"Indices: {failed_indices}")
    
    if not failed_indices:
        print("All queries already completed!")
        return
    
    # Build TF-IDF index
    print("Building TF-IDF index...")
    tfidf = SimpleTFIDF()
    for doc in corpus:
        tfidf.index(doc["id"], doc["content"])
    tfidf.build_idf()
    
    # Build BM25 index
    print("Building BM25 index...")
    from nexusflow.memory.vector_memory import BM25Retriever
    bm25 = BM25Retriever(k1=1.5, b=0.75)
    for doc in corpus:
        bm25.index(doc["id"], doc["content"])
    
    # Load existing Nemotron store
    print("Loading Nemotron store...")
    from nexusflow.memory.nemotron_store import NemotronVectorStore
    store_path = os.path.join(RESULTS_DIR, "e4_nemotron_store.json")
    provider = create_nemotron_provider(api_key=NIM_API_KEY, model_name="nvidia/nemotron-3-embed-1b")
    store = NemotronVectorStore(provider, persist_path=store_path)
    # Load the persisted store
    store._load()
    
    # Very conservative rate limiter - 10 RPM for LLM calls
    rate_limiter = RateLimiter(rpm=10)
    
    # Process failed queries
    for idx in failed_indices:
        qa = auto_qa[idx]
        query = qa["query"]
        relevant_id = qa["relevant_doc_id"]
        ground_truth = doc_map.get(relevant_id, {"id": relevant_id, "content": "未知"})
        
        print(f"\n  [{idx+1}/15] Q: {query[:60]}...")
        
        # Extra wait before each query to ensure rate limit is clear
        print(f"    Waiting 15s before processing...")
        time.sleep(15)
        
        try:
            # TF-IDF retrieval
            tfidf_results = tfidf.search(query, top_k=3)
            tfidf_docs = [doc_map.get(doc_id, {"id": doc_id, "content": ""}) for doc_id, _ in tfidf_results]
            
            # Nemotron RRF retrieval
            rate_limiter.wait()
            t_results = tfidf.search(query, top_k=10)
            b_results = bm25.search(query, top_k=10)
            n_results = store.search(query, top_k=10)
            fused = rrf_fusion_nexusflow(t_results, b_results, n_results)
            nemotron_docs = [doc_map.get(doc_id, {"id": doc_id, "content": ""}) for doc_id, _ in fused[:3]]
            
            # Generate TF-IDF answer
            rate_limiter.wait()
            time.sleep(5)  # extra buffer
            print(f"    Generating TF-IDF answer...")
            tfidf_answer = generate_answer(LLM_API_KEY, query, tfidf_docs)
            print(f"    TF-IDF answer: {tfidf_answer[:80]}...")
            
            # Generate Nemotron answer
            rate_limiter.wait()
            time.sleep(5)
            print(f"    Generating Nemotron answer...")
            nemotron_answer = generate_answer(LLM_API_KEY, query, nemotron_docs)
            print(f"    Nemotron answer: {nemotron_answer[:80]}...")
            
            # Evaluate TF-IDF answer
            rate_limiter.wait()
            time.sleep(5)
            print(f"    Evaluating TF-IDF answer...")
            tfidf_score, tfidf_comment = evaluate_answer(LLM_API_KEY, query, tfidf_answer, ground_truth)
            print(f"    TF-IDF score: {tfidf_score}/5 ({tfidf_comment[:40]})")
            
            # Evaluate Nemotron answer
            rate_limiter.wait()
            time.sleep(5)
            print(f"    Evaluating Nemotron answer...")
            nemotron_score, nemotron_comment = evaluate_answer(LLM_API_KEY, query, nemotron_answer, ground_truth)
            print(f"    Nemotron score: {nemotron_score}/5 ({nemotron_comment[:40]})")
            
            # Update result
            existing["per_query"][idx] = {
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
            }
            print(f"    SUCCESS!")
            
        except Exception as e:
            print(f"    [ERROR] {e}")
            # Keep the error entry
            existing["per_query"][idx]["error"] = str(e)
    
    # Recompute aggregates
    all_tfidf_scores = [pq.get("tfidf_score", 0) for pq in existing["per_query"] if "error" not in pq or pq.get("tfidf_score", 0) > 0]
    all_nemotron_scores = [pq.get("nemotron_score", 0) for pq in existing["per_query"] if "error" not in pq or pq.get("nemotron_score", 0) > 0]
    
    # Only count non-zero scores
    valid_results = [pq for pq in existing["per_query"] if pq.get("tfidf_score", 0) > 0 and pq.get("nemotron_score", 0) > 0]
    
    tfidf_scores = [r["tfidf_score"] for r in valid_results]
    nemotron_scores = [r["nemotron_score"] for r in valid_results]
    
    if tfidf_scores:
        tfidf_avg = statistics.mean(tfidf_scores)
        nemotron_avg = statistics.mean(nemotron_scores)
        tfidf_std = statistics.stdev(tfidf_scores) if len(tfidf_scores) > 1 else 0
        nemotron_std = statistics.stdev(nemotron_scores) if len(nemotron_scores) > 1 else 0
        
        score_dist_tfidf = {str(i): tfidf_scores.count(i) for i in range(1, 6)}
        score_dist_nemotron = {str(i): nemotron_scores.count(i) for i in range(1, 6)}
        
        improved = sum(1 for r in valid_results if r["score_diff"] > 0)
        decreased = sum(1 for r in valid_results if r["score_diff"] < 0)
        unchanged = sum(1 for r in valid_results if r["score_diff"] == 0)
        n_valid = len(valid_results)
        
        existing["num_queries"] = n_valid
        existing["tfidf_only"] = {
            "avg_score": round(tfidf_avg, 3),
            "std_score": round(tfidf_std, 3),
            "score_distribution": score_dist_tfidf,
            "scores": tfidf_scores,
        }
        existing["nemotron_rrf"] = {
            "avg_score": round(nemotron_avg, 3),
            "std_score": round(nemotron_std, 3),
            "score_distribution": score_dist_nemotron,
            "scores": nemotron_scores,
        }
        existing["improvement"] = {
            "avg_score_diff": round(nemotron_avg - tfidf_avg, 3),
            "improved_count": improved,
            "decreased_count": decreased,
            "unchanged_count": unchanged,
            "improvement_rate": round(improved / n_valid, 4) if n_valid else 0,
        }
    
    save_json(existing_path, existing)
    print(f"\nResults saved: {existing_path}")
    
    # Print summary
    print("\n" + "=" * 60)
    print("E4 Summary (after resume)")
    print("=" * 60)
    print(f"Valid queries: {len(valid_results)}/15")
    if tfidf_scores:
        print(f"TF-IDF avg:      {tfidf_avg:.3f} ± {tfidf_std:.3f}")
        print(f"Nemotron avg:    {nemotron_avg:.3f} ± {nemotron_std:.3f}")
        print(f"Score diff:      {nemotron_avg - tfidf_avg:+.3f}")
        print(f"Improved: {improved}  Decreased: {decreased}  Unchanged: {unchanged}")

if __name__ == "__main__":
    main()
