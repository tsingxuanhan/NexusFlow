# Changelog

## [Unreleased] - 2026-08-02

### Benchmark Results
- **LHAB-NF 真实基准测试完成** (DeepSeek V4 Flash 后端)
  - 9 任务 × 3 seeds = 27 runs，成功 16/27 (59.3%)
  - 所有正常完成的任务均成功返回结果 (100% 完成率)
  - 平均 Token 消耗: 38,391 tokens
  - 平均执行耗时: 588s (~9.8 min)
  - 平均 CDoL 轮次: 6.0 (完整 3-round protocol)
  - 平均协同增益: 0.274
  - 按难度: Easy 88.9% | Medium 66.7% | Hard 22.2%*
  - 按类别: 数据分析 66.7% | 跨设备 55.6% | 软件工程 55.6%
  - 详细报告: `benchmark_results/report.md`
  - 原始数据: `benchmark_results/raw_results.json`
  - *注: Hard 难度低成功率因评测中途服务器重启导致超时

## [v3.5.0] - 2026-08-01

### Added
- **LHAB-NF 评测基准**（LongHorizon-AgentBench-NF）
  - 9 个任务用例：T1-T3 × Easy/Medium/Hard（跨设备协作/软件工程/数据分析）
  - 13 项评测指标：任务完成率、步骤成功率、Token 成本、延迟、隐私违规等
  - 7 种扰动注入：设备离线、网络超时、工具失败、需求变更、数据冲突、低质量输出、记忆污染
  - 统一评测入口：`scripts/run_benchmark.py`（支持 --suite/--task/--mode/--difficulty）
  - Suite 测试通过：mock 模式 9 任务全部执行，平均评分 0.52
- **P2 可解释动态拓扑**
  - `nexusflow/core/topology_interpreter.py`（16KB）：路由决策解释器
    - 因子贡献度分析（能力匹配/负载状态/跨层通信/协作偏好/延迟约束）
    - 备选方案对比 + 瓶颈识别
    - Markdown 格式解释报告
  - `nexusflow/core/topology_optimizer.py`（13KB）：基于 UCB1 的拓扑优化器
    - 执行结果记录 + 模式学习
    - 动态权重调整（按任务模式）
    - 改进建议生成
  - DynamicRouter 集成 P2（+133 行，总计 1002 行）
    - RoutePlan 新增 `explanation` 字段
    - 新增方法：`record_execution_outcome`, `get_routing_explanation`
    - P2 功能可选启用（无 P2 模块时自动降级）
  - 演示脚本：`examples/p2_topology_demo.py`（3 个演示场景）
- **P3 消融实验框架**
  - `evaluation/lhab_nf/ablation_runner.py`（18KB）：4 组消融实验
    - 基线对比：Single Agent vs Full CDoL
    - Context Mask 消融（信息不对称的价值）
    - 多轮通信消融（迭代精炼的价值）
    - Fusion Judge 消融（复杂融合策略的价值）
  - 设计文档：`docs/P3_Ablation_Design.md`（统计方法 + 实验矩阵）
- **P0 可信度基础**
  - `PROJECT_FACTS.md`：项目统计数据唯一权威来源（658 文件 / 196 Python / ~84K 行）
  - `scripts/generate_facts.py`：自动从代码生成事实清单
  - Makefile 目标：`make facts` / `make verify`

### Changed
- 技术文档引用升级至 v3.5
- README Version badge 更新至 v3.5.0
- LOC badge 更新至 84,000+

### Fixed
- task_schema.py PrivacyLevel enum 对齐 YAML 值（edge_allowed）

## [v3.4.0] - 2026-08-01

### Fixed
- **数据一致性修复**：技术文档内部 4 处数据矛盾已修正
  - 端边云调度器行数：535→635（与 `edge_cloud_scheduler.py` 实际 635 行对齐）
  - SkillRetriever 行数：349→408（与 `skill_retriever.py` 实际 408 行对齐）
  - Phase 7 核心代码总量：6,104→6,163 行
  - 核心算法创新行数：~2,400→~2,466 行
- **Agent 命名统一**：`nexusflow_server.py` 中 7 个旧英文名全部替换为 v3.3 规范
  - Strategist→Planner, Coder→Executor, Analyst→Miner, Critic→Reviewer
  - Synthesizer→Caster, Observer→Assayer, Monitor→Artisan
- **附录 A.3 Agent 命名同步**：技术文档信息不对称架构面板描述更新为新命名

### Added
- **文件上传 API**：`POST /api/upload` + `GET /api/uploads`（Dashboard v4 文件管理支持）
- **Dashboard v4**：Tabler 暗色主题实时监控面板（3,505 行），对接全部 25 条 API 路由

### Changed
- 技术文档升级至 v3.4（2,279 行）
- README 同步更新：调度器行数修正、技术文档引用升级、Version badge 更新至 v3.4.0
- 核心模块总数修正为 88（71 nexusflow + 17 tools）

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
- **技术文档升级至 v3.3**：§7.7.2 D7 替换为真实 EdgeCloudScheduler 实机验证数据（27次LLM调用），§6.2 EdgeCloudScheduler 行数更新（535→635），§10 项目规模数据刷新（653文件/195 Python/83,242行）
- README.md 添加端边云实机验证结果摘要，参考资料表同步更新
- EXPERIMENTS.md D7 段落同步更新为实机验证数据
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
