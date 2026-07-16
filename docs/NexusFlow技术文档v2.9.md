# NexusFlow 技术文档 v2.9（增量更新）

> 基于 v2.8 技术文档，记录 v2.9 的增量变更。
> 更新时间：2026-07-15

---

## 一、v2.9 变更概览

| 变更 | 类型 | 影响模块 | 状态 |
|------|------|----------|:----:|
| CDoL 动态终止机制 | 新功能 | cognitive_division_engine.py | ✅ 已实现 |
| Phase 2 Ablation 实验 | 实验验证 | examples/ | ✅ 已完成 |
| LLM 5 维质量评分器 | 新工具 | examples/llm_quality_scorer.py | ✅ 已完成 |
| FusionJudge 虚假一致检测增强 | 增强 | cognitive_division_engine.py | ✅ 已实现 |

---

## 二、CDoL 动态终止机制

### 2.1 背景

v2.8 的 `execute()` 方法虽然有三层循环结构（Round 0 → Round 1 → Round 2），但 FusionJudge 仅做分类判定（converge / revision_round / backtrack / deep_review），**不触发循环退出**。无论 FusionJudge 判定什么结果，都固定执行到最后一轮。

这意味着框架声称的"动态自适应修正"实际上不存在——所有任务都跑满 3 轮，无论是否已收敛。

### 2.2 实现方案

在 `CognitiveDivisionEngine.execute()` 中实现真正的动态循环：

```python
# 新增参数
def execute(self, ..., max_rounds: int = 3) -> CDoLResult:
    
    # 动态修正循环
    for round_idx in range(1, max_rounds + 1):
        # Round 1: 差异归因
        round1_attributions = self.comm_layer.run_round_1(...)
        # Round 2: 修正结论
        round2_revised = self.comm_layer.run_round_2(...)
        # FusionJudge: 融合判断
        judgment = self.judge.judge(round2_revised)
        
        # 动态终止判定
        if judgment.action == "converge":
            terminated_early = True
            break  # 真实收敛，提前退出
        elif judgment.action == "backtrack":
            terminated_early = True
            break  # 需要回溯，提前退出
        # revision_round / deep_review → 继续下一轮
```

### 2.3 CDoLResult 新增字段

```python
@dataclass
class CDoLResult:
    # ... 原有字段 ...
    
    # 新增：动态终止相关
    communication_rounds: List[Dict[str, Any]]  # 每轮记录（action/type/revision_count/avg_confidence）
    terminated_early: bool                       # 是否提前终止（收敛/回溯）
    total_revision_rounds: int                   # 实际执行的修正轮次数
```

### 2.4 四种 action 的响应策略

| FusionJudge Action | 含义 | 响应 |
|-------------------|------|------|
| `converge` | 真实收敛，各 Agent 结论一致 | **提前终止** |
| `backtrack` | 根本性分歧，需要回溯重新分解 | **提前终止** |
| `revision_round` | 可归因矛盾，继续修正 | **继续下一轮** |
| `deep_review` | 虚假一致，需要更深层审查 | **继续下一轮** |

### 2.5 向后兼容

- `max_rounds` 默认值为 3，与 v2.8 行为一致
- 未设置动态终止时（所有 action 为 revision_round），等价于固定 3 轮
- 所有已有 demo 和测试无需修改

---

## 三、LLM 5 维质量评分器

### 3.1 设计动机

原有质量度量使用 hardcoded 公式：

```python
quality_score = 0.7 + (synergy_gain - 1.0) * 0.3
```

问题：无法反映不同实验条件下输出内容的真实质量差异。例如轮次 ablation 中 2/3/4 轮的 quality_score 完全相同（0.52）。

### 3.2 评分方法

使用 DeepSeek 作为评审模型，对 CDoL 输出进行 5 维评分：

| 维度 | 权重 | 含义 |
|------|:----:|------|
| Completeness | 0.25 | 任务覆盖完整度 |
| Depth | 0.25 | 推理链深度 |
| Consistency | 0.20 | 结论内部一致性 |
| Novelty | 0.15 | 创新性/独到见解 |
| Actionability | 0.15 | 可操作性 |

### 3.3 技术实现

```python
# examples/llm_quality_scorer.py

def score_output(task_description: str, output_text: str) -> Dict[str, Any]:
    """
    1. 截断输出至 3000 字符（保留头尾关键内容）
    2. 构造评分 Prompt（要求 JSON 格式输出）
    3. 调用 DeepSeek（temperature=0.1 保证评分一致性）
    4. 解析 JSON 响应，夹紧至 [0, 10]
    5. 加权合成 0-1 综合分
    """
```

### 3.4 评分结果示例

轮次 ablation（v2 评分器）：

| 轮次 | v1 质量分（hardcoded） | v2 LLM 综合分 | 区分度 |
|:----:|:---------------------:|:-------------:|:------:|
| 2 | 0.519 | **0.630** | ✅ |
| 3 | 0.521 | **0.750** | ✅ |
| 4 | 0.519 | **0.650** | ✅ |

v1 三组几乎完全相同（Δ < 0.002），v2 清晰呈现倒 U 型趋势（Δ > 0.10）。

---

## 四、Phase 2 Ablation 实验结果

详见 [Phase2_ablation实验报告.md](Phase2_ablation实验报告.md)。

### 核心发现

1. **轮次 ablation**：3 轮综合分 0.750 > 2 轮 0.630 > 4 轮 0.650，倒 U 型曲线验证 Nyquist 采样率
2. **路由 ablation**：三组有差异但噪声大（LLM-as-judge 方差），需多次试验
3. **拓扑切换成本**：Hybrid 模式表现最佳，动态模式有切换开销但潜力更高

### 可复现性

```bash
cd NexusFlow
export DEEPSEEK_API_KEY=your_key
python3 examples/demo_phase2_ablation_v2.py
```

---

## 五、v2.9 待完成项

| 任务 | 优先级 | 状态 |
|------|:------:|:----:|
| 端边云调度 fallback 修复 | 🔴 P0 | 待修复 |
| 路由 ablation 多次试验降方差 | 🟡 P1 | 待执行 |
| 拓扑切换成本多次试验 | 🟡 P1 | 待执行 |
| Embedding 认知多样性度量 | 🟢 P2 | 设计阶段 |
| Gradio Dashboard 部署 | 🟢 P2 | 待环境就绪 |
| 答辩 PPT 准备 | 🟡 P1 | 待启动 |
