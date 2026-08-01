# LHAB-NF Benchmark Suite

**Long-Horizon AgentBench for NexusFlow** — 面向超长程复杂任务的群体智能评测基准。

## 概述

LHAB-NF 评测框架包含：
- **9 个基准任务**（3 类别 × 3 难度）
- **5 个评测系统**（NexusFlow + 4 个基线）
- **7 种扰动注入**（设备离线、网络超时、工具失败、需求变更、数据冲突、低质量输出、记忆注入）
- **统计检验**（Welch's t-test + Cohen's d effect size）

## 目录结构

```
evaluation/lhab_nf/
├── tasks/                  # 9 个任务 YAML（3×3）
│   ├── T1-E-001.yaml      # 跨设备-简单
│   ├── T1-M-001.yaml      # 跨设备-中等
│   ├── T1-H-001.yaml      # 跨设备-困难
│   ├── T2-E-001.yaml      # 软件工程-简单
│   ├── T2-M-001.yaml      # 软件工程-中等
│   ├── T2-H-001.yaml      # 软件工程-困难
│   ├── T3-E-001.yaml      # 数据分析-简单
│   ├── T3-M-001.yaml      # 数据分析-中等
│   └── T3-H-001.yaml      # 数据分析-困难
├── task_schema.py          # 任务数据结构
├── scorer.py               # 评测指标计算
├── runner.py               # 基础运行器（mock/real 双模式）
├── agent_adapter.py        # NexusFlow HTTP 适配器
├── baselines.py            # 4 个基线系统
├── comprehensive_runner.py # 综合执行器
├── report_generator.py     # 分析报告生成
├── run_full_benchmark.sh   # 一键运行脚本
├── ablation_runner.py      # 消融实验框架
├── topology_interpreter.py # 路由决策解释器
└── topology_optimizer.py   # 拓扑优化器（MAB）
```

## 基线系统

| 基线 | 描述 |
|------|------|
| **StaticPipeline** | 固定顺序执行，无动态路由 |
| **FullContextMultiAgent** | 全上下文广播 + 多数投票 |
| **FixedDAG** | 静态依赖图，无重路由 |
| **PlainSingleAgent** | 单通用 Agent 串行执行 |

## 快速开始

```bash
# Mock 模式快速验证（3 seeds）
python comprehensive_runner.py --seeds 3 --mode mock --baselines all

# Real 模式完整运行（需要 server 在 8900 端口）
python comprehensive_runner.py --seeds 5 --mode real --baselines all

# 生成报告
python report_generator.py --results-dir results/

# 一键运行
./run_full_benchmark.sh mock 3
```

## 评测指标

- **TCR** (Task Completion Rate): 任务完成率
- **SSR** (Step Success Rate): 步骤成功率
- **NFRR** (Node Failure Recovery Rate): 节点失效恢复率
- **RCRR** (Requirement Change Recovery Rate): 需求变更恢复率
- **ART** (Average Recovery Time): 平均恢复时间
- **Privacy Violations**: 隐私违规次数
- **Token Cost**: Token 消耗

## 结果示例

Mock 模式典型结果（3 seeds）：

| System | Score | TCR | SSR | Recovery |
|--------|------:|----:|----:|---------:|
| NexusFlow | 0.7500 | 100% | 100% | 64.4% |
| StaticPipeline | 0.5944 | 48.2% | 89.0% | 51.1% |
| FixedDAG | 0.5944 | 48.2% | 64.7% | 33.1% |
| FullContextMultiAgent | 0.5389 | 29.6% | 80.5% | 47.0% |
| PlainSingleAgent | 0.4500 | 0.0% | 77.6% | 46.7% |
