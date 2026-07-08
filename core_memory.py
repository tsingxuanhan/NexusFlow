# -*- coding: utf-8 -*-
"""
铉枢·炉守 Core Memory — 核心记忆层
XuanHub Core Memory — Direct Prompt Injection Layer

Letta三层架构第一层：直接注入system prompt，无需检索
- 容量小(~4K tokens)，延迟为0
- 存储：用户画像 + Agent状态 + 行为规则 + 活跃上下文
- 类比：CPU寄存器
"""

import json
import time
import logging
import os
from typing import Any, Dict, List, Optional
from dataclasses import dataclass, field

logger = logging.getLogger("CoreMemory")


@dataclass
class CoreBlock:
    """核心记忆块 — 一个逻辑分区"""
    key: str                        # 块标识
    label: str                      # 显示标签
    content: str                    # 内容文本
    priority: int = 0               # 优先级(越高越靠前)
    max_tokens: int = 500           # 该块token上限
    mutable: bool = True            # 是否可运行时修改
    updated_at: float = field(default_factory=time.time)

    def estimate_tokens(self) -> int:
        """粗略估算token数（中文~1.5字/token，英文~4字/token）"""
        return max(1, len(self.content) // 3)

    def to_dict(self) -> Dict:
        return {
            "key": self.key,
            "label": self.label,
            "content": self.content,
            "priority": self.priority,
            "max_tokens": self.max_tokens,
            "mutable": self.mutable,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, d: Dict) -> "CoreBlock":
        return cls(
            key=d["key"],
            label=d["label"],
            content=d["content"],
            priority=d.get("priority", 0),
            max_tokens=d.get("max_tokens", 500),
            mutable=d.get("mutable", True),
            updated_at=d.get("updated_at", time.time()),
        )


class CoreMemory:
    """
    核心记忆 — 直接注入system prompt，无需检索

    结构化分区：
    1. user_profile   — 用户画像（姓名/学校/偏好等）
    2. agent_state    — Agent当前状态（角色/模式/活跃任务）
    3. procedural     — 行为规则（从Sleeptime提炼）
    4. active_context — 当前任务上下文
    5. project_info   — 项目信息（实验室/导师/方向）

    用法：
        cm = CoreMemory()
        cm.update("user_profile", "用户偏好: MiMo优先，DeepSeek兜底")
        prompt = cm.to_system_prompt()
    """

    DEFAULT_BLOCKS = [
        CoreBlock(key="user_profile", label="用户画像", content="", priority=10, max_tokens=800),
        CoreBlock(key="agent_state", label="Agent状态", content="", priority=9, max_tokens=400),
        CoreBlock(key="procedural", label="行为规则", content="", priority=8, max_tokens=800),
        CoreBlock(key="active_context", label="当前上下文", content="", priority=7, max_tokens=600),
        CoreBlock(key="project_info", label="项目信息", content="", priority=6, max_tokens=400),
    ]

    def __init__(
        self,
        max_total_tokens: int = 4000,
        persist_path: Optional[str] = None,
    ):
        self.max_total_tokens = max_total_tokens
        self.persist_path = persist_path
        self.blocks: Dict[str, CoreBlock] = {}

        # 初始化默认分区
        for block in self.DEFAULT_BLOCKS:
            self.blocks[block.key] = block

        # 加载持久化数据
        if persist_path:
            self._load()

    def update(self, key: str, content: str, label: Optional[str] = None) -> bool:
        """
        更新核心记忆块

        Args:
            key: 块标识
            content: 新内容
            label: 可选新标签

        Returns:
            是否更新成功
        """
        if key in self.blocks:
            block = self.blocks[key]
            if not block.mutable:
                logger.warning(f"[CoreMemory] Block '{key}' is immutable, skip update")
                return False
            block.content = content
            block.updated_at = time.time()
            if label:
                block.label = label
        else:
            # 新块
            self.blocks[key] = CoreBlock(
                key=key,
                label=label or key,
                content=content,
                priority=0,
            )

        # 检查token总量
        if self.estimate_total_tokens() > self.max_total_tokens:
            # 截断最低优先级块的内容
            self._trim_to_fit()

        logger.debug(f"[CoreMemory] Updated block '{key}' ({len(content)} chars)")
        self._auto_save()
        return True

    def append(self, key: str, line: str) -> bool:
        """向块追加一行内容"""
        if key not in self.blocks:
            return self.update(key, line)

        block = self.blocks[key]
        if not block.mutable:
            return False

        block.content = block.content.rstrip("\n") + "\n" + line
        block.updated_at = time.time()

        if self.estimate_total_tokens() > self.max_total_tokens:
            self._trim_to_fit()

        self._auto_save()
        return True

    def remove_line(self, key: str, pattern: str) -> bool:
        """移除块中匹配pattern的行"""
        if key not in self.blocks:
            return False
        block = self.blocks[key]
        lines = block.content.split("\n")
        new_lines = [l for l in lines if pattern not in l]
        block.content = "\n".join(new_lines)
        block.updated_at = time.time()
        self._auto_save()
        return True

    def get(self, key: str) -> Optional[str]:
        """获取块内容"""
        if key in self.blocks:
            return self.blocks[key].content
        return None

    def get_block(self, key: str) -> Optional[CoreBlock]:
        """获取块对象"""
        return self.blocks.get(key)

    def to_system_prompt(self) -> str:
        """
        序列化为system prompt片段

        只输出有内容的块，按优先级排序
        """
        active_blocks = [
            b for b in self.blocks.values() if b.content.strip()
        ]
        # 按优先级降序
        active_blocks.sort(key=lambda b: b.priority, reverse=True)

        parts = []
        total_tokens = 0

        for block in active_blocks:
            block_tokens = block.estimate_tokens()
            if total_tokens + block_tokens > self.max_total_tokens:
                # 截断该块内容
                remaining = self.max_total_tokens - total_tokens
                max_chars = remaining * 3
                truncated = block.content[:max_chars]
                parts.append(f"## {block.label}\n{truncated}...")
                break

            parts.append(f"## {block.label}\n{block.content}")
            total_tokens += block_tokens

        if not parts:
            return ""

        return "\n\n".join(parts)

    def to_dict(self) -> Dict:
        """序列化"""
        return {
            "max_total_tokens": self.max_total_tokens,
            "blocks": {k: v.to_dict() for k, v in self.blocks.items()},
        }

    @classmethod
    def from_dict(cls, d: Dict) -> "CoreMemory":
        """反序列化"""
        cm = cls(max_total_tokens=d.get("max_total_tokens", 4000))
        for k, v in d.get("blocks", {}).items():
            cm.blocks[k] = CoreBlock.from_dict(v)
        return cm

    def estimate_total_tokens(self) -> int:
        """估算总token数"""
        return sum(b.estimate_tokens() for b in self.blocks.values() if b.content)

    def _trim_to_fit(self) -> None:
        """按优先级从低到高截断块内容，直到总量在限制内"""
        sorted_blocks = sorted(
            [b for b in self.blocks.values() if b.content],
            key=lambda b: b.priority,
        )

        for block in sorted_blocks:
            if self.estimate_total_tokens() <= self.max_total_tokens:
                break

            # 截断到该块max_tokens的70%
            max_chars = int(block.max_tokens * 0.7) * 3
            if len(block.content) > max_chars:
                block.content = block.content[:max_chars] + "..."
                logger.info(f"[CoreMemory] Trimmed block '{block.key}' to fit token budget")

    def _auto_save(self) -> None:
        """自动保存到文件"""
        if not self.persist_path:
            return
        try:
            os.makedirs(os.path.dirname(self.persist_path) or '.', exist_ok=True)
            with open(self.persist_path, 'w', encoding='utf-8') as f:
                json.dump(self.to_dict(), f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.warning(f"[CoreMemory] Failed to save: {e}")

    def _load(self) -> None:
        """从文件加载"""
        if not self.persist_path or not os.path.exists(self.persist_path):
            return
        try:
            with open(self.persist_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            loaded = CoreMemory.from_dict(data)
            # 合并：已有块更新内容，新块添加
            for k, v in loaded.blocks.items():
                self.blocks[k] = v
            logger.info(f"[CoreMemory] Loaded {len(loaded.blocks)} blocks from {self.persist_path}")
        except Exception as e:
            logger.warning(f"[CoreMemory] Failed to load: {e}")

    def get_stats(self) -> Dict:
        """统计信息"""
        return {
            "total_blocks": len(self.blocks),
            "active_blocks": sum(1 for b in self.blocks.values() if b.content.strip()),
            "total_tokens": self.estimate_total_tokens(),
            "max_tokens": self.max_total_tokens,
            "blocks": {
                k: {
                    "label": v.label,
                    "tokens": v.estimate_tokens(),
                    "priority": v.priority,
                    "mutable": v.mutable,
                }
                for k, v in self.blocks.items()
            },
        }


def create_core_memory_with_defaults(
    user_name: str = "",
    project_name: str = "铉枢·炉守",
    persist_path: str = "data/core_memory.json",
) -> CoreMemory:
    """
    创建带默认内容的CoreMemory

    Args:
        user_name: 用户名
        project_name: 项目名
        persist_path: 持久化路径

    Returns:
        初始化好的CoreMemory
    """
    cm = CoreMemory(persist_path=persist_path)

    # 默认用户画像
    if user_name and not cm.get("user_profile"):
        cm.update("user_profile", f"用户: {user_name}")

    # 默认项目信息
    if not cm.get("project_info"):
        cm.update("project_info",
            f"项目: {project_name}\n"
            f"框架: NexusFlow v2.7\n"
            f"模型: DeepSeek PRO(推理) + Flash(验证/轻量)"
        )

    # 默认行为规则
    if not cm.get("procedural"):
        cm.update("procedural",
            "- 优先使用Flash模型完成轻量任务，PRO留给复杂推理\n"
            "- 搜索结果不经用户确认不写入记忆\n"
            "- 用户消息带问号=先给方案确认\n"
            "- API Key走环境变量，不硬编码\n"
            "- 云电脑先测，验证后再部署本机"
        )

    return cm
