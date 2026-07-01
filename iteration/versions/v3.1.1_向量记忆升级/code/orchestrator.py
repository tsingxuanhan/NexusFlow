# -*- coding: utf-8 -*-
"""
铉枢·炉守 工作流编排器
XuanHub Task Orchestrator - DAG-based workflow execution
"""

import logging
import time
import json
from typing import List, Dict, Optional, Any, Callable
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime

logger = logging.getLogger("TaskOrchestrator")


class ExecutionMode(Enum):
    """执行模式"""
    SEQUENTIAL = "sequential"      # 顺序执行
    PARALLEL = "parallel"          # 并行执行
    CONDITIONAL = "conditional"     # 条件分支


@dataclass
class Task:
    """任务定义"""
    name: str
    func: Callable
    params: Dict[str, Any] = field(default_factory=dict)
    depends_on: List[str] = field(default_factory=list)
    description: str = ""
    timeout: int = 300  # 超时时间(秒)
    
    def __hash__(self):
        return hash(self.name)


@dataclass
class TaskResult:
    """任务执行结果"""
    task_name: str
    success: bool
    result: Any = None
    error: Optional[str] = None
    duration: float = 0.0
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())


class TaskOrchestrator:
    """
    DAG工作流编排器
    
    支持:
    - 顺序执行 (sequential)
    - 并行执行 (parallel) - 同一层级的任务
    - 条件分支 (conditional)
    - 检查点保存与恢复
    """
    
    def __init__(self, name: str = "orchestrator"):
        self.name = name
        self.tasks: Dict[str, Task] = {}
        self.results: Dict[str, TaskResult] = {}
        self.checkpoints: Dict[str, Any] = {}
        
        logger.info(f"[{self.name}] TaskOrchestrator initialized")
    
    def add_task(
        self,
        name: str,
        func: Callable,
        params: Dict[str, Any] = None,
        depends_on: List[str] = None,
        description: str = "",
        timeout: int = 300
    ) -> 'TaskOrchestrator':
        """
        添加任务
        
        Args:
            name: 任务名称(唯一标识)
            func: 任务函数
            params: 任务参数
            depends_on: 依赖的任务名称列表
            description: 任务描述
            timeout: 超时时间(秒)
            
        Returns:
            self (支持链式调用)
        """
        task = Task(
            name=name,
            func=func,
            params=params or {},
            depends_on=depends_on or [],
            description=description,
            timeout=timeout
        )
        self.tasks[name] = task
        logger.debug(f"[{self.name}] Added task: {name}")
        return self
    
    def _get_execution_order(self) -> List[List[str]]:
        """
        获取拓扑排序的执行顺序
        
        Returns:
            二维列表，外层是层级，内层是同一层可并行的任务
        """
        # 计算入度
        in_degree = {name: 0 for name in self.tasks}
        for name, task in self.tasks.items():
            for dep in task.depends_on:
                if dep not in self.tasks:
                    raise ValueError(f"Task '{name}' depends on unknown task '{dep}'")
                in_degree[name] += 1
        
        # Kahn算法
        layers = []
        current_layer = [name for name, degree in in_degree.items() if degree == 0]
        
        while current_layer:
            layers.append(current_layer)
            next_layer = []
            
            for name in current_layer:
                for other_name, task in self.tasks.items():
                    if name in task.depends_on:
                        in_degree[other_name] -= 1
                        if in_degree[other_name] == 0:
                            next_layer.append(other_name)
            
            current_layer = next_layer
        
        # 检测循环依赖
        if sum(len(layer) for layer in layers) != len(self.tasks):
            raise ValueError("Circular dependency detected in tasks")
        
        return layers
    
    def execute(self, mode: ExecutionMode = ExecutionMode.SEQUENTIAL) -> Dict[str, TaskResult]:
        """
        执行工作流
        
        Args:
            mode: 执行模式
            
        Returns:
            任务名称 -> TaskResult 的字典
        """
        execution_order = self._get_execution_order()
        logger.info(f"[{self.name}] Starting workflow with {len(self.tasks)} tasks")
        
        for layer_idx, layer in enumerate(execution_order):
            logger.info(f"[{self.name}] Executing layer {layer_idx + 1}/{len(execution_order)}: {layer}")
            
            if mode == ExecutionMode.PARALLEL:
                # 并行执行当前层
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor(max_workers=len(layer)) as executor:
                    futures = {}
                    for task_name in layer:
                        task = self.tasks[task_name]
                        # 注入依赖任务的执行结果
                        params = task.params.copy()
                        for dep_name in task.depends_on:
                            if dep_name in self.results:
                                params[f"{dep_name}_result"] = self.results[dep_name].result
                        
                        future = executor.submit(self._execute_task, task, params)
                        futures[future] = task_name
                    
                    for future in concurrent.futures.as_completed(futures, timeout=max(t.timeout for t in self.tasks.values())):
                        task_name = futures[future]
                        try:
                            result = future.result()
                            self.results[task_name] = result
                        except Exception as e:
                            logger.error(f"[{self.name}] Task {task_name} failed: {e}")
                            self.results[task_name] = TaskResult(
                                task_name=task_name,
                                success=False,
                                error=str(e)
                            )
            else:
                # 顺序执行
                for task_name in layer:
                    task = self.tasks[task_name]
                    
                    # 注入依赖任务的执行结果
                    params = task.params.copy()
                    for dep_name in task.depends_on:
                        if dep_name in self.results:
                            params[f"{dep_name}_result"] = self.results[dep_name].result
                    
                    result = self._execute_task(task, params)
                    self.results[task_name] = result
                    
                    if not result.success and mode == ExecutionMode.CONDITIONAL:
                        logger.warning(f"[{self.name}] Task {task_name} failed, stopping workflow")
                        break
        
        logger.info(f"[{self.name}] Workflow completed, {sum(1 for r in self.results.values() if r.success)}/{len(self.results)} tasks succeeded")
        return self.results
    
    def _execute_task(self, task: Task, params: Dict[str, Any]) -> TaskResult:
        """执行单个任务"""
        start_time = time.time()
        
        try:
            logger.debug(f"[{self.name}] Executing task: {task.name}")
            result = task.func(**params)
            
            return TaskResult(
                task_name=task.name,
                success=True,
                result=result,
                duration=time.time() - start_time
            )
        except Exception as e:
            logger.error(f"[{self.name}] Task {task.name} failed: {e}")
            return TaskResult(
                task_name=task.name,
                success=False,
                error=str(e),
                duration=time.time() - start_time
            )
    
    def save_checkpoint(self, path: str) -> None:
        """保存检查点"""
        checkpoint = {
            "timestamp": datetime.now().isoformat(),
            "results": {
                name: {
                    "success": r.success,
                    "result": str(r.result)[:1000],  # 截断
                    "error": r.error,
                    "duration": r.duration
                }
                for name, r in self.results.items()
            },
            "tasks": list(self.tasks.keys())
        }
        
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(checkpoint, f, ensure_ascii=False, indent=2)
        
        logger.info(f"[{self.name}] Checkpoint saved to {path}")
    
    def get_results(self) -> Dict[str, Any]:
        """获取所有任务结果"""
        return {
            name: result.result 
            for name, result in self.results.items() 
            if result.success
        }
    
    def reset(self) -> None:
        """重置执行状态"""
        self.results.clear()
        logger.info(f"[{self.name}] Reset")
    
    def __repr__(self) -> str:
        return f"<TaskOrchestrator(name={self.name}, tasks={len(self.tasks)})>"
