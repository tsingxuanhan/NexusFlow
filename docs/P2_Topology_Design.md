# P2: 动态拓扑可优化、可解释升级

## 目标
将 DynamicRouter 从黑盒决策升级为可观测、可解释、可学习的系统。

## 现状分析

### 当前架构
```
TaskRequirement → DynamicTopologyRouter → RoutePlan
                    ↓
         AgentCapabilityProfile[] (静态画像)
         edge_weight = f(load, preference, tier, latency)
```

### 问题
1. **不可解释**：为什么选这个拓扑？权重怎么算的？没有人类可读的解释
2. **不可优化**：路由决策不学习历史执行结果，每次都是同样逻辑
3. **黑盒权重**：edge_weight 的 4 个因子（load/preference/tier/latency）权重固定，无法根据场景调整

## 设计方案

### 1. 可解释层 (TopologyInterpreter)

**输出格式**：
```python
@dataclass
class RoutingExplanation:
    plan_id: str
    decision_summary: str           # "选择了3-Agent串行链：coordinator→executor→reviewer"
    factor_breakdown: Dict[str, float]  # 各因子贡献度
    alternative_considered: List[str]     # 考虑过的备选方案
    confidence_factors: List[str]         # 影响置信度的因素
    human_readable: str             # 完整自然语言解释
```

**解释策略**：
- 列出 top-3 候选方案及其评分
- 说明最终选择的胜出原因（哪些因子占优）
- 指出关键瓶颈（如跨层通信惩罚、负载过高）

### 2. 可优化层 (TopologyOptimizer)

**学习机制**：
```python
class TopologyOptimizer:
    def record_execution(self, plan: RoutePlan, outcome: ExecutionOutcome):
        """记录执行结果：成功/失败/延迟/成本"""
        
    def get_optimal_weights(self, task_pattern: str) -> Dict[str, float]:
        """基于历史数据学习最优权重"""
        
    def recommend_improvements(self, plan: RoutePlan) -> List[str]:
        """分析当前方案的改进空间"""
```

**学习算法**：
- 按任务模式（capability_required × complexity）分组
- 记录每种模式下的成功路由及其成本
- 使用多臂老虎机（MAB）平衡探索/利用
- 在线更新 edge_weight 的因子权重

### 3. 集成到 DynamicRouter

```python
class DynamicTopologyRouter:
    def __init__(self):
        self.interpreter = TopologyInterpreter()
        self.optimizer = TopologyOptimizer()
    
    def route(self, task) -> RoutePlan:
        plan = self._compute_plan(task)
        
        # 生成解释
        plan.explanation = self.interpreter.explain(plan, task)
        
        # 记录用于优化
        self.optimizer.record_request(task, plan)
        
        return plan
    
    def complete_route(self, plan_id, outcome):
        """执行完成后调用，记录结果"""
        self.optimizer.record_execution(plan_id, outcome)
```

## 实现计划

### Phase 1: 可解释层
- [ ] TopologyInterpreter 类
- [ ] RoutingExplanation 数据结构
- [ ] 解释生成逻辑（factor breakdown + natural language）
- [ ] 集成到 RoutePlan

### Phase 2: 可优化层
- [ ] TopologyOptimizer 类
- [ ] 执行结果记录
- [ ] 权重学习算法（MAB）
- [ ] 在线更新机制

### Phase 3: 评测验证
- [ ] 在 LHAB-NF 中添加解释性指标
- [ ] 对比实验：固定权重 vs 学习权重
- [ ] 可解释性用户研究（人工评估解释质量）

## 预期收益
1. **调试友好**：路由决策可追溯，问题定位快
2. **持续优化**：从执行数据学习，路由质量随时间提升
3. **信任建立**：用户理解系统为什么这样决策
4. **论文价值**：可解释 + 可学习的动态拓扑是差异化贡献
