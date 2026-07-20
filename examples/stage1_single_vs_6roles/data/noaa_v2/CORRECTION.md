# 勘误说明（Erratum）：NOAA 回测 MAPE 口径修正

**日期**：2026-07-20
**影响范围**：所有引用"NOAA 综合 MAPE 18.87% → 9.37%（精度提升 50%）"的文档

## 问题

原文档中 NOAA 回测的"综合 MAPE"对比使用了**不对等的指标口径**：

- 单 Agent 侧 `overall` = mean(tmax, tmin, prcp, **comfort**) 四项平均
- 多 Agent 侧 `overall_mape` = mean(tmax, tmin, prcp) 三项平均

`comfort_score` 为高噪声合成体验指标（单 Agent 侧误差 34%~55%），计入单 Agent 侧显著抬高了其综合误差，形成"精度提升 50%"的表象。数字本身计算无误，是口径设计不当。

## 同口径重算结果（仅 tmax / tmin / prcp 三物理量）

| 城市 | 单Agent MAPE | 多Agent MAPE | 优势方 |
|------|:-----------:|:-----------:|:------:|
| 北京 | 4.74% | 7.47% | 单Agent |
| 天津 | 4.24% | 3.90% | 多Agent |
| 石家庄 | 13.47% | 3.50% | 多Agent |
| 济南 | 12.15% | 24.44% | 单Agent |
| 西安 | 11.97% | 7.53% | 多Agent |
| **平均** | **9.31%** | **9.37%** | **持平（3/5 城多Agent更优）** |

## 结论修正

- ~~"回测精度提升 50%（MAPE 18.87%→9.37%）"~~ → **"回测精度同口径整体相当（9.31% vs 9.37%），5 城中 3 城多 Agent 更优"**
- CDoL 的核心差异不在平均预测精度，而在**质量闭环能力**：北京 TMAX 趋势 +17.78°C/decade（异常）→ 质量门禁发现 → 月度距平法校正为 +3.64°C/decade（见 `corrected_trends.json`，R²=0.81）。单 Agent 无此自检机制，自信输出异常结论。
- `comfort_score` 作为独立参考维度单列，不计入综合 MAPE。

## 可复验性

原始结果文件（`single_agent_results.json` / `multi_agent_results.json`）保持原样未改动。本勘误基于其原始字段重算，任何人可用同一公式独立复验上述数字。
