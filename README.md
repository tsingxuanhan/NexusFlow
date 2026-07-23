<div align="center">

# NexusFlow

**面向超长程复杂任务的群体智能引擎**

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/Python-3.10%2B-blue.svg)]()
[![Version](https://img.shields.io/badge/Version-3.3.0-green.svg)](CHANGELOG.md)
[![Tests](https://img.shields.io/badge/Tests-357%20Passing-brightgreen.svg)](.github/workflows/tests.yml)
[![Docker](https://img.shields.io/badge/Docker-Ready-blue.svg)](Dockerfile)
[![Security](https://img.shields.io/badge/Security-Gitleaks-blue.svg)](SECURITY.md)
[![Benchmarks](https://img.shields.io/badge/Benchmarks-7%20Stages%20%7C%20PinchBench-red.svg)]()
[![LOC](https://img.shields.io/badge/LOC-82,557-blue.svg)]()

*Where cognitive diversity meets dynamic topology.*

</div>

---

## 为什么需要 NexusFlow？

当前多智能体框架的主流做法是「堆模型」——更多 Agent、更大上下文、更贵的模型。但真实任务告诉我们一个反直觉的事实：

> **框架工程的影响力是模型本身的 7.6 倍。**（[Braintrust 1,781 条轨迹实证](https://www.braintrust.dev/)）

这意味着什么？同样的裸模型，放在一个设计良好的框架里，性能可以从 3.5% 跳到 80.1%（[Joel Niklaus 法律 Agent 实验](https://x.com/joelniklaus)）。**性能瓶颈不在模型，而在 Harness。**

NexusFlow 正是为了解决这个问题而诞生。我们不是又做了一个「多 Agent 聊天室」，而是提出了一种新的范式：

**认知分工（Cognitive Division of Labor, CDoL）** —— 主动制造信息不对称，迫使每个 Agent 只能看到任务的局部切片，必须从他人输出中逆向推断上下文。这种"受限视角"反而产生了超越任何单 Agent 的推理深度，就像真实组织中专业分工带来的认知增益。

配合**端边云三层调度**、**动态拓扑路由**、**四层记忆系统**和**质量门禁**，NexusFlow 在 82,557 行代码中构建了一个真正为超长程复杂任务设计的群体智能引擎。

> *"Benchmark 测到的永远不是裸模型，而是'模型+Harness'的组合能力。最大的性能改进往往来自简单的自动化步骤，而非消耗大量 Token 去修改提示词。"*
> — Joel Niklaus, Hugging Face

---

## ✨ 核心特性

### 🧠 认知分工引擎（CDoL）

- **6 种视角分解**：同一任务被拆分为 Researcher / Executor / Reviewer / Planner / Miner / Assayer 六个信息切片
- **有损通信机制**：Agent 之间不共享原始输入，只交换压缩后的中间结论
- **虚假一致检测**：当多个 Agent 给出表面一致但推理路径矛盾的答案时自动触发
- **2-3 轮辩论平台期**：ablation 实验证明 2-3 轮即可达到质量收敛，无需无限辩论
- **核心效果**：NOAA 气候任务 64→90 分，WHO 健康评估 74→90 分

### 🌐 动态拓扑路由

- **5 种运行时拓扑**：`simple` / `research` / `coding` / `cdol` / `adaptive`
- **任务感知路由**：基于任务描述自动分类，运行时动态重建 Agent 协作图
- **Score-based 策略**：相比 Random/Static，置信度提升 35%+，延迟降低 42%

### 🏗️ 端边云三层调度

- **云端**（DeepSeek API）：Coordinator, Planner, Archivist, Reviewer, Caster, Researcher
- **边端**（Ollama 本地）：Executor, Miner — 敏感数据不出本机
- **终端**（Ollama 本地）：Assayer, Artisan — 边缘设备轻量化执行
- **隐私优先**：敏感任务可完全本地化执行

#### 🔬 端边云实机验证（真实LLM推理）

> 详见 [`examples/edge_cloud_scheduling/real_machine_report.md`](examples/edge_cloud_scheduling/real_machine_report.md)

与模拟实验不同，实机验证使用**真实LLM端点**执行推理：

| 层级 | 模型 | 端点 | 隐私 |
|:----:|:-----|:-----|:----:|
| 📱 Edge(端侧) | qwen3.5:9b (6.6GB) | Ollama 本地 | ✅ |
| 🖥️ Fog(边缘) | deepseek-r1:14b (9GB) | Ollama 本地 | ✅ |
| ☁️ Cloud(云端) | deepseek-chat | DeepSeek API | ❌ |

**验证规模**：27次真实LLM调用 | 11次EdgeCloudScheduler调度决策 | 2次层间迁移 | 3次容错Fallback

**关键结果**：

| 指标 | 混合调度 | 纯云端 | 差异 |
|:-----|:--------:|:------:|:----:|
| 成功率 | 8/8 (100%) | 8/8 (100%) | — |
| 总成本 | ¥0.0002 | ¥0.0016 | **-88%** |
| 隐私合规 | 2/8 | 0/8 | **+2** |
| 平均质量 | 0.912 | 0.974 | -0.061 |

使用项目真实的 `EdgeCloudScheduler` 类（`register_tier()` / `schedule()` / `migrate()` / `update_resource_state()`），非简化版重新实现。


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
- **API 文档自动生成**：pdoc + GitHub Pages
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

## 📊 关键数字

| 指标 | 数据 | 说明 |
|------|------|------|
| 框架 vs 模型影响力 | **7.6×** | [Braintrust 1,781 条轨迹](https://www.braintrust.dev/) |
| 法律 Agent Harness 优化 | 3.5% → **80.1%** | [Joel Niklaus](https://x.com/joelniklaus) |
| PinchBench 25 Hard Cases | NF **+6.7%** | iterative_code_refine **+200%** |
| WorkBuddy 宏观经济 | 加权 **+23.4%** | GDP 命中率 **+20pp** |
| 80 步全量 Benchmark | 质量 +2.6% | Token **-6.2%**，耗时 **-14.9%** |
| CDoL 三阶段递进 | 64→85.5→90 | SA → 6 角色 → 10 角色 |
| 质量门禁 | 错误率 **0%** | 触发率 100%，SA ≈100% |
| 四框架横向对比 | **75.0** | AutoGen 72.0 / CrewAI 61.5 / LangGraph 63.8 |
| 路由策略 Score-based | 置信度 **0.616** | 延迟 738ms，负载标准差最低 |

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

# 查看 CLI 帮助
nexusflow --help
```

<details>
<summary>🛠️ 开发模式</summary>

```bash
pip install -e ".[dev]"
make test        # 运行测试
make lint        # 代码检查
make format      # 代码格式化
make check       # 全套检查（lint + format + test）
make docker-build  # 构建 Docker 镜像
```
</details>

---

## 🏗️ 核心架构

**👉 [完整架构文档 →](docs/ARCHITECTURE.md)**

```
┌──────────────────────────────────────────────────────────┐
│               NexusOrchestrator (路由)                     │
│          simple / research / coding / cdol / adaptive      │
└───────────────────┬──────────────────────────────────────┘
                    │
        ┌───────────┼───────────┐
        ▼           ▼           ▼
┌─────────────┐ ┌──────────┐ ┌────────────────┐
│   CDoL      │ │  Memory  │ │  Agent Pool    │
│   Engine    │ │  Manager │ │  (10 Agents)   │
│             │ │          │ │  ☁️ 6  🖥️ 2   │
│ 6视角分解   │ │ 4层记忆  │ │  📱 2          │
│ 有损通信    │ │ RRF混合  │ │                │
│ 虚假一致检测│ │ 检索     │ │ 5种拓扑模式    │
└─────────────┘ └──────────┘ └────────────────┘
        │           │              │
        └───────────┼──────────────┘
                    ▼
         ┌─────────────────────┐
         │  Edge-Cloud Router  │
         │  ☁️ DeepSeek API    │
         │  🖥️📱 Ollama Local │
         └─────────────────────┘
```

**六大核心模块**：

| 模块 | 代码量 | 核心能力 |
|------|--------|----------|
| CDoL 认知分工引擎 | 2,058 行 | 6 种视角分解 + 三轮有损通信 + 虚假一致检测 |
| 自适应上下文管理器 | 1,642 行 | 对抗"大窗口懒惰症"，动态裁剪无用上下文 |
| 三层信息架构 | 511 行 | 全局视野 / CDoL 参与 / 旁观记录 |
| 动态拓扑路由器 | 869 行 | 运行时重建 Agent 协作图，任务感知路由 |
| 端边云调度器 | 535 行 | 隐私优先，云端+本地混合调度 |
| 统一编排器 | 479 行 | 自动路由分类 + 蒸馏归档 |
| BaseAgent + 7 Mixins | 2,743 行 | 模块化架构，职责单一，可独立扩展 |

---

## 🔬 实验验证

**👉 [完整实验数据 →](docs/EXPERIMENTS.md)**

七阶段递进 Benchmark，覆盖单步优化到真实宏观经济全量对比：

| 阶段 | 实验 | 核心发现 |
|------|------|----------|
| Stage 1-2 | 角色数递进 | 评分 64→85.5→90，耗时 -90.8% |
| Stage 3 | 质量门禁 | 错误结论率 **0%**（SA ≈100%） |
| Stage 4 | 50 步全流程 | 14 模块 100% 覆盖，共识度 0.1→0.95 |
| Stage 5 | 80 步真实对比 | 质量 +2.6%，Token -6.2%，3.25× 高质量步数 |
| Stage 6 | WorkBuddy 宏观 | 加权总分 +23.4%，GDP 命中率 +20pp |
| Stage 6b | L3 认知任务 | 辩论质量 +1.10，高风险决策显著领先 |
| Stage 7 | PinchBench 25 Hard | NF +6.7%，编码修复 +200% |
| 横向对比 | vs AutoGen/CrewAI/LangGraph | NF 75.0 领先，交叉验证 100% |
| 路由 Ablation | Score vs Random vs Static | 置信度 +35%，延迟 -42% |
| 轮次 Ablation | 2/3/4 轮辩论 | 2-3 轮平台期，4 轮过拟合 |

### 横向对比（四框架 · 复杂任务）

| 框架 | 得分 | 说明 |
|------|:----:|------|
| **NexusFlow v3.2** | **75.0** | CDoL + 动态拓扑 + 端边云 |
| AutoGen | 72.0 | 微软多 Agent 框架 |
| LangGraph | 63.8 | LangChain 图编排 |
| CrewAI | 61.5 | 角色协作框架 |

---

## 📦 产出展示

> 所有实验产物完整开源，可复现、可审计。

| 产出 | 说明 | 链接 |
|------|------|------|
| 📊 PinchBench 对比报告 | 25 Hard Cases SA vs NF 实时 HTML 报告 | [在线查看](https://www.coze.cn/s/RCDTzyE6r20/) |
| 📄 技术文档 v3.2 | 完整技术文档（2198 行，含 Stage 6-7 实验） | [在线查看](https://www.coze.cn/s/ow8wNkQqf0g/) |
| 🔬 Stage-7 实验 | 25 任务 SA vs NF 全量 JSON + 对比报告 | [`examples/stage7_pinchbench/`](examples/stage7_pinchbench/) |
| 🌍 Stage-6 WorkBuddy | 20 国×15 指标×41 年宏观经济对比 | [`examples/workbuddy_comparison/`](examples/workbuddy_comparison/) |
| 📈 Stage-5 80 步 | SA vs NF 逐步评分全量数据 | [`examples/stage5_eighty_steps/`](examples/stage5_eighty_steps/) |
| 🧪 CDoL Ablation | 2/3/4 轮最优平台期实验 | [`examples/demo_phase2_ablation_v3.py`](examples/demo_phase2_ablation_v3.py) |
| 🗺️ 路由实验 | Score/Random/Static 三策略对比 | [`examples/`](examples/) |

---

## 📐 项目规模

| 维度 | 数据 |
|------|------|
| 总文件数 | **903** |
| Python 文件 | **194** |
| Python 代码行 | **82,557** |
| 核心模块 | **89**（71 nexusflow + 18 tools） |
| Agent 角色 | **10** |
| 自动化测试 | **357** |
| 记忆层级 | **4** |
| CDoL 策略 | **6** |
| 拓扑模式 | **5** |
| Benchmark 阶段 | **7** |
| 最大单文件 | BaseAgent 1,211 行 + 7 Mixins 1,532 行 |

---

## 🗺️ Roadmap

- [ ] **Nemotron Embed 集成**：NVIDIA NIM 向量检索增强记忆层（代码已就绪，P0-P2 完成）
- [ ] **Dashboard v4**：Tabler 暗色主题实时监控面板
- [ ] **Stage-8 真实部署 Benchmark**：端边云三层物理设备实测
- [ ] **Multi-Modal CDoL**：将认知分工扩展到视觉+代码+文本多模态任务
- [ ] **Agent Marketplace**：社区贡献的 Agent 角色即插即用
- [ ] **RL 路由优化**：用强化学习替代规则路由，端到端优化拓扑选择

---

## ❓ FAQ

<details>
<summary><b>NexusFlow 和 AutoGen / CrewAI / LangGraph 有什么区别？</b></summary>

核心区别在**信息流设计**。AutoGen/CrewAI 让 Agent 共享上下文对话；NexusFlow 主动制造信息不对称，每个 Agent 只看到角色切片。这种"受限视角"迫使 Agent 进行更深层的推理，而不是依赖上下文中的冗余信息。横向对比（Stage 7 + 四框架对比）显示 NexusFlow 在复杂任务上领先 3-13 分。
</details>

<details>
<summary><b>为什么叫"CDoL"？和普通的角色分工有什么不同？</b></summary>

传统角色分工只是"任务拆分"，每个 Agent 仍然能看到完整输入。CDoL 的核心创新是**有损通信**——Agent 之间不共享原始 prompt，只交换压缩后的中间结论。这模拟了真实组织中"专业壁垒"带来的认知增益：每个专家必须从他人的输出中推断全局上下文，这种推断过程本身就是深度思考。
</details>

<details>
<summary><b>必须用 DeepSeek API 吗？能用其他模型吗？</b></summary>

不是。NexusFlow 支持任何 OpenAI-compatible API（OpenAI / DeepSeek / Ollama / vLLM / LM Studio 等）。端边云配置只是默认推荐——云端 Agent 用大模型，边端/终端用小模型。你也可以全部跑在本地（`docker compose --profile local up`）。
</details>

<details>
<summary><b>「端边云」具体怎么部署？</b></summary>

三层对应三种计算资源：云端（DeepSeek API，6 个 Agent）处理推理密集型任务；边端（Ollama 本地，2 个 Agent）处理敏感数据；终端（Ollama 本地，2 个 Agent）在边缘设备上轻量化执行。你可以根据实际硬件灵活调整——没有 GPU 也可以全跑在云端。
</details>

<details>
<summary><b>质量门禁是怎么工作的？</b></summary>

每一步执行后，Reviewer Agent 会进行逻辑校验和事实核查。如果发现问题，Executor 必须修正后重新提交。Critic Agent 在更高层面检查多个 Agent 的输出是否表面一致但推理矛盾（虚假一致检测）。七阶段实验显示，门禁触发率 100%，错误结论率 0%。
</details>

<details>
<summary><b>我可以只跑一部分 Agent 吗？</b></summary>

可以。NexusFlow 的 5 种拓扑模式（simple/research/coding/cdol/adaptive）会自动按需调用不同子集的 Agent。简单任务只调 2-3 个 Agent，复杂任务才启用完整 10 Agent CDoL 流程。
</details>

---

## 📖 引用

如果 NexusFlow 对你的研究或项目有帮助，欢迎引用：

```bibtex
@software{nexusflow2026,
  title   = {NexusFlow: A Cognitive Division of Labor Framework for Multi-Agent Systems},
  author  = {Jing, Xuanhan},
  year    = {2026},
  version = {3.2.0},
  url     = {https://github.com/tsingxuanhan/NexusFlow}
}
```

---

## 📚 参考资料

| 来源 | 说明 |
|------|------|
| [技术文档 v3.2](docs/NexusFlow技术文档v3.2.md) | 完整技术文档（含 Stage 6-7 实验） |
| [系统架构](docs/ARCHITECTURE.md) | 架构图、Agent 角色、模块详情 |
| [实验验证](docs/EXPERIMENTS.md) | Stage 1-7 完整实验数据 |
| [API 文档](https://tsingxuanhan.github.io/NexusFlow/) | 自动生成的模块级 API 参考 |
| [变更日志](CHANGELOG.md) | 版本变更记录（v1.0 → v3.2） |
| [贡献指南](CONTRIBUTING.md) | 开发环境、提交规范 |
| [安全策略](SECURITY.md) | 漏洞报告流程 |
| [Braintrust](https://www.braintrust.dev/) | 1,781 条真实轨迹——框架影响力 7.6 倍于模型 |
| [Joel Niklaus](https://x.com/joelniklaus) | 冻结权重仅优化 Harness，3.5% → 80.1% |
| [清华 & OpenBMB](https://arxiv.org/abs/2606.15378) | Large-Window Laziness 研究 |
| [Arbor](https://arxiv.org/abs/2606.11926) | Hypothesis-Tree Refinement 启发来源 |

---

## 🤝 贡献

欢迎 PR 和 Issue！请先阅读 [贡献指南](CONTRIBUTING.md)。

核心开发方向：
- 🧪 新 Benchmark / 评测任务
- 🤖 新 Agent 角色 / Mixin 扩展
- 🔧 性能优化 / 内存压缩
- 📚 文档翻译 / 示例补充
- 🐛 Bug 修复 / 测试覆盖

---

## 📄 License

[MIT License](LICENSE)

---

<div align="center">

**框架工程 > 模型堆叠。**

*NexusFlow: Where cognitive diversity meets dynamic topology.*

⭐ 如果这个项目对你有帮助，欢迎 Star 支持！

</div>
