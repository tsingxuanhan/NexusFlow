<div align="center">

# NexusFlow

**面向超长程复杂任务的群体智能引擎**

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/Python-3.10%2B-blue.svg)]()
[![Version](https://img.shields.io/badge/Version-3.6.0-green.svg)](CHANGELOG.md)
[![Tests](https://img.shields.io/badge/Tests-357%20Passing-brightgreen.svg)](.github/workflows/tests.yml)
[![Docker](https://img.shields.io/badge/Docker-Ready-blue.svg)](Dockerfile)
[![Benchmarks](https://img.shields.io/badge/Benchmarks-LHAB--NF%20%7C%208%20Stages%20%7C%20PinchBench-red.svg)]()
[![LOC](https://img.shields.io/badge/LOC-84,000+-blue.svg)]()

*Where cognitive diversity meets dynamic topology.*

</div>

---

## 为什么需要 NexusFlow？

当前多智能体框架的主流做法是「堆模型」——更多 Agent、更大上下文、更贵的模型。但真实任务告诉我们一个反直觉的事实：

> **框架工程的影响力是模型本身的 7.6 倍。**（[Braintrust 1,781 条轨迹实证](https://www.braintrust.dev/)）

这意味着什么？同样的裸模型，放在一个设计良好的框架里，性能可以从 3.5% 跳到 80.1%（[Joel Niklaus 法律 Agent 实验](https://x.com/joelniklaus)）。**性能瓶颈不在模型，而在 Harness。**

NexusFlow 正是为了解决这个问题而诞生。我们不是又做了一个「多 Agent 聊天室」，而是提出了一种新的范式：

**认知分工（Cognitive Division of Labor, CDoL）** —— 主动制造信息不对称，迫使每个 Agent 只能看到任务的局部切片，必须从他人输出中逆向推断上下文。这种"受限视角"反而产生了超越任何单 Agent 的推理深度，就像真实组织中专业分工带来的认知增益。

配合**可解释动态拓扑**、**端边云三层调度**、**四层记忆系统**和**质量门禁**，NexusFlow 在 84,000+ 行代码中构建了一个真正为超长程复杂任务设计的群体智能引擎。

> *"Benchmark 测到的永远不是裸模型，而是'模型+Harness'的组合能力。最大的性能改进往往来自简单的自动化步骤，而非消耗大量 Token 去修改提示词。"*
> — Joel Niklaus, Hugging Face

---

## 🏆 实证结果

### LHAB-NF 真实基准测试：NexusFlow vs Single Agent

> 2026-08-02 | DeepSeek V4 Flash | LLM-as-Judge 5维统一评分

同一批 LHAB-NF 任务分别由 NexusFlow（CDoL 多 Agent 协作）和 Single Agent（单次 LLM 调用，无协作）执行，使用相同的 LLM-as-Judge 评分体系。

| 指标 | NexusFlow (CDoL) | Single Agent | 对比 |
|------|:-:|:-:|:-:|
| **Judge 质量分** | **0.364** | 0.218 | **+67%** |
| **步骤完成率** | **100%** | 34% | **+196%** |
| 完全失败任务 | **0/6** | 3/9 | — |
| Token 消耗 | 38,391 | 14,956 | 2.6x |
| 平均耗时 | 588s | 127s | 4.6x |

<details>
<summary>按任务明细</summary>

| 任务 | NexusFlow | Single Agent | 差距 |
|------|:-:|:-:|:-:|
| 跨设备邮件摘要 (T1-E) | 0.420 | 0.356 | +0.064 |
| 跨设备日程协调 (T1-M) | 0.413 | **0.540** | -0.127 |
| 单文件功能实现 (T2-E) | 0.478 | 0.173 | **+0.305** |
| 跨模块系统重构 (T2-H) | 0.450 | **0.000** | **+0.450** |
| 单数据源统计报告 (T3-E) | 0.233 | 0.167 | +0.067 |
| 多源数据对比分析 (T3-M) | 0.237 | **0.000** | **+0.237** |

</details>

**关键发现**：
- 在复杂跨模块/多源任务上，Single Agent 完全无法处理（3 任务得 0 分），NexusFlow 全部完成
- 唯一 SA 胜出的任务（日程协调 T1-M）是相对简单的协调任务，说明 CDoL 对简单任务有额外开销——这正是动态路由的价值
- 综合来看，多 Agent 协作在质量上高出 67%，步骤覆盖率从 34% 提升到 100%

📋 [完整报告](benchmark_results/report.md) | 📊 [原始数据](benchmark_results/raw_results.json)

### 更多实验数据

> 所有实验均基于真实 LLM API 调用，数据和报告均可追溯。

| 实验 | 核心结果 | 报告 | 数据 |
|------|----------|:----:|:----:|
| PinchBench 25 Hard Cases | NF **+6.7%**，iterative_code_refine **+200%** | [📋](examples/stage7_pinchbench/STAGE7_PINCHBENCH_HARDCASES.md) | [📊](examples/stage7_pinchbench/results_nf/summary.json) |
| WorkBuddy 宏观经济 (20国×15指标×41年) | 加权 **+23.4%**，GDP 命中率 **+20pp** | [📋](examples/workbuddy_comparison/real_llm/D7_真实LLM实验报告.md) | [📊](examples/workbuddy_comparison/real_llm/real_benchmark_results.json) |
| 80 步全量 Benchmark (NF vs SA) | 质量 +2.6%，Token **-6.2%**，耗时 **-14.9%** | [📋](examples/benchmark_summary.md) | [📊](examples/stage5_eighty_steps/data/comparison.json) |
| CDoL 三阶段递进 | 64 → 85.5 → 90（SA → 6角色 → 10角色） | [📋](examples/benchmark_summary.md) | [📊](examples/stage1_single_vs_6roles/data/noaa/results_summary.json) |
| 四框架横向对比 | NF **75.0** vs AutoGen 72.0 / CrewAI 61.5 / LangGraph 63.8 | [📋](examples/horizontal_comparison/multi_framework_comparison_report.md) | [📊](examples/horizontal_comparison/multi_framework_comparison.json) |
| 质量门禁 | 错误率 **0%**（SA ≈ 100%），触发率 100% | [📋](examples/benchmark_summary.md) | — |
| 端边云实机验证 | 成本 **-88%**，质量仅差 0.061 | [📋](examples/edge_cloud_scheduling/real_machine_report.md) | [📊](examples/edge_cloud_scheduling/real_machine_data.json) |

---

## ✨ 核心特性

### 🧠 认知分工引擎（CDoL）

- **6 种视角分解**：同一任务被拆分为 Researcher / Executor / Reviewer / Planner / Miner / Assayer 六个信息切片
- **有损通信机制**：Agent 之间不共享原始输入，只交换压缩后的中间结论
- **虚假一致检测**：当多个 Agent 给出表面一致但推理路径矛盾的答案时自动触发
- **2-3 轮辩论平台期**：ablation 实验证明 2-3 轮即可达到质量收敛，无需无限辩论
- **动态终止**：FusionJudge 判定 converge 时提前退出，不浪费算力
- **核心效果**：NOAA 气候任务 64→90 分，WHO 健康评估 74→90 分

### 🌐 可解释动态拓扑

- **5 种运行时拓扑**：`simple` / `research` / `coding` / `cdol` / `adaptive`
- **任务感知路由**：基于任务描述自动分类，运行时动态重建 Agent 协作图
- **决策可解释**：每个路由决策都有因子贡献度分析（能力匹配/负载/跨层/偏好/延迟）
- **自适应优化**：UCB1 多臂老虎机算法从执行历史学习最优路由模式

```python
# 路由决策解释 — 每个决策都有因子归因
plan = router.route(task)
print(plan.explanation.human_readable)
# → "混合拓扑，4 Agent 协作：coordinator → researcher → executor → reviewer。置信度 78%。"
```

详见 [`examples/p2_topology_demo.py`](examples/p2_topology_demo.py)

### 🏗️ 端边云三层调度

- **云端**（DeepSeek API）：Coordinator, Planner, Archivist, Reviewer, Caster, Researcher
- **边端**（Ollama 本地）：Executor, Miner — 敏感数据不出本机
- **终端**（Ollama 本地）：Assayer, Artisan — 边缘设备轻量化执行

实机验证（27 次真实 LLM 调用）：混合调度 vs 纯云端，成本 **-88%**，质量仅差 0.061。详见 [`examples/edge_cloud_scheduling/real_machine_report.md`](examples/edge_cloud_scheduling/real_machine_report.md)

### 📊 LHAB-NF 评测基准

专为 NexusFlow 设计的长程任务评测框架——3 大类 × 3 难度，13 项评测指标，7 种扰动注入。

```bash
python scripts/run_benchmark.py --suite --mode real --server-url http://localhost:8900
```

详见 [`docs/LHAB-NF_Design.md`](docs/LHAB-NF_Design.md) 和 [`docs/P3_Ablation_Design.md`](docs/P3_Ablation_Design.md)

### 🧬 四层记忆架构

| 层级 | 名称 | 用途 |
|------|------|------|
| L1 | Working Memory | 当前对话上下文 |
| L2 | Episodic Memory | 近期任务经验缓存 |
| L3 | Semantic Memory | 长期知识与事实库 |
| L4 | Archival Memory | 蒸馏后的永久知识（RRF 混合检索） |

### 🚦 质量门禁系统

- **三轮验证**：每步执行 → Reviewer 审核 → Critic 闭环
- **100% 触发率**，错误结论率 **0%**（单 Agent 约 100%）
- **共识度追踪**：任务全程记录 Agent 间共识度变化（0.1→0.95）

### 🛠️ 工程化就绪

- **Docker 一键部署**：`docker compose up -d` 即可运行
- **CLI 工具链**：`nexusflow doctor` / `serve` / `run` / `benchmark`
- **CI/CD 完整**：GitHub Actions 自动测试、Lint、Docker 构建、安全扫描
- **357 个自动化测试**：覆盖率 38%，持续扩展中
- **Mixin 模块化架构**：BaseAgent 拆分为 7 个职责单一的 Mixin 模块

---

## 🤖 十大 Agent 角色

NexusFlow 内置 10 个专业 Agent，每个角色有明确的认知边界和信息权限：

| 角色 | 层级 | 职责 | 信息权限 |
|------|------|------|----------|
| **Coordinator** ☁️ | 全局视野 | 任务分解、路由分发、进度协调 | 全量信息 |
| **Planner** ☁️ | 全局视野 | 策略规划、步骤编排、资源分配 | 全量信息 |
| **Researcher** ☁️ | CDoL 参与 | 信息检索、文献分析、数据收集 | 角色切片 |
| **Executor** 🖥️ | CDoL 参与 | 代码执行、工具调用、结果生成 | 角色切片 |
| **Reviewer** ☁️ | CDoL 参与 | 质量审核、逻辑校验、反馈闭环 | 角色切片 |
| **Miner** 🖥️ | CDoL 参与 | 数据挖掘、模式识别、特征提取 | 角色切片 |
| **Assayer** 📱 | CDoL 参与 | 结果化验、交叉验证、异常检测 | 角色切片 |
| **Caster** ☁️ | CDoL 参与 | 结果铸造、格式统一、输出封装 | 角色切片 |
| **Artisan** 📱 | CDoL 参与 | 工艺打磨、细节优化、质量提升 | 角色切片 |
| **Archivist** ☁️ | 旁观记录 | 蒸馏归档、知识沉淀、经验复用 | 仅中间结论 |

> **三层信息架构**：全局视野层（2 Agent 看全量）→ CDoL 参与层（7 Agent 按角色切片）→ 旁观记录层（1 Agent 仅看中间结论）。主动制造信息不对称是 CDoL 增益的核心来源。

---

## 🚀 快速开始

### 🐳 Docker（推荐）

```bash
git clone https://github.com/tsingxuanhan/NexusFlow.git && cd NexusFlow
cp .env.example .env   # 填入 API Key
docker compose up -d
```

访问 `http://localhost:8900` 即可使用。

<details>
<summary>需要本地大模型？</summary>

```bash
docker compose --profile local up -d   # 同时启动 Ollama
docker compose exec ollama ollama pull deepseek-r1:14b
```
</details>

### 📦 pip 安装

```bash
git clone https://github.com/tsingxuanhan/NexusFlow.git && cd NexusFlow
pip install -e .
nexusflow doctor    # 检查环境
nexusflow serve     # 启动服务
```

### ⚡ 快速体验

```bash
# 端到端 Demo（架构展示，无需 API Key）
python examples/demo_e2e_pinchbench.py --arch-only

# 完整 Demo（含 SA vs NF PinchBench 对比 + HTML 报告）
python examples/demo_e2e_pinchbench.py

# 可解释拓扑演示
python examples/p2_topology_demo.py

# LHAB-NF 评测基准
make benchmark

# 查看 CLI 帮助
nexusflow --help
```

<details>
<summary>🛠️ 开发模式</summary>

```bash
pip install -e ".[dev]"
```
</details>

---

## 📚 文档与测试

- **技术文档**：[NexusFlow技术文档v3.6.md](docs/NexusFlow技术文档v3.6.md)（完整架构说明）
- **项目事实**：[PROJECT_FACTS.md](PROJECT_FACTS.md)（数据唯一权威来源）
- **评测基准**：[LHAB-NF 设计文档](docs/LHAB-NF_Design.md)
- **消融实验**：[P3 实验设计](docs/P3_Ablation_Design.md)
- **API 文档**：[docs/api/index.html](docs/api/index.html)

```bash
# 运行全量测试
pytest tests/

# 运行特定测试
pytest tests/test_edge_cloud_scheduler.py
pytest tests/test_dynamic_router.py
```

---

## 📄 License

MIT License - see [LICENSE](LICENSE) for details.

---

<div align="center">

**NexusFlow** — *Where cognitive diversity meets dynamic topology.*

[GitHub](https://github.com/tsingxuanhan/NexusFlow) · [Issues](https://github.com/tsingxuanhan/NexusFlow/issues) · [Docs](docs/)

</div>
