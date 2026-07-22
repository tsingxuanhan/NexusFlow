# -*- coding: utf-8 -*-
"""
PinchBench 工作区管理器

为每个任务创建隔离的临时工作目录，注入 workspace_files，
支持从 PinchBench GitHub assets 下载或直接写入内嵌内容。
"""

from __future__ import annotations

import logging
import shutil
import time
from pathlib import Path
from typing import Optional

import requests

from .config import (
    PINCHBENCH_ASSETS_URL,
    WORKSPACE_ROOT,
    DOWNLOAD_TIMEOUT,
    DOWNLOAD_RETRIES,
)
from .task_parser import PinchBenchTask, WorkspaceFileSpec

logger = logging.getLogger("pinchbench.workspace")


class WorkspaceManager:
    """管理工作区环境的创建、文件注入和清理。"""

    def __init__(self, workspace_root: Path | str | None = None, assets_cache: Path | str | None = None) -> None:
        self.workspace_root = Path(workspace_root) if workspace_root else WORKSPACE_ROOT
        self.workspace_root.mkdir(parents=True, exist_ok=True)
        self.assets_cache = Path(assets_cache) if assets_cache else Path(__file__).resolve().parent.parent / "assets_cache"
        self._active_workspaces: dict[str, Path] = {}

    # ──────────────────────────────────────────────
    # 创建工作区
    # ──────────────────────────────────────────────

    def create_workspace(self, task: PinchBenchTask) -> Path:
        """为任务创建隔离的临时工作目录。

        目录格式: {workspace_root}/{task_id}_{timestamp}/

        Args:
            task: 已解析的 PinchBenchTask 对象

        Returns:
            工作区绝对路径
        """
        ts = int(time.time())
        dir_name = f"{task.id}_{ts}"
        ws_path = self.workspace_root / dir_name
        ws_path.mkdir(parents=True, exist_ok=True)
        self._active_workspaces[task.id] = ws_path
        logger.info("工作区已创建: %s", ws_path)
        return ws_path

    def get_workspace(self, task_id: str) -> Optional[Path]:
        """获取已创建的工作区路径"""
        return self._active_workspaces.get(task_id)

    # ──────────────────────────────────────────────
    # 文件注入
    # ──────────────────────────────────────────────

    def inject_workspace_files(self, task: PinchBenchTask, workspace_path: Path) -> list[Path]:
        """将 workspace_files 注入到工作区目录。

        处理三种类型:
        1. content 类型: 内嵌内容直接写入
        2. source 类型: 从 PinchBench GitHub assets 下载
        3. path + content 类型: 内嵌内容写入指定路径

        Args:
            task: 任务对象（含 workspace_files 规格）
            workspace_path: 工作区路径

        Returns:
            成功写入的文件路径列表
        """
        written: list[Path] = []

        for spec in task.workspace_files:
            try:
                file_path = self._inject_single_file(spec, workspace_path)
                if file_path:
                    written.append(file_path)
            except Exception as exc:
                logger.error("注入文件失败 [%s]: %s", spec, exc)

        return written

    def _inject_single_file(self, spec: WorkspaceFileSpec, workspace_path: Path) -> Optional[Path]:
        """注入单个文件"""
        # 类型 1: 内嵌内容（path + content）
        if spec.content is not None:
            return self._write_embedded_content(spec, workspace_path)

        # 类型 2: 从远程下载（source）
        if spec.source:
            return self._download_asset(spec, workspace_path)

        logger.warning("无法处理的 WorkspaceFileSpec: %s", spec)
        return None

    def _write_embedded_content(self, spec: WorkspaceFileSpec, workspace_path: Path) -> Path:
        """将内嵌内容写入工作区"""
        # 确定目标文件名
        dest_name = spec.path or spec.dest or "embedded_file.txt"
        file_path = workspace_path / dest_name

        # 确保父目录存在
        file_path.parent.mkdir(parents=True, exist_ok=True)

        file_path.write_text(spec.content, encoding="utf-8")
        logger.info("内嵌文件已写入: %s", file_path)
        return file_path

    def _download_asset(self, spec: WorkspaceFileSpec, workspace_path: Path) -> Path:
        """从本地缓存或远程下载文件"""
        source = spec.source
        dest_name = spec.dest or Path(source).name
        file_path = workspace_path / dest_name

        # 确保父目录存在
        file_path.parent.mkdir(parents=True, exist_ok=True)

        # 如果工作区已有该文件，跳过
        if file_path.exists():
            logger.info("文件已存在，跳过: %s", file_path)
            return file_path

        # 优先从本地缓存复制
        cache_path = self.assets_cache / source
        if cache_path.exists():
            shutil.copy2(cache_path, file_path)
            logger.info("从缓存复制: %s → %s", cache_path, file_path)
            return file_path

        # 回退到远程下载
        url = f"{PINCHBENCH_ASSETS_URL}/{source}"
        last_exc: Optional[Exception] = None

        for attempt in range(1, DOWNLOAD_RETRIES + 1):
            try:
                resp = requests.get(url, timeout=DOWNLOAD_TIMEOUT)
                resp.raise_for_status()
                try:
                    file_path.write_text(resp.text, encoding="utf-8")
                except UnicodeEncodeError:
                    file_path.write_bytes(resp.content)
                logger.info("从远程下载: %s → %s", url, file_path)
                return file_path
            except Exception as exc:
                last_exc = exc
                logger.warning(
                    "下载资产失败 (attempt %d/%d): %s — %s",
                    attempt, DOWNLOAD_RETRIES, url, exc,
                )

        raise RuntimeError(f"下载资产失败: {url} — {last_exc}")

    # ──────────────────────────────────────────────
    # 清理
    # ──────────────────────────────────────────────

    def cleanup_workspace(self, task_id: str) -> bool:
        """清理指定任务的工作区目录

        Args:
            task_id: 任务ID

        Returns:
            是否成功清理
        """
        ws_path = self._active_workspaces.pop(task_id, None)
        if ws_path and ws_path.exists():
            shutil.rmtree(ws_path, ignore_errors=True)
            logger.info("工作区已清理: %s", ws_path)
            return True
        return False

    def cleanup_all(self) -> int:
        """清理所有活跃工作区

        Returns:
            清理的工作区数量
        """
        count = 0
        for task_id in list(self._active_workspaces.keys()):
            if self.cleanup_workspace(task_id):
                count += 1
        return count
