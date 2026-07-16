# -*- coding: utf-8 -*-
"""
任务树 (TaskTree) — 层次化任务分解与调度
XuanHub v4.0 Phase 2 — Planning Engine

借鉴 Magentic-One Orchestrator + TeLLAgent 双Agent分离的任务管理范式。
每个TaskNode是一棵可递归的子树，TaskTree管理全局状态和调度。
"""

import json
import re
import uuid
import logging
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any, Literal, Tuple
from datetime import datetime

logger = logging.getLogger("TaskTree")


@dataclass
class TaskNode:
    """任务节点 — 可递归的子树
    
    每个节点代表一个可执行或需进一步分解的任务。
    叶子节点(无subtasks)是原子执行单元。
    """
    id: str = field(default_factory=lambda: f"T-{uuid.uuid4().hex[:6]}")
    description: str = ""
    status: Literal["pending", "running", "done", "failed", "blocked", "skipped"] = "pending"
    
    # 分配信息 — TeLLAgent双Agent分离
    assigned_agent: Optional[str] = None       # planner/researcher/executor/reviewer
    assigned_model: Literal["pro", "flash"] = "flash"
    action_type: Literal["plan", "execute", "codeact", "tool_call", "research", "review"] = "execute"
    
    # 依赖关系
    dependencies: List[str] = field(default_factory=list)  # 依赖的TaskNode.id列表
    
    # 执行信息
    result: Optional[str] = None
    error: Optional[str] = None
    score: Optional[float] = None       # 0.0~1.0，执行质量评分
    
    # 时间
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    
    # 子任务
    subtasks: List["TaskNode"] = field(default_factory=list)
    
    # 元数据
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    # Phase 7: 认知分工支持
    execution_mode: Literal["sequential", "cognitive_division"] = "sequential"
    decomposition_strategy: Optional[str] = None
    perspective_count: int = 2
    max_communication_rounds: int = 2
    
    @property
    def needs_collaborative_reasoning(self) -> bool:
        """Phase 7: 是否需要认知分工"""
        return self.execution_mode == "cognitive_division"
    
    # ---- 属性 ----
    
    @property
    def is_leaf(self) -> bool:
        """是否叶子节点（原子执行单元）"""
        return len(self.subtasks) == 0
    
    @property
    def is_ready(self) -> bool:
        """是否可执行（pending + 所有依赖已完成）"""
        return self.status == "pending"
    
    @property
    def is_terminal(self) -> bool:
        """是否终止状态"""
        return self.status in ("done", "failed", "skipped")
    
    @property
    def depth(self) -> int:
        """子树深度"""
        if not self.subtasks:
            return 0
        return 1 + max(st.depth for st in self.subtasks)
    
    @property
    def total_tasks(self) -> int:
        """子树总任务数"""
        return 1 + sum(st.total_tasks for st in self.subtasks)
    
    @property
    def progress(self) -> float:
        """完成进度 0.0~1.0"""
        if self.is_leaf:
            return 1.0 if self.status == "done" else 0.0
        if not self.subtasks:
            return 0.0
        return sum(st.progress for st in self.subtasks) / len(self.subtasks)
    
    # ---- 方法 ----
    
    def find(self, task_id: str) -> Optional["TaskNode"]:
        """按ID查找节点"""
        if self.id == task_id:
            return self
        for st in self.subtasks:
            found = st.find(task_id)
            if found:
                return found
        return None
    
    def find_all(self, status: str = None, action_type: str = None) -> List["TaskNode"]:
        """查找所有匹配条件的节点"""
        results = []
        match = True
        if status and self.status != status:
            match = False
        if action_type and self.action_type != action_type:
            match = False
        if match:
            results.append(self)
        for st in self.subtasks:
            results.extend(st.find_all(status=status, action_type=action_type))
        return results
    
    def add_subtask(self, description: str, **kwargs) -> "TaskNode":
        """添加子任务"""
        node = TaskNode(description=description, **kwargs)
        self.subtasks.append(node)
        return node
    
    def update_status(self, status: str, result: str = None, error: str = None, score: float = None) -> None:
        """更新状态"""
        self.status = status
        if status == "running" and not self.started_at:
            self.started_at = datetime.now().isoformat()
        if status in ("done", "failed", "skipped"):
            self.completed_at = datetime.now().isoformat()
        if result is not None:
            self.result = result
        if error is not None:
            self.error = error
        if score is not None:
            self.score = score
    
    def flatten(self) -> List["TaskNode"]:
        """展平为一维列表（深度优先）"""
        result = [self]
        for st in self.subtasks:
            result.extend(st.flatten())
        return result
    
    def to_dict(self) -> Dict:
        """序列化"""
        return {
            "id": self.id,
            "description": self.description,
            "status": self.status,
            "assigned_agent": self.assigned_agent,
            "assigned_model": self.assigned_model,
            "action_type": self.action_type,
            "dependencies": self.dependencies,
            "result": self.result,
            "error": self.error,
            "score": self.score,
            "created_at": self.created_at,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "subtasks": [st.to_dict() for st in self.subtasks],
            "metadata": self.metadata,
            # Phase 7: 认知分工字段
            "execution_mode": self.execution_mode,
            "decomposition_strategy": self.decomposition_strategy,
            "perspective_count": self.perspective_count,
            "max_communication_rounds": self.max_communication_rounds,
        }
    
    @classmethod
    def from_dict(cls, d: Dict) -> "TaskNode":
        """反序列化"""
        node = cls(
            id=d.get("id", f"T-{uuid.uuid4().hex[:6]}"),
            description=d.get("description", ""),
            status=d.get("status", "pending"),
            assigned_agent=d.get("assigned_agent"),
            assigned_model=d.get("assigned_model", "flash"),
            action_type=d.get("action_type", "execute"),
            dependencies=d.get("dependencies", []),
            result=d.get("result"),
            error=d.get("error"),
            score=d.get("score"),
            created_at=d.get("created_at", datetime.now().isoformat()),
            started_at=d.get("started_at"),
            completed_at=d.get("completed_at"),
            metadata=d.get("metadata", {}),
        )
        for st_dict in d.get("subtasks", []):
            node.subtasks.append(cls.from_dict(st_dict))
        return node
    
    def to_prompt(self, indent: int = 0) -> str:
        """序列化为可注入prompt的缩进文本"""
        prefix = "  " * indent
        status_icon = {
            "pending": "⏳", "running": "🔄", "done": "✅",
            "failed": "❌", "blocked": "🚫", "skipped": "⏭️",
        }.get(self.status, "❓")
        
        lines = [f"{prefix}{status_icon} [{self.id}] {self.description}"]
        if self.result and self.status == "done":
            # 结果摘要，最多100字
            summary = self.result[:100] + "..." if len(self.result) > 100 else self.result
            lines.append(f"{prefix}   结果: {summary}")
        if self.error and self.status == "failed":
            lines.append(f"{prefix}   错误: {self.error[:100]}")
        if self.dependencies:
            lines.append(f"{prefix}   依赖: {', '.join(self.dependencies)}")
        
        for st in self.subtasks:
            lines.append(st.to_prompt(indent + 1))
        
        return "\n".join(lines)


class TaskTree:
    """任务树 — 层次化任务分解与调度管理
    
    核心职责：
    1. 维护任务层次结构
    2. 依赖解析和就绪检测
    3. 调度策略（关键路径、优先级）
    4. 状态追踪和进度报告
    """
    
    def __init__(self, root: TaskNode = None):
        self.root = root or TaskNode(description="ROOT", status="pending")
        self._id_index: Dict[str, TaskNode] = {}
        self._rebuild_index()
    
    def _rebuild_index(self) -> None:
        """重建ID索引"""
        self._id_index.clear()
        for node in self.root.flatten():
            self._id_index[node.id] = node
    
    # ---- 查询 ----
    
    def find(self, task_id: str) -> Optional[TaskNode]:
        """按ID查找节点"""
        return self._id_index.get(task_id)
    
    def next_ready(self) -> List[TaskNode]:
        """返回所有依赖已完成、可立即执行的pending叶子节点"""
        ready = []
        for node in self.root.flatten():
            if not node.is_leaf or node.status != "pending":
                continue
            # 检查所有依赖是否完成
            deps_met = True
            for dep_id in node.dependencies:
                dep = self._id_index.get(dep_id)
                if not dep or dep.status != "done":
                    deps_met = False
                    break
            if deps_met:
                ready.append(node)
        
        # 按优先级排序：有更多后续依赖的优先（关键路径优先）
        ready.sort(key=lambda n: -self._downstream_count(n.id))
        return ready
    
    def _downstream_count(self, task_id: str) -> int:
        """计算下游依赖数（有多少节点依赖此节点）"""
        count = 0
        for node in self.root.flatten():
            if task_id in node.dependencies:
                count += 1
        return count
    
    def critical_path(self) -> List[TaskNode]:
        """关键路径 — 决定总耗时的最长依赖链"""
        if not self.root.subtasks:
            return [self.root] if self.root.is_leaf else []
        
        # 收集所有叶子节点
        leaves = self.root.find_all(status=None)
        leaves = [n for n in leaves if n.is_leaf]
        
        if not leaves:
            return []
        
        # 找到最长依赖链（简化版：按深度排序）
        paths = []
        for leaf in leaves:
            path = self._trace_path(leaf)
            paths.append(path)
        
        return max(paths, key=len) if paths else []
    
    def _trace_path(self, node: TaskNode) -> List[TaskNode]:
        """从节点回溯到根的路径"""
        path = [node]
        current_deps = node.dependencies[:]
        visited = {node.id}
        
        while current_deps:
            dep_id = current_deps.pop(0)
            if dep_id in visited:
                continue
            dep_node = self._id_index.get(dep_id)
            if dep_node:
                path.append(dep_node)
                visited.add(dep_node.id)
                current_deps.extend(dep_node.dependencies)
        
        return list(reversed(path))
    
    def blocked_nodes(self) -> List[TaskNode]:
        """返回被阻塞的节点"""
        blocked = []
        for node in self.root.flatten():
            if node.status == "pending" and node.dependencies:
                for dep_id in node.dependencies:
                    dep = self._id_index.get(dep_id)
                    if dep and dep.status == "failed":
                        blocked.append(node)
                        break
        return blocked
    
    def failed_nodes(self) -> List[TaskNode]:
        """返回失败的节点"""
        return self.root.find_all(status="failed")
    
    def running_nodes(self) -> List[TaskNode]:
        """返回正在执行的节点"""
        return self.root.find_all(status="running")
    
    # ---- 修改 ----
    
    def add_task(self, parent_id: str, description: str, **kwargs) -> Optional[TaskNode]:
        """在指定父节点下添加子任务"""
        parent = self.find(parent_id)
        if not parent:
            logger.warning(f"父节点 {parent_id} 不存在")
            return None
        
        node = parent.add_subtask(description, **kwargs)
        self._id_index[node.id] = node
        return node
    
    def update_task(self, task_id: str, **kwargs) -> bool:
        """更新任务状态"""
        node = self.find(task_id)
        if not node:
            return False
        
        if "status" in kwargs:
            node.update_status(
                kwargs["status"],
                result=kwargs.get("result"),
                error=kwargs.get("error"),
                score=kwargs.get("score"),
            )
        if "assigned_agent" in kwargs:
            node.assigned_agent = kwargs["assigned_agent"]
        if "assigned_model" in kwargs:
            node.assigned_model = kwargs["assigned_model"]
        if "action_type" in kwargs:
            node.action_type = kwargs["action_type"]
        
        # 自动传播：如果父节点所有子任务完成，标记父节点完成
        self._propagate_completion()
        return True
    
    def _propagate_completion(self) -> None:
        """向上传播完成状态"""
        for node in self.root.flatten():
            if node.subtasks and node.status != "done":
                all_done = all(st.is_terminal for st in node.subtasks)
                any_failed = any(st.status == "failed" for st in node.subtasks)
                if all_done:
                    node.status = "failed" if any_failed else "done"
                    node.completed_at = datetime.now().isoformat()
    
    # ---- 统计 ----
    
    @property
    def progress(self) -> float:
        """总进度 0.0~1.0"""
        return self.root.progress
    
    @property
    def stats(self) -> Dict[str, int]:
        """统计信息"""
        all_nodes = self.root.flatten()
        return {
            "total": len(all_nodes),
            "pending": sum(1 for n in all_nodes if n.status == "pending"),
            "running": sum(1 for n in all_nodes if n.status == "running"),
            "done": sum(1 for n in all_nodes if n.status == "done"),
            "failed": sum(1 for n in all_nodes if n.status == "failed"),
            "blocked": sum(1 for n in all_nodes if n.status == "blocked"),
        }
    
    # ---- 序列化 ----
    
    def to_dict(self) -> Dict:
        return self.root.to_dict()
    
    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent, ensure_ascii=False)
    
    def to_prompt(self) -> str:
        """序列化为可注入prompt的任务树描述"""
        s = self.stats
        header = f"## 任务树 (进度: {self.progress:.0%} | {s['done']}/{s['total']}完成"
        if s["failed"]:
            header += f" | {s['failed']}失败"
        header += ")"
        
        return header + "\n" + self.root.to_prompt()
    
    @classmethod
    def from_dict(cls, d: Dict) -> "TaskTree":
        root = TaskNode.from_dict(d)
        tree = cls(root=root)
        return tree
    
    @classmethod
    def from_json(cls, json_str: str) -> "TaskTree":
        return cls.from_dict(json.loads(json_str))
    
    @classmethod
    def from_plan_text(cls, plan_text: str, goal: str = "目标") -> "TaskTree":
        """从规划文本解析任务树
        
        支持：
        - "1. 任务描述" 格式
        - "1.1 子任务描述" 格式（层级）
        - "- [依赖: T-xxx] 任务描述" 格式
        """
        root = TaskNode(description=goal, status="pending", action_type="plan")
        current_major = None
        
        for line in plan_text.split("\n"):
            stripped = line.strip()
            if not stripped:
                continue
            
            # 匹配 "1." "1)" "步骤1" 格式
            major_match = re.match(r'^(\d+)[\.\)、]\s*(.+)', stripped)
            sub_match = re.match(r'^(\d+)\.(\d+)[\.\)、]\s*(.+)', stripped)
            
            # 检查依赖标记
            dep_ids = []
            dep_match = re.search(r'\[依赖[:：]\s*([^\]]+)\]', stripped)
            if dep_match:
                dep_str = dep_match.group(1)
                dep_ids = [d.strip() for d in dep_str.split(",") if d.strip()]
                stripped = re.sub(r'\[依赖[:：][^\]]+\]\s*', '', stripped).strip()
            
            # 检查Agent分配标记
            assigned = None
            agent_match = re.search(r'\[([^\]]*Agent|[^\]]*Planner|[^\]]*Researcher|[^\]]*Executor|[^\]]*Reviewer)\]', stripped)
            if agent_match:
                assigned = agent_match.group(1)
                stripped = re.sub(r'\[[^\]]*(?:Agent|Planner|Researcher|Executor|Reviewer)[^\]]*\]\s*', '', stripped).strip()
            
            if sub_match:
                # 子任务
                if current_major:
                    desc = sub_match.group(3) if len(sub_match.groups()) >= 3 else sub_match.group(0)
                    node = current_major.add_subtask(
                        description=desc,
                        dependencies=dep_ids,
                        assigned_agent=assigned,
                    )
                    root_id = root.id  # 不会用到但避免引用问题
            elif major_match:
                # 主要任务
                desc = major_match.group(2)
                current_major = root.add_subtask(
                    description=desc,
                    dependencies=dep_ids,
                    assigned_agent=assigned,
                    assigned_model="pro",
                    action_type="plan",
                )
                self_id = current_major.id  # for debugging
        
        tree = cls(root=root)
        return tree


# ============================================================================
# 任务调度器 — 决定执行顺序和Agent分配
# ============================================================================

class TaskScheduler:
    """任务调度器 — 根据策略决定执行顺序和Agent分配
    
    TeLLAgent核心：StrategyAgent选策略，ExecutionAgent执行。
    调度器桥接TaskTree和双Agent分离架构。
    """
    
    # 策略类型
    STRATEGY_SEQUENTIAL = "sequential"    # 顺序执行
    STRATEGY_PARALLEL = "parallel"        # 并行执行
    STRATEGY_ITERATIVE = "iterative"      # 迭代精化
    STRATEGY_CODEACT = "codeact"          # 代码执行
    
    # Agent能力映射
    AGENT_CAPABILITIES = {
        "planner":   {"actions": ["plan"], "model": "pro"},
        "researcher": {"actions": ["research"], "model": "flash"},
        "executor":  {"actions": ["execute", "codeact", "tool_call"], "model": "flash"},
        "reviewer":  {"actions": ["review"], "model": "flash"},
    }
    
    def __init__(self, tree: TaskTree):
        self.tree = tree
    
    def schedule(self) -> List[Dict]:
        """生成执行计划
        
        Returns:
            按顺序执行的步骤列表，每个步骤含:
            - task_id: 任务ID
            - agent: 分配的Agent
            - model: 使用的模型
            - strategy: 执行策略
            - depends_on: 前置步骤
        """
        steps = []
        ready = self.tree.next_ready()
        scheduled_ids = set()
        
        # 多轮调度，直到所有任务被安排
        max_rounds = 50
        for _ in range(max_rounds):
            if not ready:
                break
            
            for node in ready:
                if node.id in scheduled_ids:
                    continue
                
                # 自动分配Agent
                agent = self._auto_assign_agent(node)
                strategy = self._select_strategy(node)
                
                step = {
                    "task_id": node.id,
                    "description": node.description,
                    "agent": agent,
                    "model": self.AGENT_CAPABILITIES[agent]["model"],
                    "strategy": strategy,
                    "depends_on": node.dependencies,
                }
                steps.append(step)
                scheduled_ids.add(node.id)
                
                # 标记为running（调度阶段）
                self.tree.update_task(node.id, status="running", assigned_agent=agent)
            
            # 下一轮就绪任务
            ready = self.tree.next_ready()
        
        # 重置所有为pending（调度只是规划，还没真正执行）
        for node in self.tree.root.flatten():
            if node.status == "running":
                node.status = "pending"
                node.started_at = None
        
        return steps
    
    def _auto_assign_agent(self, node: TaskNode) -> str:
        """根据action_type自动分配Agent"""
        action = node.action_type
        
        for agent_name, caps in self.AGENT_CAPABILITIES.items():
            if action in caps["actions"]:
                return agent_name
        
        # 默认分配给executor
        return "executor"
    
    def _select_strategy(self, node: TaskNode) -> str:
        """根据任务特征选择执行策略"""
        # 有代码生成需求的 → CodeAct
        code_keywords = ["代码", "code", "实现", "脚本", "script", "编写", "开发"]
        if any(kw in node.description.lower() for kw in code_keywords):
            return self.STRATEGY_CODEACT
        
        # 有搜索/研究需求的 → Iterative（搜索→验证→补充）
        research_keywords = ["调研", "研究", "搜索", "检索", "分析", "调研"]
        if any(kw in node.description.lower() for kw in research_keywords):
            return self.STRATEGY_ITERATIVE
        
        # 有依赖关系的 → Sequential
        if node.dependencies:
            return self.STRATEGY_SEQUENTIAL
        
        # 默认
        return self.STRATEGY_SEQUENTIAL
    
    def get_execution_order(self) -> List[str]:
        """获取执行顺序（拓扑排序）"""
        steps = self.schedule()
        return [s["task_id"] for s in steps]
