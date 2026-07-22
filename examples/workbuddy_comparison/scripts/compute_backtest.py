# -*- coding: utf-8 -*-
"""L2 回测计算 — 对比A组(单Agent) vs B组(NexusFlow)的预测精度

数据文件应放置在 ../data/ 目录下:
  - 表A_历史数据_1980-2020.xlsx
  - 表B_回测真值.xlsx
输出文件将保存到 ../output/ 目录。
"""
import json
import os
import numpy as np

_BASE_DIR = os.path.join(os.path.dirname(__file__), '..')
_OUTPUT_DIR = os.path.join(_BASE_DIR, 'output')
os.makedirs(_OUTPUT_DIR, exist_ok=True)

with open(os.path.join(_OUTPUT_DIR, "experiment_stats.json"), "r", encoding="utf-8") as f:
    stats = json.load(f)
with open(os.path.join(_OUTPUT_DIR, "predictions_nexusflow.json"), "r", encoding="utf-8") as f:
    nf = json.load(f)

sa_preds = stats["predictions"]
nf_preds = nf["predictions_nf"]

print("=" * 75)
print("  L2 预测回测对比 — 单Agent vs NexusFlow")
print("=" * 75)

results = {"single_agent": {}, "nexusflow": {}, "comparison": {}}

for ind in sa_preds:
    if ind not in nf_preds:
        continue

    # 单Agent
    sa_hits = 0; sa_total = 0; sa_mapes = []
    sa_widths = []
    for c in sa_preds[ind]:
        for p in sa_preds[ind][c]:
            if p["hit"] is not None:
                sa_total += 1
                if p["hit"] == 1: sa_hits += 1
                if p["mape"] is not None: sa_mapes.append(p["mape"])
                w = p["pred_upper"] - p["pred_lower"]
                sa_widths.append(w)

    # NexusFlow
    nf_hits = 0; nf_total = 0; nf_mapes = []
    nf_widths = []
    for c in nf_preds[ind]:
        for p in nf_preds[ind][c]:
            if p["hit"] is not None:
                nf_total += 1
                if p["hit"] == 1: nf_hits += 1
                if p["mape"] is not None: nf_mapes.append(p["mape"])
                w = p["pred_upper"] - p["pred_lower"]
                nf_widths.append(w)

    sa_hr = sa_hits/sa_total*100 if sa_total > 0 else 0
    nf_hr = nf_hits/nf_total*100 if nf_total > 0 else 0
    sa_mape = float(np.mean(sa_mapes)) if sa_mapes else 0
    nf_mape = float(np.mean(nf_mapes)) if nf_mapes else 0
    sa_width = float(np.mean(sa_widths)) if sa_widths else 0
    nf_width = float(np.mean(nf_widths)) if nf_widths else 0

    results["single_agent"][ind] = {
        "hit_rate": round(sa_hr,1), "hits": sa_hits, "total": sa_total,
        "mape": round(sa_mape,1), "avg_width": round(sa_width,2)
    }
    results["nexusflow"][ind] = {
        "hit_rate": round(nf_hr,1), "hits": nf_hits, "total": nf_total,
        "mape": round(nf_mape,1), "avg_width": round(nf_width,2)
    }
    results["comparison"][ind] = {
        "hit_rate_diff": round(nf_hr - sa_hr, 1),
        "mape_diff": round(nf_mape - sa_mape, 1),
        "width_diff": round(nf_width - sa_width, 2)
    }

    print(f"\n{ind}:")
    print(f"  {'指标':<20} {'单Agent':<15} {'NexusFlow':<15} {'差异':<15}")
    print(f"  {'命中率':<20} {sa_hr:>6.1f}% ({sa_hits}/{sa_total})  {nf_hr:>6.1f}% ({nf_hits}/{nf_total})  {nf_hr-sa_hr:>+6.1f}pp")
    print(f"  {'MAPE':<20} {sa_mape:>6.1f}%          {nf_mape:>6.1f}%          {nf_mape-sa_mape:>+6.1f}pp")
    print(f"  {'平均区间宽度':<20} {sa_width:>6.2f}           {nf_width:>6.2f}           {nf_width-sa_width:>+6.2f}")

# 汇总
sa_all_h = sum(results["single_agent"][i]["hits"] for i in results["single_agent"])
sa_all_t = sum(results["single_agent"][i]["total"] for i in results["single_agent"])
nf_all_h = sum(results["nexusflow"][i]["hits"] for i in results["nexusflow"])
nf_all_t = sum(results["nexusflow"][i]["total"] for i in results["nexusflow"])

# 加权MAPE
sa_all_mape = np.mean([m for i in sa_preds for c in sa_preds[i] for p in sa_preds[i][c] if p["mape"] is not None])
nf_all_mape = np.mean([m for i in nf_preds for c in nf_preds[i] for p in nf_preds[i][c] if p["mape"] is not None])

print(f"\n{'='*75}")
print(f"  总体汇总")
print(f"{'='*75}")
print(f"  {'指标':<25} {'单Agent':<15} {'NexusFlow':<15} {'差异':<15}")
print(f"  {'总命中率':<25} {sa_all_h}/{sa_all_t}={sa_all_h/sa_all_t*100:.1f}%   {nf_all_h}/{nf_all_t}={nf_all_h/nf_all_t*100:.1f}%   +{(nf_all_h/nf_all_t-sa_all_h/sa_all_t)*100:.1f}pp")
print(f"  {'加权平均MAPE':<25} {sa_all_mape:.1f}%          {nf_all_mape:.1f}%          {nf_all_mape-sa_all_mape:+.1f}pp")

results["summary"] = {
    "single_agent": {
        "total_hits": sa_all_h, "total_points": sa_all_t,
        "hit_rate": round(sa_all_h/sa_all_t*100, 1),
        "avg_mape": round(float(sa_all_mape), 1)
    },
    "nexusflow": {
        "total_hits": nf_all_h, "total_points": nf_all_t,
        "hit_rate": round(nf_all_h/nf_all_t*100, 1),
        "avg_mape": round(float(nf_all_mape), 1)
    }
}

output_path = os.path.join(_OUTPUT_DIR, "backtest_results.json")
with open(output_path, "w", encoding="utf-8") as f:
    json.dump(results, f, ensure_ascii=False, indent=2, default=str)
print(f"\n回测结果已导出: {output_path}")
