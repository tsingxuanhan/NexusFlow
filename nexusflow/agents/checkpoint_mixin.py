# -*- coding: utf-8 -*-
"""
检查点Mixin — Checkpoint保存/加载/回退
CheckpointMixin extracted from base_agent.py
"""

import logging
from typing import List, Dict, Optional

from .models import Message

logger = logging.getLogger("BaseAgent")


class CheckpointMixin:
    """检查点相关方法：save_checkpoint / load_checkpoint / rewind / _auto_checkpoint / get_checkpoint_history"""

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
