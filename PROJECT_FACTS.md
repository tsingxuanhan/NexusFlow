# PROJECT_FACTS.md — NexusFlow 项目事实清单

> **本文件是项目统计数据的唯一权威来源。** README、技术文档、答辩材料中的所有数字必须与此文件一致。
> 可通过 `python scripts/generate_facts.py` 自动重新生成。

*最后更新：2026-08-05 | 数据版本：v3.6.0*

---

## 一、代码规模

| 维度 | 数据 | 统计方式 |
|------|------|----------|
| Git tracked 文件总数 | **769** | `git ls-files \| wc -l` |
| Python 文件数 | **216** | `git ls-files '*.py' \| wc -l` |
| Python 总行数 | **91,863** | `git ls-files '*.py' \| xargs wc -l` |
| 项目总行数（全类型） | **298,454** | `git ls-files \| xargs wc -l` |

### 按目录分布

| 目录 | 文件数 | Python LOC | 说明 |
|------|--------|------------|------|
| `nexusflow/` | 74 | 31,643 | 框架核心代码 |
| `tools/` | 19 | 5,222 | 内置工具（含 `__init__.py`） |
| `server/` | 6 | 9,202 | 服务端 + Dashboard |
| `tests/` | 14 | 3,979 | 自动化测试 |
| `evaluation/` | 28 | 6,317 | 评测模块 |
| `examples/` | 435 | 34,255 | 示例 + 实验脚本 + 资源 |
| `scripts/` | 11 | 905 | 辅助脚本 |
| `frontend/` | 30 | 2,716 | Vite + React + TypeScript Dashboard |

---

## 二、核心模块

### 核心模块总数：**88**（71 nexusflow/ + 17 tools/，不含 `__init__.py`）

### 六大核心引擎

| 模块 | 文件 | 行数 | 核心能力 |
|------|------|------|----------|
| CDoL 认知分工引擎 | `cognitive_division_engine.py` | 2,058 | 6 种视角分解 + 三轮有损通信 + 虚假一致检测 |
| 自适应上下文管理器 | `adaptive_context_manager.py` | 1,642 | 动态裁剪上下文，对抗"大窗口懒惰症" |
| 动态拓扑路由器 | `dynamic_router.py` | 1,001 | 5 种拓扑模式，任务感知路由 + UCB1 优化 |
| 端边云调度器 | `edge_cloud_scheduler.py` | 635 | 隐私优先混合调度 |
| 目标验证器 | `goal_verifier.py` | 589 | 目标达成度验证 |
| 三层信息架构 | `agent_information_policy.py` | 511 | 全局/CDoL/旁观三层权限 |
| 统一编排器 | `nexus_orchestrator.py` | 479 | 自动路由 + 蒸馏归档 |
| 技能检索器 | `skill_retriever.py` | 408 | RRF 混合检索 |

**核心引擎合计：7,323 行**

### Agent 架构

| 组件 | 行数 | 说明 |
|------|------|------|
| BaseAgent | 1,211 | 主类 |
| Agent 模块文件 | 26 个 | 含 domains/、quality.py、guardrails.py、mixins 等 |

### 核心算法创新

| 模块 | 行数 |
|------|------|
| CDoL 引擎 | 2,058 |
| SkillRetriever | 408 |
| **合计** | **2,466** |

---

## 三、Agent 角色矩阵（10 个）

| # | Agent | 英文标识 | 部署层级 | 职责 |
|---|-------|----------|----------|------|
| 1 | Coordinator | `coordinator` | ☁️ 云端 | 任务分解、路由分发 |
| 2 | Planner | `planner` | ☁️ 云端 | 策略规划、步骤编排 |
| 3 | Researcher | `researcher` | ☁️ 云端 | 信息检索、文献分析 |
| 4 | Executor | `executor` | 🖥️ 边端 | 代码执行、工具调用 |
| 5 | Reviewer | `reviewer` | ☁️ 云端 | 质量审核、逻辑校验 |
| 6 | Miner | `miner` | 🖥️ 边端 | 数据挖掘、模式识别 |
| 7 | Caster | `caster` | ☁️ 云端 | 结果铸造、格式统一 |
| 8 | Archivist | `archivist` | ☁️ 云端 | 蒸馏归档、知识沉淀 |
| 9 | Assayer | `assayer` | 📱 终端 | 结果化验、交叉验证 |
| 10 | Artisan | `artisan` | 📱 终端 | 工艺打磨、细节优化 |

**信息架构**：全局视野层（2：Coordinator, Planner）→ CDoL 参与层（7）→ 旁观记录层（1：Archivist）

---

## 四、工具生态（18 个）

| # | 工具 | 说明 |
|---|------|------|
| 1 | `api_caller` | API 调用 |
| 2 | `browser` | 浏览器自动化 |
| 3 | `calculator` | 计算器 |
| 4 | `code_exec` | 代码执行 |
| 5 | `data_query` | 数据查询 |
| 6 | `data_validator` | 数据校验 |
| 7 | `file_ops` | 文件操作 |
| 8 | `git_ops` | Git 操作 |
| 9 | `literature_search` | 文献检索 |
| 10 | `model_router` | 模型路由 |
| 11 | `od_design_tool` | Open Design 工具 |
| 12 | `pdf_reader` | PDF 读取 |
| 13 | `report_generator` | 报告生成 |
| 14 | `scheduler` | 调度器 |
| 15 | `tool_registry` | 工具注册中心 |
| 16 | `web_search` | 网络搜索 |
| 17 | `base_tool` | 工具基类 |
| 18 | `office_cli` | Office 文档操作 |

---

## 五、系统配置

| 维度 | 数据 |
|------|------|
| Agent 角色数 | **10** |
| CDoL 分解策略 | **6** |
| 拓扑模式 | **5**（simple/research/coding/cdol/adaptive） |
| 记忆层级 | **4**（Working/Episodic/Semantic/Archival） |
| Benchmark 阶段 | **8**（Stage-1/2/3/4/5/6/6b/7/8） |
| 自动化测试 | **14 个测试文件** + conftest.py |
| API 集成测试 | **16 个用例**（test_api_integration.py） |
| CI 工作流 | **6**（tests/lint/docker/docs/security/frontend） |
| 可运行 Demo | **10 个** |
| 服务端口 | **8900** |
| 默认模型 | DeepSeek API (云端) + Ollama (边端/终端) |
| Dashboard 版本 | **v13**（单文件 HTML，内联部署） |
| 前端技术栈 | Vite + React + TypeScript + Tailwind v4 |

---

## 六、安全加固（v3.6.0）

| 防护项 | 措施 |
|--------|------|
| 路径穿越 | `os.path.realpath` 校验，拒绝 `..`/`/`/`\` |
| 文件上传 | 50MB 上限 + 危险扩展名黑名单 |
| CORS | 仅限 localhost / 127.0.0.1 |
| 异常处理 | 0 个裸 `except:`，全部替换为具体异常类型 |
| JSON 容错 | LLM 输出 `json.loads()` 全部加 `JSONDecodeError` 处理 |
| 结构化日志 | 可选 JSON formatter（`NEXUSFLOW_LOG_JSON=true`） |

---

## 七、可复现入口

| 操作 | 命令 |
|------|------|
| 启动服务 | `python run.py` 或 `nexusflow serve` |
| 运行测试 | `make test` |
| 带覆盖率测试 | `make test-cov` |
| 代码检查 | `make check` |
| Docker 启动 | `make docker-up` |
| 端到端 Demo | `python examples/demo_e2e_pinchbench.py` |
| 架构 Demo（无需 API Key） | `python examples/demo_e2e_pinchbench.py --arch-only` |
| CDoL 消融实验 | `python examples/demo_phase2_ablation_v3.py` |
| 端边云实验 | `python examples/edge_cloud_scheduling_experiment.py` |
| PinchBench 25 Hard Cases | `python examples/stage7_pinchbench/run_benchmark.py` |
| 环境检查 | `nexusflow doctor` |
| 重新生成本文件 | `python scripts/generate_facts.py` |

---

## 八、实验记录规范

每项实验**必须**记录以下信息：

| 记录项 | 说明 |
|--------|------|
| 代码版本 | Git commit SHA |
| 配置文件 | `.env` 关键参数（脱敏） |
| 模型及版本 | 如 `deepseek-chat v3`、`qwen3.5:9b` |
| 随机种子 | 所有随机操作的 seed |
| 温度 | `temperature` 参数 |
| 最大 Token | `max_tokens` 参数 |
| 最大轮次 | 对话/辩论最大轮数 |
| 工具权限 | 哪些工具可用 |
| 硬件与运行环境 | CPU/GPU/RAM/OS |
| 任务集版本 | 使用的 benchmark 版本 |
| 成本 | API 调用费用 |
| 时延 | 端到端时间 |
| 成功率 | 任务完成比例 |
| 失败类型 | 分类统计失败原因 |

---

## 九、表述规范

性能宣称必须使用以下格式：

> "在任务集 X、模型 Y、预算 Z、运行次数 N 的条件下，NexusFlow 在指标 A 上达到结果 B；相比基线 C，差异为 D。该结论受任务范围、模型版本、评分器和实验环境限制。"

**禁止**：
- "零错误""完全解决"等绝对化表述（无边界条件时）
- 将局部结果外推为全部任务能力
- 选择性隐藏失败案例
- 仅靠增加 Agent 数量宣称协同提升
- 不控制变量就做性能比较

---

*本文件由 `scripts/generate_facts.py` 自动生成。手动修改会在下次生成时被覆盖。*
