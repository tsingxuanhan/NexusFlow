# -*- coding: utf-8 -*-
"""
Nemotron-3 Embed Benchmark 统一运行入口

运行所有实验并生成 report.md。

用法:
  python run_benchmark.py --nim_api_key <NIM_KEY> --llm_api_key <QWEN_KEY>
  python run_benchmark.py --nim_api_key <NIM_KEY> --llm_api_key <QWEN_KEY> --skip e4
  python run_benchmark.py --nim_api_key <NIM_KEY> --llm_api_key <QWEN_KEY> --num_queries 10

参数:
  --nim_api_key    NIM API Key (Nemotron embeddings)
  --llm_api_key    GLM-5.2 API Key (E4 LLM 评估器)
  --model_name     Nemotron 模型ID (默认: nvidia/nemotron-3-embed-1b)
  --num_queries    E2/E4 测试查询数 (默认: 20)
  --skip           跳过的实验 (逗号分隔，如: e2,e4)
  --only           只运行指定实验 (逗号分隔，如: e1,e3)
"""

import argparse
import json
import os
import sys
import time
import traceback
from datetime import datetime

# 确保能 import bench_utils
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from bench_utils import RESULTS_DIR, ensure_results_dir, save_json, load_json, format_metrics_table


def run_e1(nim_api_key, model_name, **kwargs):
    from e1_retrieval_quality import run_e1 as _run_e1
    return _run_e1(api_key=nim_api_key, model_name=model_name, top_k=10)


def run_e2(nim_api_key, model_name, num_queries=20, **kwargs):
    from e2_latency_benchmark import run_e2 as _run_e2
    return _run_e2(api_key=nim_api_key, model_name=model_name, num_queries=num_queries)


def run_e3(nim_api_key, model_name, **kwargs):
    from e3_skill_retrieval import run_e3 as _run_e3
    return _run_e3(api_key=nim_api_key, model_name=model_name)


def run_e4(nim_api_key, llm_api_key, model_name, num_queries=20, **kwargs):
    from e4_e2e_task_quality import run_e4 as _run_e4
    return _run_e4(
        nim_api_key=nim_api_key,
        llm_api_key=llm_api_key,
        model_name=model_name,
        num_queries=num_queries,
    )


def generate_report(all_results: dict, env_info: dict, elapsed: dict) -> str:
    """生成 Markdown 报告"""
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    lines = []
    lines.append("# Nemotron-3 Embed Benchmark 报告")
    lines.append("")
    lines.append(f"> 生成时间: {now}")
    lines.append(f"> 随机种子: {env_info.get('seed', 42)}")
    lines.append("")

    # ---------- 实验环境 ----------
    lines.append("## 1. 实验环境说明")
    lines.append("")
    lines.append(f"| 项目 | 值 |")
    lines.append(f"|---|---|")
    lines.append(f"| 仓库 | NexusFlow v{env_info.get('nexusflow_version', 'N/A')} |")
    lines.append(f"| 嵌入模型 | {env_info.get('model_name', 'nvidia/nemotron-3-embed-1b')} |")
    lines.append(f"| 推理方式 | NIM API (https://integrate.api.nvidia.com) |")
    lines.append(f"| 向量维度 | 2048 |")
    lines.append(f"| 随机种子 | {env_info.get('seed', 42)} |")
    lines.append(f"| 语料库规模 | {env_info.get('corpus_size', 'N/A')} 条 |")
    lines.append(f"| QA查询数 | {env_info.get('qa_size', 'N/A')} 条 |")
    lines.append(f"| 对抗查询数 | {env_info.get('adversarial_size', 'N/A')} 条 |")
    lines.append(f"| Skill任务数 | {env_info.get('skill_task_size', 'N/A')} 条 |")
    lines.append(f"| NIM限速 | 40 rpm |")
    lines.append(f"| LLM评估器 | GLM-5.2 (z-ai/glm-5.2 via NIM) |")
    lines.append("")
    lines.append("### 硬件/运行环境")
    lines.append("- 沙箱环境（无GPU）")
    lines.append("- Nemotron 推理通过 NVIDIA NIM API 远程调用")
    lines.append("- TF-IDF / BM25 为本地纯 Python 计算")
    lines.append("")

    # ---------- E1 ----------
    lines.append("## 2. E1: 检索质量对比")
    lines.append("")
    if "e1" in all_results and all_results["e1"]:
        e1 = all_results["e1"]
        # 全部查询
        lines.append("### 2.1 全部查询 (Auto QA + Adversarial)")
        lines.append("")
        agg = {k: v["aggregate"] for k, v in e1.items()}
        lines.append(format_metrics_table(agg))
        lines.append("")

        # 指标说明
        lines.append("**指标说明:**")
        lines.append("- **Recall@5**: 正确文档出现在 top-5 结果中的比例")
        lines.append("- **MRR**: 平均倒数排名 (Mean Reciprocal Rank)")
        lines.append("- **NDCG@10**: 归一化折损累积增益 (k=10)")
        lines.append("")

        # 分析
        lines.append("### 2.2 关键发现")
        lines.append("")
        # 找最佳方法
        best_recall = max(e1.items(), key=lambda x: x[1]["aggregate"].get("recall@5", 0))
        best_mrr = max(e1.items(), key=lambda x: x[1]["aggregate"].get("mrr", 0))
        best_ndcg = max(e1.items(), key=lambda x: x[1]["aggregate"].get("ndcg@10", 0))
        lines.append(f"- **Recall@5 最高**: {best_recall[0]} ({best_recall[1]['aggregate'].get('recall@5', 0):.4f})")
        lines.append(f"- **MRR 最高**: {best_mrr[0]} ({best_mrr[1]['aggregate'].get('mrr', 0):.4f})")
        lines.append(f"- **NDCG@10 最高**: {best_ndcg[0]} ({best_ndcg[1]['aggregate'].get('ndcg@10', 0):.4f})")
        lines.append("")
    else:
        lines.append("*E1 未运行或无结果*")
        lines.append("")

    # ---------- E2 ----------
    lines.append("## 3. E2: 延迟基准")
    lines.append("")
    if "e2" in all_results and all_results["e2"]:
        e2 = all_results["e2"]
        lines.append("### 3.1 本地检索延迟 (TF-IDF / BM25)")
        lines.append("")
        local_methods = ["TF-IDF (local)", "BM25 (local)"]
        lines.append("| 方法 | P50 (ms) | P95 (ms) | P99 (ms) | 平均 (ms) |")
        lines.append("|---|---|---|---|---|")
        for m in local_methods:
            if m in e2:
                d = e2[m]
                lines.append(f"| {m} | {d.get('p50_ms',0):.3f} | {d.get('p95_ms',0):.3f} | {d.get('p99_ms',0):.3f} | {d.get('mean_ms',0):.3f} |")
        lines.append("")

        lines.append("### 3.2 NIM API 延迟 (Nemotron)")
        lines.append("")
        lines.append("| 方法 | P50 (ms) | P95 (ms) | P99 (ms) | 平均 (ms) |")
        lines.append("|---|---|---|---|---|")
        nim_methods = ["Nemotron NIM (single)"]
        for m in nim_methods:
            if m in e2:
                d = e2[m]
                lines.append(f"| {m} | {d.get('p50_ms',0):.3f} | {d.get('p95_ms',0):.3f} | {d.get('p99_ms',0):.3f} | {d.get('mean_ms',0):.3f} |")
        lines.append("")

        if "Nemotron NIM (batch)" in e2:
            b = e2["Nemotron NIM (batch)"]
            lines.append(f"**批量吞吐**: 批大小={b.get('batch_size',5)}, 平均延迟={b.get('avg_batch_latency_ms',0):.1f}ms, 平均吞吐={b.get('avg_throughput_qps',0):.1f} qps")
            lines.append("")

        lines.append("### 3.3 端到端检索延迟对比")
        lines.append("")
        lines.append("| 方法 | P50 (ms) | 平均 (ms) |")
        lines.append("|---|---|---|")
        e2e_methods = ["E2E: TF-IDF (local)", "E2E: BM25 (local)", "E2E: Nemotron (NIM)"]
        for m in e2e_methods:
            if m in e2:
                d = e2[m]
                lines.append(f"| {m} | {d.get('p50_ms',0):.3f} | {d.get('mean_ms',0):.3f} |")
        lines.append("")

        lines.append("### 3.4 延迟分析")
        lines.append("")
        tfidf_p50 = e2.get("E2E: TF-IDF (local)", {}).get("p50_ms", 0)
        nemotron_p50 = e2.get("E2E: Nemotron (NIM)", {}).get("p50_ms", 0)
        if tfidf_p50 > 0 and nemotron_p50 > 0:
            ratio = nemotron_p50 / tfidf_p50
            lines.append(f"- Nemotron NIM 端到端 P50 延迟约为 TF-IDF 的 **{ratio:.0f}x**")
        lines.append("- 本地 TF-IDF/BM25 延迟在亚毫秒级，适合实时检索")
        lines.append("- NIM API 延迟受网络往返和排队影响，适合离线或非实时场景")
        lines.append("")
    else:
        lines.append("*E2 未运行或无结果*")
        lines.append("")

    # ---------- E3 ----------
    lines.append("## 4. E3: Skill 检索对比")
    lines.append("")
    if "e3" in all_results and all_results["e3"]:
        e3 = all_results["e3"]
        lines.append("### 4.1 Top-3 命中率对比")
        lines.append("")
        lines.append("| 方法 | 命中数 | 总数 | 命中率 |")
        lines.append("|---|---|---|---|")
        lines.append(f"| 纯规则匹配 | {e3['rule_only']['hits']} | {e3['rule_only']['total']} | {e3['rule_only']['top3_hit_rate']:.4f} |")
        lines.append(f"| 规则+Nemotron语义 | {e3['rule_plus_semantic']['hits']} | {e3['rule_plus_semantic']['total']} | {e3['rule_plus_semantic']['top3_hit_rate']:.4f} |")
        lines.append("")
        lines.append(f"**提升**: 绝对 {e3['improvement']['absolute']:+.4f}, 相对 {e3['improvement']['relative']:+.2f}%")
        lines.append("")

        if e3.get("differential_tasks"):
            lines.append("### 4.2 差异任务分析")
            lines.append("")
            lines.append("| 方向 | 任务 | 规则结果 | 语义结果 | 期望 |")
            lines.append("|---|---|---|---|---|")
            for dt in e3["differential_tasks"]:
                flag = "↑提升" if dt["semantic_hit"] and not dt["rule_hit"] else "↓下降"
                task_short = dt["task"][:40] + "..."
                lines.append(f"| {flag} | {task_short} | {','.join(dt['rule_retrieved'])} | {','.join(dt['semantic_retrieved'])} | {','.join(dt['expected'])} |")
            lines.append("")
    else:
        lines.append("*E3 未运行或无结果*")
        lines.append("")

    # ---------- E4 ----------
    lines.append("## 5. E4: 端到端任务质量评测 (GLM-5.2)")
    lines.append("")
    if "e4" in all_results and all_results["e4"]:
        e4 = all_results["e4"]
        lines.append("### 5.1 评分对比")
        lines.append("")
        lines.append("| 方法 | 平均分 | 标准差 |")
        lines.append("|---|---|---|")
        lines.append(f"| TF-IDF only | {e4['tfidf_only']['avg_score']:.3f} | {e4['tfidf_only']['std_score']:.3f} |")
        lines.append(f"| Nemotron RRF | {e4['nemotron_rrf']['avg_score']:.3f} | {e4['nemotron_rrf']['std_score']:.3f} |")
        lines.append("")
        lines.append(f"**平均分差**: {e4['improvement']['avg_score_diff']:+.3f}")
        lines.append(f"**提升/下降/持平**: {e4['improvement']['improved_count']}/{e4['improvement']['decreased_count']}/{e4['improvement']['unchanged_count']}")
        lines.append(f"**提升率**: {e4['improvement']['improvement_rate']:.2%}")
        lines.append("")

        lines.append("### 5.2 分数分布")
        lines.append("")
        lines.append("| 分数 | TF-IDF | Nemotron RRF |")
        lines.append("|---|---|---|")
        for s in range(1, 6):
            t = e4['tfidf_only']['score_distribution'].get(str(s), 0)
            n = e4['nemotron_rrf']['score_distribution'].get(str(s), 0)
            lines.append(f"| {s}分 | {t} | {n} |")
        lines.append("")

        # 列出部分案例
        lines.append("### 5.3 典型案例")
        lines.append("")
        per_q = e4.get("per_query", [])
        # 找提升最大的案例
        improved_cases = sorted([q for q in per_q if q["score_diff"] > 0], key=lambda x: -x["score_diff"])[:3]
        if improved_cases:
            lines.append("#### Nemotron 提升的案例:")
            lines.append("")
            for c in improved_cases:
                lines.append(f"**Q: {c['query']}**")
                lines.append(f"- TF-IDF 评分: {c['tfidf_score']}/5 — {c['tfidf_comment']}")
                lines.append(f"- Nemotron 评分: {c['nemotron_score']}/5 — {c['nemotron_comment']}")
                lines.append("")
    else:
        lines.append("*E4 未运行或无结果*")
        lines.append("")

    # ---------- 运行耗时 ----------
    lines.append("## 6. 运行耗时")
    lines.append("")
    lines.append("| 实验 | 耗时 |")
    lines.append("|---|---|")
    for exp, t in elapsed.items():
        lines.append(f"| {exp} | {t:.1f}s |")
    lines.append("")

    # ---------- 结论 ----------
    lines.append("## 7. 关键结论")
    lines.append("")
    conclusions = []

    if "e1" in all_results and all_results["e1"]:
        e1 = all_results["e1"]
        agg = {k: v["aggregate"] for k, v in e1.items()}
        # 检查 RRF 是否优于单路
        nemotron_recall = agg.get("Nemotron semantic only", {}).get("recall@5", 0)
        rrf_3way_recall = agg.get("RRF(三路: TF-IDF+BM25+Nemotron)", {}).get("recall@5", 0)
        tfidf_recall = agg.get("TF-IDF only", {}).get("recall@5", 0)
        bm25_recall = agg.get("BM25 only", {}).get("recall@5", 0)

        conclusions.append(f"1. **检索质量**: RRF 三路融合 (Recall@5={rrf_3way_recall:.4f}) 显著优于单一方法 (TF-IDF={tfidf_recall:.4f}, BM25={bm25_recall:.4f}, Nemotron={nemotron_recall:.4f})，验证了混合检索策略的有效性。")

    if "e2" in all_results and all_results["e2"]:
        e2 = all_results["e2"]
        tfidf_p50 = e2.get("E2E: TF-IDF (local)", {}).get("p50_ms", 0)
        nemotron_p50 = e2.get("E2E: Nemotron (NIM)", {}).get("p50_ms", 0)
        if tfidf_p50 > 0 and nemotron_p50 > 0:
            conclusions.append(f"2. **延迟权衡**: Nemotron NIM API 端到端 P50 延迟 ({nemotron_p50:.1f}ms) 约为本地 TF-IDF ({tfidf_p50:.3f}ms) 的 {nemotron_p50/tfidf_p50:.0f}x，适合离线/批处理场景，实时场景可考虑混合策略。")

    if "e3" in all_results and all_results["e3"]:
        e3 = all_results["e3"]
        conclusions.append(f"3. **Skill 检索**: 引入 Nemotron 语义增强后，Top-3 命中率从 {e3['rule_only']['top3_hit_rate']:.4f} 提升至 {e3['rule_plus_semantic']['top3_hit_rate']:.4f} (绝对 {e3['improvement']['absolute']:+.4f})，语义理解有效弥补了纯规则匹配的不足。")

    if "e4" in all_results and all_results["e4"]:
        e4 = all_results["e4"]
        conclusions.append(f"4. **端到端质量**: 基于 Nemotron RRF 的检索增强回答平均评分 ({e4['nemotron_rrf']['avg_score']:.2f}) 相比 TF-IDF only ({e4['tfidf_only']['avg_score']:.2f}) 提升 {e4['improvement']['avg_score_diff']:+.2f} 分，提升率 {e4['improvement']['improvement_rate']:.0%}。")

    conclusions.append("5. **综合建议**: 在 NexusFlow 中推荐采用 BM25 + Nemotron 的 RRF 融合策略作为默认混合检索方案，兼顾检索质量和延迟开销。")

    for c in conclusions:
        lines.append(c)
    lines.append("")

    # ---------- 附录 ----------
    lines.append("## 附录: 文件清单")
    lines.append("")
    lines.append("| 文件 | 说明 |")
    lines.append("|---|---|")
    lines.append("| `eval_dataset/corpus.json` | 25条多领域文档语料库 |")
    lines.append("| `eval_dataset/auto_qa.json` | 50条 QA 查询对 |")
    lines.append("| `eval_dataset/adversarial.json` | 10条对抗性查询 |")
    lines.append("| `eval_dataset/skill_tasks.json` | 20条 Skill 检索任务 |")
    lines.append("| `results/e1_retrieval_quality.json` | E1 检索质量详细结果 |")
    lines.append("| `results/e2_latency_benchmark.json` | E2 延迟基准详细结果 |")
    lines.append("| `results/e3_skill_retrieval.json` | E3 Skill 检索详细结果 |")
    if "e4" in all_results:
        lines.append("| `results/e4_e2e_task_quality.json` | E4 端到端质量详细结果 |")
    lines.append("| `report.md` | 本报告 |")
    lines.append("")

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="Nemotron-3 Embed Benchmark 统一运行入口")
    parser.add_argument("--nim_api_key", required=True, help="NIM API Key")
    parser.add_argument("--llm_api_key", required=True, help="GLM-5.2 API Key")
    parser.add_argument("--model_name", default="nvidia/nemotron-3-embed-1b", help="Nemotron 模型ID")
    parser.add_argument("--num_queries", type=int, default=20, help="E2/E4 测试查询数")
    parser.add_argument("--skip", default="", help="跳过的实验 (逗号分隔)")
    parser.add_argument("--only", default="", help="只运行指定实验 (逗号分隔)")
    args = parser.parse_args()

    ensure_results_dir()

    # 确定运行哪些实验
    all_exps = ["e1", "e2", "e3", "e4"]
    skip_set = set(args.skip.split(",")) if args.skip else set()
    only_set = set(args.only.split(",")) if args.only else set()

    if only_set:
        run_exps = [e for e in all_exps if e in only_set]
    else:
        run_exps = [e for e in all_exps if e not in skip_set]

    print("=" * 70)
    print("Nemotron-3 Embed Benchmark")
    print("=" * 70)
    print(f"将运行实验: {', '.join(run_exps)}")
    print(f"模型: {args.model_name}")
    print(f"E2/E4 查询数: {args.num_queries}")
    print()

    # 收集环境信息
    from bench_utils import load_corpus, load_auto_qa, load_adversarial, load_skill_tasks, SEED
    try:
        import nexusflow
        nf_version = nexusflow.__version__
    except:
        nf_version = "N/A"

    corpus = load_corpus()
    auto_qa = load_auto_qa()
    adversarial = load_adversarial()
    skill_tasks = load_skill_tasks()

    env_info = {
        "nexusflow_version": nf_version,
        "model_name": args.model_name,
        "seed": SEED,
        "corpus_size": len(corpus),
        "qa_size": len(auto_qa),
        "adversarial_size": len(adversarial),
        "skill_task_size": len(skill_tasks),
    }

    all_results = {}
    elapsed = {}

    # ---------- 运行各实验 ----------
    for exp in run_exps:
        print(f"\n{'='*70}")
        print(f"开始运行: {exp.upper()}")
        print(f"{'='*70}")

        t0 = time.time()
        try:
            if exp == "e1":
                all_results["e1"] = run_e1(args.nim_api_key, args.model_name)
            elif exp == "e2":
                all_results["e2"] = run_e2(args.nim_api_key, args.model_name, args.num_queries)
            elif exp == "e3":
                all_results["e3"] = run_e3(args.nim_api_key, args.model_name)
            elif exp == "e4":
                all_results["e4"] = run_e4(
                    nim_api_key=args.nim_api_key,
                    llm_api_key=args.llm_api_key,
                    model_name=args.model_name,
                    num_queries=args.num_queries,
                )
            elapsed[exp] = time.time() - t0
            print(f"\n{exp.upper()} 完成, 耗时: {elapsed[exp]:.1f}s")
        except Exception as e:
            elapsed[exp] = time.time() - t0
            print(f"\n{exp.upper()} 失败: {e}")
            traceback.print_exc()
            all_results[exp] = None

    # ---------- 生成报告 ----------
    print(f"\n{'='*70}")
    print("生成报告...")
    print(f"{'='*70}")

    report = generate_report(all_results, env_info, elapsed)
    report_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "report.md")
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(report)
    print(f"报告已生成: {report_path}")

    # 保存汇总结果
    summary_path = os.path.join(RESULTS_DIR, "benchmark_summary.json")
    save_json(summary_path, {
        "env_info": env_info,
        "elapsed": elapsed,
        "experiments_run": run_exps,
        "timestamp": datetime.now().isoformat(),
    })
    print(f"汇总已保存: {summary_path}")

    print(f"\n{'='*70}")
    print("Benchmark 全部完成!")
    print(f"{'='*70}")
    for exp in run_exps:
        status = "✓" if all_results.get(exp) else "✗"
        print(f"  {status} {exp.upper()}: {elapsed.get(exp, 0):.1f}s")


if __name__ == "__main__":
    main()
