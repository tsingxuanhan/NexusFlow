# -*- coding: utf-8 -*-
"""
铉枢·炉守 增强记忆管理
XuanHub Enhanced Memory Management
"""

import logging
import time
from typing import List, Dict, Optional, Any, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timedelta

logger = logging.getLogger("EnhancedMemory")


@dataclass
class MemoryItem:
    """记忆条目"""
    content: str
    role: str  # system, user, assistant
    importance: float = 1.0  # 重要性评分 0-1
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    embeddings: Optional[List[float]] = None  # 向量表示(预留)
    
    def to_dict(self) -> Dict:
        return {
            "role": self.role,
            "content": self.content,
            "importance": self.importance,
            "timestamp": self.timestamp
        }


class EnhancedMemory:
    """
    分层记忆管理系统
    
    支持:
    - 短期记忆: 最近对话, 基于重要性自动截断
    - 长期记忆: 持久化存储, 语义检索接口
    - 摘要压缩: 自动将旧消息压缩为摘要
    """
    
    def __init__(
        self,
        max_short_term: int = 50,
        max_long_term: int = 1000,
        importance_threshold: float = 0.3,
        auto_summarize: bool = True
    ):
        """
        初始化记忆管理器
        
        Args:
            max_short_term: 短期记忆最大条数
            max_long_term: 长期记忆最大条数
            importance_threshold: 重要性阈值, 低于此值的条目可能被压缩
            auto_summarize: 是否自动摘要
        """
        self.max_short_term = max_short_term
        self.max_long_term = max_long_term
        self.importance_threshold = importance_threshold
        self.auto_summarize = auto_summarize
        
        self.short_term: List[MemoryItem] = []  # 短期记忆
        self.long_term: List[MemoryItem] = []   # 长期记忆
        self.summaries: List[MemoryItem] = []   # 摘要历史
        
        logger.info(f"[EnhancedMemory] Initialized: short={max_short_term}, long={max_long_term}")
    
    def add(self, role: str, content: str, importance: float = 1.0) -> None:
        """添加记忆"""
        item = MemoryItem(
            content=content,
            role=role,
            importance=importance,
            timestamp=datetime.now().isoformat()
        )
        
        self.short_term.append(item)
        
        # 长期记忆保留
        if importance >= self.importance_threshold:
            self.long_term.append(item)
        
        # 检查是否需要截断
        if len(self.short_term) > self.max_short_term:
            self._prune_short_term()
    
    def _prune_short_term(self) -> None:
        """修剪短期记忆"""
        if not self.auto_summarize:
            # 直接截断
            self.short_term = self.short_term[-self.max_short_term:]
            return
        
        # 按重要性排序, 保留最重要的
        sorted_items = sorted(self.short_term, key=lambda x: x.importance, reverse=True)
        
        # 分离高重要性和低重要性
        high_importance = [item for item in sorted_items if item.importance >= self.importance_threshold]
        low_importance = [item for item in sorted_items if item.importance < self.importance_threshold]
        
        # 生成摘要
        if low_importance:
            summary_content = self._generate_summary(low_importance)
            summary_item = MemoryItem(
                content=summary_content,
                role="system",
                importance=0.5,
                timestamp=datetime.now().isoformat()
            )
            self.summaries.append(summary_item)
            self.long_term.append(summary_item)
        
        # 保留高重要性和最近的
        keep_count = self.max_short_term - len(high_importance)
        recent_items = [item for item in sorted_items if item.importance >= self.importance_threshold or item in sorted_items[:keep_count]]
        
        # 按时间排序
        recent_items.sort(key=lambda x: x.timestamp, reverse=True)
        self.short_term = recent_items[:self.max_short_term]
        
        logger.debug(f"[EnhancedMemory] Pruned: {len(low_importance)} items summarized")
    
    def _generate_summary(self, items: List[MemoryItem]) -> str:
        """生成摘要 (预留接口, 可接入LLM)"""
        if not items:
            return ""
        
        summary_parts = [f"[摘要 - {len(items)}条消息]"]
        for item in items[:10]:  # 最多处理10条
            role_emoji = {"user": "👤", "assistant": "🤖", "system": "⚙️"}.get(item.role, "📝")
            content_preview = item.content[:100] + "..." if len(item.content) > 100 else item.content
            summary_parts.append(f"{role_emoji} {content_preview}")
        
        if len(items) > 10:
            summary_parts.append(f"... 还有{len(items) - 10}条消息")
        
        return "\n".join(summary_parts)
    
    def get_context(self, include_summary: bool = True) -> List[Dict]:
        """获取当前上下文"""
        context = []
        
        # 添加摘要
        if include_summary and self.summaries:
            latest_summary = self.summaries[-1]
            context.append({
                "role": "system",
                "content": f"[历史摘要]\n{latest_summary.content}"
            })
        
        # 添加短期记忆
        for item in self.short_term:
            context.append(item.to_dict())
        
        return context
    
    def search(self, query: str, top_k: int = 5) -> List[Tuple[MemoryItem, float]]:
        """
        语义检索 (预留接口)
        
        实际实现需要接入向量数据库(如Chroma/Qdrant)
        
        Args:
            query: 查询文本
            top_k: 返回前k个结果
            
        Returns:
            (MemoryItem, similarity_score) 列表
        """
        logger.warning("[EnhancedMemory] Semantic search not implemented, using keyword fallback")
        
        # 简单关键词匹配作为fallback
        query_words = set(query.lower().split())
        results = []
        
        for item in self.long_term:
            content_words = set(item.content.lower().split())
            overlap = len(query_words & content_words)
            if overlap > 0:
                score = overlap / max(len(query_words), len(content_words))
                results.append((item, score))
        
        results.sort(key=lambda x: x[1], reverse=True)
        return results[:top_k]
    
    def get_recent(self, n: int = 10, role_filter: Optional[str] = None) -> List[MemoryItem]:
        """获取最近的n条记忆"""
        items = self.short_term
        
        if role_filter:
            items = [item for item in items if item.role == role_filter]
        
        return items[-n:]
    
    def get_stats(self) -> Dict[str, Any]:
        """获取记忆统计"""
        return {
            "short_term_count": len(self.short_term),
            "long_term_count": len(self.long_term),
            "summaries_count": len(self.summaries),
            "total_items": len(self.short_term) + len(self.long_term),
            "max_short_term": self.max_short_term,
            "max_long_term": self.max_long_term
        }
    
    def reset(self) -> None:
        """重置记忆"""
        self.short_term.clear()
        # 保留长期记忆和摘要
        logger.info("[EnhancedMemory] Short-term memory reset")
    
    def to_dict(self) -> Dict:
        """导出记忆状态"""
        return {
            "short_term": [item.to_dict() for item in self.short_term],
            "long_term": [item.to_dict() for item in self.long_term[-100:]],  # 限制导出数量
            "summaries": [item.to_dict() for item in self.summaries[-10:]],
            "stats": self.get_stats()
        }
