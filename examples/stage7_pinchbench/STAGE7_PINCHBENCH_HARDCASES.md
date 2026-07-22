# Stage 7: PinchBench Hard Cases 精选方案

> **日期**: 2026-07-22
> **目标**: 从PinchBench v2.0的100+任务中精选Hard Cases，验证NexusFlow多Agent协作在复杂真实任务上的优势

---

## 1. PinchBench概述

| 属性 | 值 |
|------|-----|
| **版本** | v2.0.0 (2026-05-06) |
| **仓库** | [pinchbench/skill](https://github.com/pinchbench/skill) |
| **总任务数** | 100+ (manifest注册) |
| **任务类别** | 9大类 (Productivity, Research, Writing, Analysis, Coding, CSV Analysis, Log Analysis, Meeting Analysis, Integration/Skills) |
| **评分方式** | automated / llm_judge / hybrid |
| **当前榜首** | 百度文心助手任务Agent 94.6% (2026-07-21) |
| **运行依赖** | OpenClaw agent框架 |

### PinchBench核心评测维度
1. **Tool Usage** — 调用正确的工具、传正确的参数
2. **Multi-step Reasoning** — 链式行动完成复杂任务
3. **Real-world Messiness** — 处理模糊指令和不完整信息
4. **Practical Outcomes** — 文件是否真正创建、邮件是否真正发送

### 与NexusFlow的映射关系

| PinchBench维度 | NexusFlow对应能力 | 关键Agent |
|----------------|-------------------|-----------|
| Tool Usage | 动态工具路由 + Edge/Cloud调度 | coordinator, executor |
| Multi-step Reasoning | Planner任务分解 + 多Agent编排 | planner, coordinator |
| Real-world Messiness | 认知熵管理 + 自适应恢复 | planner, reviewer |
| Practical Outcomes | Reviewer质量守门 + Assayer验证 | reviewer, assayer |

---

## 2. 筛选标准

### 2.1 选择原则

从100+任务中筛选，聚焦**能体现多Agent协作优势**的复杂任务：

| 维度 | 入选标准 | 排除标准 |
|------|----------|----------|
| **复杂度** | 需要≥3步子任务 | 单步确定性任务 |
| **多源性** | 需要综合多个数据源/文件 | 单一输入、单一输出 |
| **协调性** | 需要角色分工/交叉验证 | 纯文本生成 |
| **可评分性** | 有automated/hybrid评分 | 仅llm_judge（保留少量高价值任务） |
| **差异化** | 能展示NF vs SA差异 | SA也能轻松完成的任务 |

### 2.2 排除的任务类型

- **简单CSV统计** (iris_summary, cities_filter, stations_filter等): 单Agent pandas即可
- **Calendar创建** (task_calendar): 单步ICS生成
- **纯文本写作** (task_email, task_humanizer): 不涉及工具链
- **简单日志统计** (log_apache_top_errors, log_hdfs_connections): grep+sort即可

### 2.3 L3 Benchmark经验指导

根据Stage-6b实验结论：
- **SA优势领域**（避免作为主战场）: 模式识别、异常检测、反事实推理、交叉辩论
- **NF优势领域**（重点进攻）: 跨国相关性(+0.10)、因果链(+0.55)、多期预测(+0.25)、风险评估(+0.85)、政策建议(+1.20)

**策略**: 选择NF优势维度对应的PinchBench任务，同时不回避SA强势领域（作为对照）。

---

## 3. 精选25个Hard Cases

### 3.1 Tier-1: 核心展示任务（10个）

这些任务最能体现NexusFlow多Agent协作的独特优势。

| # | Task ID | 类别 | 评分 | 超时 | NF优势维度 | 预计NF亮点 |
|---|---------|------|------|------|-----------|-----------|
| 1 | `task_market_research` | Research | **hybrid** | 300s | 多源综合 | 多竞品调研+分析+报告生成 |
| 2 | `task_deep_research` | Research | llm_judge | 300s | 交叉验证 | 文献检索+引用验证+深度报告 |
| 3 | `task_contract_analysis` | Analysis | llm_judge | 300s | 风险评估+0.85 | 合同解析+风险识别+合规检查 |
| 4 | `task_cve_security_triage` | Analysis | **hybrid** | 300s | 因果链+0.55 | CVE分级+优先级排序+修复建议 |
| 5 | `task_session_chain_analysis` | Analysis | automated | 300s | 长程协调 | 跨4个Session的分析链 |
| 6 | `task_eu_regulation_research` | Research | llm_judge | 300s | 政策建议+1.20 | 法规分析+风险分类+合规路径 |
| 7 | `task_csv_pension_risk` | CSV Analysis | **hybrid** | 180s | 风险评估+0.85 | 数据清洗+比率计算+风险分层 |
| 8 | `task_multi_file_refactoring` | Coding | automated | 240s | 多步协调 | 跨4文件的函数重命名+引用更新 |
| 9 | `task_daily_summary` | Productivity | llm_judge | 300s | 多源综合 | 5个研究报告→executive briefing |
| 10 | `task_meeting_executive_summary` | Meeting | llm_judge | 300s | 多源综合 | 长会议记录→结构化摘要 |

### 3.2 Tier-2: 强力补充任务（8个）

| # | Task ID | 类别 | 评分 | 超时 | NF优势维度 |
|---|---------|------|------|------|-----------|
| 11 | `task_polymarket_briefing` | Research | **hybrid** | 180s | 多源实时数据融合 |
| 12 | `task_spreadsheet_summary` | Analysis | **hybrid** | 180s | 结构化数据处理 |
| 13 | `task_financial_ratio_calculation` | Analysis | automated | 240s | 精确计算+验证 |
| 14 | `task_csv_pension_liability` | CSV Analysis | **hybrid** | 180s | 数据深度分析 |
| 15 | `task_iterative_code_refine` | Coding | automated | 300s | 跨Session状态保持 |
| 16 | `task_cicd_pipeline_debug` | Coding | automated | 240s | 因果链推理 |
| 17 | `task_k8s_debugging` | Coding | automated | 240s | 多因素诊断 |
| 18 | `task_test_generation` | Coding | **hybrid** | 300s | 代码理解+测试设计 |

### 3.3 Tier-3: 跨领域覆盖任务（7个）

| # | Task ID | 类别 | 评分 | 超时 | 覆盖目的 |
|---|---------|------|------|------|---------|
| 19 | `task_byok_best_practices` | Research | llm_judge | 300s | 安全知识深度 |
| 20 | `task_meeting_gov_qa_extract` | Meeting | hybrid | 300s | 长文档信息提取 |
| 21 | `task_meeting_sentiment_analysis` | Meeting | llm_judge | 300s | 情感分析+立场识别 |
| 22 | `task_meeting_gov_controversy` | Meeting | hybrid | 300s | 争议点检测 |
| 23 | `task_log_apache_timeline` | Log Analysis | automated | 180s | 时序分析+异常检测 |
| 24 | `task_log_mapreduce_failures` | Log Analysis | automated | 180s | 分布式系统故障诊断 |
| 25 | `task_log_ssh_brute_force` | Log Analysis | automated | 180s | 安全入侵模式识别 |

### 3.4 分布统计

| 维度 | 数量 |
|------|------|
| **按类别** | Research: 6, Analysis: 4, Coding: 5, CSV Analysis: 2, Meeting: 4, Log Analysis: 3, Productivity: 1 |
| **按评分** | hybrid: 10, automated: 10, llm_judge: 5 |
| **按NF预期优势** | 强优势(≥0.85): 8, 中等优势(0.25-0.55): 9, 对照(SA强势领域): 8 |
| **按复杂度** | 极高(需≥5步): 10, 高(需3-4步): 15 |

---

## 4. NexusFlow适配架构

### 4.1 适配层设计

```
pinchbench/tasks/*.md          NexusFlow适配层
    │                              │
    ▼                              ▼
┌─────────────┐          ┌─────────────────────┐
│  PinchBench │          │  NexusFlow Engine    │
│  Task Def   │─────────▶│  ┌───────────────┐   │
│  (prompt +  │          │  │ task_parser    │   │  解析.md任务定义
│  workspace  │          │  │ task_runner    │   │  执行NexusFlow管线
│  grading)   │          │  │ task_grader    │   │  对接PinchBench评分
│             │          │  └───────────────┘   │
└─────────────┘          └─────────────────────┘
```

### 4.2 执行流程

```
PinchBench Task (.md)
    │
    ├── 1. 解析任务定义 (YAML frontmatter + prompt + workspace_files)
    │
    ├── 2. NexusFlow管线执行
    │       ├── planner: 任务分解 → sub-tasks
    │       ├── coordinator: 分配给合适的Agent
    │       ├── researcher/executor/caster: 执行子任务
    │       ├── reviewer: 质量审查
    │       └── assayer: 结果验证
    │
    ├── 3. 产物写入workspace (文件/报告/代码)
    │
    └── 4. 调用PinchBench grade()函数评分
            ├── automated: 文件检查 + 正则匹配
            ├── llm_judge: 调用裁判模型
            └── hybrid: 加权组合
```

### 4.3 Agent映射策略

| PinchBench任务需求 | NexusFlow Agent | Run Layer |
|-------------------|-----------------|-----------|
| 信息检索/搜索 | researcher | EDGE |
| 代码生成/修改 | caster | CLOUD |
| 文件操作/执行 | executor | EDGE |
| 数据分析/计算 | assayer | CLOUD |
| 文档写作/报告 | artisan | EDGE |
| 质量审查 | reviewer | EDGE |
| 任务分解/调度 | planner + coordinator | CLOUD |

### 4.4 关键适配挑战

| 挑战 | 解决方案 |
|------|---------|
| PinchBench依赖OpenClaw | 编写NexusFlow适配层替换OpenClaw执行管线 |
| workspace_files注入 | 复用PinchBench的assets/目录，注入NexusFlow工作区 |
| automated grading | 直接调用task.md中嵌入的grade()函数 |
| llm_judge grading | 实现兼容PinchBench judge协议的评分接口 |
| 超时控制 | NexusFlow的timeout参数对齐PinchBench设置 |
| multi-session任务 | 使用NexusFlow的session管理模拟PinchBench的new_session |

---

## 5. 实施路线

### Phase 1: 基础设施（2天）
- [ ] 克隆pinchbench/skill仓库
- [ ] 编写task_parser：解析PinchBench task.md格式
- [ ] 编写workspace_manager：管理workspace_files注入和产物收集
- [ ] 编写grade_bridge：对接PinchBench评分系统

### Phase 2: Tier-1核心任务适配（3天）
- [ ] 为10个Tier-1任务设计Agent调度策略
- [ ] 实现NexusFlow执行管线与PinchBench任务接口
- [ ] 逐任务调试，确保产物格式兼容

### Phase 3: 运行与对比（2天）
- [ ] SA模式（单Agent baseline）运行25个任务
- [ ] NF模式（NexusFlow 10-Agent）运行25个任务
- [ ] 自动评分 + 结果收集

### Phase 4: 报告与分析（1天）
- [ ] 生成Stage-7对比报告
- [ ] 维度分析（工具使用、多步推理、鲁棒性、产出质量）
- [ ] 更新README和技术文档

**预计总工期: 8天**

---

## 6. 预期产出

### 6.1 文件结构

```
examples/stage7_pinchbench/
├── STAGE7_PINCHBENCH_HARDCASES.md  # 本文档
├── pinchbench_skill/               # PinchBench仓库（clone）
├── run_pinchbench.py               # 主执行脚本
├── task_parser.py                  # PinchBench任务解析器
├── grade_bridge.py                 # 评分桥接器
├── data/
│   ├── sa_results.json             # SA模式结果
│   ├── nf_results.json             # NF模式结果
│   └── comparison.json             # 对比数据
└── stage7_report.md                # 最终报告
```

### 6.2 预期结果

基于L3 Benchmark的NF优势模式，预测：
- NF在Research类任务（多源综合）上领先SA 15-25%
- NF在Analysis类任务（因果推理、风险评估）上领先SA 10-20%
- NF在Coding类任务（多步协调）上领先SA 5-15%
- NF在Log Analysis类（模式识别）上与SA持平或微胜
- NF整体平均分预期高于SA 10-15%

---

## 附录A: PinchBench完整任务清单

### Productivity (4)
| Task ID | 名称 | 评分 | 精选? |
|---------|------|------|-------|
| task_calendar | Calendar Event Creation | automated | ❌ 单步 |
| task_pdf_to_calendar | PDF to Calendar Import | automated | ❌ 单步 |
| task_daily_summary | Daily Research Summary | llm_judge | ✅ #9 |
| task_subway_navigation | NYC Subway Navigation | llm_judge | ❌ 空间推理 |

### Research (11+)
| Task ID | 名称 | 评分 | 精选? |
|---------|------|------|-------|
| task_stock | Stock Price Research | automated | ❌ 单步查询 |
| task_events | Tech Conference Research | llm_judge | ❌ 信息列举 |
| task_market_research | Competitive Market Research | hybrid | ✅ #1 |
| task_polymarket_briefing | Polymarket + News Briefing | hybrid | ✅ #11 |
| task_it_procurement | IT Procurement Research | llm_judge | ❌ 偏列举 |
| task_deep_research | Deep Research with Citations | llm_judge | ✅ #2 |
| task_eu_regulation_research | EU AI Act Compliance | llm_judge | ✅ #6 |
| task_oss_alternative_research | OSS Alternatives Research | llm_judge | ❌ 偏列举 |
| task_pricing_research | Vendor Pricing Comparison | llm_judge | ❌ 偏列举 |
| task_competitive_research | Competitive Product Comparison | llm_judge | ❌ 与#1重叠 |
| task_byok_best_practices | BYOK Best Practices | llm_judge | ✅ #19 |

### Analysis (7)
| Task ID | 名称 | 评分 | 精选? |
|---------|------|------|-------|
| task_spreadsheet_summary | CSV/Excel Data Summarization | hybrid | ✅ #12 |
| task_eli5_pdf_summary | ELI5 PDF Summarization | llm_judge | ❌ 纯改写 |
| task_summary | Document Summarization | llm_judge | ❌ 与#9重叠 |
| task_financial_ratio_calculation | Financial Ratio Calculation | automated | ✅ #13 |
| task_contract_analysis | Contract/Legal Analysis | llm_judge | ✅ #3 |
| task_cve_security_triage | CVE/Security Triage | hybrid | ✅ #4 |
| task_session_chain_analysis | Session Chain Analysis | automated | ✅ #5 |

### Coding (10)
| Task ID | 名称 | 评分 | 精选? |
|---------|------|------|-------|
| task_multi_file_refactoring | Multi-file Refactoring | automated | ✅ #8 |
| task_iterative_code_refine | Iterative Code Refinement | automated | ✅ #15 |
| task_cicd_pipeline_debug | CI/CD Pipeline Debugging | automated | ✅ #16 |
| task_k8s_debugging | Kubernetes Debugging | automated | ✅ #17 |
| task_test_generation | Test Generation | hybrid | ✅ #18 |
| task_dockerfile_optimization | Dockerfile Optimization | automated | ❌ 单文件 |
| task_selector_fix | Test Selector Fix | automated | ❌ 太简单 |
| task_weather | Weather Script | automated | ❌ 单步 |
| task_readme_generation | README Generation | llm_judge | ❌ 纯写作 |
| task_commit_message_writer | Commit Message Writer | llm_judge | ❌ 纯写作 |

### CSV Analysis (30)
| Task ID | 精选? | 原因 |
|---------|-------|------|
| task_csv_pension_risk | ✅ #7 | 多因子风险评估+数据清洗 |
| task_csv_pension_liability | ✅ #14 | 深度财务分析 |
| 其余28个 | ❌ | 统计计算类，单Agent pandas即可 |

### Meeting Analysis (30)
| Task ID | 精选? | 原因 |
|---------|-------|------|
| task_meeting_executive_summary | ✅ #10 | 多文档综合 |
| task_meeting_gov_qa_extract | ✅ #20 | 结构化信息提取 |
| task_meeting_sentiment_analysis | ✅ #21 | 多维度分析 |
| task_meeting_gov_controversy | ✅ #22 | 争议点检测 |
| 其余26个 | ❌ | 单一维度提取，SA可胜任 |

### Log Analysis (24)
| Task ID | 精选? | 原因 |
|---------|-------|------|
| task_log_apache_timeline | ✅ #23 | 时序分析+burst检测 |
| task_log_mapreduce_failures | ✅ #24 | 分布式系统诊断 |
| task_log_ssh_brute_force | ✅ #25 | 安全模式识别 |
| 其余21个 | ❌ | grep+聚合即可 |
