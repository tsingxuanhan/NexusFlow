# P0 可复现性问题扫描报告

> **扫描时间**: 2026-07-22
> **扫描范围**: `examples/` 目录全部文件
> **上次审计**: 2026-07-20（总评 4.5/10，发现 6 项 P0）
> **涉及修复提交**: `2fee87f`、`08bc004`、`a342066`

---

## 总览

| P0 编号 | 类别 | 当前状态 | 严重度 |
|:-------:|------|:--------:|:------:|
| P0-1 | 密钥泄露 | ✅ **已修复** | — |
| P0-2 | MAPE指标口径一致性 | ✅ **已修复** | — |
| P0-3 | 横向对比评分体系统一 | ⚠️ **部分修复** | 高 |
| P0-4 | NOAA数据完整性 | ✅ **已修复** | — |
| P0-5 | 外部语料库依赖 | ⚠️ **仍有问题** | 中 |
| P0-6 | 脚本可运行性 | ⚠️ **仍有问题** | 中 |

---

## P0-1: 密钥泄露

### 当前状态: ✅ 已修复

**修复提交**: `a342066` — `fix(P0): remove hardcoded API keys from config.py and prepare_real_data.py`

#### 检查过程

对 `examples/` 下所有 `.py` / `.json` / `.yaml` / `.md` 文件执行正则扫描：

```
正则: sk-[a-zA-Z0-9]{15,} | nvapi-[a-zA-Z0-9]{15,} | API_KEY\s*=\s*"[^"]{16,}"
```

**扫描结果**：当前文件树中 **未发现任何硬编码密钥**。

#### 已修复的具体项

| 文件 | 行号 | 原问题 | 修复方式 |
|------|:----:|------|---------|
| `stage7_pinchbench/adapter/config.py` | L14 | 硬编码回退密钥 `sk-e7bdbfd58dc847468d613411cee35951` | 改为 `os.environ.get("DEEPSEEK_API_KEY", "") or ""` |
| `workbuddy_comparison/real_llm/prepare_real_data.py` | L10 | 硬编码 `NEW_KEY = 'sk-41c92afd7cb5461b842a9874f7ed1f2c'` | 改为 `os.environ.get('DEEPSEEK_API_KEY', '')` |

#### 残留风险

1. **Git 历史仍含密钥**：两个密钥值仍存在于 git 历史中（commit `a342066` 之前）。如需公开仓库，建议：
   - 使用 `git filter-repo` 或 BFG Repo-Cleaner 清除历史
   - **立即轮换（rotate）这两个 API Key**
2. **文档注释不一致**：`config.py` L15 的 docstring 仍写着 "回退到硬编码值"，但实际已无回退值。属低优先级文档问题。
3. `stage3_full_system/stage3_full_system.py` L40 存在 `DEEPSEEK_API_KEY = "sk-your-key-here"`——这是占位符而非真实密钥，风险低但建议统一改为 `os.environ.get()` 模式。

---

## P0-2: MAPE指标口径一致性

### 当前状态: ✅ 已修复

**修复提交**: `08bc004` — `docs: NOAA MAPE 口径修正与勘误（P0-1）`

#### 检查过程

交叉比对以下三处 MAPE 数据：

| 文档 | MAPE 口径 | 单Agent | 多Agent | 一致性 |
|------|----------|:-------:|:-------:|:------:|
| `benchmark_summary.md` | 三物理量（tmax/tmin/prcp） | 9.31% | 9.37% | ✅ |
| `noaa_climate_diagnosis/report.md` | 三物理量 | — | 五城平均 9.4% | ✅ |
| `stage1_single_vs_6roles/README.md` | 三物理量（tmax/tmin/prcp） | 9.31% | 9.37% | ✅ |
| `stage1_single_vs_6roles/data/noaa_v2/CORRECTION.md` | 三物理量 | 9.31% | 9.37% | ✅（基准） |

#### 逐城市 MAPE 一致性验证

| 城市 | benchmark_summary.md | CORRECTION.md | report.md | 一致 |
|------|:---:|:---:|:---:|:---:|
| 北京 | 4.74% / 7.47% | 4.74% / 7.47% | 7.91%+10.66%+3.84%→**7.47%** | ✅ |
| 天津 | 4.24% / 3.90% | 4.24% / 3.90% | 0.43%+0.27%+11.01%→**3.90%** | ✅ |
| 石家庄 | 13.47% / 3.50% | 13.47% / 3.50% | 1.69%+0.21%+8.58%→**3.49%** | ✅（四舍五入） |
| 济南 | 12.15% / 24.44% | 12.15% / 24.44% | 6.46%+9.71%+57.15%→**24.44%** | ✅ |
| 西安 | 11.97% / 7.53% | 11.97% / 7.53% | 14.01%+2.86%+5.72%→**7.53%** | ✅ |

#### 口径标注一致性

- ✅ `benchmark_summary.md` 明确标注 "综合MAPE（三物理量同口径）"，含口径勘误注释
- ✅ `stage1_single_vs_6roles/README.md` 标注 "同口径（三物理量）"，链接到 CORRECTION.md
- ✅ `report.md` 使用 tmax/tmin/prcp 三物理量计算综合 MAPE
- ✅ CORRECTION.md 完整记录了问题和修正过程

#### 结论

所有文档已统一到三物理量（tmax/tmin/prcp）口径。"精度提升50%"的旧说法已被替换为"同口径持平"。`noaa_climate_diagnosis/report.md` 的五城平均 9.4% 与 9.37% 的差异属四舍五入（报告内各城市明细数据验证一致）。

---

## P0-3: 横向对比评分体系统一

### 当前状态: ⚠️ 部分修复（仍有矛盾）

**修复提交**: `2fee87f` — 评分体系统一（部分）

#### 问题分析

`examples/horizontal_comparison/` 目录中存在 **6 个不同来源的评分结果**，对同一框架的评分差异巨大：

##### NexusFlow 评分汇总

| 文件 | NexusFlow 得分 | 评估方式 | 时间 |
|------|:---:|------|------|
| `comparison_report.md` §4（LLM 5维） | **75** | LLM 5维评分 | 2026-07-07 |
| `comparison_report.md` §4（10维度手工） | **75** | 10维度加权 | 2026-07-13 |
| `comparison_results.json`（真实执行） | **84.5** | 确定性规则评估 | 2026-07-14 |
| `real_evaluation_results.json` | **86.5** | 确定性规则评估 | 2026-07-14 |
| `evaluation_scores.md`（手工10维度） | **92** | 10维度手工评分 | — |
| `multi_framework_comparison.json` | **75.0** | 10维度评分 | 2026-07-17 |
| `nexusflow_real_result.json` | **83.5** | 确定性规则评估 | 2026-07-14 |
| `llm_evaluation_results.json`（LLM 5维） | **75.0** | LLM 5维评分 | — |

##### AutoGen 评分汇总

| 文件 | AutoGen 得分 | 评估方式 | 时间 |
|------|:---:|------|------|
| `comparison_report.md` §4（LLM 5维） | **72** | LLM 5维评分 | 2026-07-07 |
| `comparison_report.md` §4（10维度手工） | **72** | 10维度加权 | 2026-07-13 |
| `comparison_results.json`（真实执行） | **100.0** | 确定性规则评估 | 2026-07-14 |
| `real_evaluation_results.json` | **55.5** | 确定性规则评估 | 2026-07-14 |
| `evaluation_scores.md`（手工10维度） | **88** | 10维度手工评分 | — |
| `multi_framework_comparison.json` | **72.0** | 10维度评分 | 2026-07-17 |
| `llm_evaluation_results.json`（LLM 5维） | **72.0** | LLM 5维评分 | — |

#### 具体矛盾

| # | 矛盾描述 | 严重度 |
|---|---------|:------:|
| 1 | **NexusFlow 有 5 个不同得分**：75 / 83.5 / 84.5 / 86.5 / 92，缺乏唯一权威分 | 🔴 高 |
| 2 | **AutoGen 有 4 个不同得分**：55.5 / 72 / 88 / 100，差异从 55.5 到满分 | 🔴 高 |
| 3 | `comparison_results.json` 给 AutoGen **满分 100**（所有维度=10），但 `real_evaluation_results.json` 给 AutoGen **55.5**（数据准确性=0） — 同一天执行的两次评估结果完全矛盾 | 🔴 高 |
| 4 | `evaluation_scores.md` 的对比总表（L64）有 **格式错误**：`| 交叉验证 | 10% | 8 | 4 | 4 |` — 多出一列 "4"，且加权总分行多出一列 "85"（`**92** | **88** | **85**`） | 🟡 中 |
| 5 | `comparison_report.md` §8 的真实执行结果表（NexusFlow=84.5, AutoGen=90.0）与 `comparison_results.json`（AutoGen=100.0）不一致 | 🟡 中 |
| 6 | `llm_evaluation_results.json` 使用 **5 维评分**（completeness/depth/consistency/novelty/actionability），而 `evaluation_scores.md` 使用 **10 维评分**，两者评估体系不同但混在同一目录中无明确区分 | 🟡 中 |

#### 建议修复方案

1. **指定权威评分文件**：选择一个评估版本作为"最终权威"（建议选 `comparison_results.json` 的确定性规则评估），其他版本明确标注为"历史版本/备选评估"
2. **清理矛盾数据**：删除或归档冲突的 JSON 文件（如 `comparison_results.json` 中 AutoGen=100 的版本），或明确标注各文件的评估时间和方法论
3. **修复 `evaluation_scores.md` 表格格式**：L64 去掉多余的列 "4"，L69 去掉多余的 "85"
4. **统一评估体系**：将所有文件收敛到同一评估维度（10 维度或 5 维度），或在每个文件中明确标注评估方法

---

## P0-4: NOAA数据完整性

### 当前状态: ✅ 已修复

#### 检查过程

##### 文件一致性

| 检查项 | 结果 |
|--------|:----:|
| `noaa_climate_diagnosis/agent_log.md` 与 `stage1_single_vs_6roles/data/noaa_v2/agent_log.md` 一致性 | ✅ MD5 相同（`ac5490df`） |
| `noaa_climate_diagnosis/report.md` 与 `stage1_single_vs_6roles/data/noaa_v2/` 的关系 | ✅ 报告位于 noaa_climate_diagnosis/，数据文件位于 noaa_v2/ |

##### agent_log.md 步骤编号连续性

- 总步骤数：**82 步**
- 编号范围：**1 ~ 82**
- 缺失步骤：**无**
- 重复步骤：**无**
- ✅ 步骤编号完全连续

##### 数据文件完整性

| 目录 | 文件数 | 关键文件 | 状态 |
|------|:------:|---------|:----:|
| `noaa_climate_diagnosis/` | 2 | `report.md`, `agent_log.md` | ✅ |
| `stage1_single_vs_6roles/data/noaa_v2/` | 5 | `CORRECTION.md`, `agent_log.md`, `corrected_trends.json`, `multi_agent_results.json`, `single_agent_results.json` | ✅ |
| `stage1_single_vs_6roles/data/noaa/` | 9 | `raw_*.json`（5城）, `analysis_results.json`, `raw_data.json`, `results_summary.json`, `validation_data.json` | ✅ |

#### 结论

NOAA 数据文件完整，两个位置的 `agent_log.md` 为同一文件的副本（MD5 一致），步骤编号连续无缺失。CORRECTION.md 已正确创建，记录了口径修正过程。

---

## P0-5: 外部语料库依赖

### 当前状态: ⚠️ 仍有问题

#### 扫描结果

##### 依赖清单

| # | 目录/脚本 | 外部依赖 | 本地是否存在 | 下载脚本/说明 | 状态 |
|---|----------|---------|:----------:|:----------:|:----:|
| 1 | `nemotron_benchmark/eval_dataset/corpus.json` | 自建语料（127行 JSON） | ✅ | — | ✅ 无问题 |
| 2 | `nemotron_benchmark/eval_dataset/auto_qa.json` | 自建 QA 数据集 | ✅ | — | ✅ 无问题 |
| 3 | `nemotron_benchmark/eval_dataset/adversarial.json` | 自建对抗数据集 | ✅ | — | ✅ 无问题 |
| 4 | `nemotron_benchmark/eval_dataset/skill_tasks.json` | 自建技能任务集 | ✅ | — | ✅ 无问题 |
| 5 | `nemotron_benchmark/e4_v2_repo_corpus.py` | **NIM API Key**（`--nim_api_key`） | ❌ 需外部 Key | ⚠️ 需手动提供 | ⚠️ |
| 6 | `nemotron_benchmark/e_all_v2_full_repos.py` | **NIM API Key** + 全仓库文件 | ❌ 需外部 Key | ⚠️ | ⚠️ |
| 7 | `workbuddy_comparison/data/表A_历史数据_1980-2020.xlsx` | 历史气象/经济数据 | ✅ 已包含 | — | ✅ 无问题 |
| 8 | `workbuddy_comparison/data/表B_回测真值.xlsx` | 回测真值数据 | ✅ 已包含 | — | ✅ 无问题 |
| 9 | `workbuddy_comparison/scripts/*.py`（5个脚本） | **硬编码 Windows 路径** `C:\Users\ASUS\Desktop\...` | ❌ 不可移植 | ❌ 无说明 | 🔴 **P0** |
| 10 | `workbuddy_comparison/real_llm/prepare_real_data.py` | **硬编码 Windows 路径** `C:\Users\ASUS\Desktop\...` | ❌ 不可移植 | ❌ 无说明 | 🔴 **P0** |
| 11 | `workbuddy_comparison/real_llm/real_benchmark_macro.py` | **硬编码 Windows 路径** `C:\Users\ASUS\Desktop\...` | ❌ 不可移植 | ❌ 无说明 | 🔴 **P0** |
| 12 | `workbuddy_comparison/real_llm/prepare_real_data.py` L216 | **硬编码输出路径** `C:\Users\ASUS\WorkBuddy\2026-07-20-19-24-07\` | ❌ 不可移植 | ❌ 无说明 | 🔴 **P0** |
| 13 | `workbuddy_comparison/scripts/compute_backtest.py` | **硬编码输入/输出路径** `C:\Users\ASUS\WorkBuddy\...` | ❌ 不可移植 | ❌ 无说明 | 🔴 **P0** |
| 14 | `stage7_pinchbench/adapter/config.py` | **PinchBench 远程资源** `https://raw.githubusercontent.com/pinchbench/skill/main/tasks` | 部分缓存 | ✅ 有本地 `tasks_raw/` 缓存 | ⚠️ |

##### 问题详情

**P0 级：workbuddy_comparison 硬编码路径（14 处）**

以下脚本使用了 Windows 开发者机器的绝对路径，在任何其他环境均无法运行：

| 文件 | 行号 | 硬编码路径 |
|------|:----:|----------|
| `scripts/compute_backtest.py` | L7, L9, L106 | `C:\Users\ASUS\WorkBuddy\2026-07-20-19-24-07\` |
| `scripts/compute_nf_predictions.py` | L10, L13, L14, L317 | `C:\Users\ASUS\Desktop\` + `C:\Users\ASUS\WorkBuddy\...` |
| `scripts/compute_stats.py` | L11, L12 | `C:\Users\ASUS\Desktop\表A/B` |
| `scripts/inspect_data.py` | L14, L15 | `C:\Users\ASUS\Desktop\表A/B` |
| `real_llm/prepare_real_data.py` | L51, L216 | `C:\Users\ASUS\Desktop\` + 输出目录 |
| `real_llm/real_benchmark_macro.py` | L47 | `C:\Users\ASUS\Desktop\表B` |

**建议修复**：将所有硬编码路径改为相对于脚本所在目录的路径，例如：
```python
TABLE_A = os.path.join(os.path.dirname(__file__), '..', 'data', '表A_历史数据_1980-2020.xlsx')
```

---

## P0-6: 脚本可运行性

### 当前状态: ⚠️ 仍有问题

#### 检查过程

##### 语法检查（AST 解析）

对 `examples/` 下所有 `.py` 文件执行 `ast.parse()` 语法检查：

| 状态 | 文件数 | 说明 |
|:----:|:------:|------|
| ✅ 通过 | ~60 | 主要脚本语法正确 |
| ❌ 失败 | 9 | `stage4_fifty_steps/artifacts/` 和 `data/artifacts/` 下的文件 |

**语法失败文件详情**：

这些 `.py` 文件实际是 **Markdown 文档中嵌入的代码片段**，不是独立可运行的 Python 脚本——文件以 ` ```python ` 或中文描述开头：

| 文件 | 首行内容 | 性质 |
|------|---------|------|
| `stage4_fifty_steps/artifacts/step18_data_cleaning_script.py` | ` ```python ` | Markdown 代码块 |
| `stage4_fifty_steps/artifacts/step27_correlation_analysis_code.py` | `以下是...分析脚本。` | 中文散文+代码 |
| `stage4_fifty_steps/artifacts/step36_cdol_protocol_code.py` | `以下是...协议代码。` | 中文散文+代码 |
| `stage4_fifty_steps/data/artifacts/step18_cleaning_code.py` | `，` 开头 | 伪代码描述 |
| `stage4_fifty_steps/data/artifacts/step18_data_cleaning_script.py` | ` ```python ` | 同上 |
| `stage4_fifty_steps/data/artifacts/step27_correlation_analysis_code.py` | `以下是...` | 同上 |
| `stage4_fifty_steps/data/artifacts/step28_regression_analysis_code.py` | `，` 开头 | 同上 |
| `stage4_fifty_steps/data/artifacts/step36_cdol_protocol.py` | `（` 开头 | 同上 |
| `stage4_fifty_steps/data/artifacts/step36_cdol_protocol_code.py` | `以下是...` | 同上 |

**建议**：将这些文件重命名为 `.md` 或 `.py.md`，或在 `stage4_fifty_steps/README.md` 中说明这些文件是"步骤产物描述"而非可执行脚本。

##### Import 路径检查

| 脚本类别 | 依赖 | 状态 |
|---------|------|:----:|
| `stage7_pinchbench/adapter/runner.py` | 包内相对导入（`.config`, `.task_parser` 等） | ✅ OK |
| `stage7_pinchbench/adapter/config.py` | `os`, `pathlib` | ✅ OK |
| `nemotron_benchmark/bench_utils.py` | `sys.path.insert(REPO_ROOT)` | ✅ OK |
| `demo/*.py` | `from nexusflow.core.*` | ✅ OK（nexusflow 包存在） |
| `demo_dashboard.py` | `from nexusflow.core.*` | ✅ OK |
| `horizontal_comparison/*.py` | 标准库 + 环境变量 | ✅ OK |

##### 硬编码路径导致的不可运行

`workbuddy_comparison/scripts/` 和 `real_llm/` 下的 6 个脚本因硬编码 Windows 路径，在非 Windows 或非原开发者机器上 **无法运行**（详见 P0-5 第 9-14 项）。

##### 外部 API 依赖

以下脚本需要有效的 DeepSeek API Key（通过环境变量 `DEEPSEEK_API_KEY`）才能运行：

| 脚本 | API 依赖 |
|------|---------|
| `demo/cdol_real_experiment.py` | DeepSeek API |
| `demo_full_system.py` | DeepSeek API |
| `demo_real_e2e.py` | DeepSeek API |
| `horizontal_comparison/experiment.py` | DeepSeek API |
| `horizontal_comparison/crewai_comparison.py` | DeepSeek API + CrewAI |
| `horizontal_comparison/langgraph_comparison.py` | DeepSeek API + LangGraph |
| `horizontal_comparison/real_autogen_comparison.py` | DeepSeek API + AutoGen |
| `stage3_full_system/stage3_full_system.py` | DeepSeek API |
| `stage5_eighty_steps/run_real_benchmark.py` | DeepSeek API |
| `stage6_L3_cognitive_tasks/run_L3_benchmark.py` | DeepSeek API |
| `nemotron_benchmark/e4_v2_repo_corpus.py` | NIM API |

这些脚本均有 `os.environ.get()` 获取密钥，**设计正确**，但缺少 README 中的"前置条件"说明。

---

## 综合评估

### 修复进度

| P0 编号 | 2026-07-20 审计 | 当前状态 | 变化 |
|:-------:|:--------------:|:--------:|:----:|
| P0-1 密钥泄露 | 🔴 6处硬编码密钥 | ✅ 已修复 | commit `a342066` |
| P0-2 MAPE口径 | 🔴 口径不一致 | ✅ 已修复 | commit `08bc004` |
| P0-3 评分体系统一 | 🔴 多版本评分矛盾 | ⚠️ 部分修复 | commit `2fee87f` 部分统一 |
| P0-4 NOAA数据完整性 | 🔴 步骤不连续/数据缺失 | ✅ 已修复 | 数据完整 |
| P0-5 外部语料库依赖 | 🟡 缺失外部数据 | ⚠️ 仍有问题 | workbuddy 硬编码路径未修 |
| P0-6 脚本可运行性 | 🟡 import失败 | ⚠️ 仍有问题 | stage4 artifacts 非真实脚本 |

### 当前总评: **6.5/10**（较上次 4.5/10 提升 2 分）

### 剩余需修复项（按优先级排序）

| 优先级 | 项目 | 工作量 | 建议 |
|:------:|------|:------:|------|
| 🔴 高 | P0-3: 统一 horizontal_comparison 评分体系 | 2-4h | 指定权威评分文件，清理矛盾数据 |
| 🔴 高 | P0-5: workbuddy 硬编码路径（14处） | 1-2h | 改为相对路径 |
| 🟡 中 | P0-6: stage4 artifacts 重命名 | 0.5h | `.py` → `.py.md` 或加 README 说明 |
| 🟡 中 | P0-1: 清理 git 历史中的密钥 | 1h | 使用 BFG/filter-repo（如需公开） |
| 🟢 低 | P0-1: config.py docstring 修正 | 5min | 更新注释 |
| 🟢 低 | P0-3: evaluation_scores.md 表格格式 | 5min | 去掉多余列 |

---

*扫描完成。报告由自动化扫描工具生成。*
