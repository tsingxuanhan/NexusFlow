# -*- coding: utf-8 -*-
"""
铉枢·炉守 基础Agent类
XuanHub Base Agent Class
v3.0 - Enhanced with Checkpoint & Handoff + Pydantic Tools
"""

import time
import json
import logging
from typing import List, Dict, Optional, Any, Iterator, Union, TYPE_CHECKING
from dataclasses import dataclass, field
from datetime import datetime

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
        # 新增参数
        thread_id: Optional[str] = None,
        checkpoint_manager: Optional[CheckpointManager] = None,
        handoff_manager: Optional[HandoffManager] = None,
        enable_checkpoint: bool = True,
        checkpoint_interval: int = 5
    ):
        self.name = name
        self.model = MODELS[model] if model in MODELS else model
        self.original_model = self.model  # 保存原始模型用于重置
        self.api_key = api_key or DEEPSEEK_API_KEY
        self.endpoint = endpoint or DEEPSEEK_ENDPOINT
        self.params = DEFAULT_PARAMS.get(model, DEFAULT_PARAMS["pro"]).copy()
        
        # 对话历史
        self.messages: List[Message] = []
        
        # 初始化system prompt
        if system_prompt:
            self.messages.append(Message("system", system_prompt))
        
        # 统计信息
        self.stats = {
            "total_requests": 0,
            "total_tokens": 0,
            "errors": 0,
            "downgrades": 0  # 降级次数
        }
        
        # 错误恢复配置
        self.auto_downgrade = auto_downgrade
        self._error_counts = {}  # 错误类型计数
        
        # ============ 新增: Checkpoint支持 ============
        self.thread_id = thread_id or f"{name}_{id(self)}"
        self.enable_checkpoint = enable_checkpoint
        self.checkpoint_interval = checkpoint_interval
        self._message_counter = 0  # 消息计数器
        
        if checkpoint_manager:
            self.checkpoint_manager = checkpoint_manager
        else:
            self.checkpoint_manager = get_checkpoint_manager()
        
        # ============ 新增: Handoff支持 ============
        self.handoff_manager = handoff_manager or get_handoff_manager()
        self.available_handoffs: List[Handoff] = []
        
        logger.info(f"[{self.name}] Agent initialized (thread_id={self.thread_id}, checkpoint={enable_checkpoint})")
    
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
            if not handoff:
                raise ValueError(f"Unknown handoff: {target}")
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
        auto_checkpoint: bool = True
    ) -> str:
        """发送对话请求"""
        self.messages.append(Message("user", user_input))
        
        msg_list = [msg.to_dict() for msg in self.messages]
        
        params = {}
        if temperature is not None:
            params["temperature"] = temperature
        
        try:
            if stream:
                return self._chat_stream(msg_list, **params)
            else:
                return self._chat_nonstream(msg_list, **params)
        except Exception as e:
            self.messages.pop()
            raise e
        finally:
            # 自动检查点
            if auto_checkpoint:
                self._auto_checkpoint()
    
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
    
    def _chat_stream(self, messages: List[Dict], **kwargs) -> str:
        """流式请求"""
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
                        print(delta, end="", flush=True)
                except json.JSONDecodeError:
                    continue
        
        print()
        self.messages.append(Message("assistant", full_content))
        self.stats["total_requests"] += 1
        
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
        return self.stats.copy()
    
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
