# -*- coding: utf-8 -*-
"""
adaptive_context_manager 模块单元测试
覆盖: _cosine_similarity / _simple_hash_embed 数学正确性,
      LocalContextWindow.truncate_messages 截断逻辑,
      GlobalMemoryPool.add / semantic_search / snapshot。
所有测试脱离 LLM 和 chromadb。
"""
import math
import pytest

from nexusflow.core.adaptive_context_manager import (
    _cosine_similarity,
    _simple_hash_embed,
    LocalContextWindow,
    GlobalMemoryPool,
    MemoryItem,
    RetrievalQuery,
)


# ---------------------------------------------------------------------------
# _cosine_similarity 数学正确性
# ---------------------------------------------------------------------------

def test_cosine_identical_vectors():
    v = [1.0, 2.0, 3.0]
    assert abs(_cosine_similarity(v, v) - 1.0) < 1e-6


def test_cosine_orthogonal_vectors():
    a = [1.0, 0.0]
    b = [0.0, 1.0]
    assert abs(_cosine_similarity(a, b)) < 1e-6


def test_cosine_opposite_vectors():
    a = [1.0, 0.0]
    b = [-1.0, 0.0]
    assert abs(_cosine_similarity(a, b) - (-1.0)) < 1e-6


def test_cosine_zero_vector():
    a = [0.0, 0.0]
    b = [1.0, 2.0]
    assert _cosine_similarity(a, b) == 0.0


def test_cosine_known_value():
    # cos(45°) = √2/2 ≈ 0.7071
    a = [1.0, 0.0]
    b = [1.0, 1.0]
    assert abs(_cosine_similarity(a, b) - math.sqrt(2) / 2) < 1e-6


def test_cosine_symmetry():
    a = [1.0, 2.0, 3.0]
    b = [4.0, 5.0, 6.0]
    assert abs(_cosine_similarity(a, b) - _cosine_similarity(b, a)) < 1e-6


# ---------------------------------------------------------------------------
# _simple_hash_embed
# ---------------------------------------------------------------------------

def test_hash_embed_dimension():
    vec = _simple_hash_embed("hello world", dim=128)
    assert len(vec) == 128


def test_hash_embed_normalized():
    vec = _simple_hash_embed("test string", dim=64)
    norm = math.sqrt(sum(v * v for v in vec))
    assert abs(norm - 1.0) < 1e-6


def test_hash_embed_deterministic():
    v1 = _simple_hash_embed("same text", dim=64)
    v2 = _simple_hash_embed("same text", dim=64)
    assert v1 == v2


def test_hash_embed_different_texts_differ():
    v1 = _simple_hash_embed("apple", dim=64)
    v2 = _simple_hash_embed("banana", dim=64)
    assert v1 != v2


def test_hash_embed_empty_string():
    vec = _simple_hash_embed("", dim=32)
    # 空字符串没有 n-gram，norm=0 → 返回零向量
    assert all(v == 0.0 for v in vec)


def test_hash_embed_custom_dim():
    vec = _simple_hash_embed("test", dim=256)
    assert len(vec) == 256


# ---------------------------------------------------------------------------
# LocalContextWindow — truncate_messages
# ---------------------------------------------------------------------------

def _make_msgs(n, content_len=50):
    """生成 n 条消息"""
    return [{"role": "user", "content": f"msg{i}" + "x" * content_len} for i in range(n)]


def test_truncate_no_truncation_needed():
    window = LocalContextWindow(max_tokens=100000)
    msgs = _make_msgs(3)
    result = window.truncate_messages(msgs)
    assert len(result) == 3


def test_truncate_recency_strategy():
    # 每条消息约 50*1.3 = 65 token (纯ASCII)，设 max_tokens 使只能容纳2条
    window = LocalContextWindow(max_tokens=200, strategy="recency")
    msgs = _make_msgs(10, content_len=50)
    result = window.truncate_messages(msgs)
    # 应该被截断
    non_system = [m for m in result if m["role"] != "system"]
    assert len(non_system) < 10


def test_truncate_preserves_system_messages():
    window = LocalContextWindow(max_tokens=100, strategy="recency")
    msgs = [{"role": "system", "content": "system prompt"}] + _make_msgs(20, content_len=50)
    result = window.truncate_messages(msgs)
    system_msgs = [m for m in result if m["role"] == "system"]
    # 至少有原始 system 消息 + 截断通知
    assert len(system_msgs) >= 1


def test_truncate_relevance_strategy():
    window = LocalContextWindow(max_tokens=300, strategy="relevance")
    msgs = _make_msgs(10, content_len=80)
    result = window.truncate_messages(msgs, query="msg0")
    non_system = [m for m in result if m["role"] != "system"]
    assert len(non_system) < 10


def test_truncate_mixed_strategy():
    window = LocalContextWindow(max_tokens=300, strategy="mixed", keep_recent=2)
    msgs = _make_msgs(10, content_len=80)
    result = window.truncate_messages(msgs, query="msg0")
    non_system = [m for m in result if m["role"] != "system"]
    assert len(non_system) < 10


def test_truncate_stats_updated():
    window = LocalContextWindow(max_tokens=100, strategy="recency")
    msgs = _make_msgs(20, content_len=50)
    window.truncate_messages(msgs)
    stats = window.get_stats()
    assert stats["total_truncations"] >= 1
    assert stats["total_messages_truncated"] > 0


def test_truncate_empty_messages():
    window = LocalContextWindow(max_tokens=100)
    result = window.truncate_messages([])
    assert result == []


def test_window_resize_adaptive():
    window = LocalContextWindow(max_tokens=4096, adaptive=True, min_window=512, max_window=8192)
    window.resize(1024)
    assert window.max_tokens == 1024
    window.resize(100)  # below min
    assert window.max_tokens == 512
    window.resize(20000)  # above max
    assert window.max_tokens == 8192


def test_window_resize_not_adaptive():
    window = LocalContextWindow(max_tokens=4096, adaptive=False)
    window.resize(1024)
    assert window.max_tokens == 4096  # 不变


# ---------------------------------------------------------------------------
# GlobalMemoryPool — add / semantic_search / snapshot
# ---------------------------------------------------------------------------

def test_memory_pool_add():
    pool = GlobalMemoryPool()
    item = pool.add("conclusion", "agent1", "结论A", importance=0.8)
    assert item.content == "结论A"
    assert item.agent_id == "agent1"
    assert item.memory_type == "conclusion"
    assert item.importance == 0.8
    assert len(item.embedding) == pool.embedding_dim
    assert pool.total_adds == 1


def test_memory_pool_add_different_types():
    pool = GlobalMemoryPool()
    pool.add("conclusion", "a1", "c1")
    pool.add("hypothesis", "a1", "h1")
    pool.add("contradiction", "a1", "ct1")
    pool.add("evidence", "a1", "e1")
    assert len(pool.conclusions) == 1
    assert len(pool.hypotheses) == 1
    assert len(pool.contradictions) == 1
    assert len(pool.evidence) == 1
    assert len(pool._all_items) == 4


def test_memory_pool_add_unknown_type_defaults_to_evidence():
    pool = GlobalMemoryPool()
    pool.add("unknown_type", "a1", "content")
    assert len(pool.evidence) == 1


def test_memory_pool_add_conclusion_from_object():
    """测试 add_conclusion 接收 IntermediateConclusion 对象"""
    from nexusflow.core.cognitive_division_engine import IntermediateConclusion
    pool = GlobalMemoryPool()
    ic = IntermediateConclusion(agent_id="a1", conclusion="结论文本", confidence=0.9)
    item = pool.add_conclusion("a1", ic)
    assert item.content == "结论文本"
    assert item.importance == 0.9


def test_memory_pool_add_conclusion_from_string():
    pool = GlobalMemoryPool()
    item = pool.add_conclusion("a1", "纯字符串结论")
    assert item.content == "纯字符串结论"
    assert item.importance == 0.5


def test_memory_pool_semantic_search():
    pool = GlobalMemoryPool()
    pool.add("conclusion", "a1", "机器学习模型训练方法")
    pool.add("conclusion", "a2", "深度学习神经网络架构")
    pool.add("conclusion", "a3", "天气预报数据分析")
    results = pool.semantic_search("机器学习", top_k=2)
    assert len(results) == 2
    assert all(isinstance(r, MemoryItem) for r in results)


def test_memory_pool_semantic_search_empty():
    pool = GlobalMemoryPool()
    results = pool.semantic_search("anything")
    assert results == []


def test_memory_pool_semantic_search_top_k():
    pool = GlobalMemoryPool()
    for i in range(20):
        pool.add("conclusion", f"a{i}", f"内容{i}")
    results = pool.semantic_search("内容", top_k=5)
    assert len(results) == 5


def test_memory_pool_snapshot():
    pool = GlobalMemoryPool()
    pool.add("conclusion", "a1", "c1")
    pool.add("hypothesis", "a2", "h1")
    snap = pool.snapshot()
    assert snap["total_items"] == 2
    assert snap["conclusions"] == 1
    assert snap["hypotheses"] == 1
    assert "a1" in snap["agent_ids"]
    assert "a2" in snap["agent_ids"]
    assert "timestamp" in snap


def test_memory_pool_get_all_items():
    pool = GlobalMemoryPool()
    pool.add("conclusion", "a1", "c1")
    pool.add("hypothesis", "a1", "h1")
    all_items = pool.get_all_items()
    assert len(all_items) == 2
    conclusions = pool.get_all_items("conclusion")
    assert len(conclusions) == 1


def test_memory_pool_get_agent_items():
    pool = GlobalMemoryPool()
    pool.add("conclusion", "a1", "c1")
    pool.add("conclusion", "a2", "c2")
    pool.add("hypothesis", "a1", "h1")
    a1_items = pool.get_agent_items("a1")
    assert len(a1_items) == 2


def test_memory_pool_stats():
    pool = GlobalMemoryPool()
    pool.add("conclusion", "a1", "c1")
    pool.semantic_search("test")
    stats = pool.get_stats()
    assert stats["total_items"] == 1
    assert stats["total_adds"] == 1
    assert stats["total_searches"] == 1
    assert stats["backing_store"] is False


def test_memory_pool_with_backing_store():
    """测试 backing_store 回调"""
    class FakeStore:
        def __init__(self):
            self.stored = []
        def store(self, content, source, domain, importance):
            self.stored.append({"content": content, "source": source})

    bs = FakeStore()
    pool = GlobalMemoryPool(backing_store=bs)
    pool.add("conclusion", "a1", "test content")
    assert len(bs.stored) == 1
    assert bs.stored[0]["content"] == "test content"


# ---------------------------------------------------------------------------
# RetrievalQuery dataclass
# ---------------------------------------------------------------------------

def test_retrieval_query_defaults():
    rq = RetrievalQuery(requester_id="a1", target_description="find data")
    assert rq.top_k == 5
    assert rq.constraints == {}
    assert rq.purpose == ""


# ---------------------------------------------------------------------------
# MemoryItem dataclass
# ---------------------------------------------------------------------------

def test_memory_item_to_dict():
    item = MemoryItem(content="test", agent_id="a1", memory_type="conclusion",
                      metadata={"k": "v"}, importance=0.7)
    d = item.to_dict()
    assert d["content"] == "test"
    assert d["agent_id"] == "a1"
    assert d["importance"] == 0.7
    assert "embedding" not in d  # to_dict 不导出 embedding
