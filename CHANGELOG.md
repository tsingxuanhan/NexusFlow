# Changelog

## [v3.3.0] - 2026-07-23

### Added
- **端边云实机验证**：使用项目真实 `EdgeCloudScheduler` 完成 27 次真实 LLM 调用验证
  - 三层真实端点：Edge(qwen3.5:9b) / Fog(deepseek-r1:14b) / Cloud(DeepSeek API)
  - 11 次调度决策 + 2 次层间迁移 + 3 次容错 Fallback
  - 混合调度模式节省 88% API 成本，隐私合规率 25%（纯云端 0%）
  - 验证脚本：`examples/edge_cloud_scheduling/edge_cloud_real_verification.py`
  - 验证报告：`examples/edge_cloud_scheduling/real_machine_report.md`
  - 原始数据：`examples/edge_cloud_scheduling/real_machine_data.json`

### Changed
- README.md 添加端边云实机验证结果摘要
- 版本号更新至 v3.3.0


NexusFlow 版本变更日志。格式基于 [Keep a Changelog](https://keepachangelog.com/zh-CN/)，版本号遵循 [Semantic Versioning](https://semver.org/lang/zh-CN/)。

## [Unreleased]

## [3.2.0] — 2026-07-23

### 新增
- **Docker 一键部署**：多阶段构建 Dockerfile（python:3.11-slim，非 root 用户，healthcheck）+ docker-compose.yml（NexusFlow + 可选 Ollama profile）+ .dockerignore
- **Makefile**：12+ targets（install/install-dev/test/test-cov/lint/format/serve/demo/doctor/docker-build/docker-up/docker-down/clean）
- **CLI 入口**：`nexusflow` 命令行工具（serve/run/demo/doctor/version）+ `python -m nexusflow` 支持，通过 pyproject.toml `[project.scripts]` 注册
- **API 文档自动生成**：`.github/workflows/docs.yml`（pdoc 生成 + GitHub Pages 部署）
- **CI/CD 完善**：`lint.yml`（ruff lint + format check）、`docker.yml`（构建 + smoke test）、`tests.yml` 升级（Python 3.10-3.12 矩阵 + coverage）
- **开发工具链**：`.pre-commit-config.yaml`（ruff + pre-commit-hooks）、pyproject.toml dev 依赖组（pytest/pytest-cov/pytest-timeout/ruff/pre-commit）

### 重构
- **base_agent.py Mixin 拆分**：2,597 行 → 1,211 行（-53%），拆为 7 个模块：
  - `models.py`（254 行）— 数据类
  - `reasoning_mixin.py`（323 行）— 推理能力
  - `codeact_mixin.py`（130 行）— CodeAct 集成
  - `memory_mixin.py`（112 行）— 记忆访问
  - `checkpoint_mixin.py`（124 行）— 检查点管理
  - `handoff_mixin.py`（188 行）— Agent 交接
  - `agi_mixin.py`（401 行）— AGI 能力扩展
  - 完全向后兼容：所有 `from nexusflow.agents.base_agent import XXX` 继续工作

### 测试
- **56 个新测试**（301 → 357 全通过，覆盖率 35% → 38%）：
  - `tests/test_cli.py`（16 个）— CLI 子命令、参数解析、环境检查
  - `tests/test_integration.py`（22 个）— 端到端集成（mock LLM）
  - `tests/test_mixins.py`（18 个）— Mixin 模块 + 向后兼容验证

### 工程
- README Quick Start 重写：Docker 优先路径，折叠式开发模式
- 端口统一为 8900（Dockerfile/docker-compose/CLI serve 一致）
- .gitignore 增加 `docs/api/`（自动生成的 API 文档不入库）

## [3.1.0] — 2026-07-22

### 新增
- **Stage-7 PinchBench Hard Cases**：25 个高难度任务 SA vs NF 全量对比（覆盖编码调试、数据分析、会议摘要等 8 类）
- **NF v2 两阶段管线**：Phase 1 CDoL 多 Agent 深度分析 → Phase 2 Producer Agent 合成完整交付物
- **端到端 Demo 脚本**：`examples/demo_e2e_pinchbench.py`，一键展示架构→组件→对比→HTML 报告
- 技术文档升级至 v3.1，全文 7 处过时引用修复（四阶段→七阶段）

### 核心数据
| 指标 | SA 基线 | NF v2 | 提升 |
|------|---------|-------|------|
| automated_avg | 0.456 | **0.487** | +6.7% |
| 最大单项提升 | — | iterative_code_refine | +200% |

### 修复
- P0 可复现性问题全量修复（API Key 清除、路径修正）
- 技术文档执行摘要过时引用（四阶段→七阶段）

---

## [3.0.0] — 2026-07-21

### 新增
- **Stage-6 WorkBuddy 宏观经济对比实验**：DBnomics IMF WEO 真实数据，20 国×15 指标×41 年
- **Stage-6b L3 认知任务 Benchmark**：9 类高复杂度认知能力对比（模式挖掘、因果推断、反事实推理等）
- **真实 LLM 端边云协同 Benchmark**：DeepSeek API（云端）+ Ollama 本地模型（端/边），零模拟全流程实机验证
  - 数据准备：DBnomics IMF WEO 20国×15指标×41年
  - 端侧数据 + 云端数据 + 元信息 + 实验报告 + 结果 JSON
  - API Key 全部改为环境变量，确保可复现
- 技术文档从 v2.9 升级至 v3.0（2071 行）

### 核心数据
- WorkBuddy 加权总分：**8.28 vs 6.71**（+23.4%）
- GDP 命中率：83% vs 63%（+20pp）
- L3 Benchmark：NF 辩论质量 +1.10，高风险决策 T8/T9 显著领先

### 修复
- 单 Agent 实验设计缺陷修正
- 文档统计数字与仓库实际状态对齐

---

## [2.9.1] — 2026-07-17 ~ 07-20

### 新增
- **Nemotron-3 Embed 集成**（P0-P3 全链路）：
  - EmbeddingProvider 接口增强 + BM25 混合检索激活
  - NemotronEmbeddingProvider + NemotronVectorStore + ArchivalMemory 三路 RRF
  - EdgeCloudScheduler EmbeddingModelRouter（GPU 感知）
  - NIM API 模式（云端推理，零外部依赖）
- **30 页精华版文档**（v2.9.1）
- **NIM/OpenRouter API 模式**：NemotronEmbeddingProvider 支持 NIM 云端推理（零外部依赖）和 OpenRouter 聚合路由两种部署模式
- **端边云调度实证实验** + Dashboard 截图
- **Nemotron Benchmark 实验报告（E1-E4）**：
  - E1：全仓库混合检索精度对比（TF-IDF vs BM25 vs Nemotron vs 三路 RRF）
  - E2：论文库语义检索召回率
  - E3：端边云三模式延迟/吞吐对比
  - E4：GPU 感知路由准确率（EmbeddingModelRouter）

### 工程性重构（2026-07-17）
- P0：删除 CrewAI 死代码、清理历史版本（9.6MB）、添加 pyproject.toml
- P1：根目录 41 个 .py 归入 6 个子包 `nexusflow/{core,agents,memory,cognition,protocol}` + `server`
- P2：config.py 转 YAML + 151 个单元测试 + 修复 start.bat 旧路径
- P3：根目录瘦身 + 评审报告 P0/P1 全部完成

### 修复
- P0 代码层硬伤（API Key 硬编码清除）
- 叙事层 P0 修复（Shannon 类比缩减、绝对化表述弱化）
- 精华版 7 处数据 + 1 处事实描述修正

---

## [2.9.0] — 2026-07-16

### 新增
- **CDoL 动态终止机制**：FusionJudge 自适应停止 + 双层自适应架构
- **Phase 2 Ablation 实验**：2/3/4 轮 CDoL 对比，验证 2-3 轮最优平台期
- **LLM 质量评分器**：5 次运行 + 固定 seed=42 + few-shot 锚定
- 横向对比实验扩展：AutoGen 真实执行 + CrewAI/LangGraph 四框架对比
- 复杂任务横向对比：全球能源转型评估 94.4 分

### 技术文档 v2.8 更新
- 五阶段 Benchmark 完整原始数据
- v3 优化 prompt 横向对比

---

## [2.8.0] — 2026-07-13 ~ 07-14

### 新增
- **深度审计报告**：62 个文件 S1-S5/M1-M6/L1-L8 全量审计
- **4 核心模块单元测试**：151 个测试用例（全量 301 测试通过）
- **M8 横向对比实验**：NexusFlow vs AutoGen 真实执行
- GitHub Actions CI 测试流水线
- 技术文档 v2.8

### 修复
- 审计报告 S1-S5/M1-M6 全量修复
- 代码-文档一致性全面修复（拓扑枚举/文件统计/测试分布/版本号）

---

## [2.7.0] — 2026-07-08

### 新增
- **README 大幅重写**：Badge 系统 + 核心定位 + 七阶段实验体系
- **Dashboard v4**：ASCII 仪表盘 + WebSocket 实时监控
- **NOAA 气候诊断 Showcases**：单 Agent vs CDoL 质量闭环对比
- Stage-1 至 Stage-4 Benchmark 案例
- 技术文档 v2.5 → v2.7

### 重构
- 清理 `xuanshu-agents` 旧命名残留，统一为 NexusFlow

---

## [2.5.0] — 2026-07-02

### 新增
- **Dashboard**：FastAPI + WebSocket 实时监控面板
- **端边云三层架构**：云端 DeepSeek API + 边端 Ollama 大模型 + 终端 Ollama 小模型

### 修复
- 移除硬编码 API Key，改为环境变量

---

## [1.0.0] — 2026-07-01

### 首发
- **三层信息架构**（AgentInformationPolicy）：全局视野层 / CDoL 参与层 / 旁观记录层
- **10 Agent 体系**：Coordinator / Archivist / Planner / Researcher / Reviewer / Caster / Executor / Miner / Assayer / Artisan
- **统一编排器**（NexusOrchestrator）：自动路由分类（simple / research / coding / cdol）
- **CDoL 认知分工引擎**（2,058 行）：6 种视角分解 + 3 轮有损通信 + FusionJudge 虚假一致检测
- **自适应上下文管理器**（1,642 行）
- **动态拓扑路由器**（869 行）：5 种拓扑模式

[Unreleased]: https://github.com/tsingxuanhan/NexusFlow/compare/v3.2.0...HEAD
[3.2.0]: https://github.com/tsingxuanhan/NexusFlow/compare/v3.1.0...v3.2.0
[3.1.0]: https://github.com/tsingxuanhan/NexusFlow/releases/tag/v3.1.0
[3.0.0]: https://github.com/tsingxuanhan/NexusFlow/releases/tag/v3.0.0
[2.9.1]: https://github.com/tsingxuanhan/NexusFlow/releases/tag/v2.9.1
[2.9.0]: https://github.com/tsingxuanhan/NexusFlow/releases/tag/v2.9.0
[2.8.0]: https://github.com/tsingxuanhan/NexusFlow/releases/tag/v2.8.0
[2.7.0]: https://github.com/tsingxuanhan/NexusFlow/releases/tag/v2.7.0
[2.5.0]: https://github.com/tsingxuanhan/NexusFlow/releases/tag/v2.5.0
[1.0.0]: https://github.com/tsingxuanhan/NexusFlow/releases/tag/v1.0.0
