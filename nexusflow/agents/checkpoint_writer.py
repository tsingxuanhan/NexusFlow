# -*- coding: utf-8 -*-
"""
铉枢·炉守 Checkpoint Writer — 异步检查点写入器
XuanHub Checkpoint Writer

参考 MiMo Code 的 checkpoint-writer 设计，独立子Agent后台写状态。

核心功能：
1. 异步写入结构化状态（11个字段）
2. 上下文利用率达20%/45%/70%时增量更新
3. 上下文接近上限时从持久化文件重建新窗口
4. 单写者约束，防止并发写导致不一致
5. notes.md机制，主Agent可追加自由形式笔记

11个字段：
- current_intent: 当前意图
- next_action: 下一步动作
- working_constraints: 工作约束
- task_tree: 任务树
- current_work: 当前工作
- involved_files: 涉及文件
- cross_task_discoveries: 跨任务发现
- errors_and_fixes: 错误与修复
- runtime_state: 运行时状态
- design_decisions: 设计决策
- misc_notes: 杂项笔记
"""

import json
import time
import logging
import os
import threading
from typing import Any, Dict, List, Optional, Set
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from enum import Enum

logger = logging.getLogger("CheckpointWriter")

# 导入配置 — 优先从 config/config.yaml 加载，回退到 config.py（向后兼容）
try:
    from config import (  # noqa: F401 — 向后兼容旧的 config.py
        DEEPSEEK_API_KEY as _cfg_key, DEEPSEEK_ENDPOINT as _cfg_endpoint,
        MODELS as _cfg_models, DEFAULT_PARAMS as _cfg_params, REQUEST_TIMEOUT as _cfg_timeout
    )
except ImportError:
    _cfg_key, _cfg_endpoint, _cfg_models, _cfg_params, _cfg_timeout = None, None, None, None, None

import yaml as _yaml
_config_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'config', 'config.yaml')
_cfg = {}
if os.path.exists(_config_path):
    try:
        with open(_config_path, 'r', encoding='utf-8') as _f:
            _cfg = _yaml.safe_load(_f) or {}
    except Exception:
        _cfg = {}

DEEPSEEK_API_KEY = _cfg_key or os.environ.get("DEEPSEEK_API_KEY", "")
DEEPSEEK_ENDPOINT = _cfg_endpoint or "https://api.deepseek.com/v1/chat/completions"
MODELS = _cfg_models or {"pro": _cfg.get('models', {}).get('pro', {}).get('name', 'deepseek-v4-pro'),
                          "flash": _cfg.get('models', {}).get('flash', {}).get('name', 'deepseek-v4-flash')}
DEFAULT_PARAMS = _cfg_params or {
    "pro": {"temperature": _cfg.get('models', {}).get('pro', {}).get('temperature', 1.0),
            "top_p": _cfg.get('models', {}).get('pro', {}).get('top_p', 1.0),
            "max_tokens": _cfg.get('models', {}).get('pro', {}).get('max_tokens', 4096)},
    "flash": {"temperature": _cfg.get('models', {}).get('flash', {}).get('temperature', 1.0),
              "top_p": _cfg.get('models', {}).get('flash', {}).get('top_p', 1.0),
              "max_tokens": _cfg.get('models', {}).get('flash', {}).get('max_tokens', 2048)}
}
REQUEST_TIMEOUT = _cfg_timeout if _cfg_timeout is not None else _cfg.get('api', {}).get('timeout', 120)


class ContextThreshold(Enum):
    """上下文利用率阈值"""
    LOW = 0.20    # 20% - 首次写入
    MEDIUM = 0.45  # 45% - 增量更新
    HIGH = 0.70    # 70% - 深度更新
    CRITICAL = 0.85  # 85% - 准备重建窗口


@dataclass
class CheckpointState:
    """
    检查点状态 — 包含所有11个字段
    
    单写者约束：每个结构化文件只有一个写者
    """
    # 核心状态字段（11个）
    current_intent: str = ""
    next_action: str = ""
    working_constraints: List[str] = field(default_factory=list)
    task_tree: Dict[str, Any] = field(default_factory=dict)
    current_work: str = ""
    involved_files: List[str] = field(default_factory=list)
    cross_task_discoveries: List[str] = field(default_factory=list)
    errors_and_fixes: List[Dict[str, str]] = field(default_factory=list)
    runtime_state: Dict[str, Any] = field(default_factory=dict)
    design_decisions: List[Dict[str, str]] = field(default_factory=list)
    misc_notes: List[str] = field(default_factory=list)
    
    # 元数据
    checkpoint_id: str = ""
    agent_name: str = ""
    created_at: str = ""
    updated_at: str = ""
    version: int = 1
    
    def to_dict(self) -> Dict:
        return {
            "current_intent": self.current_intent,
            "next_action": self.next_action,
            "working_constraints": self.working_constraints,
            "task_tree": self.task_tree,
            "current_work": self.current_work,
            "involved_files": self.involved_files,
            "cross_task_discoveries": self.cross_task_discoveries,
            "errors_and_fixes": self.errors_and_fixes,
            "runtime_state": self.runtime_state,
            "design_decisions": self.design_decisions,
            "misc_notes": self.misc_notes,
            # 元数据
            "checkpoint_id": self.checkpoint_id,
            "agent_name": self.agent_name,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "version": self.version,
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> "CheckpointState":
        return cls(
            current_intent=data.get("current_intent", ""),
            next_action=data.get("next_action", ""),
            working_constraints=data.get("working_constraints", []),
            task_tree=data.get("task_tree", {}),
            current_work=data.get("current_work", ""),
            involved_files=data.get("involved_files", []),
            cross_task_discoveries=data.get("cross_task_discoveries", []),
            errors_and_fixes=data.get("errors_and_fixes", []),
            runtime_state=data.get("runtime_state", {}),
            design_decisions=data.get("design_decisions", []),
            misc_notes=data.get("misc_notes", []),
            checkpoint_id=data.get("checkpoint_id", ""),
            agent_name=data.get("agent_name", ""),
            created_at=data.get("created_at", ""),
            updated_at=data.get("updated_at", ""),
            version=data.get("version", 1),
        )
    
    def get_stats(self) -> Dict:
        return {
            "version": self.version,
            "updated_at": self.updated_at,
            "fields_populated": sum([
                bool(self.current_intent),
                bool(self.next_action),
                bool(self.current_work),
                len(self.working_constraints),
                len(self.task_tree),
                len(self.involved_files),
                len(self.cross_task_discoveries),
                len(self.errors_and_fixes),
                len(self.design_decisions),
                len(self.misc_notes),
            ]),
        }


class CheckpointWriter:
    """
    异步检查点写入器 — 独立子Agent后台写状态
    
    设计原则：
    1. 单写者约束：每个结构化文件只有一个写者，防止并发写
    2. 增量写入：上下文利用率达阈值时增量更新
    3. 窗口重建：上下文接近上限时从持久化文件重建新窗口
    4. notes.md路由：主Agent可追加笔记，写者读取并路由到对应字段
    
    用法：
        writer = CheckpointWriter(agent_name="test", storage_dir="./checkpoints")
        writer.start()
        
        # 每次交互后检查是否需要写入
        if writer.should_checkpoint(context_usage_ratio):
            writer.update_state(current_intent="xxx", ...)
        
        # 停止时
        writer.stop()
    """
    
    # Token预算配置（总注入控制在65K内）
    MAX_INJECTION_TOKENS = 65000
    
    # 写入间隔（秒）
    MIN_WRITE_INTERVAL = 5
    
    def __init__(
        self,
        agent_name: str,
        storage_dir: str = "./checkpoints",
        model: str = "flash",
        auto_start: bool = True,
        context_threshold_low: float = ContextThreshold.LOW.value,
        context_threshold_medium: float = ContextThreshold.MEDIUM.value,
        context_threshold_high: float = ContextThreshold.HIGH.value,
        context_threshold_critical: float = ContextThreshold.CRITICAL.value,
    ):
        self.agent_name = agent_name
        self.storage_dir = Path(storage_dir)
        self.model = model
        self.auto_start = auto_start
        
        # 阈值配置
        self.threshold_low = context_threshold_low
        self.threshold_medium = context_threshold_medium
        self.threshold_high = context_threshold_high
        self.threshold_critical = context_threshold_critical
        
        # 状态
        self._state = CheckpointState(
            checkpoint_id=f"cp_{agent_name}_{int(time.time())}",
            agent_name=agent_name,
            created_at=datetime.now().isoformat(),
            updated_at=datetime.now().isoformat(),
        )
        
        # 单写者锁
        self._write_lock = threading.Lock()
        
        # 异步写入队列
        self._write_queue: List[Dict[str, Any]] = []
        self._write_thread: Optional[threading.Thread] = None
        self._running = False
        
        # 笔记文件路径
        self.notes_file = self.storage_dir / f"{agent_name}_notes.md"
        
        # 持久化文件路径
        self.checkpoint_file = self.storage_dir / f"{agent_name}_checkpoint.json"
        
        # 统计
        self._stats = {
            "writes": 0,
            "reads": 0,
            "window_rebuilds": 0,
            "notes_processed": 0,
            "last_write_time": 0.0,
            "last_context_usage": 0.0,
        }
        
        # 上次写入时间
        self._last_write_time = 0.0
        
        # 确保存储目录存在
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        
        # 自动启动写线程
        if auto_start:
            self.start()
        
        logger.info(f"[CheckpointWriter] Initialized for agent={agent_name}, storage={storage_dir}")
    
    def start(self) -> None:
        """启动写线程"""
        if self._running:
            return
        
        self._running = True
        self._write_thread = threading.Thread(target=self._write_loop, daemon=True)
        self._write_thread.start()
        logger.info(f"[CheckpointWriter] Write thread started for {self.agent_name}")
    
    def stop(self) -> None:
        """停止写线程"""
        self._running = False
        if self._write_thread and self._write_thread.is_alive():
            self._write_thread.join(timeout=2.0)
        logger.info(f"[CheckpointWriter] Write thread stopped for {self.agent_name}")
    
    def _write_loop(self) -> None:
        """写线程主循环"""
        while self._running:
            try:
                # 处理写队列
                while self._write_queue:
                    task = self._write_queue.pop(0)
                    self._do_write(task)
                
                # 处理notes.md
                self._process_notes()
                
            except Exception as e:
                logger.error(f"[CheckpointWriter] Write loop error: {e}")
            
            time.sleep(1.0)
    
    def _do_write(self, task: Dict[str, Any]) -> None:
        """执行写入任务"""
        with self._write_lock:
            try:
                # 更新状态
                for key, value in task.items():
                    if hasattr(self._state, key):
                        current_value = getattr(self._state, key)
                        
                        # 列表字段：追加
                        if isinstance(current_value, list) and isinstance(value, list):
                            setattr(self._state, key, current_value + value)
                        # 字典字段：合并
                        elif isinstance(current_value, dict) and isinstance(value, dict):
                            merged = current_value.copy()
                            merged.update(value)
                            setattr(self._state, key, merged)
                        # 其他：直接覆盖
                        else:
                            setattr(self._state, key, value)
                
                # 更新时间戳
                self._state.updated_at = datetime.now().isoformat()
                self._state.version += 1
                
                # 持久化
                self._persist_checkpoint()
                
                self._stats["writes"] += 1
                self._stats["last_write_time"] = time.time()
                
            except Exception as e:
                logger.error(f"[CheckpointWriter] Write failed: {e}")
    
    def _persist_checkpoint(self) -> None:
        """持久化检查点到文件"""
        try:
            with open(self.checkpoint_file, 'w', encoding='utf-8') as f:
                json.dump(self._state.to_dict(), f, ensure_ascii=False, indent=2)
            logger.debug(f"[CheckpointWriter] Checkpoint persisted to {self.checkpoint_file}")
        except Exception as e:
            logger.error(f"[CheckpointWriter] Persist failed: {e}")
    
    def _load_checkpoint(self) -> Optional[CheckpointState]:
        """从文件加载检查点"""
        try:
            if not self.checkpoint_file.exists():
                return None
            
            with open(self.checkpoint_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            self._stats["reads"] += 1
            return CheckpointState.from_dict(data)
            
        except Exception as e:
            logger.warning(f"[CheckpointWriter] Load checkpoint failed: {e}")
            return None
    
    def _process_notes(self) -> None:
        """处理notes.md，将笔记路由到对应字段"""
        try:
            if not self.notes_file.exists():
                return
            
            with open(self.notes_file, 'r', encoding='utf-8') as f:
                content = f.read().strip()
            
            if not content:
                return
            
            # 解析笔记内容
            notes = self._parse_notes(content)
            
            if notes:
                # 路由到对应字段
                route_result = self._route_notes(notes)
                
                # 清空notes文件
                with open(self.notes_file, 'w', encoding='utf-8') as f:
                    f.write("")
                
                self._stats["notes_processed"] += len(notes)
                logger.debug(f"[CheckpointWriter] Processed {len(notes)} notes, routed to {len(route_result)} fields")
                
        except Exception as e:
            logger.warning(f"[CheckpointWriter] Process notes failed: {e}")
    
    def _parse_notes(self, content: str) -> List[Dict[str, str]]:
        """
        解析notes.md内容
        
        格式示例：
        ## intent
        用户想要完成xxx任务
        
        ## error
        遇到了xxx错误
        
        ## note
        这是一个通用笔记
        """
        notes = []
        lines = content.split('\n')
        current_category = "misc"
        current_content = []
        
        for line in lines:
            stripped = line.strip()
            
            # 检测分类标题
            if stripped.startswith('## '):
                # 保存前一个分类的笔记
                if current_content:
                    notes.append({
                        "category": current_category,
                        "content": '\n'.join(current_content).strip()
                    })
                    current_content = []
                
                # 解析分类
                category_name = stripped[3:].strip().lower()
                category_map = {
                    "intent": "current_intent",
                    "next": "next_action",
                    "constraint": "working_constraints",
                    "task": "task_tree",
                    "work": "current_work",
                    "file": "involved_files",
                    "discovery": "cross_task_discoveries",
                    "error": "errors_and_fixes",
                    "runtime": "runtime_state",
                    "decision": "design_decisions",
                    "note": "misc_notes",
                }
                current_category = category_map.get(category_name, "misc_notes")
            else:
                current_content.append(line)
        
        # 保存最后一个分类的笔记
        if current_content:
            notes.append({
                "category": current_category,
                "content": '\n'.join(current_content).strip()
            })
        
        return notes
    
    def _route_notes(self, notes: List[Dict[str, str]]) -> Dict[str, int]:
        """将笔记路由到对应字段"""
        route_counts = {}
        
        for note in notes:
            category = note["category"]
            content = note["content"]
            
            if hasattr(self._state, category):
                current_value = getattr(self._state, category)
                
                if isinstance(current_value, list):
                    current_value.append(content)
                elif isinstance(current_value, str):
                    # 字符串字段：追加（用分隔符）
                    if current_value:
                        setattr(self._state, category, current_value + "\n" + content)
                    else:
                        setattr(self._state, category, content)
                
                route_counts[category] = route_counts.get(category, 0) + 1
        
        return route_counts
    
    # ============ 公开API ============
    
    def should_checkpoint(self, context_usage_ratio: float) -> bool:
        """
        检查是否应该写入检查点
        
        Args:
            context_usage_ratio: 上下文利用率（0.0-1.0）
        
        Returns:
            是否应该写入
        """
        # 检查阈值
        thresholds = [
            ContextThreshold.LOW.value,
            ContextThreshold.MEDIUM.value,
            ContextThreshold.HIGH.value,
        ]
        
        # 检查上次写入后上下文使用率是否突破新阈值
        last_usage = self._stats["last_context_usage"]
        
        for threshold in thresholds:
            if context_usage_ratio >= threshold and last_usage < threshold:
                # 检查写入间隔
                if time.time() - self._last_write_time >= self.MIN_WRITE_INTERVAL:
                    return True
        
        self._stats["last_context_usage"] = context_usage_ratio
        return False
    
    def update_state(self, **kwargs) -> None:
        """
        异步更新检查点状态
        
        Args:
            current_intent: 当前意图
            next_action: 下一步动作
            working_constraints: 工作约束列表
            task_tree: 任务树字典
            current_work: 当前工作描述
            involved_files: 涉及文件列表
            cross_task_discoveries: 跨任务发现列表
            errors_and_fixes: 错误修复列表
            runtime_state: 运行时状态字典
            design_decisions: 设计决策列表
            misc_notes: 杂项笔记列表
        """
        # 过滤有效字段
        valid_fields = [
            "current_intent", "next_action", "working_constraints",
            "task_tree", "current_work", "involved_files",
            "cross_task_discoveries", "errors_and_fixes",
            "runtime_state", "design_decisions", "misc_notes"
        ]
        
        task = {k: v for k, v in kwargs.items() if k in valid_fields}
        
        if task:
            self._write_queue.append(task)
    
    def append_note(self, category: str, content: str) -> None:
        """
        主Agent追加笔记到notes.md
        
        Args:
            category: 分类（intent/next/constraint/task/work/file/discovery/error/runtime/decision/note）
            content: 笔记内容
        """
        try:
            # 验证分类
            valid_categories = {
                "intent", "next", "constraint", "task", "work",
                "file", "discovery", "error", "runtime", "decision", "note"
            }
            
            if category not in valid_categories:
                category = "note"
            
            # 追加到notes文件
            with open(self.notes_file, 'a', encoding='utf-8') as f:
                f.write(f"\n## {category}\n")
                f.write(f"{content}\n")
            
            logger.debug(f"[CheckpointWriter] Note appended: ## {category}")
            
        except Exception as e:
            logger.error(f"[CheckpointWriter] Append note failed: {e}")
    
    def get_state(self) -> CheckpointState:
        """获取当前检查点状态"""
        return self._state
    
    def get_rebuild_context(self, max_tokens: int = 65000) -> str:
        """
        获取重建上下文的内容
        
        当上下文接近上限时，生成可注入新窗口的上下文内容。
        顺序：task_list → checkpoint → recent messages → project_memory → global_memory → notes → tail_reminder
        
        Args:
            max_tokens: 最大token数
        
        Returns:
            重建上下文文本
        """
        state = self._state
        
        sections = []
        
        # 1. task_list
        if state.task_tree:
            sections.append("## 任务列表\n")
            sections.append(json.dumps(state.task_tree, ensure_ascii=False, indent=2))
            sections.append("")
        
        # 2. checkpoint状态摘要
        sections.append("## 检查点状态\n")
        if state.current_intent:
            sections.append(f"- 当前意图: {state.current_intent}")
        if state.next_action:
            sections.append(f"- 下一步: {state.next_action}")
        if state.current_work:
            sections.append(f"- 当前工作: {state.current_work}")
        if state.working_constraints:
            sections.append(f"- 约束: {', '.join(state.working_constraints)}")
        sections.append("")
        
        # 3. recent messages引用
        sections.append("## 近期对话摘要\n")
        sections.append(f"- 共{len(state.current_work)}条消息已处理")
        sections.append("")
        
        # 4. involved_files
        if state.involved_files:
            sections.append("## 涉及文件\n")
            for f in state.involved_files[:10]:
                sections.append(f"- {f}")
            sections.append("")
        
        # 5. errors_and_fixes
        if state.errors_and_fixes:
            sections.append("## 错误与修复\n")
            for ef in state.errors_and_fixes[-5:]:
                sections.append(f"- 错误: {ef.get('error', 'N/A')}")
                sections.append(f"  修复: {ef.get('fix', 'N/A')}")
            sections.append("")
        
        # 6. design_decisions
        if state.design_decisions:
            sections.append("## 设计决策\n")
            for d in state.design_decisions[-5:]:
                sections.append(f"- {d.get('decision', 'N/A')}: {d.get('rationale', 'N/A')}")
            sections.append("")
        
        # 7. misc_notes
        if state.misc_notes:
            sections.append("## 杂项笔记\n")
            for note in state.misc_notes[-10:]:
                sections.append(f"- {note}")
            sections.append("")
        
        # 8. tail_reminder
        sections.append("## 继续执行提醒\n")
        if state.next_action:
            sections.append(f"请继续执行: {state.next_action}")
        if state.current_intent:
            sections.append(f"目标: {state.current_intent}")
        
        context = "\n".join(sections)
        
        # 简单token估算（中文约2token/字）
        estimated_tokens = len(context) * 2
        if estimated_tokens > max_tokens:
            # 截断
            max_chars = max_tokens // 2
            context = context[:max_chars] + f"\n\n[内容已截断，原长度约{estimated_tokens}token]"
        
        return context
    
    def rebuild_window(self, messages: List[Dict], max_tokens: int = 65000) -> List[Dict]:
        """
        从持久化文件重建新窗口
        
        注入顺序：
        1. task_list → checkpoint → recent messages → project_memory → global_memory → notes → tail_reminder
        
        Args:
            messages: 当前消息列表
            max_tokens: 最大token数
        
        Returns:
            重建后的消息列表
        """
        # 从文件加载最新检查点
        loaded_state = self._load_checkpoint()
        if loaded_state:
            self._state = loaded_state
            self._stats["window_rebuilds"] += 1
        
        # 提取system消息
        system_msgs = [m for m in messages if m.get("role") == "system"]
        non_system = [m for m in messages if m.get("role") != "system"]
        
        # 生成重建上下文
        rebuild_context = self.get_rebuild_context(max_tokens)
        
        # 构建重建后的消息
        rebuild_msg = {
            "role": "system",
            "content": f"[窗口重建]\n{rebuild_context}"
        }
        
        # 保留最近的非system消息
        recent_msgs = non_system[-20:] if len(non_system) > 20 else non_system
        
        # 截断提示
        truncation_notice = {
            "role": "system",
            "content": f"[注意] 已重建窗口，保留了最近的{len(recent_msgs)}条消息。"
        }
        
        # 组装新消息列表
        new_messages = system_msgs + [rebuild_msg, truncation_notice] + recent_msgs
        
        logger.info(f"[CheckpointWriter] Window rebuilt: system={len(system_msgs)}, rebuild_context={len(rebuild_context)}chars, recent={len(recent_msgs)}")
        
        return new_messages
    
    def validate_file_paths(self, file_paths: List[str]) -> Dict[str, bool]:
        """
        验证文件路径有效性
        
        Args:
            file_paths: 要验证的文件路径列表
        
        Returns:
            {file_path: 是否存在}
        """
        results = {}
        
        for fp in file_paths:
            try:
                # 支持相对路径和绝对路径
                path = Path(fp)
                if not path.is_absolute():
                    path = self.storage_dir.parent / path
                
                results[fp] = path.exists()
            except Exception:
                results[fp] = False
        
        # 更新involved_files为有效路径
        valid_files = [fp for fp, exists in results.items() if exists]
        if valid_files != self._state.involved_files:
            self._state.involved_files = valid_files
            # 异步写入
            self._write_queue.append({"involved_files": []})  # 占位，触发写入
        
        return results
    
    def get_stats(self) -> Dict:
        """获取统计信息"""
        return {
            **self._stats,
            "state_version": self._state.version,
            "running": self._running,
            "queue_size": len(self._write_queue),
            "checkpoint_file": str(self.checkpoint_file),
            "notes_file": str(self.notes_file),
        }
    
    def to_dict(self) -> Dict:
        """导出为字典"""
        return {
            "state": self._state.to_dict(),
            "stats": self.get_stats(),
        }
