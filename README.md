<div align="center">

# NexusFlow

**面向超长程复杂任务的群体智能引擎**

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/Python-3.10%2B-blue.svg)]()
[![Version](https://img.shields.io/badge/Version-2.7-green.svg)]()
[![Code Size](https://img.shields.io/badge/Code-433%20Python%20files%20%7C%2037%2B%20modules-orange.svg)]()
[![Benchmarks](https://img.shields.io/badge/Benchmarks-4%20Stages%20%7C%2050%20Steps%20E2E-red.svg)]()

*Where cognitive diversity meets dynamic topology.*

</div>

---

## 核心定位

**框架工程 > 模型堆叠** —— NexusFlow 不是又一个 Agent 框架，而是第一个实现**认知分工（Cognitive Division of Labor, CDoL）**的群体智能引擎。不同于传统的任务分割式多 Agent 系统，NexusFlow 通过**主动制造信息不对称**，迫使每个 Agent 发展出从他人输出中逆向推断对方所见上下文的能力，从而产生超越任何单 Agent 的推理深度。

### 三层证据链

| 证据层 | 来源 | 核心发现 |
|--------|------|----------|
| 🔬 因果验证 | [Joel Niklaus (Hugging Face)](https://x.com/joelniklaus) — 冻结 DeepSeek-V4-Pro 权重，仅优化外层 Harness | 法律 Agent 基准 **3.5% → 80.1%**，追平 Claude Sonnet 4.6，成本仅 1/7 |
| 📊 生产实证 | [Braintrust](https://www.braintrust.dev/) — 1,781 条真实 Agent 轨迹 | 框架对成功率的影响力是模型的 **7.6 倍**（5.3% vs 0.7%） |
| ✅ 自身验证 | NexusFlow 四阶段递进 Benchmark | 质量门禁触发率 100%，50 步端到端全流程验证 |

> *"Benchmark 测到的永远不是裸模型，而是'模型+Harness'的组合能力。最大的性能改进往往来自简单的自动化步骤，而非消耗大量 Token 去修改提示词。"*
> — Joel Niklaus, Hugging Face

---

## 核心特性

- **CDoL 认知分工引擎**（1,960 行）：六种视角分解策略 + 三轮有损通信协议 + FusionJudge 虚假一致检测，将"信息不对称"从缺陷转化为认知资源
- **自适应上下文管理器**（1,642 行）：解决清华 & OpenBMB 发现的"大窗口懒惰症"——上下文越大，Agent 越倾向浅层推理
- **三层信息架构**（AgentInformationPolicy，511 行）：全局视野层 / CDoL 参与层 / 旁观记录层，为每个 Agent 分配角色化 ContextMask
- **动态拓扑路由器**（869 行）：运行时重建 Agent 协作图，支持五种拓扑模式（Sequential / Parallel / Tree / Star / Dynamic）
- **端边云三层调度器**（535 行）：隐私优先调度，MiMo + DeepSeek 兜底策略
- **统一编排器**（NexusOrchestrator，478 行）：自动路由分类（simple / research / coding / cdol），任务完成后自动触发 Archivist 蒸馏归档

---

## 架构图

```
┌─────────────────────────────────────────────────────────────────┐
│                        NexusFlow 系统架构                         │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌─────────┐    ┌──────────────┐    ┌──────────────────────┐   │
│  │  用户    │───▶│  Dashboard   │◀──▶│  FastAPI Server      │   │
│  │         │    │  (WebSocket) │    │                      │   │
│  └─────────┘    └──────────────┘    └──────────┬───────────┘   │
│                                                │                │
│                           ┌────────────────────┼───────────┐   │
│                           ▼                                 ▼   │
│                   ┌───────────────┐              ┌──────────┐ │
│                   │ NexusOrchestrator │              │ LLM Router│ │
│                   └───────┬───────┘              └────┬─────┘ │
│                           │                             │       │
│         ┌─────────────────┼─────────────────────────┤       │
│         ▼                 ▼                         ▼       │
│  ┌────────────┐    ┌────────────┐    ┌──────────────────────┐ │
│  │ CDoL Engine│    │   Memory   │    │  Agent Pool (10个)   │ │
│  │            │    │  Manager   │    │                      │ │
│  │ • Round 0  │    │            │    │ ☁️ Cloud:           │ │
│  │ • Round 1  │    │  • Vector  │    │   Coordinator       │ │
│  │ • Round 2  │    │  • Recall  │    │   Strategist        │ │
│  │ • Fusion   │    │  • Archival│    │   Archivist         │ │
│  │            │    │            │    │   Critic            │ │
│  └────────────┘    └────────────┘    │   Synthesizer       │ │
│                                       │   Researcher        │ │
│                                       ├──────────────────────┤ │
│                                       │ 🖥️ Edge:           │ │
│                                       │   Coder             │ │
│                                       │   Analyst           │ │
│                                       ├──────────────────────┤ │
│                                       │ 📱 Endpoint:        │ │
│                                       │   Observer          │ │
│                                       │   Monitor          │ │
│                                       └──────────────────────┘ │
│                                                        │       │
│                         ┌───────────────────────────────┼───┐   │
│                         ▼                               ▼   │   │
│                  ┌─────────────┐              ┌─────────────┐ │   │
│                  │   Ollama    │              │  DeepSeek   │ │   │
│                  │  (本地)     │              │   (云端)    │ │   │
│                  │ deepseek-r1 │              │ deepseek-chat│ │   │
│                  │ qwen3.5    │              │             │ │   │
│                  └─────────────┘              └─────────────┘ │   │
└─────────────────────────────────────────────────────────────────┘
```

---

## 实验验证

四阶段递进 Benchmark，覆盖单步优化到 50 步端到端全流程：

### Stage-1：NOAA 精度翻倍 & WHO 排名纠错

| 指标 | 单 Agent | NexusFlow (CDoL) | 提升 |
|------|:--------:|:----------------:|:----:|
| NOAA 综合 MAPE | 18.87% | **9.37%** | **-50%** |
| WHO 健康指数排名 | 错误（俄罗斯 #1） | **正确（中国 #1）** | 排名纠错 |
| 质量指标 | 归一化失真导致错误结论 | Strategist 设计合理权重后结论正确 | 系统性偏差消除 |

### Stage-2：10 角色评分跃升

| 指标 | 单 Agent | 6 角色 | 10 角色 |
|------|:--------:|:------:|:-------:|
| NOAA 评分 | 64 | 85 | **90** |
| WHO 评分 | 74 | 86 | **90** |
| 平均提升 | — | +24% | **+30%** |
| 耗时 | — | — | **-90.8%** |

### Stage-3：质量门禁——知道"自己不知道"

| 对比维度 | 单 Agent | NexusFlow |
|----------|:--------:|:---------:|
| 错误结论率 | **≈100%** | **0%** |
| 质量门禁触发率 | — | **100%**（2/2 任务检测数据异常） |
| revision_rate | — | **1.0**（所有 Agent 修正了结论） |
| synergy_gain | — | **1.25**（真实协同增益） |

> Stage-3 核心发现：当数据存在严重质量问题时，NexusFlow 主动拒绝输出——WHO 任务因维度严重缺失（仅 1/7 维度可用）触发门禁。在真实科研场景中，**"无法确诊"远比"误诊"安全**。

### Stage-4：50 步端到端科研全流程验证

| 指标 | 数值 |
|------|------|
| 总步数 | 50 步（38 步真实执行 + 12 步模拟） |
| 核心模块覆盖 | 14 / 14 = **100%** |
| 拓扑动态切换 | **9 次**，4 种模式全覆盖 |
| CDoL 三轮辩论共识度 | 0.1 → 0.3 → 0.7 → **0.95** |
| DeepSeek API 调用 | 28 次 / ~63,869 tokens |
| 产物文件数 | 52 个 / ~680 KB |
| 质量门禁 | Critic 第一轮即识别生态学谬误（根本性方法论缺陷） |

**CDoL 三轮辩论详情**：

| 轮次 | 焦点 | 共识度 |
|------|------|:------:|
| R1 — 方法论审查 | 生态学谬误、遗漏变量偏差、因果推断局限 | 0.1 → 0.3 |
| R2 — 结果可靠性 | 效应量意义、样本代表性、模型选择偏差 | 0.3 → 0.7 |
| R3 — 整体结论 | 外部效度、政策可行性、实际贡献度 | 0.7 → 0.95 |

### 横向对比：NexusFlow vs AutoGen vs CrewAI

统一任务（WHO BRICS 五国分析）、统一 LLM（DeepSeek），10 维度评分：

| 框架 | 总分 | 耗时 | API 调用 | Tokens |
|------|:----:|:----:|:--------:|:------:|
| **NexusFlow** | **92** | 69.5s | 43 次 | ~20,500 |
| AutoGen | 88 | 36.5s | 17 次 | 6,329 |
| CrewAI | 85 | 42.0s | 18 次 | 5,171 |

> 关键发现：同一 LLM 下架构差异决定性能上限。NexusFlow 在**交叉验证**维度得分 8 分，AutoGen/CrewAI 均为 4 分——领先 100%。4 倍 tokens 的额外投入换来 4-7 分的实质性质量提升。

<details>
<summary>📋 实验方法说明</summary>

- **NexusFlow**: 真实代码管线运行，CDoL 引擎完整执行
- **AutoGen / CrewAI**: Python 3.13 环境下 AutoGen ext 模块不可用、CrewAI 安装失败（hash 校验不通过），因此使用相同 LLM + 等价提示词**模拟**其核心交互模式（AutoGen=对话式、CrewAI=顺序式），确保公平对比
- 详细方法说明见 [examples/horizontal_comparison/comparison_report.md](examples/horizontal_comparison/comparison_report.md)

</details>

---

## 实验案例

所有实验产物完整开源，可复现、可审计：

| 阶段 | 实验 | 核心发现 | 目录 |
|------|------|----------|------|
| Stage 1 | 单Agent vs 6角色CDoL | NOAA MAPE 18.87%→9.37%，WHO 排名纠错 | [`examples/stage1_single_vs_6roles/`](examples/stage1_single_vs_6roles/) |
| Stage 2 | 6角色 vs 10角色CDoL | 评分 85→90，API调用 -53%，Critic 0 次被驳回 | [`examples/stage2_6roles_vs_10roles/`](examples/stage2_6roles_vs_10roles/) |
| Stage 3 | 完整系统真实管线 | 质量门禁触发率 100%，ContextMask 真实裁剪 | [`examples/stage3_full_system/`](examples/stage3_full_system/) |
| Stage 4 | 50步端到端全流程 | 14模块100%覆盖，9次拓扑切换，共识度 0.1→0.95 | [`examples/stage4_fifty_steps/`](examples/stage4_fifty_steps/) |
| 横向对比 | NexusFlow vs AutoGen vs CrewAI | 交叉验证能力领先 100% | [`examples/horizontal_comparison/`](examples/horizontal_comparison/) |

---

## 端边云三层架构

| 层级 | 模型 | Agent | 说明 |
|------|------|-------|------|
| ☁️ 云端 | DeepSeek API | Coordinator, Strategist, Archivist, Critic, Synthesizer, Researcher | 高质量推理 + 广知识 |
| 🖥️ 边端 | Ollama deepseek-r1:14b | Coder, Analyst | 本地大模型，计算密集任务 |
| 📱 终端 | Ollama qwen3.5:9b | Observer, Monitor | 本地小模型，轻量监控 |

---

## Agent 角色表

| Agent | 角色 | 层级 | 职责 |
|-------|------|------|------|
| 🧭 Coordinator | 编排者 | ☁️ 全局 | 任务分发、进度协调、冲突裁决 |
| 📚 Archivist | 档案师 | ☁️ 全局 | 经验蒸馏、知识沉淀 |
| 📈 Strategist | 策略师 | 🔗 CDoL | 任务分解、视角设计 |
| 🔥 Critic | 批评家 | 🔗 CDoL | 对抗质疑、逻辑审查、质量门禁 |
| 🔬 Synthesizer | 整合师 | 🔗 CDoL | 多视角融合、矛盾解决 |
| 🔍 Researcher | 研究员 | 🔗 CDoL | 联网搜索、文献分析 |
| 💻 Coder | 编码师 | 🖥️ CDoL | 代码开发、工具实现 |
| 📊 Analyst | 分析师 | 🖥️ CDoL | 数据分析、模式识别 |
| 👁 Observer | 观察者 | 📱 旁观 | 元观察、偏见检测 |
| 📡 Monitor | 监控者 | 📱 旁观 | 健康检查、异常检测 |

---

## 项目规模

| 指标 | 数值 |
|------|------|
| 总文件数 | **889** |
| Python 文件 | **433** |
| 仓库大小 | **~14 MB** |
| 核心模块 | **37+** |
| Agent 角色 | 10 |
| 内置工具 | 17 |
| 记忆层级 | 4 层 |
| CDoL 分解策略 | 6 种 |
| 路由拓扑模式 | 5 种 |

---

## 快速开始

### 环境要求

- Python 3.10+
- [Ollama](https://ollama.com/) (本地部署)
- DeepSeek API Key (可选，用于云端 Agent)

### 安装

```bash
# 克隆仓库
git clone https://github.com/tsingxuanhan/NexusFlow.git
cd NexusFlow

# 安装依赖
pip install -r requirements.txt

# 配置环境变量
cp config/.env.example .env
# 编辑 .env 填入你的 API Key
```

### 启动

```bash
# Windows
config\start.bat

# Linux/Mac
python server/nexusflow_server.py
```

访问 Dashboard: http://localhost:8900

---

## 配置说明

### 环境变量 (config.py 或 Shell)

```python
# config.py — 复制 config.example.py 并修改
DEEPSEEK_API_KEY = "your_api_key_here"        # 或 export DEEPSEEK_API_KEY=...
DEEPSEEK_ENDPOINT = "https://api.deepseek.com/v1/chat/completions"

# Ollama (端边云架构)
OLLAMA_BASE_URL = "http://localhost:11434"
OLLAMA_PRO_MODEL = "deepseek-r1:14b"
OLLAMA_LITE_MODEL = "qwen3.5:9b"

# Dashboard
DASHBOARD_PORT = 8900
```

### Ollama 模型安装

```bash
ollama pull deepseek-r1:14b
ollama pull qwen3.5:9b
```

---

## 参考资料

| 来源 | 说明 |
|------|------|
| [技术文档 v2.7](docs/NexusFlow技术文档v2.7.md) | NexusFlow 完整技术文档（89.5 KB） |
| [Braintrust AI Evaluation Platform](https://www.braintrust.dev/) | 1,781 条真实轨迹——框架影响力 7.6 倍于模型 |
| [Joel Niklaus — Don't Train the Model, Evolve the Harness](https://x.com/joelniklaus) | 冻结权重仅优化 Harness，3.5% → 80.1% |
| [清华 & OpenBMB — 大窗口懒惰症研究](https://arxiv.org/abs/2606.15378) | Large-Window Laziness 现象的 Transformer 层证据 |
| [Arbor — Hypothesis-Tree Refinement](https://arxiv.org/abs/2606.11926) | 跨任务 Insight 回传机制的启发来源 |

---

## 技术架构

详见 [docs/architecture.md](docs/architecture.md)

---

## License

[MIT License](LICENSE) - 详见 [LICENSE](LICENSE)

---

<div align="center">

**框架工程 > 模型堆叠。**

*NexusFlow: Where cognitive diversity meets dynamic topology.*

</div>
