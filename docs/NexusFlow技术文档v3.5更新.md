# NexusFlow 技术文档 v3.5 更新

> 本文档记录 v3.5.0 版本（2026-08-01）的新增内容。完整技术文档请参见 v3.4。

---

## 第 15 章：LHAB-NF 评测基准（P1）

### 15.1 设计目标

LongHorizon-AgentBench-NF（LHAB-NF）是专为 NexusFlow 设计的长程任务评测框架，旨在：

1. **量化长程任务能力**：超越单步问答，评测多步协作、动态调整、异常恢复
2. **对比基准缺失**：现有基准（SWE-bench/WebArena）缺乏对端边云架构的评测
3. **扰动鲁棒性**：测试系统在设备离线、网络超时、工具失败等异常下的恢复能力
4. **隐私合规性**：验证敏感数据在端侧处理的合规性

### 15.2 任务设计

#### 任务矩阵

| 类别 | Easy | Medium | Hard |
|------|------|--------|------|
| T1 跨设备协作 | 邮件摘要 | 日程协调 + 扰动 | 多任务 + 隐私 |
| T2 软件工程 | 单文件功能 | 多模块Bug修复 | 跨模块重构 |
| T3 数据分析 | 单源统计 | 多源对比 | 异构深度研究 |

#### 任务示例：T1-M-001 日程协调

```yaml
task_id: T1-M-001
category: cross_device_collaboration
difficulty: medium
description: "协调3人会议时间，处理设备离线"

steps:
  - id: s1_query_calendars
    description: "查询3个端侧日历"
    agent_role: coordinator
    device_preference: edge
    privacy_level: edge_allowed
  
  - id: s2_find_overlap
    description: "计算时间交集"
    agent_role: executor
    device_preference: edge
    input_deps: [s1_query_calendars]
  
  - id: s3_send_invites
    description: "发送会议邀请"
    agent_role: caster
    device_preference: cloud
    input_deps: [s2_find_overlap]

perturbations:
  - type: device_offline
    trigger_at_step: s2_find_overlap
    target: edge_device_1
    params:
      duration_seconds: 30
    expected_recovery: migrate_to_cloud
```

### 15.3 评测指标

#### 核心指标（13 项）

| 指标 | 说明 | 计算方式 |
|------|------|----------|
| 任务完成率 (TCR) | 成功完成的任务比例 | completed / total |
| 步骤成功率 (SSR) | 所有步骤的成功率 | successful_steps / total_steps |
| 长程依赖恢复率 (LDRR) | 依赖链中断后的恢复率 | recovered / broken |
| 目标保持率 (GHR) | 长程任务中目标不偏离的比例 | on_track_steps / total_steps |
| 需求变更恢复率 (RCRR) | 中途需求变更后的恢复率 | adapted / changed |
| 节点失效恢复率 (NFRR) | 节点故障后的恢复率 | recovered / failed |
| 平均恢复时间 (ART) | 从故障到恢复的平均时间 | mean(recovery_time) |
| 人工干预次数 (HIC) | 需要人工介入的次数 | count(interventions) |
| 总 Token 成本 | 任务总 Token 消耗 | sum(tokens) |
| 每成功任务成本 | 平均每个成功任务的成本 | total_cost / successful_tasks |
| 端到端时延 | 从任务开始到完成的总时间 | total_elapsed |
| 输出质量 | 最终输出的质量评分 | 0-1 分 |
| 隐私违规次数 | 违反隐私约束的次数 | count(violations) |

#### 综合评分

```python
score = (
    0.25 * task_completion_rate +      # 任务完成
    0.20 * step_success_rate +          # 步骤成功
    0.15 * recovery_rate +              # 恢复能力
    0.15 * output_quality +             # 输出质量
    0.10 * (1 - normalized_cost) +      # 成本效率
    0.10 * (1 - normalized_latency) +   # 时间效率
    0.05 * (1 - privacy_violation_rate) # 隐私合规
)
```

### 15.4 扰动注入

#### 7 种扰动类型

| 类型 | 说明 | 预期恢复策略 |
|------|------|--------------|
| device_offline | 设备离线 | 迁移到备用设备 |
| network_timeout | 网络超时 | 重试 + 降级 |
| tool_failure | 工具失败 | 换用备用工具 |
| requirement_change | 需求变更 | 部分重规划 |
| data_conflict | 数据冲突 | 交叉验证 |
| low_quality_output | 低质量输出 | Reviewer 拒绝 + 重试 |
| memory_injection | 记忆污染 | 记忆验证器拒绝 |

### 15.5 评测框架架构

```
evaluation/lhab_nf/
├── task_schema.py       # Task/Step/Perturbation dataclass
├── scorer.py            # 指标计算 + 综合评分
├── runner.py            # 任务执行 + 依赖解析
├── agent_adapter.py     # mock/real 双模式适配器
├── ablation_runner.py   # 消融实验框架
└── tasks/               # 9 个任务 YAML
    ├── T1-E-001.yaml
    ├── T1-M-001.yaml
    ├── T1-H-001.yaml
    ├── T2-E-001.yaml
    ├── ...
    └── T3-H-001.yaml
```

---

## 第 16 章：可解释动态拓扑（P2）

### 16.1 设计动机

传统动态路由器是"黑盒"：给定任务，输出拓扑，但无法解释为什么选择这个拓扑。这导致：

1. **调试困难**：路由决策不可追溯
2. **无法优化**：固定权重无法从历史数据学习
3. **信任缺失**：用户不理解系统为什么这样决策

P2 将 DynamicRouter 升级为**可解释、可优化、可学习**的系统。

### 16.2 TopologyInterpreter（拓扑解释器）

#### 因子贡献度分析

每个路由决策由 5 个因子决定：

| 因子 | 权重 | 说明 |
|------|------|------|
| 能力匹配度 | 0.35 | Agent 能力与任务需求的匹配程度 |
| 负载状态 | 0.25 | Agent 的可用性和健康度 |
| 跨层通信 | 0.15 | 端边云跨层通信的延迟惩罚 |
| 协作偏好 | 0.15 | Agent 间的协作偏好加成 |
| 延迟约束 | 0.10 | 是否在延迟预算内 |

#### 解释生成

```python
@dataclass
class RoutingExplanation:
    plan_id: str
    decision_summary: str                    # 一句话总结
    factor_breakdown: List[FactorContribution]  # 因子分析
    alternatives: List[AlternativeOption]    # 备选方案
    confidence_factors: List[str]            # 影响置信度的因素
    bottlenecks: List[str]                   # 识别的瓶颈
    human_readable: str                      # 完整自然语言解释
```

#### 解释示例

```
路由决策解释: plan_abc123

## 决策摘要
为任务选择混合拓扑，由 4 个 Agent 协作执行：
coordinator → researcher → executor → reviewer。
预估延迟 12.3s，置信度 78%。

## 因子分析
- ✅ 能力匹配度 (贡献: +0.85, 权重: 0.35)
  - 候选 Agent 与任务需求的平均能力匹配度为 0.85
- ✅ 负载状态 (贡献: +0.72, 权重: 0.25)
  - 选中 Agent 的平均可用性评分为 0.86
- ❌ 跨层通信 (贡献: -0.30, 权重: 0.15)
  - 涉及 2 个部署层（edge, cloud），增加跨层通信延迟
- ✅ 延迟约束 (贡献: +0.20, 权重: 0.10)
  - 预估延迟在预算内，余量 59%

## 识别的瓶颈
- ⚠️ Agent researcher → executor 协作成本较高（权重 2.3），可能成为性能瓶颈
```

### 16.3 TopologyOptimizer（拓扑优化器）

#### UCB1 多臂老虎机算法

优化器使用 UCB1 算法平衡探索与利用：

```python
def ucb_score(pattern: RoutePattern) -> float:
    if pattern.total_count == 0:
        return float('inf')  # 优先探索未尝试的
    
    # 利用：成功率 + 低延迟
    reward = pattern.success_rate * 0.7 + (1.0 / (1.0 + pattern.avg_latency_ms / 10000.0)) * 0.3
    
    # 探索：不确定性（越少尝试越倾向探索）
    exploration = math.sqrt(2.0 * math.log(total_trials) / pattern.total_count)
    
    return reward + exploration_factor * exploration
```

#### 学习机制

```python
class TopologyOptimizer:
    def record_request(self, task, plan):
        """记录路由请求（执行前）"""
        
    def record_execution(self, plan_id, outcome):
        """记录执行结果（执行后）"""
        
    def get_optimal_pattern(self, task_pattern) -> RoutePattern:
        """获取给定任务模式的最优路由模式"""
        
    def learn_weights(self, task_pattern):
        """基于历史数据学习最优权重"""
```

#### 动态权重调整

优化器按任务模式（capability × complexity）学习权重：

```python
# 默认权重
default_weights = {
    "capability_match": 0.35,
    "load_state": 0.25,
    "cross_tier": 0.15,
    "preference": 0.15,
    "latency": 0.10,
}

# 学习到的权重（针对特定任务模式）
learned_weights["data_analysis:complex"] = {
    "capability_match": 0.25,
    "load_state": 0.20,
    "cross_tier": 0.10,
    "preference": 0.15,
    "latency": 0.30,  # 数据任务更关注延迟
}
```

### 16.4 DynamicRouter 集成

#### 修改点

1. **__init__**：初始化 TopologyInterpreter 和 TopologyOptimizer
2. **route()**：生成解释 + 记录请求
3. **新方法**：
   - `_get_edge_weights()`：获取当前拓扑的边权重
   - `record_execution_outcome()`：记录执行结果
   - `get_routing_explanation()`：获取路由解释
   - `get_optimization_stats()`：获取优化器统计

#### RoutePlan 扩展

```python
@dataclass
class RoutePlan:
    # ... 原有字段 ...
    
    # P2: 可解释性
    explanation: Optional[Any] = None  # RoutingExplanation object
```

### 16.5 演示脚本

```bash
# 运行 P2 演示
python examples/p2_topology_demo.py
```

演示内容：
1. 路由决策解释（因子分析 + 瓶颈识别）
2. 优化器学习（从执行结果改进）
3. 不同任务的拓扑对比

---

## 第 17 章：消融实验（P3）

### 17.1 实验目标

证明 CDoL（认知分工）的独立价值，量化每个组件的贡献。

**核心假设**：CDoL 的增益来自"信息受限条件下的认知过程"，而非"多模型 ensemble 的统计降噪"。

### 17.2 实验矩阵

#### 实验 1: Single Agent vs Full CDoL（基线对比）

| 配置 | Agent 数 | 信息可见性 | 通信轮次 | 融合方式 |
|------|----------|------------|----------|----------|
| Single Agent | 1 | 全量证据 | 0 | N/A |
| Full CDoL | 3 | 不对称掩码 | 2 | FusionJudge |

**预期**：CDoL 在推理深度上显著优于 Single Agent（p < 0.01）

#### 实验 2: Context Mask 消融

| 配置 | 掩码策略 | 说明 |
|------|----------|------|
| Full CDoL | 不对称掩码 | 每个 Agent 看到不同证据子集 |
| No Mask | 全量可见 | 所有 Agent 看到相同完整信息 |
| Random Mask | 随机掩码 | 掩码与任务无关（控制组） |

**预期**：Full CDoL > No Mask > Random Mask（信息不对称设计是关键）

#### 实验 3: 多轮通信消融

| 配置 | 通信轮次 | 说明 |
|------|----------|------|
| 0 轮（Single Shot） | 0 | 各 Agent 独立输出，直接融合 |
| 1 轮 | 1 | Round 0: 初始结论 → Round 1: 交叉质疑 |
| 2 轮（Full） | 2 | Round 0 + Round 1 + Round 2: 最终修正 |

**预期**：2 轮 > 1 轮 > 0 轮，但边际收益递减

#### 实验 4: Fusion Judge 消融

| 配置 | 融合方式 | 说明 |
|------|----------|------|
| FusionJudge | 4 类矛盾分类 | 可归因/不可归因/虚假一致/真实收敛 |
| Majority Vote | 多数投票 | 简单投票选多数结论 |
| Average | 平均融合 | 数值型结论取平均 |

**预期**：FusionJudge > Majority Vote > Average（结构化融合更优）

### 17.3 统计方法

- **样本量**：每配置 × 每任务 × 3 次 = 4 配置 × 3 任务 × 3 次 = 36 次/实验
- **显著性检验**：Welch's t-test（不等方差）或 Mann-Whitney U（非正态）
- **效应量**：Cohen's d
- **置信区间**：95% CI

### 17.4 消融实验框架

```python
class AblationRunner:
    def run_experiment(self, config, task_id, run_index, ground_truth):
        """执行单次消融实验"""
        
    def run_all_experiments(self, task_ids, num_runs=3):
        """运行所有消融实验"""
        
    def _generate_summaries(self, task_ids, configs):
        """生成汇总统计（均值 ± 标准差 + p-value + Cohen's d）"""
```

---

## 附录 E：P1/P2/P3 文件清单

### P1 评测基准

| 文件 | 大小 | 功能 |
|------|------|------|
| evaluation/lhab_nf/task_schema.py | 9KB | Task/Step/Perturbation dataclass |
| evaluation/lhab_nf/scorer.py | 8.4KB | 13项指标 + 综合评分 |
| evaluation/lhab_nf/runner.py | 18.5KB | 任务执行 + 依赖解析 |
| evaluation/lhab_nf/agent_adapter.py | 7KB | mock/real 双模式适配器 |
| evaluation/lhab_nf/ablation_runner.py | 18KB | 消融实验框架 |
| evaluation/lhab_nf/tasks/*.yaml | 9个 | T1-T3 × 3难度 |
| scripts/run_benchmark.py | 12.3KB | 统一评测入口 |
| docs/LHAB-NF_Design.md | 8.7KB | 设计规格书 |
| docs/P3_Ablation_Design.md | 3.3KB | 消融实验设计 |

### P2 可解释动态拓扑

| 文件 | 大小 | 功能 |
|------|------|------|
| nexusflow/core/topology_interpreter.py | 16KB | 路由决策解释器 |
| nexusflow/core/topology_optimizer.py | 13KB | UCB1 学习优化器 |
| nexusflow/core/dynamic_router.py | 1002行 | 集成P2（+133行） |
| docs/P2_Topology_Design.md | 3.6KB | 设计规格书 |
| examples/p2_topology_demo.py | 9KB | 演示脚本 |

---

## 总结

v3.5.0 是 NexusFlow 的**评测与可解释性里程碑**：

1. **P1 LHAB-NF**：建立了完整的长程任务评测体系，9 任务 × 13 指标 × 7 扰动
2. **P2 可解释拓扑**：让路由决策透明可追溯，UCB1 学习最优模式
3. **P3 消融实验**：量化 CDoL 各组件贡献，证明信息不对称的核心价值

这三项工作共同构成了 NexusFlow 的**可信 AI 基础设施**：可评测、可解释、可优化。
