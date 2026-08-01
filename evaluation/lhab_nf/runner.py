"""
LHAB-NF Runner
===============
Executes benchmark tasks and collects metrics.
Loads task YAML definitions, runs through NexusFlow agents,
injects perturbations, and produces scored results.
"""

import os
import sys
import json
import time
import yaml
import logging
from datetime import datetime
from typing import List, Dict, Optional, Any
from pathlib import Path

# Add parent to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lhab_nf.task_schema import Task, Step, Perturbation, PerturbationType
from lhab_nf.scorer import TaskResult, StepResult, MetricScores, compute_metrics, compute_composite_score, format_report

logger = logging.getLogger("lhab_nf.runner")


class PerturbationInjector:
    """
    Injects perturbations into task execution.
    
    Supports:
    - device_offline: Simulate device becoming unavailable
    - network_timeout: Simulate API timeout
    - tool_failure: Simulate tool returning error
    - requirement_change: Inject mid-task requirement change
    - data_conflict: Inject conflicting data
    - low_quality_output: Simulate poor agent output
    - memory_injection: Attempt to pollute memory
    """
    
    def __init__(self, config: Dict = None):
        self.config = config or {}
        self.history: List[Dict] = []
        self.active_perturbations: List[Dict] = []
    
    def inject(self, perturbation: Perturbation, context: Dict) -> Dict:
        """
        Inject a perturbation and return its effect.
        
        Args:
            perturbation: The perturbation to inject
            context: Current execution context (step_id, agent, device, etc.)
        
        Returns:
            Dict with: triggered, effect, recovery_action
        """
        timestamp = datetime.now().isoformat()
        
        effect = {
            "perturbation_id": f"pert_{len(self.history)}",
            "type": perturbation.type.value,
            "triggered_at": timestamp,
            "target": perturbation.target,
            "trigger_step": perturbation.trigger_at_step,
            "params": perturbation.params,
        }
        
        # Determine effect based on type
        if perturbation.type == PerturbationType.DEVICE_OFFLINE:
            effect["effect"] = "device_unavailable"
            effect["duration_seconds"] = perturbation.params.get("duration_seconds", 30)
            effect["recovery_action"] = "migrate_to_alternative_device"
            effect["blocking"] = True
            
        elif perturbation.type == PerturbationType.NETWORK_TIMEOUT:
            effect["effect"] = "api_timeout"
            effect["timeout_seconds"] = perturbation.params.get("timeout_seconds", 60)
            effect["recovery_action"] = "retry_with_backoff"
            effect["blocking"] = True
            
        elif perturbation.type == PerturbationType.TOOL_FAILURE:
            effect["effect"] = "tool_error"
            effect["error"] = perturbation.params.get("error", "unknown_error")
            effect["recovery_action"] = "try_alternative_tool"
            effect["blocking"] = True
            
        elif perturbation.type == PerturbationType.REQUIREMENT_CHANGE:
            effect["effect"] = "scope_change"
            effect["new_requirement"] = perturbation.params.get("new_requirement", "")
            effect["recovery_action"] = "replan_partial"
            effect["blocking"] = False  # Doesn't block current step
            
        elif perturbation.type == PerturbationType.DATA_CONFLICT:
            effect["effect"] = "data_inconsistency"
            effect["description"] = perturbation.params.get("description", "")
            effect["recovery_action"] = "cross_validate_and_select"
            effect["blocking"] = False
            
        elif perturbation.type == PerturbationType.LOW_QUALITY_OUTPUT:
            effect["effect"] = "degraded_output"
            effect["error_type"] = perturbation.params.get("error_type", "generic")
            effect["description"] = perturbation.params.get("description", "")
            effect["recovery_action"] = "reviewer_reject_and_retry"
            effect["blocking"] = False
            
        elif perturbation.type == PerturbationType.MEMORY_INJECTION:
            effect["effect"] = "memory_pollution_attempt"
            effect["payload"] = perturbation.params.get("payload", "")
            effect["recovery_action"] = "memory_validator_reject"
            effect["blocking"] = False
        
        effect["expected_recovery"] = perturbation.expected_recovery
        self.history.append(effect)
        self.active_perturbations.append(effect)
        
        logger.info(f"Perturbation injected: {effect['perturbation_id']} ({effect['type']})")
        return effect
    
    def resolve(self, perturbation_id: str, success: bool = True) -> Dict:
        """Mark a perturbation as resolved."""
        for p in self.active_perturbations:
            if p["perturbation_id"] == perturbation_id:
                p["resolved_at"] = datetime.now().isoformat()
                p["recovery_success"] = success
                self.active_perturbations.remove(p)
                return p
        return {"error": f"Perturbation {perturbation_id} not found"}
    
    def get_stats(self) -> Dict:
        """Get perturbation statistics."""
        total = len(self.history)
        resolved = sum(1 for p in self.history if "resolved_at" in p)
        successful = sum(1 for p in self.history if p.get("recovery_success", False))
        
        return {
            "total_triggered": total,
            "total_resolved": resolved,
            "recovery_success_rate": successful / max(1, resolved),
            "active_count": len(self.active_perturbations),
        }


class NexusFlowAgentAdapter:
    """
    Adapter to run steps through NexusFlow agents.
    
    In mock mode: simulates agent responses for framework testing.
    In real mode: connects to actual NexusFlow agent system.
    """
    
    def __init__(self, mode: str = "mock", config: Dict = None):
        self.mode = mode
        self.config = config or {}
        self.execution_log: List[Dict] = []
    
    def execute_step(self, step: Step, context: Dict) -> StepResult:
        """
        Execute a single step through the agent system.
        
        Args:
            step: The step to execute
            context: Execution context including previous step outputs
        
        Returns:
            StepResult with execution details
        """
        start_time = time.time()
        
        if self.mode == "mock":
            result = self._mock_execute(step, context)
        else:
            result = self._real_execute(step, context)
        
        elapsed = time.time() - start_time
        result.elapsed_seconds = elapsed
        
        self.execution_log.append({
            "step_id": step.id,
            "agent_role": step.agent_role,
            "success": result.success,
            "elapsed": elapsed,
            "tokens": result.tokens_used,
        })
        
        return result
    
    def _mock_execute(self, step: Step, context: Dict) -> StepResult:
        """Mock execution for framework testing."""
        import random
        
        # Simulate realistic execution
        # Most steps succeed, some may fail based on perturbations
        success_prob = 0.85  # Base success rate
        
        # Check if there's an active perturbation affecting this step
        perturbation_active = context.get("active_perturbation")
        if perturbation_active:
            if perturbation_active["blocking"]:
                success_prob = 0.3  # Reduced when perturbation is active
            else:
                success_prob = 0.7
        
        success = random.random() < success_prob
        
        return StepResult(
            step_id=step.id,
            success=success,
            output={
                "action": "completed" if success else "failed",
                "summary": f"Mock output for {step.description[:50]}",
                "data_quality": random.uniform(0.6, 0.95) if success else 0.0,
            },
            error=None if success else f"Simulated failure in {step.id}",
            tokens_used=random.randint(500, 3000),
            cost_cny=random.uniform(0.001, 0.01),
            agent_role=step.agent_role,
            device_used=step.device_preference,
            privacy_violation=False,
        )
    
    def _real_execute(self, step: Step, context: Dict) -> StepResult:
        """
        Real execution through NexusFlow agents.
        
        This connects to the actual NexusFlow server (port 8900)
        and dispatches the step to the appropriate agent.
        """
        # TODO: Implement real execution
        # This would:
        # 1. POST to /api/tasks to create a task
        # 2. Route to the appropriate agent via AGENT_ID_MAP
        # 3. Execute the step with the agent
        # 4. Collect the output
        
        raise NotImplementedError(
            "Real execution mode not yet implemented. "
            "Use --mock flag or set mode='mock' for testing."
        )


class LHABRunner:
    """
    Main benchmark runner.
    
    Orchestrates task execution, perturbation injection,
    and metric collection.
    """
    
    def __init__(self, mode: str = "mock", output_dir: str = "results/"):
        self.mode = mode
        self.output_dir = output_dir
        self.agent_adapter = NexusFlowAgentAdapter(mode=mode)
        self.perturbation_injector = PerturbationInjector()
        
        os.makedirs(output_dir, exist_ok=True)
    
    def load_task(self, task_path: str) -> Task:
        """Load a task definition from YAML."""
        with open(task_path, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f)
        return Task.from_dict(data)
    
    def run_task(self, task: Task) -> Dict:
        """
        Execute a complete task and return results.
        
        Returns dict with:
        - task_result: TaskResult object
        - metrics: MetricScores
        - score: composite score
        - report: formatted report string
        """
        logger.info(f"Running task: {task.id} ({task.difficulty.value})")
        
        task_result = TaskResult(task_id=task.id)
        start_time = time.time()
        
        # Build dependency graph
        step_outputs: Dict[str, Any] = {}
        step_map = {s.id: s for s in task.steps}
        
        # Execute steps in dependency order
        executed = set()
        pending = set(s.id for s in task.steps)
        
        while pending:
            # Find steps whose dependencies are met
            ready = []
            for step_id in pending:
                step = step_map[step_id]
                deps_met = all(d in executed for d in step.input_deps)
                if deps_met:
                    ready.append(step)
            
            if not ready:
                logger.error(f"Deadlock: no ready steps. Pending: {pending}")
                break
            
            for step in ready:
                # Check if perturbation should fire
                context = {
                    "step_id": step.id,
                    "step_outputs": step_outputs,
                    "active_perturbation": None,
                }
                
                for pert in task.perturbations:
                    if pert.trigger_at_step == step.id:
                        effect = self.perturbation_injector.inject(pert, context)
                        context["active_perturbation"] = effect
                        task_result.perturbations_triggered += 1
                
                # Execute step
                result = self.agent_adapter.execute_step(step, context)
                task_result.steps.append(result)
                
                if result.success:
                    step_outputs[step.id] = result.output
                    executed.add(step.id)
                    
                    # Check if perturbation was recovered
                    if context["active_perturbation"]:
                        task_result.perturbations_recovered += 1
                        self.perturbation_injector.resolve(
                            context["active_perturbation"]["perturbation_id"],
                            success=True
                        )
                else:
                    # Step failed - attempt recovery
                    logger.warning(f"Step {step.id} failed: {result.error}")
                    # In real mode, would trigger retry/fallback logic
                
                pending.discard(step.id)
        
        # Finalize
        task_result.total_elapsed_seconds = time.time() - start_time
        task_result.total_tokens = sum(s.tokens_used for s in task_result.steps)
        task_result.total_cost_cny = sum(s.cost_cny for s in task_result.steps)
        task_result.privacy_violations = sum(1 for s in task_result.steps if s.privacy_violation)
        
        # Compute metrics
        metrics = compute_metrics(task_result, task.max_steps)
        score = compute_composite_score(metrics)
        report = format_report(task.id, metrics, score)
        
        # Save results
        self._save_results(task, task_result, metrics, score)
        
        return {
            "task_result": task_result,
            "metrics": metrics,
            "score": score,
            "report": report,
        }
    
    def run_suite(self, task_dir: str, difficulty: str = None) -> List[Dict]:
        """Run all tasks in a directory."""
        results = []
        
        task_files = sorted(Path(task_dir).glob("*.yaml"))
        if difficulty:
            task_files = [f for f in task_files if f"-{difficulty.upper()}-" in f.stem]
        
        logger.info(f"Running suite: {len(task_files)} tasks")
        
        for task_file in task_files:
            task = self.load_task(str(task_file))
            result = self.run_task(task)
            results.append(result)
        
        # Summary
        scores = [r["score"] for r in results]
        avg_score = sum(scores) / len(scores) if scores else 0
        
        logger.info(f"Suite complete: avg_score={avg_score:.4f}")
        
        return results
    
    def _save_results(self, task: Task, task_result: TaskResult, 
                      metrics: MetricScores, score: float):
        """Save results to output directory."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Save report
        report_path = os.path.join(self.output_dir, f"{task.id}_{timestamp}_report.md")
        with open(report_path, 'w', encoding='utf-8') as f:
            f.write(task_result.report if hasattr(task_result, 'report') else format_report(task.id, metrics, score))
        
        # Save metrics JSON
        metrics_dict = {
            "task_id": task.id,
            "timestamp": timestamp,
            "score": score,
            "perturbation_stats": self.perturbation_injector.get_stats(),
            "metrics": {
                "task_completion_rate": metrics.task_completion_rate,
                "step_success_rate": metrics.step_success_rate,
                "total_tokens": metrics.total_tokens,
                "cost_per_success": metrics.cost_per_success,
                "end_to_end_latency": metrics.end_to_end_latency,
                "privacy_violation_count": metrics.privacy_violation_count,
            },
            "steps": [
                {
                    "step_id": s.step_id,
                    "success": s.success,
                    "elapsed": s.elapsed_seconds,
                    "tokens": s.tokens_used,
                }
                for s in task_result.steps
            ],
        }
        
        json_path = os.path.join(self.output_dir, f"{task.id}_{timestamp}_metrics.json")
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(metrics_dict, f, ensure_ascii=False, indent=2)
        
        logger.info(f"Results saved: {report_path}")


def main():
    """CLI entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(description="LHAB-NF Benchmark Runner")
    parser.add_argument("task", nargs="?", help="Task YAML file or directory")
    parser.add_argument("--mode", default="mock", choices=["mock", "real"],
                       help="Execution mode (default: mock)")
    parser.add_argument("--difficulty", choices=["easy", "medium", "hard"],
                       help="Filter tasks by difficulty")
    parser.add_argument("--output", default="results/lhab_nf/",
                       help="Output directory")
    parser.add_argument("--suite", action="store_true",
                       help="Run all tasks in directory")
    parser.add_argument("--verbose", "-v", action="store_true")
    
    args = parser.parse_args()
    
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s"
    )
    
    runner = LHABRunner(mode=args.mode, output_dir=args.output)
    
    if args.suite or (args.task and os.path.isdir(args.task)):
        task_dir = args.task or "evaluation/lhab_nf/tasks"
        results = runner.run_suite(task_dir, difficulty=args.difficulty)
        
        # Print summary
        print("\n" + "="*60)
        print("  LHAB-NF Suite Results")
        print("="*60)
        for r in results:
            task_id = r["task_result"].task_id
            score = r["score"]
            status = "✅" if r["metrics"].task_completion_rate > 0 else "❌"
            print(f"  {status} {task_id:15s}  score={score:.4f}")
        
        avg = sum(r["score"] for r in results) / len(results)
        print(f"\n  Average score: {avg:.4f}")
    
    elif args.task:
        task = runner.load_task(args.task)
        result = runner.run_task(task)
        print(result["report"])
    
    else:
        # Default: run T1-E-001 as demo
        print("No task specified. Running demo task T1-E-001...")
        demo_task = Path("evaluation/lhab_nf/tasks/T1-E-001.yaml")
        if demo_task.exists():
            task = runner.load_task(str(demo_task))
            result = runner.run_task(task)
            print(result["report"])
        else:
            print("Demo task not found. Specify a task file or --suite.")


if __name__ == "__main__":
    main()
