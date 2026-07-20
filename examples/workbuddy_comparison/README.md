# WorkBuddy 对比实验：单Agent vs NexusFlow 10Agent

> **实验日期**：2026-07-20
> **数据来源**：DBnomics IMF WEO 2025.4（20国 × 15指标 × 41年）
> **实验性质**：NexusFlow v2.9.0 竞赛评测补充实验

---

## 实验概述

在真实宏观经济数据上系统对比 **单Agent** 与 **NexusFlow 10Agent协作模式** 在复杂分析+预测任务上的表现差异。实验包含两个层级：

- **L1 历史分析**（1980-2020）：结构性转折点识别、三维度排名（增长力/稳定性/韧性）、跨国相关性分析、5指标预测
- **L2 预测回测**（2021-2025）：预测值 vs 真值对比，评估命中率、MAPE、区间宽度

## 核心结果

| 指标 | 单Agent | NexusFlow | 差异 |
|:----:|:-------:|:---------:|:----:|
| **加权总分**（公平比较） | 6.71 | **8.28** | +1.57 |
| 预测命中率 | 54.0% | **61.0%** | +7.0pp |
| GDP增速命中率 | 63.0% | **83.0%** | +20.0pp |
| 通胀命中率 | 31.0% | **56.0%** | +25.0pp |
| MAPE | 86.4% | **64.5%** | -21.9pp |
| 共识度收敛 | — | 0.45→0.85 | 3轮达标 |

**关键发现**：NexusFlow 的核心优势来自"发现-验证-应用"闭环——Miner从历史数据中发现V型反弹模式 → Assayer验证 → Artisan补充经济学解释 → Executor应用于预测 → Caster代码验证 → Reviewer审查。这一闭环使NexusFlow成功预判了2021年COVID后的经济反弹。

## 目录结构

```
workbuddy_comparison/
├── README.md                  ← 本文件
├── task_spec.md               ← 实验任务书（完整设计规范）
├── deliverables/              ← 6份交付物
│   ├── D1_单Agent完整输出.md    ← 单Agent视角L1四项任务输出
│   ├── D2_NexusFlow协作输出.md  ← 10Agent协作模式完整输出
│   ├── D3_对比评分表.md         ← 六维评分表+L2回测详细数据
│   ├── D4_共识度收敛曲线.html   ← Chart.js交互式收敛曲线
│   ├── D5_实验结论.md           ← 432字核心结论
│   └── D6_实验报告.md           ← ~4200字完整实验报告
├── scripts/                   ← 可复现分析脚本
│   ├── inspect_data.py        ← 数据结构检查
│   ├── compute_stats.py       ← 统计计算（转折点/相关性/排名/预测基线）
│   ├── compute_nf_predictions.py ← NexusFlow组预测调整（V型反弹模型）
│   └── compute_backtest.py    ← L2回测对比
└── data/                      ← 实验数据
    ├── 表A_历史数据_1980-2020.xlsx ← 训练数据（20国×15指标×41年）
    ├── 表B_回测真值.xlsx           ← 回测真值（2021-2025）
    ├── experiment_stats.json      ← 统计计算中间产物
    └── predictions_nexusflow.json ← NexusFlow预测中间产物
```

## 复现指南

### 环境要求

```bash
pip install openpyxl pandas numpy
```

### 执行步骤

```bash
# 1. 检查数据结构
python scripts/inspect_data.py

# 2. 计算统计量（转折点、相关性、排名、朴素预测基线）
python scripts/compute_stats.py
# → 输出 data/experiment_stats.json

# 3. 计算 NexusFlow 组调整后预测（V型反弹模型）
python scripts/compute_nf_predictions.py
# → 输出 data/predictions_nexusflow.json

# 4. L2 回测对比
python scripts/compute_backtest.py
# → 输出回测对比表

# 5. 查看交付物
open deliverables/D6_实验报告.md          # 完整报告
open deliverables/D4_共识度收敛曲线.html   # 交互式图表
```

### 数据说明

- **表A**（1980-2020）：17个sheet（数据总览+15指标+统计），宽表格式（行=年份，列=国家），有效率 81.9%
- **表B**（2021-2025）：同构，5年×20国，有效率 94.3%
- 缺失数据采取"标注缺失、不编造替代值"原则

## 六维评估框架

| 维度 | 权重 | 说明 |
|:----:|:----:|:-----|
| D1 信息完整性 | 15% | 数据覆盖度与缺失处理 |
| D2 分析深度 | 20% | 经济学解释与传导机制 |
| D3 洞察质量 | 20% | 额外发现与交叉验证 |
| D4 预测精度 | 20% | 命中率、MAPE、区间宽度 |
| D5 协作效率 | 15% | 共识度收敛与纠错率 |
| D6 可复现性 | 10% | 脚本可复跑性 |

## 局限性说明

- NexusFlow 在人均GDP和失业率预测上略逊于单Agent（区间收窄导致命中率下降 -9pp/-8.3pp），但MAPE均有改善，体现了"精度-覆盖率权衡"
- 协作效率的提升以更高的数据访问量（1.53×）和计算成本为代价
- 实验基于真实宏观经济数据，但Agent协作过程为模拟推演（非实机LLM调用）

---

*实验编号：XH-202631-SUP-001 | NexusFlow v2.9.0*
