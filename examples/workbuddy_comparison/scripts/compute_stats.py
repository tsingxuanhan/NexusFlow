# -*- coding: utf-8 -*-
"""NexusFlow 对比实验 — 真实数据提取与统计量计算
所有后续分析报告中的数字必须可追溯到这里的计算输出
"""
import pandas as pd
import numpy as np
import json
import os
from itertools import combinations

TABLE_A = r"C:\Users\ASUS\Desktop\表A_历史数据_1980-2020.xlsx"
TABLE_B = r"C:\Users\ASUS\Desktop\表B_回测真值.xlsx"

# 15个指标
INDICATORS = [
    "NGDP_RPCH", "NGDPDPC", "PCPIPCH", "LUR", "GGXWDN_NGDP",
    "GGXCNL_NGDP", "BCA_NGDPD", "TM_RPCH", "TX_RPCH", "NGSD_NGDP",
    "NID_NGDP", "GGXWDG_NGDP", "GGX_NGDP", "GGR_NGDP", "NGAP_NPGDP"
]

# 指标中文名
INDICATOR_NAMES = {
    "NGDP_RPCH": "实际GDP增速(%)", "NGDPDPC": "人均GDP(美元)", "PCPIPCH": "通胀率(%)",
    "LUR": "失业率(%)", "GGXWDN_NGDP": "政府净债务/GDP(%)", "GGXCNL_NGDP": "政府净借贷/GDP(%)",
    "BCA_NGDPD": "经常账户/GDP(%)", "TM_RPCH": "进口量增速(%)", "TX_RPCH": "出口量增速(%)",
    "NGSD_NGDP": "国民总储蓄/GDP(%)", "NID_NGDP": "总投资/GDP(%)", "GGXWDG_NGDP": "政府总债务/GDP(%)",
    "GGX_NGDP": "政府总支出/GDP(%)", "GGR_NGDP": "政府总收入/GDP(%)", "NGAP_NPGDP": "产出缺口(%)"
}

# 20个国家 (代码: 中文名)
COUNTRIES = {
    "USA": "美国", "CHN": "中国", "JPN": "日本", "DEU": "德国", "GBR": "英国",
    "FRA": "法国", "CAN": "加拿大", "AUS": "澳大利亚", "KOR": "韩国",
    "IND": "印度", "BRA": "巴西", "RUS": "俄罗斯", "MEX": "墨西哥", "IDN": "印尼",
    "TUR": "土耳其", "ZAF": "南非", "SAU": "沙特", "ARG": "阿根廷", "EGY": "埃及", "NGA": "尼日利亚"
}

# 国家列名映射 (Excel中的列名 -> 国家代码)
def build_country_map(columns):
    """从列名中提取国家代码"""
    mapping = {}
    for col in columns:
        if col == "年份":
            continue
        for code, name in COUNTRIES.items():
            if code in col or name in col:
                mapping[col] = code
                break
    return mapping

def load_table(path):
    """加载一个表的所有指标数据，返回 {indicator: DataFrame(index=year, cols=country_code)}"""
    xls = pd.ExcelFile(path)
    data = {}
    for sheet in xls.sheet_names:
        if sheet in INDICATORS:
            df = pd.read_excel(path, sheet_name=sheet)
            cmap = build_country_map(df.columns)
            # 重命名列为国家代码
            df = df.rename(columns={**cmap, "年份": "YEAR"})
            df = df.set_index("YEAR")
            data[sheet] = df
    return data

def compute_missing_stats(data_a, data_b):
    """计算缺失统计"""
    results = {"table_a": {}, "table_b": {}}

    for label, data, results_key in [("A", data_a, "table_a"), ("B", data_b, "table_b")]:
        total_cells = 0
        total_missing = 0
        per_country_missing = {c: {"total": 0, "missing": 0} for c in COUNTRIES}
        per_indicator_missing = {}

        for ind, df in data.items():
            n_cells = df.shape[0] * df.shape[1]
            n_missing = df.isna().sum().sum()
            total_cells += n_cells
            total_missing += n_missing
            per_indicator_missing[ind] = {
                "total": int(n_cells), "missing": int(n_missing),
                "rate": round(n_missing / n_cells * 100, 1) if n_cells > 0 else 0
            }
            for col in df.columns:
                if col in per_country_missing:
                    per_country_missing[col]["total"] += df.shape[0]
                    per_country_missing[col]["missing"] += int(df[col].isna().sum())

        results[results_key] = {
            "total_cells": int(total_cells),
            "total_missing": int(total_missing),
            "missing_rate": round(total_missing / total_cells * 100, 1) if total_cells > 0 else 0,
            "valid_cells": int(total_cells - total_missing),
            "per_indicator": per_indicator_missing,
            "per_country": {
                c: {"total": v["total"], "missing": v["missing"],
                    "rate": round(v["missing"] / v["total"] * 100, 1) if v["total"] > 0 else 0}
                for c, v in per_country_missing.items()
            }
        }
    return results

def compute_country_stats(data_a):
    """计算各国各指标的描述统计量 (均值、标准差、最后5年均值、趋势)"""
    stats = {}
    for ind, df in data_a.items():
        stats[ind] = {}
        for country in COUNTRIES:
            if country in df.columns:
                series = df[country].dropna()
                if len(series) > 5:
                    recent = series.iloc[-5:]  # 2016-2020
                    early = series.iloc[:10]   # 1980-1989
                    mid = series.iloc[10:20]   # 1990-1999
                    late = series.iloc[20:31]   # 2000-2010
                    stats[ind][country] = {
                        "mean": round(float(series.mean()), 2),
                        "std": round(float(series.std()), 2),
                        "min": round(float(series.min()), 2),
                        "max": round(float(series.max()), 2),
                        "early_mean": round(float(early.mean()), 2) if len(early) > 0 else None,
                        "mid_mean": round(float(mid.mean()), 2) if len(mid) > 0 else None,
                        "late_mean": round(float(late.mean()), 2) if len(late) > 0 else None,
                        "recent_mean": round(float(recent.mean()), 2),
                        "trend": round(float(recent.mean() - early.mean()), 2) if len(early) > 0 else None,
                        "n_valid": int(len(series))
                    }
    return stats

def detect_structural_breaks(data_a):
    """用简单方法检测结构性转折点 — 基于GDP增速的一阶差分绝对值最大的年份"""
    breaks = {}
    gdp = data_a["NGDP_RPCH"]

    for country in COUNTRIES:
        if country not in gdp.columns:
            continue
        series = gdp[country].dropna()
        if len(series) < 10:
            breaks[country] = []
            continue

        # 计算一阶差分
        diff = series.diff().abs()
        # 取最大的3个年份作为候选转折点
        top3 = diff.nlargest(3)

        # 也检测均值变化最大的点 (10年窗口前后均值差)
        results = []
        for idx in top3.index:
            year = int(idx)
            before = series.loc[:year-1].tail(5)
            after = series.loc[year:].head(5)
            if len(before) >= 3 and len(after) >= 3:
                mean_shift = float(after.mean() - before.mean())
                results.append({
                    "year": year,
                    "gdp_before_5yr_avg": round(float(before.mean()), 2),
                    "gdp_after_5yr_avg": round(float(after.mean()), 2),
                    "mean_shift": round(mean_shift, 2),
                    "diff_magnitude": round(float(diff.loc[idx]), 2)
                })

        # 补充: 检查通胀率的剧烈变化
        infl = data_a.get("PCPIPCH")
        if infl is not None and country in infl.columns:
            infl_series = infl[country].dropna()
            if len(infl_series) > 10:
                infl_diff = infl_series.diff().abs()
                infl_top = infl_diff.nlargest(2)
                for idx in infl_top.index:
                    year = int(idx)
                    if not any(r["year"] == year for r in results):
                        results.append({
                            "year": year,
                            "type": "inflation_spike",
                            "inflation": round(float(infl_series.loc[idx]), 1)
                        })

        results.sort(key=lambda x: x["year"])
        breaks[country] = results

    return breaks

def compute_cross_country_correlations(data_a):
    """计算跨国相关性 — 基于GDP增速的领先/滞后相关"""
    gdp = data_a["NGDP_RPCH"]
    correlations = []
    countries_with_data = [c for c in COUNTRIES if c in gdp.columns]

    for c1, c2 in combinations(countries_with_data, 2):
        s1 = gdp[c1].dropna()
        s2 = gdp[c2].dropna()
        # 对齐年份
        common = s1.index.intersection(s2.index)
        if len(common) < 15:
            continue
        a1 = s1.loc[common]
        a2 = s2.loc[common]

        # 同期相关
        corr0 = float(a1.corr(a2))

        # 领先1-3年相关
        best_lag = 0
        best_corr = corr0
        for lag in range(1, 4):
            shifted = a2.shift(lag)
            aligned = pd.concat([a1, shifted], axis=1).dropna()
            if len(aligned) > 10:
                c = float(aligned.iloc[:, 0].corr(aligned.iloc[:, 1]))
                if abs(c) > abs(best_corr):
                    best_corr = c
                    best_lag = lag

        if abs(best_corr) > 0.4:  # 只记录中等以上相关
            strength = "强" if abs(best_corr) > 0.7 else "中等"
            direction = "正" if best_corr > 0 else "负"
            correlations.append({
                "country1": c1, "country2": c2,
                "correlation": round(best_corr, 3),
                "lag": best_lag,
                "strength": strength,
                "direction": direction,
                "interpretation": f"{c1}的GDP增速{('领先' if best_lag>0 else '同期')}{c2}{abs(best_lag) if best_lag>0 else ''}年, {strength}{direction}相关(r={round(best_corr,2)})"
            })

    # 按绝对值排序
    correlations.sort(key=lambda x: abs(x["correlation"]), reverse=True)
    return correlations

def compute_three_dim_scores(data_a):
    """计算三维度评分: 财政健康、外部平衡、价格稳定 (基于2016-2020近5年均值)"""
    scores = {}

    # 财政健康: GGXWDN_NGDP(净债务,越低越好), GGXCNL_NGDP(净借贷,越接近0越好), GGXWDG_NGDP(总债务,越低越好)
    # 外部平衡: BCA_NGDPD(经常账户,越接近0越好), TM_RPCH(进口增速), TX_RPCH(出口增速)
    # 价格稳定: PCPIPCH(通胀,越低越好), NGAP_NPGDP(产出缺口,越接近0越好)

    def recent_avg(df, country, years=5):
        if country not in df.columns:
            return None
        s = df[country].dropna()
        if len(s) < years:
            return None
        return float(s.iloc[-years:].mean())

    for country, cname in COUNTRIES.items():
        # 财政健康 (0-100, 越高越好)
        net_debt = recent_avg(data_a["GGXWDN_NGDP"], country)
        net_lending = recent_avg(data_a["GGXCNL_NGDP"], country)
        gross_debt = recent_avg(data_a["GGXWDG_NGDP"], country)

        fiscal_components = []
        if net_debt is not None:
            # 净债务: 负值(净资产)得高分, 正值按比例扣分
            fiscal_components.append(max(0, 100 - abs(net_debt) * 1.5))
        if net_lending is not None:
            # 净借贷: 越接近0越好, 盈余(负值)好于赤字(正值)
            fiscal_components.append(max(0, 100 - abs(net_lending) * 3))
        if gross_debt is not None:
            fiscal_components.append(max(0, 100 - gross_debt * 0.8))
        fiscal_score = float(np.mean(fiscal_components)) if fiscal_components else None

        # 外部平衡
        ca = recent_avg(data_a["BCA_NGDPD"], country)
        imp = recent_avg(data_a["TM_RPCH"], country)
        exp = recent_avg(data_a["TX_RPCH"], country)

        ext_components = []
        if ca is not None:
            ext_components.append(max(0, 100 - abs(ca) * 2))
        if imp is not None and exp is not None:
            trade_balance = exp - imp
            ext_components.append(max(0, 50 + trade_balance * 5))
        ext_score = float(np.mean(ext_components)) if ext_components else None

        # 价格稳定
        infl = recent_avg(data_a["PCPIPCH"], country)
        gap = recent_avg(data_a["NGAP_NPGDP"], country)

        price_components = []
        if infl is not None:
            price_components.append(max(0, 100 - infl * 4))
        if gap is not None:
            price_components.append(max(0, 100 - abs(gap) * 10))
        price_score = float(np.mean(price_components)) if price_components else None

        # 综合 (三维度等权)
        all_scores = [s for s in [fiscal_score, ext_score, price_score] if s is not None]
        overall = float(np.mean(all_scores)) if all_scores else None

        scores[country] = {
            "name": cname,
            "fiscal_health": round(fiscal_score, 1) if fiscal_score else None,
            "external_balance": round(ext_score, 1) if ext_score else None,
            "price_stability": round(price_score, 1) if price_score else None,
            "overall": round(overall, 1) if overall else None,
            "raw": {
                "net_debt_gdp": round(net_debt, 1) if net_debt else None,
                "net_lending_gdp": round(net_lending, 1) if net_lending else None,
                "gross_debt_gdp": round(gross_debt, 1) if gross_debt else None,
                "current_account": round(ca, 1) if ca else None,
                "import_growth": round(imp, 1) if imp else None,
                "export_growth": round(exp, 1) if exp else None,
                "inflation": round(infl, 1) if infl else None,
                "output_gap": round(gap, 1) if gap else None,
            }
        }

    # 排名
    ranked = sorted([(c, s) for c, s in scores.items() if s["overall"] is not None],
                    key=lambda x: x[1]["overall"], reverse=True)
    for rank, (c, s) in enumerate(ranked, 1):
        scores[c]["rank"] = rank

    return scores

def compute_prediction_basis(data_a, data_b):
    """计算预测基础 — 基于历史趋势为5项关键指标生成预测区间"""
    # 5项: NGDP_RPCH, NGDPDPC, PCPIPCH, LUR, GGXWDN_NGDP
    pred_indicators = ["NGDP_RPCH", "NGDPDPC", "PCPIPCH", "LUR", "GGXWDN_NGDP"]
    predictions = {}

    for ind in pred_indicators:
        if ind not in data_a:
            continue
        df_a = data_a[ind]
        df_b = data_b.get(ind)
        predictions[ind] = {}

        for country in COUNTRIES:
            if country not in df_a.columns:
                continue
            series = df_a[country].dropna()
            if len(series) < 10:
                continue

            # 历史5年均值和标准差
            recent5 = series.iloc[-5:]
            recent_mean = float(recent5.mean())
            recent_std = float(recent5.std())

            # 10年趋势
            recent10 = series.iloc[-10:]
            x = np.arange(len(recent10))
            if len(recent10) >= 10:
                trend_slope = float(np.polyfit(x, recent10.values, 1)[0])
            else:
                trend_slope = 0

            # 真实值 (表B)
            actual = []
            if df_b is not None and country in df_b.columns:
                actual = df_b[country].dropna().tolist()

            # 生成预测区间: 中值=近5年均值+趋势外推, 区间宽度=1.5*标准差
            for i, year in enumerate([2021, 2022, 2023, 2024, 2025]):
                mid = recent_mean + trend_slope * (i + 1)
                # 对GDP增速等可能为负的指标，区间要宽一些
                width = max(abs(recent_std) * 1.5, abs(mid) * 0.3, 0.5)
                lower = mid - width
                upper = mid + width

                # NGDPDPC是绝对值，增长趋势明显
                if ind == "NGDPDPC" and mid > 0:
                    width = mid * 0.15  # 15%的区间宽度
                    lower = mid * 0.85
                    upper = mid * 1.15

                actual_val = actual[i] if i < len(actual) else None
                hit = None
                if actual_val is not None:
                    hit = 1 if lower <= actual_val <= upper else 0
                    mape = abs(mid - actual_val) / abs(actual_val) * 100 if actual_val != 0 else None
                else:
                    mape = None

                if country not in predictions[ind]:
                    predictions[ind][country] = []
                predictions[ind][country].append({
                    "year": year,
                    "pred_mid": round(mid, 2),
                    "pred_lower": round(lower, 2),
                    "pred_upper": round(upper, 2),
                    "actual": round(actual_val, 2) if actual_val is not None else None,
                    "hit": hit,
                    "mape": round(mape, 1) if mape is not None else None
                })

    return predictions

def main():
    print("=" * 70)
    print("  NexusFlow 对比实验 — 数据提取与统计计算")
    print("=" * 70)

    # 加载数据
    print("\n[1] 加载表A...")
    data_a = load_table(TABLE_A)
    print(f"  加载 {len(data_a)} 个指标: {list(data_a.keys())}")

    print("\n[2] 加载表B...")
    data_b = load_table(TABLE_B)
    print(f"  加载 {len(data_b)} 个指标: {list(data_b.keys())}")

    # 验证数据形状
    for ind in INDICATORS:
        if ind in data_a:
            print(f"  表A {ind}: {data_a[ind].shape} (年×国)")
        if ind in data_b:
            print(f"  表B {ind}: {data_b[ind].shape} (年×国)")

    # 缺失统计
    print("\n[3] 计算缺失统计...")
    missing = compute_missing_stats(data_a, data_b)
    print(f"  表A: {missing['table_a']['valid_cells']}/{missing['table_a']['total_cells']} 有效 ({100-missing['table_a']['missing_rate']}%)")
    print(f"  表B: {missing['table_b']['valid_cells']}/{missing['table_b']['total_cells']} 有效 ({100-missing['table_b']['missing_rate']}%)")

    # 各国缺失率
    print("\n  表A 各国缺失率:")
    for c in sorted(COUNTRIES.keys()):
        s = missing["table_a"]["per_country"].get(c, {})
        print(f"    {c} ({COUNTRIES[c]}): {s.get('missing',0)}/{s.get('total',0)} ({s.get('rate',0)}%)")

    # 描述统计
    print("\n[4] 计算各国描述统计量...")
    stats = compute_country_stats(data_a)
    print(f"  完成: {len(stats)} 个指标 × ~20 个国家")

    # 结构性转折点
    print("\n[5] 检测结构性转折点 (基于GDP增速差分)...")
    breaks = detect_structural_breaks(data_a)
    for c in ["USA", "CHN", "JPN", "DEU", "BRA", "ARG", "RUS", "KOR"]:
        if c in breaks and breaks[c]:
            print(f"  {c} ({COUNTRIES[c]}):")
            for b in breaks[c]:
                if "mean_shift" in b:
                    print(f"    {b['year']}: GDP均值变化 {b['gdp_before_5yr_avg']}→{b['gdp_after_5yr_avg']} (shift={b['mean_shift']})")
                else:
                    print(f"    {b['year']}: {b.get('type','break')}")

    # 跨国相关性
    print("\n[6] 计算跨国相关性 (GDP增速)...")
    corrs = compute_cross_country_correlations(data_a)
    print(f"  发现 {len(corrs)} 组 |r|>0.4 的跨国相关")
    print("  TOP 15:")
    for c in corrs[:15]:
        print(f"    {c['country1']}-{c['country2']}: r={c['correlation']} (lag={c['lag']}) {c['interpretation']}")

    # 三维度评分
    print("\n[7] 计算三维度评分 (基于2016-2020)...")
    scores = compute_three_dim_scores(data_a)
    ranked = sorted([(c, s) for c, s in scores.items() if s.get("overall")],
                    key=lambda x: x[1]["overall"], reverse=True)
    print(f"{'排名':<4} {'国家':<6} {'财政':<8} {'外部':<8} {'价格':<8} {'综合':<8}")
    for rank, (c, s) in enumerate(ranked, 1):
        print(f"{rank:<4} {c:<6} {s['fiscal_health'] or 'N/A':<8} {s['external_balance'] or 'N/A':<8} {s['price_stability'] or 'N/A':<8} {s['overall']:<8}")

    # 预测基础
    print("\n[8] 计算预测基础 (5项关键指标)...")
    preds = compute_prediction_basis(data_a, data_b)
    for ind in preds:
        total = 0
        hits = 0
        mapes = []
        for c in preds[ind]:
            for p in preds[ind][c]:
                total += 1
                if p["hit"] == 1:
                    hits += 1
                if p["mape"] is not None:
                    mapes.append(p["mape"])
        hit_rate = hits / total * 100 if total > 0 else 0
        avg_mape = float(np.mean(mapes)) if mapes else 0
        print(f"  {ind} ({INDICATOR_NAMES[ind]}): 命中率={hits}/{total}={hit_rate:.1f}%, MAPE={avg_mape:.1f}%")

    # 汇总
    total_hits = sum(1 for ind in preds for c in preds[ind] for p in preds[ind][c] if p["hit"] == 1)
    total_preds = sum(1 for ind in preds for c in preds[ind] for p in preds[ind][c] if p["hit"] is not None)
    all_mapes = [p["mape"] for ind in preds for c in preds[ind] for p in preds[ind][c] if p["mape"] is not None]
    print(f"\n  总体: 命中率={total_hits}/{total_preds}={total_hits/total_preds*100:.1f}%, 平均MAPE={float(np.mean(all_mapes)):.1f}%")

    # 导出
    output = {
        "missing_stats": missing,
        "country_stats": stats,
        "structural_breaks": breaks,
        "cross_country_correlations": corrs,
        "three_dim_scores": scores,
        "predictions": preds,
        "summary": {
            "table_a": {
                "indicators": len(data_a),
                "years": f"{min(data_a[list(data_a.keys())[0]].index)}-{max(data_a[list(data_a.keys())[0]].index)}",
                "countries": 20,
                "total_cells": missing["table_a"]["total_cells"],
                "valid_cells": missing["table_a"]["valid_cells"],
                "missing_rate": missing["table_a"]["missing_rate"]
            },
            "table_b": {
                "indicators": len(data_b),
                "years": f"{min(data_b[list(data_b.keys())[0]].index)}-{max(data_b[list(data_b.keys())[0]].index)}",
                "countries": 20,
                "total_cells": missing["table_b"]["total_cells"],
                "valid_cells": missing["table_b"]["valid_cells"],
                "missing_rate": missing["table_b"]["missing_rate"]
            },
            "overall_hit_rate": round(total_hits / total_preds * 100, 1) if total_preds > 0 else 0,
            "overall_mape": round(float(np.mean(all_mapes)), 1) if all_mapes else 0,
            "n_correlations": len(corrs)
        }
    }

    output_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "experiment_stats.json")
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2, default=str)
    print(f"\n[9] 统计结果已导出: {output_path}")
    print("\n" + "=" * 70)
    print("  数据提取与统计计算完成")
    print("=" * 70)

if __name__ == "__main__":
    main()
