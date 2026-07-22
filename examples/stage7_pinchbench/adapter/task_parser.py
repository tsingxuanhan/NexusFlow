# -*- coding: utf-8 -*-
"""
PinchBench 任务定义解析器

解析 .md 任务定义文件，提取 YAML frontmatter 和 Markdown 各节，
编译 automated_checks 中的 grade() 函数。

支持从本地文件或远程 URL 读取任务定义。
"""

from __future__ import annotations

import logging
import re
import textwrap
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Optional

import requests
import yaml

from .config import PINCHBENCH_RAW_URL, DOWNLOAD_TIMEOUT, DOWNLOAD_RETRIES

logger = logging.getLogger("pinchbench.parser")


# ============================================================================
# 数据模型
# ============================================================================

@dataclass
class WorkspaceFileSpec:
    """工作区文件规格

    支持三种格式:
    1. 字符串: source路径（如 "csvs/us_pension_by_state.csv"）
    2. dict with source+dest: 从PinchBench assets下载
    3. dict with path+content: 内嵌内容直接写入
    """
    source: Optional[str] = None
    dest: Optional[str] = None
    content: Optional[str] = None
    path: Optional[str] = None

    @classmethod
    def from_raw(cls, raw: Any) -> WorkspaceFileSpec:
        """从 YAML frontmatter 原始值构建"""
        if isinstance(raw, str):
            # 简单字符串 → source路径
            return cls(source=raw, dest=Path(raw).name)
        if isinstance(raw, dict):
            return cls(
                source=raw.get("source"),
                dest=raw.get("dest"),
                content=raw.get("content"),
                path=raw.get("path"),
            )
        return cls()


@dataclass
class PinchBenchTask:
    """解析后的 PinchBench 任务对象"""
    id: str = ""
    name: str = ""
    category: str = ""
    grading_type: str = ""  # automated | llm_judge | hybrid
    timeout_seconds: int = 300
    grading_weights: dict[str, float] = field(default_factory=lambda: {"automated": 1.0, "llm_judge": 0.0})
    workspace_files: list[WorkspaceFileSpec] = field(default_factory=list)

    # Markdown sections
    prompt: str = ""
    expected_behavior: str = ""
    grading_criteria: str = ""
    automated_checks_code: str = ""
    llm_rubric: str = ""

    # 多Session支持（如 task_session_chain_analysis）
    multi_session: bool = False
    sessions: list[dict[str, Any]] = field(default_factory=list)

    # 编译后的 grade 函数
    grade_fn: Optional[Callable[..., dict[str, float]]] = field(default=None, repr=False)

    # 原始文件路径/URL
    source: str = ""


# ============================================================================
# 解析逻辑
# ============================================================================

# Markdown section 标题 → 字段映射
_SECTION_MAP: dict[str, str] = {
    "prompt": "prompt",
    "expected behavior": "expected_behavior",
    "expected_behavior": "expected_behavior",
    "grading criteria": "grading_criteria",
    "grading_criteria": "grading_criteria",
    "automated checks": "automated_checks_code",
    "automated_checks": "automated_checks_code",
    "llm judge rubric": "llm_rubric",
    "llm_judge_rubric": "llm_rubric",
    "additional notes": "",
    "notes": "",
}


def _split_frontmatter(text: str) -> tuple[dict[str, Any], str]:
    """分离 YAML frontmatter 和正文。

    Returns:
        (frontmatter_dict, body_text)
    """
    match = re.match(r"^---\s*\n(.*?)\n---\s*\n(.*)", text, re.DOTALL)
    if not match:
        logger.warning("未找到 YAML frontmatter，整体视为正文")
        return {}, text
    fm_text, body = match.group(1), match.group(2)
    try:
        fm = yaml.safe_load(fm_text) or {}
    except yaml.YAMLError as exc:
        logger.error("YAML frontmatter 解析失败: %s", exc)
        fm = {}
    return fm, body


def _parse_sections(body: str) -> dict[str, str]:
    """解析 Markdown ## 标题分节。

    Returns:
        {section_key: section_content}
    """
    sections: dict[str, str] = {}
    # 按 ## 标题分割
    parts = re.split(r"^##\s+(.+)$", body, flags=re.MULTILINE)
    # parts[0] 是 ## 之前的正文，之后交替为 title, content
    for i in range(1, len(parts), 2):
        title = parts[i].strip().lower()
        content = parts[i + 1].strip() if i + 1 < len(parts) else ""
        # 提取代码块（仅用于 automated checks）
        if "automated" in title and "check" in title:
            code_match = re.search(r"```python\s*\n(.*?)```", content, re.DOTALL)
            if code_match:
                content = code_match.group(1).strip()
        sections[title] = content
    return sections


def _compile_grade_fn(code: str) -> Optional[Callable[..., dict[str, float]]]:
    """从 automated_checks 代码块编译 grade() 函数。

    使用 exec 在受控命名空间中编译，返回 grade 函数引用。
    如果编译失败，返回 None。
    """
    if not code.strip():
        return None

    # 确保代码中包含 grade 函数定义
    if "def grade(" not in code:
        logger.warning("automated_checks 代码块中未找到 grade() 函数")
        return None

    namespace: dict[str, Any] = {}
    try:
        exec(code, namespace)
        grade_fn = namespace.get("grade")
        if callable(grade_fn):
            return grade_fn
        logger.warning("grade 不是可调用对象")
        return None
    except Exception as exc:
        logger.error("grade() 函数编译失败: %s", exc)
        return None


def _extract_sessions(fm: dict[str, Any]) -> tuple[bool, list[dict[str, Any]]]:
    """从 frontmatter 提取多 Session 配置"""
    multi = fm.get("multi_session", False)
    sessions = fm.get("sessions", [])
    return bool(multi), sessions


def parse_task_definition(text: str, source: str = "") -> PinchBenchTask:
    """解析 PinchBench 任务定义文本。

    Args:
        text: .md 文件的完整内容
        source: 来源标识（文件路径或 URL），用于调试

    Returns:
        PinchBenchTask 对象
    """
    fm, body = _split_frontmatter(text)
    sections = _parse_sections(body)

    # 映射 section 到字段
    mapped: dict[str, str] = {}
    for title, content in sections.items():
        key = _SECTION_MAP.get(title)
        if key:
            mapped[key] = content

    # 构建 workspace_files
    raw_ws_files = fm.get("workspace_files", [])
    ws_files = [WorkspaceFileSpec.from_raw(f) for f in raw_ws_files]

    # grading_weights
    weights = fm.get("grading_weights", {"automated": 1.0, "llm_judge": 0.0})
    if not isinstance(weights, dict):
        weights = {"automated": 1.0, "llm_judge": 0.0}

    # multi-session
    multi_session, sessions = _extract_sessions(fm)

    # 编译 grade 函数
    grade_code = mapped.get("automated_checks_code", "")
    grade_fn = _compile_grade_fn(grade_code)

    task = PinchBenchTask(
        id=fm.get("id", ""),
        name=fm.get("name", ""),
        category=fm.get("category", ""),
        grading_type=fm.get("grading_type", ""),
        timeout_seconds=fm.get("timeout_seconds", 300),
        grading_weights=weights,
        workspace_files=ws_files,
        prompt=mapped.get("prompt", ""),
        expected_behavior=mapped.get("expected_behavior", ""),
        grading_criteria=mapped.get("grading_criteria", ""),
        automated_checks_code=grade_code,
        llm_rubric=mapped.get("llm_rubric", ""),
        multi_session=multi_session,
        sessions=sessions,
        grade_fn=grade_fn,
        source=source,
    )
    return task


# ============================================================================
# 文件 / 远程加载
# ============================================================================

def load_task_from_file(file_path: str | Path) -> PinchBenchTask:
    """从本地 .md 文件加载任务定义。

    Args:
        file_path: .md 文件路径

    Returns:
        PinchBenchTask 对象
    """
    path = Path(file_path)
    text = path.read_text(encoding="utf-8")
    return parse_task_definition(text, source=str(path))


def load_task_from_url(task_id: str, base_url: str = PINCHBENCH_RAW_URL) -> PinchBenchTask:
    """从 PinchBench GitHub 下载任务定义。

    Args:
        task_id: 任务ID（如 task_market_research）
        base_url: 基础URL

    Returns:
        PinchBenchTask 对象
    """
    url = f"{base_url}/{task_id}.md"
    last_exc: Optional[Exception] = None

    for attempt in range(1, DOWNLOAD_RETRIES + 1):
        try:
            resp = requests.get(url, timeout=DOWNLOAD_TIMEOUT)
            resp.raise_for_status()
            return parse_task_definition(resp.text, source=url)
        except Exception as exc:
            last_exc = exc
            logger.warning("下载 %s 失败 (attempt %d/%d): %s", url, attempt, DOWNLOAD_RETRIES, exc)

    raise RuntimeError(f"下载任务定义失败: {url} — {last_exc}")


def load_task(task_id: str, local_dir: str | Path | None = None) -> PinchBenchTask:
    """加载任务定义：优先本地，fallback 远程。

    Args:
        task_id: 任务ID
        local_dir: 本地 .md 文件目录（None 则只从远程下载）

    Returns:
        PinchBenchTask 对象
    """
    if local_dir:
        local_path = Path(local_dir) / f"{task_id}.md"
        if local_path.exists():
            logger.info("从本地加载任务: %s", local_path)
            return load_task_from_file(local_path)

    logger.info("从远程下载任务: %s", task_id)
    return load_task_from_url(task_id)
