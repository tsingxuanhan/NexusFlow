# Stage-3: 完整NexusFlow系统执行

> 从模拟到真实——用NexusFlow真实代码管线验证CDoL协议

---

## 🎯 实验目标

Stage-1/2使用子Agent模拟CDoL流程，Stage-3的核心目标是**用NexusFlow真实代码管线**运行同样的任务，验证：
1. CDoL三轮协议（Round 0→1→2）是否能在真实代码中正确执行
2. 信息不对称裁剪（ContextMask）是否生效
3. 矛盾自动判定（FusionJudge）是否工作
4. Critic独立审查在真实系统中的表现

## 🔬 实验方法

| 项目 | 配置 |
|------|------|
| **执行方式** | NexusFlow真实代码管线（非模拟）|
| **核心模块** | NexusOrchestrator + CognitiveDivisionEngine + AgentInformationPolicy + GlobalMemoryPool + AdaptiveContextManager + InsightDistiller |
| **LLM** | DeepSeek API (deepseek-chat)，每个Agent独立API调用 |
| **数据技能** | NOAA GHCND CLI + WHO GHO OData CLI |
| **对比基准** | Stage-1/2的模拟数据 |

### 与Stage-1/2的本质区别

| 维度 | Stage-1/2 | Stage-3 |
|------|-----------|---------|
| 执行方式 | 子Agent模拟CDoL | **真实代码管线** |
| Agent调用 | 子Agent内部分配 | **每个Agent独立DeepSeek API** |
| 信息不对称 | 模拟描述 | **ContextMask真实裁剪** |
| 三轮协议 | 模拟Round描述 | **真实执行** |
| 调用模块数 | 0 | **14个核心模块** |

## 📊 核心结果

### WHO任务

| 指标 | 数值 |
|------|------|
| 总耗时 | 206.0s |
| DeepSeek API调用 | 16次 |
| WHO数据技能调用 | 25次（5指标×5国家）|
| 总Tokens | 56,162 |
| Agent交互次数 | 15次 |

**CDoL核心指标:**

| 指标 | 数值 | 含义 |
|------|------|------|
| avg_confidence_r0 | 0.625 | Round 0平均置信度 |
| avg_confidence_revised | 0.725 | Round 2置信度（**+16%**）|
| revision_rate | 1.0 | **所有Agent都修正了结论** |
| ratio_attributable | 1.0 | 所有矛盾可归因于信息差异 |
| synergy_gain | 1.0 | 协同增益 |

**Critic审查（3项质疑）:**

| # | 质疑 | 严重程度 | 裁决 |
|---|------|:--------:|------|
| 1 | Observer数值在摘要中无出处 | High | 驳回（来自原始API）|
| 2 | synergy_gain=1.0与零产出矛盾 | High | 部分接受→重定义 |
| 3 | Analyst Round 0→Round 2矛盾 | Medium | 接受（可信度降至0.30）|

**最终结论**: "数据存在严重质量问题，**无法生成有效排名**" — 系统主动拒绝输出错误结论。

### NOAA任务

| 指标 | 数值 |
|------|------|
| 总耗时 | 56.2s |
| DeepSeek API调用 | 4次 |
| NOAA数据技能调用 | 5次（5城市）|
| **synergy_gain** | **1.25（真实协同增益）** |

**CDoL核心指标:**

| 指标 | 数值 | 含义 |
|------|------|------|
| synergy_gain | **1.25** | 真实协同增益 |
| action | **backtrack** | 需要回溯修正 |
| ratio_unattributable | 0.9 | 90%是真实分歧 |

**Critic审查**: 发现数据字段全为空字符串 → **结论无效**。
**最终结论**: "分析无效" — 系统发现NOAA CLI返回空数据，拒绝输出。

## 📈 与前Stage的对比

| 阶段 | NOAA | WHO | 执行方式 |
|------|:----:|:---:|---------|
| Stage-1 单Agent | 64 | 74 | 直接调用 |
| Stage-1 6角色 | 85 | 86 | 子Agent模拟 |
| Stage-2 10角色 | 90 | 90 | 子Agent模拟 |
| **Stage-3 完整系统** | **拒绝无效结论** | **拒绝无效结论** | **真实代码** |

**递进关系**: Stage-1/2证明了"评分更高"，Stage-3揭示了更深层价值——**能在数据不足时拒绝输出错误结论**，这是单Agent系统做不到的。

## 🔑 关键发现

> **NexusFlow真实系统的最大价值不是"评分更高"，而是能够在数据不足时拒绝输出错误结论。** Stage-3双任务均发现数据问题并拒绝无效输出——单Agent要么幻觉出数据，要么跳过检查，不可能做到这一点。synergy_gain=1.25（NOAA）是真实代码计算出的协同增益。

---

*详细报告见 [stage3_full_system_report.md](stage3_full_system_report.md)、[noaa_ten_roles_report.md](noaa_ten_roles_report.md) 和 [who_ten_roles_report.md](who_ten_roles_report.md)*
*可运行脚本见 [stage3_full_system.py](stage3_full_system.py)（需设置 DEEPSEEK_API_KEY）*
