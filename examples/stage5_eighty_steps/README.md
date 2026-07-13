# Stage-5: 80步公平对比 Benchmark（大宗商品分析）

## 实验设计

- **目标**：在相同步数（80步 vs 80步）下，对比 Single-Agent 和 NexusFlow 在复杂大宗商品分析任务上的表现
- **日期**：2026-07-08
- **LLM**：deepseek-chat（DeepSeek API）
- **数据源**：AKShare 大宗商品数据（14个接口真实采集：电力/现货/合约/库存/持仓/期权等）

## 公平性保证

| 控制项 | Single-Agent | NexusFlow |
|--------|:-----------:|:---------:|
| 步数 | 80 | 80 |
| 相同任务集 | ✅ | ✅ |
| 相同LLM | deepseek-chat | deepseek-chat |
| 相同数据源 | 14个AKShare接口 | 14个AKShare接口 |
| 相同评估器 | 独立LLM评估(1-10) | 独立LLM评估(1-10) |

## 核心结果

| 指标 | Single-Agent | NexusFlow | NF优势 |
|:-----|:-----------:|:---------:|:------:|
| 平均质量分 | 7.72 | **7.92** | +2.6% |
| ≥9分步数 | 4 | **13** | 3.25倍 |
| 总耗时 | 1704s | **1450s** | -14.9% |
| 总Token | 276,723 | **259,559** | -6.2% |
| 每1000Token产出质量 | 2.23 | **2.44** | +9.4% |

## Phase 胜负

| Phase | SA均Q | NF均Q | 胜者 |
|:------|:-----:|:-----:|:----:|
| P1 数据审查 | 7.83 | 8.00 | NF |
| P2 专业分析 | 7.62 | 7.92 | NF |
| P3 产业链 | 7.00 | 7.75 | NF (+0.75) |
| P4 宏观 | 7.88 | 8.00 | NF |
| P5 策略/CDoL | 7.65 | 8.38 | NF (+0.73) |
| P6 迭代/验证 | **8.14** | 7.67 | SA |
| P7 报告/审核 | 8.00 | 8.20 | NF |

NF 赢 6/7 Phase。SA 唯一优势在 P6 自我迭代。

## 关键发现

1. **SA灾难性失误**：Step 32（黑色产业链分析）仅2分，上下文污染导致"串台"
2. **CDoL讨论质量高**：P5阶段8轮CDoL讨论均Q=8.5，3步拿9分
3. **NF Agent排名**：PreciousAnalyst(8.33) > MetalsAnalyst(8.14) > MacroAnalyst(8.00)
4. **Token效率**：NF每Agent只看专业数据，不浪费Token在无关上下文

## 文件说明

- `run_real_benchmark.py` — 实验脚本（含断点续跑、真实API调用、独立质量评估）
- `data/comparison.json` — 完整对比数据（含Phase分布、质量分布、Token统计）
- `data/sa_results.json` — Single-Agent 80步逐步骤结果
- `data/nf_results.json` — NexusFlow 80步逐步骤结果
- `data/full_outputs_single_agent.json` — SA完整LLM输出（可复现验证）
- `data/full_outputs_nexusflow.json` — NF完整LLM输出（可复现验证）

## 复现方法

```bash
# 需要设置环境变量
export DEEPSEEK_API_KEY="your-key-here"

# 运行80步对比
python run_real_benchmark.py --steps 80 --mode both
```

> **数据真实性声明**：所有数据来自真实LLM输出（deepseek-chat API），质量分由独立LLM评估器打分（1-10分），耗时和Token来自API实际返回。实验可完整复现。
