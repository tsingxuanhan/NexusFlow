# 荣耀MagicOS跨设备AI协同场景设计

> 场景编号：Honor-MagicOS-CrossDevice-001
> 设计日期：2026-07-23
> Demo脚本：`examples/honor_scenario/honor_magicos_demo.py`
> 验证数据：`examples/honor_scenario/honor_magicos_demo_data.json`

---

## 1. 场景概述

### 用户故事

用户对荣耀手机说：

> "帮我分析比亚迪的投资价值，我持有500股成本价210元，结合最新财报给个建议"

这是一个**超长程复杂任务**，需要跨手机、平板/PC、云端三层设备协同完成。涉及隐私数据处理、大上下文分析、深度推理、质量审核等多个环节。

### 荣耀生态映射

| NexusFlow层级 | 荣耀设备 | 角色 | 模型 |
|:------------:|:---------|:-----|:-----|
| 📱 Edge(端侧) | 荣耀手机 (MagicOS AI助手) | 隐私数据处理、简单交互、结果展示 | qwen3.5:9b |
| 🖥️ Fog(边缘) | 荣耀平板/PC (YOYO助手) | 深度推理、质量审核 | deepseek-r1:14b |
| ☁️ Cloud(云端) | 荣耀云服务 | 大上下文分析、报告生成 | DeepSeek API |

---

## 2. 任务分解（6步长程流程）

| 步骤 | 名称 | 执行设备 | 调度策略 | 隐私 | 说明 |
|:----:|:-----|:---------|:--------:|:----:|:-----|
| 1 | 意图解析与隐私提取 | 📱 荣耀手机 | PRIVACY_FIRST | 🔒 | 提取用户意图和持仓隐私数据，数据不出设备 |
| 2 | 财报数据获取与行业分析 | ☁️ 荣耀云服务 | BALANCED | — | 获取比亚迪财报+行业趋势，需大上下文 |
| 3 | 深度财务推理 | 🖥️ 荣耀平板/PC | BALANCED | — | 估值分析+投资逻辑推理，需GPU算力 |
| 4 | 综合分析与建议生成 | ☁️ 荣耀云服务 | BALANCED | — | 整合分析结果，生成投资建议报告 |
| 5 | 持仓盈亏计算 | 📱 荣耀手机 | PRIVACY_FIRST | 🔒 | 结合持仓数据计算盈亏，隐私端侧处理 |
| 6 | 质量审核 | 🖥️ 荣耀平板/PC | BALANCED | — | Reviewer审核建议合理性和完整性 |

### 数据流向

```
用户语音输入
    │
    ▼
┌─────────────────────────────────────────────────────┐
│  Step 1 [📱 手机] 意图解析 + 隐私提取               │
│  输出: {intent, stock, shares, cost_price}          │
│  🔒 持仓数据(500股/210元)留在手机本地               │
└──────────────────────┬──────────────────────────────┘
                       │ 仅传递: 分析意图 + 股票名称
                       ▼
┌─────────────────────────────────────────────────────┐
│  Step 2 [☁️ 云端] 财报获取 + 行业分析               │
│  输出: 营收/利润/市场份额/竞争格局/风险              │
└──────────────────────┬──────────────────────────────┘
                       │ 分析结果摘要
                       ▼
┌─────────────────────────────────────────────────────┐
│  Step 3 [🖥️ 平板] 深度财务推理                      │
│  输出: 估值分析 + 买入/持有/卖出建议                 │
└──────────────────────┬──────────────────────────────┘
                       │ 推理结论
                       ▼
┌─────────────────────────────────────────────────────┐
│  Step 4 [☁️ 云端] 综合报告生成                      │
│  输出: 投资评级 + 目标价 + 核心逻辑 + 风险提示       │
└──────────────────────┬──────────────────────────────┘
                       │ 投资建议(不含持仓数据)
                       ▼
┌─────────────────────────────────────────────────────┐
│  Step 5 [📱 手机] 持仓盈亏计算                      │
│  🔒 持仓数据在手机本地与建议结合计算盈亏             │
│  输出: 持仓市值 + 浮动盈亏 + 操作建议               │
└──────────────────────┬──────────────────────────────┘
                       │ 计算结果
                       ▼
┌─────────────────────────────────────────────────────┐
│  Step 6 [🖥️ 平板] 质量审核                         │
│  输出: 审核结论(通过/需修改/拒绝) + 审核意见        │
└─────────────────────────────────────────────────────┘
                       │
                       ▼
                 最终投研报告交付到用户手机
```

---

## 3. 实验结果

### 执行统计

| 指标 | 数据 |
|:-----|:-----|
| 总步骤数 | 6 |
| 成功步骤 | 6/6 (100%) |
| 总延迟 | 108,940ms (108.9s) |
| 总Token | 3,562 |
| 隐私保障步骤 | 2/6 |
| 层分布 | Edge:2 / Fog:2 / Cloud:2 |

### 执行轨迹

| 步骤 | 设备 | 延迟(ms) | Token | 隐私 | 响应摘要 |
|:----:|:----:|:--------:|:-----:|:----:|:---------|
| 1 | 📱 Edge | 13,999 | 157 | 🔒 | 提取JSON: intent/stock/shares/cost_price |
| 2 | ☁️ Cloud | 5,220 | 467 | — | 比亚迪财报+行业趋势结构化分析 |
| 3 | 🖥️ Fog | 34,158 | 993 | — | 估值合理偏低，建议买入 |
| 4 | ☁️ Cloud | 4,679 | 488 | — | 投资评级:买入，目标价280元 |
| 5 | 📱 Edge | 21,536 | 680 | 🔒 | 持仓市值125,000，浮盈20,000(+19%) |
| 6 | 🖥️ Fog | 29,347 | 777 | — | 审核结论:需修改，逻辑基本自洽 |

### 调度器决策

所有调度决策由 NexusFlow `EdgeCloudScheduler` 真实产出：

| 步骤 | 策略 | 调度层 | 置信度 | 决策原因 |
|:----:|:----:|:------:|:------:|:---------|
| 1 | PRIVACY_FIRST | Edge | 0.900 | Privacy-sensitive: forced to edge tier |
| 2 | BALANCED | Cloud | 0.836 | Balanced selection: score=0.836 at cloud |
| 3 | BALANCED | Fog | 0.921 | Balanced selection: score=0.921 at fog |
| 4 | BALANCED | Cloud | 0.836 | Balanced selection: score=0.836 at cloud |
| 5 | PRIVACY_FIRST | Edge | 0.900 | Privacy-sensitive: forced to edge tier |
| 6 | BALANCED | Fog | 0.921 | Balanced selection: score=0.921 at fog |

---

## 4. 场景价值分析

### 赛题维度对应

| 赛题要求 | 场景体现 |
|:---------|:---------|
| 超长程上下文连续性 | 6步流程跨设备执行，上下文通过步骤间传递保持 |
| 动态异构拓扑与低熵通信 | 三层设备按任务特征自动路由，非静态全连接 |
| 端-边-云异构资源自适应调度 | 隐私→Edge，推理→Fog，大上下文→Cloud |
| 典型产业场景验证 | 投资研究是高频金融场景，贴合"数字劳动力"定位 |

### 荣耀生态价值

1. **MagicOS AI助手协同**：手机接收用户意图，平板/PC执行深度推理，云端提供大模型能力
2. **隐私优先架构**：用户持仓数据（股数、成本价）始终在手机本地处理，不上传云端
3. **跨设备任务流转**：任务在手机→云端→平板→云端→手机→平板间自动流转，用户无感知
4. **质量保障闭环**：Step 6 Reviewer审核确保投资建议质量

### 社会价值

- **降低投研门槛**：普通用户通过手机语音即可获得专业级投研分析
- **隐私保护**：敏感财务数据不出设备，符合数据安全法规
- **算力优化**：简单任务在端侧免费执行，复杂任务才调用云端API，降低服务成本

---

## 5. 技术实现

### 使用的 NexusFlow 真实组件

| 组件 | 方法 | 用途 |
|:-----|:-----|:-----|
| EdgeCloudScheduler | register_tier() | 注册荣耀手机/平板/云服务三层资源 |
| EdgeCloudScheduler | schedule() | 6次调度决策 |
| SchedulingPolicy | PRIVACY_FIRST / BALANCED | 按任务特征动态切换策略 |
| TierResource | compute_fitness() | 资源适配度计算 |
| SchedulingDecision | selected_tier / confidence / reason | 调度决策结果 |

### 三层资源配置

```python
# 📱 Terminal: 荣耀手机 (MagicOS AI助手)
TierResource(tier=DeployTier.EDGE, name="honor-phone-magicos",
             supported_models=["qwen3.5:9b"], max_context_window=8192,
             latency_to_user_ms=5.0, cost_per_token=0.0)

# 🖥️ Fog: 荣耀平板/PC (YOYO助手)
TierResource(tier=DeployTier.FOG, name="honor-tablet-yoyo",
             gpu_count=1, gpu_memory_gb=16.0,
             supported_models=["deepseek-r1:14b"], max_context_window=32768,
             latency_to_user_ms=15.0, cost_per_token=0.0)

# ☁️ Cloud: 荣耀云服务
TierResource(tier=DeployTier.CLOUD, name="honor-cloud-service",
             supported_models=["deepseek-chat"], max_context_window=65536,
             latency_to_user_ms=150.0, cost_per_token=0.000001)
```

---

## 6. 运行方式

```bash
# 设置 API Key
export DEEPSEEK_API_KEY=your_api_key

# 运行 Demo
cd NexusFlow
python examples/honor_scenario/honor_magicos_demo.py
```

---

*本场景使用 NexusFlow 项目真实的 EdgeCloudScheduler 进行调度决策，所有 LLM 推理为真实调用。*
