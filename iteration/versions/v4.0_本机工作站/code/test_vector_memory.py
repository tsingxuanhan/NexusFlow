#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
验证 N-gram TF-IDF 语义嵌入的质量

测试场景：
1. 添加 "nano SiO2 supersulfated cement"
2. 添加 "LC3 limestone calcined clay"  
3. 添加 "deep learning optimization"
4. 搜索 "silica nanoparticle concrete" 应该返回第一条
5. 搜索 "machine learning" 应该返回第三条
6. 验证持久化：save -> reload -> search
"""

import sys
import os

# 添加 xuanshu-agents 到路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from vector_memory import (
    NGramTFIDFProvider, 
    PersistentVectorStore, 
    InMemoryVectorStore,
    cosine_similarity
)


def test_ngram_semantic_quality():
    """测试 N-gram 语义质量"""
    print("=" * 60)
    print("Test 1: N-gram 语义质量测试")
    print("=" * 60)
    
    provider = NGramTFIDFProvider(dimension=5000)
    
    # 测试文本
    texts = [
        "nano SiO2 supersulfated cement",
        "LC3 limestone calcined clay",
        "deep learning optimization"
    ]
    
    # 搜索查询
    queries = [
        ("silica nanoparticle concrete", 0),  # 应该匹配第0条
        ("machine learning", 2),  # 应该匹配第2条
        ("calcined clay cement", 1),  # 应该匹配第1条
    ]
    
    # 先添加所有文本更新 IDF
    provider.update_idf(texts)
    
    # 生成嵌入
    embeddings = [provider.embed(t) for t in texts]
    
    print("\n[文本列表]")
    for i, t in enumerate(texts):
        print(f"  {i}: {t}")
    
    print("\n[搜索测试]")
    all_passed = True
    for query, expected_idx in queries:
        query_emb = provider.embed(query)
        
        # 计算与所有文本的相似度
        scores = [(i, cosine_similarity(query_emb, emb)) for i, emb in enumerate(embeddings)]
        scores.sort(key=lambda x: x[1], reverse=True)
        
        top_match = scores[0][0]
        status = "✓ PASS" if top_match == expected_idx else "✗ FAIL"
        if top_match != expected_idx:
            all_passed = False
        
        print(f"\n  查询: '{query}'")
        print(f"  期望匹配: {expected_idx} ({texts[expected_idx]})")
        print(f"  实际匹配: {top_match} ({texts[top_match]})")
        print(f"  状态: {status}")
        print(f"  相似度: {scores[0][1]:.4f}")
    
    return all_passed


def test_char_ngram_similarity():
    """测试字符 n-gram 对子词相似性的捕获"""
    print("\n" + "=" * 60)
    print("Test 2: 字符 n-gram 子词相似性测试")
    print("=" * 60)
    
    provider = NGramTFIDFProvider(dimension=5000)
    
    # 测试对
    test_pairs = [
        ("SiO2", "silica"),  # 应该有一定相似度（共享 char n-gram）
        ("nano", "nanoparticle"),
        ("cement", "concrete"),
    ]
    
    print("\n[字符 n-gram 相似度]")
    provider.update_idf([t for pair in test_pairs for t in pair])
    
    for t1, t2 in test_pairs:
        emb1 = provider.embed(t1)
        emb2 = provider.embed(t2)
        sim = cosine_similarity(emb1, emb2)
        
        # 分析共享的 char n-gram
        tokens1 = provider._tokenize(t1)
        tokens2 = provider._tokenize(t2)
        ngrams1 = provider._get_ngrams(tokens1)
        ngrams2 = provider._get_ngrams(tokens2)
        shared = set(ngrams1.keys()) & set(ngrams2.keys())
        
        print(f"\n  '{t1}' vs '{t2}'")
        print(f"  相似度: {sim:.4f}")
        print(f"  共享 n-grams ({len(shared)}): {list(shared)[:5]}")
    
    return True


def test_persistent_vector_store():
    """测试持久化向量存储"""
    print("\n" + "=" * 60)
    print("Test 3: 持久化向量存储测试")
    print("=" * 60)
    
    import tempfile
    import shutil
    
    # 使用临时目录
    tmpdir = tempfile.mkdtemp(prefix="vm_test_")
    persist_path = os.path.join(tmpdir, "vector_memory.json")
    
    try:
        # 创建第一个实例并添加数据
        provider = NGramTFIDFProvider(dimension=5000)
        store1 = PersistentVectorStore(provider, persist_path=persist_path, auto_save_interval=999)
        
        entries = [
            "nano silica cement hydration",
            "machine learning neural networks",
            "greenhouse gas emissions reduction"
        ]
        
        print(f"\n[添加 {len(entries)} 条记忆]")
        for content in entries:
            entry = store1.embedding_provider.embed(content)
            from vector_memory import MemoryEntry
            mem_entry = MemoryEntry(content=content, embedding=entry)
            store1.add([mem_entry])
            print(f"  + {content[:50]}...")
        
        print(f"  当前条目数: {store1.count()}")
        
        # 手动保存
        store1.save()
        print(f"  已保存到: {persist_path}")
        
        # 创建第二个实例（应该自动加载）
        provider2 = NGramTFIDFProvider(dimension=5000)
        store2 = PersistentVectorStore(provider2, persist_path=persist_path)
        
        print(f"\n[重新加载]")
        print(f"  加载条目数: {store2.count()}")
        
        # 验证数据一致性
        if store2.count() == len(entries):
            print("  ✓ 数据一致性检查通过")
        else:
            print("  ✗ 数据一致性检查失败")
            return False
        
        # 搜索测试
        query = "silica nanoparticle concrete"
        results1 = store1.search(query, top_k=1)
        results2 = store2.search(query, top_k=1)
        
        print(f"\n[搜索一致性测试]")
        print(f"  查询: '{query}'")
        print(f"  Store1 结果: {results1[0].entry.content if results1 else 'None'}")
        print(f"  Store2 结果: {results2[0].entry.content if results2 else 'None'}")
        
        if results1 and results2 and results1[0].entry.content == results2[0].entry.content:
            print("  ✓ 搜索一致性检查通过")
            return True
        else:
            print("  ✗ 搜索一致性检查失败")
            return False
        
    finally:
        # 清理临时目录
        shutil.rmtree(tmpdir, ignore_errors=True)


def test_vs_simple_provider():
    """对比 N-gram vs Simple 嵌入质量"""
    print("\n" + "=" * 60)
    print("Test 4: N-gram vs Simple 嵌入对比")
    print("=" * 60)
    
    from vector_memory import SimpleEmbeddingProvider
    
    texts = [
        "nano SiO2 supersulfated cement",
        "LC3 limestone calcined clay",
        "deep learning optimization"
    ]
    
    queries = [
        ("silica nanoparticle concrete", 0),  # 应该匹配第0条
        ("machine learning", 2),  # 应该匹配第2条
    ]
    
    print("\n[对比结果]")
    print(f"{'查询':<35} {'Simple':<30} {'N-gram'}")
    print("-" * 90)
    
    for query, expected_idx in queries:
        # Simple
        simple_provider = SimpleEmbeddingProvider()
        simple_emb = simple_provider.embed(query)
        simple_scores = [(i, cosine_similarity(simple_emb, simple_provider.embed(t))) for i, t in enumerate(texts)]
        simple_scores.sort(key=lambda x: x[1], reverse=True)
        simple_match = texts[simple_scores[0][0]]
        
        # N-gram
        ngram_provider = NGramTFIDFProvider(dimension=5000)
        ngram_provider.update_idf(texts)
        ngram_emb = ngram_provider.embed(query)
        ngram_scores = [(i, cosine_similarity(ngram_emb, ngram_provider.embed(t))) for i, t in enumerate(texts)]
        ngram_scores.sort(key=lambda x: x[1], reverse=True)
        ngram_match = texts[ngram_scores[0][0]]
        
        expected = texts[expected_idx]
        simple_ok = "✓" if simple_match == expected else "✗"
        ngram_ok = "✓" if ngram_match == expected else "✗"
        
        print(f"'{query[:33]}...'")
        print(f"  期望: {expected[:28]}...")
        print(f"  Simple: {simple_match[:28]}... {simple_ok}")
        print(f"  N-gram: {ngram_match[:28]}... {ngram_ok}")
        print()


def main():
    print("=" * 60)
    print("xuanshu-agents 向量记忆系统升级验证")
    print("=" * 60)
    
    results = []
    
    # 测试1: 语义质量
    try:
        r1 = test_ngram_semantic_quality()
        results.append(("语义质量测试", r1))
    except Exception as e:
        print(f"\n✗ 语义质量测试失败: {e}")
        results.append(("语义质量测试", False))
    
    # 测试2: 字符 n-gram 相似性
    try:
        r2 = test_char_ngram_similarity()
        results.append(("字符n-gram测试", r2))
    except Exception as e:
        print(f"\n✗ 字符n-gram测试失败: {e}")
        results.append(("字符n-gram测试", False))
    
    # 测试3: 持久化
    try:
        r3 = test_persistent_vector_store()
        results.append(("持久化测试", r3))
    except Exception as e:
        print(f"\n✗ 持久化测试失败: {e}")
        import traceback
        traceback.print_exc()
        results.append(("持久化测试", False))
    
    # 测试4: 对比 Simple
    try:
        test_vs_simple_provider()
        results.append(("对比测试", True))
    except Exception as e:
        print(f"\n✗ 对比测试失败: {e}")
        results.append(("对比测试", False))
    
    # 汇总
    print("\n" + "=" * 60)
    print("测试结果汇总")
    print("=" * 60)
    for name, passed in results:
        status = "✓ PASS" if passed else "✗ FAIL"
        print(f"  {name:<20} {status}")
    
    all_passed = all(r for _, r in results)
    print()
    if all_passed:
        print("🎉 所有测试通过！")
    else:
        print("⚠️  部分测试失败，请检查上述输出")
    
    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())
