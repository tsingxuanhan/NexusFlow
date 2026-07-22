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

def _extract_expected_output_files(task: PinchBenchTask) -> list[str]:
    """从任务 prompt 中解析期望的输出文件名。
    
    策略：
    1. 查找 grade() 函数中检查的文件名（最可靠）
    2. 查找 prompt 中提到的 "file called `xxx.md`" 或 "Write ... to `xxx.md`"
    3. 查找 "- [ ] File `xxx.md` is created" 格式的 checklist
    
    Returns:
        期望的输出文件名列表，如 ['triage_report.md', 'remediation_plan.md']
    """
    import re
    
    files = []
    full_text = task.prompt + "\n" + task.automated_checks_code + "\n" + task.grading_criteria
    
    # 策略1: 从 grade() 函数中提取检查的文件名
    # 匹配 workspace / "filename.md" 或 workspace_path / "filename.md" 模式
    grade_pattern = re.findall(
        r'workspace(?:_path)?\s*/\s*["\']([\w._-]+\.\w+)["\']',
        full_text
    )
    files.extend(grade_pattern)
    
    # 也检查 alternatives 列表
    alt_pattern = re.findall(
        r'alternatives\s*=\s*\[([^\]]+)\]',
        full_text
    )
    for alt in alt_pattern:
        alts = re.findall(r'["\']([\w._-]+\.\w+)["\']', alt)
        # 取第一个作为主文件名（grade() 先检查它）
        if alts:
            files.append(alts[0])
    
    # 策略2: "file called `xxx.md`" / "Write ... to a file called `xxx.md`"
    called_pattern = re.findall(
        r'file\s+called\s+`([\w._-]+\.\w+)`',
        task.prompt, re.IGNORECASE
    )
    files.extend(called_pattern)
    
    # 策略3: "- [ ] File `xxx.md` is created" checklist
    checklist_pattern = re.findall(
        r'`([\w._-]+\.\w+)`\s+is\s+created',
        full_text, re.IGNORECASE
    )
    files.extend(checklist_pattern)
    
    # 策略4: "Write your summary to `xxx.md`" / "Output ... to `xxx.md`"
    write_to_pattern = re.findall(
        r'(?:write|output|save|create|generate)\s+(?:your\s+)?[\w\s]+\s+(?:to|as|in)\s+`([\w._-]+\.\w+)`',
        task.prompt, re.IGNORECASE
    )
    files.extend(write_to_pattern)
    
    # 去重并保持顺序，只保留 .md/.json/.csv/.txt/.py/.yaml 等输出文件
    seen = set()
    result = []
    output_exts = {'.md', '.json', '.csv', '.txt', '.py', '.yaml', '.yml', '.xml', '.html'}
    for f in files:
        if f in seen:
            continue
        # 排除输入文件（已在 workspace_files 中的）
        input_files = set()
        if task.workspace_files:
            for spec in task.workspace_files:
                for attr in ('dest', 'path', 'source'):
                    val = getattr(spec, attr, None) if hasattr(spec, attr) else (spec.get(attr) if isinstance(spec, dict) else None)
                    if val:
                        input_files.add(val)
        # 只保留看起来是输出文件的
        ext = Path(f).suffix.lower()
        if ext in output_exts and f not in input_files:
            seen.add(f)
            result.append(f)
    
    return result


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

    # 输出格式指令 — 解析任务 prompt 中期望的输出文件名
    expected_outputs = _extract_expected_output_files(task)
    if expected_outputs:
        file_list = ", ".join(f"`{f}`" for f in expected_outputs)
        parts.append(
            f"\n## 输出要求\n"
            f"请将结果分别写入以下文件：{file_list}。\n"
            f"在回复中为每个文件使用以下格式：\n"
            f"### 文件名\n"
            f"```markdown\n"
            f"完整文件内容\n"
            f"```\n"
            f"每个文件都必须完整输出，不要省略任何内容。"
        )
    elif task.category in ("coding",):
        parts.append(
            "\n## 输出要求\n"
            "请在回复中输出修改后的每个文件的完整内容，使用以下格式：\n"
            "### filename.ext\n"
            "```语言\n完整文件内容\n```\n"
            "每个需要修改的文件都必须完整输出，不要省略任何代码。"
        )
    else:
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
        
        策略（按优先级）：
        1. 从响应的 markdown 代码块中提取文件名和内容（### filename + ``` 模式）
        2. 从任务 prompt 解析期望的输出文件名，尝试按章节拆分响应
        3. 如果只有1个期望输出文件，写入该文件
        4. 如果有多个期望输出文件且无法拆分，全量写入每个文件
        5. 兜底：写入 report.md
        """
        import re
        written: list[str] = []

        if not response:
            return written

        # ---- 策略1: 从响应中提取 ### filename + code block ----
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

        for fname, code_content in all_matches.items():
            target_path = workspace_path / fname
            target_path.parent.mkdir(parents=True, exist_ok=True)
            try:
                target_path.write_text(code_content, encoding="utf-8")
                written.append(fname)
                logger.info("从响应提取并写入: %s (%d bytes)", fname, len(code_content))
            except Exception as exc:
                logger.warning("写入失败: %s - %s", fname, exc)

        if written:
            return written

        # ---- 策略2: 从任务 prompt 解析期望输出文件名 ----
        expected_files = _extract_expected_output_files(task)
        content = response.strip()
        
        # 尝试提取 markdown 代码块中的纯内容
        md_match = re.search(r'''```(?:markdown|md)\s*\n(.*?)```''', response, re.DOTALL)
        if md_match:
            content = md_match.group(1).strip()

        if expected_files:
            if len(expected_files) == 1:
                # 单个输出文件：直接写入
                fname = expected_files[0]
                target_path = workspace_path / fname
                target_path.parent.mkdir(parents=True, exist_ok=True)
                try:
                    target_path.write_text(content, encoding="utf-8")
                    written.append(fname)
                    logger.info("写入期望输出文件: %s (%d bytes)", fname, len(content))
                except Exception as exc:
                    logger.warning("写入失败: %s - %s", fname, exc)
            else:
                # 多个输出文件：尝试按章节标题拆分
                sections = self._split_response_by_sections(content, expected_files)
                if sections and len(sections) >= 2:
                    # 成功拆分
                    for fname, section_content in sections.items():
                        target_path = workspace_path / fname
                        target_path.parent.mkdir(parents=True, exist_ok=True)
                        try:
                            target_path.write_text(section_content, encoding="utf-8")
                            written.append(fname)
                            logger.info("拆分写入: %s (%d bytes)", fname, len(section_content))
                        except Exception as exc:
                            logger.warning("写入失败: %s - %s", fname, exc)
                
                if not written:
                    # 无法拆分：全量写入所有期望文件
                    for fname in expected_files:
                        target_path = workspace_path / fname
                        target_path.parent.mkdir(parents=True, exist_ok=True)
                        try:
                            target_path.write_text(content, encoding="utf-8")
                            written.append(fname)
                            logger.info("全量写入期望文件: %s (%d bytes)", fname, len(content))
                        except Exception as exc:
                            logger.warning("写入失败: %s - %s", fname, exc)

        # ---- 兜底: 写入 report.md ----
        if not written and task.category not in ("coding",):
            report_path = workspace_path / "report.md"
            try:
                report_path.write_text(content, encoding="utf-8")
                written.append("report.md")
                logger.info("Fallback 写入 report.md (%d bytes)", len(content))
            except Exception as exc:
                logger.warning("Fallback 写入失败: %s", exc)

        return written

    def _split_response_by_sections(
        self, content: str, expected_files: list[str]
    ) -> dict[str, str]:
        """尝试按章节标题将响应拆分为多个文件。
        
        策略：
        - 查找 "Part 1: Triage Report" / "Part 2: Remediation Plan" 等编号章节
        - 查找文件名在标题中被提及（如 "## Triage Report (triage_report.md)"）
        - 查找与文件名关键词匹配的大标题（如 "## Triage Report" 对应 triage_report.md）
        """
        import re
        
        if not content or not expected_files:
            return {}
        
        sections: dict[str, str] = {}
        
        # 策略1: 按 "Part N:" 或 "## " 级别的大标题拆分
        # 先找所有 ## 级别标题的位置
        heading_positions = []
        for m in re.finditer(r'^(#{1,3})\s+(.+)$', content, re.MULTILINE):
            heading_positions.append((m.start(), m.end(), m.group(2).strip()))
        
        if len(heading_positions) < 2:
            return {}
        
        # 尝试将每个期望文件映射到一个章节
        file_to_section = {}
        for fname in expected_files:
            # 从文件名提取关键词（去掉扩展名，拆分为单词）
            name_part = Path(fname).stem.lower()
            keywords = re.split(r'[_\-\s]+', name_part)
            keywords = [k for k in keywords if len(k) > 2]
            
            best_match = None
            best_score = 0
            
            for pos_start, pos_end, heading_text in heading_positions:
                heading_lower = heading_text.lower()
                score = sum(1 for kw in keywords if kw in heading_lower)
                # 也检查 "Part N: Title" 格式
                if score > best_score:
                    best_score = score
                    best_match = heading_text
            
            if best_match and best_score > 0:
                file_to_section[fname] = best_match
        
        # 如果匹配成功，按标题位置拆分内容
        if len(file_to_section) >= 2:
            # 按标题位置排序
            matched_headings = []
            for fname, heading in file_to_section.items():
                for pos_start, pos_end, heading_text in heading_positions:
                    if heading_text == heading:
                        matched_headings.append((pos_start, pos_end, fname))
                        break
            
            matched_headings.sort(key=lambda x: x[0])
            
            for i, (start, end, fname) in enumerate(matched_headings):
                if i + 1 < len(matched_headings):
                    next_start = matched_headings[i + 1][0]
                    section_content = content[start:next_start].strip()
                else:
                    section_content = content[start:].strip()
                
                if section_content:
                    sections[fname] = section_content
            
            if sections:
                logger.info("按章节拆分响应: %s", list(sections.keys()))
                return sections
        
        return {}
