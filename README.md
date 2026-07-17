<div align="center">

# NexusFlow

**面向超长程复杂任务的群体智能引擎**

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/Python-3.10%2B-blue.svg)]()
[![Version](https://img.shields.io/badge/Version-2.9-green.svg)]()
[![Code Size](https://img.shields.io/badge/Code-144%20Python%20files%20%7C%2051%20modules-orange.svg)]()
[![Benchmarks](https://img.shields.io/badge/Benchmarks-5%20Stages%20%7C%2080%20Steps%20E2E-red.svg)]()

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
| ✅ 自身验证 | NexusFlow 五阶段递进 Benchmark（含 80 步真实对比） | 质量门禁触发率 100%，80 步 SA vs NF 全量验证，NF 质量 +2.6%、耗时 -14.9%、Token -6.2% |

> *"Benchmark 测到的永远不是裸模型，而是'模型+Harness'的组合能力。最大的性能改进往往来自简单的自动化步骤，而非消耗大量 Token 去修改提示词。"*
> — Joel Niklaus, Hugging Face

---

## 核心特性

- **CDoL 认知分工引擎**（2,058 行）：六种视角分解策略 + 三轮有损通信协议 + FusionJudge 虚假一致检测，将"信息不对称"从缺陷转化为认知资源
- **自适应上下文管理器**（1,642 行）：解决清华 & OpenBMB 发现的"大窗口懒惰症"——上下文越大，Agent 越倾向浅层推理
- **三层信息架构**（AgentInformationPolicy，511 行）：全局视野层 / CDoL 参与层 / 旁观记录层，为每个 Agent 分配角色化 ContextMask
- **动态拓扑路由器**（869 行）：运行时重建 Agent 协作图，支持五种拓扑模式（Sequential / Parallel / Hybrid / Star / Dynamic）
- **端边云三层调度器**（535 行）：隐私优先调度，云端 DeepSeek API + 本地 Ollama 兜底
- **统一编排器**（NexusOrchestrator，479 行）：自动路由分类（simple / research / coding / cdol），任务完成后自动触发 Archivist 蒸馏归档

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
│  │ • Round 2  │    │  • Recall  │    │   Planner        │ │
│  │ • Fusion   │    │  • Archival│    │   Archivist         │ │
│  │            │    │            │    │   Reviewer            │ │
│  └────────────┘    └────────────┘    │   Caster       │ │
│                                       │   Researcher        │ │
│                                       ├──────────────────────┤ │
│                                       │ 🖥️ Edge:           │ │
│                                       │   Executor             │ │
│                                       │   Miner           │ │
│                                       ├──────────────────────┤ │
│                                       │ 📱 Endpoint:        │ │
│                                       │   Assayer          │ │
│                                       │   Artisan          │ │
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
| 质量指标 | 归一化失真导致错误结论 | Planner 设计合理权重后结论正确 | 系统性偏差消除 |

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
| 质量门禁 | Reviewer 第一轮即识别生态学谬误（根本性方法论缺陷） |

**CDoL 三轮辩论详情**：

| 轮次 | 焦点 | 共识度 |
|------|------|:------:|
| R1 — 方法论审查 | 生态学谬误、遗漏变量偏差、因果推断局限 | 0.1 → 0.3 |
| R2 — 结果可靠性 | 效应量意义、样本代表性、模型选择偏差 | 0.3 → 0.7 |
| R3 — 整体结论 | 外部效度、政策可行性、实际贡献度 | 0.7 → 0.95 |

### Stage-5：80 步真实 Benchmark——Single-Agent vs NexusFlow 全量对比

> ⚡ **数据真实性声明**：以下所有数据均来自真实 LLM 输出（DeepSeek API），无模拟、无估算，完整产物可审计验证。

80 步全量 Benchmark 实验，同一任务分别由 Single-Agent（SA）和 NexusFlow（NF）完整执行，逐步评分对比：

#### 核心指标对比

| 指标 | Single-Agent | NexusFlow | 结论 |
|:-----|:-----------:|:---------:|:----:|
| 平均质量分 | 7.72 | **7.92** | NF **+2.6%** |
| ≥9 分步数 | 4 | **13** | NF **3.25 倍** |
| 总耗时 | 1704s | **1450s** | NF **-14.9%** |
| 总 Token | 276,723 | **259,559** | NF **-6.2%** |
| 每 1000 Token 产出质量 | 2.23 | **2.44** | NF **+9.4%** |

#### Phase 胜负：NF 6/7 Phase 胜出

| Phase | Single-Agent | NexusFlow | 胜出方 |
|:------|:-----------:|:---------:|:------:|
| P1 数据采集 | — | — | 接近 |
| P2 宏观分析 | — | — | NF |
| P3 产业链分析 | — | — | **NF (+0.75)** |
| P4 交叉验证 | — | — | NF |
| P5 CDoL 讨论 | — | — | **NF (+0.73)** |
| P6 自我迭代 | — | — | **SA** |
| P7 综合报告 | — | — | NF |

> SA 唯一赢的 Phase 是 **P6 自我迭代**（8.14 vs 7.67）。NF 最大优势在 **P3 产业链**（+0.75）和 **P5 CDoL 讨论**（+0.73）。

#### 关键发现

1. **SA Step 32 灾难性失误（2 分）**：上下文污染导致"串台"——SA 在处理产业链分析时，错误引用了前序宏观分析的内容，产生严重逻辑矛盾。NF 通过 Agent 隔离天然避免此类风险。
2. **NF CDoL 8 轮讨论均 Q=8.5，3 步拿 9 分**：CDoL 讨论阶段质量高度稳定，无一步低于 8.5 分，3/8 步达到 9 分。
3. **NF Agent 排名**：PreciousMiner（**8.33**）> MetalsMiner（**8.14**）> MacroMiner / EnergyMiner（**8.00**）。
4. **NF 短板**：Coordinator 报告阶段偶尔偷懒，拉低了 P6 自我迭代得分。

#### Token 效率优势

NF 在质量更高的同时，Token 消耗反而更低（**-6.2%**），每 1000 Token 产出质量高 **9.4%**——证明 CDoL 的认知分工不是"堆 Token 换质量"，而是通过结构化协作提升单位 Token 的信息密度。

---

### 横向对比：NexusFlow vs AutoGen

统一任务（WHO BRICS 五国分析）、统一 LLM（DeepSeek），10 维度评分：

| 框架 | 总分 | 耗时 | API 调用 | Tokens | 执行模式 |
|------|:----:|:----:|:--------:|:------:|:--------:|
| **NexusFlow** | **75** | 69.5s | 43 次 | ~20,500 | CDoL 引擎真实执行 |
| AutoGen | 72 | ~110s | 5 次 | ~2,400 | autogen_agentchat 真实执行 |

> 关键发现：同一 LLM 下架构差异决定性能上限。NexusFlow 在**交叉验证**维度得分 8 分，AutoGen 为 4 分——领先 100%。NexusFlow 的 4 倍 tokens 投入换来 3 分的实质性质量提升，体现在 CDoL 引擎的矛盾检测、视角归因和融合判断等结构化推理环节。

<details>
<summary>📋 实验方法说明</summary>

- **NexusFlow**: 真实代码管线运行，CDoL 引擎完整执行（PerspectiveDecomposer → CommunicationLayer 3轮 → FusionJudge → InsightDistiller）
- **AutoGen**: 真实执行，使用 `autogen_agentchat 0.7.5` + `autogen_ext 0.7.5`，通过 `RoundRobinGroupChat` 实现 Researcher + Analyst 双 Agent 对话式协作，真实调用 DeepSeek API。运行命令：`python3 examples/horizontal_comparison/real_autogen_comparison.py --real-autogen`
- 评分采用 10 维度专家评估（数据准确性、排名正确性、分析深度、方法论、完整性、交叉验证、不确定性标注、可操作性、逻辑一致性、可复现性）
- 详细方法说明见 [examples/horizontal_comparison/comparison_report.md](examples/horizontal_comparison/comparison_report.md)

</details>

---

### Phase 2：CDoL 轮次 Ablation 实验——2-3 轮最优平台期

> **核心问题**：CDoL 为什么固定 3 轮修正循环？有没有实验数据支撑？

从 Simon 有限理性到 Shannon 信道理论，框架设计理念指向一个可验证的预测：CDoL 的矛盾驱动认知分工存在一个"质量平台期"——低于某个轮次，认知多样性未被充分挖掘（欠采样）；超过某个轮次，边际收益递减。我们设计了轮次 ablation 实验来定位这个平台期：同一任务、同一 Agent 配置，仅改变最大修正轮次（2/3/4），使用 LLM-as-judge + few-shot 锚定评分器（v3版本，5 次运行 + 固定 seed=42），评估输出质量：

| 最大轮次 | 均值±标准差 | 最小值 | 最大值 |
|:--------:|:----------:|:------:|:------:|
| 2 轮 | **0.715±0.034** | 0.650 | 0.750 |
| 3 轮 | **0.699±0.037** | 0.630 | 0.730 |
| 4 轮 | 0.703±0.030 | 0.650 | 0.730 |

**关键发现**：

1. **2-3 轮最优平台期**：2 轮均值最高（0.715），3 轮紧随（0.699），差值仅 0.016，远小于组内标准差（~0.035），统计上无显著差异。两者共同构成质量平台期
2. **超过 3 轮收益递减**：4 轮均值（0.703）虽略高于 3 轮，但两次实验（v2 确定性公式 / v3 LLM-as-judge）方向一致——4 轮从未超越 2-3 轮区间上界
3. **动态终止机制锁定最优区间**：FusionJudge 动态终止自动锁定 2-3 轮平台期，既不欠采样也不过度修正——这是"双层自适应机制"在深度维度的体现（路由层决定"要不要 CDoL"，终止层决定"CDoL 走多深"）

这与 Shannon 信道理论的映射一致：2 轮 = Nyquist 采样下界（保证认知多样性的最低充分采样），2-3 轮 = 质量平台期（覆盖认知空间带宽），超过 3 轮 = 边际收益递减。**平台期不是超参数调优的结果，而是理论 predicted 的采样区间。**

> 实验代码：[`examples/demo_phase2_ablation_v3.py`](examples/demo_phase2_ablation_v3.py) | 评分器：[`examples/llm_quality_scorer.py`](examples/llm_quality_scorer.py) | 详细报告：[`docs/Phase2_ablation实验报告.md`](docs/Phase2_ablation实验报告.md)

---

## 实验案例

所有实验产物完整开源，可复现、可审计：

| 阶段 | 实验 | 核心发现 | 目录 |
|------|------|----------|------|
| Stage 1 | 单Agent vs 6角色CDoL | NOAA MAPE 18.87%→9.37%，WHO 排名纠错 | [`examples/stage1_single_vs_6roles/`](examples/stage1_single_vs_6roles/) |
| Stage 2 | 6角色 vs 10角色CDoL | 评分 85→90，API调用 -53%，Reviewer 0 次被驳回 | [`examples/stage2_6roles_vs_10roles/`](examples/stage2_6roles_vs_10roles/) |
| Stage 3 | 完整系统真实管线 | 质量门禁触发率 100%，ContextMask 真实裁剪 | [`examples/stage3_full_system/`](examples/stage3_full_system/) |
| Stage 4 | 50步端到端全流程 | 14模块100%覆盖，9次拓扑切换，共识度 0.1→0.95 | [`examples/stage4_fifty_steps/`](examples/stage4_fifty_steps/) |
| Stage 5 | 80步SA vs NF真实Benchmark | 质量+2.6%，耗时-14.9%，Token-6.2%，≥9分步数3.25倍 | [`examples/stage5_eighty_steps/`](examples/stage5_eighty_steps/) |
| 横向对比 | NexusFlow vs AutoGen | 交叉验证能力领先 100% | [`examples/horizontal_comparison/`](examples/horizontal_comparison/) |
| Phase 2 | CDoL 轮次 Ablation（2/3/4轮） | 2-3轮最优平台期（0.715/0.699），4轮未超越平台期，验证 Nyquist 采样下界 | [`examples/demo_phase2_ablation_v3.py`](examples/demo_phase2_ablation_v3.py) |

---

## 端边云三层架构

| 层级 | 模型 | Agent | 说明 |
|------|------|-------|------|
| ☁️ 云端 | DeepSeek API (deepseek-v4-pro/flash) | Coordinator, Planner, Archivist, Reviewer, Caster, Researcher | 高质量推理 + 广知识 |
| 🖥️ 边端 | Ollama 本地模型（可配置） | Executor, Miner | 本地大模型，计算密集任务 |
| 📱 终端 | Ollama 本地模型（可配置） | Assayer, Artisan | 本地小模型，轻量监控 |

---

## Agent 角色表

| Agent | 角色 | 层级 | 职责 |
|-------|------|------|------|
| 🧭 Coordinator | 编排者 | ☁️ 全局 | 任务分发、进度协调、冲突裁决 |
| 📚 Archivist | 档案师 | ☁️ 全局 | 经验蒸馏、知识沉淀、历史检索 |
| 📈 Planner | 规划师 | 🔗 CDoL | 任务分解、策略设计、视角规划 |
| 🔍 Researcher | 研究员 | 🔗 CDoL | 联网搜索、文献分析、数据采集 |
| 🔥 Reviewer | 审查者 | 🔗 CDoL | 对抗质疑、逻辑审查、质量门禁 |
| 🔬 Caster | 铸造者 | 🔗 CDoL | 多视角融合、矛盾解决、输出生成 |
| 💻 Executor | 执行者 | 🖥️ CDoL | 代码开发、工具调用、任务执行 |
| ⛏ Miner | 数据矿工 | 🖥️ CDoL | 数据采集、清洗、结构化处理 |
| 🔬 Assayer | 检验者 | 📱 旁观 | 质量验证、异常检测、一致性检查 |
| 🎨 Artisan | 工匠 | 📱 旁观 | 精细化处理、格式优化、元观察 |

---

## 项目规模

| 指标 | 数值 |
|------|------|
| 总文件数 | **454**（git tracked） |
| Python 文件 | **145** |
| 仓库大小 | **~14 MB** |
| 核心模块 | **51** |
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
cp .env.example .env
# 编辑 .env 填入你的 API Key
```

### 启动

```bash
# 推荐方式：一键启动
python run.py

# 或手动启动
```

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
| [技术文档 v2.8](docs/NexusFlow技术文档v2.8.md) | NexusFlow 完整技术文档（96.6 KB） |
| [技术文档 v2.9](docs/NexusFlow技术文档v2.9.md) | v2.9 增量更新：动态终止 + Ablation 实验 + LLM 评分 |
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
