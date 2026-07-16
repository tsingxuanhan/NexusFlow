# 变更日志

## [v5.3] — 2026-06-20
### 新增 (Phase 7: Deep Collaborative Reasoning)
- `cognitive_division_engine.py` — 认知分工引擎 (1498行)，6种视角分解策略 + 3轮通信协议 + 假共识检测
- `adaptive_context_manager.py` — 自适应上下文管理器 (1518行)，惰性检测 + 动态窗口 + 全局记忆池

### 架构变更
- 代码规模: 27,000+ → 35,000+ 行
- 新增 2 核心模块共 3016 行，修改 8 个文件共 278 行
- 所有新功能向后兼容，支持延迟降级

### 灵感来源
- Tsinghua & OpenBMB 混合注意力研究 (2026) — "大窗口懒惰症" 对策
- Herbert Simon 有限理性理论 — 约束作为认知资源

---

## [v5.2] — 2026-06-13
### 新增 (Phase 6: Dynamic Swarm Intelligence)
- `dynamic_router.py` — 动态拓扑路由器 (870行)，NetworkX 图 + 能力匹配 + 负载均衡
- `edge_cloud_scheduler.py` — 边-雾-云调度器 (535行)，隐私优先 + 5种调度策略
- `dashboard.py` — NexusFlow 实时监控面板 (370行)

### 增强
- `a2a_protocol.py` — 新增 6 种 CDoL 消息类型
- `task_tree.py` — 支持 CDoL 节点标记

---

## [v5.1] — 2026-06-10
### 新增 (Phase 5: AGI Core)
- `autonomous.py` — 自主目标处理器 (780行)，6阶段目标闭环
- `meta_cognition.py` — 元认知系统 (680行)，自我评估 + 策略调整
- `cross_domain.py` — 跨域迁移 (590行)，8个种子类比
- `agentos.py` — AgentOS 服务 (640行)，FastAPI + stdio

### 架构变更
- 从 Agent 框架扩展为 AGI 核心引擎
- 新增 4 个核心模块共 2690 行

---

## [v4.3] — 2026-06-13
### 新增
- `thought_crystallization.py` — 思想结晶引擎，每次推理后提炼思想钻石(ThoughtDiamond)
- `abstraction_hierarchy.py` — 抽象层级系统，L1事实→L2推理→L3策略→L4元规则
- `confidence_filter.py` — 置信度门控，4维加权评分 + ACCEPT/REJECT/MERGE/NEEDS_REVIEW
- `v4_3_integration.py` — 统一初始化入口 + crystallize_and_filter() 一站式流程

### 灵感来源
- Thought-Retriever (TMLR 2026, UIUC/MIT/CMU) — "存思想不存数据"

---

## [v4.2] — 2026-06-12
### 新增
- `knowledge_library.py` — 领域知识库，5种知识类型 + 6级领域范围
- `hypothesis_engine.py` — 假说引擎，H=(C,A,E,O)四元组 + 7种生命周期状态
- `discovery_exploitation.py` — 发现-剥削交替探索
- `self_healing.py` — 自修复循环，5次重试 + 指数退避
- `succinct_comm.py` — Agent间通信极简化
- `structured_pattern_memory.py` — 结构化模式记忆，5类模式 + 跨域迁移
- `v4_2_integration.py` — 统一初始化入口

### 灵感来源
- Agora (ICML 2026, 0G Lab + 新国立 + 北大) — 去中心化多Agent协作

---

## [v4.1] — 2026-06-12
### 新增
- `checkpoint_writer.py` — 推理过程检查点，崩溃可恢复
- `goal_verifier.py` — 目标验证器，产出偏离目标时自动打回

### 增强
- `reflection.py` — Dream/Distill增强
- `continuous_learning.py` — 持续学习优化

### 灵感来源
- MiMo Code — checkpoint-writer / goal-verifier / Dream增强

---

## [v4.0] — 2025-06 ~ 2026-05
### 架构变更
- 从纯Agent框架扩展为完整AI工作站
- 13文件 → 68文件（+423%）
- 3,511行 → 25,773行（+631%）

### 新增模块
- **记忆系统**: Letta 3层架构 (core_memory / recall_memory / archival_memory)
- **工具生态**: 20+工具 (code_exec, file_ops, web_search, browser, git_ops...)
- **控制面板**: 液态玻璃UI (index / models / monitor / commands)
- **AgentOS**: 本地服务编排
- **元认知**: meta_cognition + autonomous + cross_domain + continuous_learning
- **质量安全**: guardrails + quality + circuit_breaker + dead_letter_queue

---

## [v3.3] — 2025-06
### 变更
- API密钥管理安全化：硬编码 → 环境变量
- 新增 `mcp_client.py` — MCP协议客户端
- 安全护栏增强

---

## [v3.2] — 2025-05
### 架构变更
- 四角色Agent架构成型：矿工/试金/铸师/匠人
- 新增 A2A协议 + Handoff机制
- 编排调度器 (orchestrator.py)

---

## [v3.1.1] — 2025-05
### 变更
- 引入 NGram+TF-IDF 向量记忆
- hybrid_retrieve: 向量相似度 + 关键词匹配，RRF融合排序
- SlotMemory 槽位机制 + 冲突检测
