# NexusFlow Benchmark 实验数据

> 更新日期: 2026-07-14

## 目录结构

```
examples/
├── benchmark_summary.md          # 全阶段数据总表
├── stage1_single_vs_6roles/      # Stage-1: 单Agent vs 6角色CDoL
│   ├── README.md                 # 阶段说明
│   ├── noaa_comparison_report.md # NOAA对比报告
│   ├── who_comparison_report.md  # WHO对比报告
│   └── data/                     # 原始数据
│       ├── noaa/                 # NOAA原始API数据(5城市×多年)
│       └── noaa_v2/              # v2版对比结果
├── stage2_6roles_vs_10roles/     # Stage-2: 6角色 vs 10角色CDoL
│   ├── README.md
│   ├── comparison_report.md
│   ├── noaa_ten_roles_report.md
│   ├── who_ten_roles_report.md
│   └── data/noaa_ten_roles/      # 十角色NOAA原始数据(5维度)
├── stage3_full_system/           # Stage-3: 完整NexusFlow代码管线
│   ├── README.md
│   ├── stage3_full_system_report.md
│   ├── stage3_full_system.py     # 执行脚本
│   └── data/                     # 原始数据
│       ├── who/                  # WHO执行数据(cdol_result/execution_stats/agent_interactions)
│       └── noaa/                 # NOAA执行数据(analysis_summary/monitor_log)
├── stage4_fifty_steps/           # Stage-4: 50步端到端任务
│   ├── README.md
│   ├── stage4_execution_report.md
│   ├── stage4_task_design.md
│   ├── engine.py
│   └── data/                     # 原始数据
│       ├── artifacts/            # 77个中间产物(JSON/MD/PY)
│       └── scripts/              # 6个batch脚本+engine
├── stage5_eighty_steps/          # Stage-5: 80步公平对比
│   ├── README.md
│   ├── run_real_benchmark.py
│   └── data/                     # 原始数据(2.3MB)
│       ├── comparison.json       # 逐阶段汇总对比
│       ├── nf_results.json       # NexusFlow逐步骤详细结果
│       ├── sa_results.json       # Single-Agent逐步骤详细结果
│       ├── full_outputs_*.json   # 完整输出
└── horizontal_comparison/        # 横向对比: NexusFlow vs AutoGen vs CrewAI
    ├── README.md
    ├── comparison_report.md      # 完整对比报告
    ├── comparison_results.json   # 实验指标JSON
    ├── evaluation_scores.md      # 10维度评估明细
    ├── nexusflow_real_v2_output.md  # NexusFlow CDoL真实执行输出
    ├── autogen_output.md         # AutoGen真实执行输出
    ├── evaluate_real_outputs.py  # 确定性评估脚本
    └── ...                       # 其他脚本和输出
```

## 数据来源说明

| 阶段 | 执行方式 | 数据真实性 |
|------|---------|-----------|
| Stage-1 | 子Agent模拟CDoL流程 | NOAA/WHO数据真实，Agent交互模拟 |
| Stage-2 | 子Agent模拟10角色CDoL | NOAA/WHO数据真实，Agent交互模拟 |
| Stage-3 | NexusFlow完整代码管线 | **全部真实执行**（14个模块调用） |
| Stage-4 | 50步端到端真实执行 | **全部真实执行** |
| Stage-5 | 80步公平对比真实执行 | **全部真实执行**（Single-Agent vs NexusFlow） |
| 横向对比 | CDoL真实执行 + AutoGen真实 | **NexusFlow/AutoGen真实，CrewAI模拟** |

## 核心数据摘要

### 逐阶段提升幅度

| 模式 | NOAA | WHO | 平均 |
|------|:----:|:---:|:----:|
| 单Agent | 64 | 74 | 69 |
| 6角色CDoL | 85 | 86 | 85.5 |
| 10角色CDoL | 90 | 90 | 90 |

### 80步公平对比

| 指标 | Single-Agent | NexusFlow | 差异 |
|:-----|:-----------:|:---------:|:----:|
| 平均质量分 | 7.72 | 7.92 | +2.6% |
| 总耗时 | 1704s | 1450s | -14.9% |
| 总Token | 276,723 | 259,559 | -6.2% |

### 横向对比（WHO简单查询任务）

| 框架 | 得分 | 耗时 | API调用 | Tokens | 模式 |
|------|:----:|:----:|:-------:|:------:|:----:|
| AutoGen | 90.0 | 131.1s | 5 | 2,426 | real |
| NexusFlow | 84.5 | 89.8s | 7 | 18,799 | real (CDoL) |
| CrewAI | 85 | 42.0s | 18 | 5,171 | simulated |

> 注: 横向对比是简单查询任务，NexusFlow的核心优势在复杂任务（Stage-4/5）。
