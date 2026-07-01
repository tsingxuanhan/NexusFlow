# -*- coding: utf-8 -*-
"""
铉枢·炉守 基础Agent类
XuanHub Base Agent Class
v4.0 - Generalization Foundation: Plan/Execute/Reflect + ContextCompactor + TodoProvider + PRO/Flash Auto-switch
"""

import time
import json
import logging
import re
from typing import List, Dict, Optional, Any, Iterator, Union, Tuple, TYPE_CHECKING, Callable
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from contextlib import contextmanager


class _nullcontext:
    """空上下文管理器（用于tracer可选时的with语句）"""
    def __enter__(self): return self
    def __exit__(self, *args): pass

# 导入配置
try:
    from config import *
except ImportError:
    # 备用配置
    DEEPSEEK_API_KEY = ""
    DEEPSEEK_ENDPOINT = "https://api.deepseek.com/v1/chat/completions"
    MODELS = {"pro": "deepseek-v4-pro", "flash": "deepseek-v4-flash"}
    DEFAULT_PARAMS = {
        "pro": {"temperature": 1.0, "top_p": 1.0, "max_tokens": 4096},
        "flash": {"temperature": 1.0, "top_p": 1.0, "max_tokens": 2048}
    }
    REQUEST_TIMEOUT = 120

# 导入增强模块
from checkpoint import (
    CheckpointManager, 
    MemoryCheckpointer,
    SqliteCheckpointer,
    get_default_manager as get_checkpoint_manager
)
from handoff import (
    HandoffManager,
    Handoff,
    HandoffContext,
    HandoffResult,
    HandoffPolicy,
    create_handoff,
    get_handoff_manager
)
from circuit_breaker import (
    get_circuit_breaker, 
    CircuitBreakerConfig, 
    CircuitBreakerOpenError
)

# 导入A2A协议 (延迟导入避免循环依赖)
_A2A_AVAILABLE = True
try:
    from a2a_protocol import A2AProtocol, A2AMessageType, TaskStatus, get_a2a_network
except ImportError:
    _A2A_AVAILABLE = False

# 导入Guardrails
_GUARDRAILS_AVAILABLE = True
try:
    from guardrails import GuardrailManager, GuardrailResult, GuardrailAction, create_default_guardrails
except ImportError:
    _GUARDRAILS_AVAILABLE = False

# 导入Quality模块 (Taste-Skill旋钮 + Impeccable自检)
_QUALITY_AVAILABLE = True
try:
    from quality import (
        QualityDials, AgentMode, MODE_PROFILES,
        ResearchPreset, RESEARCH_PRESETS, get_research_preset,
        ReviewPipeline, ReviewAction, ReviewResult,
        PatternAuditCommand, StructureAuditCommand, PolishCommand,
        DistillCommand, BolderCommand,
        create_default_pipeline, create_strict_pipeline, create_quick_pipeline
    )
except ImportError:
    _QUALITY_AVAILABLE = False

# 导入可观测性
_OBSERVABILITY_AVAILABLE = True
try:
    from observability import AgentTracer, MetricsCollector
except ImportError:
    _OBSERVABILITY_AVAILABLE = False

# v4.1 新增：导入 CheckpointWriter 和 GoalVerifier
_CHECKPOINT_WRITER_AVAILABLE = True
_GOAL_VERIFIER_AVAILABLE = True
try:
    from checkpoint_writer import CheckpointWriter
    from goal_verifier import GoalVerifier
except ImportError:
    _CHECKPOINT_WRITER_AVAILABLE = False
    _GOAL_VERIFIER_AVAILABLE = False

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("BaseAgent")


@dataclass
class Message:
    """对话消息"""
    role: str  # system, user, assistant
    content: str
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    
    def to_dict(self) -> Dict:
        return {"role": self.role, "content": self.content}


# ============================================================================
# v4.0 新增: Agent角色 + 运行模式 + ContextCompactor + TodoProvider
# ============================================================================

class AgentRole(Enum):
    """泛化Agent角色 — 与领域正交"""
    PLANNER = "planner"       # 规划：分解任务，策略推理（PRO模型）
    RESEARCHER = "researcher"  # 研究：检索、挖掘、验证
    EXECUTOR = "executor"     # 执行：代码、脚本、工具调用（Flash模型）
    REVIEWER = "reviewer"     # 审查：验证、质控、反馈


class AgentRunMode(Enum):
    """Agent运行模式 — TeLLAgent双Agent分离"""
    PLAN = "plan"       # 策略推理（PRO）— 只规划不执行
    EXECUTE = "execute"  # 精确执行（Flash）— 按计划逐步执行
    REFLECT = "reflect"  # 反思评估（PRO）— 评估结果，修正计划


# 角色默认模型映射
ROLE_MODEL_MAP = {
    AgentRole.PLANNER: "pro",
    AgentRole.RESEARCHER: "flash",
    AgentRole.EXECUTOR: "flash",
    AgentRole.REVIEWER: "flash",
}

# 模式默认模型映射
MODE_MODEL_MAP = {
    AgentRunMode.PLAN: "pro",
    AgentRunMode.EXECUTE: "flash",
    AgentRunMode.REFLECT: "pro",
}


@dataclass
class TodoItem:
    """待办事项"""
    id: str
    task: str
    priority: int = 0
    status: str = "pending"  # pending / running / done / failed / blocked
    result: Optional[str] = None
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    
    def to_dict(self) -> Dict:
        return {
            "id": self.id, "task": self.task, "priority": self.priority,
            "status": self.status, "result": self.result, "created_at": self.created_at,
        }


class TodoProvider:
    """任务追踪器 — 让Agent知道自己还有什么没做"""
    
    def __init__(self):
        self._todos: Dict[str, TodoItem] = {}
        self._counter = 0
    
    def add(self, task: str, priority: int = 0) -> str:
        self._counter += 1
        tid = f"todo_{self._counter}"
        self._todos[tid] = TodoItem(id=tid, task=task, priority=priority)
        return tid
    
    def complete(self, task_id: str, result: str = None) -> bool:
        if task_id in self._todos:
            self._todos[task_id].status = "done"
            self._todos[task_id].result = result
            return True
        return False
    
    def fail(self, task_id: str, reason: str = None) -> bool:
        if task_id in self._todos:
            self._todos[task_id].status = "failed"
            self._todos[task_id].result = reason
            return True
        return False
    
    def start(self, task_id: str) -> bool:
        if task_id in self._todos:
            self._todos[task_id].status = "running"
            return True
        return False
    
    def get_pending(self) -> List[TodoItem]:
        items = [t for t in self._todos.values() if t.status == "pending"]
        return sorted(items, key=lambda x: -x.priority)
    
    def get_running(self) -> List[TodoItem]:
        return [t for t in self._todos.values() if t.status == "running"]
    
    def get_all(self) -> List[TodoItem]:
        return list(self._todos.values())
    
    def to_context(self) -> str:
        """生成可注入system prompt的待办列表"""
        pending = self.get_pending()
        running = self.get_running()
        if not pending and not running:
            return ""
        
        lines = ["## 当前任务列表"]
        if running:
            lines.append("### 进行中")
            for t in running:
                lines.append(f"  🔄 [{t.id}] {t.task}")
        if pending:
            lines.append("### 待执行")
            for t in pending:
                lines.append(f"  ⏳ [{t.id}] (P{t.priority}) {t.task}")
        done = [t for t in self._todos.values() if t.status == "done"]
        if done:
            lines.append(f"### 已完成 ({len(done)}项)")
        return "\n".join(lines)


class ContextCompactor:
    """上下文压缩器 — 监控token使用，超阈值自动摘要
    
    借鉴 Microsoft Agent Framework 的 Agent Harness ContextCompactor。
    用Flash模型压缩历史对话，保留最近几轮不压缩。
    """
    
    def __init__(self, threshold: int = 8000, keep_recent: int = 4, model: str = "flash"):
        self.threshold = threshold    # token阈值（粗估：1中文字≈2token）
        self.keep_recent = keep_recent  # 保留最近N轮不压缩
        self.model = model
        self._compacted = False
    
    def estimate_tokens(self, messages: List[Dict]) -> int:
        """粗估token数 — 中文约2token/字，英文约1.3token/字"""
        total = 0
        for msg in messages:
            content = msg.get("content", "")
            # 中文字符数
            cn_chars = len(re.findall(r'[\u4e00-\u9fff]', content))
            other_chars = len(content) - cn_chars
            total += cn_chars * 2 + int(other_chars * 1.3)
        return total
    
    def check_and_compact(self, messages: List[Dict], api_call: Callable = None) -> List[Dict]:
        """检查是否需要压缩，需要则压缩
        
        Args:
            messages: 消息列表
            api_call: 可选的API调用函数，用于LLM摘要。为None时用截断策略。
            
        Returns:
            压缩后的消息列表
        """
        estimated = self.estimate_tokens(messages)
        
        if estimated < self.threshold * 0.8:
            self._compacted = False
            return messages
        
        if self._compacted:
            # 已经压缩过，再超阈值就截断
            return self._truncate(messages)
        
        # 第一次超阈值：尝试LLM摘要
        if api_call and len(messages) > self.keep_recent + 2:
            compacted = self._llm_compact(messages, api_call)
            if compacted:
                self._compacted = True
                return compacted
        
        # Fallback：截断
        return self._truncate(messages)
    
    def _llm_compact(self, messages: List[Dict], api_call: Callable) -> Optional[List[Dict]]:
        """用LLM摘要压缩历史"""
        # 分离：system消息 + 历史消息 + 最近消息
        system_msgs = [m for m in messages if m.get("role") == "system"]
        non_system = [m for m in messages if m.get("role") != "system"]
        
        if len(non_system) <= self.keep_recent:
            return None
        
        history = non_system[:-self.keep_recent]
        recent = non_system[-self.keep_recent:]
        
        # 构造摘要请求
        history_text = "\n".join(
            f"[{m.get('role', 'unknown')}]: {m.get('content', '')[:300]}"
            for m in history
        )
        
        summary_prompt = f"请用简洁的中文总结以下对话历史的关键信息，保留重要结论、决策和未完成任务：\n\n{history_text}"
        
        try:
            summary = api_call(summary_prompt)
            if summary:
                compact_msg = {
                    "role": "system",
                    "content": f"[历史摘要]\n{summary}"
                }
                return system_msgs + [compact_msg] + recent
        except Exception as e:
            logger.warning(f"ContextCompactor LLM摘要失败: {e}")
        
        return None
    
    def _truncate(self, messages: List[Dict]) -> List[Dict]:
        """截断策略：保留system + 最近消息"""
        system_msgs = [m for m in messages if m.get("role") == "system"]
        non_system = [m for m in messages if m.get("role") != "system"]
        
        # 保留最近的消息
        keep = non_system[-self.keep_recent:]
        
        # 加截断标记
        if len(non_system) > self.keep_recent:
            truncation_notice = {
                "role": "system",
                "content": f"[注意] 之前{len(non_system) - self.keep_recent}条对话已因长度限制被截断。"
            }
            return system_msgs + [truncation_notice] + keep
        
        return system_msgs + keep

class BaseAgent:
    """
    DeepSeek API基础Agent类
    v3.0 - 增强版
    
    新增功能:
    - Checkpoint检查点持久化
    - Handoff任务移交
    - Pydantic工具类型支持
    """
    
    # 错误类型枚举
    ERROR_RATE_LIMIT = "rate_limit"
    ERROR_SERVER = "server_error"
    ERROR_BAD_REQUEST = "bad_request"
    ERROR_AUTH = "auth_error"
    ERROR_TIMEOUT = "timeout"
    ERROR_UNKNOWN = "unknown"
    
    def __init__(
        self,
        name: str,
        model: str = "pro",
        system_prompt: str = "",
        api_key: Optional[str] = None,
        endpoint: Optional[str] = None,
        auto_downgrade: bool = True,
        # v3 新增参数
        thread_id: Optional[str] = None,
        checkpoint_manager: Optional[CheckpointManager] = None,
        handoff_manager: Optional[HandoffManager] = None,
        enable_checkpoint: bool = True,
        checkpoint_interval: int = 5,
        # v4.0 新增参数 — 泛化基建
        role: Optional[AgentRole] = None,
        domain_name: Optional[str] = None,
        run_mode: Optional[AgentRunMode] = None,
        enable_compactor: bool = True,
        compact_threshold: int = 8000,
    ):
        self.name = name
        # v4.0: 角色决定默认模型
        self.agent_role = role
        if role and model == "pro" and role in ROLE_MODEL_MAP:
            model = ROLE_MODEL_MAP[role]
        self.model = MODELS[model] if model in MODELS else model
        self.original_model = self.model
        self.model_key = model  # 保存模型key用于切换
        self.api_key = api_key or DEEPSEEK_API_KEY
        self.endpoint = endpoint or DEEPSEEK_ENDPOINT
        self.params = DEFAULT_PARAMS.get(model, DEFAULT_PARAMS["pro"]).copy()
        
        # 对话历史
        self.messages: List[Message] = []
        
        # v4.0: 领域配置
        self.domain = None
        self.domain_name = domain_name
        if domain_name:
            try:
                from agents.domains import get_domain
                self.domain = get_domain(domain_name)
            except ImportError:
                pass
        
        # 构建system prompt（v4.0: 角色+领域联合构建）
        final_prompt = system_prompt
        if role and self.domain:
            role_desc = self._get_role_description(role)
            domain_prompt = self.domain.format_system_prompt(
                role=role.value,
                role_description=role_desc,
            )
            final_prompt = domain_prompt if not system_prompt else f"{system_prompt}\n\n{domain_prompt}"
        
        if final_prompt:
            self.messages.append(Message("system", final_prompt))
        
        # v4.0: 运行模式
        self.run_mode = run_mode
        if run_mode:
            self._apply_run_mode(run_mode)
        
        # 统计信息
        self.stats = {
            "total_requests": 0,
            "total_tokens": 0,
            "errors": 0,
            "downgrades": 0,
            "mode_switches": 0,
            "compactions": 0,
        }
        
        # 错误恢复配置
        self.auto_downgrade = auto_downgrade
        self._error_counts = {}
        
        # v4.0: ContextCompactor
        self.compactor: Optional[ContextCompactor] = None
        if enable_compactor:
            self.compactor = ContextCompactor(threshold=compact_threshold)
        
        # v4.0: TodoProvider
        self.todo = TodoProvider()
        
        # ============ v3: Checkpoint支持 ============
        self.thread_id = thread_id or f"{name}_{id(self)}"
        self.enable_checkpoint = enable_checkpoint
        self.checkpoint_interval = checkpoint_interval
        self._message_counter = 0
        
        if checkpoint_manager:
            self.checkpoint_manager = checkpoint_manager
        else:
            self.checkpoint_manager = get_checkpoint_manager()
        
        # ============ v3: Handoff支持 ============
        self.handoff_manager = handoff_manager or get_handoff_manager()
        self.available_handoffs: List[Handoff] = []
        
        # ============ v3: Circuit Breaker ============
        self.api_circuit = get_circuit_breaker(
            f"{name}_api", 
            CircuitBreakerConfig(failure_threshold=5)
        )
        
        # ============ v3: A2A协议 ============
        self._a2a_action_map: Dict[str, Callable] = {}
        self.a2a: Optional[A2AProtocol] = None
        if _A2A_AVAILABLE:
            self._init_a2a_protocol()
        
        # ============ v3: Guardrails ============
        self.guardrails: Optional[GuardrailManager] = None
        if _GUARDRAILS_AVAILABLE:
            self.guardrails = create_default_guardrails()
        
        # ============ v3: Tracer ============
        self.tracer: Optional[AgentTracer] = None
        self.metrics: Optional[MetricsCollector] = None
        if _OBSERVABILITY_AVAILABLE:
            self.tracer = AgentTracer(name)
            self.metrics = MetricsCollector()
        
        # ============ v3: Quality Dials ============
        self.quality_dials: Optional[QualityDials] = None
        self.agent_mode: Optional[AgentMode] = None
        self.review_pipeline: Optional[ReviewPipeline] = None
        if _QUALITY_AVAILABLE:
            self.quality_dials = QualityDials()
            self.agent_mode = AgentMode.BALANCED
            self.review_pipeline = create_default_pipeline()
        
        logger.info(f"[{self.name}] Agent initialized v4.0 (role={role}, domain={domain_name}, mode={run_mode})")
        
        # Phase 7: 自适应上下文管理
        self._context_window = None
        self._global_sync_callback = None
    
    # ============ v4.0: 角色与模式方法 ============
    
    @staticmethod
    def _get_role_description(role: AgentRole) -> str:
        """获取角色描述文本"""
        descriptions = {
            AgentRole.PLANNER: "策略规划者：分解任务、设计执行策略、评估结果。你负责思考全局，不直接执行。",
            AgentRole.RESEARCHER: "知识研究者：检索信息、挖掘数据、验证事实。你负责获取和验证知识。",
            AgentRole.EXECUTOR: "精确执行者：编写代码、调用工具、完成具体操作。你负责把计划变成现实。",
            AgentRole.REVIEWER: "质量审查者：验证结果、发现问题、提供反馈。你负责确保产出质量。",
        }
        return descriptions.get(role, "通用智能体")
    
    def _apply_run_mode(self, mode: AgentRunMode) -> None:
        """应用运行模式 — 切换模型和参数"""
        self.run_mode = mode
        target_model = MODE_MODEL_MAP.get(mode, "flash")
        self.model = MODELS[target_model]
        self.model_key = target_model
        self.params = DEFAULT_PARAMS.get(target_model, DEFAULT_PARAMS["pro"]).copy()
        
        # Plan模式：高温度鼓励发散
        if mode == AgentRunMode.PLAN:
            self.params["temperature"] = 1.0
            self.params["max_tokens"] = 4096
        # Execute模式：低温度精确执行
        elif mode == AgentRunMode.EXECUTE:
            self.params["temperature"] = 0.3
            self.params["max_tokens"] = 4096
        # Reflect模式：中温度平衡
        elif mode == AgentRunMode.REFLECT:
            self.params["temperature"] = 0.7
            self.params["max_tokens"] = 4096
        
        logger.info(f"[{self.name}] 模式切换 → {mode.value} (model={target_model})")
    
    def set_run_mode(self, mode: str) -> None:
        """公开接口：切换运行模式
        
        Args:
            mode: "plan" / "execute" / "reflect"
        """
        try:
            run_mode = AgentRunMode(mode)
        except ValueError:
            logger.warning(f"[{self.name}] 未知运行模式 '{mode}'，可选: plan/execute/reflect")
            return
        
        self._apply_run_mode(run_mode)
        self.stats["mode_switches"] += 1
    
    # ============ Phase 7: 自适应上下文管理 ============
    
    def set_context_window(self, window) -> None:
        """Phase 7: 设置上下文窗口管理器"""
        self._context_window = window
    
    def set_global_sync_callback(self, callback) -> None:
        """Phase 7: 设置全局同步回调"""
        self._global_sync_callback = callback
    
    def _apply_context_window_to_messages(self, messages: List[Dict]) -> List[Dict]:
        """Phase 7: 应用上下文窗口截断"""
        if not self._context_window:
            return messages
        
        # 保留system消息
        system_msgs = [m for m in messages if m.get("role") == "system"]
        other_msgs = [m for m in messages if m.get("role") != "system"]
        
        # 截断
        truncated = self._context_window.truncate(other_msgs)
        
        # 注入全局同步信息
        if self._global_sync_callback:
            global_summary = self._global_sync_callback()
            if global_summary:
                truncated.append({
                    "role": "system",
                    "content": f"[全局同步] {global_summary}"
                })
        
        return system_msgs + truncated
    
    def plan(self, goal: str) -> str:
        """策略规划 — 用PRO模型分解目标
        
        Args:
            goal: 高层目标描述
            
        Returns:
            任务分解和策略方案
        """
        old_mode = self.run_mode
        self._apply_run_mode(AgentRunMode.PLAN)
        
        todo_context = self.todo.to_context()
        todo_section = f"\n\n{todo_context}" if todo_context else ""
        
        prompt = f"""请对以下目标进行策略性分析和任务分解：

## 目标
{goal}
{todo_section}

## 要求
1. 将目标分解为可执行的子任务
2. 识别子任务间的依赖关系
3. 为每个子任务指定最合适的执行策略
4. 评估潜在风险和备选方案

输出格式：
### 任务分解
[子任务列表，含依赖关系]

### 执行策略
[每个子任务的策略选择]

### 风险评估
[潜在问题与应对]"""

        result = self.chat(prompt)
        
        # 自动添加子任务到TodoProvider
        self._parse_plan_to_todos(result)
        
        # 恢复原模式
        if old_mode:
            self._apply_run_mode(old_mode)
        
        return result
    
    def execute_step(self, step: str) -> str:
        """精确执行 — 用Flash模型执行步骤
        
        Args:
            step: 要执行的具体步骤
            
        Returns:
            执行结果
        """
        old_mode = self.run_mode
        self._apply_run_mode(AgentRunMode.EXECUTE)
        
        todo_context = self.todo.to_context()
        todo_section = f"\n\n{todo_context}" if todo_context else ""
        
        prompt = f"""请精确执行以下步骤：

## 步骤
{step}
{todo_section}

## 要求
1. 严格按照步骤描述执行
2. 输出具体的、可验证的结果
3. 如果需要工具调用，明确说明
4. 如果遇到问题，记录问题并尝试替代方案"""

        result = self.chat(prompt)
        
        # 恢复原模式
        if old_mode:
            self._apply_run_mode(old_mode)
        
        return result
    
    def reflect(self, result: str, expectation: str = "") -> str:
        """反思评估 — 用PRO模型评估执行结果
        
        Args:
            result: 执行结果
            expectation: 预期目标
            
        Returns:
            反思评估报告
        """
        old_mode = self.run_mode
        self._apply_run_mode(AgentRunMode.REFLECT)
        
        prompt = f"""请评估以下执行结果：

## 预期目标
{expectation or "（未指定）"}

## 实际结果
{result}

## 评估维度
1. **目标达成度**: 结果是否满足预期？百分比评估。
2. **质量问题**: 有无错误、遗漏或不一致？
3. **改进空间**: 如何优化？
4. **经验提炼**: 从中可以总结什么规则或经验？

输出格式：
- 达成度: X%
- 问题: [列表]
- 改进: [建议]
- 经验: [可复用规则]"""

        reflection = self.chat(prompt)
        
        # 恢复原模式
        if old_mode:
            self._apply_run_mode(old_mode)
        
        return reflection
    
    def _parse_plan_to_todos(self, plan_text: str) -> None:
        """从规划文本中提取子任务添加到TodoProvider"""
        # 简单提取：找数字开头的行作为子任务
        lines = plan_text.split("\n")
        for line in lines:
            stripped = line.strip()
            # 匹配 "1." "1)" "步骤1" 等模式
            if re.match(r'^(\d+[\.\)、]|步骤\d+|Step\s*\d+)', stripped):
                # 去掉序号前缀
                task_text = re.sub(r'^(\d+[\.\)、]|步骤\d+[:：]?|Step\s*\d+[:：]?)\s*', '', stripped)
                if task_text and len(task_text) > 3:
                    self.todo.add(task_text, priority=0)
    
    # ============ v4.0 Phase 2: 规划引擎集成 ============
    
    def plan_with_tree(self, goal: str, depth: int = 2) -> Any:
        """用TaskTree进行层次化规划
        
        Phase 2核心方法：plan→decompose→TaskTree
        
        Args:
            goal: 高层目标
            depth: 分解深度
            
        Returns:
            TaskTree对象
        """
        from task_tree import TaskTree
        
        # 切到PLAN模式
        old_mode = self.run_mode
        self._apply_run_mode(AgentRunMode.PLAN)
        
        try:
            prompt = f"""请对以下目标进行{depth}层深度任务分解：

## 目标
{goal}

## 要求
- 第1层：主要阶段（3-5个），每个用编号标注
- 第2层：每个阶段的子任务
{"- 第3层：每个子任务的具体步骤" if depth >= 3 else ""}
- 标注依赖关系：[依赖: T-xxx]
- 标注分配Agent：[Planner]/[Researcher]/[Executor]/[Reviewer]

输出Markdown层级格式。"""
            
            response = self.chat(prompt)
            tree = TaskTree.from_plan_text(response, goal=goal)
            
            # 将叶子节点添加到TodoProvider
            for node in tree.root.flatten():
                if node.is_leaf and node.status == "pending":
                    self.todo.add(node.description, priority=0)
            
            logger.info(f"[{self.name}] TaskTree规划完成: {tree.stats['total']}个任务, 进度基线0%")
            return tree
            
        finally:
            if old_mode:
                self._apply_run_mode(old_mode)
    
    def reflect_on_results(
        self,
        results: Dict[str, str],
        expectations: Dict[str, str] = None,
        plan_summary: str = "",
    ) -> Any:
        """对执行结果进行反思
        
        Phase 2核心方法：reflect→经验提取→重规划决策
        
        Args:
            results: {task_id: result_text}
            expectations: {task_id: expectation_text}
            plan_summary: 计划摘要
            
        Returns:
            Reflection对象
        """
        from reflection import ReflectionLoop
        
        # 创建反思循环（使用当前agent的chat函数）
        reflection_loop = ReflectionLoop(
            strategy_chat=self.chat,
            flash_chat=None,  # 用规则化快速评估
        )
        
        # 如果是PRO角色，用自身做深度反思
        if self.agent_role == AgentRole.PLANNER:
            reflection_loop.flash_chat = self.chat
        
        reflection = reflection_loop.reflect(
            plan_summary=plan_summary,
            results=results,
            expectations=expectations or {},
        )
        
        # 将经验规则记录到TodoProvider
        for lesson in reflection.lessons_learned:
            self.todo.add(f"📝 经验: {lesson}", priority=-1)
        
        logger.info(f"[{self.name}] 反思完成: 达成度{reflection.achievement_score:.0%}, "
                     f"重规划={'需要' if reflection.should_replan else '不需要'}")
        
        return reflection
    
    def think_with_tot(self, problem: str, context: str = "") -> Dict[str, Any]:
        """用Tree of Thought推理复杂问题
        
        Phase 2核心方法：ToT推理→最优路径→解答
        
        Args:
            problem: 复杂问题
            context: 背景信息
            
        Returns:
            ToT搜索结果（含solution, path, score等）
        """
        from tot import TreeOfThought
        
        tot = TreeOfThought(
            strategy_chat=self.chat,
            evaluation_chat=None,  # 用自身快速评估
            branch_factor=3,
            max_depth=4,
        )
        
        result = tot.search(problem, context)
        
        logger.info(f"[{self.name}] ToT推理完成: 探索{result['branches_explored']}个分支, "
                     f"最优评分{result['best_score']:.1f}")
        
        return result
    
    def execute_tree(self, tree, executor_agent=None) -> Dict[str, str]:
        """执行TaskTree中的所有就绪任务
        
        Phase 2核心方法：调度→执行→更新状态
        
        Args:
            tree: TaskTree对象
            executor_agent: 执行Agent（None则用自身）
            
        Returns:
            {task_id: result_text}
        """
        from task_tree import TaskScheduler
        
        results = {}
        executor = executor_agent or self
        
        # 生成调度计划
        scheduler = TaskScheduler(tree)
        steps = scheduler.schedule()
        
        for step in steps:
            task_id = step["task_id"]
            task_node = tree.find(task_id)
            if not task_node:
                continue
            
            # 标记为运行中
            task_node.update_status("running")
            
            # 执行
            if hasattr(executor, 'execution') and hasattr(executor.execution, 'execute_task_node'):
                result = executor.execution.execute_task_node(task_node)
            else:
                result = executor.execute_step(task_node.description)
                task_node.update_status("done", result=result)
            
            results[task_id] = result
        
        # 汇总统计
        stats = tree.stats
        logger.info(f"[{self.name}] TaskTree执行完成: {stats['done']}/{stats['total']}成功, "
                     f"{stats['failed']}失败, 进度{tree.progress:.0%}")
        
        return results
    
    # ============ v4.0 Phase 3: 工具生态集成 ============
    
    def init_codeact(self, extra_tools: Optional[Dict] = None) -> None:
        """
        初始化CodeAct执行器和工具注册中心
        
        Args:
            extra_tools: 额外工具函数字典 {name: callable}
        """
        from tools.code_exec import CodeActExecutor
        from tools.tool_registry import create_default_registry
        
        # 创建执行器
        self._codeact = CodeActExecutor(
            timeout=CODEACT_CONFIG.get("timeout", 15),
            max_output_length=CODEACT_CONFIG.get("max_output_length", 10000),
            enable_guardrails=CODEACT_CONFIG.get("enable_guardrails", True),
            persist_locals=CODEACT_CONFIG.get("persist_locals", True),
        )
        
        # 创建工具注册中心
        self._tool_registry = create_default_registry()
        
        # 注入工具到CodeAct执行环境
        globals_dict = self._tool_registry.to_codeact_globals()
        self._codeact.add_globals(globals_dict)
        
        # 注册CodeAct覆盖（直接使用工具函数而非BaseTool包装）
        from tools.web_search import search
        from tools.file_ops import read_file as _read_file, write_file as _write_file, list_dir
        from tools.data_query import query_data, register_dataset
        from tools.api_caller import http_get, http_post
        from tools.calculator import calculate, linear_regression
        from tools.git_ops import git_op
        from tools.pdf_reader import read_pdf
        from tools.browser import browse
        from tools.scheduler import schedule_task, cancel_task, list_scheduled_tasks
        
        codeact_globals = {
            "search": search,
            "read_file": _read_file,
            "write_file": _write_file,
            "list_dir": list_dir,
            "query_data": query_data,
            "register_dataset": register_dataset,
            "http_get": http_get,
            "http_post": http_post,
            "calculate": calculate,
            "linear_regression": linear_regression,
            "git_op": git_op,
            "read_pdf": read_pdf,
            "browse": browse,
            "schedule_task": schedule_task,
            "cancel_task": cancel_task,
            "list_scheduled_tasks": list_scheduled_tasks,
        }
        self._codeact.add_globals(codeact_globals)
        
        # 额外工具
        if extra_tools:
            self._codeact.add_globals(extra_tools)
        
        logger.info(f"[{self.name}] CodeAct initialized with {len(self._codeact.available_globals())} globals")
    
    def execute_codeact(self, code: str, extra_globals: Optional[Dict] = None) -> Any:
        """
        执行CodeAct代码
        
        Args:
            code: Python代码字符串
            extra_globals: 额外全局变量
            
        Returns:
            CodeActResult
        """
        if not hasattr(self, '_codeact'):
            self.init_codeact()
        
        result = self._codeact.execute(code, extra_globals=extra_globals)
        
        # 更新统计
        self.stats["codeact_executions"] = self.stats.get("codeact_executions", 0) + 1
        if not result.success:
            self.stats["codeact_failures"] = self.stats.get("codeact_failures", 0) + 1
        
        return result
    
    def get_tool_registry(self):
        """获取工具注册中心"""
        if not hasattr(self, '_tool_registry'):
            self.init_codeact()
        return self._tool_registry
    
    def register_tool(self, tool) -> None:
        """
        注册自定义工具
        
        Args:
            tool: BaseTool实例
        """
        if not hasattr(self, '_tool_registry'):
            self.init_codeact()
        self._tool_registry.register(tool)
        # 同时更新CodeAct环境
        globals_dict = self._tool_registry.to_codeact_globals()
        self._codeact.add_globals(globals_dict)
    
    def codeact_status(self) -> Dict[str, Any]:
        """获取CodeAct执行状态"""
        if not hasattr(self, '_codeact'):
            return {"initialized": False}
        
        return {
            "initialized": True,
            "codeact_stats": self._codeact.get_stats(),
            "tool_registry_stats": self._tool_registry.get_stats(),
        }

    # ============ v4.0 Phase 4: 知识记忆集成 ============

    def init_memory(self, data_dir: str = "data") -> None:
        """
        初始化Letta三层记忆系统
        
        Args:
            data_dir: 记忆数据目录
        """
        from memory_manager import MemoryManager, create_memory_manager
        from sleeptime import SleeptimeEngine
        from multi_hop_rag import MultiHopRAG

        # 创建Memory Manager
        self._memory = create_memory_manager(
            data_dir=data_dir,
            api_endpoint=DEEPSEEK_ENDPOINT,
            api_key=DEEPSEEK_API_KEY,
        )

        # 创建Sleeptime Engine
        self._sleeptime = SleeptimeEngine(
            memory_manager=self._memory,
            api_endpoint=DEEPSEEK_ENDPOINT,
            api_key=DEEPSEEK_API_KEY,
        )

        # 创建Multi-Hop RAG
        self._multihop_rag = MultiHopRAG(
            archival_memory=self._memory.archival,
            api_endpoint=DEEPSEEK_ENDPOINT,
            api_key=DEEPSEEK_API_KEY,
        )

        logger.info(f"[{self.name}] Memory system initialized: {self._memory.get_summary()}")

    def remember(self, content: str, memory_type: str = "auto", **kwargs) -> str:
        """
        统一记忆写入接口
        
        Args:
            content: 记忆内容
            memory_type: "core"/"archival"/"recall"/"auto"
            **kwargs: 传递给MemoryManager.remember的参数
        """
        if not hasattr(self, '_memory'):
            self.init_memory()
        return self._memory.remember(content, memory_type=memory_type, **kwargs)

    def recall(self, query: str, top_k: int = 5, multi_hop: bool = False) -> Dict:
        """
        统一记忆检索接口
        
        Args:
            query: 查询文本
            top_k: 返回数量
            multi_hop: 是否使用多跳检索
        """
        if not hasattr(self, '_memory'):
            self.init_memory()

        if multi_hop:
            rag_result = self._multihop_rag.retrieve(query)
            return {
                "archival": rag_result.all_entries,
                "total_hops": rag_result.total_hops,
                "sufficient": rag_result.sufficient,
                "context": rag_result.to_context_string(),
            }

        return self._memory.recall_memory(query, top_k=top_k)

    def dream(self, force: bool = False) -> Dict:
        """
        触发Sleeptime整理
        
        Args:
            force: 是否强制执行
        """
        if not hasattr(self, '_sleeptime'):
            self.init_memory()
        result = self._sleeptime.dream(force=force)
        return result.to_dict()

    def memory_status(self) -> Dict:
        """获取记忆系统状态"""
        if not hasattr(self, '_memory'):
            return {"initialized": False}

        stats = self._memory.get_stats()
        sleeptime_stats = self._sleeptime.get_stats() if hasattr(self, '_sleeptime') else {}
        rag_stats = self._multihop_rag.get_stats() if hasattr(self, '_multihop_rag') else {}

        return {
            "initialized": True,
            "memory": stats,
            "sleeptime": sleeptime_stats,
            "multihop_rag": rag_stats,
        }

    # ============ v4.0: chat方法升级（集成Compactor+Todo） ============

    def _estimate_context_usage(self) -> float:
        """
        估算当前上下文使用率

        Returns:
            0.0-1.0 的使用率
        """
        # 默认上下文上限（假设100K tokens）
        max_tokens = 100000

        # 粗估当前token数
        total_chars = sum(len(m.content) for m in self.messages)
        # 中文约2token/字，英文约1.3token/字
        cn_chars = sum(len(re.findall(r'[\u4e00-\u9fff]', m.content)) for m in self.messages)
        other_chars = total_chars - cn_chars
        estimated_tokens = cn_chars * 2 + int(other_chars * 1.3)

        return min(1.0, estimated_tokens / max_tokens)

    def _pre_chat_compact(self) -> None:
        """chat前自动压缩上下文"""
        if not self.compactor:
            return
        
        msg_dicts = [m.to_dict() for m in self.messages]
        
        def _quick_summary(prompt: str) -> str:
            """用当前模型快速摘要（不递归调用chat）"""
            try:
                compact_msg = [
                    {"role": "system", "content": "你是摘要助手，用简洁中文总结。"},
                    {"role": "user", "content": prompt},
                ]
                # 临时切到flash
                old_model = self.model
                self.model = MODELS["flash"]
                old_params = self.params.copy()
                self.params = DEFAULT_PARAMS["flash"].copy()
                
                result = self._chat_nonstream(compact_msg)
                
                self.model = old_model
                self.params = old_params
                return result
            except Exception:
                return ""
        
        compacted = self.compactor.check_and_compact(msg_dicts, api_call=_quick_summary)
        
        if compacted != msg_dicts:
            # 重建messages
            self.messages = [Message(m["role"], m["content"]) for m in compacted]
            self.stats["compactions"] += 1
            logger.info(f"[{self.name}] 上下文压缩完成 (messages: {len(msg_dicts)} → {len(compacted)})")
    
    def _post_chat_todo_inject(self) -> None:
        """chat后将Todo上下文注入system prompt（如果待办有更新）"""
        todo_ctx = self.todo.to_context()
        if not todo_ctx:
            return
        
        # 检查是否已有todo注入
        for i, msg in enumerate(self.messages):
            if msg.role == "system" and "当前任务列表" in msg.content:
                self.messages[i] = Message("system", 
                    re.sub(r'## 当前任务列表.*', todo_ctx, msg.content, flags=re.DOTALL))
                return
        
        # 首次注入：找到第一个system消息后追加
        for i, msg in enumerate(self.messages):
            if msg.role == "system":
                self.messages.insert(i + 1, Message("system", todo_ctx))
                return
    
    def _init_a2a_protocol(self) -> None:
        """初始化A2A协议实例"""
        from a2a_protocol import A2AProtocol
        
        # 获取Agent角色名
        role = self.__class__.__name__.replace("Agent", "").lower()
        
        self.a2a = A2AProtocol(
            agent_id=self.name.lower(),
            agent_name=self.name,
            agent_role=role
        )
        
        # 绑定_execute_action到_action_map
        _action_map = self._a2a_action_map
        _agent = self
        
        def _execute_with_map(action: str, parameters: Dict) -> Any:
            if action in _action_map:
                return _action_map[action](**parameters)
            logger.warning(f"[{_agent.name}] No handler for A2A action: {action}")
            return None
        
        self.a2a._execute_action = _execute_with_map
    
    def register_a2a_action(self, action_name: str, method: Callable) -> None:
        """注册A2A action到实际方法的映射
        
        Args:
            action_name: A2A action名称
            method: 实际执行的方法
        """
        self._a2a_action_map[action_name] = method
        logger.debug(f"[{self.name}] Registered A2A action: {action_name}")
    
    def register_a2a_capability(
        self,
        name: str,
        description: str,
        keywords: Optional[List[str]] = None
    ) -> None:
        """注册A2A能力
        
        Args:
            name: 能力名称
            description: 能力描述
            keywords: 触发关键词
        """
        if self.a2a:
            self.a2a.register_capability(
                name=name,
                description=description,
                keywords=keywords or []
            )
    
    # ============ Checkpoint相关方法 ============
    
    def save_checkpoint(self, thread_id: Optional[str] = None) -> str:
        """
        保存检查点
        
        Args:
            thread_id: 线程ID(可选，默认使用agent的thread_id)
            
        Returns:
            checkpoint_id
        """
        if not self.enable_checkpoint:
            return ""
        
        thread_id = thread_id or self.thread_id
        
        state = {
            "messages": [m.to_dict() for m in self.messages],
            "stats": self.stats.copy(),
            "model": self.model,
            "params": self.params.copy()
        }
        
        checkpoint_id = self.checkpoint_manager.save(
            thread_id,
            state,
            metadata={"agent_name": self.name, "source": "manual"}
        )
        
        logger.debug(f"[{self.name}] Checkpoint saved: {checkpoint_id}")
        return checkpoint_id
    
    def load_checkpoint(
        self,
        thread_id: Optional[str] = None,
        checkpoint_id: Optional[str] = None
    ) -> bool:
        """
        加载检查点
        
        Args:
            thread_id: 线程ID
            checkpoint_id: 检查点ID(可选，加载最新)
            
        Returns:
            是否成功加载
        """
        thread_id = thread_id or self.thread_id
        
        checkpoint = self.checkpoint_manager.checkpointer.load(thread_id, checkpoint_id)
        
        if not checkpoint:
            logger.warning(f"[{self.name}] No checkpoint found for {thread_id}")
            return False
        
        # 恢复状态
        state = checkpoint.state
        self.messages = [Message(**m) for m in state.get("messages", [])]
        self.stats = state.get("stats", self.stats)
        self.model = state.get("model", self.original_model)
        
        logger.info(f"[{self.name}] Checkpoint loaded: {checkpoint.checkpoint_id}")
        return True
    
    def rewind(
        self,
        steps_back: int = 1,
        thread_id: Optional[str] = None
    ) -> bool:
        """
        Rewind回退指定步数
        
        Args:
            steps_back: 回退步数
            thread_id: 线程ID
            
        Returns:
            是否成功回退
        """
        checkpoint = self.checkpoint_manager.rewind(
            thread_id or self.thread_id,
            steps_back=steps_back
        )
        
        if checkpoint:
            return self.load_checkpoint(checkpoint_id=checkpoint.checkpoint_id)
        return False
    
    def _auto_checkpoint(self) -> None:
        """自动检查点"""
        if not self.enable_checkpoint:
            return
        
        self._message_counter += 1
        
        if self._message_counter % self.checkpoint_interval == 0:
            self.save_checkpoint()
    
    def get_checkpoint_history(
        self,
        thread_id: Optional[str] = None,
        limit: int = 10
    ) -> List[Dict]:
        """获取检查点历史"""
        return self.checkpoint_manager.get_history(
            thread_id or self.thread_id,
            limit
        )
    
    # ============ Handoff相关方法 ============
    
    def register_handoff(
        self,
        name: str,
        target_agent: 'BaseAgent',
        policy: HandoffPolicy = HandoffPolicy.TRANSFER,
        description: str = "",
        keywords: Optional[List[str]] = None
    ) -> None:
        """
        注册Handoff
        
        Args:
            name: Handoff名称
            target_agent: 目标Agent
            policy: 移交策略
            description: 描述
            keywords: 触发关键词
        """
        handoff = create_handoff(
            name=name,
            target_agent=target_agent,
            policy=policy,
            description=description,
            keywords=keywords
        )
        
        self.available_handoffs.append(handoff)
        self.handoff_manager.register(self.name, handoff)
        
        logger.info(f"[{self.name}] Registered handoff '{name}' -> {target_agent.name}")
    
    def handoff_to(
        self,
        target: Union[str, 'BaseAgent'],
        request: str,
        include_history: bool = True,
        max_history: int = 10
    ) -> HandoffResult:
        """
        移交任务到另一个Agent
        
        Args:
            target: 目标Agent或Handoff名称
            request: 原始请求
            include_history: 是否包含对话历史
            max_history: 最多包含的历史消息数
            
        Returns:
            HandoffResult
        """
        # 解析目标
        if isinstance(target, str):
            handoff = self.handoff_manager.get_handoff(target)
            
            # 新增: 如果找不到handoff，尝试A2A网络
            if not handoff and _A2A_AVAILABLE and self.a2a:
                network = get_a2a_network()
                agent_protocol = network.find_agent_by_capability(target)
                
                if agent_protocol:
                    logger.info(f"[{self.name}] A2A桥接: 查找能力 '{target}' -> {agent_protocol.agent_name}")
                    
                    # 通过A2A网络发送任务请求
                    msg = self.a2a.create_task_request(
                        receiver_id=agent_protocol.agent_id,
                        action=target,
                        parameters={"request": request}
                    )
                    response = network.send_message(msg)
                    
                    if response and response.content:
                        return HandoffResult(
                            success=True,
                            result=response.content,
                            target_agent_name=agent_protocol.agent_name,
                            metadata={"via": "a2a_network", "message_id": msg.message_id, "action": target}
                        )
                    
                    return HandoffResult(
                        success=False,
                        result=None,
                        target_agent_name=agent_protocol.agent_name,
                        error="A2A请求未获得响应",
                        metadata={"via": "a2a_network", "action": target}
                    )
            
            if not handoff:
                raise ValueError(f"Unknown handoff: {target} (也未在A2A网络找到匹配能力)")
        else:
            # 直接传递Agent，创建临时Handoff
            handoff = create_handoff(
                name=f"{self.name}_to_{target.name}",
                target_agent=target
            )
        
        # 生成任务摘要
        task_summary = self._generate_task_summary()
        
        # 获取对话历史
        messages = None
        if include_history:
            messages = [m.to_dict() for m in self.messages[-max_history:]]
        
        # 获取当前状态
        state = self.get_state()
        
        # 创建上下文
        context = handoff.create_context(
            source_agent=self,
            original_request=request,
            task_summary=task_summary,
            state=state,
            messages=messages
        )
        
        # 执行Handoff
        result = self.handoff_manager.execute(handoff, context)
        
        logger.info(f"[{self.name}] Handoff to {handoff.target_agent.name}: {'success' if result.success else 'failed'}")
        
        return result
    
    def _generate_task_summary(self) -> str:
        """生成任务摘要"""
        if not self.messages:
            return ""
        
        # 获取最近几条消息作为摘要
        recent = self.messages[-5:] if len(self.messages) > 5 else self.messages
        
        summary_parts = []
        for msg in recent:
            if msg.role == "user":
                summary_parts.append(f"用户: {msg.content[:100]}")
            elif msg.role == "assistant":
                summary_parts.append(f"助手: {msg.content[:100]}")
        
        return "\n".join(summary_parts)
    
    def get_state(self) -> Dict[str, Any]:
        """获取Agent状态"""
        return {
            "name": self.name,
            "model": self.model,
            "stats": self.stats.copy(),
            "message_count": len(self.messages)
        }
    
    def get_available_handoffs(self) -> List[Dict]:
        """获取可用的Handoff列表"""
        return [
            {
                "name": h.name,
                "target": h.target_agent.name,
                "policy": h.policy.value,
                "description": h.description
            }
            for h in self.available_handoffs
        ]
    
    # ============ 原有方法 ============
    
    def _classify_error(self, status_code: int, exception: Exception = None) -> str:
        """错误分类"""
        if status_code == 429:
            return self.ERROR_RATE_LIMIT
        elif status_code in (500, 502, 503, 504):
            return self.ERROR_SERVER
        elif status_code == 400:
            return self.ERROR_BAD_REQUEST
        elif status_code in (401, 403):
            return self.ERROR_AUTH
        
        if exception:
            exc_name = type(exception).__name__
            if "Timeout" in exc_name:
                return self.ERROR_TIMEOUT
            if "Connection" in exc_name:
                return self.ERROR_TIMEOUT
        
        return self.ERROR_UNKNOWN
    
    def _get_retry_config(self, error_type: str) -> Dict[str, Any]:
        """获取重试配置"""
        configs = {
            self.ERROR_RATE_LIMIT: {
                "max_retries": 5,
                "base_delay": 5,
                "max_delay": 120,
                "backoff": 2.0
            },
            self.ERROR_SERVER: {
                "max_retries": 3,
                "base_delay": 2,
                "max_delay": 30,
                "backoff": 1.5
            },
            self.ERROR_TIMEOUT: {
                "max_retries": 2,
                "base_delay": 1,
                "max_delay": 20,
                "backoff": 2.0
            },
            self.ERROR_AUTH: {
                "max_retries": 0,
                "base_delay": 0,
                "max_delay": 0
            }
        }
        return configs.get(error_type, {
            "max_retries": 1,
            "base_delay": 1,
            "max_delay": 10,
            "backoff": 1.5
        })
    
    def _should_downgrade(self, error_type: str, attempt: int) -> bool:
        """判断是否应该降级模型"""
        if not self.auto_downgrade:
            return False
        
        if self.model != "deepseek-v4-pro":
            return False
        
        if error_type in (self.ERROR_TIMEOUT, self.ERROR_SERVER):
            return attempt >= 2
        
        return False
    
    def reset_model(self) -> None:
        """重置模型到原始配置"""
        self.model = self.original_model
        logger.info(f"[{self.name}] Model reset to {self.model}")
    
    def _call_api(
        self,
        messages: List[Dict],
        stream: bool = False,
        **kwargs
    ) -> Any:
        """调用DeepSeek API - 增强版错误恢复"""
        import requests
        
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}"
        }
        
        params = self.params.copy()
        params.update(kwargs)
        params["model"] = self.model
        
        payload = {
            "messages": messages,
            "stream": stream,
            **params
        }
        
        current_attempt = 0
        error_type = self.ERROR_UNKNOWN
        config = self._get_retry_config(error_type)
        max_retries = config["max_retries"]
        
        while current_attempt <= max_retries:
            try:
                # 使用熔断器包裹实际的API请求
                with self.api_circuit:
                    response = requests.post(
                        self.endpoint,
                        headers=headers,
                        json=payload,
                        timeout=REQUEST_TIMEOUT,
                        stream=stream
                    )
                
                if response.status_code == 429:
                    error_type = self.ERROR_RATE_LIMIT
                    config = self._get_retry_config(error_type)
                    max_retries = config["max_retries"]
                    
                    if current_attempt < max_retries:
                        wait_time = min(config["base_delay"] * (config["backoff"] ** current_attempt), config["max_delay"])
                        logger.warning(f"[{self.name}] 速率限制，等待 {wait_time:.1f}秒...")
                        time.sleep(wait_time)
                        current_attempt += 1
                        continue
                    else:
                        self.stats["errors"] += 1
                        raise Exception(f"[{self.name}] 速率限制重试耗尽")
                
                if response.status_code >= 500:
                    error_type = self.ERROR_SERVER
                    config = self._get_retry_config(error_type)
                    max_retries = config["max_retries"]
                    
                    if self._should_downgrade(error_type, current_attempt):
                        self._downgrade_model()
                    
                    if current_attempt < max_retries:
                        wait_time = min(config["base_delay"] * (config["backoff"] ** current_attempt), config["max_delay"])
                        logger.warning(f"[{self.name}] 服务端错误 {response.status_code}，{wait_time:.1f}秒后重试...")
                        time.sleep(wait_time)
                        current_attempt += 1
                        continue
                
                if response.status_code != 200:
                    error_type = self._classify_error(response.status_code)
                    logger.error(f"[{self.name}] API错误 {response.status_code}: {response.text[:200]}")
                    self.stats["errors"] += 1
                    
                    if error_type == self.ERROR_AUTH:
                        raise Exception(f"[{self.name}] 认证失败，请检查API Key")
                    
                    raise Exception(f"[{self.name}] API错误 {response.status_code}")
                
                return response.json() if not stream else response
                
            except requests.exceptions.Timeout:
                error_type = self.ERROR_TIMEOUT
                config = self._get_retry_config(error_type)
                max_retries = config["max_retries"]
                
                if self._should_downgrade(error_type, current_attempt):
                    self._downgrade_model()
                
                if current_attempt < max_retries:
                    wait_time = min(config["base_delay"] * (config["backoff"] ** current_attempt), config["max_delay"])
                    logger.warning(f"[{self.name}] 请求超时，{wait_time:.1f}秒后重试...")
                    time.sleep(wait_time)
                    current_attempt += 1
                    continue
                else:
                    self.stats["errors"] += 1
                    raise Exception(f"[{self.name}] 请求超时超过最大重试次数")
                    
            except requests.exceptions.RequestException as e:
                if current_attempt < 2:
                    wait_time = 2 * (2 ** current_attempt)
                    logger.warning(f"[{self.name}] 请求异常: {e}，{wait_time}秒后重试")
                    time.sleep(wait_time)
                    current_attempt += 1
                    continue
                else:
                    self.stats["errors"] += 1
                    raise
        
        self.stats["errors"] += 1
        raise Exception(f"[{self.name}] 达到最大重试次数")
    
    def _downgrade_model(self) -> None:
        """降级到轻量模型"""
        if self.model == "deepseek-v4-pro":
            old_model = self.model
            self.model = "deepseek-v4-flash"
            self.stats["downgrades"] += 1
            self.params = DEFAULT_PARAMS.get("flash", DEFAULT_PARAMS["flash"]).copy()
            logger.warning(f"[{self.name}] 模型降级: {old_model} → {self.model}")
    
    def chat(
        self,
        user_input: str,
        stream: bool = False,
        temperature: Optional[float] = None,
        auto_checkpoint: bool = True,
        on_chunk: Optional[Callable[[str], None]] = None,
        on_complete: Optional[Callable[[str], None]] = None
    ) -> str:
        """发送对话请求
        
        Args:
            user_input: 用户输入
            stream: 是否流式输出
            temperature: 温度参数
            auto_checkpoint: 是否自动保存检查点
            on_chunk: 流式回调，每收到一个chunk调用一次 (chunk_text) -> None
            on_complete: 完成回调，收到完整响应后调用 (full_text) -> None
        """
        self.messages.append(Message("user", user_input))
        
        # v4.0: chat前自动压缩上下文
        self._pre_chat_compact()
        
        msg_list = [msg.to_dict() for msg in self.messages]
        
        # Phase 7: 应用上下文窗口截断
        msg_list = self._apply_context_window_to_messages(msg_list)
        
        params = {}
        if temperature is not None:
            params["temperature"] = temperature
        else:
            # Quality Dials: 根据旋钮自动调整temperature
            if self.quality_dials:
                gen_params = self.quality_dials.to_generation_params()
                params["temperature"] = gen_params["temperature"]
                params["top_p"] = gen_params["top_p"]
                params["max_tokens"] = gen_params["max_tokens"]
        
        try:
            # Guardrails输入校验
            if self.guardrails:
                input_result = self.guardrails.check_input(user_input)
                if input_result.blocked:
                    logger.warning(f"[{self.name}] Input blocked by guardrail: {input_result.message}")
                    self.messages.pop()
                    return f"[Guardrail] 输入被阻止: {input_result.message}"
                if input_result.action.value == "modify" and input_result.modified_value:
                    user_input = input_result.modified_value
                    # 更新已添加的Message
                    self.messages[-1] = Message("user", user_input)
                    msg_list = [msg.to_dict() for msg in self.messages]
            
            # Tracer
            if self.tracer:
                self.tracer.start_trace()
            
            if stream:
                return self._chat_stream(msg_list, on_chunk=on_chunk, on_complete=on_complete, **params)
            else:
                with self.tracer.span("chat_nonstream") if self.tracer else _nullcontext():
                    result = self._chat_nonstream(msg_list, **params)
                
                # Guardrails输出校验
                if self.guardrails and result:
                    output_result = self.guardrails.check_output(result)
                    if output_result.blocked:
                        logger.warning(f"[{self.name}] Output blocked by guardrail: {output_result.message}")
                        result = f"[Guardrail] 输出被过滤: {output_result.message}"
                    elif output_result.action.value == "modify" and output_result.modified_value:
                        result = output_result.modified_value
                
                # 记录指标
                if self.metrics:
                    self.metrics.increment("chat_requests")
                    self.metrics.record("response_length", len(result))
                
                if on_complete:
                    on_complete(result)
                return result
        except Exception as e:
            self.messages.pop()
            raise e
        finally:
            # 自动检查点
            if auto_checkpoint:
                self._auto_checkpoint()
            
            # v4.1: CheckpointWriter上下文利用率检查
            if hasattr(self, '_checkpoint_writer') and self._checkpoint_writer:
                context_usage = self._estimate_context_usage()
                if self._checkpoint_writer.should_checkpoint(context_usage):
                    # 异步更新检查点
                    self._checkpoint_writer.update_state(
                        current_work=f"最近对话: {user_input[:100]}...",
                    )
    
    def _chat_nonstream(self, messages: List[Dict], **kwargs) -> str:
        """非流式请求"""
        response = self._call_api(messages, stream=False, **kwargs)
        
        assistant_msg = response["choices"][0]["message"]["content"]
        self.messages.append(Message("assistant", assistant_msg))
        
        self.stats["total_requests"] += 1
        if "usage" in response:
            tokens = response["usage"].get("total_tokens", 0)
            self.stats["total_tokens"] += tokens
        
        return assistant_msg
    
    def _chat_stream(
        self,
        messages: List[Dict],
        on_chunk: Optional[Callable[[str], None]] = None,
        on_complete: Optional[Callable[[str], None]] = None,
        **kwargs
    ) -> str:
        """流式请求（支持回调）
        
        Args:
            messages: 消息列表
            on_chunk: 每个chunk的回调 (chunk_text) -> None
            on_complete: 完成回调 (full_text) -> None
        """
        response = self._call_api(messages, stream=True, **kwargs)
        
        full_content = ""
        for line in response.iter_lines():
            if line:
                data = line.decode('utf-8')
                if data.startswith('data: '):
                    data = data[6:]
                if data == '[DONE]':
                    break
                try:
                    obj = json.loads(data)
                    delta = obj["choices"][0].get("delta", {}).get("content", "")
                    if delta:
                        full_content += delta
                        # 优先使用回调，无回调时 fallback 到 print
                        if on_chunk:
                            on_chunk(delta)
                        else:
                            print(delta, end="", flush=True)
                except json.JSONDecodeError:
                    continue
        
        if not on_chunk:
            print()
        
        self.messages.append(Message("assistant", full_content))
        self.stats["total_requests"] += 1
        
        if on_complete:
            on_complete(full_content)
        
        return full_content
    
    def reset(self):
        """重置对话历史"""
        system_msgs = [m for m in self.messages if m.role == "system"]
        self.messages = system_msgs
    
    def get_history(self) -> List[Dict]:
        """获取对话历史"""
        return [msg.to_dict() for msg in self.messages]
    
    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        stats = self.stats.copy()
        if self.quality_dials:
            stats["quality_dials"] = self.quality_dials.to_dict()
        if self.agent_mode:
            stats["agent_mode"] = self.agent_mode.value
        return stats
    
    # ============ Quality Dials + Agent Mode 方法 (Taste-Skill/Impeccable) ============
    
    def set_mode(self, mode: str) -> None:
        """切换Agent行为模式
        
        基础6档只调Dials；科研3档(research/engineering/casual)联动模型、
        审查管道、工具权限、记忆策略、护栏等级——一键折叠7项参数。
        
        Args:
            mode: 模式名称
                基础: "precise"/"creative"/"concise"/"thorough"/"balanced"/"cautious"
                科研: "research"/"engineering"/"casual"
        
        示例:
            agent.set_mode("research")    # 科研：Pro+严格审查+全工具
            agent.set_mode("engineering") # 工程：Pro规划+Flash执行+代码工具
            agent.set_mode("casual")      # 日常：Flash+轻量+快速
        """
        if not _QUALITY_AVAILABLE:
            logger.warning(f"[{self.name}] quality模块不可用，无法切换模式")
            return
        
        try:
            agent_mode = AgentMode(mode)
        except ValueError:
            valid = [m.value for m in AgentMode]
            logger.warning(f"[{self.name}] 未知模式 '{mode}'，可选: {valid}")
            return
        
        self.agent_mode = agent_mode
        self.quality_dials = QualityDials(**MODE_PROFILES[agent_mode].__dict__)
        
        # 科研3档：联动模型+审查+工具+记忆+护栏
        preset = get_research_preset(mode)
        if preset:
            # 模型切换
            self.model = preset.model
            # 审查管道
            if preset.review_pipeline == "strict":
                self.review_pipeline = create_strict_pipeline()
            elif preset.review_pipeline == "quick":
                self.review_pipeline = create_quick_pipeline()
            elif preset.review_pipeline == "none":
                self.review_pipeline = None
            else:
                self.review_pipeline = create_default_pipeline()
            # 自动审查
            self._auto_review = preset.auto_review
            # 工具权限
            self._enabled_tools = preset.enabled_tools  # 空=全部
            # 记忆策略
            self._memory_strategy = preset.memory_strategy
            # 护栏等级
            self._guardrails_level = preset.guardrails_level
            
            logger.info(f"[{self.name}] 科研模式 → {mode} "
                       f"(model={preset.model}, review={preset.review_pipeline}, "
                       f"auto_review={preset.auto_review}, tools={'all' if not preset.enabled_tools else len(preset.enabled_tools)}, "
                       f"memory={preset.memory_strategy}, guardrails={preset.guardrails_level})")
        else:
            logger.info(f"[{self.name}] 切换模式 → {mode} (dials: {self.quality_dials.to_dict()})")
    
    def set_dials(self, **kwargs: float) -> None:
        """手动调整质量旋钮
        
        Args:
            creativity: 创造性 0.0-1.0
            precision:  精确性 0.0-1.0
            verbosity:  详细度 0.0-1.0
            caution:    谨慎度 0.0-1.0
        
        示例:
            agent.set_dials(creativity=0.8, verbosity=0.3)
        """
        if not _QUALITY_AVAILABLE:
            logger.warning(f"[{self.name}] quality模块不可用")
            return
        
        current = self.quality_dials.to_dict() if self.quality_dials else {}
        current.update({k: v for k, v in kwargs.items() if k in ("creativity", "precision", "verbosity", "caution")})
        self.quality_dials = QualityDials(**current)
        self.agent_mode = None  # 手动调整后不再关联预设模式
        logger.info(f"[{self.name}] 旋钮调整: {self.quality_dials.to_dict()}")
    
    def review(self, output: Optional[str] = None, pipeline: Optional[str] = None) -> Dict[str, Any]:
        """对Agent输出执行自检审查
        
        灵感: Impeccable 的 /audit /critique /polish 命令
        
        Args:
            output: 要审查的文本，默认审查最后一条助手消息
            pipeline: 管道类型 "default"/"strict"/"quick"，默认default
        
        Returns:
            {"score": float, "issues": List, "suggestions": List, "revised": Optional[str]}
        """
        if not _QUALITY_AVAILABLE:
            return {"score": 0.0, "issues": ["quality模块不可用"], "suggestions": [], "revised": None}
        
        # 获取待审查文本
        if output is None:
            assistant_msgs = [m for m in self.messages if m.role == "assistant"]
            if not assistant_msgs:
                return {"score": 0.0, "issues": ["无输出可审查"], "suggestions": [], "revised": None}
            output = assistant_msgs[-1].content
        
        # 选择管道
        if pipeline == "strict":
            pipe = create_strict_pipeline()
        elif pipeline == "quick":
            pipe = create_quick_pipeline()
        else:
            pipe = self.review_pipeline or create_default_pipeline()
        
        revised, score, all_issues = pipe.run_with_summary(output)
        
        # 收集建议
        results = pipe.run(output, auto_fix=False)
        suggestions = []
        for r in results:
            suggestions.extend(r.suggestions)
        
        if self.metrics:
            self.metrics.record("review_score", score)
        
        return {
            "score": score,
            "issues": all_issues,
            "suggestions": suggestions,
            "revised": revised if revised != output else None
        }
    
    def chat_with_review(
        self,
        user_input: str,
        stream: bool = False,
        temperature: Optional[float] = None,
        pipeline: Optional[str] = None
    ) -> Tuple[str, Dict[str, Any]]:
        """对话 + 自动自检审查
        
        等价于 chat() + review()，一次性返回回复和审查结果。
        
        Returns:
            (agent_reply, review_result)
        """
        reply = self.chat(user_input, stream=stream, temperature=temperature)
        review_result = self.review(output=reply, pipeline=pipeline)
        return reply, review_result
    
    def load_knowledge(self, file_path: str) -> str:
        """加载知识库文件"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            logger.info(f"[{self.name}] 加载知识库: {file_path}")
            return content
        except Exception as e:
            logger.error(f"[{self.name}] 加载知识库失败: {e}")
            return ""

    # ============ ReAct Agent Loop ============
    
    def react(
        self,
        task: str,
        max_iterations: int = 5,
        tool_manager: Optional[Any] = None,
        on_thought: Optional[Callable[[str], None]] = None,
        on_action: Optional[Callable[[str, Dict], None]] = None,
        on_observation: Optional[Callable[[str], None]] = None
    ) -> str:
        """ReAct推理-行动-观察循环
        
        参考: LangGraph state machine + smolagents agent loop
        执行 Thought -> Action -> Observation 循环，
        每轮通过LLM决定下一步行动，直到给出最终答案。
        """
        if self.tracer:
            self.tracer.start_trace()
        
        prompt = f"""你需要完成以下任务: {task}

请按照 ReAct 格式思考:
Thought: 你的思考过程
Action: 要执行的动作（如果需要）
Action Input: 动作的参数（JSON格式）

如果你已经有了最终答案，请输出:
Thought: 我已经知道答案了
Final Answer: 你的最终答案

开始!"""
        
        history = prompt
        final_answer = None
        
        for iteration in range(max_iterations):
            if self.tracer:
                with self.tracer.span(f"react_iter_{iteration}"):
                    response = self.chat(history, auto_checkpoint=False)
            else:
                response = self.chat(history, auto_checkpoint=False)
            
            thought = self._extract_section(response, "Thought")
            if thought and on_thought:
                on_thought(thought)
            
            final = self._extract_section(response, "Final Answer")
            if final:
                final_answer = final
                break
            
            action_name = self._extract_section(response, "Action")
            action_input_str = self._extract_section(response, "Action Input")
            
            if action_name:
                action_params = {}
                if action_input_str:
                    try:
                        action_params = json.loads(action_input_str)
                    except json.JSONDecodeError:
                        action_params = {"input": action_input_str}
                
                if on_action:
                    on_action(action_name, action_params)
                
                if self.guardrails:
                    tool_result = self.guardrails.check_tool(action_name, action_params)
                    if tool_result.blocked:
                        observation = f"[Guardrail] 动作被阻止: {tool_result.message}"
                    else:
                        observation = self._execute_react_action(action_name, action_params, tool_manager)
                else:
                    observation = self._execute_react_action(action_name, action_params, tool_manager)
                
                if on_observation:
                    on_observation(observation)
                
                history += f"\nObservation: {observation}\n"
            else:
                history += "\n请继续思考，给出Action或Final Answer。\n"
        
        if final_answer is None:
            final_answer = response if response else "未能得出最终答案"
        
        if self.metrics:
            self.metrics.increment("react_completions")
            self.metrics.record("react_iterations", iteration + 1)
        
        if self.tracer:
            self.tracer.log_summary()
        
        return final_answer
    
    def _extract_section(self, text: str, section: str) -> Optional[str]:
        """从LLM输出中提取指定section"""
        import re as _re
        pattern = f"{section}:\\s*(.+?)(?=\\n(Thought|Action|Final Answer|Observation)|$)"
        match = _re.search(pattern, text, _re.DOTALL | _re.IGNORECASE)
        if match:
            return match.group(1).strip()
        lines = text.split('\n')
        for line in lines:
            if line.strip().lower().startswith(section.lower() + ":"):
                return line.split(":", 1)[1].strip()
        return None
    
    def _execute_react_action(
        self,
        action_name: str,
        action_params: Dict,
        tool_manager: Optional[Any] = None
    ) -> str:
        """执行ReAct循环中的动作"""
        if tool_manager:
            tool = tool_manager.get(action_name)
            if tool:
                result = tool.execute(**action_params)
                return str(result.output) if result.success else f"Error: {result.error}"
        
        if self.a2a:
            network = get_a2a_network() if _A2A_AVAILABLE else None
            if network:
                agent_protocol = network.find_agent_by_capability(action_name)
                if agent_protocol:
                    msg = self.a2a.create_task_request(
                        receiver_id=agent_protocol.agent_id,
                        action=action_name,
                        parameters=action_params
                    )
                    response = network.send_message(msg)
                    if response and response.content:
                        return str(response.content)
        
        return f"Action '{action_name}' 未找到可执行的处理器"



    # ============ v4.0 Phase 5: AGI核心能力集成 ============

    def init_agi(
        self,
        strategy_chat: Optional[Any] = None,
        execution_chat: Optional[Any] = None,
    ) -> None:
        """
        初始化Phase 5 AGI核心能力模块

        包括：自主目标分解、元认知、跨领域迁移、持续学习管道
        """
        from autonomous import AutonomousGoalHandler
        from meta_cognition import MetaCognition
        from cross_domain import CrossDomainTransfer
        from continuous_learning import ContinuousLearningPipelineV41 as ContinuousLearningPipeline

        # 确保记忆系统已初始化
        if not hasattr(self, '_memory'):
            self.init_memory()

        # 获取chat函数引用
        _strategy = strategy_chat or self.chat
        _execution = execution_chat or self.chat

        # 1. 自主目标处理器
        self._autonomous = AutonomousGoalHandler(
            strategy_chat=_strategy,
            execution_chat=_execution,
            memory_manager=self._memory if hasattr(self, '_memory') else None,
            sleeptime_engine=self._sleeptime if hasattr(self, '_sleeptime') else None,
            api_endpoint=DEEPSEEK_ENDPOINT,
            api_key=DEEPSEEK_API_KEY,
        )

        # 2. 元认知
        self._meta_cognition = MetaCognition(
            memory_manager=self._memory if hasattr(self, '_memory') else None,
            api_endpoint=DEEPSEEK_ENDPOINT,
            api_key=DEEPSEEK_API_KEY,
        )

        # 3. 跨领域迁移
        self._cross_domain = CrossDomainTransfer(
            memory_manager=self._memory if hasattr(self, '_memory') else None,
            api_endpoint=DEEPSEEK_ENDPOINT,
            api_key=DEEPSEEK_API_KEY,
        )

        # 4. 持续学习管道
        self._continuous_learning = ContinuousLearningPipeline(
            memory_manager=self._memory if hasattr(self, '_memory') else None,
            sleeptime_engine=self._sleeptime if hasattr(self, '_sleeptime') else None,
            meta_cognition=self._meta_cognition,
            api_endpoint=DEEPSEEK_ENDPOINT,
            api_key=DEEPSEEK_API_KEY,
        )

        # v4.1 新增：5. Checkpoint Writer（异步检查点写入器）
        if _CHECKPOINT_WRITER_AVAILABLE:
            self._checkpoint_writer = CheckpointWriter(
                agent_name=self.name,
                storage_dir=f"./data/checkpoints/{self.name}",
                model="flash",
                auto_start=True,
            )
        else:
            self._checkpoint_writer = None
            logger.warning(f"[{self.name}] CheckpointWriter not available")

        # v4.1 新增：6. Goal Verifier（独立目标验证器）
        if _GOAL_VERIFIER_AVAILABLE:
            self._goal_verifier = GoalVerifier(
                model="flash",
                api_endpoint=DEEPSEEK_ENDPOINT,
                api_key=DEEPSEEK_API_KEY,
                max_verifications=3,
            )
        else:
            self._goal_verifier = None
            logger.warning(f"[{self.name}] GoalVerifier not available")

        logger.info(f"[{self.name}] AGI capabilities initialized: autonomous + meta_cognition + cross_domain + continuous_learning + checkpoint_writer + goal_verifier")

    def autonomous(self, goal: str, context: str = "", stop_condition: str = "") -> Dict:
        """
        自主执行目标 — 从模糊意图到完整结果

        Args:
            goal: 用户的高层目标
            context: 额外上下文
            stop_condition: 停止条件（自然语言），用于GoalVerifier验证
        """
        if not hasattr(self, '_autonomous'):
            self.init_agi()
        
        # v4.1: 如果提供了停止条件，定义给GoalVerifier
        if stop_condition and self._goal_verifier:
            self._goal_verifier.define_goal(stop_condition, context=context)
        
        result = self._autonomous.handle(goal, context=context)
        
        # v4.1: 自主执行后自动验证目标
        if stop_condition and self._goal_verifier:
            verification = self._goal_verifier.verify(
                conversation_history=self.messages if hasattr(self, 'messages') else [],
                task_output=result.get("result", "") if isinstance(result, dict) else str(result),
            )
            result["verification"] = verification.to_dict()
            
            # 检查是否应该继续
            should_continue, reason = self._goal_verifier.should_continue(verification)
            result["should_continue"] = should_continue
            result["verification_reason"] = reason
            
            if not should_continue:
                logger.info(f"[{self.name}] Autonomous task complete: {reason}")
        
        return result.to_dict() if hasattr(result, 'to_dict') else result

    def assess_confidence(self, query: str) -> Dict:
        """
        元认知置信度评估 — 知道自己"知道什么"和"不知道什么"

        Args:
            query: 要评估的问题
        """
        if not hasattr(self, '_meta_cognition'):
            self.init_agi()
        assessment = self._meta_cognition.assess_confidence(query)
        return assessment.to_dict()

    def identify_gaps(self, domain: Optional[str] = None) -> List[Dict]:
        """
        识别知识盲区

        Args:
            domain: 限定领域（None=全领域扫描）
        """
        if not hasattr(self, '_meta_cognition'):
            self.init_agi()
        gaps = self._meta_cognition.identify_knowledge_gaps(domain=domain)
        return [g.to_dict() for g in gaps]

    def cross_domain_analogy(self, source: str, target: str, concept: Optional[str] = None) -> List[Dict]:
        """
        跨领域类比发现

        Args:
            source: 源领域
            target: 目标领域
            concept: 限定概念（可选）
        """
        if not hasattr(self, '_cross_domain'):
            self.init_agi()
        analogies = self._cross_domain.find_analogy(source, target, concept)
        return [a.to_dict() for a in analogies]

    def learn_from_interaction(
        self,
        query: str,
        response: str,
        outcome: str = "neutral",
        feedback: str = "",
        domain: str = "general",
    ) -> Dict:
        """
        从交互中学习

        Args:
            query: 用户问题
            response: Agent回答
            outcome: "positive"/"negative"/"neutral"/"corrected"
            feedback: 用户反馈
            domain: 领域
        """
        if not hasattr(self, '_continuous_learning'):
            self.init_agi()

        from continuous_learning import InteractionOutcome
        outcome_map = {
            "positive": InteractionOutcome.POSITIVE,
            "negative": InteractionOutcome.NEGATIVE,
            "neutral": InteractionOutcome.NEUTRAL,
            "corrected": InteractionOutcome.CORRECTED,
        }
        outcome_enum = outcome_map.get(outcome, InteractionOutcome.NEUTRAL)

        result = self._continuous_learning.on_interaction(
            query=query,
            response=response,
            outcome=outcome_enum,
            feedback=feedback,
            domain=domain,
        )
        return result.to_dict()

    def periodic_learn(self, force: bool = False) -> Dict:
        """
        触发定期深度学习（Sleeptime整合）

        Args:
            force: 是否强制执行
        """
        if not hasattr(self, '_continuous_learning'):
            self.init_agi()
        result = self._continuous_learning.on_periodic(force=force)
        return result.to_dict()

    # ============ v4.1: 新增公开方法 ============

    def verify_goal(self, goal_condition: str) -> Dict:
        """
        验证目标是否完成（手动触发GoalVerifier）

        Args:
            goal_condition: 自然语言描述的停止条件

        Returns:
            验证结果
        """
        if not hasattr(self, '_goal_verifier'):
            self.init_agi()
        
        if not self._goal_verifier:
            return {"error": "GoalVerifier not available"}
        
        # 定义目标
        self._goal_verifier.define_goal(goal_condition)
        
        # 执行验证
        result = self._goal_verifier.verify(
            conversation_history=self.messages if hasattr(self, 'messages') else [],
        )
        
        return result.to_dict()

    def dream_cycle(self, force: bool = False) -> Dict:
        """
        触发7天周期深度整合（Dream Cycle）

        区别于on_periodic（按小时执行），dream_cycle是深度整合：
        - 路径有效性验证
        - 去重压缩
        - 重要性衰减加速

        Args:
            force: 是否强制执行

        Returns:
            DreamCycleResult
        """
        if not hasattr(self, '_continuous_learning'):
            self.init_agi()
        
        if hasattr(self._continuous_learning, 'dream_cycle'):
            result = self._continuous_learning.dream_cycle(force=force)
            return result.to_dict()
        else:
            return {"error": "dream_cycle not available in this version"}

    def distill(self, force: bool = False) -> Dict:
        """
        触发30天经验沉淀（Distill）

        识别重复工作模式，固化成可复用的skill/规则/SOP。

        Args:
            force: 是否强制执行

        Returns:
            DistillResult
        """
        if not hasattr(self, '_continuous_learning'):
            self.init_agi()
        
        if hasattr(self._continuous_learning, 'distill'):
            result = self._continuous_learning.distill(force=force)
            return result.to_dict()
        else:
            return {"error": "distill not available in this version"}

    def append_checkpoint_note(self, category: str, content: str) -> None:
        """
        追加笔记到checkpoint（主Agent调用）

        Args:
            category: 分类（intent/next/constraint/task/work/file/discovery/error/runtime/decision/note）
            content: 笔记内容
        """
        if not hasattr(self, '_checkpoint_writer'):
            self.init_agi()
        
        if self._checkpoint_writer:
            self._checkpoint_writer.append_note(category, content)

    def update_checkpoint(self, **kwargs) -> None:
        """
        更新检查点状态（异步写入）

        Args:
            current_intent: 当前意图
            next_action: 下一步动作
            working_constraints: 工作约束列表
            task_tree: 任务树字典
            current_work: 当前工作描述
            involved_files: 涉及文件列表
            cross_task_discoveries: 跨任务发现列表
            errors_and_fixes: 错误修复列表
            runtime_state: 运行时状态字典
            design_decisions: 设计决策列表
            misc_notes: 杂项笔记列表
        """
        if not hasattr(self, '_checkpoint_writer'):
            self.init_agi()
        
        if self._checkpoint_writer:
            self._checkpoint_writer.update_state(**kwargs)

    def agi_status(self) -> Dict:
        """获取AGI核心能力状态"""
        initialized = hasattr(self, '_autonomous')

        result = {
            "initialized": initialized,
            "modules": {
                "autonomous": hasattr(self, '_autonomous'),
                "meta_cognition": hasattr(self, '_meta_cognition'),
                "cross_domain": hasattr(self, '_cross_domain'),
                "continuous_learning": hasattr(self, '_continuous_learning'),
                "agentos": hasattr(self, '_agentos'),
                # v4.1 新增
                "checkpoint_writer": hasattr(self, '_checkpoint_writer') and self._checkpoint_writer is not None,
                "goal_verifier": hasattr(self, '_goal_verifier') and self._goal_verifier is not None,
            },
        }

        if hasattr(self, '_autonomous'):
            result["autonomous_stats"] = self._autonomous.get_stats()
        if hasattr(self, '_meta_cognition'):
            result["meta_stats"] = self._meta_cognition.get_stats()
        if hasattr(self, '_cross_domain'):
            result["cross_domain_stats"] = self._cross_domain.get_stats()
        if hasattr(self, '_continuous_learning'):
            result["learning_stats"] = self._continuous_learning.get_stats()
        # v4.1 新增模块统计
        if hasattr(self, '_checkpoint_writer') and self._checkpoint_writer:
            result["checkpoint_writer_stats"] = self._checkpoint_writer.get_stats()
        if hasattr(self, '_goal_verifier') and self._goal_verifier:
            result["goal_verifier_stats"] = self._goal_verifier.get_stats()

        return result

    def start_agentos(self, host: str = "127.0.0.1", port: int = 9090, mode: str = "http") -> None:
        """
        启动AgentOS运行时

        Args:
            host: 监听地址
            port: 监听端口
            mode: "http" 或 "stdio"
        """
        from agentos import AgentOS

        if not hasattr(self, '_agentos'):
            self._agentos = AgentOS(
                agent=self,
                memory_manager=self._memory if hasattr(self, '_memory') else None,
                sleeptime_engine=self._sleeptime if hasattr(self, '_sleeptime') else None,
                meta_cognition=self._meta_cognition if hasattr(self, '_meta_cognition') else None,
                continuous_learning=self._continuous_learning if hasattr(self, '_continuous_learning') else None,
                autonomous_handler=self._autonomous if hasattr(self, '_autonomous') else None,
                cross_domain=self._cross_domain if hasattr(self, '_cross_domain') else None,
                host=host,
                port=port,
            )

        # 非阻塞启动（在后台线程中运行）
        import threading
        server_thread = threading.Thread(
            target=self._agentos.run,
            kwargs={"host": host, "port": port, "mode": mode},
            daemon=True,
        )
        server_thread.start()
        logger.info(f"[{self.name}] AgentOS started on {host}:{port} ({mode})")
