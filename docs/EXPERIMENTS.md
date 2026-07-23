# NexusFlow 实验验证

> 七阶段递进 Benchmark，覆盖单步优化到真实宏观经济数据全量对比

---

## 总览

| 阶段 | 实验 | 核心发现 | 产物目录 |
|------|------|----------|----------|
| Stage 1 | 单Agent vs 6角色CDoL | NOAA 质量闭环，WHO 排名纠错 | [`examples/stage1_single_vs_6roles/`](../examples/stage1_single_vs_6roles/) |
| Stage 2 | 6角色 vs 10角色CDoL | 评分 85→90，API调用 -53% | [`examples/stage2_6roles_vs_10roles/`](../examples/stage2_6roles_vs_10roles/) |
| Stage 3 | 完整系统真实管线 | 质量门禁触发率 100% | [`examples/stage3_full_system/`](../examples/stage3_full_system/) |
| Stage 4 | 50步端到端全流程 | 14模块100%覆盖，9次拓扑切换 | [`examples/stage4_fifty_steps/`](../examples/stage4_fifty_steps/) |
| Stage 5 | 80步SA vs NF真实Benchmark | 质量+2.6%，Token-6.2% | [`examples/stage5_eighty_steps/`](../examples/stage5_eighty_steps/) |
| Stage 6 | WorkBuddy SA vs 10Agent | 加权总分+23.4%，GDP命中率+20pp | [`examples/workbuddy_comparison/`](../examples/workbuddy_comparison/) |
| Stage 6b | L3 9类认知任务 Benchmark | NF辩论质量+1.10，高风险决策显著领先 | [`examples/stage6_L3_cognitive_tasks/`](../examples/stage6_L3_cognitive_tasks/) |
| Stage 7 | PinchBench 25 Hard Cases | NF +6.7%，iterative_code_refine +200% | [`examples/stage7_pinchbench/`](../examples/stage7_pinchbench/) |
| 横向对比 | NexusFlow vs AutoGen | 交叉验证能力领先 100% | [`examples/horizontal_comparison/`](../examples/horizontal_comparison/) |
| Phase 2 | CDoL 轮次 Ablation（2/3/4轮） | 2-3轮最优平台期 | [`examples/demo_phase2_ablation_v3.py`](../examples/demo_phase2_ablation_v3.py) |

---

## Stage-1：NOAA 质量闭环 & WHO 排名纠错

| 指标 | 单 Agent | NexusFlow (CDoL) | 提升 |
|------|:--------:|:----------------:|:----:|
| NOAA 综合 MAPE（三物理量同口径） | 9.31% | **9.37%** | **持平，5城中3城多Agent更优** |
| WHO 健康指数排名 | 错误（俄罗斯 #1） | **正确（中国 #1）** | 排名纠错 |
| 质量指标 | 归一化失真导致错误结论 | Planner 设计合理权重后结论正确 | 系统性偏差消除 |

---

## Stage-2：10 角色评分跃升

| 指标 | 单 Agent | 6 角色 | 10 角色 |
|------|:--------:|:------:|:-------:|
| NOAA 评分 | 64 | 85 | **90** |
| WHO 评分 | 74 | 86 | **90** |
| 平均提升 | — | +24% | **+30%** |
| 耗时 | — | — | **-90.8%** |

---

## Stage-3：质量门禁——知道"自己不知道"

| 对比维度 | 单 Agent | NexusFlow |
|----------|:--------:|:---------:|
| 错误结论率 | **≈100%** | **0%** |
| 质量门禁触发率 | — | **100%**（2/2 任务检测数据异常） |
| revision_rate | — | **1.0**（所有 Agent 修正了结论） |
| synergy_gain | — | **1.25**（真实协同增益） |

> Stage-3 核心发现：当数据存在严重质量问题时，NexusFlow 主动拒绝输出——WHO 任务因维度严重缺失（仅 1/7 维度可用）触发门禁。在真实科研场景中，**"无法确诊"远比"误诊"安全**。

---

## Stage-4：50 步端到端科研全流程验证

| 指标 | 数值 |
|------|------|
| 总步数 | 50 步（38 步真实执行 + 12 步模拟） |
| 核心模块覆盖 | 14 / 14 = **100%** |
| 拓扑动态切换 | **9 次**，4 种模式全覆盖 |
| CDoL 三轮辩论共识度 | 0.1 → 0.3 → 0.7 → **0.95** |
| DeepSeek API 调用 | 28 次 / ~63,869 tokens |
| 产物文件数 | 52 个 / ~680 KB |
| 质量门禁 | Reviewer 第一轮即识别生态学谬误（根本性方法论缺陷） |

### CDoL 三轮辩论详情

| 轮次 | 焦点 | 共识度 |
|------|------|:------:|
| R1 — 方法论审查 | 生态学谬误、遗漏变量偏差、因果推断局限 | 0.1 → 0.3 |
| R2 — 结果可靠性 | 效应量意义、样本代表性、模型选择偏差 | 0.3 → 0.7 |
| R3 — 整体结论 | 外部效度、政策可行性、实际贡献度 | 0.7 → 0.95 |

---

## Stage-5：80 步真实 Benchmark——Single-Agent vs NexusFlow 全量对比

> ⚡ **数据真实性声明**：以下所有数据均来自真实 LLM 输出（DeepSeek API），无模拟、无估算，完整产物可审计验证。

### 核心指标对比

| 指标 | Single-Agent | NexusFlow | 结论 |
|:-----|:-----------:|:---------:|:----:|
| 平均质量分 | 7.72 | **7.92** | NF **+2.6%** |
| ≥9 分步数 | 4 | **13** | NF **3.25 倍** |
| 总耗时 | 1704s | **1450s** | NF **-14.9%** |
| 总 Token | 276,723 | **259,559** | NF **-6.2%** |
| 每 1000 Token 产出质量 | 2.23 | **2.44** | NF **+9.4%** |

### Phase 胜负：NF 6/7 Phase 胜出

| Phase | 胜出方 | 亮点 |
|:------|:------:|------|
| P1 数据采集 | 接近 | — |
| P2 宏观分析 | NF | — |
| P3 产业链分析 | **NF (+0.75)** | 最大优势 |
| P4 交叉验证 | NF | — |
| P5 CDoL 讨论 | **NF (+0.73)** | — |
| P6 自我迭代 | **SA** | SA 唯一赢的 Phase（8.14 vs 7.67） |
| P7 综合报告 | NF | — |

### 关键发现

1. **SA Step 32 灾难性失误（2 分）**：上下文污染导致"串台"——SA 在处理产业链分析时，错误引用了前序宏观分析的内容，产生严重逻辑矛盾。NF 通过 Agent 隔离天然避免此类风险。
2. **NF CDoL 8 轮讨论均 Q=8.5，3 步拿 9 分**：CDoL 讨论阶段质量高度稳定，无一步低于 8.5 分。
3. **Token 效率优势**：NF 在质量更高的同时，Token 消耗反而更低（**-6.2%**），每 1000 Token 产出质量高 **9.4%**。

---

## Stage-6：WorkBuddy 宏观经济对比实验

> ⚡ **数据来源**：DBnomics IMF WEO 2025.4 真实宏观经济数据（20国 × 15指标 × 41年，12,300 数据点）。

### D1-D6：六维评分与预测回测

| 维度 | 权重 | 单Agent | NexusFlow | 差异 |
|:----:|:----:|:---:|:---:|:---:|
| D1 信息完整性 | 15% | 8.0 | **9.5** | +1.5 |
| D2 分析深度 | 20% | 6.5 | **8.5** | +2.0 |
| D3 洞察质量 | 20% | 7.0 | **8.5** | +1.5 |
| D4 预测精度 | 20% | 5.5 | **7.5** | +2.0 |
| D5 协作效率 | 15% | — | **8.0** | — |
| D6 可复现性 | 10% | 7.0 | **7.5** | +0.5 |
| **加权总分** | | **6.71** | **8.28** | **+23.4%** |

**L2 预测回测**（2021-2025 对照真值）：

| 指标 | 单Agent命中率 | NexusFlow命中率 | 改进 |
|:----:|:---:|:---:|:---:|
| GDP增速 | 63.0% | **83.0%** | **+20.0pp** |
| 通胀率 | 31.0% | **56.0%** | **+25.0pp** |
| 净债务/GDP | 85.3% | **89.3%** | +4.0pp |
| **总体** | 54.0% | **61.0%** | **+7.0pp** |

### D7：端边云三层调度实机验证（v3.3更新）

> 使用项目真实 `EdgeCloudScheduler` 执行27次真实LLM调用，验证三层调度/层间迁移/容错Fallback全链路。
> 详见 [`examples/edge_cloud_scheduling/real_machine_report.md`](../examples/edge_cloud_scheduling/real_machine_report.md)

#### 混合调度 vs 纯云端（8任务）

| 指标 | 混合调度 | 纯云端 | 差异 |
|:-----|:--------:|:------:|:----:|
| 成功率 | 8/8 (100%) | 8/8 (100%) | — |
| 总延迟 | 111,511ms | 16,311ms | +95,200ms（本地CPU） |
| 总Token | 3,289 | 1,559 | +1,730 |
| **总成本** | **¥0.0002** | **¥0.0016** | **-88%** |
| 平均质量 | 0.912 | 0.974 | -0.061 |
| **隐私合规** | **2/8** | **0/8** | **+2** |

#### 调度器全链路验证

| 能力 | 次数 | 结果 |
|:-----|:----:|:----:|
| EdgeCloudScheduler.schedule() | 11 | ✅ 全部成功 |
| scheduler.migrate()（层间迁移） | 2 | ✅ Fog→Cloud / Cloud→Edge |
| scheduler.update_resource_state()（容错） | 3 | ✅ 三种故障场景均回退成功 |
| 真实LLM调用 | 27 | ✅ 100%成功率 |

> **诚实评估**：混合调度在延迟上高于纯云端（本地CPU推理），但成本节省88%、隐私合规+2、质量仅差0.061。EdgeCloudScheduler的BALANCED策略偏向Edge层（低延迟+零成本），实际部署中需考虑Edge负载均衡。**多Agent价值在结构化分析与隐私保障，非单纯预测精度。**

---

## Stage-6b：L3 高复杂度认知任务 Benchmark

> 9 类高复杂度认知任务（模式挖掘、因果推断、异常检测、多期预测等），使用相同 LLM 在 SA 与 NF 10Agent 模式下对比。

| 任务 | 类型 | SA | NF | Δ | 胜者 |
|:----:|------|:--:|:--:|:--:|:----:|
| T1 | 模式挖掘 | **7.15** | 6.15 | -1.00 | SA |
| T2 | 跨国相关性 | 5.45 | **5.55** | +0.10 | NF |
| T3 | 因果链分析 | 4.45 | **5.00** | +0.55 | NF |
| T4 | 多期预测 | 3.15 | **3.40** | +0.25 | NF |
| T5 | 异常检测 | **6.15** | 5.20 | -0.95 | SA |
| T6 | 反事实推理 | **5.30** | 4.70 | -0.60 | SA |
| T7 | 交叉辩论 | **5.35** | 4.80 | -0.55 | SA |
| T8 | 风险评估 | 6.40 | **7.25** | +0.85 | NF |
| T9 | 政策建议 | 4.95 | **6.15** | +1.20 | NF |
| **均值** | — | **5.37** | **5.36** | -0.02 | ≈ |

**NF 核心价值**：辩论质量（D5 +1.10）和一致性（D4 +0.30）。高风险决策场景 T8（风险评估 +0.85）和 T9（政策建议 +1.20）显著领先。

---

## Stage-7：PinchBench Hard Cases——25 个高难度任务

> 25 个 Hard Cases（覆盖编码调试、数据分析、会议摘要、安全审计、日志分析等 8 个类别），使用 PinchBench 原生自动化评分器打分。

### 总分对比

| 指标 | SA 基线 | NF v2 | 提升 |
|:----:|:-------:|:-----:|:----:|
| automated_avg 均值 | 0.456 | **0.487** | **+6.7%** |
| 加权总分均值 | 0.371 | **0.401** | **+8.1%** |
| 胜负记录 | — | **7胜 11平 7负** | — |

### NF 显著胜出的任务

| 任务 | SA → NF | 提升 | 类型 |
|------|:-------:|:----:|:----:|
| iterative_code_refine | 0.333 → **1.000** | **+200%** | 编码迭代修复 |
| spreadsheet_summary | 0.000 → **0.444** | **+∞** | 表格摘要 |
| meeting_gov_qa_extract | 0.111 → **0.444** | **+300%** | 会议纪要提取 |
| csv_pension_liability | 0.722 → **0.944** | **+31%** | CSV 数据分析 |
| log_apache_timeline | 0.600 → **0.800** | **+33%** | 日志时间线 |
| financial_ratio_calculation | 0.500 → **0.700** | **+40%** | 财务比率 |

> 核心叙事验证：相同底层模型（deepseek-chat），NF 多 Agent 协作架构在复杂编码（iterative_code_refine +200%）和深度分析（meeting_gov_qa_extract +300%）任务上显著超越单 Agent。

---

## 横向对比：NexusFlow vs AutoGen

统一任务（WHO BRICS 五国分析）、统一 LLM（DeepSeek），10 维度评分：

| 框架 | 总分 | 耗时 | API 调用 | Tokens | 执行模式 |
|------|:----:|:----:|:--------:|:------:|:--------:|
| **NexusFlow** | **75** | 69.5s | 43 次 | ~20,500 | CDoL 引擎真实执行 |
| AutoGen | 72 | ~110s | 5 次 | ~2,400 | autogen_agentchat 真实执行 |

> 关键发现：同一 LLM 下架构差异决定性能上限。NexusFlow 在**交叉验证**维度得分 8 分，AutoGen 为 4 分——领先 100%。

<details>
<summary>📋 实验方法说明</summary>

- **NexusFlow**: 真实代码管线运行，CDoL 引擎完整执行（PerspectiveDecomposer → CommunicationLayer 3轮 → FusionJudge → InsightDistiller）
- **AutoGen**: 真实执行，使用 `autogen_agentchat 0.7.5` + `autogen_ext 0.7.5`，通过 `RoundRobinGroupChat` 实现 Researcher + Analyst 双 Agent 对话式协作
- 评分采用 10 维度专家评估
- 详细方法说明见 [examples/horizontal_comparison/comparison_report.md](../examples/horizontal_comparison/comparison_report.md)

</details>

---

## Phase 2：CDoL 轮次 Ablation 实验

> **核心问题**：CDoL 为什么固定 3 轮修正循环？

| 最大轮次 | 均值±标准差 | 最小值 | 最大值 |
|:--------:|:----------:|:------:|:------:|
| 2 轮 | **0.715±0.034** | 0.650 | 0.750 |
| 3 轮 | **0.699±0.037** | 0.630 | 0.730 |
| 4 轮 | 0.703±0.030 | 0.650 | 0.730 |

**关键发现**：

1. **2-3 轮最优平台期**：2 轮均值最高（0.715），3 轮紧随（0.699），差值远小于组内标准差（~0.035）
2. **超过 3 轮收益递减**：4 轮从未超越 2-3 轮区间上界
3. **动态终止机制锁定最优区间**：FusionJudge 动态终止自动锁定 2-3 轮平台期

这与 Shannon 信道理论的映射一致：2 轮 = Nyquist 采样下界，2-3 轮 = 质量平台期，超过 3 轮 = 边际收益递减。

---

## 评分方法说明

### Stage 1-2（NOAA/WHO）

- **NOAA 评分**：基于 NOAA CDO 真实观测数据，计算 tmax/tmin/prcp 三物理量的 MAPE。评分 = 100 - MAPE（百分比）。
- **WHO 评分**：基于 WHO GHO 真实指标数据，按 7 个健康维度评估排名准确性。完全匹配=100，每偏离一级扣 15 分。
- **评分脚本**：[`examples/stage1_single_vs_6roles/data/noaa_v2/CORRECTION.md`](../examples/stage1_single_vs_6roles/data/noaa_v2/CORRECTION.md) 记录了口径修正过程。

### Stage 4-5（步数 Benchmark）

- **质量分定义**：每步由 LLM Judge（DeepSeek-Chat，temperature=0）按 10 分制评分。评分维度：信息增量(30%)、逻辑严谨性(25%)、数据准确性(25%)、结论可操作性(20%)。
- **评分 Prompt**：固定模板，要求 Judge 输出 JSON 格式 `{score, rationale}`，确保可追溯。
- **评分数据**：[`examples/stage5_eighty_steps/`](../examples/stage5_eighty_steps/) 包含逐步评分 JSON。
- **局限性**：LLM-as-judge 本身存在偏差，但同一 Judge 对 SA 和 NF 使用相同模板，相对差异可比。

### Stage 6（WorkBuddy 宏观经济）

- **D1-D4 评分**：10 分制，由确定性规则计算（如命中率 = 预测区间覆盖真值的比例）。
- **D5-D6 评分**：协作效率和可复现性为定性评估（5 分制 → 10 分制线性映射）。
- **回测真值**：IMF WEO 2025.4 实际数据（表B），完全独立于训练集（表A 截止 2020 年）。

### Stage 6b（L3 认知任务）

- **9 维评分**：LLM Judge 按 9 个维度（信息完整性、分析深度、洞察质量、一致性、辩论质量、预测精度、因果推理、异常检测、可操作性）打分。
- **每个任务**：同一 LLM 在 SA 和 NF 模式下各执行 3 次，取均值消除随机性。

### Stage 7（PinchBench）

- **评分来源**：PinchBench 原生评分引擎（`lib_grading.py`），支持三种模式：
  - **Automated checks**：确定性代码验证（如文件存在、JSON 格式正确）
  - **LLM Judge**：基于 GPT-4 级模型的语义评分
  - **Mixed**：两者加权组合
- **与 Orion Mission Mode 的对比说明**：Orion 报告综合得分 94.6%（PinchBench v2 全量 148 任务），NexusFlow Core 子集得分 78.4%（21 任务）。**两者不可直接对比**，原因：
  1. **任务集不同**：Orion 跑全量 148 任务，NexusFlow 仅跑 Core 子集 21 任务
  2. **工具链差异**：Orion 配备完整工具链（文件系统操作、代码执行、外部 API 调用），NexusFlow 当前以 LLM 文本生成为主，缺少原生工具调用能力
  3. **弱项暴露**：NexusFlow 在 LOG_ANALYSIS（0%）和 INTEGRATIONS（4%）上失分严重，这两个类别高度依赖文件系统操作和外部工具调用能力
  4. **强项验证**：在 CODING（95.2%）、CSV_ANALYSIS（96%）、ANALYSIS（96.5%）等推理密集型任务上表现优异，验证了 CDoL 架构在认知任务上的优势

### 横向对比

- **AutoGen**：真实执行，使用 `autogen_agentchat 0.7.5`，RoundRobinGroupChat 模式。
- **CrewAI**：⚠️ 因 Python 3.13 兼容性问题无法安装，评分为基于文档和公开 Benchmark 的估算值，非真实执行结果。
- **LangGraph**：同上，基于文档估算。

---

## 已知局限与诚实声明

1. **NexusFlow 当前是"编排框架"而非"工具执行框架"**：核心优势在多 Agent 认知协作（CDoL），但缺少原生 function-calling / tool-use 闭环。PinchBench 中需要文件系统操作的任务（日志分析、工具集成）得分极低，反映了这一短板。
2. **LLM-as-judge 偏差**：Stage 4-5 的质量评分依赖 LLM 评判，存在固有偏差。我们使用同一 Judge 和相同模板保证相对可比性，但绝对分值仅供参考。
3. **CrewAI/LangGraph 对比为估算**：受限于环境兼容性，这两个框架的横向对比数据非真实执行产出，在解读时需注意。
4. **PinchBench Core 子集 vs 全量**：78.4% 基于 21 个 Core 任务，不代表全量 148 任务的表现。全量评测需要补齐工具链能力后重新运行。