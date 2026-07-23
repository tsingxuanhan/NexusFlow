# -*- coding: utf-8 -*-
"""
记忆Mixin — Letta三层记忆系统
MemoryMixin extracted from base_agent.py
"""

import logging
from typing import Dict

logger = logging.getLogger("BaseAgent")


class MemoryMixin:
    """记忆相关方法：init_memory / remember / recall / dream / memory_status"""

    def init_memory(self, data_dir: str = "data") -> None:
        """
        初始化Letta三层记忆系统

        Args:
            data_dir: 记忆数据目录
        """
        from nexusflow.memory.memory_manager import MemoryManager, create_memory_manager
        from nexusflow.memory.sleeptime import SleeptimeEngine
        from nexusflow.memory.multi_hop_rag import MultiHopRAG

        # 创建Memory Manager
        self._memory = create_memory_manager(
            data_dir=data_dir,
            api_endpoint=self.endpoint,
            api_key=self.api_key,
        )

        # 创建Sleeptime Engine
        self._sleeptime = SleeptimeEngine(
            memory_manager=self._memory,
            api_endpoint=self.endpoint,
            api_key=self.api_key,
        )

        # 创建Multi-Hop RAG
        self._multihop_rag = MultiHopRAG(
            archival_memory=self._memory.archival,
            api_endpoint=self.endpoint,
            api_key=self.api_key,
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
