# -*- coding: utf-8 -*-
"""
NexusFlow Agent 执行器

接收解析后的 PinchBench Task 对象，通过 NexusFlow Agent 体系执行任务。

核心流程:
1. 根据 task.category 选择合适的 NexusFlow Agent
2. 构造系统提示词（使用 agent_registry 中的 system_prompt）
3. 构造用户输入（PinchBench prompt + workspace 文件路径提示）
4. 调用 agent.chat() 获取响应
5. 将响应写入工作区（如果 prompt 要求输出文件）
6. 记录 transcript（用于评分）
"""

from __future__ import annotations

import json
import logging
import os
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from .config import (
    CATEGORY_AGENT_MAP,
    DEEPSEEK_API_KEY,
    DEEPSEEK_ENDPOINT,
    NEXUSFLOW_REPO_ROOT,
)
from .task_parser import PinchBenchTask

logger = logging.getLogger("pinchbench.agent_runner")


# ============================================================================
# 确保 nexusflow 包可导入
# ============================================================================

def _ensure_nexusflow_importable() -> None:
    """将 NexusFlow 仓库根目录加入 sys.path"""
    repo_root = str(NEXUSFLOW_REPO_ROOT)
    if repo_root not in sys.path:
        sys.path.insert(0, repo_root)
        logger.info("sys.path 已添加: %s", repo_root)


# ============================================================================
# 数据模型
# ============================================================================

@dataclass
class AgentRunResult:
    """Agent 执行结果"""
    task_id: str = ""
    agent_used: str = ""
    response: str = ""
    transcript: list[dict[str, Any]] = field(default_factory=list)
    workspace_files_written: list[str] = field(default_factory=list)
    duration_seconds: float = 0.0
    status: str = "pending"  # pending | completed | failed
    error: Optional[str] = None


# ============================================================================
# Agent 选择
# ============================================================================

def select_agent_for_task(task: PinchBenchTask) -> str:
    """根据任务类别选择 NexusFlow Agent。

    Args:
        task: PinchBench 任务对象

    Returns:
        Agent 名称（如 'researcher'）
    """
    agents = CATEGORY_AGENT_MAP.get(task.category, ["executor"])
    return agents[0]


def get_agent_spec(agent_name: str) -> Any:
    """从 agent_registry 获取 Agent 规格。

    Args:
        agent_name: Agent 名称

    Returns:
        AgentSpec 对象
    """
    _ensure_nexusflow_importable()
    from nexusflow.agents.agent_registry import AGENT_REGISTRY

    spec = AGENT_REGISTRY.get(agent_name)
    if not spec:
        raise ValueError(f"未知 Agent: {agent_name}，可用: {list(AGENT_REGISTRY.keys())}")
    return spec


# ============================================================================
# Agent 创建
# ============================================================================

def create_agent(agent_name: str, system_prompt_override: str | None = None) -> Any:
    """创建 NexusFlow BaseAgent 实例。

    使用 agent_registry 中的 system_prompt 和模型配置。

    Args:
        agent_name: Agent 名称
        system_prompt_override: 可选的系统提示词覆盖

    Returns:
        BaseAgent 实例
    """
    _ensure_nexusflow_importable()
    from nexusflow.agents.base_agent import BaseAgent
    from nexusflow.agents.agent_registry import AGENT_REGISTRY, ModelTier, RunLayer

    spec = AGENT_REGISTRY.get(agent_name)
    if not spec:
        raise ValueError(f"未知 Agent: {agent_name}")

    # 根据 run_layer 和 model_tier 确定 model 参数
    # Cloud + PRO → "pro", Cloud + FLASH → "flash"
    # Edge 暂不支持，统一走 Cloud
    if spec.model_tier == ModelTier.PRO:
        model = "pro"
    else:
        model = "flash"

    system_prompt = system_prompt_override or spec.system_prompt

    agent = BaseAgent(
        name=agent_name,
        model=model,
        system_prompt=system_prompt,
        api_key=DEEPSEEK_API_KEY,
        endpoint=DEEPSEEK_ENDPOINT,
        enable_checkpoint=False,  # PinchBench 任务不需要持久化检查点
        enable_compactor=True,
    )

    logger.info("Agent 已创建: %s (model=%s)", agent_name, model)
    return agent


# ============================================================================
# Prompt 构造
# ============================================================================

def build_user_prompt(task: PinchBenchTask, workspace_path: Path) -> str:
    """构造发送给 Agent 的用户输入。

    包含：
    - PinchBench 的原始 prompt
    - 工作区文件路径提示
    - 多 Session 任务的 session prompt

    Args:
        task: 任务对象
        workspace_path: 工作区路径

    Returns:
        完整的用户 prompt
    """
    parts: list[str] = []

    # 工作区上下文
    parts.append(f"## 工作区\n你的工作目录是: {workspace_path}\n")

    # 工作区文件列表
    if task.workspace_files:
        file_list = []
        for spec in task.workspace_files:
            fname = spec.dest or spec.path or spec.source or "unknown"
            file_list.append(f"  - {fname}")
        parts.append("### 可用文件\n" + "\n".join(file_list) + "\n")

    # 任务 prompt
    if task.multi_session and task.sessions:
        parts.append("## 任务\n这是一个多轮对话任务，请依次处理以下各轮：\n")
        for i, session in enumerate(task.sessions, 1):
            session_prompt = session.get("prompt", "")
            parts.append(f"### Session {i}\n{session_prompt}\n")
    else:
        parts.append("## 任务\n" + task.prompt)

    return "\n".join(parts)


def build_workspace_hint(workspace_path: Path) -> str:
    """构造工作区文件路径提示，追加到 prompt 末尾。"""
    return f"\n\n请将输出文件保存到工作目录: {workspace_path}"


# ============================================================================
# Agent 执行
# ============================================================================

class NFAgentRunner:
    """NexusFlow Agent 执行器"""

    def __init__(self, api_key: str | None = None, endpoint: str | None = None) -> None:
        self.api_key = api_key or DEEPSEEK_API_KEY
        self.endpoint = endpoint or DEEPSEEK_ENDPOINT

    def run_task(
        self,
        task: PinchBenchTask,
        workspace_path: Path,
    ) -> AgentRunResult:
        """执行单个 PinchBench 任务。

        Args:
            task: 已解析的任务对象
            workspace_path: 工作区路径

        Returns:
            AgentRunResult
        """
        start = time.time()
        result = AgentRunResult(task_id=task.id)

        # 1. 选择 Agent
        agent_name = select_agent_for_task(task)
        result.agent_used = agent_name

        # 2. 创建 Agent
        try:
            agent = create_agent(agent_name)
        except Exception as exc:
            result.status = "failed"
            result.error = f"Agent 创建失败: {exc}"
            result.duration_seconds = time.time() - start
            return result

        # 3. 构造 prompt
        user_prompt = build_user_prompt(task, workspace_path)
        if not task.multi_session:
            user_prompt += build_workspace_hint(workspace_path)

        # 4. 执行
        try:
            if task.multi_session and task.sessions:
                response = self._run_multi_session(agent, task, workspace_path)
            else:
                response = agent.chat(user_prompt)

            result.response = response
            result.status = "completed"

        except Exception as exc:
            result.status = "failed"
            result.error = f"Agent 执行失败: {exc}"
            logger.error("任务 %s 执行失败: %s", task.id, exc)

        # 5. 检查工作区输出文件
        result.workspace_files_written = self._check_workspace_outputs(task, workspace_path)

        # 6. 构建 transcript
        from .grade_bridge import build_transcript
        result.transcript = build_transcript(
            result.response,
            result.workspace_files_written,
        )

        result.duration_seconds = time.time() - start
        return result

    def _run_multi_session(
        self,
        agent: Any,
        task: PinchBenchTask,
        workspace_path: Path,
    ) -> str:
        """执行多 Session 任务

        每轮使用 agent.chat()，保持上下文连续性。

        Args:
            agent: BaseAgent 实例
            task: 任务对象（含 sessions 列表）
            workspace_path: 工作区路径

        Returns:
            最后一轮的响应
        """
        last_response = ""
        for i, session in enumerate(task.sessions, 1):
            session_prompt = session.get("prompt", "")
            # 首轮加入工作区信息
            if i == 1:
                session_prompt = f"工作目录: {workspace_path}\n\n{session_prompt}"

            logger.info("Session %d/%d: %s", i, len(task.sessions), session_prompt[:80])
            last_response = agent.chat(session_prompt)

        return last_response

    def _check_workspace_outputs(
        self,
        task: PinchBenchTask,
        workspace_path: Path,
    ) -> list[str]:
        """检查工作区中的输出文件

        根据 prompt 中的文件名提示（如 "save to `market_research.md`"），
        检查是否已创建。

        Args:
            task: 任务对象
            workspace_path: 工作区路径

        Returns:
            存在的文件名列表
        """
        written: list[str] = []

        # 从 prompt 中提取可能的输出文件名
        import re
        # 匹配 "save to `filename`" / "named exactly `filename`" / "write to filename"
        filename_patterns = re.findall(
            r'(?:save|write|output|create|named?\s+(?:exactly\s+)?)[`"]([\w.-]+(?:\.\w+)?)["`]',
            task.prompt,
            re.IGNORECASE,
        )
        # 也匹配行内的 markdown 文件名
        filename_patterns.extend(
            re.findall(r'`([\w-]+\.\w+)`', task.prompt)
        )

        # 去重
        unique_names = list(dict.fromkeys(filename_patterns))

        for fname in unique_names:
            fpath = workspace_path / fname
            if fpath.exists():
                written.append(fname)
                logger.info("输出文件已创建: %s", fpath)

        # 如果 agent 没有自动写入文件，尝试从响应中提取并写入
        if not written and task.status != "failed":
            written = self._try_write_from_response(task, workspace_path)

        return written

    def _try_write_from_response(
        self,
        task: PinchBenchTask,
        workspace_path: Path,
    ) -> list[str]:
        """如果 Agent 没有自动写文件，尝试从响应中提取内容并写入。

        这是一个 fallback 机制：BaseAgent.chat() 只返回文本，
        不会直接写文件。如果 prompt 要求保存文件但文件不存在，
        尝试将 Agent 的完整响应写入目标文件。

        Args:
            task: 任务对象
            workspace_path: 工作区路径

        Returns:
            成功写入的文件名列表
        """
        import re

        written: list[str] = []

        # 提取期望的文件名
        filename_patterns = re.findall(
            r'(?:save|write|output|create|named?\s+(?:exactly\s+)?)[`"]([\w.-]+\.\w+)["`]',
            task.prompt,
            re.IGNORECASE,
        )
        if not filename_patterns:
            # 从 prompt 中的 markdown 代码块文件名提取
            filename_patterns = re.findall(r'`([\w-]+\.\w+)`', task.prompt)

        if not filename_patterns:
            return written

        target_fname = filename_patterns[0]
        target_path = workspace_path / target_fname

        if target_path.exists():
            return [target_fname]

        # 尝试从 Agent 的 response 中提取 markdown 内容并写入
        # 获取最后一次 Agent 响应
        # 注意：此时需要从外部传入 response，这里用文件检查方式间接判断
        logger.info("尝试 fallback 写入: %s", target_path)

        return written
