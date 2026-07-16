# xuanshu-agents v4.0 AGI Evolution Plan

> 从领域专用协作框架 → 通用自主智能体系统
> 预算：190K 积分 | 周期：5个阶段 | API：DeepSeek PRO(推理) + Flash(验证/轻量)
> 修订：v2 — 整合2026年5-6月开源项目调研修正

---

## 现状诊断

| 维度 | 当前 v3.3.0 | 目标 v4.0 | Gap |
|------|-------------|-----------|-----|
| Agent角色 | 4个建材领域固定角色 | 动态角色分配，通用能力 | 🔴 强领域绑定 |
| 规划能力 | ReAct单步循环 | TeLLAgent双Agent分离 + 层次化任务分解 | 🔴 无规划器 |
| 记忆系统 | 向量库空(0条)，NGram TF-IDF | Letta三层OS式 + 4类Agentic Memory | 🔴 落后一代 |
| 工具生态 | base_tool.py(290行)，无实际工具 | CodeAct优先 + MCP 2.0 + 14K生态接入 | 🔴 无工具+隔绝生态 |
| 知识库 | 9篇建材文档(~2700行) | 10+领域，100+文档，50K+条目 | 🟠 极度偏科 |
| 自学习 | 无反馈循环 | Sleeptime离线整理 + 经验→规则→能力 | 🔴 无进化机制 |
| 自主性 | 被动响应 | 自主目标分解 + 迭代精化 + 自我修正 | 🔴 纯被动 |

**核心结论**：v3.3.0 是一个"有骨架没血肉"的框架——架构设计到位（Guardrails/Quality/A2A/MCP），但所有能力层都是空壳。升级重点不是加新模块，而是**填满现有骨架 + 补齐缺失的规划层和进化层**。

**v2修正要点**（基于2026年5-6月开源项目调研）：
1. ~~BaseTool JSON Schema为主~~ → **CodeAct（代码执行）为主**，JSON Schema降级为兼容层
2. ~~简单4类记忆分类~~ → **Letta三层OS式记忆（Core/Archival/Recall）** + Sleeptime离线整理
3. ~~单PlannerAgent~~ → **TeLLAgent双Agent分离**：StrategyAgent(PRO) + ExecutionAgent(Flash)

---

## 行业对标（2026年5-6月调研）

### 第一梯队：直接影响架构设计

| 项目/框架 | 核心启发 | 我们的行动 |
|-----------|---------|-----------|
| **TeLLAgent** | 双Agent分离：StrategyAgent做策略推理，ExecutionAgent做精确执行，超越GPT-5 | → Phase 2: PlannerAgent(PRO策略) + ExecutorAgent(Flash执行) |
| **OpenHands / CodeAct** | 用Python代码替代JSON工具调用，成为2026年行动空间主流范式 | → Phase 3: CodeExec优先于BaseTool JSON |
| **Letta** (ex-MemGPT) | 三层OS式记忆：Core(上下文)/Archival(持久存储)/Recall(检索)，最成熟 | → Phase 4: 记忆底座对标Letta |
| **Microsoft Agent Framework 1.0** (2026.4 GA) | Agent Harness: 上下文压缩、FileMemory、TodoProvider、plan/execute模式 | → Phase 1: plan/execute + ContextCompactor + TodoProvider |
| **MCP 2026-07协议** | 无状态化大改、14K+服务器、97M月下载、Tasks原语 | → Phase 3: 接入MCP生态是P0 |
| **A2A v1.0** (Google) | 150+组织支持，Agent↔Agent标准，与MCP互补 | → Phase 3: A2A用于跨框架协作 |

### 第二梯队：能力参考

| 项目/框架 | 核心启发 | 我们的行动 |
|-----------|---------|-----------|
| **sleeptime_agent** | "做梦"机制：离线时整理记忆、提取规则、修剪冗余 | → Phase 4: Sleeptime Consolidation |
| **CAMEL-AI / OWL** | GAIA基准69.09%（开源#1），角色编排范式 | → Phase 2: 角色编排参考 |
| **Mem0** (51.8K⭐) | 混合存储(向量+图+KV)，生态最大 | → Phase 4: 图存储参考 |
| **Agno 2.0** (ex-phidata) | 轻量Agent类 + AgentOS生产运行时(FastAPI) | → Phase 5: AgentOS运行时 |
| **Magentic-One** | 通用多Agent系统，Orchestrator+ Specialists | → Phase 2: Orchestrator模式 |
| **Google Agentic RAG** | 多Agent迭代检索 + 充分上下文验证，准确率+34% | → Phase 4: 多跳RAG |
| **D-MEM / CraniMem** | 仿生记忆：多巴胺门控、大脑模拟 | → Phase 4: 遗忘/衰减机制参考 |

### xuanshu-agents v3.3.0 关键差距（调研结论）

| 优先级 | 差距 | 影响 |
|--------|------|------|
| **P0** | 缺MCP协议 | 隔绝14K+工具生态，无法与任何主流框架互操作 |
| **P0** | 记忆架构落后一代 | NGram TF-IDF vs Letta三层OS式，检索质量差距大 |
| **P1** | 缺A2A协议 | 无法跨框架协作，Agent只能内部通信 |
| **P1** | 缺CodeAct行动空间 | JSON工具调用无法表达复杂逻辑，限制Agent能力上限 |
| **P2** | 无AgentOS部署层 | 无沙箱/REST API/可观测性 |
| **P2** | 固定4-Agent角色 | 无法动态创建/销毁Agent |

---

## Phase 1: 泛化基建 (Generalization Foundation)

**目标**：从建材领域框架 → 通用Agent框架  
**积分**：~15K | **耗时**：2天

### 1.1 Agent角色泛化

当前4个Agent全部绑定建材领域，需要拆成**角色+领域**双层：

```python
# v3.3: 固定角色+固定领域
Miner = "文献挖掘专家" + "低碳建材"
Caster = "代码生成专家" + "Python/Docker"

# v4.0: 角色与领域解耦
class AgentRole(Enum):
    PLANNER = "planner"      # 规划：分解任务，策略推理（PRO模型）
    RESEARCHER = "researcher"  # 研究：检索、挖掘、验证
    EXECUTOR = "executor"     # 执行：代码、脚本、工具调用（Flash模型）
    REVIEWER = "reviewer"     # 审查：验证、质控、反馈

class DomainProfile:
    """可插拔领域配置 — 领域与角色正交"""
    name: str
    knowledge_dirs: List[str]
    system_prompt_template: str
    validation_rules: List[str]
    preferred_tools: List[str]  # 该领域优先使用的工具
```

**TeLLAgent双Agent分离**（v2修正）：Planner用PRO做策略推理，Executor用Flash做精确执行，两个模型各司其职。

### 1.2 Plan/Execute/Reflect 三模式

借鉴 MAF AgentModeProvider + TeLLAgent双Agent分离：

```python
class AgentMode(Enum):
    PLAN = "plan"       # 策略推理模式（PRO模型）— 只规划不执行
    EXECUTE = "execute"  # 精确执行模式（Flash模型）— 按计划逐步执行
    REFLECT = "reflect"  # 反思模式（PRO模型）— 评估结果，修正计划

# TeLLAgent核心思路：策略和执行用不同模型
agent.set_mode("plan")     # 切换到PRO
plan = agent.chat("设计一个AI辅助材料发现系统")  # 输出策略分解

agent.set_mode("execute")  # 切换到Flash
result = agent.chat("执行步骤3：实现SSC配方预测模型")  # 精确执行

agent.set_mode("reflect")  # 切换到PRO
review = agent.chat("步骤3的执行结果是否达到预期？")  # 反思评估
```

### 1.3 上下文压缩

借鉴 MAF Agent Harness 的自动上下文压缩，防止长工具链耗尽token：

```python
class ContextCompactor:
    """监控token使用，超阈值自动摘要（用Flash模型压缩）"""
    def check_and_compact(self, messages: List[Dict]) -> List[Dict]:
        if self.token_count(messages) > self.threshold * 0.8:
            # 用flash模型压缩历史（成本低，摘要质量够用）
            summary = self._summarize(messages[:-4])  # 保留最近4轮
            return [{"role": "system", "content": f"[历史摘要]\n{summary}"}] + messages[-4:]
        return messages
```

### 1.4 TodoProvider

内置任务追踪，让Agent知道自己还有什么没做：

```python
class TodoProvider:
    def add(self, task: str, priority: int = 0): ...
    def complete(self, task_id: str): ...
    def get_pending(self) -> List[TodoItem]: ...
    def to_context(self) -> str:
        """生成可注入system prompt的待办列表"""
```

### 交付物
- `agents/` 重写：4个泛化Agent + DomainProfile
- `base_agent.py` 升级：plan/execute/reflect模式(含PRO/Flash切换) + ContextCompactor + TodoProvider
- `config.py` 新增领域注册表
- 向后兼容：建材领域作为默认DomainProfile

---

## Phase 2: 规划引擎 (Planning Engine)

**目标**：从被动ReAct循环 → TeLLAgent双Agent分离 + 主动层次化规划  
**积分**：~25K | **耗时**：3天

### 2.1 双Agent分离架构（v2修正）

借鉴TeLLAgent，规划与执行用不同模型和不同策略：

```python
class StrategyAgent(BaseAgent):
    """策略Agent — 用PRO模型做深度推理"""
    model = "pro"
    
    def decompose(self, goal: str) -> TaskTree:
        """将高层目标分解为任务树（深度推理）"""
        
    def select_strategy(self, task: Task) -> str:
        """选择执行策略：sequential/parallel/iterative/codeact"""
        
    def evaluate_execution(self, result: Any, expectation: str) -> float:
        """评估执行结果是否符合策略预期"""

class ExecutionAgent(BaseAgent):
    """执行Agent — 用Flash模型做精确执行"""
    model = "flash"
    
    def execute_step(self, step: TaskNode) -> Any:
        """精确执行单个步骤"""
        
    def generate_code(self, description: str) -> str:
        """生成执行代码（CodeAct风格）"""
        
    def call_tool(self, tool_name: str, params: Dict) -> ToolResult:
        """调用工具"""
```

**为什么双Agent分离比单Agent更好**：
- PRO擅长策略但不擅长精确执行（贵+慢）
- Flash擅长精确执行但不擅长策略（便宜+快）
- 分离后每个Agent的system prompt更聚焦，幻觉更少
- TeLLAgent已验证：分离策略后超越GPT-5

### 2.2 任务树 (TaskTree)

```python
@dataclass
class TaskNode:
    id: str
    description: str
    status: Literal["pending", "running", "done", "failed", "blocked"]
    assigned_agent: Optional[str]
    assigned_model: Literal["pro", "flash"]  # v2: 明确指定用哪个模型
    action_type: Literal["plan", "execute", "codeact", "tool_call"]  # v2: 行动类型
    dependencies: List[str]
    result: Optional[Any]
    subtasks: List["TaskNode"]
    
class TaskTree:
    root: TaskNode
    
    def next_ready(self) -> List[TaskNode]:
        """返回所有依赖已完成、可立即执行的任务"""
        
    def critical_path(self) -> List[TaskNode]:
        """关键路径 — 决定总耗时"""
        
    def to_prompt(self) -> str:
        """序列化为可注入prompt的任务树描述"""
```

### 2.3 ToT/GoT 推理

对复杂问题，不只是ReAct，而是生成多棵推理树择优：

```python
class TreeOfThought:
    """Tree of Thought推理"""
    
    def generate_branches(self, state: str, n: int = 3) -> List[str]:
        """从当前状态生成n个候选推理方向（用PRO）"""
        
    def evaluate(self, branches: List[str]) -> List[float]:
        """用Flash评估每个方向的可行性"""
        
    def search(self, problem: str, max_depth: int = 3) -> str:
        """BFS/DFS搜索最优推理路径"""
```

### 2.4 反思循环

每次执行后强制反思，这是自主进化的关键：

```python
class ReflectionLoop:
    def reflect(self, plan: TaskTree, results: Dict) -> Reflection:
        """反思：什么做对了？什么做错了？下次怎么改？（PRO模型）"""
        # 1. 结果与预期对比
        # 2. 识别偏差和错误
        # 3. 提取经验规则
        # 4. 更新procedural memory
        
    def should_replan(self, reflection: Reflection) -> bool:
        """是否需要重规划"""
        
    def replan(self, tree: TaskTree, failed_node: str, reflection: Reflection) -> TaskTree:
        """局部重规划 — 不重新分解整棵树"""
```

### 交付物
- `planner.py`: StrategyAgent + ExecutionAgent + TaskTree + ToT
- `reflection.py`: ReflectionLoop
- `base_agent.py` 集成：plan_mode → StrategyAgent.decompose → ExecutionAgent.execute → reflect
- 测试：3个多步推理案例（含双Agent协作验证）

---

## Phase 3: 工具生态 — CodeAct优先 (Tool Ecosystem)

**目标**：从0个工具 → CodeAct行动空间 + MCP 2.0 + 14K生态接入  
**积分**：~30K | **耗时**：3天

### 3.0 CodeAct范式（v2核心修正）

**旧方案**：BaseTool JSON Schema为主 → 每个工具定义参数JSON → LLM生成JSON调用
**新方案**：CodeExec为主 → LLM直接写Python代码执行 → BaseTool降级为兼容层

**为什么CodeAct更好**（OpenHands/LangGraph已验证）：
- JSON Schema只能表达简单参数，无法表达复杂逻辑
- Python代码是图灵完备的，可以组合多个操作、加条件判断、处理异常
- DeepSeek PRO的代码能力极强，CodeExec比JSON工具调用更自然
- 实测：CodeAct在SWE-Bench上比JSON工具调用高15-20%

```python
class CodeActExecutor:
    """CodeAct行动空间 — Agent通过写代码而非调工具"""
    
    def execute(self, code: str, sandbox: bool = True) -> CodeActResult:
        """执行Agent生成的Python代码"""
        # 1. Guardrails检查：禁止import os.system/subprocess等危险操作
        # 2. 沙箱执行：受限环境，超时15秒
        # 3. 返回 stdout/stderr/return_value
        
    def available_globals(self) -> Dict:
        """注入到执行环境的预定义对象"""
        return {
            "search": web_search,        # 搜索函数
            "read_file": file_read,       # 文件读取
            "write_file": file_write,     # 文件写入
            "http_get": http_get,         # HTTP请求
            "query_data": data_query,     # 数据查询
            "calculate": calculator,      # 数学计算
        }
```

**对比**：
```python
# 旧方案：JSON工具调用
tool_call("web_search", {"query": "SSC cement", "limit": 5})
tool_call("data_query", {"file": "data.csv", "filter": "year > 2020"})

# 新方案：CodeAct — Agent直接写代码
results = search("SSC cement", limit=5)
recent = query_data("data.csv", filter=lambda r: r.year > 2020)
combined = [r for r in results if r.cited_by > 10]
write_file("output.md", format_results(combined))
```

### 3.1 内置工具集（兼容层 + CodeAct globals）

| 工具 | 类名 | CodeAct全局名 | 用途 | 优先级 |
|------|------|--------------|------|--------|
| CodeExec | `tools/code_exec.py` | — | **沙箱代码执行（核心）** | P0 |
| WebSearch | `tools/web_search.py` | `search` | 联网搜索 | P0 |
| FileOps | `tools/file_ops.py` | `read_file/write_file` | 文件读写 | P0 |
| DataQuery | `tools/data_query.py` | `query_data` | 结构化数据查询 | P1 |
| APICaller | `tools/api_caller.py` | `http_get/http_post` | 通用HTTP请求 | P1 |
| BrowserControl | `tools/browser.py` | `browse` | 浏览器自动化 | P1 |
| Calculator | `tools/calculator.py` | `calculate` | 数学计算 | P2 |
| GitOps | `tools/git_ops.py` | `git_op` | Git操作 | P2 |
| PDFReader | `tools/pdf_reader.py` | `read_pdf` | PDF解析 | P2 |
| Scheduler | `tools/scheduler.py` | `schedule` | 定时任务 | P2 |

**双重接口**：每个工具同时支持BaseTool JSON调用和CodeAct全局函数，前者兼容外部框架，后者供内部Agent使用。

### 3.2 MCP 2.0 升级（P0 — 接入14K生态）

```python
class MCPClientV2(MCPClient):
    """MCP 2026-07协议: 无状态化 + Tasks原语 + 动态发现 + Authorization"""
    
    def discover_tools(self, registry_url: str = "https://registry.modelcontextprotocol.io") -> List[MCPResource]:
        """从MCP Registry动态发现可用工具（14K+服务器）"""
        
    def create_task(self, description: str) -> MCPTask:
        """MCP 2.0 Tasks原语 — 长时任务"""
        
    def with_auth(self, oauth_config: Dict) -> "MCPClientV2":
        """OAuth 2.0认证"""
        
    def to_codeact_globals(self) -> Dict:
        """将MCP工具映射为CodeAct全局函数"""
        # MCP tool "sql_query" → codeact global mcp_sql_query
```

### 3.3 MCP Server模式

让xuanshu-agents自己也作为MCP Server，被其他Agent/框架调用：

```python
class XuanshuMCPServer:
    """将xuanshu-agents的能力暴露为MCP Server"""
    
    tools = [
        "research_topic",    # 研究能力 → 文献挖掘
        "verify_claim",      # 审查能力 → 交叉验证
        "generate_code",     # 执行能力 → 代码生成
        "answer_question",   # 问答能力 → 领域问答
        "plan_task",         # 规划能力 → 任务分解（v2新增）
    ]
```

### 3.4 A2A v1.0 集成

```python
class A2AGateway:
    """A2A v1.0网关 — 跨框架Agent协作"""
    
    def register_agent(self, agent_info: AgentInfo) -> str:
        """注册到A2A网络"""
        
    def discover_agents(self, capability: str) -> List[AgentInfo]:
        """发现具有指定能力的其他Agent"""
        
    def delegate_task(self, agent_id: str, task: A2ATask) -> A2AResult:
        """将任务委托给其他框架的Agent"""
```

### 3.5 ToolRegistry

```python
class ToolRegistry:
    """运行时工具注册与发现 — 同时管理本地工具和MCP远程工具"""
    
    def register(self, tool: BaseTool): ...
    def register_mcp(self, mcp_server: str): ...
    def discover(self, capability: str) -> List[Union[BaseTool, MCPResource]]: ...
    def execute(self, tool_name: str, params: Dict, guardrails=True) -> ToolResult:
        """统一执行入口 — 带Guardrail检查"""
    def to_codeact_globals(self) -> Dict:
        """导出所有工具为CodeAct全局函数"""
```

### 交付物
- `code_exec.py`: CodeAct沙箱执行器（核心）
- `tools/` 目录：10+工具实现（双重接口）
- `tool_registry.py`: 工具注册中心
- `mcp_client.py` 升级到2026-07协议
- `mcp_server.py`: MCP Server模式
- `a2a_gateway.py`: A2A v1.0网关
- 测试：CodeAct端到端 + MCP工具发现 + A2A跨框架调用

---

## Phase 4: 知识与记忆进化 — Letta三层架构 (Knowledge & Memory Evolution)

**目标**：从0条记忆+9篇文档 → Letta三层OS式记忆 + 10领域知识库  
**积分**：~60K | **耗时**：5天

### 4.1 Letta三层OS式记忆（v2核心修正）

```
┌─────────────────────────────────────────────────────────┐
│                  Memory Manager (核心)                    │
│                                                         │
│  ┌─────────────────────────────────────────────────┐   │
│  │  Core Memory (核心层) — 类似CPU寄存器             │   │
│  │  • 当前对话上下文 + 用户画像 + Agent状态          │   │
│  │  • 直接注入system prompt，无需检索               │   │
│  │  • 容量小(~4K tokens)，但延迟为0                  │   │
│  │  • 存储: base_agent.py内存                       │   │
│  └─────────────────────────────────────────────────┘   │
│                                                         │
│  ┌─────────────────────────────────────────────────┐   │
│  │  Archival Memory (归档层) — 类似硬盘              │   │
│  │  • 持久事实、概念、关系、知识库                   │   │
│  │  • 向量+关键词混合检索                           │   │
│  │  • 容量大(无上限)，但需要检索                     │   │
│  │  • 存储: JSON文件 + NGram TF-IDF索引              │   │
│  │  • 对标: Semantic Memory + 知识库                 │   │
│  └─────────────────────────────────────────────────┘   │
│                                                         │
│  ┌─────────────────────────────────────────────────┐   │
│  │  Recall Memory (回忆层) — 类似情景记忆            │   │
│  │  • 时间戳事件、交互记录、经验情节                 │   │
│  │  • 时序+相关性检索                               │   │
│  │  • 可衰减遗忘（D-MEM多巴胺门控）                  │   │
│  │  • 存储: JSON文件 + 时序索引                      │   │
│  │  • 对标: Episodic Memory + Procedural Memory      │   │
│  └─────────────────────────────────────────────────┘   │
│                                                         │
│  ┌─────────────────────────────────────────────────┐   │
│  │  Sleeptime Engine (离线整理) — v2新增              │   │
│  │  • Agent空闲时自动"做梦"：整理记忆、提取规则       │   │
│  │  • Recall → patterns → procedural rules           │   │
│  │  • 修剪冗余、合并相似、遗忘过时                   │   │
│  │  • 用Flash模型执行（成本低）                       │   │
│  └─────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────┘
```

**Letta三层 vs 我们原来的4类映射**：

| Letta层 | 对应v1分类 | 新定位 |
|---------|-----------|--------|
| **Core** | Working Memory | 直接注入prompt的当前上下文 |
| **Archival** | Semantic Memory | 持久知识 + RAG检索 |
| **Recall** | Episodic + Procedural | 经验情节 + 行为规则 + 可遗忘 |

**为什么Letta三层比4类分类更好**：
- 4类是学术分类，3层是工程实现，更易落地
- Letta已在生产环境验证（ex-MemGPT，10K+⭐）
- Core/Archival/Recall直接对应"读什么/存什么/想什么"
- Sleeptime Engine是4类分类没有的关键能力

### 4.2 Sleeptime Engine — 离线"做梦"（v2新增）

借鉴sleeptime_agent，Agent空闲时自动整理记忆：

```python
class SleeptimeEngine:
    """Agent空闲时的离线整理 — 让记忆持续进化"""
    
    def dream(self, memory_manager: MemoryManager):
        """定期执行（如每小时或Agent空闲时）"""
        # Phase 1: 回忆整理
        episodes = memory_manager.recall.get_recent(hours=24)
        patterns = self.extract_patterns(episodes)  # Flash模型
        
        # Phase 2: 规则提炼
        rules = self.generalize(patterns)  # Flash模型
        conflicts = memory_manager.detect_conflicts(rules)
        resolved = self.resolve_conflicts(conflicts)  # PRO模型（少量）
        
        # Phase 3: 记忆修剪（D-MEM多巴胺门控）
        self.decay_memories(memory_manager.recall, 
                           dopamine_threshold=0.3)  # 重要性<0.3的衰减
        
        # Phase 4: Core Memory更新
        self.update_core(memory_manager, rules)
        
    def extract_patterns(self, episodes: List[Episode]) -> List[Pattern]:
        """从情节中提取重复模式"""
        
    def generalize(self, patterns: List[Pattern]) -> List[Rule]:
        """将模式泛化为可复用规则"""
        # "当用户问X类问题时，用Y策略更有效"
        
    def decay_memories(self, recall: RecallMemory, dopamine_threshold: float):
        """仿生遗忘 — 低重要性记忆逐渐衰减"""
        # 借鉴D-MEM：多巴胺信号决定记忆保留/遗忘
        # 高重要性(>0.7) → 永久保留
        # 中重要性(0.3-0.7) → 保留但降权
        # 低重要性(<0.3) → 标记为可遗忘，定期清理
```

### 4.3 Core Memory — 直接注入Prompt

```python
@dataclass
class CoreMemory:
    """核心记忆 — 直接注入system prompt，无需检索"""
    user_profile: Dict[str, Any]     # 用户画像
    agent_state: Dict[str, Any]      # Agent当前状态
    active_context: str              # 当前任务上下文
    procedural_rules: List[str]      # 从Sleeptime提炼的行为规则
    
    def to_system_prompt(self) -> str:
        """序列化为system prompt片段"""
        
    def update(self, key: str, value: Any):
        """运行时更新（无需检索，直接修改）"""
```

### 4.4 Archival Memory — 向量+关键词混合检索

```python
class ArchivalMemory:
    """归档记忆 — 持久知识，需要检索"""
    
    def __init__(self):
        self.index = NGramTFIDFProvider()  # 已有，复用
        self.documents = {}  # 文档存储
        self.metadata = {}   # 元数据
        
    def store(self, content: str, metadata: Dict = None):
        """存储知识（自动索引）"""
        
    def search(self, query: str, top_k: int = 5) -> List[SearchResult]:
        """混合检索（RRF融合）"""
        # 已有hybrid_retrieve，复用
        
    def search_multi_hop(self, query: str, max_hops: int = 3) -> List[SearchResult]:
        """多跳检索 — 自动追踪引用链"""
        # 借鉴Google Agentic RAG
```

### 4.5 多领域知识库扩展

从9篇建材文档 → 10+领域覆盖：

| 领域 | 文档数 | 优先级 | 来源 |
|------|--------|--------|------|
| 材料科学 | 15+ | P0 | 已有+DeepSeek生成 |
| AI/ML | 20+ | P0 | 搜索+整理 |
| 计算机科学 | 15+ | P0 | 搜索+整理 |
| 数学/统计 | 10+ | P1 | 公式+概念 |
| 物理学 | 10+ | P1 | 基础+前沿 |
| 生物学 | 8+ | P2 | 基础概念 |
| 经济学 | 8+ | P2 | 基础+行为 |
| 法律 | 5+ | P2 | AI相关法规 |
| 心理学 | 5+ | P2 | 认知+决策 |
| 历史/哲学 | 5+ | P2 | 思想史 |

**知识生成流程**（CodeAct风格）：
```python
# Agent用CodeAct自动生成知识
code = """
results = search("LC3 cement latest research 2024-2026", limit=10)
papers = [extract_paper(r) for r in results]
verified = [p for p in papers if verify_citation(p.doi)]
write_file("knowledge/materials/lc3-latest.md", format_kb(verified))
"""
executor.execute(code)
```

### 4.6 多跳RAG

借鉴 Google Agentic RAG，支持跨文档/跨领域推理：

```python
class MultiHopRAG:
    """多跳检索 — 自动追踪引用链"""
    
    def retrieve(self, query: str, max_hops: int = 3) -> List[RetrievalResult]:
        """
        Q: "SSC的纳米改性对混凝土耐久性的影响"
        Hop1: Archival检索SSC纳米改性 → 发现"孔结构优化"
        Hop2: 检索"孔结构优化→耐久性" → 碳化深度降低30%
        Hop3: 交叉验证碳化深度数据
        """
    
    def with_sufficient_context_check(self, results: List) -> bool:
        """Google Agentic RAG关键创新：验证上下文是否充分"""
        # 不充分 → 继续检索；充分 → 停止
```

### 交付物
- `memory_manager.py`: Letta三层记忆统一管理
- `core_memory.py`: Core Memory（直接注入prompt）
- `archival_memory.py`: Archival Memory（向量检索）
- `recall_memory.py`: Recall Memory（时序+衰减）
- `sleeptime.py`: Sleeptime Engine（离线"做梦"）
- `multi_hop_rag.py`: 多跳检索
- `knowledge/`: 10+领域，100+文档
- `data/`: 三层记忆全部populated
- 测试：记忆存取、遗忘衰减、冲突解决、多跳检索、Sleeptime整理

---

## Phase 5: AGI核心能力 (AGI Capabilities)

**目标**：从工具框架 → 自主智能体  
**积分**：~60K | **耗时**：5天

### 5.1 自主目标分解

Agent收到高层目标后，不再需要逐步指令：

```python
class AutonomousGoalHandler:
    def handle(self, goal: str) -> ExecutionResult:
        """
        输入: "帮我调研2026年最有潜力的3个AI Agent框架"
        
        自动执行（TeLLAgent双Agent分离）:
        1. StrategyAgent(PRO).decompose → 5个子任务的任务树
        2. StrategyAgent分配: Researcher×3(并行) + Executor(整理)
        3. ExecutionAgent(Flash).execute_step → 逐步执行
        4. StrategyAgent(PRO).evaluate_execution → 验证结果
        5. ReflectionLoop.reflect → 提取经验
        6. SleeptimeEngine.consolidate → 更新规则
        7. 返回结构化报告
        """
```

### 5.2 跨领域知识迁移

```python
class CrossDomainTransfer:
    """将A领域的经验迁移到B领域"""
    
    def find_analogy(self, source_domain: str, target_domain: str) -> List[Analogy]:
        """找领域间的类比关系（PRO模型）"""
        # "材料相变" ↔ "神经网络相变"
        # "晶体缺陷工程" ↔ "对抗样本防御"
        # "复合材料界面" ↔ "多Agent协作接口"
        
    def transfer_rule(self, rule: Rule, analogy: Analogy) -> Rule:
        """通过类比迁移规则"""
```

### 5.3 元认知 (Meta-Cognition)

Agent知道自己"知道什么"和"不知道什么"：

```python
class MetaCognition:
    def assess_confidence(self, query: str) -> ConfidenceAssessment:
        """评估自己对某个问题的置信度"""
        # 1. 检查Archival Memory中的相关知识量
        # 2. 检查Recall Memory中的相关经验
        # 3. 检查Procedural Rules中的相关规则
        # → 高置信(>0.8) → 直接回答
        # → 中置信(0.4-0.8) → 回答+标注不确定性+建议搜索
        # → 低置信(<0.4) → 主动搜索/求助/触发学习
        
    def identify_knowledge_gaps(self) -> List[str]:
        """识别自己的知识盲区 — 基于Archival Memory覆盖率分析"""
        
    def self_improve(self, gap: str):
        """针对盲区主动学习 — 生成搜索+整理的CodeAct代码"""
```

### 5.4 持续学习管道

```python
class ContinuousLearningPipeline:
    """持续学习 — 每次交互都在进步"""
    
    def on_interaction(self, interaction: Interaction):
        """每次交互后"""
        # 1. 存入Recall Memory
        # 2. 更新Core Memory（用户偏好、任务状态）
        # 3. 如果效果差 → 标记为negative episode
        # 4. 如果效果好 → 标记为positive episode
        # 5. Sleeptime Engine会在空闲时自动consolidate
        
    def on_periodic(self):
        """Sleeptime Engine定期执行"""
        # 1. Consolidation: recall episodes → patterns → rules → core/procedural
        # 2. Decay: D-MEM多巴胺门控 → 低重要性记忆衰减
        # 3. Conflict resolution: 规则冲突检测和解决
        # 4. Archival reindex: 新知识重新索引
        # 5. Knowledge graph update: 跨领域关系更新
```

### 5.5 AgentOS运行时

借鉴 Agno AgentOS + MCP Server，加一个FastAPI生产运行时层：

```python
# agentos.py
app = FastAPI(title="xuanshu-agents AgentOS")

# 对话接口
@app.post("/chat")
async def chat(request: ChatRequest): ...

# 异步任务（支持CodeAct）
@app.post("/task")
async def submit_task(request: TaskRequest): ...

@app.get("/task/{task_id}")
async def get_task_status(task_id: str): ...

# 记忆管理
@app.get("/memory/stats")
async def memory_stats(): ...

@app.post("/memory/core/update")
async def update_core_memory(request: CoreMemoryUpdate): ...

# 工具发现（MCP兼容）
@app.get("/tools")
async def list_tools(): ...

@app.post("/tools/{tool_name}/execute")
async def execute_tool(tool_name: str, request: ToolRequest): ...

# Sleeptime触发
@app.post("/sleeptime/dream")
async def trigger_dream(): ...

# 健康检查
@app.get("/health")
async def health_check(): ...
```

### 交付物
- `autonomous.py`: 自主目标处理器
- `meta_cognition.py`: 元认知模块
- `cross_domain.py`: 跨领域迁移
- `continuous_learning.py`: 持续学习管道
- `agentos.py`: FastAPI运行时
- 集成测试：端到端自主任务执行 + Sleeptime验证

---

## 积分预算

| 阶段 | PRO调用 | Flash调用 | 总积分 | 占比 |
|------|---------|-----------|--------|------|
| Phase 1 泛化基建 | ~8K | ~7K | 15K | 8% |
| Phase 2 规划引擎 | ~15K | ~10K | 25K | 13% |
| Phase 3 工具生态 | ~12K | ~18K | 30K | 16% |
| Phase 4 知识记忆 | ~25K | ~35K | 60K | 32% |
| Phase 5 AGI能力 | ~20K | ~40K | 60K | 32% |
| **合计** | **80K** | **110K** | **190K** | 100% |

**v2修正**：Flash比例从43%提升到58%，因为：
- CodeAct执行用Flash（精确执行不需要深度推理）
- Sleeptime Engine用Flash（整理和摘要足够）
- 知识提取用Flash（搜索+格式化为主）
- 只有策略推理、知识验证、冲突解决用PRO

### PRO vs Flash 分工原则（v2更新）

| 用途 | 模型 | 原因 |
|------|------|------|
| **策略推理** | PRO | TeLLAgent验证：策略需要深度推理 |
| **任务分解** | PRO | 需要理解全局和权衡 |
| **知识验证** | PRO | 准确性优先 |
| **冲突解决** | PRO | 需要判断力 |
| **精确执行** | Flash | TeLLAgent验证：执行不需要深度推理 |
| **CodeAct代码生成** | Flash | DeepSeek Flash代码能力足够 |
| **Sleeptime整理** | Flash | 摘要和整理不需要PRO |
| **搜索/提取** | Flash | 速度快，成本低 |
| **上下文压缩** | Flash | 摘要足够 |
| **知识格式化** | Flash | 简单转换 |

---

## 技术约束与应对

| 约束 | 影响 | 应对方案 |
|------|------|---------|
| RAM 3.8GB 无swap | 不能装ChromaDB/sentence-transformers | 继续用NGram TF-IDF + 优化索引 |
| HuggingFace不通 | 不能下载embedding模型 | DeepSeek API做embedding代理（CodeAct调用） |
| 无Docker | 服务隔离受限 | 纯Python进程管理 + CodeExec沙箱 |
| 云电脑可用 | 可以跑浏览器/代码执行 | CodeExec对接云电脑 |
| 云手机可用 | 可以做移动端操作 | mobile_use工具 |
| DeepSeek API | 推理和生成都靠它 | PRO/Flash + TeLLAgent分离优化成本 |

---

## 里程碑与验收标准

| 里程碑 | 时间 | 验收标准 |
|--------|------|---------|
| v4.0-alpha | Phase 1完成 | Agent角色泛化，plan/execute/reflect模式可用，PRO/Flash自动切换 |
| v4.0-beta | Phase 2+3完成 | TeLLAgent双Agent协作，CodeAct执行3+步任务，MCP接入5+工具 |
| v4.0-rc | Phase 4完成 | Letta三层记忆运行，Sleeptime自动整理，知识库10+领域 |
| v4.0 | Phase 5完成 | 自主执行复杂任务，经验自动提炼，AgentOS可部署 |

**终极验收**：给定一个模糊目标（如"调研X领域最新进展并生成报告"），系统无需任何进一步指令，自主完成：StrategyAgent分解 → ExecutionAgent执行CodeAct代码 → Reviewer验证 → Sleeptime提炼经验 → 返回结构化报告。

---

## 文件结构规划

```
xuanshu-agents/
├── base_agent.py          # 升级: +plan/execute/reflect + PRO/Flash切换 + ContextCompactor + TodoProvider
├── planner.py             # 新增: StrategyAgent(PRO) + ExecutionAgent(Flash) + TaskTree + ToT
├── reflection.py          # 新增: ReflectionLoop
├── meta_cognition.py      # 新增: 元认知模块
├── cross_domain.py        # 新增: 跨领域迁移
├── continuous_learning.py # 新增: 持续学习管道
├── memory_manager.py      # 新增: Letta三层记忆统一管理
├── core_memory.py         # 新增: Core Memory (直接注入prompt)
├── archival_memory.py     # 新增: Archival Memory (向量检索)
├── recall_memory.py       # 新增: Recall Memory (时序+衰减)
├── sleeptime.py           # 新增: Sleeptime Engine (离线"做梦")
├── consolidation.py       # 新增: 经验→规则提炼 (Sleeptime调用)
├── multi_hop_rag.py       # 新增: 多跳RAG
├── code_exec.py           # 新增: CodeAct沙箱执行器 (核心!)
├── tool_registry.py       # 新增: 工具注册中心 (含MCP远程工具)
├── agentos.py             # 新增: FastAPI运行时
├── vector_memory.py       # 升级: → ArchivalMemory底层，保留NGram TF-IDF
├── a2a_protocol.py        # 升级: +A2A v1.0 + hierarchical agent
├── a2a_gateway.py         # 新增: A2A v1.0跨框架网关
├── guardrails.py          # 升级: +CodeAct安全检查 + tool guardrails
├── quality.py             # 升级: +meta-cognition quality check
├── mcp_client.py          # 升级: MCP 2026-07协议
├── mcp_server.py          # 新增: MCP Server模式
├── config.py              # 升级: +领域注册表 + Letta三层配置
├── agents/
│   ├── planner.py         # 新增: StrategyAgent (PRO)
│   ├── executor.py        # 重写: ExecutionAgent (Flash, CodeAct)
│   ├── researcher.py      # 重写: 泛化Miner
│   ├── reviewer.py        # 重写: 泛化Assayer
│   └── domains/           # 新增: 领域配置
│       ├── materials.py
│       ├── ai_ml.py
│       └── general.py
├── tools/
│   ├── base_tool.py       # 已有 (降级为兼容层)
│   ├── web_search.py      # 新增 (search全局函数)
│   ├── file_ops.py        # 新增 (read_file/write_file全局函数)
│   ├── data_query.py      # 新增 (query_data全局函数)
│   ├── api_caller.py      # 新增 (http_get/http_post全局函数)
│   ├── browser.py         # 新增 (browse全局函数)
│   ├── calculator.py      # 新增 (calculate全局函数)
│   ├── git_ops.py         # 新增 (git_op全局函数)
│   ├── pdf_reader.py      # 新增 (read_pdf全局函数)
│   └── scheduler.py       # 新增 (schedule全局函数)
├── knowledge/
│   ├── materials/         # 已有，扩充
│   ├── ai_ml/             # 新增
│   ├── cs/                # 新增
│   ├── math/              # 新增
│   ├── physics/           # 新增
│   ├── biology/           # 新增
│   ├── economics/         # 新增
│   ├── law/               # 新增
│   ├── psychology/        # 新增
│   └── philosophy/        # 新增
└── data/
    ├── core_memory.json       # 新增: Core Memory持久化
    ├── archival_memory.json   # 新增: Archival Memory索引
    ├── recall_memory.json     # 新增: Recall Memory + 重要性评分
    ├── procedural_rules.json  # 新增: Sleeptime提炼的行为规则
    └── vector_memory.json     # 升级: 统一向量索引
```

---

## v1→v2 变更摘要

| 变更项 | v1方案 | v2方案 | 依据 |
|--------|--------|--------|------|
| 工具范式 | BaseTool JSON Schema为主 | **CodeAct代码执行为主**，JSON降级兼容层 | OpenHands/LangGraph CodeAct验证，DeepSeek代码能力匹配 |
| 记忆架构 | 4类记忆分类 | **Letta三层OS式** (Core/Archival/Recall) + Sleeptime | Letta生产验证，4类偏学术难落地 |
| 规划Agent | 单PlannerAgent | **TeLLAgent双Agent分离**: StrategyAgent(PRO) + ExecutionAgent(Flash) | TeLLAgent超越GPT-5验证 |
| 离线整理 | 无 | **Sleeptime Engine** ("做梦"机制) | sleeptime_agent验证 |
| 遗忘机制 | 无 | **D-MEM多巴胺门控**衰减 | 仿生记忆研究 |
| PRO/Flash比 | 57%/43% | **42%/58%** (Flash更多) | TeLLAgent分离+CodeAct+Sleep都偏Flash |
| MCP | 2.0一般升级 | **2026-07无状态化协议** + Registry发现 + 14K生态 | MCP生态爆发，不接入=隔绝 |
| A2A | 无 | **A2A v1.0网关** | 150+组织支持，跨框架协作必需 |
