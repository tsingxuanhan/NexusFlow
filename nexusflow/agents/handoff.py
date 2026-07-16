# -*- coding: utf-8 -*-
"""
铉枢·炉守 Agent Handoff机制
XuanHub Agent Handoff - Task Transfer Between Agents
参考: OpenAI Agents SDK Handoff + AG2 Subagent
"""

import logging
import json
from typing import Any, Optional, List, Dict, Callable, Union, TYPE_CHECKING
from dataclasses import dataclass, field
from enum import Enum

if TYPE_CHECKING:
    from .base_agent import BaseAgent

logger = logging.getLogger("Handoff")


class HandoffPolicy(Enum):
    """
    Handoff策略枚举
    
    - TRANSFER: 完全移交，控制权完全转移给目标Agent
    - CONSULT: 咨询模式，目标Agent执行后返回给源Agent
    - DELEGATE: 委托执行，目标Agent执行后汇报结果
    """
    TRANSFER = "transfer"      # 完全移交
    CONSULT = "consult"         # 咨询后返回
    DELEGATE = "delegate"      # 委托执行后返回


@dataclass
class HandoffContext:
    """
    Handoff上下文
    
    包含从一个Agent传递给另一个Agent的所有上下文信息
    """
    # 源Agent信息
    source_agent_name: str
    source_agent_type: str
    
    # 任务信息
    original_request: str       # 原始请求
    task_summary: str           # 任务摘要(已处理的对话摘要)
    
    # 状态信息
    state: Dict[str, Any]       # 传递的状态
    messages: List[Dict]        # 相关对话历史(可选)
    
    # 元数据
    policy: HandoffPolicy       # 移交策略
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict:
        """转换为字典"""
        return {
            "source_agent_name": self.source_agent_name,
            "source_agent_type": self.source_agent_type,
            "original_request": self.original_request,
            "task_summary": self.task_summary,
            "state": self.state,
            "messages": self.messages,
            "policy": self.policy.value,
            "metadata": self.metadata
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'HandoffContext':
        """从字典创建"""
        data = data.copy()
        if "policy" in data and isinstance(data["policy"], str):
            data["policy"] = HandoffPolicy(data["policy"])
        return cls(**data)


@dataclass
class HandoffResult:
    """
    Handoff执行结果
    
    包含目标Agent执行后的返回结果
    """
    success: bool
    target_agent_name: str
    result: Any = None
    error: Optional[str] = None
    context: Optional[HandoffContext] = None
    new_handoffs: List['Handoff'] = field(default_factory=list)  # 可能的继续移交
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Handoff:
    """
    Agent Handoff定义
    
    表示一个Agent可以向另一个Agent移交任务的能力
    """
    name: str                                          # Handoff名称
    target_agent: 'BaseAgent'                          # 目标Agent
    policy: HandoffPolicy = HandoffPolicy.TRANSFER     # 移交策略
    description: str = ""                              # 描述(用于LLM决策)
    
    # 触发条件
    condition: Optional[Callable[['HandoffContext'], bool]] = None  # 自定义条件
    keywords: Optional[List[str]] = None               # 关键词触发
    
    # 上下文控制
    include_messages: bool = True                      # 是否包含对话历史
    max_messages: int = 10                             # 最多传递的消息数
    include_state: bool = True                         # 是否包含状态
    
    def should_trigger(self, context: HandoffContext) -> bool:
        """
        判断是否应该触发此Handoff
        
        Args:
            context: Handoff上下文
            
        Returns:
            是否触发
        """
        # 自定义条件
        if self.condition is not None:
            return self.condition(context)
        
        # 关键词匹配
        if self.keywords:
            request_lower = context.original_request.lower()
            return any(kw.lower() in request_lower for kw in self.keywords)
        
        return True
    
    def create_context(
        self,
        source_agent: 'BaseAgent',
        original_request: str,
        task_summary: str,
        state: Optional[Dict[str, Any]] = None,
        messages: Optional[List[Dict]] = None
    ) -> HandoffContext:
        """
        创建Handoff上下文
        
        Args:
            source_agent: 源Agent
            original_request: 原始请求
            task_summary: 任务摘要
            state: 状态数据
            messages: 对话历史
            
        Returns:
            HandoffContext对象
        """
        return HandoffContext(
            source_agent_name=source_agent.name,
            source_agent_type=source_agent.__class__.__name__,
            original_request=original_request,
            task_summary=task_summary,
            state=state or {},
            messages=messages[-self.max_messages:] if messages and self.include_messages else [],
            policy=self.policy
        )


class HandoffManager:
    """
    Agent间Handoff管理器
    
    负责:
    - 注册和管理Agent间的Handoff关系
    - 执行Handoff操作
    - 维护Handoff历史
    """
    
    def __init__(self):
        # 源Agent名称 -> 可用Handoff列表
        self._handoffs_by_agent: Dict[str, List[Handoff]] = {}
        # Handoff名称 -> Handoff对象
        self._handoffs_by_name: Dict[str, Handoff] = {}
        # Handoff历史
        self._history: List[Dict] = []
        
        logger.info("[HandoffManager] Initialized")
    
    def register(self, agent_name: str, handoff: Handoff) -> None:
        """
        注册Handoff
        
        Args:
            agent_name: 源Agent名称
            handoff: Handoff对象
        """
        if agent_name not in self._handoffs_by_agent:
            self._handoffs_by_agent[agent_name] = []
        
        self._handoffs_by_agent[agent_name].append(handoff)
        self._handoffs_by_name[handoff.name] = handoff
        
        logger.debug(f"[HandoffManager] Registered handoff '{handoff.name}' for agent '{agent_name}'")
    
    def unregister(self, agent_name: str, handoff_name: str) -> bool:
        """
        注销Handoff
        
        Args:
            agent_name: 源Agent名称
            handoff_name: Handoff名称
            
        Returns:
            是否成功注销
        """
        if agent_name in self._handoffs_by_agent:
            handoffs = self._handoffs_by_agent[agent_name]
            for i, h in enumerate(handoffs):
                if h.name == handoff_name:
                    handoffs.pop(i)
                    self._handoffs_by_name.pop(handoff_name, None)
                    return True
        return False
    
    def get_handoffs(self, agent_name: str) -> List[Handoff]:
        """获取Agent的所有可用Handoff"""
        return self._handoffs_by_agent.get(agent_name, [])
    
    def get_handoff(self, name: str) -> Optional[Handoff]:
        """根据名称获取Handoff"""
        return self._handoffs_by_name.get(name)
    
    def find_best_handoff(
        self,
        agent_name: str,
        context: HandoffContext
    ) -> Optional[Handoff]:
        """
        根据上下文找到最佳Handoff
        
        Args:
            agent_name: 源Agent名称
            context: Handoff上下文
            
        Returns:
            最佳匹配的Handoff或None
        """
        available = self.get_handoffs(agent_name)
        
        if not available:
            return None
        
        # 尝试关键词匹配
        for handoff in available:
            if handoff.keywords:
                request_lower = context.original_request.lower()
                if any(kw.lower() in request_lower for kw in handoff.keywords):
                    return handoff
        
        # 返回第一个(默认)
        return available[0] if available else None
    
    def execute(
        self,
        handoff: Handoff,
        context: HandoffContext
    ) -> HandoffResult:
        """
        执行Handoff
        
        Args:
            handoff: Handoff对象
            context: Handoff上下文
            
        Returns:
            HandoffResult对象
        """
        logger.info(f"[HandoffManager] Executing handoff '{handoff.name}' to {handoff.target_agent.name}")
        
        try:
            target = handoff.target_agent
            
            # 构建传递给目标Agent的提示
            prompt = self._build_transfer_prompt(context, handoff)
            
            # 执行
            if handoff.policy == HandoffPolicy.TRANSFER:
                # 完全移交，直接在目标Agent中处理
                result = target.chat(prompt)
            elif handoff.policy == HandoffPolicy.CONSULT:
                # 咨询模式，结果返回给源Agent
                result = target.chat(prompt)
            elif handoff.policy == HandoffPolicy.DELEGATE:
                # 委托模式
                result = target.chat(prompt)
            else:
                result = target.chat(prompt)
            
            # 记录历史
            self._record_history(handoff, context, True)
            
            return HandoffResult(
                success=True,
                target_agent_name=target.name,
                result=result,
                context=context
            )
            
        except Exception as e:
            logger.error(f"[HandoffManager] Handoff failed: {e}")
            self._record_history(handoff, context, False, str(e))
            
            return HandoffResult(
                success=False,
                target_agent_name=handoff.target_agent.name,
                error=str(e),
                context=context
            )
    
    def _build_transfer_prompt(
        self,
        context: HandoffContext,
        handoff: Handoff
    ) -> str:
        """构建传递给目标Agent的提示"""
        prompt_parts = []
        
        # 添加任务说明
        if context.task_summary:
            prompt_parts.append(f"## 来自{context.source_agent_name}的任务摘要\n{context.task_summary}")
        
        # 添加原始请求
        prompt_parts.append(f"## 原始请求\n{context.original_request}")
        
        # 添加状态信息
        if context.state and handoff.include_state:
            prompt_parts.append(f"## 相关状态\n{json.dumps(context.state, ensure_ascii=False, indent=2)}")
        
        # 添加对话历史
        if context.messages and handoff.include_messages:
            history_text = "\n".join([
                f"**{m.get('role', 'unknown')}**: {m.get('content', '')[:200]}"
                for m in context.messages[-handoff.max_messages:]
            ])
            prompt_parts.append(f"## 对话历史\n{history_text}")
        
        # 添加Handoff描述
        if handoff.description:
            prompt_parts.append(f"## 附加说明\n{handoff.description}")
        
        return "\n\n".join(prompt_parts)
    
    def _record_history(
        self,
        handoff: Handoff,
        context: HandoffContext,
        success: bool,
        error: Optional[str] = None
    ) -> None:
        """记录Handoff历史"""
        record = {
            "timestamp": context.metadata.get("timestamp", ""),
            "handoff_name": handoff.name,
            "source_agent": context.source_agent_name,
            "target_agent": handoff.target_agent.name,
            "policy": handoff.policy.value,
            "success": success,
            "error": error
        }
        self._history.append(record)
        
        # 限制历史长度
        if len(self._history) > 1000:
            self._history = self._history[-500:]
    
    def get_history(self, limit: int = 50) -> List[Dict]:
        """获取Handoff历史"""
        return self._history[-limit:]
    
    def get_statistics(self) -> Dict[str, Any]:
        """获取统计信息"""
        total = len(self._history)
        successful = sum(1 for h in self._history if h["success"])
        
        agent_stats = {}
        for h in self._history:
            target = h["target_agent"]
            if target not in agent_stats:
                agent_stats[target] = {"total": 0, "success": 0}
            agent_stats[target]["total"] += 1
            if h["success"]:
                agent_stats[target]["success"] += 1
        
        return {
            "total_handoffs": total,
            "successful": successful,
            "failed": total - successful,
            "success_rate": successful / total if total > 0 else 0,
            "by_agent": agent_stats
        }


# ============ Handoff路由 ============

class HandoffRouter:
    """
    Handoff路由器
    
    基于规则和LLM的Handoff决策
    """
    
    def __init__(self, handoff_manager: HandoffManager):
        self.manager = handoff_manager
        
        # 注册的Agent路由规则
        self._routes: Dict[str, Callable] = {}
    
    def register_route(
        self,
        agent_name: str,
        route_func: Callable[[str], Optional[Handoff]]
    ) -> None:
        """
        注册路由函数
        
        Args:
            agent_name: Agent名称
            route_func: 路由函数，输入原始请求，返回Handoff或None
        """
        self._routes[agent_name] = route_func
        logger.debug(f"[HandoffRouter] Registered route for '{agent_name}'")
    
    def route(
        self,
        agent_name: str,
        request: str,
        context: Optional[HandoffContext] = None
    ) -> Optional[Handoff]:
        """
        路由请求
        
        Args:
            agent_name: 当前Agent名称
            request: 原始请求
            context: 上下文(可选)
            
        Returns:
            匹配的Handoff或None
        """
        # 尝试自定义路由
        if agent_name in self._routes:
            handoff = self._routes[agent_name](request)
            if handoff:
                return handoff
        
        # 使用关键词/条件匹配
        if context:
            return self.manager.find_best_handoff(agent_name, context)
        
        return None


# ============ 便捷函数 ============

_default_manager: Optional[HandoffManager] = None


def get_handoff_manager() -> HandoffManager:
    """获取全局Handoff管理器"""
    global _default_manager
    if _default_manager is None:
        _default_manager = HandoffManager()
    return _default_manager


def create_handoff(
    name: str,
    target_agent: 'BaseAgent',
    policy: HandoffPolicy = HandoffPolicy.TRANSFER,
    description: str = "",
    keywords: Optional[List[str]] = None
) -> Handoff:
    """
    便捷函数: 创建Handoff
    
    Args:
        name: Handoff名称
        target_agent: 目标Agent
        policy: 移交策略
        description: 描述
        keywords: 触发关键词
        
    Returns:
        Handoff对象
    """
    return Handoff(
        name=name,
        target_agent=target_agent,
        policy=policy,
        description=description,
        keywords=keywords
    )
