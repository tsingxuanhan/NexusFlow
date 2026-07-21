# 真实 LLM 端云协同 Benchmark

> 2026-07-21 | 真实 DeepSeek API + Ollama 本地模型 | 零模拟

## 概述

本实验使用**真实 LLM API 调用**验证 NexusFlow 的端云协同调度架构，对比 10 Agent 协作模式与单 Agent 模式在宏观经济分析+预测任务上的表现。

## 端云调度

| Agent | 端/云 | 模型 |
|-------|:-----:|------|
| Coordinator, Planner, Miner, Assayer, Artisan, Reviewer, Coordinator(最终) | ☁️ 云端 | DeepSeek-chat (API) |
| Researcher, Executor, Caster, Archivist | 📱 端侧 | Qwen3.5-9B (Ollama) |

**分配原则**: 深度推理任务→云端大模型；标准化任务→端侧轻量模型

## 核心结果

| 指标 | NexusFlow | SingleAgent | 优势方 |
|------|:---------:|:-----------:|:------:|
| 通胀预测 MAPE | **3.8%** | 11.4% | NF (3x) |
| GDP预测 MAPE | 2.8% | 2.5% | SA (微弱) |
| 命中率 | 100% | 100% | 持平 |
| 总 Token | 175,948 | 2,701 | — |
| 总耗时 | 265s | 20s | — |
| 端云调用 | 7云+4端=11 | 1云 | — |
| 错误 | 0 | 0 | — |

## 关键发现

1. **端云协同调度实机验证成功**（P0 达成）
2. **NexusFlow 通胀预测 3 倍优于单 Agent**（MAPE 3.8% vs 11.4%）
3. **多 Agent 协作核心价值在交叉验证**：Miner发现→Assayer验证→Artisan解释→Reviewer审查

## 文件清单

| 文件 | 说明 |
|------|------|
| `prepare_real_data.py` | 数据准备：验证API + 提取表A数据 |
| `real_benchmark_macro.py` | Benchmark主脚本：10Agent端云协同 + 单Agent对照 |
| `real_benchmark_results.json` | 完整结果（所有Agent输出+Token记录+对比数据） |
| `data_cloud.txt` | 云端版数据（全量，8290 tokens） |
| `data_edge.txt` | 端侧版数据（摘要，2637 tokens） |
| `D7_真实LLM实验报告.md` | 完整实验报告 |

## 复现

```bash
# 环境要求
# - Python 3.12+
# - DeepSeek API key (付费)
# - Ollama + qwen3.5:9b 模型

# 运行
python prepare_real_data.py    # 验证API + 提取数据
python real_benchmark_macro.py # 运行benchmark (~5分钟)
```
