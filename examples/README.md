# NexusFlow Benchmark Examples

> 渐进式实验验证体系：从单Agent到完整系统的系统性对比

---

## 📊 实验总览

| 阶段 | 对比维度 | 核心发现 | 数据源 |
|------|---------|---------|--------|
| [Stage-1](stage1_single_vs_6roles/) | 单Agent vs 6角色CDoL | 回测精度提升50%，排名纠错 | NOAA + WHO |
| [Stage-2](stage2_6roles_vs_10roles/) | 6角色 vs 10角色CDoL | Critic质疑闭环，效率提升90% | NOAA + WHO |
| [Stage-3](stage3_full_system/) | 完整NexusFlow系统 | 拒绝无效结论，14模块真实执行 | NOAA + WHO |
| [Stage-4](stage4_fifty_steps/) | 50步端到端科研全流程 | 全链路拓扑切换，15个代表性产物 | NOAA + WHO |
| [横向对比](horizontal_comparison/) | NexusFlow vs AutoGen vs CrewAI | NexusFlow 92分领先，交叉验证能力突出 | WHO |

---

## 🏗️ 实验递进逻辑

```
Stage-1: 验证CDoL认知分工是否有价值
   ↓ 6角色显著优于单Agent → 进入Stage-2
Stage-2: 验证更多角色是否更好
   ↓ 10角色的Critic质疑闭环带来质变 → 进入Stage-3
Stage-3: 用真实代码管线验证
   ↓ 系统能拒绝错误结论（核心价值）→ 进入Stage-4
Stage-4: 50步端到端科研全流程
   ↓ 完整科研Pipeline验证 → 横向对比
横向对比: 与主流框架对比定位
```

---

## 📁 案例目录

### Stage-1: 单Agent vs 6角色CDoL
- **NOAA**: 华北5城气候诊断 — 综合MAPE从18.87%降至9.37%（精度翻倍）
- **WHO**: BRICS健康诊断 — 单Agent错误将俄罗斯排第1 → CDoL正确识别中国第1

### Stage-2: 6角色 vs 10角色CDoL
- 新增Critic/Coder/Monitor三角色
- NOAA: 综合评分85→90，结论严谨性+36%
- WHO: 耗时555s→51.2s（效率提升90.8%）
- Critic共7次质疑，全部有价值

### Stage-3: 完整NexusFlow系统
- 14个核心模块真实执行
- WHO: 置信度0.625→0.725（+16%），100%修正率
- NOAA: synergy_gain=1.25（真实协同增益）
- **核心价值**: 双任务均拒绝输出无效结论

### Stage-4: 50步端到端科研全流程
- 气候-健康关联分析（NOAA + WHO跨域）
- 50步 × 10角色 × 9次拓扑切换
- 15个代表性产物覆盖全链路
- CDoL引擎独立运行版（engine.py）

### 横向对比: NexusFlow vs AutoGen vs CrewAI
- NexusFlow: 92/100（交叉验证8分，唯一支持多源比对）
- AutoGen: 88/100（对话式验证，代码最简洁）
- CrewAI: 85/100（角色分工清晰，报告质量高）

---

## 🔢 数据总表

完整实验数据汇总见 [benchmark_summary.md](benchmark_summary.md)

### 核心数字速览

1. **回测精度翻倍**: NOAA MAPE 18.87% → 9.37%
2. **排名纠错**: WHO单Agent俄罗斯第1 → CDoL中国第1
3. **Critic质疑**: 10角色版本7次质疑全部有价值
4. **效率提升**: WHO 10角色耗时51.2s vs 6角色555s（-90.8%）
5. **拒绝错误**: Stage-3双任务均拒绝无效输出
6. **横向领先**: NexusFlow 92分 vs AutoGen 88分 vs CrewAI 85分

---

## 📋 运行环境

| 项目 | 配置 |
|------|------|
| LLM | DeepSeek Chat (deepseek-chat) |
| Python | 3.13+ |
| 数据源 | NOAA NCEI CDO v2 + WHO GHO OData API |
| 框架 | NexusFlow (本项目) |

---

*实验数据全部来自真实执行产物，非模拟数据*
*原始实验产物: [nexusflow-ppt/](../nexusflow-ppt/)*
