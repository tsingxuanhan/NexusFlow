# -*- coding: utf-8 -*-
"""
铉枢·炉守 定时任务工具
XuanHub Scheduler Tool — Phase 3

双重接口: BaseTool JSON调用 + CodeAct全局函数 schedule_task()
轻量级定时任务管理（非Cron级别，Agent内部调度）
"""

import time
import uuid
import logging
import threading
from typing import Any, Callable, Dict, List, Optional
from dataclasses import dataclass, field
from .base_tool import BaseTool, ToolResult

logger = logging.getLogger("Scheduler")


@dataclass
class ScheduledTask:
    """调度任务"""
    task_id: str
    name: str
    callback: Optional[str] = None  # CodeAct代码
    interval: Optional[float] = None  # 间隔秒数（周期任务）
    run_at: Optional[float] = None  # 运行时间戳（一次性）
    repeat: bool = False
    enabled: bool = True
    last_run: Optional[float] = None
    run_count: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)


class TaskScheduler:
    """轻量级任务调度器"""
    
    def __init__(self):
        self._tasks: Dict[str, ScheduledTask] = {}
        self._running = False
        self._thread: Optional[threading.Thread] = None
    
    def add_task(self, task: ScheduledTask) -> str:
        self._tasks[task.task_id] = task
        return task.task_id
    
    def remove_task(self, task_id: str) -> bool:
        if task_id in self._tasks:
            del self._tasks[task_id]
            return True
        return False
    
    def get_task(self, task_id: str) -> Optional[ScheduledTask]:
        return self._tasks.get(task_id)
    
    def list_tasks(self) -> List[Dict]:
        return [
            {
                "task_id": t.task_id,
                "name": t.name,
                "interval": t.interval,
                "repeat": t.repeat,
                "enabled": t.enabled,
                "run_count": t.run_count,
                "last_run": t.last_run,
            }
            for t in self._tasks.values()
        ]


# 全局调度器实例
_scheduler = TaskScheduler()


def schedule_task(
    name: str,
    code: str,
    delay: Optional[float] = None,
    interval: Optional[float] = None,
    repeat: bool = False,
) -> Dict[str, Any]:
    """
    创建定时任务 — CodeAct全局函数
    
    Args:
        name: 任务名称
        code: 要执行的CodeAct代码
        delay: 延迟秒数（一次性任务）
        interval: 间隔秒数（周期任务）
        repeat: 是否周期执行
    
    Returns:
        {"task_id": str, "name": str, "status": str}
    
    CodeAct用法:
        task = schedule_task("daily_report",
                            code='write_file("output/report.md", "Daily report")',
                            interval=86400, repeat=True)
        print(task["task_id"])
    """
    task_id = str(uuid.uuid4())[:8]
    
    run_at = time.time() + delay if delay else None
    
    task = ScheduledTask(
        task_id=task_id,
        name=name,
        callback=code,
        interval=interval,
        run_at=run_at,
        repeat=repeat or (interval is not None),
    )
    
    _scheduler.add_task(task)
    logger.info(f"[Scheduler] Created task: {task_id} '{name}'")
    
    return {
        "task_id": task_id,
        "name": name,
        "status": "scheduled",
        "interval": interval,
        "repeat": task.repeat,
    }


def cancel_task(task_id: str) -> Dict[str, Any]:
    """取消定时任务"""
    success = _scheduler.remove_task(task_id)
    return {"task_id": task_id, "cancelled": success}


def list_scheduled_tasks() -> List[Dict]:
    """列出所有调度任务"""
    return _scheduler.list_tasks()


class SchedulerTool(BaseTool):
    """定时任务工具 — BaseTool JSON兼容"""
    
    def __init__(self):
        super().__init__(
            name="scheduler",
            description="Schedule delayed or periodic tasks. Tasks execute CodeAct code at specified intervals.",
            parameters={
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "enum": ["schedule", "cancel", "list"],
                        "description": "Action type",
                        "default": "schedule"
                    },
                    "name": {
                        "type": "string",
                        "description": "Task name"
                    },
                    "code": {
                        "type": "string",
                        "description": "CodeAct code to execute"
                    },
                    "delay": {
                        "type": "number",
                        "description": "Delay in seconds (one-time task)"
                    },
                    "interval": {
                        "type": "number",
                        "description": "Interval in seconds (periodic task)"
                    },
                    "task_id": {
                        "type": "string",
                        "description": "Task ID (for cancel)"
                    }
                },
                "required": ["action"]
            }
        )
    
    def execute(self, action: str = "schedule", name: str = "", code: str = "",
                delay: Optional[float] = None, interval: Optional[float] = None,
                task_id: str = "", **kwargs) -> ToolResult:
        
        if action == "schedule":
            if not name or not code:
                return ToolResult(success=False, error="name and code required")
            result = schedule_task(name, code, delay=delay, interval=interval)
            return ToolResult(success=True, output=result)
        
        elif action == "cancel":
            if not task_id:
                return ToolResult(success=False, error="task_id required")
            result = cancel_task(task_id)
            return ToolResult(success=True, output=result)
        
        elif action == "list":
            result = list_scheduled_tasks()
            return ToolResult(success=True, output=result)
        
        else:
            return ToolResult(success=False, error=f"Unknown action: {action}")
