# -*- coding: utf-8 -*-
"""NexusFlow 对比实验 - 数据解析脚本
检查表A、表B的结构、数据质量、缺失分布

数据文件应放置在 ../data/ 目录下:
  - 表A_历史数据_1980-2020.xlsx
  - 表B_回测真值.xlsx
"""
import pandas as pd
import numpy as np
import sys
import os

pd.set_option('display.max_columns', None)
pd.set_option('display.width', 200)
pd.set_option('display.max_rows', 100)

_BASE_DIR = os.path.join(os.path.dirname(__file__), '..')
_DATA_DIR = os.path.join(_BASE_DIR, 'data')

TABLE_A = os.path.join(_DATA_DIR, "表A_历史数据_1980-2020.xlsx")
TABLE_B = os.path.join(_DATA_DIR, "表B_回测真值.xlsx")

# 任务书定义的15个指标代码
EXPECTED_INDICATORS = [
    "NGDP_RPCH", "NGDPDPC", "PCPIPCH", "LUR", "GGXWDN_NGDP",
    "GGXCNL_NGDP", "BCA_NGDPD", "TM_RPCH", "TX_RPCH", "NGSD_NGDP",
    "NID_NGDP", "GGXWDG_NGDP", "GGX_NGDP", "GGR_NGDP", "NGAP_NPGDP"
]

# 20个国家代码
EXPECTED_COUNTRIES = [
    "USA", "CHN", "JPN", "DEU", "GBR", "FRA", "CAN", "AUS", "KOR",
    "IND", "BRA", "RUS", "MEX", "IDN", "TUR", "ZAF", "SAU", "ARG", "EGY", "NGA"
]

def inspect_excel(path, label):
    print("=" * 80)
    print(f"  {label}: {os.path.basename(path)}")
    print("=" * 80)

    # 读取所有sheet
    xls = pd.ExcelFile(path)
    print(f"\n[Sheet列表] {xls.sheet_names}")

    for sheet_name in xls.sheet_names:
        df = pd.read_excel(path, sheet_name=sheet_name)
        print(f"\n--- Sheet: '{sheet_name}' ---")
        print(f"形状 (行×列): {df.shape}")
        print(f"\n[列名]")
        for i, c in enumerate(df.columns):
            print(f"  {i}: {repr(c)}")
        print(f"\n[前10行]")
        print(df.head(10).to_string())
        print(f"\n[数据类型]")
        print(df.dtypes.to_string())
    return xls

def deep_inspect(path, label, expected_years_range):
    """对主数据sheet做深度检查"""
    print("\n" + "#" * 80)
    print(f"  深度检查: {label}")
    print("#" * 80)

    xls = pd.ExcelFile(path)
    # 用第一个sheet做深度检查
    df = pd.read_excel(path, sheet_name=xls.sheet_names[0])

    print(f"\n形状: {df.shape}")
    print(f"\n[全部列名] {list(df.columns)}")

    # 推断结构：找国家列、年份列、指标列
    cols = [str(c) for c in df.columns]
    print(f"\n[前5行原始数据]")
    print(df.head().to_string())

    # 检查是否有国家代码列
    country_col = None
    for c in df.columns:
        vals = df[c].astype(str).str.upper().unique()
        match_count = sum(1 for v in vals if v in EXPECTED_COUNTRIES)
        if match_count >= 15:  # 至少匹配15个国家
            country_col = c
            print(f"\n[检测到国家列] '{c}' — 匹配 {match_count}/20 个预期国家代码")
            print(f"  实际国家值: {sorted(df[c].dropna().astype(str).str.upper().unique().tolist())}")
            break

    # 检查是否有年份列
    year_col = None
    for c in df.columns:
        if country_col and c == country_col:
            continue
        try:
            vals = pd.to_numeric(df[c], errors='coerce').dropna()
            if vals.min() >= 1970 and vals.max() <= 2030 and vals.nunique() > 5:
                year_col = c
                print(f"\n[检测到年份列] '{c}' — 范围 {int(vals.min())}-{int(vals.max())}, {vals.nunique()}个年份")
                break
        except:
            pass

    # 检查指标 - 可能是列(宽表)或行(长表)
    print(f"\n[结构推断] country_col={country_col}, year_col={year_col}")

    if country_col and year_col:
        # 长表格式: country, year, indicator1, indicator2, ...
        remaining_cols = [c for c in df.columns if c not in [country_col, year_col]]
        print(f"  剩余列(指标): {remaining_cols}")

        # 检查指标是否匹配
        matched_indicators = [ind for ind in EXPECTED_INDICATORS
                            if any(ind in str(c).upper() for c in remaining_cols)]
        print(f"  匹配指标: {len(matched_indicators)}/15")
        print(f"  匹配的指标: {matched_indicators}")

        # 数据质量
        countries = df[country_col].dropna().astype(str).str.upper().unique()
        years = pd.to_numeric(df[year_col], errors='coerce').dropna()
        print(f"\n[数据覆盖]")
        print(f"  国家数: {len(countries)}")
        print(f"  年份范围: {int(years.min())}-{int(years.max())}")
        print(f"  年份数: {years.nunique()}")
        print(f"  理论行数: {len(countries) * years.nunique()}")

        # 缺失值分析
        print(f"\n[缺失值分析]")
        for col in remaining_cols[:20]:  # 最多看20列
            null_count = df[col].isna().sum()
            total = len(df)
            pct = null_count / total * 100
            if null_count > 0:
                print(f"  {col}: {null_count}/{total} 缺失 ({pct:.1f}%)")

        total_cells = df[remaining_cols].size
        total_nulls = df[remaining_cols].isna().sum().sum()
        print(f"\n  总数据点: {total_cells}")
        print(f"  总缺失: {total_nulls} ({total_nulls/total_cells*100:.1f}%)")
        print(f"  有效数据点: {total_cells - total_nulls}")

        # 各国家缺失率
        print(f"\n[各国家缺失率]")
        for country in sorted(countries):
            sub = df[df[country_col].astype(str).str.upper() == country]
            sub_cells = sub[remaining_cols].size
            sub_nulls = sub[remaining_cols].isna().sum().sum()
            pct = sub_nulls / sub_cells * 100 if sub_cells > 0 else 0
            print(f"  {country}: {sub_nulls}/{sub_cells} ({pct:.1f}%) | 年份: {sub[year_col].min()}-{sub[year_col].max()}")

    return df, country_col, year_col

if __name__ == "__main__":
    xls_a = inspect_excel(TABLE_A, "表A (训练集)")
    xls_b = inspect_excel(TABLE_B, "表B (验证集)")

    df_a, cc_a, yc_a = deep_inspect(TABLE_A, "表A", (1980, 2020))
    df_b, cc_b, yc_b = deep_inspect(TABLE_B, "表B", (2021, 2025))

    print("\n\n" + "=" * 80)
    print("  数据解析完成")
    print("=" * 80)
