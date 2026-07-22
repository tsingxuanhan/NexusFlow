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
    category = task.category.lower().replace(" ", "_")
    agents = CATEGORY_AGENT_MAP.get(category, ["executor"])
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

    # PinchBench 任务需要处理大输入，禁用 guardrails 避免误拦截
    agent.guardrails = None

    logger.info("Agent 已创建: %s (model=%s, guardrails=disabled)", agent_name, model)
    return agent


# ============================================================================
# Prompt 构造
# ============================================================================

def build_user_prompt(task: PinchBenchTask, workspace_path: Path) -> str:
    """构造发送给 Agent 的用户输入。
    
    策略：
    - 小文件 (<5KB): 嵌入完整内容
    - 大文件 (>=5KB): 只嵌入前30行 + 文件统计信息
    - 输出指令根据任务类型调整
    """
    parts: list[str] = []
    
    # 工作区上下文
    parts.append(f"## 工作区\n你的工作目录是: {workspace_path}\n")
    
    if task.workspace_files:
        file_contents = []
        for spec in task.workspace_files:
            fname = spec.dest or spec.path or spec.source or "unknown"
            fpath = workspace_path / fname
            
            # 获取文件内容
            fcontent = None
            if fpath.exists():
                try:
                    fcontent = fpath.read_text(encoding="utf-8", errors="replace")
                except Exception:
                    fcontent = None
            elif spec.content:
                fcontent = spec.content
            
            if fcontent is None:
                file_contents.append(f"### {fname} (binary/unreadable)\n")
                continue
            
            lines = fcontent.split("\n")
            total_lines = len(lines)
            total_chars = len(fcontent)
            
            if total_chars < 50000:
                # 小文件：完整嵌入
                file_contents.append(f"### {fname} ({total_lines} lines, {total_chars} chars)\n```\n{fcontent}\n```\n")
            else:
                # 大文件：只嵌入前30行
                preview = "\n".join(lines[:30])
                file_contents.append(
                    f"### {fname} ({total_lines} lines, {total_chars} chars)\n"
                    f"文件较大，以下是前30行预览：\n"
                    f"```\n{preview}\n```\n"
                    f"[文件共 {total_lines} 行，以上为前30行。请基于你的知识分析此文件。]\n"
                )
        
        if file_contents:
            parts.append("### 当前工作区文件\n" + "\n".join(file_contents))

    # 任务 prompt
    if task.multi_session and task.sessions:
        parts.append("## 任务\n这是一个多轮对话任务，请依次处理以下各轮：\n")
        for i, session in enumerate(task.sessions, 1):
            session_prompt = session.get("prompt", "")
            parts.append(f"### Session {i}\n{session_prompt}\n")
    else:
        parts.append("## 任务\n" + task.prompt)

    # 输出格式指令 — 根据任务类别调整
    if task.category in ("coding",):
        parts.append(
            "\n## 输出要求\n"
            "请在回复中输出修改后的每个文件的完整内容，使用以下格式：\n"
            "### filename.ext\n"
            "```语言\n完整文件内容\n```\n"
            "每个需要修改的文件都必须完整输出，不要省略任何代码。"
        )
    else:
        # 分析/报告类任务
        parts.append(
            "\n## 输出要求\n"
            "请将分析结果保存为 `report.md` 文件。在回复中输出完整的报告内容，使用以下格式：\n"
            "### report.md\n"
            "```markdown\n完整报告内容\n```\n"
            "报告应包含完整的数据分析、结论和建议。"
        )

    return "\n".join(parts)


def build_workspace_hint(workspace_path: Path) -> str:
    return ""


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

        # 5. 从 Agent 响应中提取文件内容并写入工作区
        result.workspace_files_written = self._extract_and_write_files(
            task, workspace_path, result.response
        )

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

    def _extract_and_write_files(
        self,
        task: PinchBenchTask,
        workspace_path: Path,
        response: str,
    ) -> list[str]:
        """从 Agent 响应中提取文件内容并写入工作区。
        
        策略：
        1. 从响应的 markdown 代码块中提取文件名和内容
        2. 将提取的内容写入工作区（覆盖原文件）
        3. 如果没有提取到文件且任务非 coding 类，将响应保存为 report.md
        """
        import re
        written: list[str] = []

        if not response:
            return written

        # 从响应中提取文件名+代码块的模式
        pattern1 = re.findall(
            r'''###\s+([\w._/-]+\.[\w]+)\s*\n```(?:\w+)?\s*\n(.*?)```''',
            response, re.DOTALL
        )
        pattern2 = re.findall(
            r'''\*\*([\w._/-]+\.[\w]+)\*\*\s*\n```(?:\w+)?\s*\n(.*?)```''',
            response, re.DOTALL
        )

        all_matches = {}
        for fname, code in pattern1 + pattern2:
            clean_name = fname.strip()
            if clean_name not in all_matches:
                all_matches[clean_name] = code.strip()

        # 写入提取到的文件
        for fname, code_content in all_matches.items():
            target_path = workspace_path / fname
            target_path.parent.mkdir(parents=True, exist_ok=True)
            try:
                target_path.write_text(code_content, encoding="utf-8")
                written.append(fname)
                logger.info("从响应提取并写入: %s (%d bytes)", fname, len(code_content))
            except Exception as exc:
                logger.warning("写入失败: %s - %s", fname, exc)

        # Fallback: 如果没有提取到文件，将完整响应写入 report.md
        if not written and task.category not in ("coding",):
            report_path = workspace_path / "report.md"
            try:
                # 尝试提取 markdown 代码块内容
                md_match = re.search(r'''```(?:markdown|md)\s*\n(.*?)```''', response, re.DOTALL)
                content = md_match.group(1).strip() if md_match else response.strip()
                report_path.write_text(content, encoding="utf-8")
                written.append("report.md")
                logger.info("Fallback 写入 report.md (%d bytes)", len(content))
            except Exception as exc:
                logger.warning("Fallback 写入失败: %s", exc)

        return written
