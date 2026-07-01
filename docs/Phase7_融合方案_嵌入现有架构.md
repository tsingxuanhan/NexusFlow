# Phase 7 融合方案：将认知分工 + 自适应上下文嵌入现有架构

> 核心原则：不堆砌模块， surgically嵌入已有接口的关键节点

---

## 一、现有架构全景与注入点

```
用户输入
    │
    ▼
┌──────────────────────────────────────────────────────────────────┐
│  PlannerAgent (PRO模型)                                          │
│  └─ decompose() → TaskTree                                       │
│      └─ TaskNode: id, description, assigned_agent, dependencies  │
│                                                                  │
│  ★ 注入点①：TaskNode 增加 execution_mode 字段                     │
│    "sequential"(默认) | "cognitive_division"(认知分工)             │
└──────────────────────────┬───────────────────────────────────────┘
                           │
                           ▼
┌──────────────────────────────────────────────────────────────────┐
│  DynamicTopologyRouter.route(task) → RoutePlan                   │
│  └─ 当前：选出 agent_chain = [A, B, C]（串行执行链）              │
│                                                                  │
│  ★ 注入点②：RoutePlan 增加 cdol_plan 字段                        │
│    当 execution_mode="cognitive_division" 时，                    │
│    router 不再产出 agent_chain，而是产出 perspective_assignments   │
└──────────────────────────┬───────────────────────────────────────┘
                           │
              ┌────────────┴────────────┐
              ▼                         ▼
     sequential模式              cognitive_division模式
     (现有流程不变)              ★ 注入点③：CDoL Engine 接管
              │                         │
              ▼                         ▼
┌─────────────────────┐   ┌────────────────────────────────────────┐
│ Agent串行执行        │   │  PerspectiveDecomposer                 │
│ A→B→C→结果           │   │  ├─ 分配视角+掩码给各Agent              │
│ (现有逻辑)           │   │  ├─ CommunicationLayer (Round 0→1→2)   │
│                     │   │  └─ FusionJudge (矛盾分类→输出)         │
│                     │   │                                        │
│                     │   │  ★ 注入点④：全程由 AdaptiveContextMgr   │
│                     │   │    管理每个Agent的本地窗口+全局同步       │
└──────────┬──────────┘   └──────────────────┬─────────────────────┘
           │                                  │
           └──────────────┬───────────────────┘
                          ▼
┌──────────────────────────────────────────────────────────────────┐
│  MemoryManager (Core/Archival/Recall)                            │
│                                                                  │
│  ★ 注入点⑤：GlobalMemoryPool 作为第四层，桥接三层记忆              │
│    - Core → 注入到Agent prompt（不变）                            │
│    - Archival → GlobalMemoryPool 的持久化后端                      │
│    - Recall → RetrievalHeadAgent 的经验检索源                     │
│    - 新增 Global层 → 跨Agent推理产物的实时汇聚                    │
└──────────────────────────────────────────────────────────────────┘
```

---

## 二、六个注入点的具体设计

### 注入点①：TaskNode 增加 execution_mode

**改什么**：`task_tree.py` 的 TaskNode dataclass

```python
# task_tree.py — TaskNode 新增字段（约+15行）
@dataclass
class TaskNode:
    # ... 现有字段不变 ...
    
    # Phase 7 新增：执行模式
    execution_mode: Literal["sequential", "cognitive_division"] = "sequential"
    
    # 认知分工专属字段（仅 execution_mode="cognitive_division" 时有效）
    decomposition_strategy: Optional[str] = None  # 证据拆分/角色约束/层级分离/...
    perspective_count: int = 2                     # 视角数量（默认2）
    max_communication_rounds: int = 2              # 最大通信轮次
    
    @property
    def needs_collaborative_reasoning(self) -> bool:
        return self.execution_mode == "cognitive_division"
```

**谁设置它**：PlannerAgent.decompose() 在分解任务时，对需要深度推理的节点标记 `execution_mode="cognitive_division"`

```python
# agents/planner.py — PlannerAgent.decompose() 增加自动标记逻辑（约+30行）
class PlannerAgent:
    def decompose(self, goal: str, depth: int = 2) -> "TaskTree":
        # ... 现有分解逻辑不变 ...
        
        # Phase 7: 自动识别需要认知分工的节点
        for node in task_tree.get_all_nodes():
            if self._requires_collaborative_reasoning(node):
                node.execution_mode = "cognitive_division"
                node.decomposition_strategy = self._select_strategy(node)
        
        return task_tree
    
    def _requires_collaborative_reasoning(self, node: TaskNode) -> bool:
        """判断节点是否需要认知分工"""
        signals = [
            "验证" in node.description or "假设" in node.description,  # 假设检验
            "对比" in node.description or "评估" in node.description,  # 对比评估
            node.action_type == "review",                                # 审查类
            len(node.dependencies) >= 2,                                 # 多依赖汇聚
        ]
        return sum(signals) >= 2  # 至少2个信号触发
```

**效果**：TaskTree 的可视化中，每个节点不仅有 `assigned_agent`，还有 `execution_mode`。Demo中可以清晰展示"哪些节点用了认知分工"。

---

### 注入点②：DynamicTopologyRouter 支持认知分工路由

**改什么**：`dynamic_router.py` 的 RoutePlan + route() 方法

```python
# dynamic_router.py — RoutePlan 新增字段（约+20行）
@dataclass
class RoutePlan:
    # ... 现有字段不变 ...
    
    # Phase 7: 认知分工计划
    cdol_enabled: bool = False
    perspective_assignments: List[Dict] = field(default_factory=list)
    # 每个 assignment: {agent_id, perspective_question, context_mask, role_constraint}

# dynamic_router.py — route() 方法增加分支（约+40行）
class DynamicTopologyRouter:
    def route(self, task: TaskRequirement) -> RoutePlan:
        # ... 现有逻辑不变 ...
        
        # Phase 7: 认知分工模式
        if task.execution_mode == "cognitive_division":
            plan.cdol_enabled = True
            plan.perspective_assignments = self._generate_perspective_assignments(
                task, candidates
            )
            # 认知分工不需要串行agent_chain，而是并行Agent集合
            plan.agent_chain = [a.agent_id for a in candidates[:task.perspective_count]]
            plan.topology_type = "star"  # 星型拓扑：所有Agent连到FusionJudge
        
        return plan
    
    def _generate_perspective_assignments(self, task, candidates):
        """基于任务特征生成视角分配"""
        from cognitive_division_engine import PerspectiveDecomposer
        decomposer = PerspectiveDecomposer(llm_chat=self._llm_chat)
        plan = decomposer.decompose(task.description, candidates)
        return [
            {
                "agent_id": a.agent_id,
                "perspective_question": a.perspective_question,
                "context_mask": a.context_mask.to_dict(),
                "role_constraint": a.role_constraint,
            }
            for a in plan.assignments
        ]
```

**关键**：TaskRequirement 也需要增加对应字段。

```python
# dynamic_router.py — TaskRequirement 新增字段（约+5行）
@dataclass
class TaskRequirement:
    # ... 现有字段不变 ...
    execution_mode: str = "sequential"  # "sequential" | "cognitive_division"
    perspective_count: int = 2
    decomposition_strategy: Optional[str] = None
```

---

### 注入点③：CDoL Engine 作为新的执行后端

**新增文件**：`cognitive_division_engine.py`（~400行）

**与现有架构的关系**：

```python
# cognitive_division_engine.py
from base_agent import BaseAgent
from a2a_protocol import A2AMessageType, get_a2a_network

class CognitiveDivisionEngine:
    """
    认知分工引擎 — 作为 DynamicTopologyRouter 的执行后端
    
    调用链：
    TaskNode(execution_mode="cognitive_division")
      → DynamicTopologyRouter.route() → RoutePlan(cdol_enabled=True)
      → CognitiveDivisionEngine.execute(route_plan)
      → 返回结果给 TaskTree
    """
    
    def __init__(self, agents: Dict[str, BaseAgent], memory_pool: GlobalMemoryPool):
        self.agents = agents
        self.decomposer = PerspectiveDecomposer()
        self.comm_layer = CommunicationLayer()
        self.judge = FusionJudge()
        self.memory_pool = memory_pool
        self.context_mgr = AdaptiveContextManager(memory_pool)  # 注入点④联动
    
    async def execute(self, route_plan: RoutePlan, task: TaskRequirement) -> CDoLResult:
        """
        认知分工执行流程
        
        与现有框架的对接：
        - 输入：RoutePlan（来自Router）+ TaskRequirement（来自TaskTree）
        - 输出：CDoLResult → 写回 TaskNode.result
        - 中间产物：写入 GlobalMemoryPool
        """
        # Round 0: 各Agent在受限上下文下独立推理
        conclusions = await self.comm_layer.run_round_0(
            assignments=route_plan.perspective_assignments,
            agents=self.agents,
            context_mgr=self.context_mgr  # 小窗口策略在此生效
        )
        
        # 中间结论写入全局记忆池
        for c in conclusions:
            self.memory_pool.add_conclusion(c.agent_id, c)
        
        # Round 1: 差异归因
        attributions = await self.comm_layer.run_round_1(
            conclusions=conclusions,
            agents=self.agents,
            context_mgr=self.context_mgr
        )
        
        # Round 2: 修正结论
        revised = await self.comm_layer.run_round_2(attributions, conclusions)
        
        # 融合判断
        judgment = await self.judge.judge(revised)
        
        return CDoLResult(
            final_answer=judgment.final_answer,
            reasoning_tree=judgment.reasoning_tree,
            contradiction_report=judgment.contradiction_report,
            metrics=self._compute_metrics(conclusions, revised, judgment)
        )
```

**在 agents/__init__.py 中注册**：

```python
# agents/__init__.py — Phase 7 新增（约+10行）
from cognitive_division_engine import CognitiveDivisionEngine, CDoLResult
from adaptive_context_manager import AdaptiveContextManager, GlobalMemoryPool, LazinessDetector

__all__ += [
    "CognitiveDivisionEngine", "CDoLResult",
    "AdaptiveContextManager", "GlobalMemoryPool", "LazinessDetector",
]
```

---

### 注入点④：AdaptiveContextManager 嵌入 Agent 执行循环

**改什么**：`base_agent.py` 的 BaseAgent 增加上下文窗口控制钩子

```python
# base_agent.py — BaseAgent 新增方法（约+40行）
class BaseAgent:
    def __init__(self, ...):
        # ... 现有初始化 ...
        self._context_window = None        # Phase 7: 自适应上下文窗口
        self._global_sync_callback = None  # Phase 7: 全局同步回调
    
    def set_context_window(self, window):
        """Phase 7: 被 AdaptiveContextManager 调用，设置本地窗口"""
        self._context_window = window
    
    def set_global_sync_callback(self, callback):
        """Phase 7: 被 ForcedGlobalSync 调用，设置同步注入回调"""
        self._global_sync_callback = callback
    
    def _prepare_messages(self, user_message: str) -> List[Dict]:
        """修改消息准备逻辑，加入上下文窗口截断"""
        messages = self._build_system_messages()
        messages.append({"role": "user", "content": user_message})
        
        # Phase 7: 如果启用了自适应上下文管理
        if self._context_window is not None:
            messages = self._context_window.truncate_messages(messages)
            
            # 检查是否需要注入全局同步信息
            if self._global_sync_callback:
                sync_info = self._global_sync_callback()
                if sync_info:
                    messages.insert(-1, {
                        "role": "system",
                        "content": f"[全局状态同步] {sync_info}"
                    })
        
        return messages
```

**AdaptiveContextManager 的编排入口**：

```python
# adaptive_context_manager.py
class AdaptiveContextManager:
    """
    自适应上下文管理器 — 编排入口
    
    在 CDoL Engine 执行过程中被调用：
    - 控制每个Agent的本地窗口大小
    - 定期触发全局同步
    - 检测懒惰并干预
    """
    
    def __init__(self, global_memory: GlobalMemoryPool):
        self.global_memory = global_memory
        self.window_controller = AdaptiveWindowController()
        self.laziness_detector = LazinessDetector()
        self.sync_engine = ForcedGlobalSync()
        self.retrieval_head = RetrievalHeadAgent("retrieval-head", global_memory)
    
    def prepare_agent(self, agent: BaseAgent, task_progress: float):
        """在Agent执行前准备上下文环境"""
        laziness = self.laziness_detector.check(agent.id, agent.get_state())
        
        # 自适应窗口
        window_size = self.window_controller.adjust(task_progress, laziness.laziness_score)
        window = LocalContextWindow(max_tokens=window_size)
        agent.set_context_window(window)
        
        # 全局同步回调
        agent.set_global_sync_callback(
            lambda: self.sync_engine.get_latest_summary(self.global_memory)
        )
        
        # 懒惰干预
        if laziness.is_lazy:
            intervention = self.laziness_detector.intervention(laziness)
            if intervention.forced_query:
                agent.inject_forced_retrieval(intervention.forced_query)
    
    async def on_step_complete(self, agent: BaseAgent, step_result):
        """每步完成后：更新全局记忆 + 检查同步"""
        # 将Agent的中间结论写入全局记忆
        if step_result.has_conclusion:
            self.global_memory.add_conclusion(agent.id, step_result.conclusion)
        
        # 检查是否触发全局同步
        sync_result = await self.sync_engine.maybe_sync(
            self.global_memory, 
            agents=[agent]
        )
        return sync_result
```

---

### 注入点⑤：GlobalMemoryPool 作为第四层记忆

**改什么**：`memory_manager.py` 增加 Global 层

```python
# memory_manager.py — MemoryManager 扩展（约+30行）
class MemoryManager:
    def __init__(self, ...):
        # ... 现有三层 ...
        self.core = create_core_memory_with_defaults(...)
        self.archival = ArchivalMemory(...)
        self.recall = RecallMemory(...)
        
        # Phase 7: 第四层 — Global Memory Pool（跨Agent推理产物汇聚）
        from adaptive_context_manager import GlobalMemoryPool
        self.global_pool = GlobalMemoryPool(backing_store=self.archival)
    
    def remember_global(self, agent_id: str, conclusion, memory_type="conclusion"):
        """Agent提交推理产物到全局记忆"""
        self.global_pool.add(memory_type, agent_id, conclusion)
        
        # 同步到 Archival 持久化
        self.archival.add_entry(
            content=conclusion.conclusion,
            metadata={"agent_id": agent_id, "type": memory_type, "source": "global_pool"}
        )
    
    def recall_global(self, query: str, top_k: int = 5):
        """从全局记忆中检索（RetrievalHeadAgent的核心依赖）"""
        return self.global_pool.semantic_search(query, top_k)
```

**与现有三层记忆的关系**：

| 层 | 存什么 | 谁写 | 谁读 | 延迟 |
|---|---|---|---|---|
| Core | 用户画像/Agent状态/规则 | 系统 | 注入到prompt | 0ms |
| Archival | 持久知识（文档/事实） | Agent交互 | 语义检索 | ~20ms |
| Recall | 时序经验（交互/错误） | Agent交互 | 经验回忆 | ~5ms |
| **Global（新）** | **跨Agent推理产物** | **CDoL Engine** | **RetrievalHead + FusionJudge** | **~10ms** |

Global 层不替代任何现有层，它是**横向的**——汇聚所有Agent的推理产物，让不同Agent能"看到"彼此的结论（通过检索，不是直接共享）。

---

### 注入点⑥：A2A Protocol 增加认知分工消息类型

**改什么**：`a2a_protocol.py` 的 A2AMessageType

```python
# a2a_protocol.py — 新增消息类型（约+10行）
class A2AMessageType(Enum):
    # ... 现有类型 ...
    
    # Phase 7: 认知分工协议
    CDOL_PERSPECTIVE = "cdol_perspective"             # 视角分配通知
    CDOL_CONCLUSION = "cdol_conclusion"               # 中间结论（通信层载体）
    CDOL_ATTRIBUTION = "cdol_attribution"             # 差异归因
    CDOL_REVISION = "cdol_revision"                   # 修正结论
    CDOL_FALSE_CONSENSUS = "cdol_false_consensus"     # 虚假一致警告
    CDOL_SYNC = "cdol_sync"                           # 全局同步消息
```

---

## 三、Demo 升级：展示认知分工过程

**改什么**：`demo/nexusflow_demo.py` 增加认知分工演示场景

```python
# demo/nexusflow_demo.py — 新增演示场景（约+80行）
def demo_cognitive_division():
    """
    演示：低碳水泥配方优化中的关键决策
    
    展示内容：
    1. 视角分解：Miner看实验数据，Assayer看理论推导
    2. Round 0：各自推理，得出不同结论
    3. Round 1：差异归因（"对方可能看到了什么？"）
    4. 融合判断：检测虚假一致 → 输出条件依赖型混合方案
    5. 对比：单Agent全量信息 → 倾向某一方
              认知分工 → 条件依赖型混合方案
    """
    from cognitive_division_engine import CognitiveDivisionEngine
    from adaptive_context_manager import GlobalMemoryPool
    
    # 初始化
    memory_pool = GlobalMemoryPool()
    engine = CognitiveDivisionEngine(agents=create_team()["agents"], memory_pool=memory_pool)
    
    # 任务：偏高岭土 vs 石灰石粉作为SCM
    task = TaskRequirement(
        task_id="cdol-demo-001",
        description="评估偏高岭土和石灰石粉作为 Supplementary Cementitious Material 的优选方案",
        execution_mode="cognitive_division",
        perspective_count=2,
        decomposition_strategy="evidence_split",  # 证据拆分
    )
    
    # 执行认知分工
    result = engine.execute(route_plan=router.route(task), task=task)
    
    # 可视化输出
    print(f"\n{'='*60}")
    print(f"认知分工演示：{task.description}")
    print(f"{'='*60}")
    print(f"\n[视角分配]")
    for a in result.perspective_assignments:
        print(f"  {a.agent_id}: {a.perspective_question}")
        print(f"    掩码: 可见={a.context_mask.allowed_evidence}, 屏蔽={a.context_mask.blocked_evidence}")
    
    print(f"\n[Round 0: 独立推理]")
    for c in result.round0_conclusions:
        print(f"  {c.agent_id}: {c.conclusion} (置信度={c.confidence:.2f})")
    
    print(f"\n[Round 1: 差异归因]")
    for a in result.attributions:
        print(f"  {a.agent_id}: {a.revision_reason}")
    
    print(f"\n[融合判断]")
    print(f"  矛盾类型: {result.judgment.contradiction_type}")
    print(f"  最终结论: {result.final_answer}")
    
    print(f"\n[对比基线]")
    print(f"  单Agent(全量信息): {result.baseline_single_agent}")
    print(f"  认知分工:          {result.final_answer}")
    print(f"  协同增益:          {result.synergy_gain:.2f}x")
```

---

## 四、代码量与文件清单

| 文件 | 操作 | 行数 | 说明 |
|------|------|------|------|
| `cognitive_division_engine.py` | 新增 | ~400 | 认知分工引擎主体 |
| `adaptive_context_manager.py` | 新增 | ~500 | 自适应上下文管理器主体 |
| `task_tree.py` | 修改 | +15 | TaskNode 增加 execution_mode |
| `dynamic_router.py` | 修改 | +65 | RoutePlan/TaskRequirement/route() 扩展 |
| `base_agent.py` | 修改 | +40 | 上下文窗口钩子 + 同步回调 |
| `a2a_protocol.py` | 修改 | +10 | 6个新消息类型 |
| `memory_manager.py` | 修改 | +30 | Global层 + remember_global/recall_global |
| `agents/__init__.py` | 修改 | +15 | 注册新模块 |
| `agents/planner.py` | 修改 | +30 | 自动标记 CDoL 节点 |
| `demo/nexusflow_demo.py` | 修改 | +80 | 认知分工演示场景 |
| **合计** | | **~1185新增** | 现有文件改动~205行 |

---

## 五、赛题对应关系

| 赛题关键词 | 对应代码 | 评委可见的证据 |
|-----------|---------|-------------|
| **动态异构** | DynamicTopologyRouter（Phase 6已有）| Demo中拓扑重建动画 |
| **群体智能** | CDoL Engine（Phase 7）| 多Agent协同推理过程可视化 |
| **深度协同推理** | PerspectiveDecomposer + FusionJudge | 视角分配→差异归因→虚假一致检测 |
| **超长程任务** | AdaptiveContextManager + GlobalMemoryPool | 50步任务Benchmark + 懒惰检测曲线 |
| **动态拓扑** | Router + CDoL 联动 | 任务节点标记 CDoL → Router产出星型拓扑 |

---

## 六、叙事线：评委视角的融合体验

```
评委看到：
1. 用户输入一个复杂科研问题
2. Planner 自动分解 → TaskTree 中某些节点高亮为"认知分工"模式
3. Router 识别 CDoL 节点 → 产出视角分配方案（展示两个Agent看到的不同信息）
4. Round 0: 两个Agent各自推理 → 中间结论 + 置信度
5. Round 1: 差异归因 → "对方可能看到了什么"
6. FusionJudge: 检测到虚假一致 → 回溯修正
7. 最终输出：条件依赖型方案（任何单Agent都无法独立得出）
8. 全程：AdaptiveContextManager 的窗口变化曲线 + 懒惰检测仪表盘
9. 对比：单Agent vs 认知分工的准确率/推理深度
```
