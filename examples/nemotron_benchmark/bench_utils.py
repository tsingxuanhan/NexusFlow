# -*- coding: utf-8 -*-
"""
Benchmark 公共工具模块
提供数据加载、指标计算、Nemotron provider 初始化等共享功能。
"""

import json
import os
import sys
import math
import random
import time
import re
from typing import List, Dict, Tuple, Optional

# NexusFlow 仓库根目录
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

BENCH_DIR = os.path.dirname(os.path.abspath(__file__))
DATASET_DIR = os.path.join(BENCH_DIR, "eval_dataset")
RESULTS_DIR = os.path.join(BENCH_DIR, "results")

# 固定随机种子
SEED = 42
random.seed(SEED)


def ensure_results_dir():
    os.makedirs(RESULTS_DIR, exist_ok=True)


def load_json(path: str):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_json(path: str, data):
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def load_corpus() -> List[Dict]:
    return load_json(os.path.join(DATASET_DIR, "corpus.json"))


def load_auto_qa() -> List[Dict]:
    return load_json(os.path.join(DATASET_DIR, "auto_qa.json"))


def load_adversarial() -> List[Dict]:
    return load_json(os.path.join(DATASET_DIR, "adversarial.json"))


def load_skill_tasks() -> List[Dict]:
    return load_json(os.path.join(DATASET_DIR, "skill_tasks.json"))


def create_nemotron_provider(api_key: str = None, model_name: str = "nvidia/nemotron-3-embed-1b"):
    """创建 Nemotron NIM 模式的 embedding provider"""
    from nexusflow.memory.nemotron_provider import NemotronEmbeddingProvider
    provider = NemotronEmbeddingProvider(
        model_name=model_name,
        mode="nim",
        api_key=api_key,
        dimension=2048,
    )
    return provider


# ===================== 检索指标计算 =====================

def compute_recall_at_k(retrieved_ids: List[str], relevant_id: str, k: int = 5) -> float:
    """Recall@k: 相关文档是否出现在 top-k 中"""
    return 1.0 if relevant_id in retrieved_ids[:k] else 0.0


def compute_mrr(retrieved_ids: List[str], relevant_id: str) -> float:
    """MRR: 相关文档的倒数排名"""
    for i, doc_id in enumerate(retrieved_ids):
        if doc_id == relevant_id:
            return 1.0 / (i + 1)
    return 0.0


def compute_ndcg_at_k(retrieved_ids: List[str], relevant_id: str, k: int = 10) -> float:
    """NDCG@k: 归一化折损累积增益（二值相关性）"""
    dcg = 0.0
    for i, doc_id in enumerate(retrieved_ids[:k]):
        rel = 1.0 if doc_id == relevant_id else 0.0
        if rel > 0:
            dcg += rel / math.log2(i + 2)  # i+2 because log2(1)=0

    # IDCG: 相关文档排在第1位
    idcg = 1.0 / math.log2(2)  # = 1.0
    return dcg / idcg if idcg > 0 else 0.0


def compute_metrics(retrieved_ids: List[str], relevant_id: str, k_recall: int = 5, k_ndcg: int = 10) -> Dict[str, float]:
    """计算单个 query 的全部指标"""
    return {
        f"recall@{k_recall}": compute_recall_at_k(retrieved_ids, relevant_id, k_recall),
        "mrr": compute_mrr(retrieved_ids, relevant_id),
        f"ndcg@{k_ndcg}": compute_ndcg_at_k(retrieved_ids, relevant_id, k_ndcg),
    }


def aggregate_metrics(per_query_results: List[Dict[str, float]]) -> Dict[str, float]:
    """聚合多个 query 的指标平均值"""
    if not per_query_results:
        return {"recall@5": 0.0, "mrr": 0.0, "ndcg@10": 0.0}
    keys = per_query_results[0].keys()
    return {k: sum(r[k] for r in per_query_results) / len(per_query_results) for k in keys}


# ===================== 简易 TF-IDF =====================

class SimpleTFIDF:
    """简易 TF-IDF 检索器（不依赖 NexusFlow，用于 E1 对比）"""

    def __init__(self):
        self.doc_ids: List[str] = []
        self.doc_tokens: Dict[str, List[str]] = {}
        self.tf: Dict[str, Dict[str, float]] = {}
        self.idf: Dict[str, float] = {}
        self.doc_norms: Dict[str, float] = {}

    def _tokenize(self, text: str) -> List[str]:
        text = text.lower()
        tokens = re.findall(r'[\w\u4e00-\u9fff]+', text)
        # 对中文进一步按字切分
        result = []
        for t in tokens:
            result.append(t)
            if any('\u4e00' <= c <= '\u9fff' for c in t):
                # 中文单字也加入
                for c in t:
                    if '\u4e00' <= c <= '\u9fff':
                        result.append(c)
        return result

    def index(self, doc_id: str, content: str):
        tokens = self._tokenize(content)
        self.doc_ids.append(doc_id)
        self.doc_tokens[doc_id] = tokens
        tf = {}
        for t in tokens:
            tf[t] = tf.get(t, 0) + 1
        self.tf[doc_id] = tf

    def build_idf(self):
        N = len(self.doc_ids)
        all_terms = set()
        for tf in self.tf.values():
            all_terms.update(tf.keys())
        for term in all_terms:
            df = sum(1 for d in self.tf.values() if term in d)
            self.idf[term] = math.log((N + 1) / (df + 1)) + 1

        # 计算文档向量范数
        for doc_id in self.doc_ids:
            norm = 0.0
            for term, freq in self.tf[doc_id].items():
                weight = freq * self.idf.get(term, 0)
                norm += weight * weight
            self.doc_norms[doc_id] = math.sqrt(norm) if norm > 0 else 1.0

    def search(self, query: str, top_k: int = 5) -> List[Tuple[str, float]]:
        query_tokens = self._tokenize(query)
        query_tf = {}
        for t in query_tokens:
            query_tf[t] = query_tf.get(t, 0) + 1

        scores = {}
        for doc_id in self.doc_ids:
            score = 0.0
            for term, qf in query_tf.items():
                if term in self.tf[doc_id] and term in self.idf:
                    tf = self.tf[doc_id][term]
                    score += qf * tf * self.idf[term] * self.idf[term]
            if self.doc_norms[doc_id] > 0:
                score /= self.doc_norms[doc_id]
            scores[doc_id] = score

        ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        return ranked[:top_k]


# ===================== RRF 融合 =====================

def rrf_fusion(*result_lists: List[Tuple[str, float]], k: int = 60) -> List[Tuple[str, float]]:
    """多路 RRF 融合"""
    fused: Dict[str, float] = {}
    for results in result_lists:
        for rank, (doc_id, _) in enumerate(results):
            fused[doc_id] = fused.get(doc_id, 0) + 1.0 / (k + rank + 1)
    return sorted(fused.items(), key=lambda x: x[1], reverse=True)


def rrf_fusion_nexusflow(*result_lists: List[Tuple[str, float]], k: int = 60) -> List[Tuple[str, float]]:
    """使用 NexusFlow 的 reciprocal_rank_fusion 进行两两融合"""
    from nexusflow.memory.vector_memory import reciprocal_rank_fusion
    if len(result_lists) == 1:
        return list(result_lists[0])
    elif len(result_lists) == 2:
        return reciprocal_rank_fusion(list(result_lists[0]), list(result_lists[1]), k)
    else:
        # 先融合前两路，再逐步融合后续
        fused = reciprocal_rank_fusion(list(result_lists[0]), list(result_lists[1]), k)
        for i in range(2, len(result_lists)):
            fused = reciprocal_rank_fusion(fused, list(result_lists[i]), k)
        return fused


# ===================== 限速控制 =====================

class RateLimiter:
    """简单的速率限制器，控制每分钟请求数"""

    def __init__(self, rpm: int = 40):
        self.min_interval = 60.0 / rpm  # 秒
        self.last_call = 0.0

    def wait(self):
        now = time.time()
        elapsed = now - self.last_call
        if elapsed < self.min_interval:
            time.sleep(self.min_interval - elapsed)
        self.last_call = time.time()


# ===================== 报告工具 =====================

def format_metrics_table(results: Dict[str, Dict[str, float]]) -> str:
    """将指标结果格式化为 Markdown 表格"""
    if not results:
        return "无数据"

    headers = ["方法"] + list(next(iter(results.values())).keys())
    lines = ["| " + " | ".join(headers) + " |", "|" + "|".join(["---"] * len(headers)) + "|"]
    for method, metrics in results.items():
        row = [method] + [f"{v:.4f}" for v in metrics.values()]
        lines.append("| " + " | ".join(row) + " |")
    return "\n".join(lines)


def format_latency_table(results: Dict[str, Dict[str, float]]) -> str:
    """将延迟结果格式化为 Markdown 表格"""
    if not results:
        return "无数据"
    headers = ["方法"] + list(next(iter(results.values())).keys())
    lines = ["| " + " | ".join(headers) + " |", "|" + "|".join(["---"] * len(headers)) + "|"]
    for method, metrics in results.items():
        row = [method] + [f"{v:.2f}" for v in metrics.values()]
        lines.append("| " + " | ".join(row) + " |")
    return "\n".join(lines)
