# -*- coding: utf-8 -*-
"""
铉枢·炉守 Self-Healing Loop — 自修复循环
XuanHub Self-Healing Loop v4.2

基于 Agora (ICML 2026) Self-Healing Reflection Loop 设计。

核心功能：
1. Agent 执行失败时自动捕获错误日志和执行上下文
2. 进行定向自我修正（不是重新开始，而是精准修复）
3. 5次重试 + 指数退避（1s/2s/4s/8s/16s）
4. 错误分类：RECOVERABLE / REQUIRES_HUMAN / FATAL
5. 精简错误回传（只传错误摘要+最近3步上下文，不传全量历史）
6. 与 GoalVerifier 集成（修复后结果仍需验证）

与 GoalVerifier 的关系：
- Self-Healing Loop = 内部修复（Agent 自己修）
- GoalVerifier = 外部验证（独立 judge 判定）
- 形成双保险：内修复 + 外验证
"""

import logging
import time
import traceback
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger("SelfHealing")


# ============================================================================
# 枚举与数据结构
# ============================================================================

class HealingStatus(Enum):
    """Healing loop status"""
    SUCCESS = "success"
    HEALING = "healing"
    ESCALATED = "escalated"
    FAILED = "failed"
    NOT_NEEDED = "not_needed"


class ErrorClassification(Enum):
    """Error classification for routing healing strategy"""
    RECOVERABLE = "recoverable"       # Can self-heal (format error, timeout, missing data)
    REQUIRES_HUMAN = "requires_human" # Needs human input (ambiguous requirement, domain judgment)
    FATAL = "fatal"                   # Cannot recover (permission denied, invalid config)


@dataclass
class ErrorContext:
    """
    Captured error context for directed self-correction.
    Analogous to Agora's stack trace + execution log capture.
    """
    error_type: str
    error_message: str
    stack_trace: str = ""
    execution_context: str = ""
    input_data: str = ""
    agent_role: str = ""
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_compact_str(self) -> str:
        """
        Compact error representation for self-correction prompt.
        Key insight from Agora: "精简回传进行定向自我修正"
        """
        parts = [f"[{self.error_type}] {self.error_message}"]
        if self.execution_context:
            parts.append(f"Context: {self.execution_context[:200]}")
        if self.stack_trace:
            frames = self.stack_trace.strip().split('\n')
            relevant = frames[-min(6, len(frames)):]
            parts.append("Stack (last 3 frames):\n" + '\n'.join(relevant))
        return '\n'.join(parts)


@dataclass
class HealingAttempt:
    """A single healing attempt"""
    attempt_number: int
    error_context: ErrorContext
    fix_applied: str = ""
    result: str = ""
    success: bool = False
    duration_seconds: float = 0.0
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self) -> Dict:
        return {
            "attempt_number": self.attempt_number,
            "error_type": self.error_context.error_type,
            "fix_applied": self.fix_applied[:200],
            "success": self.success,
            "duration_seconds": self.duration_seconds,
        }


@dataclass
class HealingResult:
    """Result of the complete healing process"""
    status: HealingStatus
    attempts: List[HealingAttempt] = field(default_factory=list)
    final_output: str = ""
    total_duration: float = 0.0

    def to_dict(self) -> Dict:
        return {
            "status": self.status.value,
            "attempts": [a.to_dict() for a in self.attempts],
            "final_output": self.final_output[:500],
            "total_duration": self.total_duration,
            "total_attempts": len(self.attempts),
        }


# ============================================================================
# SelfHealingLoop 主类
# ============================================================================

class SelfHealingLoop:
    """
    Self-Healing Reflection Loop.

    Wraps any agent execution function with automatic error recovery.

    Usage:
        healing = SelfHealingLoop()
        result = healing.execute_with_healing(
            task_fn=agent.chat,
            task_input="Analyze this paper...",
            agent_role="miner",
            max_retries=5,
        )

    Integration with existing system:
    - Wraps BaseAgent.chat() or any execution function
    - Error context recorded in CheckpointWriter.errors_and_fixes
    - Final result still goes through GoalVerifier
    """

    # Default configuration
    DEFAULT_MAX_RETRIES: int = 5
    BASE_BACKOFF_SECONDS: float = 1.0
    MAX_BACKOFF_SECONDS: float = 30.0
    ESCALATION_THRESHOLD: int = 3

    def __init__(
        self,
        max_retries: int = DEFAULT_MAX_RETRIES,
        checkpoint_writer: Any = None,
    ):
        self.max_retries = max_retries
        self.checkpoint_writer = checkpoint_writer

        self._stats: Dict[str, int] = {
            "total_healing_sessions": 0,
            "total_attempts": 0,
            "successful_heals": 0,
            "escalations": 0,
            "failures": 0,
        }

    # ============ Core API ============

    def attempt_healing(
        self,
        task_fn: Callable,
        task_input: str,
        agent_role: str = "",
        max_retries: Optional[int] = None,
        escalation_fn: Optional[Callable] = None,
    ) -> HealingResult:
        """
        Alias for execute_with_healing — primary API name per spec.
        """
        return self.execute_with_healing(
            task_fn=task_fn,
            task_input=task_input,
            agent_role=agent_role,
            max_retries=max_retries,
            escalation_fn=escalation_fn,
        )

    def execute_with_healing(
        self,
        task_fn: Callable,
        task_input: str,
        agent_role: str = "",
        max_retries: Optional[int] = None,
        escalation_fn: Optional[Callable] = None,
    ) -> HealingResult:
        """
        Execute a task function with automatic self-healing.

        Args:
            task_fn: The function to execute (e.g., agent.chat)
            task_input: Input to the function
            agent_role: Role of the executing agent
            max_retries: Override default max retries
            escalation_fn: Function to call for escalation

        Returns:
            HealingResult with status and output
        """
        start_time = time.time()
        retries = max_retries or self.max_retries
        attempts: List[HealingAttempt] = []

        self._stats["total_healing_sessions"] += 1

        for attempt_num in range(1, retries + 1):
            attempt_start = time.time()

            try:
                result = task_fn(task_input)

                if self._is_error_result(result):
                    error_ctx = self._extract_error(result, task_input, agent_role)
                else:
                    # Success!
                    attempt = HealingAttempt(
                        attempt_number=attempt_num,
                        error_context=ErrorContext(error_type="", error_message=""),
                        fix_applied="No fix needed",
                        result=str(result)[:500],
                        success=True,
                        duration_seconds=time.time() - attempt_start,
                    )
                    attempts.append(attempt)

                    self._stats["successful_heals"] += 1
                    self._stats["total_attempts"] += len(attempts)

                    return HealingResult(
                        status=HealingStatus.SUCCESS if attempt_num > 1 else HealingStatus.NOT_NEEDED,
                        attempts=attempts,
                        final_output=str(result),
                        total_duration=time.time() - start_time,
                    )

            except Exception as e:
                error_ctx = self._capture_exception(e, task_input, agent_role)

            # Classify the error
            classification = self.classify_error(error_ctx)

            if classification == ErrorClassification.FATAL:
                logger.warning(f"[SelfHealing] Fatal error at attempt {attempt_num}, aborting")
                attempts.append(HealingAttempt(
                    attempt_number=attempt_num,
                    error_context=error_ctx,
                    fix_applied="Fatal error — no retry",
                    success=False,
                    duration_seconds=time.time() - attempt_start,
                ))
                break

            # We have an error - attempt self-healing
            fix_prompt = self._build_fix_prompt(error_ctx, attempts)

            try:
                fix_result = task_fn(fix_prompt)
                fix_applied = f"Attempt {attempt_num}: {fix_prompt[:100]}..."

                attempt = HealingAttempt(
                    attempt_number=attempt_num,
                    error_context=error_ctx,
                    fix_applied=fix_applied,
                    result=str(fix_result)[:500],
                    success=not self._is_error_result(fix_result),
                    duration_seconds=time.time() - attempt_start,
                )
                attempts.append(attempt)

                if attempt.success:
                    self._stats["successful_heals"] += 1
                    self._stats["total_attempts"] += len(attempts)
                    self._record_in_checkpoint(error_ctx, fix_applied)

                    return HealingResult(
                        status=HealingStatus.SUCCESS,
                        attempts=attempts,
                        final_output=str(fix_result),
                        total_duration=time.time() - start_time,
                    )

            except Exception as fix_e:
                attempt = HealingAttempt(
                    attempt_number=attempt_num,
                    error_context=error_ctx,
                    fix_applied=f"Fix attempt failed: {str(fix_e)[:100]}",
                    success=False,
                    duration_seconds=time.time() - attempt_start,
                )
                attempts.append(attempt)

            # Escalation check
            if attempt_num >= self.ESCALATION_THRESHOLD and escalation_fn:
                try:
                    esc_result = escalation_fn(task_input, error_ctx.to_compact_str())
                    if not self._is_error_result(esc_result):
                        attempts[-1].success = True
                        self._stats["escalations"] += 1
                        return HealingResult(
                            status=HealingStatus.ESCALATED,
                            attempts=attempts,
                            final_output=str(esc_result),
                            total_duration=time.time() - start_time,
                        )
                except Exception:
                    pass

            # Backoff before next retry (exponential: 1s, 2s, 4s, 8s, 16s)
            if attempt_num < retries:
                backoff = min(
                    self.BASE_BACKOFF_SECONDS * (2 ** (attempt_num - 1)),
                    self.MAX_BACKOFF_SECONDS,
                )
                time.sleep(backoff)

        # All retries exhausted
        self._stats["failures"] += 1
        self._stats["total_attempts"] += len(attempts)

        return HealingResult(
            status=HealingStatus.FAILED,
            attempts=attempts,
            final_output="",
            total_duration=time.time() - start_time,
        )

    def classify_error(self, error_ctx: ErrorContext) -> ErrorClassification:
        """
        Classify error type to determine healing strategy.

        Returns:
            RECOVERABLE — can self-heal
            REQUIRES_HUMAN — needs human input
            FATAL — cannot recover
        """
        msg_lower = error_ctx.error_message.lower()

        # Fatal errors — no point retrying
        fatal_indicators = [
            "permission denied",
            "unauthorized",
            "invalid api key",
            "disk full",
            "out of memory",
            "配置错误",
            "权限不足",
        ]
        if any(ind in msg_lower for ind in fatal_indicators):
            return ErrorClassification.FATAL

        # Requires human — ambiguous or domain-specific
        human_indicators = [
            "ambiguous",
            "需要确认",
            "请确认",
            "multiple interpretations",
            "domain expertise required",
        ]
        if any(ind in msg_lower for ind in human_indicators):
            return ErrorClassification.REQUIRES_HUMAN

        # Default: recoverable
        return ErrorClassification.RECOVERABLE

    def escalate(
        self,
        task_input: str,
        error_ctx: ErrorContext,
        escalation_fn: Callable,
    ) -> str:
        """
        Escalate an error to a higher-level agent or human.

        Args:
            task_input: Original task input
            error_ctx: The error context
            escalation_fn: Function to handle escalation

        Returns:
            Result from escalation handler
        """
        self._stats["escalations"] += 1
        try:
            return escalation_fn(task_input, error_ctx.to_compact_str())
        except Exception as e:
            logger.error(f"[SelfHealing] Escalation failed: {e}")
            return f"Escalation failed: {str(e)[:200]}"

    # ============ Internal Methods ============

    def _is_error_result(self, result: Any) -> bool:
        """Check if a result indicates an error"""
        if result is None:
            return True
        result_str = str(result).lower()
        error_indicators = [
            "error:", "exception:", "failed:", "traceback:",
            "错误", "失败", "异常", "无法完成",
        ]
        return any(ind in result_str for ind in error_indicators)

    def _extract_error(self, result: Any, task_input: str, agent_role: str) -> ErrorContext:
        """Extract error context from an error result"""
        result_str = str(result)
        return ErrorContext(
            error_type="ExecutionError",
            error_message=result_str[:500],
            execution_context=task_input[:300],
            agent_role=agent_role,
        )

    def _capture_exception(self, e: Exception, task_input: str, agent_role: str) -> ErrorContext:
        """Capture error context from an exception"""
        return ErrorContext(
            error_type=type(e).__name__,
            error_message=str(e),
            stack_trace=traceback.format_exc()[:1000],
            execution_context=task_input[:300],
            agent_role=agent_role,
        )

    def _build_fix_prompt(self, error_ctx: ErrorContext, prev_attempts: List[HealingAttempt]) -> str:
        """
        Build a directed self-correction prompt.
        Key insight: "精简回传进行定向自我修正"
        """
        parts = [
            "## 任务执行出错，请进行定向自我修正\n",
            "### 错误信息（精简版）",
            error_ctx.to_compact_str(),
        ]

        if prev_attempts:
            parts.append("\n### 之前尝试过的修复（不要重复）")
            for a in prev_attempts[-3:]:
                status = '成功' if a.success else '失败'
                parts.append(f"  尝试{a.attempt_number}: {a.fix_applied[:100]} → {status}")

        parts.append("\n### 修正要求")
        parts.append("1. 分析错误的根因（不要猜测）")
        parts.append("2. 采用与之前不同的修复策略")
        parts.append("3. 直接输出修正后的完整结果")

        return '\n'.join(parts)

    def _record_in_checkpoint(self, error: ErrorContext, fix: str) -> None:
        """Record healing result in CheckpointWriter"""
        if self.checkpoint_writer:
            try:
                self.checkpoint_writer.update_state(
                    errors_and_fixes=[{
                        "error": f"[{error.error_type}] {error.error_message[:200]}",
                        "fix": fix[:200],
                        "agent": error.agent_role,
                        "timestamp": error.timestamp,
                    }]
                )
            except Exception as e:
                logger.warning(f"[SelfHealing] Failed to record in checkpoint: {e}")

    def get_stats(self) -> Dict:
        """Return a copy of current stats"""
        return self._stats.copy()
