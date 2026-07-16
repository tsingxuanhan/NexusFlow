# -*- coding: utf-8 -*-
"""
铉枢·炉守 检查点机制
XuanHub Checkpoint System - Session State Persistence
参考: LangGraph Checkpointer + AG2 MemoryStream
"""

import json
import uuid
import logging
from typing import Any, Optional, List, Dict, Callable
from dataclasses import dataclass, field, asdict
from datetime import datetime
from abc import ABC, abstractmethod
from enum import Enum

logger = logging.getLogger("Checkpoint")


class CheckpointStatus(Enum):
    """检查点状态"""
    ACTIVE = "active"
    ARCHIVED = "archived"
    ROLLBACK = "rollback"


@dataclass
class Checkpoint:
    """
    检查点数据模型
    
    包含完整的Agent运行状态，用于会话恢复和回滚
    """
    checkpoint_id: str           # 唯一检查点ID
    thread_id: str              # 线程/会话ID
    state: Dict[str, Any]       # 状态快照
    metadata: Dict[str, Any]     # 元数据(创建时间、来源等)
    status: CheckpointStatus = CheckpointStatus.ACTIVE
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    
    def to_dict(self) -> Dict:
        """转换为字典"""
        data = asdict(self)
        data["status"] = self.status.value
        return data
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'Checkpoint':
        """从字典创建"""
        data = data.copy()
        if "status" in data and isinstance(data["status"], str):
            data["status"] = CheckpointStatus(data["status"])
        return cls(**data)


class Checkpointer(ABC):
    """
    检查点抽象基类
    
    定义检查点存储的接口，支持不同存储后端
    """
    
    @abstractmethod
    def save(
        self,
        thread_id: str,
        state: Dict[str, Any],
        metadata: Optional[Dict[str, Any]] = None,
        checkpoint_id: Optional[str] = None
    ) -> str:
        """
        保存检查点
        
        Args:
            thread_id: 线程/会话ID
            state: 状态数据
            metadata: 元数据
            checkpoint_id: 指定检查点ID(可选，默认自动生成)
            
        Returns:
            checkpoint_id: 保存的检查点ID
        """
        pass
    
    @abstractmethod
    def load(
        self,
        thread_id: str,
        checkpoint_id: Optional[str] = None
    ) -> Optional[Checkpoint]:
        """
        加载检查点
        
        Args:
            thread_id: 线程/会话ID
            checkpoint_id: 检查点ID(可选，默认加载最新)
            
        Returns:
            Checkpoint对象或None
        """
        pass
    
    @abstractmethod
    def list_checkpoints(
        self,
        thread_id: str,
        limit: int = 50
    ) -> List[Checkpoint]:
        """
        列出线程的所有检查点
        
        Args:
            thread_id: 线程/会话ID
            limit: 返回数量限制
            
        Returns:
            Checkpoint列表(按时间倒序)
        """
        pass
    
    @abstractmethod
    def delete(
        self,
        thread_id: str,
        checkpoint_id: str
    ) -> bool:
        """删除检查点"""
        pass


class MemoryCheckpointer(Checkpointer):
    """
    内存检查点存储
    
    适用于开发环境和轻量级应用
    数据存储在内存中，进程结束会丢失
    """
    
    def __init__(self):
        self._storage: Dict[str, Dict[str, Checkpoint]] = {}
        logger.info("[MemoryCheckpointer] Initialized (in-memory storage)")
    
    def save(
        self,
        thread_id: str,
        state: Dict[str, Any],
        metadata: Optional[Dict[str, Any]] = None,
        checkpoint_id: Optional[str] = None
    ) -> str:
        checkpoint_id = checkpoint_id or str(uuid.uuid4())[:8]
        
        if thread_id not in self._storage:
            self._storage[thread_id] = {}
        
        checkpoint = Checkpoint(
            checkpoint_id=checkpoint_id,
            thread_id=thread_id,
            state=state,
            metadata=metadata or {}
        )
        
        self._storage[thread_id][checkpoint_id] = checkpoint
        logger.debug(f"[MemoryCheckpointer] Saved checkpoint {checkpoint_id} for thread {thread_id}")
        
        return checkpoint_id
    
    def load(
        self,
        thread_id: str,
        checkpoint_id: Optional[str] = None
    ) -> Optional[Checkpoint]:
        if thread_id not in self._storage:
            return None
        
        checkpoints = self._storage[thread_id]
        
        if checkpoint_id:
            return checkpoints.get(checkpoint_id)
        
        # 返回最新的检查点
        if checkpoints:
            latest_id = max(checkpoints.keys(), key=lambda k: checkpoints[k].created_at)
            return checkpoints[latest_id]
        
        return None
    
    def list_checkpoints(
        self,
        thread_id: str,
        limit: int = 50
    ) -> List[Checkpoint]:
        if thread_id not in self._storage:
            return []
        
        checkpoints = list(self._storage[thread_id].values())
        # 按创建时间倒序
        checkpoints.sort(key=lambda c: c.created_at, reverse=True)
        return checkpoints[:limit]
    
    def delete(self, thread_id: str, checkpoint_id: str) -> bool:
        if thread_id in self._storage and checkpoint_id in self._storage[thread_id]:
            del self._storage[thread_id][checkpoint_id]
            return True
        return False
    
    def clear(self, thread_id: Optional[str] = None) -> None:
        """清空存储"""
        if thread_id:
            self._storage.pop(thread_id, None)
        else:
            self._storage.clear()
        logger.info(f"[MemoryCheckpointer] Storage cleared for thread: {thread_id or 'all'}")


class SqliteCheckpointer(Checkpointer):
    """
    SQLite检查点存储
    
    适用于生产环境，支持持久化存储
    """
    
    def __init__(self, db_path: str = "checkpoints.db"):
        import sqlite3
        
        self.db_path = db_path
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self._init_db()
        logger.info(f"[SqliteCheckpointer] Initialized with db: {db_path}")
    
    def _init_db(self) -> None:
        """初始化数据库表"""
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS checkpoints (
                checkpoint_id TEXT PRIMARY KEY,
                thread_id TEXT NOT NULL,
                state TEXT NOT NULL,
                metadata TEXT,
                status TEXT DEFAULT 'active',
                created_at TEXT NOT NULL,
                INDEX idx_thread_id (thread_id),
                INDEX idx_created_at (created_at)
            )
        """)
        self.conn.commit()
    
    def save(
        self,
        thread_id: str,
        state: Dict[str, Any],
        metadata: Optional[Dict[str, Any]] = None,
        checkpoint_id: Optional[str] = None
    ) -> str:
        checkpoint_id = checkpoint_id or str(uuid.uuid4())[:8]
        
        self.conn.execute("""
            INSERT OR REPLACE INTO checkpoints 
            (checkpoint_id, thread_id, state, metadata, status, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            checkpoint_id,
            thread_id,
            json.dumps(state, ensure_ascii=False),
            json.dumps(metadata or {}, ensure_ascii=False),
            CheckpointStatus.ACTIVE.value,
            datetime.now().isoformat()
        ))
        self.conn.commit()
        
        logger.debug(f"[SqliteCheckpointer] Saved checkpoint {checkpoint_id}")
        return checkpoint_id
    
    def load(
        self,
        thread_id: str,
        checkpoint_id: Optional[str] = None
    ) -> Optional[Checkpoint]:
        cursor = self.conn.execute("""
            SELECT checkpoint_id, thread_id, state, metadata, status, created_at
            FROM checkpoints
            WHERE thread_id = ? AND checkpoint_id = ?
        """, (thread_id, checkpoint_id)) if checkpoint_id else \
                self.conn.execute("""
            SELECT checkpoint_id, thread_id, state, metadata, status, created_at
            FROM checkpoints
            WHERE thread_id = ?
            ORDER BY created_at DESC
            LIMIT 1
        """, (thread_id,))
        
        row = cursor.fetchone()
        
        if row:
            return Checkpoint(
                checkpoint_id=row[0],
                thread_id=row[1],
                state=json.loads(row[2]),
                metadata=json.loads(row[3]) if row[3] else {},
                status=CheckpointStatus(row[4]),
                created_at=row[5]
            )
        
        return None
    
    def list_checkpoints(
        self,
        thread_id: str,
        limit: int = 50
    ) -> List[Checkpoint]:
        cursor = self.conn.execute("""
            SELECT checkpoint_id, thread_id, state, metadata, status, created_at
            FROM checkpoints
            WHERE thread_id = ?
            ORDER BY created_at DESC
            LIMIT ?
        """, (thread_id, limit))
        
        checkpoints = []
        for row in cursor.fetchall():
            checkpoints.append(Checkpoint(
                checkpoint_id=row[0],
                thread_id=row[1],
                state=json.loads(row[2]),
                metadata=json.loads(row[3]) if row[3] else {},
                status=CheckpointStatus(row[4]),
                created_at=row[5]
            ))
        
        return checkpoints
    
    def delete(self, thread_id: str, checkpoint_id: str) -> bool:
        cursor = self.conn.execute("""
            DELETE FROM checkpoints
            WHERE thread_id = ? AND checkpoint_id = ?
        """, (thread_id, checkpoint_id))
        self.conn.commit()
        return cursor.rowcount > 0


class CheckpointManager:
    """
    检查点管理器
    
    提供高级检查点操作:
    - 自动检查点(每N轮对话或节点完成)
    - Rewind(回滚到任意历史检查点)
    - 版本分支管理
    """
    
    def __init__(
        self,
        checkpointer: Checkpointer = None,
        auto_interval: int = 5,  # 每N轮自动保存
        max_checkpoints: int = 50
    ):
        self.checkpointer = checkpointer or MemoryCheckpointer()
        self.auto_interval = auto_interval
        self.max_checkpoints = max_checkpoints
        
        # 线程计数器
        self._thread_counters: Dict[str, int] = {}
        
        logger.info(f"[CheckpointManager] Initialized with interval={auto_interval}")
    
    def _get_next_counter(self, thread_id: str) -> int:
        """获取并递增线程计数器"""
        if thread_id not in self._thread_counters:
            self._thread_counters[thread_id] = 0
        self._thread_counters[thread_id] += 1
        return self._thread_counters[thread_id]
    
    def save(
        self,
        thread_id: str,
        state: Dict[str, Any],
        metadata: Optional[Dict[str, Any]] = None,
        auto: bool = False
    ) -> str:
        """
        保存检查点
        
        Args:
            thread_id: 线程ID
            state: 状态数据
            metadata: 元数据
            auto: 是否自动保存(受auto_interval控制)
            
        Returns:
            checkpoint_id
        """
        # 自动检查点: 只有达到间隔才保存
        if auto:
            counter = self._get_next_counter(thread_id)
            if counter % self.auto_interval != 0:
                return ""
        
        # 添加元数据
        meta = metadata or {}
        meta["auto"] = auto
        meta["counter"] = self._thread_counters.get(thread_id, 0)
        
        checkpoint_id = self.checkpointer.save(thread_id, state, meta)
        
        # 清理旧检查点
        self._prune_checkpoints(thread_id)
        
        return checkpoint_id
    
    def _prune_checkpoints(self, thread_id: str) -> None:
        """清理超过限制的检查点"""
        checkpoints = self.checkpointer.list_checkpoints(thread_id)
        
        if len(checkpoints) > self.max_checkpoints:
            # 删除最旧的
            to_delete = checkpoints[self.max_checkpoints:]
            for cp in to_delete:
                self.checkpointer.delete(thread_id, cp.checkpoint_id)
            
            logger.info(f"[CheckpointManager] Pruned {len(to_delete)} old checkpoints")
    
    def rewind(
        self,
        thread_id: str,
        checkpoint_id: Optional[str] = None,
        steps_back: int = 0
    ) -> Optional[Checkpoint]:
        """
        Rewind到指定检查点
        
        Args:
            thread_id: 线程ID
            checkpoint_id: 检查点ID(可选)
            steps_back: 回退步数(相对当前)
            
        Returns:
            恢复的Checkpoint
        """
        if steps_back > 0:
            checkpoints = self.checkpointer.list_checkpoints(thread_id)
            if len(checkpoints) > steps_back:
                checkpoint_id = checkpoints[steps_back].checkpoint_id
            else:
                logger.warning(f"[CheckpointManager] Cannot rewind {steps_back} steps, only {len(checkpoints)} available")
                return None
        
        checkpoint = self.checkpointer.load(thread_id, checkpoint_id)
        
        if checkpoint:
            logger.info(f"[CheckpointManager] Rewound to checkpoint {checkpoint.checkpoint_id}")
        else:
            logger.warning(f"[CheckpointManager] Checkpoint not found: {checkpoint_id}")
        
        return checkpoint
    
    def create_branch(
        self,
        source_thread_id: str,
        source_checkpoint_id: str,
        new_thread_id: str
    ) -> str:
        """
        从指定检查点创建分支
        
        Args:
            source_thread_id: 源线程ID
            source_checkpoint_id: 源检查点ID
            new_thread_id: 新线程ID
            
        Returns:
            新线程的最新检查点ID
        """
        checkpoint = self.checkpointer.load(source_thread_id, source_checkpoint_id)
        
        if not checkpoint:
            raise ValueError(f"Source checkpoint not found: {source_checkpoint_id}")
        
        # 在新线程中保存相同的state
        new_checkpoint_id = self.checkpointer.save(
            new_thread_id,
            checkpoint.state,
            {
                "branched_from": {
                    "thread_id": source_thread_id,
                    "checkpoint_id": source_checkpoint_id
                }
            }
        )
        
        logger.info(f"[CheckpointManager] Created branch: {new_thread_id} from {source_thread_id}:{source_checkpoint_id}")
        return new_checkpoint_id
    
    def get_history(
        self,
        thread_id: str,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """获取检查点历史"""
        checkpoints = self.checkpointer.list_checkpoints(thread_id, limit)
        
        return [
            {
                "checkpoint_id": cp.checkpoint_id,
                "created_at": cp.created_at,
                "metadata": cp.metadata
            }
            for cp in checkpoints
        ]


# ============ 自动检查点装饰器 ============

def auto_checkpoint(
    manager: CheckpointManager,
    get_state: Callable[[], Dict],
    thread_id: str
):
    """
    自动检查点装饰器工厂
    
    用法:
        checkpoint_decorator = auto_checkpoint(manager, lambda: agent.get_state(), "user123")
        
        @checkpoint_decorator
        def process_task():
            ...
    """
    def decorator(func: Callable) -> Callable:
        def wrapper(*args, **kwargs):
            result = func(*args, **kwargs)
            
            # 执行后自动保存检查点
            state = get_state()
            manager.save(thread_id, state, auto=True)
            
            return result
        return wrapper
    return decorator


# ============ 全局默认检查点管理器 ============

_default_manager: Optional[CheckpointManager] = None


def get_default_manager() -> CheckpointManager:
    """获取全局默认检查点管理器"""
    global _default_manager
    if _default_manager is None:
        _default_manager = CheckpointManager()
    return _default_manager


def init_checkpoint_manager(
    checkpointer: Checkpointer = None,
    auto_interval: int = 5
) -> CheckpointManager:
    """初始化全局检查点管理器"""
    global _default_manager
    _default_manager = CheckpointManager(checkpointer, auto_interval)
    return _default_manager
