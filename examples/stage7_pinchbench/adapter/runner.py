# -*- coding: utf-8 -*-
"""
PinchBench Adapter 主运行器

命令行入口，编排任务加载 → 工作区准备 → Agent 执行 → 评分 → 结果输出。

用法:
    python -m adapter.runner --task task_market_research
    python -m adapter.runner --tier 1
    python -m adapter.runner --all
    python -m adapter.runner --task task_csv_pension_risk --output results/
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
import time
from pathlib import Path
from typing import Optional

from .config import (
    TASK_MANIFEST_PATH,
    TASKS_RAW_DIR,
    RESULTS_ROOT,
    NEXUSFLOW_REPO_ROOT,
    DEFAULT_TIMEOUT,
)
from .task_parser import load_task, PinchBenchTask
from .workspace_manager import WorkspaceManager
from .nf_agent_runner import NFAgentRunner, AgentRunResult
from .nf_orchestrator_runner import NFOrchestratorRunner
from .grade_bridge import GradeBridge, GradeResult, build_transcript

logger = logging.getLogger("pinchbench.runner")


# ============================================================================
# 清单加载
# ============================================================================

def load_manifest(manifest_path: Path | str | None = None) -> list[dict]:
    """加载 task_manifest.json

    Args:
        manifest_path: 清单文件路径

    Returns:
        任务条目列表
    """
    path = Path(manifest_path) if manifest_path else TASK_MANIFEST_PATH
    if not path.exists():
        raise FileNotFoundError(f"任务清单不存在: {path}")

    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    return data.get("selected_tasks", [])


def filter_tasks(
    manifest: list[dict],
    task_id: Optional[str] = None,
    tier: Optional[int] = None,
    all_tasks: bool = False,
) -> list[dict]:
    """根据命令行参数过滤任务

    Args:
        manifest: 完整清单
        task_id: 指定单个任务ID
        tier: 指定 tier 等级
        all_tasks: 选择全部任务

    Returns:
        过滤后的任务条目
    """
    if task_id:
        matched = [t for t in manifest if t["id"] == task_id]
        if not matched:
            raise ValueError(f"未找到任务: {task_id}")
        return matched

    if tier is not None:
        return [t for t in manifest if t.get("tier") == tier]

    if all_tasks:
        return manifest

    # 默认只跑 Tier-1
    return [t for t in manifest if t.get("tier") == 1]


# ============================================================================
# 单任务执行流程
# ============================================================================

def run_single_task(
    task_entry: dict,
    ws_manager: WorkspaceManager,
    agent_runner,  # NFAgentRunner | NFOrchestratorRunner
    grade_bridge: GradeBridge,
    local_tasks_dir: Path | str | None = None,
) -> GradeResult:
    """执行单个任务的完整流程。

    流程: 加载定义 → 创建工作区 → 注入文件 → Agent 执行 → 评分 → 保存结果

    Args:
        task_entry: 清单中的任务条目
        ws_manager: 工作区管理器
        agent_runner: Agent 执行器
        grade_bridge: 评分桥接器
        local_tasks_dir: 本地任务定义目录

    Returns:
        GradeResult
    """
    task_id = task_entry["id"]
    logger.info("=" * 60)
    logger.info("开始执行任务: %s (%s)", task_id, task_entry.get("name", ""))
    logger.info("=" * 60)

    # 1. 加载任务定义
    try:
        task = load_task(task_id, local_dir=local_tasks_dir)
    except Exception as exc:
        logger.error("加载任务定义失败 [%s]: %s", task_id, exc)
        return GradeResult(
            task_id=task_id,
            status="error",
            error=f"加载任务定义失败: {exc}",
            timestamp=time.strftime("%Y-%m-%dT%H:%M:%S"),
        )

    # 2. 创建工作区
    try:
        workspace_path = ws_manager.create_workspace(task)
    except Exception as exc:
        logger.error("创建工作区失败 [%s]: %s", task_id, exc)
        return GradeResult(
            task_id=task_id,
            status="error",
            error=f"创建工作区失败: {exc}",
            timestamp=time.strftime("%Y-%m-%dT%H:%M:%S"),
        )

    # 3. 注入工作区文件
    try:
        ws_manager.inject_workspace_files(task, workspace_path)
    except Exception as exc:
        logger.warning("注入工作区文件失败 [%s]: %s", task_id, exc)

    # 4. Agent 执行
    try:
        run_result: AgentRunResult = agent_runner.run_task(task, workspace_path)
    except Exception as exc:
        logger.error("Agent 执行失败 [%s]: %s", task_id, exc)
        return GradeResult(
            task_id=task_id,
            status="error",
            error=f"Agent 执行异常: {exc}",
            timestamp=time.strftime("%Y-%m-%dT%H:%M:%S"),
        )

    # 5. 如果 Agent 没有自动写文件，尝试 fallback
    if not run_result.workspace_files_written and run_result.status == "completed":
        _fallback_write_response(task, run_result, workspace_path)

    # 6. 评分
    grade_result = grade_bridge.grade_task(
        task=task,
        transcript=run_result.transcript,
        workspace_path=workspace_path,
        agent_used=run_result.agent_used,
    )

    # 7. 保存结果
    grade_bridge.save_result(grade_result)

    # 日志输出
    logger.info(
        "任务 %s 完成: status=%s, automated_avg=%.3f, weighted=%.3f, agent=%s, duration=%.1fs",
        task_id,
        grade_result.status,
        grade_result.automated_avg,
        grade_result.weighted_total,
        grade_result.agent_used,
        grade_result.duration_seconds,
    )

    return grade_result


def _fallback_write_response(
    task: PinchBenchTask,
    run_result: AgentRunResult,
    workspace_path: Path,
) -> None:
    """Fallback: 如果 Agent 没有自动写文件，从响应中提取内容写入。

    检查 prompt 中要求的输出文件，如果不存在，
    将 Agent 响应写入该文件。
    """
    import re

    # 提取期望的输出文件名
    filename_patterns = re.findall(
        r'(?:save|write|output|create|named?\s+(?:exactly\s+)?)[`"]([\w.-]+\.\w+)["`]',
        task.prompt,
        re.IGNORECASE,
    )
    if not filename_patterns:
        filename_patterns = re.findall(r'`([\w-]+\.\w+)`', task.prompt)

    if not filename_patterns:
        return

    target_fname = filename_patterns[0]
    target_path = workspace_path / target_fname

    if target_path.exists():
        run_result.workspace_files_written.append(target_fname)
        return

    # 将响应写入文件
    response = run_result.response
    if not response:
        return

    # 尝试提取 markdown 内容（去除代码块包裹）
    content = response
    # 如果响应包含 ```markdown ... ``` 包裹，提取内容
    code_block_match = re.search(r"```(?:markdown|md)?\s*\n(.*?)```", response, re.DOTALL)
    if code_block_match:
        content = code_block_match.group(1).strip()

    try:
        target_path.write_text(content, encoding="utf-8")
        run_result.workspace_files_written.append(target_fname)
        logger.info("Fallback 写入文件: %s", target_path)
    except Exception as exc:
        logger.warning("Fallback 写入失败: %s — %s", target_path, exc)


# ============================================================================
# CLI 入口
# ============================================================================

def build_parser() -> argparse.ArgumentParser:
    """构建命令行参数解析器"""
    parser = argparse.ArgumentParser(
        prog="adapter.runner",
        description="PinchBench Hard Cases Adapter — NexusFlow 执行器",
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "--task",
        type=str,
        help="指定单个任务ID (如 task_market_research)",
    )
    group.add_argument(
        "--tier",
        type=int,
        choices=[1, 2, 3],
        help="执行指定 tier 的所有任务",
    )
    group.add_argument(
        "--all",
        action="store_true",
        dest="all_tasks",
        help="执行全部任务",
    )
    parser.add_argument(
        "--mode",
        type=str,
        choices=["sa", "nf"],
        default="sa",
        help="执行模式: sa=单Agent基线(默认), nf=NexusFlow完整管线(CDoL多Agent协作)",
    )
    parser.add_argument(
        "--output",
        type=str,
        default=None,
        help="结果输出目录 (默认: SA模式→./results/, NF模式→./results_nf/)",
    )
    parser.add_argument(
        "--tasks-dir",
        type=str,
        default=None,
        help="本地任务定义目录 (默认: ./tasks_raw/)",
    )
    parser.add_argument(
        "--no-cleanup",
        action="store_true",
        help="执行后不清理工作区",
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="详细日志输出",
    )
    return parser


def main() -> None:
    """CLI 入口函数"""
    parser = build_parser()
    args = parser.parse_args()

    # 日志配置
    log_level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    )

    # 路径配置
    tasks_dir = Path(args.tasks_dir) if args.tasks_dir else TASKS_RAW_DIR

    # 根据模式确定结果目录
    mode = args.mode
    if args.output:
        results_dir = Path(args.output)
    elif mode == "nf":
        results_dir = Path(__file__).resolve().parent.parent / "results_nf"
    else:
        results_dir = RESULTS_ROOT

    logger.info("执行模式: %s, 结果目录: %s", mode.upper(), results_dir)

    # 加载清单
    try:
        manifest = load_manifest()
    except FileNotFoundError as exc:
        logger.error("无法加载任务清单: %s", exc)
        sys.exit(1)

    # 过滤任务
    try:
        selected = filter_tasks(
            manifest,
            task_id=args.task,
            tier=args.tier,
            all_tasks=args.all_tasks,
        )
    except ValueError as exc:
        logger.error("%s", exc)
        sys.exit(1)

    logger.info("选中 %d 个任务: %s", len(selected), [t["id"] for t in selected])

    # 初始化组件
    ws_manager = WorkspaceManager()

    # 根据模式选择执行器
    if mode == "nf":
        agent_runner = NFOrchestratorRunner()
        logger.info("使用 NF 完整管线模式 (NexusOrchestrator + CDoL)")
    else:
        agent_runner = NFAgentRunner()
        logger.info("使用 SA 单Agent基线模式")

    grade_bridge = GradeBridge(results_root=results_dir)

    # 逐任务执行
    results: list[GradeResult] = []
    for i, task_entry in enumerate(selected, 1):
        logger.info("[%d/%d] 执行: %s", i, len(selected), task_entry["id"])
        result = run_single_task(
            task_entry=task_entry,
            ws_manager=ws_manager,
            agent_runner=agent_runner,
            grade_bridge=grade_bridge,
            local_tasks_dir=tasks_dir,
        )
        results.append(result)

    # 保存汇总
    summary_path = grade_bridge.save_summary(results)

    # 清理工作区
    if not args.no_cleanup:
        cleaned = ws_manager.cleanup_all()
        logger.info("已清理 %d 个工作区", cleaned)

    # 打印摘要
    print("\n" + "=" * 60)
    print("PinchBench Hard Cases 执行摘要")
    print("=" * 60)
    for r in results:
        status_icon = "✓" if r.status == "completed" else "✗" if r.status == "error" else "⊘"
        print(
            f"  {status_icon} {r.task_id}: "
            f"automated_avg={r.automated_avg:.3f}, "
            f"weighted={r.weighted_total:.3f}, "
            f"agent={r.agent_used}, "
            f"status={r.status}"
        )
    print(f"\n汇总报告: {summary_path}")
    print("=" * 60)


if __name__ == "__main__":
    main()
