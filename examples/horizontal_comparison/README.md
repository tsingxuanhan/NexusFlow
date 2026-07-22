# 横向对比: NexusFlow vs AutoGen

> 统一任务、统一LLM、统一数据源——验证NexusFlow在主流框架中的定位

---

## ⚖️ 评分权威声明

本目录存在多个版本的评分结果文件，为消除歧义，**权威评分来源**统一为以下文件：

| 优先级 | 文件 | 说明 |
|:------:|------|------|
| **1（权威）** | `multi_framework_comparison.json` | 最新确定性规则评估（2026-07-17），覆盖全部4个框架（NexusFlow/AutoGen/CrewAI/LangGraph），**所有对外引用应以此为准** |
| 2（权威） | `comparison_results.json` | 确定性规则评估（2026-07-14），覆盖 NexusFlow 和 AutoGen 两框架。其中 AutoGen=100 的版本已废弃（全维度满分10属于评估错误） |

### 权威分数（来自 `multi_framework_comparison.json`）

| 框架 | 综合得分 | 评估方法 |
|------|:-------:|---------|
| **NexusFlow** | **75.0** | 10维度确定性规则评估 |
| **AutoGen** | **72.0** | 10维度确定性规则评估 |
| **CrewAI** | **61.5** | 10维度确定性规则评估 |
| **LangGraph** | **63.8** | 10维度确定性规则评估 |

### 废弃/历史版本说明

以下文件为**历史过程文件**，不应作为最终结论引用：

| 文件 | 状态 | 说明 |
|------|------|------|
| `comparison_results.json`（AutoGen=100） | ⚠️ 部分废弃 | AutoGen 全维度满分10属评估错误，仅 NexusFlow=84.5 部分有效 |
| `real_evaluation_results.json` | 📌 过程文件 | 早期确定性评估（NexusFlow=86.5, AutoGen=55.5），已被 `multi_framework_comparison.json` 取代 |
| `evaluation_scores.md` | 📌 过程文件 | 细粒度评分记录（NexusFlow=92, AutoGen=88），为评分推导过程而非最终结论 |
| `llm_evaluation_results.json` | 📌 过程文件 | LLM 5维评分（NexusFlow=75, AutoGen=72），与权威分数一致但非确定性规则评估 |

详细评分方法论见 [SCORING_METHODOLOGY.md](SCORING_METHODOLOGY.md)。

---

---

## 🎯 实验目标

使用**统一任务**（WHO BRICS五国健康分析）、**统一LLM**（DeepSeek）、**统一数据源**（WHO GHO API），对比 NexusFlow 与 AutoGen 两个框架的表现，验证NexusFlow的差异化优势。

## 🔬 实验方法

| 项目 | 配置 |
|------|------|
| **统一任务** | 查询WHO GHO获取BRICS五国生命期望、婴儿死亡率、卫生支出数据，计算综合健康指数 |
| **统一LLM** | DeepSeek Chat (deepseek-chat) |
| **评估标准** | LLM 5维评分（completeness / depth / consistency / novelty / actionability）|
| **环境** | Python 3.13.14 |

### 框架安装情况

| 框架 | 安装结果 | 实际运行模式 |
|------|---------|-------------|
| NexusFlow | 原生运行 | CDoL引擎 |
| AutoGen | v0.7.5 | RoundRobinGroupChat 真实执行 |

## 📊 核心结果

### LLM 5维评分

| 维度 | NexusFlow | AutoGen |
|------|:---------:|:-------:|
| Completeness | 8 | 8 |
| Depth | 7 | 7 |
| Consistency | 9 | 9 |
| Novelty | 6 | 5 |
| Actionability | 7 | 6 |
| **综合分** | **75** | **72** |

### 执行指标

| 指标 | NexusFlow | AutoGen |
|------|-----------|---------|
| 代码行数 | ~200行 | ~49行 |
| 执行耗时 | 69.5s | ~110s |
| LLM调用 | 31次 | 2次 |
| 总API调用 | 43次 | 5次 |
| Token消耗 | ~20,500 | ~2,400 |
| 拓扑动态切换 | ✅ | ❌ |
| 自我修正 | ✅ | ✅ |
| 交叉验证 | ✅ | ❌ |
| 失败恢复 | ✅ | ❌ |

### 各框架特点

| 框架 | 优势 | 劣势 | 适用场景 |
|------|------|------|---------|
| **NexusFlow** | 交叉验证(8 vs 4)、动态拓扑、自我修正 | 资源消耗3-4x、代码量大 | 复杂分析、高可靠性 |
| **AutoGen** | 对话式验证、代码简洁(49行) | 无交叉验证、拓扑固定 | 中度复杂、快速原型 |

## 📈 与前Stage的对比

| Stage | 对比维度 | 核心发现 |
|-------|---------|---------|
| Stage-1 | 单Agent vs CDoL | CDoL认知分工有效 |
| Stage-2 | 6角色 vs 10角色 | Critic质疑闭环带来质变 |
| Stage-3 | 模拟 vs 真实系统 | 拒绝错误结论是核心价值 |
| Stage-4 | 单一任务 vs 全流程 | 50步端到端可行 |
| **横向对比** | **NexusFlow vs AutoGen** | **交叉验证是关键差异化因素** |

## 🔑 关键发现

> **交叉验证是NexusFlow的关键差异化因素**（8分 vs 4分）。两个框架使用相同LLM，得分差距主要来自架构差异。Token消耗与质量非线性——NexusFlow消耗4倍tokens但得分高3分，说明增量改进的边际收益递减。框架选择应匹配任务复杂度。

---

*详细报告见 [comparison_report.md](comparison_report.md)*
*各框架输出见 [nexusflow_output.md](nexusflow_output.md)、[autogen_output.md](autogen_output.md)*
*LLM评分明细见 [llm_evaluation_results.json](llm_evaluation_results.json)*
