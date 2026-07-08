# Stage-4: 50步端到端科研全流程

> 从单一任务到完整科研Pipeline——验证NexusFlow的端到端科研能力

---

## 🎯 实验目标

验证NexusFlow能否执行**50步端到端科研全流程**，覆盖从文献检索到论文生成的完整科研Pipeline。这是最复杂的实验阶段，验证系统在真实科研场景中的全链路能力。

## 🔬 实验方法

| 项目 | 配置 |
|------|------|
| **任务主题** | 基于NOAA+WHO数据的气候-健康关联分析 |
| **竞赛编号** | XH-202631（荣耀揭榜挂帅）|
| **步骤总数** | 50步 |
| **Agent角色** | 10个（Coordinator, Strategist, Researcher, Analyst, Coder, Critic, FusionJudge, Archivist, Reviewer, Observer）|
| **核心模块** | 14个（TaskRouter, MetaPlanner, ResearchLoop, DataAnalyzer, CodingExecutor, CriticEngine, FusionEngine, ContextManager等）|
| **数据源** | NOAA CDO GSOY + WHO GHO |
| **CDoL轮次** | 3轮（方法论审查→结果可靠性→整体结论）|

### 50步阶段划分

| 阶段 | 步骤范围 | 步数 | 主要Agent | 拓扑模式 |
|------|---------|------|----------|----------|
| 文献检索与分析 | 1-8 | 8 | Coordinator, Researcher | Chain→Parallel→Chain |
| 假设生成 | 9-13 | 5 | Strategist, Critic | Chain→Debate |
| 数据获取与清洗 | 14-20 | 7 | Researcher, Coder, Analyst | Parallel→Chain |
| 实验设计 | 21-26 | 6 | Strategist, Critic, FusionJudge | Chain→Debate→Chain |
| 数据分析 | 27-34 | 8 | Coder, Analyst, Critic | Parallel→Tree→Debate |
| 代码实现 | 35-40 | 6 | Coder, Critic, FusionJudge | Chain→Debate |
| 结果综合 | 41-45 | 5 | Analyst, Strategist, Critic, FusionJudge | Chain→Debate |
| 报告生成 | 46-50 | 5 | Archivist | Chain |
| **合计** | **1-50** | **50** | **10角色** | **9次拓扑切换** |

### 研究问题

- **RQ1**: 年平均温度变化与呼吸系统疾病负担之间是否存在显著关联？
- **RQ2**: 极端降水事件与心血管疾病之间是否存在滞后关联效应？
- **RQ3**: 气候-健康关联在不同WHO区域是否存在异质性？

## 📊 核心结果

### 执行统计

| 指标 | 数值 |
|------|------|
| 真实执行步骤 | 全部50步 |
| 拓扑切换次数 | 9次（Chain/Parallel/Tree/Debate）|
| 调用模块数 | 14个 |
| 代表性产物 | 15个关键文件 |
| CDoL轮次 | 3轮完整执行 |

### 代表性产物（15个精选文件）

| 文件 | 步骤 | 内容 |
|------|------|------|
| `step01_task_dag.json` | 1 | 任务分解DAG（9791 chars）|
| `step03_framework.md` | 3 | 分析框架（变量体系+统计方法）|
| `step09_13_hypothesis_generation.md` | 9-13 | 三个假设定义+审查 |
| `step14_noaa_temperature_data.json` | 14 | NOAA温度数据 |
| `step16a_who_respiratory_indicators.json` | 16 | WHO呼吸疾病数据 |
| `step18_data_cleaning_script.py` | 18 | 数据清洗代码 |
| `step19_quality_report.md` | 19 | 数据质量报告 |
| `step27_correlation_analysis_code.py` | 27 | 相关性分析代码 |
| `step33_cdol_round1_critic.md` | 33 | CDoL Round 1 Critic质疑 |
| `step36_cdol_protocol_code.py` | 36 | CDoL协议实现代码 |
| `step40_cdol_round2_fusion.md` | 40 | CDoL Round 2 融合 |
| `step45_cdol_round3_fusion.md` | 45 | CDoL Round 3 最终融合 |
| `step47_methods_section.md` | 47 | 论文方法部分 |
| `step49_abstract_conclusion.md` | 49 | 摘要+结论 |
| `step50_quality_check.md` | 50 | 最终质量检查 |

### CDoL引擎（engine.py）

独立运行的CDoL引擎版本，展示核心协议：
- PerspectiveDecomposer: 视角分解
- CommunicationLayer: 有损通信
- FusionJudge: 融合判定
- 支持3轮CDoL协议完整执行

## 📈 与前Stage的对比

| Stage | 任务复杂度 | 步骤数 | 拓扑切换 | 模块数 |
|-------|:---------:|:------:|:--------:|:------:|
| Stage-1 | 单任务诊断 | ~10 | 无 | 0（模拟）|
| Stage-2 | 单任务+质疑 | ~20 | 无 | 0（模拟）|
| Stage-3 | 双任务完整系统 | ~30 | 无 | 14 |
| **Stage-4** | **跨域科研全流程** | **50** | **9次** | **14** |

**递进关系**: Stage-3证明了真实系统的价值，Stage-4进一步验证系统能执行**跨域科研全流程**——从NOAA气候数据到WHO健康数据的关联分析，涵盖文献、假设、数据、分析、论文全链路。

## 🔑 关键发现

> **NexusFlow能执行50步端到端科研全流程，支持9次拓扑动态切换（Chain→Parallel→Tree→Debate），15个代表性产物覆盖从任务分解到论文生成的完整链路。** 这是CDoL协议在真实科研场景中的最全面验证。

---

*详细文档见 [stage4_task_design.md](stage4_task_design.md) 和 [stage4_execution_report.md](stage4_execution_report.md)*
*CDoL引擎代码见 [engine.py](engine.py)（需设置 DEEPSEEK_KEY）*
*代表性产物见 [artifacts/](artifacts/) 目录*
