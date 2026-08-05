# -*- coding: utf-8 -*-
"""
PinchBench Adapter — 共享配置

路径、API 端点、Agent 映射、默认参数。
"""

import os
from pathlib import Path

# ── 路径 ────────────────────────────────────────────────────────────────────
STAGE7_DIR = Path(__file__).resolve().parent.parent
NEXUSFLOW_REPO_ROOT = STAGE7_DIR.parent.parent  # repo 根目录

TASKS_RAW_DIR = STAGE7_DIR / "tasks_raw"
TASK_MANIFEST_PATH = TASKS_RAW_DIR / "task_manifest.json"
RESULTS_ROOT = STAGE7_DIR / "results_nf"
WORKSPACE_ROOT = STAGE7_DIR / "workspaces"

# ── 远程资源 URL ─────────────────────────────────────────────────────────────
_GITHUB_RAW = "https://raw.githubusercontent.com/tsingxuanhan/NexusFlow/main/examples/stage7_pinchbench"
PINCHBENCH_RAW_URL = f"{_GITHUB_RAW}/tasks_raw"
PINCHBENCH_ASSETS_URL = f"{_GITHUB_RAW}/assets_cache"

# ── 网络 ────────────────────────────────────────────────────────────────────
DOWNLOAD_TIMEOUT = 30
DOWNLOAD_RETRIES = 3
DEFAULT_TIMEOUT = 300  # 单任务最长执行时间（秒）

# ── LLM ─────────────────────────────────────────────────────────────────────
DEEPSEEK_API_KEY = os.environ.get("DEEPSEEK_API_KEY", "")
DEEPSEEK_ENDPOINT = "https://api.deepseek.com/chat/completions"

# ── 评分 ────────────────────────────────────────────────────────────────────
DEFAULT_GRADING_WEIGHTS = {"automated": 1.0, "llm_judge": 0.0}

# ── 任务类别 → Agent 映射 ───────────────────────────────────────────────────
CATEGORY_AGENT_MAP = {
    "research":          ["researcher"],
    "coding":            ["executor"],
    "analysis":          ["analyst"],
    "csv_analysis":      ["executor"],
    "log_analysis":      ["executor"],
    "meeting_analysis":  ["researcher"],
    "productivity":      ["executor"],
    "security":          ["assayer"],
}
