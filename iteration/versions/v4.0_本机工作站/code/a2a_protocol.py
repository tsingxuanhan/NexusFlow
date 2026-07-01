# -*- coding: utf-8 -*-
"""
铉枢·炉守 Agent-to-Agent (A2A) 协议
XuanHub A2A Protocol - Multi-Agent Communication Standard
参考: Microsoft Agent Framework + CrewAI A2A + OpenAgents Protocol
https://agentprotocol.ai
"""

import logging
import json
import uuid
from typing import Any, Dict, List, Optional, Callable, Union
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime

logger = logging.getLogger("A2AProtocol")


class A2AMessageType(Enum):
    """A2A消息类型"""
    # 任务相关
    TASK_REQUEST = "task_request"         # 任务请求
    TASK_RESPONSE = "task_response"       # 任务响应
    TASK_UPDATE = "task_update"          # 任务状态更新
    TASK_CANCEL = "task_cancel"          # 取消任务
    
    # 协作相关
    HANDOVER = "handover"               # 任务交接
    CONSULT = "consult"                 # 咨询请求
    CONSULT_RESPONSE = "consult_response"  # 咨询响应
    
    # 能力相关
    CAPABILITY_QUERY = "capability_query"   # 能力查询
    CAPABILITY_RESPONSE = "capability_response"  # 能力响应
    
    # 系统相关
    HEARTBEAT = "heartbeat"             # 心跳
    ERROR = "error"                     # 错误通知


class TaskStatus(Enum):
    """任务状态"""
    PENDING = "pending"
    RUNNING = "running"
    WAITING = "waiting"      # 等待其他Agent
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class A2ACapability:
    """Agent能力描述"""
    name: str                           # 能力名称
    description: str                    # 能力描述
    input_types: List[str] = field(default_factory=list)  # 输入类型
    output_types: List[str] = field(default_factory=list)  # 输出类型
    keywords: List[str] = field(default_factory=list)    # 触发关键词


@dataclass
class AgentInfo:
    """Agent信息"""
    agent_id: str
    name: str
    role: str
    capabilities: List[A2ACapability] = field(default_factory=list)
    status: str = "online"
    metadata: Dict = field(default_factory=dict)


@dataclass
class A2AMessage:
    """A2A消息"""
    message_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    message_type: A2AMessageType = A2AMessageType.TASK_REQUEST
    sender_id: str = ""
    sender_name: str = ""
    receiver_id: str = ""
    
    # 任务信息
    task_id: Optional[str] = None
    session_id: Optional[str] = None
    
    # 内容
    content: Any = None
    action: str = ""                    # 操作名称
    parameters: Dict = field(default_factory=dict)
    
    # 状态
    status: Optional[TaskStatus] = None
    progress: float = 0.0               # 0.0-1.0
    
    # 上下文传递
    context: Dict = field(default_factory=dict)  # 传递的状态
    history: List[Dict] = field(default_factory=list)  # 对话历史
    
    # 元数据
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    expires_at: Optional[str] = None    # 过期时间
    metadata: Dict = field(default_factory=dict)
    
    def to_dict(self) -> Dict:
        return {
            "message_id": self.message_id,
            "message_type": self.message_type.value,
            "sender_id": self.sender_id,
            "sender_name": self.sender_name,
            "receiver_id": self.receiver_id,
            "task_id": self.task_id,
            "session_id": self.session_id,
            "content": self.content,
            "action": self.action,
            "parameters": self.parameters,
            "status": self.status.value if self.status else None,
            "progress": self.progress,
            "context": self.context,
            "history": self.history,
            "timestamp": self.timestamp,
            "expires_at": self.expires_at,
            "metadata": self.metadata
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'A2AMessage':
        data = data.copy()
        if "message_type" in data:
            data["message_type"] = A2AMessageType(data["message_type"])
        if "status" in data and data["status"]:
            data["status"] = TaskStatus(data["status"])
        return cls(**data)


@dataclass
class Task:
    """A2A任务"""
    task_id: str
    task_type: str
    description: str
    
    # 参与者
    initiator_id: str = ""
    owner_id: str = ""              # 当前处理者
    participants: List[str] = field(default_factory=list)  # 所有参与者
    
    # 状态
    status: TaskStatus = TaskStatus.PENDING
    progress: float = 0.0
    
    # 消息历史
    messages: List[A2AMessage] = field(default_factory=list)
    
    # 结果
    result: Any = None
    error: Optional[str] = None
    
    # 时间
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat())
    completed_at: Optional[str] = None
    
    def to_dict(self) -> Dict:
        return {
            "task_id": self.task_id,
            "task_type": self.task_type,
            "description": self.description,
            "initiator_id": self.initiator_id,
            "owner_id": self.owner_id,
            "participants": self.participants,
            "status": self.status.value,
            "progress": self.progress,
            "messages": [m.to_dict() for m in self.messages],
            "result": self.result,
            "error": self.error,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "completed_at": self.completed_at
        }


class A2AProtocol:
    """
    A2A协议处理器
    
    支持:
    - 任务请求/响应
    - 任务交接 (Handover)
    - 咨询请求 (Consult)
    - 能力发现
    - 任务状态追踪
    
    用法:
        protocol = A2AProtocol(my_agent)
        
        # 注册能力
        protocol.register_capability(
            name="literature_search",
            description="搜索学术论文",
            keywords=["论文", "研究", "paper", "search"]
        )
        
        # 发送任务请求
        msg = protocol.create_task_request(
            receiver_id="assayer",
            action="verify_entry",
            parameters={"entry": "SSC的主要成分是矿渣"}
        )
        
        # 处理接收到的消息
        response = protocol.handle_message(received_message)
    """
    
    def __init__(self, agent_id: str, agent_name: str, agent_role: str = ""):
        self.agent_id = agent_id
        self.agent_name = agent_name
        self.agent_role = agent_role
        
        # 能力注册
        self._capabilities: Dict[str, A2ACapability] = {}
        
        # 任务管理
        self._tasks: Dict[str, Task] = {}
        
        # 消息路由
        self._handlers: Dict[A2AMessageType, Callable] = {}
        
        # 注册默认处理器
        self._register_default_handlers()
        
        logger.info(f"[A2AProtocol] Agent '{agent_name}' ({agent_id}) initialized")
    
    def _register_default_handlers(self) -> None:
        """注册默认消息处理器"""
        self._handlers[A2AMessageType.TASK_REQUEST] = self._handle_task_request
        self._handlers[A2AMessageType.TASK_RESPONSE] = self._handle_task_response
        self._handlers[A2AMessageType.HANDOVER] = self._handle_handover
        self._handlers[A2AMessageType.CONSULT] = self._handle_consult
        self._handlers[A2AMessageType.CAPABILITY_QUERY] = self._handle_capability_query
    
    def register_capability(
        self,
        name: str,
        description: str,
        input_types: Optional[List[str]] = None,
        output_types: Optional[List[str]] = None,
        keywords: Optional[List[str]] = None
    ) -> None:
        """注册Agent能力"""
        capability = A2ACapability(
            name=name,
            description=description,
            input_types=input_types or [],
            output_types=output_types or [],
            keywords=keywords or []
        )
        self._capabilities[name] = capability
        logger.debug(f"[A2AProtocol] Registered capability: {name}")
    
    def get_capabilities(self) -> List[A2ACapability]:
        """获取所有能力"""
        return list(self._capabilities.values())
    
    def find_capability(self, query: str) -> Optional[A2ACapability]:
        """根据查询找到匹配的能力"""
        query_lower = query.lower()
        
        # 精确匹配关键词
        for cap in self._capabilities.values():
            for keyword in cap.keywords:
                if keyword.lower() in query_lower:
                    return cap
        
        # 模糊匹配描述
        for cap in self._capabilities.values():
            if query_lower in cap.description.lower():
                return cap
        
        return None
    
    # ============ 消息创建 ============
    
    def create_message(
        self,
        message_type: A2AMessageType,
        receiver_id: str,
        content: Any = None,
        **kwargs
    ) -> A2AMessage:
        """创建A2A消息"""
        return A2AMessage(
            message_type=message_type,
            sender_id=self.agent_id,
            sender_name=self.agent_name,
            receiver_id=receiver_id,
            content=content,
            **kwargs
        )
    
    def create_task_request(
        self,
        receiver_id: str,
        action: str,
        parameters: Optional[Dict] = None,
        task_id: Optional[str] = None,
        session_id: Optional[str] = None
    ) -> A2AMessage:
        """创建任务请求消息"""
        return self.create_message(
            message_type=A2AMessageType.TASK_REQUEST,
            receiver_id=receiver_id,
            action=action,
            parameters=parameters or {},
            task_id=task_id or str(uuid.uuid4())[:8],
            session_id=session_id
        )
    
    def create_handover(
        self,
        receiver_id: str,
        original_task: str,
        context: Optional[Dict] = None,
        history: Optional[List[Dict]] = None
    ) -> A2AMessage:
        """创建任务交接消息"""
        return self.create_message(
            message_type=A2AMessageType.HANDOVER,
            receiver_id=receiver_id,
            content=original_task,
            context=context or {},
            history=history or []
        )
    
    def create_consult(
        self,
        receiver_id: str,
        question: str,
        parameters: Optional[Dict] = None
    ) -> A2AMessage:
        """创建咨询请求消息"""
        return self.create_message(
            message_type=A2AMessageType.CONSULT,
            receiver_id=receiver_id,
            content=question,
            parameters=parameters or {}
        )
    
    # ============ 消息处理 ============
    
    def handle_message(self, message: Union[A2AMessage, Dict]) -> Optional[A2AMessage]:
        """
        处理接收到的A2A消息
        
        Args:
            message: A2AMessage对象或字典
            
        Returns:
            响应消息
        """
        if isinstance(message, Dict):
            message = A2AMessage.from_dict(message)
        
        logger.info(
            f"[A2AProtocol] Handling {message.message_type.value} "
            f"from {message.sender_name} ({message.sender_id})"
        )
        
        # 查找处理器
        handler = self._handlers.get(message.message_type)
        
        if handler:
            try:
                response = handler(message)
                return response
            except Exception as e:
                logger.error(f"[A2AProtocol] Handler error: {e}")
                return self.create_error_response(message, str(e))
        else:
            logger.warning(f"[A2AProtocol] No handler for {message.message_type.value}")
            return None
    
    def _handle_task_request(self, message: A2AMessage) -> A2AMessage:
        """处理任务请求"""
        action = message.action
        
        # 查找匹配的能力
        capability = self.find_capability(action)
        
        if not capability:
            return self.create_message(
                message_type=A2AMessageType.TASK_RESPONSE,
                receiver_id=message.sender_id,
                content=None,
                status=TaskStatus.FAILED,
                metadata={"error": f"Cannot handle action: {action}"}
            )
        
        # 执行任务
        result = self._execute_action(action, message.parameters)
        
        return self.create_message(
            message_type=A2AMessageType.TASK_RESPONSE,
            receiver_id=message.sender_id,
            task_id=message.task_id,
            content=result,
            status=TaskStatus.COMPLETED if result else TaskStatus.FAILED
        )
    
    def _handle_task_response(self, message: A2AMessage) -> Optional[A2AMessage]:
        """处理任务响应"""
        # 更新任务状态
        task_id = message.task_id
        if task_id in self._tasks:
            task = self._tasks[task_id]
            task.status = message.status or TaskStatus.COMPLETED
            task.result = message.content
            task.updated_at = datetime.now().isoformat()
            
            if task.status == TaskStatus.COMPLETED:
                task.completed_at = datetime.now().isoformat()
        
        logger.info(f"[A2AProtocol] Task {task_id} response received: {task.status.value}")
        return None
    
    def _handle_handover(self, message: A2AMessage) -> A2AMessage:
        """处理任务交接"""
        # 确认接收
        return self.create_message(
            message_type=A2AMessageType.TASK_RESPONSE,
            receiver_id=message.sender_id,
            content={
                "accepted": True,
                "task": message.content,
                "context_keys": list(message.context.keys()) if message.context else []
            },
            status=TaskStatus.RUNNING
        )
    
    def _handle_consult(self, message: A2AMessage) -> A2AMessage:
        """处理咨询请求"""
        question = message.content
        
        # 使用Agent能力回答
        answer = self._answer_consult(question, message.parameters)
        
        return self.create_message(
            message_type=A2AMessageType.CONSULT_RESPONSE,
            receiver_id=message.sender_id,
            content=answer
        )
    
    def _handle_capability_query(self, message: A2AMessage) -> A2AMessage:
        """处理能力查询"""
        return self.create_message(
            message_type=A2AMessageType.CAPABILITY_RESPONSE,
            receiver_id=message.sender_id,
            content={
                "agent_id": self.agent_id,
                "agent_name": self.agent_name,
                "role": self.agent_role,
                "capabilities": [c.name for c in self.get_capabilities()]
            }
        )
    
    def create_error_response(
        self,
        original: A2AMessage,
        error: str
    ) -> A2AMessage:
        """创建错误响应"""
        return self.create_message(
            message_type=A2AMessageType.ERROR,
            receiver_id=original.sender_id,
            task_id=original.task_id,
            content={"error": error},
            status=TaskStatus.FAILED
        )
    
    # ============ 任务管理 ============
    
    def create_task(
        self,
        task_type: str,
        description: str,
        participants: Optional[List[str]] = None
    ) -> Task:
        """创建任务"""
        task = Task(
            task_id=str(uuid.uuid4())[:8],
            task_type=task_type,
            description=description,
            initiator_id=self.agent_id,
            owner_id=self.agent_id,
            participants=participants or []
        )
        
        self._tasks[task.task_id] = task
        logger.info(f"[A2AProtocol] Created task {task.task_id}: {description}")
        
        return task
    
    def get_task(self, task_id: str) -> Optional[Task]:
        """获取任务"""
        return self._tasks.get(task_id)
    
    def update_task_status(
        self,
        task_id: str,
        status: TaskStatus,
        progress: Optional[float] = None
    ) -> None:
        """更新任务状态"""
        task = self._tasks.get(task_id)
        
        if task:
            task.status = status
            if progress is not None:
                task.progress = progress
            task.updated_at = datetime.now().isoformat()
            
            logger.debug(f"[A2AProtocol] Task {task_id} status: {status.value}")
    
    # ============ 辅助方法 (子类可重写) ============
    
    def _execute_action(self, action: str, parameters: Dict) -> Any:
        """执行动作 (子类应重写)"""
        logger.warning(f"[A2AProtocol] No executor for action: {action}")
        return None
    
    def _answer_consult(self, question: str, parameters: Dict) -> str:
        """回答咨询 (子类应重写)"""
        return f"咨询已收到: {question}"


# ============ A2A Agent Network ============

class A2ANetwork:
    """
    A2A Agent网络
    
    管理多个Agent之间的通信，支持：
    - 中心式消息路由（原有）
    - P2P直连通道（新增）
    """
    
    def __init__(self):
        self._agents: Dict[str, A2AProtocol] = {}
        self._message_queue: List[A2AMessage] = []
        
        # P2P通道：key = frozenset(agent_id_a, agent_id_b)
        self._p2p_channels: Dict[frozenset, 'P2PChannel'] = {}
        
        logger.info("[A2ANetwork] Initialized")
    
    def register(self, protocol: A2AProtocol) -> None:
        """注册Agent到网络"""
        self._agents[protocol.agent_id] = protocol
        logger.info(f"[A2ANetwork] Registered agent: {protocol.agent_name}")
    
    def unregister(self, agent_id: str) -> None:
        """从网络注销Agent"""
        if agent_id in self._agents:
            del self._agents[agent_id]
            # 清理相关的P2P通道
            to_remove = [k for k in self._p2p_channels if agent_id in k]
            for key in to_remove:
                del self._p2p_channels[key]
            logger.info(f"[A2ANetwork] Unregistered agent: {agent_id}")
    
    def get_agent(self, agent_id: str) -> Optional[A2AProtocol]:
        """获取Agent"""
        return self._agents.get(agent_id)
    
    def find_agent_by_capability(self, query: str) -> Optional[A2AProtocol]:
        """根据能力查找Agent"""
        for agent in self._agents.values():
            if agent.find_capability(query):
                return agent
        return None
    
    def send_message(self, message: Union[A2AMessage, Dict]) -> Optional[A2AMessage]:
        """发送消息"""
        if isinstance(message, Dict):
            message = A2AMessage.from_dict(message)
        
        receiver = self._agents.get(message.receiver_id)
        
        if not receiver:
            logger.error(f"[A2ANetwork] Unknown receiver: {message.receiver_id}")
            return None
        
        return receiver.handle_message(message)
    
    def broadcast(
        self,
        sender_id: str,
        message_type: A2AMessageType,
        content: Any = None,
        filter_capability: Optional[str] = None
    ) -> List[A2AMessage]:
        """广播消息"""
        responses = []
        
        for agent_id, agent in self._agents.items():
            if agent_id == sender_id:
                continue
            
            # 能力过滤
            if filter_capability and not agent.find_capability(filter_capability):
                continue
            
            message = A2AMessage(
                message_type=message_type,
                sender_id=sender_id,
                receiver_id=agent_id,
                content=content
            )
            
            response = agent.handle_message(message)
            if response:
                responses.append(response)
        
        return responses
    
    # ============ P2P 直连通道 ============
    
    def establish_p2p(
        self,
        agent_id_a: str,
        agent_id_b: str,
        channel_type: str = "direct",
        max_queue_size: int = 100,
        ttl_seconds: Optional[float] = None
    ) -> Optional['P2PChannel']:
        """建立两个Agent之间的P2P直连通道
        
        Args:
            agent_id_a: Agent A的ID
            agent_id_b: Agent B的ID
            channel_type: 通道类型 ("direct" | "buffered" | "priority")
            max_queue_size: 缓冲区大小（仅buffered/priority类型）
            ttl_seconds: 通道存活时间（秒），None表示永久
            
        Returns:
            P2PChannel实例，失败返回None
        """
        if agent_id_a not in self._agents or agent_id_b not in self._agents:
            logger.error(
                f"[A2ANetwork] Cannot establish P2P: "
                f"agent {agent_id_a if agent_id_a not in self._agents else agent_id_b} not registered"
            )
            return None
        
        key = frozenset([agent_id_a, agent_id_b])
        
        if key in self._p2p_channels:
            logger.debug(f"[A2ANetwork] P2P channel already exists, refreshing")
            self._p2p_channels[key].refresh(ttl_seconds)
            return self._p2p_channels[key]
        
        channel = P2PChannel(
            agent_id_a=agent_id_a,
            agent_id_b=agent_id_b,
            channel_type=channel_type,
            max_queue_size=max_queue_size,
            ttl_seconds=ttl_seconds
        )
        
        self._p2p_channels[key] = channel
        logger.info(
            f"[A2ANetwork] P2P channel established: "
            f"{agent_id_a} <-> {agent_id_b} (type={channel_type})"
        )
        
        return channel
    
    def get_p2p_channel(self, agent_id_a: str, agent_id_b: str) -> Optional['P2PChannel']:
        """获取两个Agent之间的P2P通道"""
        key = frozenset([agent_id_a, agent_id_b])
        return self._p2p_channels.get(key)
    
    def send_p2p(
        self,
        sender_id: str,
        receiver_id: str,
        content: Any,
        message_type: A2AMessageType = A2AMessageType.TASK_REQUEST,
        priority: int = 0,
        **kwargs
    ) -> Optional[A2AMessage]:
        """通过P2P通道发送消息（低延迟直连）
        
        如果P2P通道存在，走通道直接投递；
        否则 fallback 到标准 send_message。
        
        Args:
            sender_id: 发送者ID
            receiver_id: 接收者ID
            content: 消息内容
            message_type: 消息类型
            priority: 优先级（0=普通，1=高优先）
            
        Returns:
            响应消息
        """
        key = frozenset([sender_id, receiver_id])
        channel = self._p2p_channels.get(key)
        
        if channel and channel.is_active():
            # P2P直连：创建消息并通过通道投递
            message = A2AMessage(
                message_type=message_type,
                sender_id=sender_id,
                sender_name=self._agents[sender_id].agent_name if sender_id in self._agents else "",
                receiver_id=receiver_id,
                content=content,
                **kwargs
            )
            
            channel.enqueue(message, priority=priority)
            
            # 直接投递给接收者
            receiver = self._agents.get(receiver_id)
            if receiver:
                response = receiver.handle_message(message)
                channel.dequeue()  # 已处理，从缓冲区移除
                return response
            
            return None
        else:
            # Fallback 到标准路由
            message = A2AMessage(
                message_type=message_type,
                sender_id=sender_id,
                receiver_id=receiver_id,
                content=content,
                **kwargs
            )
            return self.send_message(message)
    
    def list_p2p_channels(self) -> List[Dict]:
        """列出所有活跃的P2P通道"""
        return [
            {
                "peers": list(ch.key),
                "type": ch.channel_type,
                "active": ch.is_active(),
                "queue_size": ch.queue_size(),
                "total_sent": ch.total_sent,
                "created_at": ch.created_at
            }
            for ch in self._p2p_channels.values()
            if ch.is_active()
        ]
    
    def close_p2p(self, agent_id_a: str, agent_id_b: str) -> bool:
        """关闭P2P通道"""
        key = frozenset([agent_id_a, agent_id_b])
        if key in self._p2p_channels:
            del self._p2p_channels[key]
            logger.info(f"[A2ANetwork] P2P channel closed: {agent_id_a} <-> {agent_id_b}")
            return True
        return False
    
    def get_network_status(self) -> Dict:
        """获取网络状态"""
        return {
            "registered_agents": len(self._agents),
            "p2p_channels": len([ch for ch in self._p2p_channels.values() if ch.is_active()]),
            "agents": [
                {
                    "id": p.agent_id,
                    "name": p.agent_name,
                    "role": p.agent_role,
                    "capabilities": [c.name for c in p.get_capabilities()]
                }
                for p in self._agents.values()
            ]
        }


@dataclass
class P2PChannel:
    """P2P直连通道
    
    两个Agent之间的专用通信通道，特点：
    - 跳过中心路由，直接投递
    - 支持缓冲队列（buffered/priority模式）
    - 可设置TTL自动过期
    - 统计通信指标
    
    Args:
        agent_id_a: Agent A的ID
        agent_id_b: Agent B的ID
        channel_type: 通道类型
            - "direct": 无缓冲，直接投递
            - "buffered": FIFO缓冲队列
            - "priority": 优先级队列
        max_queue_size: 缓冲区最大容量
        ttl_seconds: 存活时间（秒），None=永久
    """
    agent_id_a: str
    agent_id_b: str
    channel_type: str = "direct"
    max_queue_size: int = 100
    ttl_seconds: Optional[float] = None
    
    # 内部状态
    _queue: List = field(default_factory=list)
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    _expires_at: Optional[float] = None
    total_sent: int = 0
    total_received: int = 0
    
    def __post_init__(self):
        if self.ttl_seconds is not None:
            import time as _time
            self._expires_at = _time.time() + self.ttl_seconds
    
    @property
    def key(self) -> frozenset:
        """通道唯一标识"""
        return frozenset([self.agent_id_a, self.agent_id_b])
    
    def is_active(self) -> bool:
        """通道是否活跃"""
        if self._expires_at is not None:
            import time as _time
            return _time.time() < self._expires_at
        return True
    
    def refresh(self, ttl_seconds: Optional[float] = None) -> None:
        """刷新通道TTL"""
        import time as _time
        if ttl_seconds is not None:
            self.ttl_seconds = ttl_seconds
        if self.ttl_seconds is not None:
            self._expires_at = _time.time() + self.ttl_seconds
    
    def enqueue(self, message: A2AMessage, priority: int = 0) -> bool:
        """消息入队
        
        Args:
            message: A2A消息
            priority: 优先级（仅priority模式有效，数值越大优先级越高）
            
        Returns:
            是否成功入队
        """
        if self.channel_type == "direct":
            # 直接模式不缓冲
            self.total_sent += 1
            return True
        
        if len(self._queue) >= self.max_queue_size:
            if self.channel_type == "buffered":
                # FIFO溢出：丢弃最旧的
                self._queue.pop(0)
            elif self.channel_type == "priority":
                # 优先级模式：丢弃最低优先级的
                if self._queue:
                    min_idx = min(range(len(self._queue)), key=lambda i: self._queue[i][1])
                    self._queue.pop(min_idx)
        
        self._queue.append((message, priority))
        self.total_sent += 1
        return True
    
    def dequeue(self) -> Optional[A2AMessage]:
        """消息出队"""
        if not self._queue:
            return None
        
        if self.channel_type == "priority":
            # 取最高优先级
            max_idx = max(range(len(self._queue)), key=lambda i: self._queue[i][1])
            message, _ = self._queue.pop(max_idx)
        else:
            message, _ = self._queue.pop(0)
        
        self.total_received += 1
        return message
    
    def queue_size(self) -> int:
        """当前队列大小"""
        return len(self._queue)
    
    def get_stats(self) -> Dict:
        """获取通道统计"""
        return {
            "peers": [self.agent_id_a, self.agent_id_b],
            "type": self.channel_type,
            "active": self.is_active(),
            "queue_size": self.queue_size(),
            "total_sent": self.total_sent,
            "total_received": self.total_received
        }


# 全局网络实例
_a2a_network: Optional[A2ANetwork] = None


def get_a2a_network() -> A2ANetwork:
    """获取全局A2A网络"""
    global _a2a_network
    if _a2a_network is None:
        _a2a_network = A2ANetwork()
    return _a2a_network
