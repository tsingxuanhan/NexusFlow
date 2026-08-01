"""
LHAB-NF Scorer
===============
Evaluates task execution results against acceptance criteria.
Computes all metrics defined in the LHAB-NF specification.
"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any
import json
import math


@dataclass
class StepResult:
    """Result of a single step execution."""
    step_id: str
    success: bool
    output: Any = None
    error: Optional[str] = None
    elapsed_seconds: float = 0.0
    tokens_used: int = 0
    cost_cny: float = 0.0
    agent_role: str = ""
    device_used: str = ""
    privacy_violation: bool = False
    evidence_chain: List[Dict] = field(default_factory=list)


@dataclass
class TaskResult:
    """Complete result of a task execution."""
    task_id: str
    steps: List[StepResult] = field(default_factory=list)
    total_elapsed_seconds: float = 0.0
    total_tokens: int = 0
    total_cost_cny: float = 0.0
    perturbations_triggered: int = 0
    perturbations_recovered: int = 0
    requirement_changes_handled: int = 0
    human_interventions: int = 0
    privacy_violations: int = 0
    memory_pollution_detected: bool = False
    final_output: Any = None


@dataclass
class MetricScores:
    """All computed metrics for a task."""
    # Core metrics
    task_completion_rate: float = 0.0      # TCR
    step_success_rate: float = 0.0         # SSR
    long_horizon_recovery_rate: float = 0.0 # LDRR
    goal_hold_rate: float = 0.0            # GHR
    requirement_change_recovery: float = 0.0 # RCRR
    node_failure_recovery: float = 0.0     # NFRR
    avg_recovery_time: float = 0.0         # ART
    human_intervention_count: int = 0      # HIC
    
    # Efficiency
    total_tokens: int = 0
    cost_per_success: float = 0.0          # CPS
    end_to_end_latency: float = 0.0        # E2E
    communication_efficiency: float = 0.0  # CE
    
    # Quality
    output_quality: float = 0.0            # OQ
    error_conclusion_rate: float = 0.0     # ECR
    privacy_violation_count: int = 0       # PVC
    memory_pollution_rate: float = 0.0     # MPR


def compute_metrics(result: TaskResult, max_steps: int = 100) -> MetricScores:
    """Compute all metrics from a task result."""
    metrics = MetricScores()
    
    total_steps = len(result.steps)
    if total_steps == 0:
        return metrics
    
    # Step Success Rate
    successful = sum(1 for s in result.steps if s.success)
    metrics.step_success_rate = successful / total_steps
    
    # Task Completion Rate (binary: all steps must succeed + acceptance criteria met)
    metrics.task_completion_rate = 1.0 if metrics.step_success_rate == 1.0 else 0.0
    
    # Perturbation Recovery
    if result.perturbations_triggered > 0:
        metrics.node_failure_recovery = result.perturbations_recovered / result.perturbations_triggered
    
    # Average Recovery Time (simplified: estimate from step elapsed times)
    recovery_steps = [s for s in result.steps if "recover" in (s.output or {}).get("action", "") if isinstance(s.output, dict)]
    if recovery_steps:
        metrics.avg_recovery_time = sum(s.elapsed_seconds for s in recovery_steps) / len(recovery_steps)
    
    # Human interventions
    metrics.human_intervention_count = result.human_interventions
    
    # Efficiency metrics
    metrics.total_tokens = result.total_tokens
    if successful > 0:
        metrics.cost_per_success = result.total_cost_cny / max(1, successful)
    metrics.end_to_end_latency = result.total_elapsed_seconds
    
    # Communication Efficiency (simplified)
    # CE = (Q_downstream * R_fact) / (T_msg * (1 + R_dup + R_conflict))
    # Placeholder calculation
    quality = metrics.step_success_rate  # proxy for downstream quality
    metrics.communication_efficiency = quality / max(1, metrics.total_tokens / 1000)
    
    # Privacy violations
    metrics.privacy_violation_count = result.privacy_violations
    
    # Memory pollution
    metrics.memory_pollution_rate = 1.0 if result.memory_pollution_detected else 0.0
    
    return metrics


def compute_composite_score(metrics: MetricScores, weights: Dict[str, float] = None) -> float:
    """
    Compute composite task score.
    
    S = w1*TCR + w2*OQ + w3*(1-ECR) + w4*ART_norm + w5*(1-PVC_norm)
    
    Default weights: w1=0.3, w2=0.25, w3=0.2, w4=0.15, w5=0.1
    """
    if weights is None:
        weights = {
            "tcr": 0.3,
            "oq": 0.25,
            "ecr": 0.2,
            "art": 0.15,
            "pvc": 0.1,
        }
    
    tcr = metrics.task_completion_rate
    oq = metrics.output_quality
    ecr = metrics.error_conclusion_rate
    
    # Normalize ART (inverse: faster is better, cap at 60s)
    art_norm = 1.0 / (1.0 + metrics.avg_recovery_time / 60.0)
    
    # PVC (0 or 1)
    pvc_norm = 1.0 if metrics.privacy_violation_count == 0 else 0.0
    
    score = (
        weights["tcr"] * tcr +
        weights["oq"] * oq +
        weights["ecr"] * (1 - ecr) +
        weights["art"] * art_norm +
        weights["pvc"] * pvc_norm
    )
    
    return round(score, 4)


def compare_methods(scores_a: List[float], scores_b: List[float]) -> Dict:
    """
    Compare two methods using bootstrap confidence interval and Wilcoxon test.
    
    Returns:
        delta: mean difference
        ci_95: 95% bootstrap CI
        p_value: from Wilcoxon signed-rank test
        significant: whether p < 0.05
    """
    import random
    
    if len(scores_a) != len(scores_b) or len(scores_a) < 3:
        return {"error": "Need at least 3 paired observations"}
    
    n = len(scores_a)
    diffs = [a - b for a, b in zip(scores_a, scores_b)]
    delta = sum(diffs) / n
    
    # Bootstrap CI (1000 iterations)
    random.seed(42)
    bootstrap_deltas = []
    for _ in range(1000):
        sample = [random.choice(diffs) for _ in range(n)]
        bootstrap_deltas.append(sum(sample) / n)
    
    bootstrap_deltas.sort()
    ci_low = bootstrap_deltas[int(0.025 * 1000)]
    ci_high = bootstrap_deltas[int(0.975 * 1000)]
    
    # Simple Wilcoxon approximation
    # For production, use scipy.stats.wilcoxon
    positive = sum(1 for d in diffs if d > 0)
    # Approximate p-value using normal approximation
    if n >= 10:
        z = (positive - n/2) / math.sqrt(n/4)
        p_value = 2 * (1 - _normal_cdf(abs(z)))
    else:
        p_value = 0.05  # conservative for small samples
    
    return {
        "delta": round(delta, 4),
        "ci_95": [round(ci_low, 4), round(ci_high, 4)],
        "p_value": round(p_value, 4),
        "significant": p_value < 0.05,
        "n_observations": n,
    }


def _normal_cdf(x: float) -> float:
    """Approximate standard normal CDF."""
    return 0.5 * (1 + math.erf(x / math.sqrt(2)))


def format_report(task_id: str, metrics: MetricScores, score: float) -> str:
    """Format a human-readable metric report."""
    lines = [
        f"# LHAB-NF 评测报告: {task_id}",
        "",
        "## 核心指标",
        f"| 指标 | 值 |",
        f"|------|-----|",
        f"| 任务完成率 (TCR) | {metrics.task_completion_rate:.2%} |",
        f"| 步骤成功率 (SSR) | {metrics.step_success_rate:.2%} |",
        f"| 长程依赖恢复率 (LDRR) | {metrics.long_horizon_recovery_rate:.2%} |",
        f"| 目标保持率 (GHR) | {metrics.goal_hold_rate:.2f} |",
        f"| 需求变更恢复率 (RCRR) | {metrics.requirement_change_recovery:.2%} |",
        f"| 节点失效恢复率 (NFRR) | {metrics.node_failure_recovery:.2%} |",
        f"| 平均恢复时间 (ART) | {metrics.avg_recovery_time:.1f}s |",
        f"| 人工干预次数 (HIC) | {metrics.human_intervention_count} |",
        "",
        "## 效率指标",
        f"| 指标 | 值 |",
        f"|------|-----|",
        f"| 总 Token | {metrics.total_tokens:,} |",
        f"| 每成功任务成本 | ¥{metrics.cost_per_success:.4f} |",
        f"| 端到端时延 | {metrics.end_to_end_latency:.1f}s |",
        f"| 通信效率 | {metrics.communication_efficiency:.4f} |",
        "",
        "## 质量指标",
        f"| 指标 | 值 |",
        f"|------|-----|",
        f"| 输出质量 | {metrics.output_quality:.2f} |",
        f"| 错误结论率 | {metrics.error_conclusion_rate:.2%} |",
        f"| 隐私违规次数 | {metrics.privacy_violation_count} |",
        f"| 记忆污染率 | {metrics.memory_pollution_rate:.2%} |",
        "",
        f"**综合评分: {score:.4f}**",
    ]
    return "\n".join(lines)
