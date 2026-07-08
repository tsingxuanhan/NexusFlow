# Stage-4：NexusFlow 50步端到端科研全流程任务设计文档

## 1. 任务概述

| 项目 | 内容 |
|------|------|
| **任务主题** | 基于NOAA+WHO数据的气候-健康关联分析 |
| **竞赛编号** | XH-202631（荣耀揭榜挂帅） |
| **步骤总数** | 50步 |
| **涉及Agent角色** | 10个（Coordinator, Strategist, Researcher, Analyst, Coder, Critic, FusionJudge, Archivist, Reviewer, Observer） |
| **涉及核心模块** | 14个（TaskRouter, MetaPlanner, ResearchLoop, DataAnalyzer, CodingExecutor, CriticEngine, FusionEngine, ContextManager等） |
| **数据源** | NOAA CDO GSOY（气温/降水）+ WHO GHO（健康指标） |
| **CDoL轮次** | 3轮（方法论审查→结果可靠性→整体结论） |

## 2. 研究问题

基于NOAA气候数据和WHO健康数据，分析以下核心问题：
- **RQ1**：年平均温度变化与公共健康指标（呼吸系统疾病负担）之间是否存在显著关联？
- **RQ2**：极端降水事件与心血管疾病之间是否存在滞后关联效应？
- **RQ3**：气候-健康关联在不同WHO区域是否存在异质性？

## 3. 50步任务总览表

### 阶段一：文献检索与分析（步骤1-8，8步）

| 步骤 | Agent角色 | NexusFlow模块 | 输入 | 输出 | 拓扑模式 |
|------|-----------|--------------|------|------|----------|
| 1 | Coordinator | TaskRouter | 原始任务描述 | 任务分解DAG(JSON) | Chain |
| 2 | Coordinator | TaskRouter | 任务DAG | 执行路由+拓扑切换策略 | Chain |
| 3 | Strategist | MetaPlanner | 任务DAG | 分析框架文档 | Chain |
| 4 | Researcher | ResearchLoop | 分析框架 | 文献检索结果列表 | Parallel |
| 5 | Researcher | ResearchLoop | 检索结果 | 核心发现分类表 | Parallel |
| 6 | Researcher | ResearchLoop | 核心发现 | 研究空白清单 | Parallel |
| 7 | Researcher | ResearchLoop | 研究空白 | 文献综述+3个研究问题 | Chain |
| 8 | Researcher | ResearchLoop | 文献综述 | 结构化文献图谱 | Chain |

### 阶段二：假设生成（步骤9-13，5步）

| 步骤 | Agent角色 | NexusFlow模块 | 输入 | 输出 | 拓扑模式 |
|------|-----------|--------------|------|------|----------|
| 9 | Strategist | MetaPlanner | 文献综述 | 假设H1定义 | Chain |
| 10 | Strategist | MetaPlanner | H1框架 | 假设H2定义 | Chain |
| 11 | Strategist | MetaPlanner | H2框架 | 假设H3定义 | Chain |
| 12 | Strategist | MetaPlanner | H1-H3 | 验证框架(方法+数据需求) | Chain |
| 13 | Critic | CriticEngine | 假设+框架 | 假设审查意见+修订建议 | Debate |

### 阶段三：数据获取与清洗（步骤14-20，7步）

| 步骤 | Agent角色 | NexusFlow模块 | 输入 | 输出 | 拓扑模式 |
|------|-----------|--------------|------|------|----------|
| 14 | Researcher | ResearchLoop | 数据需求 | NOAA温度数据(GSOY) | Parallel |
| 15 | Researcher | ResearchLoop | 数据需求 | NOAA降水数据(GSOY) | Parallel |
| 16 | Researcher | ResearchLoop | 数据需求 | WHO呼吸系统疾病数据 | Parallel |
| 17 | Researcher | ResearchLoop | 数据需求 | WHO心血管疾病数据 | Parallel |
| 18 | Coder | CodingExecutor | 原始数据 | 数据清洗Python脚本 | Chain |
| 19 | Coder | CodingExecutor | 清洗脚本 | 清洗后数据+质量报告 | Chain |
| 20 | Analyst | DataAnalyzer | 清洗数据 | 数据质量检查(分布/异常值) | Chain |

### 阶段四：实验设计（步骤21-26，6步）

| 步骤 | Agent角色 | NexusFlow模块 | 输入 | 输出 | 拓扑模式 |
|------|-----------|--------------|------|------|----------|
| 21 | Strategist | MetaPlanner | 分析框架 | DLNM模型设计 | Chain |
| 22 | Strategist | MetaPlanner | DLNM设计 | 变量定义表 | Chain |
| 23 | Strategist | MetaPlanner | 变量表 | 敏感性分析方案 | Chain |
| 24 | Critic | CriticEngine | 实验方案 | 审查意见(混淆/效力) | Debate |
| 25 | FusionJudge | FusionEngine | 方案+审查 | 综合评审决定 | Debate |
| 26 | Strategist | MetaPlanner | 评审结果 | 最终实验方案 | Chain |

### 阶段五：数据分析（步骤27-34，8步）

| 步骤 | Agent角色 | NexusFlow模块 | 输入 | 输出 | 拓扑模式 |
|------|-----------|--------------|------|------|----------|
| 27 | Coder | CodingExecutor | 实验方案 | 相关性分析代码 | Parallel |
| 28 | Coder | CodingExecutor | 实验方案 | 回归分析代码 | Parallel |
| 29 | Coder | CodingExecutor | 实验方案 | 滞后效应分析代码 | Parallel |
| 30 | Analyst | DataAnalyzer | 分析代码 | 相关性分析结果 | Tree |
| 31 | Analyst | DataAnalyzer | 分析代码 | 回归分析结果 | Tree |
| 32 | Analyst | DataAnalyzer | 清洗数据 | 区域异质性分析 | Tree |
| 33 | Critic | CriticEngine | 分析结果 | **CDoL R1质疑** | Debate |
| 34 | Analyst | DataAnalyzer | R1质疑 | CDoL R1回应+稳健性检验 | Debate |

### 阶段六：代码实现（步骤35-40，6步）

| 步骤 | Agent角色 | NexusFlow模块 | 输入 | 输出 | 拓扑模式 |
|------|-----------|--------------|------|------|----------|
| 35 | Coder | CodingExecutor | 分析结果 | 可视化代码 | Chain |
| 36 | Coder | CodingExecutor | 协议规范 | CDoL多轮辩论协议代码 | Chain |
| 37 | Coder | CodingExecutor | 结果集 | 结果整合脚本 | Chain |
| 38 | Coder | CodingExecutor | 代码集 | 代码审查与优化报告 | Chain |
| 39 | Critic | CriticEngine | 分析结果 | **CDoL R2质疑** | Debate |
| 40 | FusionJudge | FusionEngine | R2质疑+回应 | **CDoL R2融合判定** | Debate |

### 阶段七：结果综合（步骤41-45，5步）

| 步骤 | Agent角色 | NexusFlow模块 | 输入 | 输出 | 拓扑模式 |
|------|-----------|--------------|------|------|----------|
| 41 | Analyst | DataAnalyzer | 全部分析结果 | 温度-健康综合结论 | Chain |
| 42 | Analyst | DataAnalyzer | 全部分析结果 | 降水-健康综合结论 | Chain |
| 43 | Strategist | MetaPlanner | 综合结论 | H1/H2/H3验证裁定 | Chain |
| 44 | Critic | CriticEngine | 假设裁定 | **CDoL R3质疑** | Debate |
| 45 | FusionJudge | FusionEngine | R3质疑+全部 | **CDoL R3最终融合判定** | Debate |

### 阶段八：报告生成（步骤46-50，5步）

| 步骤 | Agent角色 | NexusFlow模块 | 输入 | 输出 | 拓扑模式 |
|------|-----------|--------------|------|------|----------|
| 46 | Archivist | ContextManager | 全部产物 | 报告大纲 | Chain |
| 47 | Archivist | ContextManager | 大纲+方法产物 | 研究方法章节 | Chain |
| 48 | Archivist | ContextManager | 大纲+分析产物 | 结果与讨论章节 | Chain |
| 49 | Archivist | ContextManager | 全部结论 | 摘要+结论章节 | Chain |
| 50 | Archivist | ContextManager | 完整草稿 | 质量检查+最终定稿 | Chain |

## 4. 拓扑模式切换设计

```
阶段一(1-3):  Chain串行     → Coordinator主导，任务分解
阶段一(4-6):  Parallel并行   → Researcher并行检索多个文献库
阶段一(7-8):  Chain串行      → 汇总整理
阶段二(9-12): Chain串行      → 逐步构建假设
阶段二(13):   Debate辩论     → Critic审查假设
阶段三(14-17):Parallel并行   → 多数据源并行获取
阶段三(18-20):Chain串行      → 逐步清洗
阶段四(21-23):Chain串行      → 实验设计
阶段四(24-25):Debate辩论     → Critic+FusionJudge审查
阶段四(26):   Chain串行      → 最终方案
阶段五(27-29):Parallel并行   → 多分析代码并行开发
阶段五(30-32):Tree树形       → 多分析并行执行
阶段五(33-34):Debate辩论     → CDoL R1
阶段六(35-38):Chain串行      → 代码实现
阶段六(39-40):Debate辩论     → CDoL R2
阶段七(41-43):Chain串行      → 结果综合
阶段七(44-45):Debate辩论     → CDoL R3
阶段八(46-50):Chain串行      → 报告生成
```

**拓扑切换点**：步骤3→4, 6→7, 12→13, 17→18, 23→24, 29→30, 32→33, 38→39, 43→44

**切换条件**：
- Chain→Parallel: 存在可独立执行的子任务
- Parallel→Chain: 需要汇聚结果
- Chain→Debate: 需要批判性审查节点
- Debate→Chain: 共识达成或达到最大轮次

## 5. 上下文窗口配置

| 阶段 | Token预算 | 窗口策略 | 说明 |
|------|----------|----------|------|
| 文献检索(1-8) | 32K | 滑动窗口 | 文献摘要累积，超过阈值自动压缩 |
| 假设生成(9-13) | 16K | 选择性加载 | 仅加载文献综述核心结论 |
| 数据获取(14-20) | 64K | 扩展窗口 | 原始数据需要大窗口 |
| 实验设计(21-26) | 24K | 标准窗口 | 框架+数据摘要 |
| 数据分析(27-34) | 48K | 动态扩展 | CDoL辩论需要完整历史 |
| 代码实现(35-40) | 32K | 标准窗口 | 代码+结果 |
| 结果综合(41-45) | 48K | 最大窗口 | CDoL R3需要全部历史 |
| 报告生成(46-50) | 64K | 最大窗口 | 完整报告需要全部产物 |

## 6. 10个Agent角色定义

| 角色 | 职责 | 主要活跃阶段 |
|------|------|-------------|
| **Coordinator** | 任务分解、路由调度、拓扑管理 | 阶段一 |
| **Strategist** | 研究策略、假设生成、框架设计 | 阶段二、四、七 |
| **Researcher** | 文献检索、数据获取、知识整合 | 阶段一、三 |
| **Analyst** | 统计分析、结果解读、CDoL回应 | 阶段五、七 |
| **Coder** | 代码实现、脚本开发、协议编码 | 阶段三、五、六 |
| **Critic** | 批判审查、质疑挑战、CDoL质疑方 | 阶段二-七(CDoL) |
| **FusionJudge** | 融合判定、共识度量、CDoL裁判 | CDoL各轮 |
| **Archivist** | 报告生成、产物整理、质量把关 | 阶段八 |
| **Reviewer** | 交叉审查、格式检查 | 阶段八末尾 |
| **Observer** | 过程监控、资源追踪、异常告警 | 全程 |

## 7. CDoL三轮辩论协议设计

### Round 1（步骤33-34）：方法论审查
- **Critic焦点**：生态学谬误、遗漏变量偏差、时间/空间自相关、因果推断局限
- **Analyst回应**：逐条辩护或承认+修正方案
- **终止条件**：方法论问题清单已确认

### Round 2（步骤39-40）：结果可靠性
- **Critic焦点**：效应量实际意义、样本代表性、模型选择偏差、多重比较、外部效度
- **FusionJudge判定**：共识度评分、分歧点裁决
- **终止条件**：共识度>0.7 或 确认核心分歧

### Round 3（步骤44-45）：整体结论
- **Critic焦点**：外部效度、政策可行性、实际贡献度
- **FusionJudge最终裁决**：最终共识度、可发表性判定、报告呈现建议
- **终止条件**：最终共识达成

## 8. 预期产物清单

| 产物 | 文件 | 格式 |
|------|------|------|
| 任务DAG | step01_task_dag.json | JSON |
| 拓扑路由 | step02_dag_routing.json | JSON |
| 分析框架 | step03_framework.md | Markdown |
| 文献综述 | step04_08_literature.md | Markdown |
| 假设体系 | step09_13_hypothesis.md | Markdown |
| NOAA数据 | step14_noaa_temp.json, step15_noaa_prcp.json | JSON |
| WHO数据 | step16c_who_life_expectancy.json, step17e_who_le_both.json | JSON |
| 清洗代码 | step18_cleaning_code.py | Python |
| 质量报告 | step19_quality_report.md | Markdown |
| 实验方案 | step20_26_experiment.md | Markdown |
| 分析结果 | step27_correlation.md ~ step31_lag_effect.md | Markdown |
| CDoL R1 | step33_critic_r1.md, step34_analyst_r1.md | Markdown |
| CDoL协议 | step36_cdol_protocol.py | Python |
| CDoL R2 | step39_critic_r2.md, step40_fusion_r2.md | Markdown |
| 综合结论 | step41_synthesis.md, step43_hypothesis.md | Markdown |
| CDoL R3 | step44_critic_r3.md, step45_final_fusion.md | Markdown |
| 报告章节 | step46_outline.md ~ step50_quality.md | Markdown |
