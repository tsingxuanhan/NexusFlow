# -*- coding: utf-8 -*-
"""
任务移交Mixin — Handoff注册/执行
HandoffMixin extracted from base_agent.py
"""

import logging
from typing import List, Dict, Optional, Any, Union

from .models import Message

logger = logging.getLogger("BaseAgent")


class HandoffMixin:
    """任务移交相关方法：register_handoff / handoff_to / _generate_task_summary / get_state / get_available_handoffs"""

    def register_handoff(
        self,
        name: str,
        target_agent: 'BaseAgent',
        policy=None,
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
        from .handoff import HandoffPolicy, create_handoff

        if policy is None:
            policy = HandoffPolicy.TRANSFER

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
    ):
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
        from .handoff import create_handoff, HandoffResult

        # 导入A2A可用性标记（在base_agent模块级定义）
        from . import base_agent as _ba
        _A2A_AVAILABLE = getattr(_ba, '_A2A_AVAILABLE', False)

        # 解析目标
        if isinstance(target, str):
            handoff = self.handoff_manager.get_handoff(target)

            # 新增: 如果找不到handoff，尝试A2A网络
            if not handoff and _A2A_AVAILABLE and self.a2a:
                from nexusflow.protocol.a2a_protocol import get_a2a_network
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
