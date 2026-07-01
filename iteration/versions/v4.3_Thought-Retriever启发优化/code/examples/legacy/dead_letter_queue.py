# -*- coding: utf-8 -*-
"""
铉枢·炉守 死信队列
XuanHub Dead Letter Queue (DLQ) Pattern
参考: Supergood + Galileo AI 错误处理
"""

import json
import logging
import time
from typing import Any, Callable, Dict, List, Optional
from dataclasses import dataclass, field, asdict
from enum import Enum
from datetime import datetime
from pathlib import Path
from queue import Queue, Empty
from threading import Thread, Lock
from collections import deque

logger = logging.getLogger("DeadLetterQueue")


class DLQStatus(Enum):
    """任务状态"""
    PENDING = "pending"      # 等待处理
    RETRYING = "retrying"    # 重试中
    DEAD = "dead"           # 永久失败
    SUCCESS = "success"     # 成功(已处理)


class DLQPriority(Enum):
    """任务优先级"""
    HIGH = 1
    NORMAL = 2
    LOW = 3


@dataclass
class DLQEntry:
    """死信队列条目"""
    entry_id: str
    original_task: str              # 原始任务标识
    payload: Any                    # 任务载荷
    error: str                      # 错误信息
    error_type: str                 # 错误类型
    attempt_count: int = 0         # 已尝试次数
    max_attempts: int = 3          # 最大尝试次数
    status: DLQStatus = DLQStatus.PENDING
    priority: DLQPriority = DLQPriority.NORMAL
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    last_attempt_at: Optional[str] = None
    next_retry_at: Optional[str] = None
    metadata: Dict = field(default_factory=dict)
    
    def to_dict(self) -> Dict:
        data = asdict(self)
        data["status"] = self.status.value
        data["priority"] = self.priority.value
        return data
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'DLQEntry':
        data = data.copy()
        data["status"] = DLQStatus(data.get("status", "pending"))
        data["priority"] = DLQPriority(data.get("priority", 2))
        return cls(**data)
    
    def can_retry(self) -> bool:
        """是否可以重试"""
        return (
            self.status in (DLQStatus.PENDING, DLQStatus.RETRYING) and
            self.attempt_count < self.max_attempts
        )
    
    def should_dead(self) -> bool:
        """是否应该标记为永久失败"""
        return self.attempt_count >= self.max_attempts


@dataclass
class RetryConfig:
    """重试配置"""
    max_attempts: int = 3           # 最大重试次数
    base_delay: float = 1.0         # 基础延迟(秒)
    max_delay: float = 60.0         # 最大延迟(秒)
    backoff_multiplier: float = 2.0 # 退避倍数
    jitter: bool = True             # 是否添加jitter
    jitter_range: float = 0.5       # jitter范围(秒)
    
    def get_delay(self, attempt: int) -> float:
        """计算延迟时间"""
        delay = min(
            self.base_delay * (self.backoff_multiplier ** attempt),
            self.max_delay
        )
        
        if self.jitter:
            import random
            offset = random.uniform(-self.jitter_range, self.jitter_range)
            delay = max(0, delay + offset)
        
        return delay


class DeadLetterQueue:
    """
    死信队列
    
    收集处理失败的任务，支持:
    - 延迟重试
    - 永久失败标记
    - 任务状态追踪
    - 自动重试工作者
    
    用法:
        dlq = DeadLetterQueue()
        
        # 提交失败任务
        dlq.submit("task_123", payload, error, error_type="timeout")
        
        # 启动重试工作者
        dlq.start_worker(retry_func)
        
        # 查询状态
        status = dlq.get_entry("task_123")
    """
    
    def __init__(
        self,
        storage_path: Optional[str] = None,
        retry_config: Optional[RetryConfig] = None,
        max_queue_size: int = 1000
    ):
        self.storage_path = storage_path
        self.retry_config = retry_config or RetryConfig()
        
        # 内存队列
        self._pending: deque = deque(maxlen=max_queue_size)  # 等待处理
        self._retrying: deque = deque(maxlen=max_queue_size)  # 重试中
        self._dead: deque = deque(maxlen=max_queue_size)  # 永久失败
        self._completed: deque = deque(maxlen=max_queue_size)  # 已完成
        
        # 索引
        self._index: Dict[str, DLQEntry] = {}
        
        # 工作者
        self._worker_thread: Optional[Thread] = None
        self._worker_running = False
        self._worker_func: Optional[Callable] = None
        
        # 线程安全
        self._lock = Lock()
        
        # 统计
        self._stats = {
            "total_submitted": 0,
            "total_retried": 0,
            "total_dead": 0,
            "total_success": 0
        }
        
        # 加载已有数据
        if storage_path:
            self._load()
        
        logger.info(f"[DLQ] Initialized (storage={storage_path}, max_attempts={self.retry_config.max_attempts})")
    
    def submit(
        self,
        task_id: str,
        payload: Any,
        error: Exception,
        error_type: str = "unknown",
        priority: DLQPriority = DLQPriority.NORMAL,
        max_attempts: Optional[int] = None,
        metadata: Optional[Dict] = None
    ) -> DLQEntry:
        """
        提交失败任务到死信队列
        
        Args:
            task_id: 任务唯一标识
            payload: 任务载荷
            error: 异常对象
            error_type: 错误类型
            priority: 优先级
            max_attempts: 最大尝试次数
            metadata: 附加元数据
            
        Returns:
            DLQEntry
        """
        entry = DLQEntry(
            entry_id=task_id,
            original_task=task_id,
            payload=payload,
            error=str(error),
            error_type=error_type,
            priority=priority,
            max_attempts=max_attempts or self.retry_config.max_attempts,
            metadata=metadata or {}
        )
        
        with self._lock:
            self._pending.append(entry)
            self._index[task_id] = entry
            self._stats["total_submitted"] += 1
            
            # 计算下次重试时间
            entry.next_retry_at = datetime.now().isoformat()
        
        logger.warning(f"[DLQ] Submitted task '{task_id}' (error={error_type}, attempts=0/{entry.max_attempts})")
        
        return entry
    
    def get_entry(self, task_id: str) -> Optional[DLQEntry]:
        """获取任务条目"""
        with self._lock:
            return self._index.get(task_id)
    
    def get_pending(self, limit: int = 10) -> List[DLQEntry]:
        """获取待处理任务"""
        with self._lock:
            entries = [e for e in self._pending if e.can_retry()]
            return sorted(entries, key=lambda e: (e.priority.value, e.created_at))[:limit]
    
    def get_dead(self, limit: int = 50) -> List[DLQEntry]:
        """获取永久失败任务"""
        with self._lock:
            return list(self._dead)[:limit]
    
    def get_stats(self) -> Dict:
        """获取统计信息"""
        with self._lock:
            return {
                "pending": len(self._pending),
                "retrying": len(self._retrying),
                "dead": len(self._dead),
                "completed": len(self._completed),
                **self._stats
            }
    
    def retry_now(self, task_id: str, retry_func: Callable) -> bool:
        """
        立即重试指定任务
        
        Args:
            task_id: 任务ID
            retry_func: 重试函数
            
        Returns:
            是否重试成功
        """
        entry = self.get_entry(task_id)
        
        if not entry:
            logger.error(f"[DLQ] Task '{task_id}' not found")
            return False
        
        if not entry.can_retry():
            logger.warning(f"[DLQ] Task '{task_id}' cannot be retried (attempts={entry.attempt_count})")
            return False
        
        # 更新状态
        with self._lock:
            entry.status = DLQStatus.RETRYING
            entry.attempt_count += 1
            entry.last_attempt_at = datetime.now().isoformat()
            
            # 从pending移到retrying
            if entry in self._pending:
                self._pending.remove(entry)
            self._retrying.append(entry)
        
        try:
            # 执行重试
            result = retry_func(entry.payload)
            
            # 成功
            with self._lock:
                entry.status = DLQStatus.SUCCESS
                self._retrying.remove(entry)
                self._completed.append(entry)
                self._stats["total_success"] += 1
            
            logger.info(f"[DLQ] Task '{task_id}' succeeded on attempt {entry.attempt_count}")
            return True
            
        except Exception as e:
            # 失败
            with self._lock:
                entry.error = str(e)
                entry.error_type = type(e).__name__
                entry.status = DLQStatus.DEAD if entry.should_dead() else DLQStatus.PENDING
                
                if entry in self._retrying:
                    self._retrying.remove(entry)
                
                if entry.status == DLQStatus.DEAD:
                    self._dead.append(entry)
                    self._stats["total_dead"] += 1
                    logger.error(f"[DLQ] Task '{task_id}' marked DEAD after {entry.attempt_count} attempts")
                else:
                    entry.next_retry_at = datetime.now().isoformat()
                    self._pending.append(entry)
                    delay = self.retry_config.get_delay(entry.attempt_count)
                    entry.next_retry_at = datetime.fromtimestamp(
                        time.time() + delay
                    ).isoformat()
                    self._stats["total_retried"] += 1
                    logger.warning(f"[DLQ] Task '{task_id}' failed, will retry in {delay:.1f}s")
            
            return False
    
    def start_worker(
        self,
        retry_func: Callable,
        poll_interval: float = 5.0
    ) -> None:
        """
        启动重试工作者
        
        Args:
            retry_func: 重试函数，接收payload，返回结果
            poll_interval: 轮询间隔(秒)
        """
        if self._worker_running:
            logger.warning("[DLQ] Worker already running")
            return
        
        self._worker_func = retry_func
        self._worker_running = True
        
        def worker_loop():
            logger.info("[DLQ] Worker started")
            
            while self._worker_running:
                try:
                    # 获取待重试任务
                    pending = self.get_pending(limit=5)
                    
                    for entry in pending:
                        if not self._worker_running:
                            break
                        
                        # 检查是否到重试时间
                        if entry.next_retry_at:
                            next_time = datetime.fromisoformat(entry.next_retry_at)
                            if datetime.now() < next_time:
                                continue
                        
                        # 执行重试
                        self.retry_now(entry.entry_id, retry_func)
                    
                    # 保存状态
                    if self.storage_path:
                        self._save()
                
                except Exception as e:
                    logger.error(f"[DLQ] Worker error: {e}")
                
                time.sleep(poll_interval)
            
            logger.info("[DLQ] Worker stopped")
        
        self._worker_thread = Thread(target=worker_loop, daemon=True)
        self._worker_thread.start()
    
    def stop_worker(self) -> None:
        """停止重试工作者"""
        self._worker_running = False
        if self._worker_thread:
            self._worker_thread.join(timeout=5)
            self._worker_thread = None
        logger.info("[DLQ] Worker stop requested")
    
    def _save(self) -> None:
        """保存队列状态到文件"""
        if not self.storage_path:
            return
        
        try:
            data = {
                "pending": [e.to_dict() for e in self._pending],
                "dead": [e.to_dict() for e in self._dead],
                "completed": [e.to_dict() for e in self._completed],
                "stats": self._stats
            }
            
            path = Path(self.storage_path)
            path.parent.mkdir(parents=True, exist_ok=True)
            
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            
            logger.debug(f"[DLQ] State saved to {self.storage_path}")
        except Exception as e:
            logger.error(f"[DLQ] Failed to save state: {e}")
    
    def _load(self) -> None:
        """从文件加载队列状态"""
        if not self.storage_path:
            return
        
        path = Path(self.storage_path)
        if not path.exists():
            return
        
        try:
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            with self._lock:
                self._pending = deque(
                    [DLQEntry.from_dict(e) for e in data.get("pending", [])],
                    maxlen=1000
                )
                self._dead = deque(
                    [DLQEntry.from_dict(e) for e in data.get("dead", [])],
                    maxlen=1000
                )
                self._completed = deque(
                    [DLQEntry.from_dict(e) for e in data.get("completed", [])],
                    maxlen=1000
                )
                
                # 重建索引
                self._index = {e.entry_id: e for e in self._pending}
                
                self._stats = data.get("stats", self._stats)
            
            logger.info(f"[DLQ] State loaded from {self.storage_path}")
        except Exception as e:
            logger.error(f"[DLQ] Failed to load state: {e}")
    
    def clear_dead(self) -> int:
        """清空死信列表"""
        with self._lock:
            count = len(self._dead)
            for entry in self._dead:
                self._index.pop(entry.entry_id, None)
            self._dead.clear()
            return count


# 全局单例
_dlq_instance: Optional[DeadLetterQueue] = None


def get_dlq(
    storage_path: Optional[str] = None,
    retry_config: Optional[RetryConfig] = None
) -> DeadLetterQueue:
    """获取全局DLQ实例"""
    global _dlq_instance
    if _dlq_instance is None:
        _dlq_instance = DeadLetterQueue(storage_path, retry_config)
    return _dlq_instance
