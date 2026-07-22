# -*- coding: utf-8 -*-
"""
PinchBench 评分桥接器

对接 PinchBench 的 grade() 评分系统：
1. 执行 automated_checks 中的 grade() 函数
2. 适配 NexusFlow 输出 → PinchBench transcript 格式
3. 计算加权分数（automated + llm_judge）
4. 生成评分报告

Phase 1: LLM judge 评分暂时跳过（标记 TODO），只运行 automated 部分。
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from .task_parser import PinchBenchTask
from .config import DEFAULT_GRADING_WEIGHTS, RESULTS_ROOT

logger = logging.getLogger("pinchbench.grade")


# ============================================================================
# 数据模型
# ============================================================================

@dataclass
class GradeResult:
    """单任务评分结果"""
    task_id: str = ""
    status: str = "pending"  # pending | completed | skipped | error
    automated_scores: dict[str, float] = field(default_factory=dict)
    automated_avg: float = 0.0
    llm_judge_scores: dict[str, float] = field(default_factory=dict)
    llm_judge_avg: float = 0.0
    weighted_total: float = 0.0
    grading_weights: dict[str, float] = field(default_factory=dict)
    error: Optional[str] = None
    duration_seconds: float = 0.0
    agent_used: str = ""
    timestamp: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "status": self.status,
            "automated_scores": self.automated_scores,
            "automated_avg": round(self.automated_avg, 4),
            "llm_judge_scores": self.llm_judge_scores,
            "llm_judge_avg": round(self.llm_judge_avg, 4),
            "weighted_total": round(self.weighted_total, 4),
            "grading_weights": self.grading_weights,
            "error": self.error,
            "duration_seconds": round(self.duration_seconds, 2),
            "agent_used": self.agent_used,
            "timestamp": self.timestamp,
        }


# ============================================================================
# Transcript 适配
# ============================================================================

def build_transcript(
    agent_response: str,
    workspace_files_written: list[str] | None = None,
) -> list[dict[str, Any]]:
    """将 NexusFlow Agent 的输出适配为 PinchBench transcript 格式。

    PinchBench 期望 transcript 是 list[dict]，每个 dict 有 type/message 字段。

    Args:
        agent_response: Agent 的文本响应
        workspace_files_written: 已写入工作区的文件列表

    Returns:
        PinchBench 格式的 transcript
    """
    transcript: list[dict[str, Any]] = []

    # 用户消息（模拟任务输入）
    transcript.append({
        "type": "message",
        "message": {"role": "user", "content": "[PinchBench Task Prompt]"},
    })

    # Agent 响应
    transcript.append({
        "type": "message",
        "message": {"role": "assistant", "content": agent_response},
    })

    # 工作区文件信息
    if workspace_files_written:
        for fpath in workspace_files_written:
            transcript.append({
                "type": "tool_result",
                "message": {"role": "tool", "content": f"File written: {fpath}"},
            })

    return transcript


# ============================================================================
# 评分执行
# ============================================================================

class GradeBridge:
    """PinchBench 评分桥接器"""

    def __init__(self, results_root: Path | str | None = None) -> None:
        self.results_root = Path(results_root) if results_root else RESULTS_ROOT
        self.results_root.mkdir(parents=True, exist_ok=True)

    def grade_task(
        self,
        task: PinchBenchTask,
        transcript: list[dict[str, Any]],
        workspace_path: str | Path,
        agent_used: str = "",
    ) -> GradeResult:
        """对单个任务执行评分。

        1. 如果 task 有 grade_fn，执行 automated 评分
        2. 如果 grading_type 为 llm_judge 或 hybrid，TODO: 暂跳过
        3. 计算加权总分

        Args:
            task: 已解析的任务对象
            transcript: PinchBench 格式的对话记录
            workspace_path: 工作区路径（grade 函数需要）
            agent_used: 使用的 Agent 名称

        Returns:
            GradeResult
        """
        start = time.time()
        result = GradeResult(
            task_id=task.id,
            grading_weights=task.grading_weights,
            agent_used=agent_used,
            timestamp=time.strftime("%Y-%m-%dT%H:%M:%S"),
        )

        # ── Automated 评分 ──
        if task.grade_fn is not None:
            try:
                ws_str = str(workspace_path)
                logger.info("执行 automated 评分: %s (workspace=%s)", task.id, ws_str)
                auto_scores = task.grade_fn(transcript, ws_str)

                if isinstance(auto_scores, dict):
                    result.automated_scores = {k: float(v) for k, v in auto_scores.items()}
                    if result.automated_scores:
                        result.automated_avg = sum(result.automated_scores.values()) / len(result.automated_scores)
                    result.status = "completed"
                else:
                    result.error = f"grade() 返回了非 dict 类型: {type(auto_scores)}"
                    result.status = "error"

            except Exception as exc:
                logger.error("automated 评分执行失败 [%s]: %s", task.id, exc)
                result.error = f"grade() 执行异常: {exc}"
                result.status = "error"
        else:
            # 没有 grade 函数的任务
            if task.grading_type in ("automated", "hybrid"):
                result.error = "任务要求 automated/hybrid 评分但无 grade() 函数"
                result.status = "skipped"
            else:
                # llm_judge 类型 — Phase 1 暂跳过
                result.automated_scores = {}
                result.automated_avg = 0.0
                result.status = "completed"
                logger.info("llm_judge 评分暂跳过: %s", task.id)

        # ── LLM Judge 评分（TODO: Phase 2）──
        if task.grading_type in ("llm_judge", "hybrid") and task.llm_rubric:
            result.llm_judge_scores = {}
            result.llm_judge_avg = 0.0
            # TODO: Phase 2 实现 LLM judge 评分
            logger.info("LLM judge 评分暂未实现，跳过: %s", task.id)

        # ── 加权总分 ──
        weights = task.grading_weights or DEFAULT_GRADING_WEIGHTS
        auto_w = weights.get("automated", 0.0)
        llm_w = weights.get("llm_judge", 0.0)

        # 如果 llm_judge 未执行，将其权重归零并重新归一化
        if llm_w > 0 and result.llm_judge_avg == 0.0 and result.status != "error":
            total_w = auto_w + llm_w
            if total_w > 0:
                auto_w = auto_w / total_w
            llm_w = 0.0

        result.weighted_total = auto_w * result.automated_avg + llm_w * result.llm_judge_avg

        result.duration_seconds = time.time() - start
        return result

    # ──────────────────────────────────────────────
    # 结果输出
    # ──────────────────────────────────────────────

    def save_result(self, result: GradeResult) -> Path:
        """将评分结果保存为 JSON 文件

        Args:
            result: 评分结果

        Returns:
            保存的文件路径
        """
        out_path = self.results_root / f"{result.task_id}_result.json"
        out_path.write_text(
            json.dumps(result.to_dict(), indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        logger.info("评分结果已保存: %s", out_path)
        return out_path

    @staticmethod
    def generate_summary(results: list[GradeResult]) -> dict[str, Any]:
        """生成汇总报告

        Args:
            results: 所有任务的评分结果

        Returns:
            汇总字典
        """
        total = len(results)
        completed = sum(1 for r in results if r.status == "completed")
        errors = sum(1 for r in results if r.status == "error")
        skipped = sum(1 for r in results if r.status == "skipped")

        avg_scores: dict[str, float] = {}
        if completed > 0:
            avg_scores["automated_avg"] = sum(r.automated_avg for r in results if r.status == "completed") / completed
            avg_scores["weighted_total_avg"] = sum(r.weighted_total for r in results if r.status == "completed") / completed

        by_category: dict[str, dict[str, Any]] = {}
        for r in results:
            cat = r.task_id  # fallback
            if cat not in by_category:
                by_category[cat] = {"count": 0, "weighted_total_sum": 0.0}
            by_category[cat]["count"] += 1
            by_category[cat]["weighted_total_sum"] += r.weighted_total

        return {
            "total_tasks": total,
            "completed": completed,
            "errors": errors,
            "skipped": skipped,
            "average_scores": {k: round(v, 4) for k, v in avg_scores.items()},
            "per_task": {r.task_id: r.to_dict() for r in results},
            "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        }

    def save_summary(self, results: list[GradeResult]) -> Path:
        """保存汇总报告

        Args:
            results: 所有任务的评分结果

        Returns:
            保存的文件路径
        """
        summary = self.generate_summary(results)
        out_path = self.results_root / "summary.json"
        out_path.write_text(
            json.dumps(summary, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        logger.info("汇总报告已保存: %s", out_path)
        return out_path
