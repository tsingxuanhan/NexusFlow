"""
LHAB-NF Runner
===============
Executes benchmark tasks and collects metrics.
Supports mock mode (testing) and real mode (NexusFlow server).
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

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lhab_nf.task_schema import Task, Step, Perturbation, PerturbationType
from lhab_nf.scorer import TaskResult, StepResult, MetricScores, compute_metrics, compute_composite_score, format_report

logger = logging.getLogger("lhab_nf.runner")


class PerturbationInjector:
    """
    Injects perturbations into task execution.
    7 types: device_offline, network_timeout, tool_failure, requirement_change,
    data_conflict, low_quality_output, memory_injection
    """
    
    def __init__(self, config: Dict = None):
        self.config = config or {}
        self.history: List[Dict] = []
        self.active_perturbations: List[Dict] = []
    
    def inject(self, perturbation: Perturbation, context: Dict) -> Dict:
        """Inject perturbation and return effect."""
        timestamp = datetime.now().isoformat()
        
        effect = {
            "perturbation_id": f"pert_{len(self.history)}",
            "type": perturbation.type.value,
            "triggered_at": timestamp,
            "target": perturbation.target,
            "trigger_step": perturbation.trigger_at_step,
            "params": perturbation.params,
        }
        
        if perturbation.type == PerturbationType.DEVICE_OFFLINE:
            effect["effect"] = "device_unavailable"
            effect["duration_seconds"] = perturbation.params.get("duration_seconds", 30)
            effect["blocking"] = True
            
        elif perturbation.type == PerturbationType.NETWORK_TIMEOUT:
            effect["effect"] = "api_timeout"
            effect["timeout_seconds"] = perturbation.params.get("timeout_seconds", 60)
            effect["blocking"] = True
            
        elif perturbation.type == PerturbationType.TOOL_FAILURE:
            effect["effect"] = "tool_error"
            effect["error"] = perturbation.params.get("error", "unknown_error")
            effect["blocking"] = True
            
        elif perturbation.type == PerturbationType.REQUIREMENT_CHANGE:
            effect["effect"] = "scope_change"
            effect["new_requirement"] = perturbation.params.get("new_requirement", "")
            effect["blocking"] = False
            
        elif perturbation.type == PerturbationType.DATA_CONFLICT:
            effect["effect"] = "data_inconsistency"
            effect["description"] = perturbation.params.get("description", "")
            effect["blocking"] = False
            
        elif perturbation.type == PerturbationType.LOW_QUALITY_OUTPUT:
            effect["effect"] = "degraded_output"
            effect["error_type"] = perturbation.params.get("error_type", "generic")
            effect["blocking"] = False
            
        elif perturbation.type == PerturbationType.MEMORY_INJECTION:
            effect["effect"] = "memory_pollution_attempt"
            effect["payload"] = perturbation.params.get("payload", "")
            effect["blocking"] = False
        
        effect["expected_recovery"] = perturbation.expected_recovery
        self.history.append(effect)
        self.active_perturbations.append(effect)
        
        logger.info(f"Perturbation injected: {effect['perturbation_id']} ({effect['type']})")
        return effect
    
    def resolve(self, perturbation_id: str, success: bool = True) -> Dict:
        """Mark perturbation as resolved."""
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
    Mock mode: simulates for testing.
    Real mode: connects to server at port 8900.
    """
    
    def __init__(self, mode: str = "mock", config: Dict = None):
        self.mode = mode
        self.config = config or {}
        self.execution_log: List[Dict] = []
        
        if mode == "real":
            from lhab_nf.agent_adapter import NexusFlowRealAdapter
            self.real_adapter = NexusFlowRealAdapter(config=config)
        else:
            self.real_adapter = None
    
    def execute_step(self, step: Step, context: Dict) -> StepResult:
        """Execute step and return StepResult."""
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
        """Mock execution for testing."""
        import random
        
        success_prob = 0.85
        if context.get("active_perturbation") and context["active_perturbation"].get("blocking"):
            success_prob = 0.3
        
        success = random.random() < success_prob
        
        return StepResult(
            step_id=step.id,
            success=success,
            output={"action": "completed" if success else "failed", "summary": f"Mock output"},
            error=None if success else f"Simulated failure",
            tokens_used=random.randint(500, 3000),
            cost_cny=random.uniform(0.001, 0.01),
            agent_role=step.agent_role,
            device_used=step.device_preference,
            privacy_violation=False,
        )
    
    def _real_execute(self, step: Step, context: Dict) -> StepResult:
        """Real execution via NexusFlow server."""
        if not self.real_adapter:
            raise RuntimeError("Real adapter not initialized")
        
        result_dict = self.real_adapter.execute_step(step, context)
        
        return StepResult(
            step_id=result_dict["step_id"],
            success=result_dict["success"],
            output=result_dict.get("output"),
            error=result_dict.get("error"),
            tokens_used=result_dict.get("tokens_used", 0),
            cost_cny=result_dict.get("cost_cny", 0.0),
            agent_role=result_dict.get("agent_role", step.agent_role),
            device_used=result_dict.get("device_used", step.device_preference),
            privacy_violation=result_dict.get("privacy_violation", False),
        )


class LHABRunner:
    """
    Main benchmark runner.
    Orchestrates task execution, perturbation injection, metric collection.
    """
    
    def __init__(self, mode: str = "mock", output_dir: str = "results/"):
        self.mode = mode
        self.output_dir = output_dir
        self.agent_adapter = NexusFlowAgentAdapter(mode=mode)
        self.perturbation_injector = PerturbationInjector()
        
        os.makedirs(output_dir, exist_ok=True)
    
    def load_task(self, task_path: str) -> Task:
        """Load task from YAML."""
        with open(task_path, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f)
        return Task.from_dict(data)
    
    def run_task(self, task: Task) -> Dict:
        """Execute task and return results."""
        logger.info(f"Running task: {task.id} ({task.difficulty.value})")
        
        task_result = TaskResult(task_id=task.id)
        start_time = time.time()
        
        step_outputs: Dict[str, Any] = {}
        step_map = {s.id: s for s in task.steps}
        executed = set()
        pending = set(s.id for s in task.steps)
        
        while pending:
            ready = [s for s in (step_map[pid] for pid in list(pending))
                    if all(d in executed for d in s.input_deps)]
            
            if not ready:
                logger.error(f"Deadlock: no ready steps. Pending: {pending}")
                break
            
            for step in ready:
                context = {"step_id": step.id, "step_outputs": step_outputs, "active_perturbation": None}
                
                for pert in task.perturbations:
                    if pert.trigger_at_step == step.id:
                        effect = self.perturbation_injector.inject(pert, context)
                        context["active_perturbation"] = effect
                        task_result.perturbations_triggered += 1
                
                result = self.agent_adapter.execute_step(step, context)
                task_result.steps.append(result)
                
                if result.success:
                    step_outputs[step.id] = result.output
                    executed.add(step.id)
                    if context["active_perturbation"]:
                        task_result.perturbations_recovered += 1
                        self.perturbation_injector.resolve(
                            context["active_perturbation"]["perturbation_id"], success=True
                        )
                
                pending.discard(step.id)
        
        task_result.total_elapsed_seconds = time.time() - start_time
        task_result.total_tokens = sum(s.tokens_used for s in task_result.steps)
        task_result.total_cost_cny = sum(s.cost_cny for s in task_result.steps)
        task_result.privacy_violations = sum(1 for s in task_result.steps if s.privacy_violation)
        
        metrics = compute_metrics(task_result, task.max_steps)
        score = compute_composite_score(metrics)
        report = format_report(task.id, metrics, score)
        
        self._save_results(task, task_result, metrics, score)
        
        return {"task_result": task_result, "metrics": metrics, "score": score, "report": report}
    
    def run_suite(self, task_dir: str, difficulty: str = None) -> List[Dict]:
        """Run all tasks in directory."""
        results = []
        task_files = sorted(Path(task_dir).glob("*.yaml"))
        if difficulty:
            task_files = [f for f in task_files if f"-{difficulty.upper()}-" in f.stem]
        
        logger.info(f"Running suite: {len(task_files)} tasks")
        
        for task_file in task_files:
            task = self.load_task(str(task_file))
            result = self.run_task(task)
            results.append(result)
        
        scores = [r["score"] for r in results]
        avg_score = sum(scores) / len(scores) if scores else 0
        logger.info(f"Suite complete: avg_score={avg_score:.4f}")
        
        return results
    
    def _save_results(self, task: Task, task_result: TaskResult, metrics: MetricScores, score: float):
        """Save results to output directory."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        report_path = os.path.join(self.output_dir, f"{task.id}_{timestamp}_report.md")
        with open(report_path, 'w', encoding='utf-8') as f:
            f.write(format_report(task.id, metrics, score))
        
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
        }
        
        json_path = os.path.join(self.output_dir, f"{task.id}_{timestamp}_metrics.json")
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(metrics_dict, f, ensure_ascii=False, indent=2)
        
        logger.info(f"Results saved: {report_path}")


def main():
    """CLI entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(description="LHAB-NF Benchmark Runner")
    parser.add_argument("task", nargs="?", help="Task YAML or directory")
    parser.add_argument("--mode", default="mock", choices=["mock", "real"])
    parser.add_argument("--difficulty", choices=["easy", "medium", "hard"])
    parser.add_argument("--output", default="results/lhab_nf/")
    parser.add_argument("--suite", action="store_true")
    parser.add_argument("--server-url", default="http://localhost:8900")
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
        print("No task specified. Run with --suite or specify a task YAML.")


if __name__ == "__main__":
    main()
