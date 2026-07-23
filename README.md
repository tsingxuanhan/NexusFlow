<div align="center">

# NexusFlow

**面向超长程复杂任务的群体智能引擎**

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/Python-3.10%2B-blue.svg)]()
[![Version](https://img.shields.io/badge/Version-3.1.0-green.svg)](CHANGELOG.md)
[![Tests](https://img.shields.io/badge/Tests-Passing-brightgreen.svg)](.github/workflows/tests.yml)
[![Security](https://img.shields.io/badge/Security-Gitleaks-blue.svg)](SECURITY.md)
[![Benchmarks](https://img.shields.io/badge/Benchmarks-7%20Stages%20%7C%20PinchBench-red.svg)]()

*Where cognitive diversity meets dynamic topology.*

</div>

---

**框架工程 > 模型堆叠** —— NexusFlow 是第一个实现**认知分工（Cognitive Division of Labor, CDoL）**的群体智能引擎。通过**主动制造信息不对称**，迫使每个 Agent 从他人输出中逆向推断上下文，产生超越任何单 Agent 的推理深度。

> *"Benchmark 测到的永远不是裸模型，而是'模型+Harness'的组合能力。最大的性能改进往往来自简单的自动化步骤，而非消耗大量 Token 去修改提示词。"*
> — Joel Niklaus, Hugging Face

---

## 关键数字

| 指标 | 数据 |
|------|------|
| 框架 vs 模型影响力 | **7.6 倍**（[Braintrust 1,781条轨迹](https://www.braintrust.dev/)） |
| 法律 Agent 优化 Harness | 3.5% → **80.1%**（[Joel Niklaus](https://x.com/joelniklaus)） |
| PinchBench 25 Hard Cases | NF **+6.7%**（iterative_code_refine **+200%**） |
| WorkBuddy 宏观经济 | 加权总分 **+23.4%**，GDP命中率 **+20pp** |
| 80步全量 Benchmark | 质量+2.6%，Token **-6.2%**，耗时 **-14.9%** |
| 质量门禁 | 触发率 **100%**，错误结论率 **0%** |

---

## 快速开始

### 环境要求

- Python 3.10+
- [Ollama](https://ollama.com/)（本地部署）
- DeepSeek API Key（可选，用于云端 Agent）

### 安装

```bash
git clone https://github.com/tsingxuanhan/NexusFlow.git
cd NexusFlow
pip install -r requirements.txt

# 配置环境变量
cp .env.example .env
# 编辑 .env 填入你的 API Key
```

### 运行

```bash
# 一键启动（推荐）
python run.py

# 端到端 Demo（架构展示，无需 API Key）
python examples/demo_e2e_pinchbench.py --arch-only

# 完整 Demo（含 SA vs NF PinchBench 对比 + HTML报告）
python examples/demo_e2e_pinchbench.py
```

运行完成后，在浏览器打开 `examples/demo_e2e_report.html` 查看可视化报告

### 端边云配置

```bash
# Ollama 模型安装
ollama pull deepseek-r1:14b
ollama pull qwen3.5:9b
```

| 层级 | 模型 | Agent |
|------|------|-------|
| ☁️ 云端 | DeepSeek API | Coordinator, Planner, Archivist, Reviewer, Caster, Researcher |
| 🖥️ 边端 | Ollama 本地 | Executor, Miner |
| 📱 终端 | Ollama 本地 | Assayer, Artisan |

---

## 产出展示

> 所有实验产物完整开源，可复现、可审计。

| 产出 | 说明 | 链接 |
|------|------|------|
| 📊 PinchBench 对比报告 | 25 Hard Cases SA vs NF 实时 HTML 报告 | [在线查看](https://www.coze.cn/s/RCDTzyE6r20/) |
| 📄 技术文档 v3.1 | 完整技术文档（2198行，含 Stage 6-7 实验） | [在线查看](https://www.coze.cn/s/ow8wNkQqf0g/) |
| 🔬 Stage-7 实验 | 25 任务 SA vs NF 全量 JSON + 对比报告 | [`examples/stage7_pinchbench/`](examples/stage7_pinchbench/) |
| 🌍 Stage-6 WorkBuddy | 20国×15指标×41年 宏观经济对比 | [`examples/workbuddy_comparison/`](examples/workbuddy_comparison/) |
| 📈 Stage-5 80步 | SA vs NF 逐步评分全量数据 | [`examples/stage5_eighty_steps/`](examples/stage5_eighty_steps/) |
| 🧪 CDoL Ablation | 2/3/4轮最优平台期实验 | [`examples/demo_phase2_ablation_v3.py`](examples/demo_phase2_ablation_v3.py) |

---

## 核心架构

**👉 [完整架构文档 →](docs/ARCHITECTURE.md)**

```
┌──────────────────────────────────────────────────────┐
│              NexusOrchestrator (路由)                  │
│         simple / research / coding / cdol             │
└──────────────┬───────────────────────────────────────┘
               │
    ┌──────────┼──────────┐
    ▼          ▼          ▼
┌────────┐ ┌────────┐ ┌────────────────┐
│  CDoL  │ │ Memory │ │  Agent Pool    │
│ Engine │ │Manager │ │  (10 Agents)   │
│        │ │        │ │ ☁️ 6 · 🖥️ 2   │
│ 3轮辩论│ │4层记忆 │ │ 📱 2           │
│ 虚假一致│ │RRF混合 │ │                │
│ 检测   │ │检索    │ │ 5种拓扑模式     │
└────────┘ └────────┘ └────────────────┘
```

**六大核心模块**：

- **CDoL 认知分工引擎**（2,058行）— 6种视角分解 + 三轮有损通信 + 虚假一致检测
- **自适应上下文管理器**（1,642行）— 对抗"大窗口懒惰症"
- **三层信息架构**（511行）— 全局视野 / CDoL参与 / 旁观记录
- **动态拓扑路由器**（869行）— 运行时重建 Agent 协作图
- **端边云调度器**（535行）— 隐私优先，云端+本地混合
- **统一编排器**（479行）— 自动路由分类 + 蒸馏归档

---

## 实验验证

**👉 [完整实验数据 →](docs/EXPERIMENTS.md)**

七阶段递进 Benchmark，覆盖单步优化到真实宏观经济全量对比：

| 阶段 | 实验 | 核心发现 |
|------|------|----------|
| Stage 1-2 | 角色数递进 | 评分 64→90，耗时 -90.8% |
| Stage 3 | 质量门禁 | 错误结论率 **0%**（SA ≈100%） |
| Stage 4 | 50步全流程 | 14模块100%覆盖，共识度 0.1→0.95 |
| Stage 5 | 80步真实对比 | 质量+2.6%，Token-6.2%，3.25倍高质量步数 |
| Stage 6 | WorkBuddy宏观 | 加权总分+23.4%，GDP命中率+20pp |
| Stage 6b | L3认知任务 | 辩论质量+1.10，高风险决策显著领先 |
| Stage 7 | PinchBench 25 Hard | NF +6.7%，编码修复 +200% |
| 横向 | vs AutoGen | 交叉验证领先 100% |

---

## 项目规模

**524 文件** · **167 Python** · **68 核心模块** · **10 Agent** · **17 工具** · **4 层记忆** · **6 种CDoL策略** · **5 种拓扑模式** · **7 阶段Benchmark**

---

## 参考资料

| 来源 | 说明 |
|------|------|
| [技术文档 v3.1](docs/NexusFlow技术文档v3.1.md) | 完整技术文档（含 Stage 6-7 实验） |
| [系统架构](docs/ARCHITECTURE.md) | 架构图、Agent角色、模块详情 |
| [实验验证](docs/EXPERIMENTS.md) | Stage 1-7 完整实验数据 |
| [变更日志](CHANGELOG.md) | 版本变更记录（v1.0 → v3.1） |
| [贡献指南](CONTRIBUTING.md) | 开发环境、提交规范 |
| [安全策略](SECURITY.md) | 漏洞报告流程 |
| [Braintrust](https://www.braintrust.dev/) | 1,781 条真实轨迹——框架影响力 7.6 倍于模型 |
| [Joel Niklaus](https://x.com/joelniklaus) | 冻结权重仅优化 Harness，3.5% → 80.1% |
| [清华 & OpenBMB](https://arxiv.org/abs/2606.15378) | Large-Window Laziness 研究 |
| [Arbor](https://arxiv.org/abs/2606.11926) | Hypothesis-Tree Refinement 启发来源 |

---

## License

[MIT License](LICENSE)

---

<div align="center">

**框架工程 > 模型堆叠。**

*NexusFlow: Where cognitive diversity meets dynamic topology.*

</div>
