# -*- coding: utf-8 -*-
"""
铉枢·炉守 A2A v1.0网关
XuanHub A2A Gateway — Phase 3

跨框架Agent协作网关 — 发现、委托、接收任务
参考: Google A2A Protocol v1.0 (2025.04, 150+组织支持)
"""

import json
import uuid
import logging
import time
from typing import Any, Dict, List, Optional, Callable
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger("A2AGateway")


class A2ATaskStatus(Enum):
    """A2A任务状态"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class A2AAgentInfo:
    """A2A Agent信息"""
    agent_id: str
    agent_name: str
    agent_url: str = ""
    capabilities: List[str] = field(default_factory=list)
    description: str = ""
    framework: str = ""  # xuanshu / crewai / langgraph / auto_gen
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict:
        return {
            "agent_id": self.agent_id,
            "agent_name": self.agent_name,
            "agent_url": self.agent_url,
            "capabilities": self.capabilities,
            "description": self.description,
            "framework": self.framework,
        }


@dataclass
class A2ATask:
    """A2A跨框架任务"""
    task_id: str
    description: str
    sender_id: str
    receiver_id: str
    status: A2ATaskStatus = A2ATaskStatus.PENDING
    result: Any = None
    error: Optional[str] = None
    created_at: float = field(default_factory=time.time)
    completed_at: Optional[float] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict:
        return {
            "task_id": self.task_id,
            "description": self.description,
            "sender_id": self.sender_id,
            "receiver_id": self.receiver_id,
            "status": self.status.value,
            "result": self.result,
            "error": self.error,
            "created_at": self.created_at,
            "completed_at": self.completed_at,
        }


class A2AGateway:
    """
    A2A v1.0网关
    
    功能:
    - 注册Agent到A2A网络
    - 发现具有指定能力的其他Agent
    - 将任务委托给其他框架的Agent
    - 接收并处理来自其他Agent的任务
    - 任务状态追踪
    
    用法:
        gateway = A2AGateway()
        
        # 注册自己
        gateway.register_self(A2AAgentInfo(
            agent_id="xuanshu-planner",
            agent_name="StrategyAgent",
            capabilities=["plan_task", "decompose"],
        ))
        
        # 发现其他Agent
        agents = gateway.discover_agents("research_topic")
        
        # 委托任务
        result = gateway.delegate_task(
            agent_id="external-researcher",
            task=A2ATask(
                description="Research SSC cement latest papers",
                sender_id="xuanshu-planner",
                receiver_id="external-researcher",
            )
        )
    """
    
    def __init__(self, self_agent_id: str = "xuanshu-agents"):
        self.self_agent_id = self_agent_id
        self._agents: Dict[str, A2AAgentInfo] = {}
        self._tasks: Dict[str, A2ATask] = {}
        self._task_handlers: Dict[str, Callable] = {}
        self._delegation_history: List[Dict] = []
        
        logger.info(f"[A2AGateway] Initialized for {self_agent_id}")
    
    # ============ Agent注册 ============
    
    def register_agent(self, agent_info: A2AAgentInfo) -> str:
        """注册Agent到A2A网络"""
        self._agents[agent_info.agent_id] = agent_info
        logger.info(f"[A2AGateway] Registered agent: {agent_info.agent_id} ({agent_info.framework})")
        return agent_info.agent_id
    
    def register_self(self, agent_info: A2AAgentInfo) -> str:
        """注册自身Agent"""
        self.self_agent_id = agent_info.agent_id
        return self.register_agent(agent_info)
    
    def unregister_agent(self, agent_id: str) -> bool:
        """注销Agent"""
        if agent_id in self._agents:
            del self._agents[agent_id]
            return True
        return False
    
    # ============ Agent发现 ============
    
    def discover_agents(self, capability: str) -> List[A2AAgentInfo]:
        """
        发现具有指定能力的其他Agent
        
        Args:
            capability: 能力关键词
            
        Returns:
            匹配的Agent列表
        """
        results = []
        keyword = capability.lower()
        
        for agent in self._agents.values():
            if agent.agent_id == self.self_agent_id:
                continue  # 排除自己
            
            if (keyword in " ".join(agent.capabilities).lower() or
                keyword in agent.description.lower()):
                results.append(agent)
        
        logger.info(f"[A2AGateway] Discover '{capability}': {len(results)} agents found")
        return results
    
    def get_agent(self, agent_id: str) -> Optional[A2AAgentInfo]:
        """获取Agent信息"""
        return self._agents.get(agent_id)
    
    def list_agents(self) -> List[A2AAgentInfo]:
        """列出所有已知Agent"""
        return list(self._agents.values())
    
    # ============ 任务委托 ============
    
    def delegate_task(
        self,
        agent_id: str,
        description: str,
        metadata: Optional[Dict] = None,
    ) -> A2ATask:
        """
        将任务委托给其他Agent
        
        Args:
            agent_id: 目标Agent ID
            description: 任务描述
            metadata: 额外元数据
            
        Returns:
            A2ATask实例
        """
        if agent_id not in self._agents:
            raise ValueError(f"Unknown agent: {agent_id}")
        
        task_id = str(uuid.uuid4())[:8]
        task = A2ATask(
            task_id=task_id,
            description=description,
            sender_id=self.self_agent_id,
            receiver_id=agent_id,
            metadata=metadata or {},
        )
        
        self._tasks[task_id] = task
        
        # 尝试实际委托（如果目标Agent有URL）
        target = self._agents[agent_id]
        if target.agent_url:
            try:
                import requests
                resp = requests.post(
                    f"{target.agent_url}/a2a/task",
                    json=task.to_dict(),
                    timeout=30,
                )
                if resp.status_code == 200:
                    task.status = A2ATaskStatus.RUNNING
                else:
                    task.status = A2ATaskStatus.FAILED
                    task.error = f"HTTP {resp.status_code}"
            except Exception as e:
                task.status = A2ATaskStatus.PENDING
                task.error = f"Connection failed: {e}"
        else:
            task.status = A2ATaskStatus.PENDING
        
        self._delegation_history.append({
            "task_id": task_id,
            "target": agent_id,
            "description": description[:100],
            "status": task.status.value,
            "timestamp": time.time(),
        })
        
        logger.info(f"[A2AGateway] Delegated task {task_id} to {agent_id}")
        return task
    
    def get_task_status(self, task_id: str) -> Optional[A2ATask]:
        """获取任务状态"""
        return self._tasks.get(task_id)
    
    def complete_task(self, task_id: str, result: Any) -> bool:
        """完成任务"""
        task = self._tasks.get(task_id)
        if task:
            task.status = A2ATaskStatus.COMPLETED
            task.result = result
            task.completed_at = time.time()
            return True
        return False
    
    def fail_task(self, task_id: str, error: str) -> bool:
        """标记任务失败"""
        task = self._tasks.get(task_id)
        if task:
            task.status = A2ATaskStatus.FAILED
            task.error = error
            task.completed_at = time.time()
            return True
        return False
    
    # ============ 任务接收 ============
    
    def register_task_handler(self, capability: str, handler: Callable) -> None:
        """
        注册任务处理器
        
        当收到与capability匹配的任务时，调用handler处理
        """
        self._task_handlers[capability] = handler
        logger.info(f"[A2AGateway] Registered handler for: {capability}")
    
    def receive_task(self, task: A2ATask) -> Any:
        """
        接收并处理来自其他Agent的任务
        
        Args:
            task: A2ATask实例
            
        Returns:
            任务执行结果
        """
        self._tasks[task.task_id] = task
        task.status = A2ATaskStatus.RUNNING
        
        # 查找匹配的处理器
        for capability, handler in self._task_handlers.items():
            if capability.lower() in task.description.lower():
                try:
                    result = handler(task.description, **task.metadata)
                    task.status = A2ATaskStatus.COMPLETED
                    task.result = result
                    task.completed_at = time.time()
                    return result
                except Exception as e:
                    task.status = A2ATaskStatus.FAILED
                    task.error = str(e)
                    task.completed_at = time.time()
                    raise
        
        task.status = A2ATaskStatus.FAILED
        task.error = "No matching handler"
        raise ValueError(f"No handler for task: {task.description[:100]}")
    
    # ============ 统计 ============
    
    def get_stats(self) -> Dict[str, Any]:
        """获取网关统计"""
        status_counts = {}
        for task in self._tasks.values():
            s = task.status.value
            status_counts[s] = status_counts.get(s, 0) + 1
        
        return {
            "self_agent_id": self.self_agent_id,
            "known_agents": len(self._agents),
            "total_tasks": len(self._tasks),
            "task_status": status_counts,
            "handlers": list(self._task_handlers.keys()),
            "delegations": len(self._delegation_history),
        }
    
    def get_delegation_history(self, limit: int = 50) -> List[Dict]:
        """获取委托历史"""
        return self._delegation_history[-limit:]
