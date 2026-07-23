# -*- coding: utf-8 -*-
"""
数据类、枚举与映射表 — 从 base_agent.py 提取
Data classes, enums, and mapping tables extracted from base_agent.py
"""

import re
import logging
from typing import List, Dict, Optional, Any, Callable
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

logger = logging.getLogger("BaseAgent")


class _nullcontext:
    """空上下文管理器（用于tracer可选时的with语句）"""
    def __enter__(self): return self
    def __exit__(self, *args): pass


@dataclass
class Message:
    """对话消息"""
    role: str  # system, user, assistant
    content: str
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    
    def to_dict(self) -> Dict:
        return {"role": self.role, "content": self.content}


# ============================================================================
# v4.0 新增: Agent角色 + 运行模式
# ============================================================================

class AgentRole(Enum):
    """泛化Agent角色 — 与领域正交"""
    PLANNER = "planner"       # 规划：分解任务，策略推理（PRO模型）
    RESEARCHER = "researcher"  # 研究：检索、挖掘、验证
    EXECUTOR = "executor"     # 执行：代码、脚本、工具调用（Flash模型）
    REVIEWER = "reviewer"     # 审查：验证、质控、反馈


class AgentRunMode(Enum):
    """Agent运行模式 — TeLLAgent双Agent分离"""
    PLAN = "plan"       # 策略推理（PRO）— 只规划不执行
    EXECUTE = "execute"  # 精确执行（Flash）— 按计划逐步执行
    REFLECT = "reflect"  # 反思评估（PRO）— 评估结果，修正计划


# 角色默认模型映射
ROLE_MODEL_MAP = {
    AgentRole.PLANNER: "pro",
    AgentRole.RESEARCHER: "flash",
    AgentRole.EXECUTOR: "flash",
    AgentRole.REVIEWER: "flash",
}

# 模式默认模型映射
MODE_MODEL_MAP = {
    AgentRunMode.PLAN: "pro",
    AgentRunMode.EXECUTE: "flash",
    AgentRunMode.REFLECT: "pro",
}


@dataclass
class TodoItem:
    """待办事项"""
    id: str
    task: str
    priority: int = 0
    status: str = "pending"  # pending / running / done / failed / blocked
    result: Optional[str] = None
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    
    def to_dict(self) -> Dict:
        return {
            "id": self.id, "task": self.task, "priority": self.priority,
            "status": self.status, "result": self.result, "created_at": self.created_at,
        }


class TodoProvider:
    """任务追踪器 — 让Agent知道自己还有什么没做"""
    
    def __init__(self):
        self._todos: Dict[str, TodoItem] = {}
        self._counter = 0
    
    def add(self, task: str, priority: int = 0) -> str:
        self._counter += 1
        tid = f"todo_{self._counter}"
        self._todos[tid] = TodoItem(id=tid, task=task, priority=priority)
        return tid
    
    def complete(self, task_id: str, result: str = None) -> bool:
        if task_id in self._todos:
            self._todos[task_id].status = "done"
            self._todos[task_id].result = result
            return True
        return False
    
    def fail(self, task_id: str, reason: str = None) -> bool:
        if task_id in self._todos:
            self._todos[task_id].status = "failed"
            self._todos[task_id].result = reason
            return True
        return False
    
    def start(self, task_id: str) -> bool:
        if task_id in self._todos:
            self._todos[task_id].status = "running"
            return True
        return False
    
    def get_pending(self) -> List[TodoItem]:
        items = [t for t in self._todos.values() if t.status == "pending"]
        return sorted(items, key=lambda x: -x.priority)
    
    def get_running(self) -> List[TodoItem]:
        return [t for t in self._todos.values() if t.status == "running"]
    
    def get_all(self) -> List[TodoItem]:
        return list(self._todos.values())
    
    def to_context(self) -> str:
        """生成可注入system prompt的待办列表"""
        pending = self.get_pending()
        running = self.get_running()
        if not pending and not running:
            return ""
        
        lines = ["## 当前任务列表"]
        if running:
            lines.append("### 进行中")
            for t in running:
                lines.append(f"  🔄 [{t.id}] {t.task}")
        if pending:
            lines.append("### 待执行")
            for t in pending:
                lines.append(f"  ⏳ [{t.id}] (P{t.priority}) {t.task}")
        done = [t for t in self._todos.values() if t.status == "done"]
        if done:
            lines.append(f"### 已完成 ({len(done)}项)")
        return "\n".join(lines)


class ContextCompactor:
    """上下文压缩器 — 监控token使用，超阈值自动摘要
    
    借鉴 Microsoft Agent Framework 的 Agent Harness ContextCompactor。
    用Flash模型压缩历史对话，保留最近几轮不压缩。
    """
    
    def __init__(self, threshold: int = 8000, keep_recent: int = 4, model: str = "flash"):
        self.threshold = threshold    # token阈值（粗估：1中文字≈2token）
        self.keep_recent = keep_recent  # 保留最近N轮不压缩
        self.model = model
        self._compacted = False
    
    def estimate_tokens(self, messages: List[Dict]) -> int:
        """粗估token数 — 中文约2token/字，英文约1.3token/字"""
        total = 0
        for msg in messages:
            content = msg.get("content", "")
            # 中文字符数
            cn_chars = len(re.findall(r'[\u4e00-\u9fff]', content))
            other_chars = len(content) - cn_chars
            total += cn_chars * 2 + int(other_chars * 1.3)
        return total
    
    def check_and_compact(self, messages: List[Dict], api_call: Callable = None) -> List[Dict]:
        """检查是否需要压缩，需要则压缩
        
        Args:
            messages: 消息列表
            api_call: 可选的API调用函数，用于LLM摘要。为None时用截断策略。
            
        Returns:
            压缩后的消息列表
        """
        estimated = self.estimate_tokens(messages)
        
        if estimated < self.threshold * 0.8:
            self._compacted = False
            return messages
        
        if self._compacted:
            # 已经压缩过，再超阈值就截断
            return self._truncate(messages)
        
        # 第一次超阈值：尝试LLM摘要
        if api_call and len(messages) > self.keep_recent + 2:
            compacted = self._llm_compact(messages, api_call)
            if compacted:
                self._compacted = True
                return compacted
        
        # Fallback：截断
        return self._truncate(messages)
    
    def _llm_compact(self, messages: List[Dict], api_call: Callable) -> Optional[List[Dict]]:
        """用LLM摘要压缩历史"""
        # 分离：system消息 + 历史消息 + 最近消息
        system_msgs = [m for m in messages if m.get("role") == "system"]
        non_system = [m for m in messages if m.get("role") != "system"]
        
        if len(non_system) <= self.keep_recent:
            return None
        
        history = non_system[:-self.keep_recent]
        recent = non_system[-self.keep_recent:]
        
        # 构造摘要请求
        history_text = "\n".join(
            f"[{m.get('role', 'unknown')}]: {m.get('content', '')[:300]}"
            for m in history
        )
        
        summary_prompt = f"请用简洁的中文总结以下对话历史的关键信息，保留重要结论、决策和未完成任务：\n\n{history_text}"
        
        try:
            summary = api_call(summary_prompt)
            if summary:
                compact_msg = {
                    "role": "system",
                    "content": f"[历史摘要]\n{summary}"
                }
                return system_msgs + [compact_msg] + recent
        except Exception as e:
            logger.warning(f"ContextCompactor LLM摘要失败: {e}")
        
        return None
    
    def _truncate(self, messages: List[Dict]) -> List[Dict]:
        """截断策略：保留system + 最近消息"""
        system_msgs = [m for m in messages if m.get("role") == "system"]
        non_system = [m for m in messages if m.get("role") != "system"]
        
        # 保留最近的消息
        keep = non_system[-self.keep_recent:]
        
        # 加截断标记
        if len(non_system) > self.keep_recent:
            truncation_notice = {
                "role": "system",
                "content": f"[注意] 之前{len(non_system) - self.keep_recent}条对话已因长度限制被截断。"
            }
            return system_msgs + [truncation_notice] + keep
        
        return system_msgs + keep
