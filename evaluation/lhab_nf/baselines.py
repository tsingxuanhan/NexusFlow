"""
LHAB-NF Baseline Systems
=========================
Four baseline implementations for comparative benchmarking against NexusFlow.

Baselines:
  A. StaticPipeline     - Fixed sequential execution, no dynamic routing
  B. FullContextMultiAgent - All agents receive all context, vote on decisions
  C. FixedDAG           - Predefined dependency graph, no re-routing
  D. PlainSingleAgent   - Single general-purpose agent, serial execution

Each baseline executes the same 9 tasks using identical task definitions.
"""

import os
import sys
import json
import time
import random
import logging
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any, Tuple
from datetime import datetime
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lhab_nf.task_schema import Task, Step, Perturbation, PerturbationType, PrivacyLevel
from lhab_nf.scorer import (
    TaskResult, StepResult, MetricScores,
    compute_metrics, compute_composite_score, format_report,
)
from lhab_nf.runner import PerturbationInjector

logger = logging.getLogger("lhab_nf.baselines")


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _mock_step_execution(
    step: Step,
    context: Dict,
    rng: random.Random,
    success_prob: float = 0.80,
    token_range: Tuple[int, int] = (500, 3000),
) -> StepResult:
    """Deterministic mock step execution driven by an external RNG."""
    perturbation_active = context.get("active_perturbation")
    if perturbation_active and perturbation_active.get("blocking"):
        success_prob *= 0.35

    success = rng.random() < success_prob
    tokens = rng.randint(*token_range)
    cost = tokens * 0.000002  # ¥0.002 per 1k tokens

    return StepResult(
        step_id=step.id,
        success=success,
        output={"action": "completed" if success else "failed", "summary": "mock output"},
        error=None if success else "Simulated failure",
        tokens_used=tokens,
        cost_cny=cost,
        agent_role=step.agent_role,
        device_used=step.device_preference,
        privacy_violation=False,
    )


def _topological_order(steps: List[Step]) -> List[Step]:
    """Return steps in topological (dependency) order."""
    step_map = {s.id: s for s in steps}
    visited: set = set()
    order: List[Step] = []
    pending = set(s.id for s in steps)

    while pending:
        ready = [
            step_map[sid]
            for sid in list(pending)
            if all(d in visited for d in step_map[sid].input_deps)
        ]
        if not ready:
            # Deadlock – append remaining to break loop
            order.extend(step_map[sid] for sid in pending)
            break
        for s in ready:
            order.append(s)
            visited.add(s.id)
            pending.discard(s.id)
    return order


# ===========================================================================
# A. StaticPipeline
# ===========================================================================

class StaticPipeline:
    """
    Fixed-order sequential pipeline.

    Characteristics:
      - Executes steps in the order they appear in the task YAML.
      - Ignores device_preference, privacy_level, and load.
      - No dynamic re-routing or retry logic.
      - On failure, moves to next step regardless.
    """

    name: str = "StaticPipeline"

    def __init__(self, seed: int = 42):
        self.rng = random.Random(seed)
        self.perturbation_injector = PerturbationInjector()

    def run_task(self, task: Task) -> Dict:
        """Execute task with static pipeline and return result dict."""
        task_result = TaskResult(task_id=task.id)
        start = time.time()
        step_outputs: Dict[str, Any] = {}

        # Hard-coded order: as defined in YAML (list order)
        for step in task.steps:
            context: Dict[str, Any] = {
                "step_id": step.id,
                "step_outputs": step_outputs,
                "active_perturbation": None,
            }

            # Inject perturbations at the designated step
            for pert in task.perturbations:
                if pert.trigger_at_step == step.id:
                    effect = self.perturbation_injector.inject(pert, context)
                    context["active_perturbation"] = effect
                    task_result.perturbations_triggered += 1

            result = _mock_step_execution(step, context, self.rng, success_prob=0.75)
            task_result.steps.append(result)

            if result.success:
                step_outputs[step.id] = result.output
                if context["active_perturbation"]:
                    task_result.perturbations_recovered += 1
                    self.perturbation_injector.resolve(
                        context["active_perturbation"]["perturbation_id"], success=True
                    )

        task_result.total_elapsed_seconds = time.time() - start
        task_result.total_tokens = sum(s.tokens_used for s in task_result.steps)
        task_result.total_cost_cny = sum(s.cost_cny for s in task_result.steps)
        task_result.privacy_violations = sum(1 for s in task_result.steps if s.privacy_violation)

        metrics = compute_metrics(task_result, task.max_steps)
        score = compute_composite_score(metrics)

        return {
            "task_result": task_result,
            "metrics": metrics,
            "score": score,
            "trajectory": [
                {"step_id": s.step_id, "success": s.success, "tokens": s.tokens_used,
                 "elapsed": s.elapsed_seconds, "device": s.device_used}
                for s in task_result.steps
            ],
        }


# ===========================================================================
# B. FullContextMultiAgent
# ===========================================================================

class FullContextMultiAgent:
    """
    All agents receive ALL context, each independently decides, then vote.

    Characteristics:
      - Every step broadcasts the full step_outputs to every agent role.
      - Each agent independently produces an output; majority vote selects
        the final output.
      - No selective context filtering – wastes tokens on irrelevant info.
      - 3 virtual agents per step vote.
    """

    name: str = "FullContextMultiAgent"
    NUM_VOTERS: int = 3

    def __init__(self, seed: int = 42):
        self.rng = random.Random(seed)
        self.perturbation_injector = PerturbationInjector()

    def run_task(self, task: Task) -> Dict:
        task_result = TaskResult(task_id=task.id)
        start = time.time()
        step_outputs: Dict[str, Any] = {}

        for step in _topological_order(task.steps):
            context: Dict[str, Any] = {
                "step_id": step.id,
                "step_outputs": step_outputs,
                "active_perturbation": None,
            }

            for pert in task.perturbations:
                if pert.trigger_at_step == step.id:
                    effect = self.perturbation_injector.inject(pert, context)
                    context["active_perturbation"] = effect
                    task_result.perturbations_triggered += 1

            # Full context: every voter receives ALL prior outputs
            full_ctx_bytes = sum(
                len(json.dumps(v)) for v in step_outputs.values()
            )

            votes: List[bool] = []
            total_tokens = 0
            for _voter in range(self.NUM_VOTERS):
                # Each voter gets full context (wasteful)
                voter_result = _mock_step_execution(
                    step, context, self.rng,
                    success_prob=0.72,
                    token_range=(1500, 5000),  # higher token cost
                )
                votes.append(voter_result.success)
                total_tokens += voter_result.tokens_used

            # Majority vote
            majority_success = sum(votes) > len(votes) // 2

            result = StepResult(
                step_id=step.id,
                success=majority_success,
                output={"action": "completed" if majority_success else "failed",
                        "votes": votes, "context_bytes": full_ctx_bytes},
                error=None if majority_success else "Majority voted failure",
                tokens_used=total_tokens,
                cost_cny=total_tokens * 0.000002,
                agent_role=step.agent_role,
                device_used=step.device_preference,
                privacy_violation=False,
            )
            task_result.steps.append(result)

            if majority_success:
                step_outputs[step.id] = result.output
                if context["active_perturbation"]:
                    task_result.perturbations_recovered += 1
                    self.perturbation_injector.resolve(
                        context["active_perturbation"]["perturbation_id"], success=True
                    )

        task_result.total_elapsed_seconds = time.time() - start
        task_result.total_tokens = sum(s.tokens_used for s in task_result.steps)
        task_result.total_cost_cny = sum(s.cost_cny for s in task_result.steps)
        task_result.privacy_violations = sum(1 for s in task_result.steps if s.privacy_violation)

        metrics = compute_metrics(task_result, task.max_steps)
        score = compute_composite_score(metrics)

        return {
            "task_result": task_result,
            "metrics": metrics,
            "score": score,
            "trajectory": [
                {"step_id": s.step_id, "success": s.success, "tokens": s.tokens_used,
                 "elapsed": s.elapsed_seconds, "votes": s.output.get("votes", [])
                 if isinstance(s.output, dict) else []}
                for s in task_result.steps
            ],
        }


# ===========================================================================
# C. FixedDAG
# ===========================================================================

class FixedDAG:
    """
    Pre-defined dependency graph parsed statically from task YAML.

    Characteristics:
      - Builds DAG from input_deps, respects topological order.
      - NO dynamic re-routing: if a step fails, its dependents are skipped.
      - No retry, no migration.
      - Failure propagation: cascading skip on upstream failure.
    """

    name: str = "FixedDAG"

    def __init__(self, seed: int = 42):
        self.rng = random.Random(seed)
        self.perturbation_injector = PerturbationInjector()

    def run_task(self, task: Task) -> Dict:
        task_result = TaskResult(task_id=task.id)
        start = time.time()
        step_outputs: Dict[str, Any] = {}
        failed_steps: set = set()

        for step in _topological_order(task.steps):
            # Cascade failure: skip if any dependency failed
            if any(dep in failed_steps for dep in step.input_deps):
                result = StepResult(
                    step_id=step.id,
                    success=False,
                    output=None,
                    error="Skipped: upstream dependency failed",
                    tokens_used=0,
                    cost_cny=0.0,
                    agent_role=step.agent_role,
                    device_used=step.device_preference,
                    privacy_violation=False,
                )
                task_result.steps.append(result)
                failed_steps.add(step.id)
                continue

            context: Dict[str, Any] = {
                "step_id": step.id,
                "step_outputs": step_outputs,
                "active_perturbation": None,
            }

            for pert in task.perturbations:
                if pert.trigger_at_step == step.id:
                    effect = self.perturbation_injector.inject(pert, context)
                    context["active_perturbation"] = effect
                    task_result.perturbations_triggered += 1

            result = _mock_step_execution(step, context, self.rng, success_prob=0.82)
            task_result.steps.append(result)

            if result.success:
                step_outputs[step.id] = result.output
                if context["active_perturbation"]:
                    task_result.perturbations_recovered += 1
                    self.perturbation_injector.resolve(
                        context["active_perturbation"]["perturbation_id"], success=True
                    )
            else:
                failed_steps.add(step.id)

        task_result.total_elapsed_seconds = time.time() - start
        task_result.total_tokens = sum(s.tokens_used for s in task_result.steps)
        task_result.total_cost_cny = sum(s.cost_cny for s in task_result.steps)
        task_result.privacy_violations = sum(1 for s in task_result.steps if s.privacy_violation)

        metrics = compute_metrics(task_result, task.max_steps)
        score = compute_composite_score(metrics)

        return {
            "task_result": task_result,
            "metrics": metrics,
            "score": score,
            "trajectory": [
                {"step_id": s.step_id, "success": s.success, "tokens": s.tokens_used,
                 "elapsed": s.elapsed_seconds, "error": s.error}
                for s in task_result.steps
            ],
        }


# ===========================================================================
# D. PlainSingleAgent
# ===========================================================================

class PlainSingleAgent:
    """
    Single general-purpose agent handles ALL steps serially.

    Characteristics:
      - One agent role ("generalist") for every step.
      - No agent specialisation, no parallelism.
      - Lower per-step success probability (no specialisation bonus).
      - No context partitioning.
    """

    name: str = "PlainSingleAgent"

    def __init__(self, seed: int = 42):
        self.rng = random.Random(seed)
        self.perturbation_injector = PerturbationInjector()

    def run_task(self, task: Task) -> Dict:
        task_result = TaskResult(task_id=task.id)
        start = time.time()
        step_outputs: Dict[str, Any] = {}

        for step in _topological_order(task.steps):
            context: Dict[str, Any] = {
                "step_id": step.id,
                "step_outputs": step_outputs,
                "active_perturbation": None,
            }

            for pert in task.perturbations:
                if pert.trigger_at_step == step.id:
                    effect = self.perturbation_injector.inject(pert, context)
                    context["active_perturbation"] = effect
                    task_result.perturbations_triggered += 1

            # Single agent: no specialisation bonus, lower success
            result = _mock_step_execution(
                step, context, self.rng,
                success_prob=0.70,
                token_range=(2000, 6000),  # higher tokens (no specialisation)
            )
            # Override agent_role to "generalist"
            result.agent_role = "generalist"

            task_result.steps.append(result)

            if result.success:
                step_outputs[step.id] = result.output
                if context["active_perturbation"]:
                    task_result.perturbations_recovered += 1
                    self.perturbation_injector.resolve(
                        context["active_perturbation"]["perturbation_id"], success=True
                    )

        task_result.total_elapsed_seconds = time.time() - start
        task_result.total_tokens = sum(s.tokens_used for s in task_result.steps)
        task_result.total_cost_cny = sum(s.cost_cny for s in task_result.steps)
        task_result.privacy_violations = sum(1 for s in task_result.steps if s.privacy_violation)

        metrics = compute_metrics(task_result, task.max_steps)
        score = compute_composite_score(metrics)

        return {
            "task_result": task_result,
            "metrics": metrics,
            "score": score,
            "trajectory": [
                {"step_id": s.step_id, "success": s.success, "tokens": s.tokens_used,
                 "elapsed": s.elapsed_seconds}
                for s in task_result.steps
            ],
        }


# ===========================================================================
# Registry
# ===========================================================================

BASELINE_REGISTRY: Dict[str, type] = {
    "StaticPipeline": StaticPipeline,
    "FullContextMultiAgent": FullContextMultiAgent,
    "FixedDAG": FixedDAG,
    "PlainSingleAgent": PlainSingleAgent,
}


def get_baseline(name: str, seed: int = 42):
    """Instantiate a baseline by name."""
    cls = BASELINE_REGISTRY.get(name)
    if cls is None:
        raise ValueError(f"Unknown baseline: {name}. Available: {list(BASELINE_REGISTRY)}")
    return cls(seed=seed)


def run_all_baselines(task: Task, seed: int = 42) -> Dict[str, Dict]:
    """Run all 4 baselines on a single task, return {name: result_dict}."""
    results = {}
    for name in BASELINE_REGISTRY:
        baseline = get_baseline(name, seed=seed)
        results[name] = baseline.run_task(task)
        logger.info(f"  {name}: score={results[name]['score']:.4f}")
    return results
