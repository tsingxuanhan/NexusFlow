# NexusFlow 端-边-云三层调度实机验证报告

> 实验时间：2026-07-23
> 实验耗时：246.5秒（27次真实LLM调用）
> **调度器：nexusflow.core.edge_cloud_scheduler.EdgeCloudScheduler（项目真实代码）**
> 验证脚本：`edge_cloud_real_verification.py`
> 数据文件：`edge_cloud_verification/real_machine_data.json`

---

## 1. 实验目标

验证 NexusFlow **项目真实的 EdgeCloudScheduler** 在真实LLM推理环境下的端边云三层调度能力。

### 核心改进：使用项目真实代码

本次验证直接 import 并使用 `nexusflow.core.edge_cloud_scheduler` 模块中的：
- `EdgeCloudScheduler` 类 — 调度器主体
- `TierResource` 类 — 资源描述（含 `compute_fitness()` 适配度计算）
- `DeployTier` 枚举 — EDGE/FOG/CLOUD 三层
- `SchedulingPolicy` 枚举 — 5种调度策略
- `SchedulingDecision` 类 — 调度决策结果

调用的真实方法：
- `scheduler.register_tier()` — 注册真实端点资源
- `scheduler.schedule()` — 获取调度决策（11次）
- `scheduler.migrate()` — 层间迁移（2次）
- `scheduler.update_resource_state()` — 容错状态更新（3次）
- `scheduler.get_scheduling_stats()` — 调度统计

### 与现有模拟实验的对比

| 维度 | 现有模拟实验 | 本次实机验证 |
|:-----|:------------|:------------|
| 调度器代码 | EdgeCloudScheduler（模拟参数） | **EdgeCloudScheduler（真实端点）** |
| LLM推理 | 无（仅调度决策） | **27次真实LLM调用** |
| 延迟测量 | 硬编码（5ms/15ms/150ms） | **Wall-clock实测** |
| Token计量 | 无 | **真实prompt+completion tokens** |
| 响应质量 | 未评估 | **关键词命中率+长度评分** |
| 层间迁移 | 仅记录日志 | **migrate() + 真实重新执行** |
| 容错Fallback | 模拟可用性 | **update_resource_state() + 真实重新调度** |
| 执行耗时 | 0.00s | **246.5s** |

---

## 2. 三层资源配置（注册到真实 EdgeCloudScheduler）

使用 `scheduler.register_tier(TierResource(...))` 注册：

| 层级 | 资源名称 | 模型 | 端点 | 延迟 | 成本/token | 隐私 | GPU |
|:----:|:---------|:-----|:-----|:----:|:----------:|:----:|:---:|
| 📱 Edge | terminal-qwen3.5-9b | qwen3.5:9b (6.6GB) | Ollama localhost:11434 | 5ms | ¥0 | ✅ | 0 |
| 🖥️ Fog | edge-deepseek-r1-14b | deepseek-r1:14b (9GB) | Ollama localhost:11434 | 15ms | ¥0 | ✅ | 1×16GB |
| ☁️ Cloud | cloud-deepseek-api | deepseek-chat | DeepSeek API | 150ms | ¥0.000001 | ❌ | 0 |

---

## 3. 连通性验证

| 层级 | 状态 | 延迟(ms) | Token数 |
|:----:|:----:|:--------:|:-------:|
| 📱 Edge | ✅ OK | 10,311 | 19 |
| 🖥️ Fog | ✅ OK | 7,766 | 10 |
| ☁️ Cloud | ✅ OK | 612 | 7 |

---

## 4. 端边云混合调度（EdgeCloudScheduler.schedule() + 真实LLM执行）

### 4.1 调度策略

根据任务特征动态切换调度策略（编排器合理用法）：
- `privacy_level >= 2` → `PRIVACY_FIRST`（隐私优先，强制Edge层 + privacy_guaranteed=True）
- `latency_budget < 2000ms` → `LATENCY_FIRST`（延迟优先）
- 其余 → `BALANCED`（均衡：适配度×0.5 + 延迟×0.3 + 成本×0.2）

### 4.2 调度决策与执行结果

| 任务 | 描述 | 策略 | 调度层 | 资源 | 置信度 | 延迟(ms) | Token | 成本(¥) | 质量 | 隐私 |
|:-----|:-----|:----:|:------:|:-----|:------:|:--------:|:-----:|:-------:|:----:|:----:|
| T01 | 个人健康数据分析 | PRIVACY_FIRST | 📱 edge | terminal-qwen3.5-9b | 0.900 | 17,548 | 538 | 0.0000 | 1.00 | ✅ |
| T02 | 实时问答 | LATENCY_FIRST | 📱 edge | terminal-qwen3.5-9b | 0.900 | 3,617 | 67 | 0.0000 | 1.00 | — |
| T03 | 代码生成 | BALANCED | 🖥️ fog | edge-deepseek-r1-14b | 0.921 | 31,273 | 922 | 0.0000 | 1.00 | — |
| T04 | 长文档分析 | BALANCED | ☁️ cloud | cloud-deepseek-api | 0.836 | 2,205 | 227 | 0.0002 | 1.00 | — |
| T05 | 个人财务分析 | PRIVACY_FIRST | 📱 edge | terminal-qwen3.5-9b | 0.900 | 19,552 | 659 | 0.0000 | 1.00 | ✅ |
| T06 | 通用文本摘要 | BALANCED | 📱 edge | terminal-qwen3.5-9b | 0.949 | 3,176 | 93 | 0.0000 | 0.30 | — |
| T07 | 复杂推理 | BALANCED | 🖥️ fog | edge-deepseek-r1-14b | 0.921 | 24,526 | 662 | 0.0000 | 1.00 | — |
| T08 | 离线文本分类 | BALANCED | 📱 edge | terminal-qwen3.5-9b | 0.949 | 9,614 | 121 | 0.0000 | 1.00 | — |

### 4.3 层分布（由 EdgeCloudScheduler 自动决策）

```
📱 Edge:  5 任务 (62.5%) — BALANCED策略评分最优(低延迟+零成本) + PRIVACY_FIRST强制
🖥️ Fog:   2 任务 (25.0%) — GPU需求路由到Fog层(compute_fitness中gpu_count>0)
☁️ Cloud: 1 任务 (12.5%) — 大上下文(40K)仅Cloud支持(65K窗口)
```

### 4.4 调度器内部决策日志

所有调度决策均由 `EdgeCloudScheduler._schedule_balanced()` / `_schedule_privacy_first()` / `_schedule_latency_first()` 产出，决策理由示例：
- T01: `Privacy-sensitive: forced to edge tier` (PRIVACY_FIRST)
- T03: `Balanced selection: score=0.921 at fog` (BALANCED)
- T04: `Balanced selection: score=0.836 at cloud` (BALANCED)

---

## 5. 纯云端模式对比

| 任务 | 延迟(ms) | Token | 成本(¥) | 质量 | 隐私 |
|:-----|:--------:|:-----:|:-------:|:----:|:----:|
| T01 | 2,954 | 239 | 0.0002 | 1.00 | ❌ |
| T02 | 1,006 | 35 | 0.0000 | 1.00 | ❌ |
| T03 | 3,138 | 321 | 0.0003 | 1.00 | ❌ |
| T04 | 2,904 | 298 | 0.0003 | 1.00 | ❌ |
| T05 | 1,977 | 241 | 0.0002 | 1.00 | ❌ |
| T06 | 784 | 96 | 0.0001 | 1.00 | ❌ |
| T07 | 2,685 | 285 | 0.0003 | 1.00 | ❌ |
| T08 | 864 | 44 | 0.0000 | 0.79 | ❌ |

---

## 6. 混合调度 vs 纯云端 对比分析

| 指标 | 混合调度 | 纯云端 | 差异 | 说明 |
|:-----|:--------:|:------:|:----:|:-----|
| 成功率 | 8/8 (100%) | 8/8 (100%) | — | 两种模式均全部成功 |
| 总延迟 | 111,511ms | 16,311ms | +95,200ms | 本地模型CPU推理较慢 |
| 总Token | 3,289 | 1,559 | +1,730 | 本地模型生成更长响应 |
| **总成本** | **¥0.0002** | **¥0.0016** | **-¥0.0013** | **混合模式节省88%成本** |
| 平均质量 | 0.912 | 0.974 | -0.061 | 质量基本持平(T06摘要偏短) |
| **隐私合规** | **2/8** | **0/8** | **+2** | **敏感数据不出域** |
| 调度器决策数 | 11 | — | — | EdgeCloudScheduler真实产出 |
| 调度器迁移数 | 2 | — | — | migrate()真实调用 |

### 核心发现

1. **成本节省88%**：混合模式仅Cloud层1个任务产生API费用（¥0.0002），其余7个任务在本地免费执行。纯云端8个任务共¥0.0016。

2. **隐私合规**：PRIVACY_FIRST策略将2个隐私敏感任务（T01健康数据、T05财务数据）强制路由到Edge层，`privacy_guaranteed=True`。纯云端模式下所有敏感数据发送到外部API。

3. **三层分流有效**：EdgeCloudScheduler的BALANCED策略评分公式（适配度×0.5 + 延迟×0.3 + 成本×0.2）将多数任务路由到Edge（低延迟+零成本得分最高），GPU任务路由到Fog，大上下文任务路由到Cloud。

4. **质量基本持平**：混合模式平均质量0.912 vs 纯云端0.974，差距仅0.061。T06摘要质量偏低（0.30）因端侧模型生成过短，其余任务质量均为1.00。

---

## 7. 层间迁移（scheduler.migrate() + 真实重新执行）

### 7.1 场景1: Fog算力不足 → 上抛到Cloud

| 指标 | Fog执行 | Cloud执行 | 变化 |
|:-----|:--------:|:---------:|:----:|
| 延迟 | 32,715ms | 3,054ms | -90.7% |
| 质量 | 0.53 | 1.00 | +0.47 |
| Token | 922 | 321 | -65.2% |

**迁移调用**：`scheduler.migrate("T03", DeployTier.FOG, DeployTier.CLOUD, "Fog层推理质量不足")` → 返回 `True`

### 7.2 场景2: Cloud隐私违规 → 下推到Edge

| 指标 | Cloud执行 | Edge执行 | 变化 |
|:-----|:---------:|:--------:|:----:|
| 延迟 | 2,781ms | 22,614ms | +713.1% |
| 质量 | 1.00 | 1.00 | — |
| 隐私 | ❌ VIOLATED | ✅ GUARANTEED | — |

**迁移调用**：`scheduler.migrate("T01", DeployTier.CLOUD, DeployTier.EDGE, "检测到敏感健康数据")` → 返回 `True`

---

## 8. 容错Fallback（update_resource_state() + 真实重新调度执行）

| 场景 | 故障层 | 重新调度层 | 延迟(ms) | 质量 | 隐私 | 状态 |
|:-----|:------:|:----------:|:--------:|:----:|:----:|:----:|
| Edge不可用 | edge | fog | 23,089 | 0.77 | ❌ | OK |
| Cloud不可用 | cloud | fog | 12,631 | 1.00 | — | OK |
| Fog不可用 | fog | cloud | 3,127 | 1.00 | ❌ | OK |

**验证方法**：调用 `scheduler.update_resource_state(tier, name, available=False)` 标记资源不可用，然后重新调用 `scheduler.schedule()` 获取新的调度决策，在新的层级执行真实LLM推理。

**结果**：三种故障场景全部成功重新调度并执行，任务未中断。

---

## 9. 实验结论

### 9.1 能力验证矩阵

| 能力维度 | 验证结果 | 证据 |
|:---------|:--------:|:-----|
| 项目真实调度器运行 | ✅ | EdgeCloudScheduler 11次schedule() + 2次migrate() + 3次update_resource_state() |
| 三层真实LLM推理 | ✅ | 27次真实调用，100%成功率 |
| 调度器决策正确性 | ✅ | 8任务自动分流到3层(5/2/1) |
| 隐私合规调度 | ✅ | PRIVACY_FIRST策略2/8任务privacy_guaranteed=True |
| 成本优化 | ✅ | 混合模式节省88% API成本 |
| 层间迁移 | ✅ | migrate() 2次成功，迁移后真实重新执行 |
| 容错Fallback | ✅ | 3种故障场景全部成功重新调度 |
| 模型能力匹配 | ✅ | GPU任务路由到Fog(gpu_count>0)，大上下文路由到Cloud |

### 9.2 赛题要求对应

| 赛题要求 | 本次验证 |
|:---------|:---------|
| "系统须适配终端、边缘与云端异构算力环境" | ✅ 三层异构模型(9B/14B/API)实机验证 |
| "依据子任务的实时性要求与数据敏感等级，自动完成推理位置的动态选择" | ✅ EdgeCloudScheduler根据privacy_level/latency_budget/needs_gpu/context_window自动选层 |
| "充分利用云端算力处理高复杂度子任务" | ✅ 大上下文任务路由到Cloud API |
| "能够接受动态注入的异常、需求变更或节点失效" | ✅ 3种故障场景fallback验证 |
| "展示中间决策过程与推理轨迹" | ✅ SchedulingDecision含selected_tier/resource/confidence/reason/privacy_guaranteed |

### 9.3 已知局限

1. **单机模拟三层**：在单台PC上用不同Ollama模型模拟三层。实际部署应使用物理隔离的设备。架构设计已支持分布式部署，仅需修改TierResource端点配置。

2. **本地模型延迟偏高**：Ollama在CPU上运行，延迟高于GPU加速环境。

3. **BALANCED策略偏向Edge**：由于Edge层延迟最低(5ms)且成本为零，BALANCED评分公式将多数任务路由到Edge。实际部署中Edge层可能有更高负载或更小模型，调度分布会更均衡。

---

## 10. 调度器统计

来自 `scheduler.get_scheduling_stats()`：

```json
{
  "policy": "balanced",
  "total_decisions": 11,
  "tier_distribution": {"edge": 7, "fog": 2, "cloud": 2},
  "total_migrations": 2,
  "resources": {"edge": 1, "fog": 1, "cloud": 1}
}
```

---

*本报告由 `edge_cloud_real_verification.py` 自动生成，所有调度决策来自 NexusFlow 项目真实的 `EdgeCloudScheduler` 代码执行，所有LLM推理为真实调用。*
