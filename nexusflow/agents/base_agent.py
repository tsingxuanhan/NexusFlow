# -*- coding: utf-8 -*-
"""
铉枢·炉守 基础Agent类
XuanHub Base Agent Class
v4.0 - Generalization Foundation: Plan/Execute/Reflect + ContextCompactor + TodoProvider + PRO/Flash Auto-switch

Refactored: BaseAgent now inherits from Mixin classes;
           data classes/enums extracted to models.py;
           all backward-compatible re-exports are at the bottom of this file.
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

# 从 models 导入基础数据类
from .models import (
    _nullcontext, Message, AgentRole, AgentRunMode,
    TodoItem, TodoProvider, ContextCompactor,
    ROLE_MODEL_MAP, MODE_MODEL_MAP,
)

# 导入Mixin
from .reasoning_mixin import ReasoningMixin
from .codeact_mixin import CodeActMixin
from .memory_mixin import MemoryMixin
from .checkpoint_mixin import CheckpointMixin
from .handoff_mixin import HandoffMixin
from .agi_mixin import AGIMixin

# 导入配置 — 优先从 config/config.yaml 加载，回退到 config.py（向后兼容）
import os as _os
_config = {}
_config_path = _os.path.join(_os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))), 'config', 'config.yaml')
if _os.path.exists(_config_path):
    try:
        import yaml
        with open(_config_path, 'r', encoding='utf-8') as _f:
            _config = yaml.safe_load(_f) or {}
    except (ImportError, Exception):
        _config = {}

# 从 YAML 配置提取常用变量（优先 YAML > config.py > 环境变量 > 默认值）
DEEPSEEK_API_KEY = (_config.get('models', {}).get('pro', {}).get('name')
                    if False else "")  # placeholder, env var takes priority
try:
    from config import *  # noqa: F401,F403 — 向后兼容旧的 config.py
except ImportError:
    pass

DEEPSEEK_API_KEY = _os.environ.get("DEEPSEEK_API_KEY", DEEPSEEK_API_KEY if 'DEEPSEEK_API_KEY' in dir() else "")
DEEPSEEK_ENDPOINT = _os.environ.get("DEEPSEEK_ENDPOINT", "https://api.deepseek.com/v1/chat/completions")
MODELS = {"pro": _config.get('models', {}).get('pro', {}).get('name', 'deepseek-v4-pro'),
          "flash": _config.get('models', {}).get('flash', {}).get('name', 'deepseek-v4-flash')}
DEFAULT_PARAMS = {
    "pro": {
        "temperature": _config.get('models', {}).get('pro', {}).get('temperature', 1.0),
        "top_p": _config.get('models', {}).get('pro', {}).get('top_p', 1.0),
        "max_tokens": _config.get('models', {}).get('pro', {}).get('max_tokens', 4096),
    },
    "flash": {
        "temperature": _config.get('models', {}).get('flash', {}).get('temperature', 1.0),
        "top_p": _config.get('models', {}).get('flash', {}).get('top_p', 1.0),
        "max_tokens": _config.get('models', {}).get('flash', {}).get('max_tokens', 2048),
    }
}
REQUEST_TIMEOUT = _config.get('api', {}).get('timeout', 120)

# 导入增强模块
from .checkpoint import (
    CheckpointManager, 
    MemoryCheckpointer,
    SqliteCheckpointer,
    get_default_manager as get_checkpoint_manager
)
from .handoff import (
    HandoffManager,
    Handoff,
    HandoffContext,
    HandoffResult,
    HandoffPolicy,
    create_handoff,
    get_handoff_manager
)
from .circuit_breaker import (
    get_circuit_breaker, 
    CircuitBreakerConfig, 
    CircuitBreakerOpenError
)

# 导入A2A协议 (延迟导入避免循环依赖)
_A2A_AVAILABLE = True
try:
    from nexusflow.protocol.a2a_protocol import A2AProtocol, A2AMessageType, TaskStatus, get_a2a_network
except ImportError:
    _A2A_AVAILABLE = False

# 导入Guardrails
_GUARDRAILS_AVAILABLE = True
try:
    from .guardrails import GuardrailManager, GuardrailResult, GuardrailAction, create_default_guardrails
except ImportError:
    _GUARDRAILS_AVAILABLE = False

# 导入Quality模块 (Taste-Skill旋钮 + Impeccable自检)
_QUALITY_AVAILABLE = True
try:
    from .quality import (
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
    from .observability import AgentTracer, MetricsCollector
except ImportError:
    _OBSERVABILITY_AVAILABLE = False

# v4.1 新增：导入 CheckpointWriter 和 GoalVerifier
_CHECKPOINT_WRITER_AVAILABLE = True
_GOAL_VERIFIER_AVAILABLE = True
try:
    from .checkpoint_writer import CheckpointWriter
    from nexusflow.core.goal_verifier import GoalVerifier
except ImportError:
    _CHECKPOINT_WRITER_AVAILABLE = False
    _GOAL_VERIFIER_AVAILABLE = False

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("BaseAgent")


# ============================================================================
# BaseAgent — 继承所有Mixin，保留核心逻辑
# ============================================================================

class BaseAgent(ReasoningMixin, CodeActMixin, MemoryMixin, CheckpointMixin, HandoffMixin, AGIMixin):
    """
    DeepSeek API基础Agent类
    v3.0 - 增强版
    
    新增功能:
    - Checkpoint检查点持久化
    - Handoff任务移交
    - Pydantic工具类型支持
    
    架构重构 (v4.0+):
    - BaseAgent 继承 ReasoningMixin, CodeActMixin, MemoryMixin, CheckpointMixin, HandoffMixin, AGIMixin
    - 数据类/枚举提取到 models.py
    - 所有外部 import 向后兼容（见文件底部 re-exports）
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
        from nexusflow.protocol.a2a_protocol import A2AProtocol
        
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


# ============================================================================
# Backward compatibility re-exports
# 所有 `from nexusflow.agents.base_agent import XXX` 必须继续工作
# ============================================================================
from .models import (  # noqa: E402, F401
    Message, AgentRole, AgentRunMode, TodoItem, TodoProvider,
    ContextCompactor, ROLE_MODEL_MAP, MODE_MODEL_MAP,
)
