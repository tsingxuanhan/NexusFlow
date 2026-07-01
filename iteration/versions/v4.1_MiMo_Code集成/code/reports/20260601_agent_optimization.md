# Agent架构优化监控报告（第4周）

> **执行时间:** 2026-06-01
> **执行人:** 炉守
> **框架版本:** v3.1
> **状态:** ✅ 分析完成 + 优化模块已实施

---

## 一、行业动态追踪

### 1.1 重大变化：Microsoft Agent Framework 1.0 发布

据微软官方博客（2026年4月），Microsoft Agent Framework 1.0 正式发布，AutoGen进入维护模式。

| 变化 | 说明 |
|------|------|
| AutoGen → Agent Framework | 合并AutoGen和Semantic Kernel |
| Graph-based Workflows | 图工作流替代对话驱动 |
| MCP + A2A 默认支持 | 模型上下文协议成为标准 |
| OpenTelemetry 集成 | 结构化链路追踪成为标配 |

### 1.2 开源框架能力矩阵 (2026年5月更新)

| 框架 | Stars | 状态管理 | 向量记忆 | 熔断器 | A2A | OTel |
|------|-------|---------|---------|--------|-----|------|
| LangGraph | 25k+ | TypedDict+DAG | 外接 | 外接 | 外接 | LangSmith |
| CrewAI | 44k+ | Implicit | ChromaDB | 部分 | ✅ | 部分 |
| AutoGen | 54k+ | 维护中 | 外接 | ❌ | ❌ | ✅ |
| Agent Framework | 新 | Graph | 原生 | ✅ | ✅ | ✅ |

### 1.3 关键架构趋势

**向量记忆演进**（据RankSquire 2026）：
```
L1 Hot (Redis, <1ms) → L2 Semantic (Qdrant, ~20ms) → L3 Episodic
```
检索型注入比全量注入节省 **51-72% Token**。

**错误恢复最佳实践**（据Supergood 2026）：
- 熔断器模式：防止级联故障
- 死信队列：失败任务持久化与重试
- 指数退避+Jitter：避免雷鸣羊群效应

---

## 二、当前架构问题分析

### 2.1 架构现状 (v3.0)

```
┌─────────────────────────────────────────────────────────────┐
│                        BaseAgent v3.0                       │
│  ✅ Checkpoint持久化    ✅ Handoff任务移交                    │
│  ✅ 错误分类与重试      ✅ OpenTelemetry导出                  │
│  ✅ DAG编排器(TaskOrchestrator)                             │
│  ✅ 分层记忆(EnhancedMemory)                                │
│  ⚠️ 熔断器: 无        ⚠️ 死信队列: 无                       │
│  ⚠️ 向量检索: 预留接口  ⚠️ A2A协议: 仅Handoff基础            │
└─────────────────────────────────────────────────────────────┘
```

### 2.2 问题清单

| 问题 | 严重程度 | 影响 |
|------|---------|------|
| 无熔断器模式 | 🔴 高 | 服务故障时持续重试，浪费资源 |
| 无死信队列 | 🟡 中 | 失败任务丢失，无法追踪 |
| 向量检索仅预留 | 🟡 中 | 无法真正节省Token |
| A2A协议不完整 | 🟡 中 | Agent间通信受限 |

---

## 三、优化实施

### 3.1 新增模块

#### 模块1: 熔断器 (`circuit_breaker.py`)

```python
from circuit_breaker import CircuitBreaker, CircuitBreakerConfig

# 配置
config = CircuitBreakerConfig(
    failure_threshold=5,      # 5次失败后打开
    success_threshold=2,      # 半开状态2次成功后关闭
    timeout=30.0,            # 30秒后尝试恢复
    jitter=True              # 防止雷鸣羊群
)

cb = CircuitBreaker("ollama_api", config)

# 使用方式1: with语句
with cb:
    result = call_api()

# 使用方式2: call方法
result = cb.call(call_api)
```

**状态机:**
```
CLOSED (正常) ──[5次失败]──→ OPEN (熔断)
    ↑                              │
    └────[2次成功]──── HALF_OPEN ──┘
              ↑                      │
              └────[超时30s]─────────┘
```

#### 模块2: 死信队列 (`dead_letter_queue.py`)

```python
from dead_letter_queue import DeadLetterQueue, DLQPriority, get_dlq

# 初始化
dlq = get_dlq(storage_path="./dlq_state.json")

# 提交失败任务
dlq.submit(
    task_id="task_123",
    payload={"query": "..."},
    error=Exception("timeout"),
    error_type="timeout",
    priority=DLQPriority.HIGH
)

# 启动自动重试工作者
dlq.start_worker(retry_func=my_retry_function)

# 查询状态
stats = dlq.get_stats()
```

**工作流程:**
```
失败 → DLQ(pending) → [重试] → DLQ(retrying)
                              ↓成功     ↓失败
                          DLQ(completed) → [重试直到dead]
```

#### 模块3: 向量记忆 (`vector_memory.py`)

```python
from vector_memory import VectorMemory, MemoryTier

vm = VectorMemory(
    l1_max_size=20,      # 热状态
    l2_max_size=500,     # 语义存储
    l3_max_size=2000     # 情景日志
)

# 添加记忆
vm.add("用户偏好详细答案", role="system", importance=0.8)

# 检索
entries = vm.retrieve("用户的答案偏好是什么", top_k=5)

# 注入上下文
context = vm.get_context_for_llm("答案偏好", max_tokens=500)
```

**L1/L2/L3架构:**
```
查询 → L1热状态(重要性≥0.7) → L2语义(0.3-0.7) → L3情景(<0.3)
                        ↓
                   向量检索(节省51-72% Token)
```

#### 模块4: A2A协议 (`a2a_protocol.py`)

```python
from a2a_protocol import A2AProtocol, A2ANetwork

# Agent端
protocol = A2AProtocol("miner", "Miner", "literature")
protocol.register_capability(
    name="literature_search",
    description="搜索学术论文",
    keywords=["论文", "paper", "search"]
)

# 创建任务请求
msg = protocol.create_task_request(
    receiver_id="assayer",
    action="verify_entry",
    parameters={"entry": "..."}
)

# 网络管理
network = get_a2a_network()
network.register(protocol)
network.send_message(message)
```

### 3.2 代码Diff

#### 新增文件列表

| 文件 | 行数 | 功能 |
|------|------|------|
| `circuit_breaker.py` | 280+ | 熔断器模式 |
| `dead_letter_queue.py` | 380+ | 死信队列 |
| `vector_memory.py` | 400+ | 三层向量记忆 |
| `a2a_protocol.py` | 450+ | A2A通信协议 |

---

## 四、架构对比图

### 优化前 (v3.0)
```
┌─────────────────────────────────────────────────────────┐
│                      BaseAgent                          │
│  • 简单对话历史(固定50条截断)                            │
│  • 基础重试(429指数退避)                                 │
│  • 无工具调用框架                                       │
│  • 简单logging                                          │
└─────────────────────────────────────────────────────────┘
```

### 优化后 (v3.1)
```
┌──────────────────────────────────────────────────────────────────┐
│                         BaseAgent v3.1                            │
│  ┌────────────────┐  ┌────────────────┐  ┌────────────────┐       │
│  │ CircuitBreaker │  │  DeadLetterQ   │  │ VectorMemory   │       │
│  │  熔断器模式     │  │  死信队列      │  │  L1/L2/L3记忆  │       │
│  └────────────────┘  └────────────────┘  └────────────────┘       │
│  ┌────────────────┐  ┌────────────────┐  ┌────────────────┐       │
│  │  A2AProtocol   │  │  TaskOrchestr  │  │   Observabil.  │       │
│  │  Agent间通信   │  │  DAG工作流     │  │   OTel追踪     │       │
│  └────────────────┘  └────────────────┘  └────────────────┘       │
└──────────────────────────────────────────────────────────────────┘
                              │
┌──────────────────────────────────────────────────────────────────┐
│  ┌─────────────────────────────────────────────────────────────┐  │
│  │                    Knowledge Base (知识库)                    │  │
│  │  7个建材领域MD + 向量检索 → 相关记忆注入                     │  │
│  └─────────────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────────┘
```

---

## 五、模块集成建议

### 5.1 熔断器集成到BaseAgent

```python
# 在base_agent.py中集成熔断器
from circuit_breaker import get_circuit_breaker, CircuitBreakerConfig

class BaseAgent:
    def __init__(self, name, ...):
        # API熔断器
        self.api_circuit = get_circuit_breaker(
            f"{name}_api",
            CircuitBreakerConfig(failure_threshold=5)
        )
    
    def chat(self, user_input: str, ...):
        with self.api_circuit:
            return self._call_api(...)
```

### 5.2 死信队列集成到Orchestrator

```python
# 在orchestrator.py中集成DLQ
from dead_letter_queue import get_dlq

class TaskOrchestrator:
    def __init__(self, ...):
        self.dlq = get_dlq()
    
    def execute(self, ...):
        try:
            result = self._execute_task(task)
        except Exception as e:
            # 失败任务入队
            self.dlq.submit(
                task_id=task.name,
                payload=task.params,
                error=e,
                error_type=type(e).__name__
            )
```

### 5.3 向量记忆集成到Agent

```python
# 在具体Agent中集成向量记忆
from vector_memory import get_vector_memory

class MinerAgent(BaseAgent):
    def __init__(self, ...):
        super().__init__(...)
        self.memory = get_vector_memory()
    
    def search_papers(self, keywords: str, ...):
        # 检索相关记忆
        context = self.memory.get_context_for_llm(keywords)
        
        # 构建提示
        prompt = f"{context}\n\n{keywords}"
        return self.chat(prompt)
```

---

## 六、测试验证

### 6.1 新模块测试

```bash
cd ./xuanshu-agents

# 测试熔断器
python -c "
from circuit_breaker import CircuitBreaker, CircuitState
cb = CircuitBreaker('test', failure_threshold=2)
print('Initial state:', cb.state)
cb.record_failure(Exception('test'))
cb.record_failure(Exception('test'))
print('After 2 failures:', cb.state)
"

# 测试死信队列
python -c "
from dead_letter_queue import get_dlq
dlq = get_dlq()
dlq.submit('t1', {'data': 'test'}, Exception('timeout'))
print('DLQ stats:', dlq.get_stats())
"

# 测试向量记忆
python -c "
from vector_memory import get_vector_memory
vm = get_vector_memory()
vm.add('测试记忆', importance=0.8)
results = vm.retrieve('测试')
print('Found:', len(results), 'entries')
"

# 测试A2A协议
python -c "
from a2a_protocol import A2AProtocol
p = A2AProtocol('test', 'Test')
p.register_capability('test_action', '测试动作')
cap = p.find_capability('测试')
print('Found capability:', cap.name if cap else None)
"
```

### 6.2 完整测试

```bash
cd ./xuanshu-agents
python test_all.py
```

---

## 七、备份与GitHub同步

### 7.1 备份位置
- `./xuanshu-agents/archive/20260601_backup/`
- 包含: base_agent.py, checkpoint.py, handoff.py, memory.py, observability.py, orchestrator.py, mcp_client.py, config.py

### 7.2 新增模块
- `./xuanshu-agents/circuit_breaker.py` (新增)
- `./xuanshu-agents/dead_letter_queue.py` (新增)
- `./xuanshu-agents/vector_memory.py` (新增)
- `./xuanshu-agents/a2a_protocol.py` (新增)

### 7.3 GitHub推送状态
待验证测试后推送至 `tsingxuanhan/xuan-hub` (private)

---

## 八、后续优化计划

| 优先级 | 优化项 | 预计工时 | 依赖 |
|--------|--------|---------|------|
| P1 | 向量数据库部署(Chroma/Qdrant) | 2h | Docker |
| P1 | BaseAgent集成熔断器+DLQ | 1h | circuit_breaker, dlq |
| P2 | Agent能力注册到A2A网络 | 2h | a2a_protocol |
| P2 | 向量记忆注入到4个Agent | 2h | vector_memory |
| P3 | MCP+A2A协议桥接 | 3h | mcp_client |

---

## 九、结论

本次优化紧跟行业趋势，新增4个关键模块：

1. **熔断器模式** - 防止级联故障，与OpenClaw最佳实践一致
2. **死信队列** - 失败任务持久化与自动重试，与Supergood方案对齐
3. **三层向量记忆** - L1/L2/L3架构，预计节省51-72% Token
4. **A2A协议** - Agent间标准化通信，向Microsoft Agent Framework看齐

**建议下一步:** 部署向量数据库，将vector_memory从简单嵌入升级到ChromaDB/Qdrant，实现真正的语义检索。

---

*报告生成: 炉守 @ 2026-06-01*
