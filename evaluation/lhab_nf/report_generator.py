"""
LHAB-NF Report Generator
==========================
Generates comprehensive Markdown analysis reports from benchmark results.

Reports include:
  1. NexusFlow vs 4 baselines comparison table
  2. Statistical tests (t-test + Cohen's d effect size)
  3. Cost analysis (per-task tokens, time, API calls)
  4. Failure analysis (Top-5 failure modes)
  5. Recovery analysis (by perturbation type)

Usage:
  python report_generator.py --results-dir results/
  python report_generator.py --results-dir results/ --output report.md
"""

import os
import sys
import json
import math
import logging
import argparse
import statistics
from datetime import datetime
from typing import List, Dict, Any, Optional, Tuple
from pathlib import Path
from collections import Counter, defaultdict

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logger = logging.getLogger("lhab_nf.report")


# ---------------------------------------------------------------------------
# Statistical helpers
# ---------------------------------------------------------------------------

def welch_t_test(
    group_a: List[float], group_b: List[float]
) -> Dict[str, float]:
    """
    Welch's t-test for unequal variances.

    Returns:
        t_statistic, p_value (two-tailed), df (degrees of freedom)
    """
    n1, n2 = len(group_a), len(group_b)
    if n1 < 2 or n2 < 2:
        return {"t_stat": 0.0, "p_value": 1.0, "df": 0}

    mean1 = statistics.mean(group_a)
    mean2 = statistics.mean(group_b)
    var1 = statistics.variance(group_a)
    var2 = statistics.variance(group_b)

    se = math.sqrt(var1 / n1 + var2 / n2) if (var1 / n1 + var2 / n2) > 0 else 1e-9
    t_stat = (mean1 - mean2) / se

    # Welch–Satterthwaite degrees of freedom
    num = (var1 / n1 + var2 / n2) ** 2
    denom = (var1 / n1) ** 2 / (n1 - 1) + (var2 / n2) ** 2 / (n2 - 1)
    df = num / denom if denom > 0 else 1

    # Approximate p-value using normal approximation for large df
    p_value = 2 * (1 - _normal_cdf(abs(t_stat)))

    return {"t_stat": round(t_stat, 4), "p_value": round(p_value, 4), "df": round(df, 2)}


def cohens_d(group_a: List[float], group_b: List[float]) -> float:
    """Cohen's d effect size."""
    n1, n2 = len(group_a), len(group_b)
    if n1 < 2 or n2 < 2:
        return 0.0
    mean1 = statistics.mean(group_a)
    mean2 = statistics.mean(group_b)
    var1 = statistics.variance(group_a)
    var2 = statistics.variance(group_b)
    pooled_std = math.sqrt(((n1 - 1) * var1 + (n2 - 1) * var2) / (n1 + n2 - 2))
    if pooled_std == 0:
        return 0.0
    return round((mean1 - mean2) / pooled_std, 4)


def _normal_cdf(x: float) -> float:
    """Approximate standard normal CDF."""
    return 0.5 * (1 + math.erf(x / math.sqrt(2)))


def _interpret_effect_size(d: float) -> str:
    """Interpret Cohen's d magnitude."""
    abs_d = abs(d)
    if abs_d < 0.2:
        return "negligible"
    elif abs_d < 0.5:
        return "small"
    elif abs_d < 0.8:
        return "medium"
    else:
        return "large"


# ---------------------------------------------------------------------------
# Report Generator
# ---------------------------------------------------------------------------

class ReportGenerator:
    """
    Generates comprehensive Markdown benchmark reports.
    """

    def __init__(self, results_dir: str):
        self.results_dir = results_dir
        self.summary_path = os.path.join(results_dir, "summary.json")
        self.summary: Dict = {}
        self.runs: List[Dict] = []

    def load_data(self) -> None:
        """Load summary.json and reconstruct per-run data."""
        if not os.path.exists(self.summary_path):
            raise FileNotFoundError(f"Summary not found: {self.summary_path}")

        with open(self.summary_path, "r", encoding="utf-8") as f:
            self.summary = json.load(f)

        # Reconstruct per-run data from individual metrics.json files
        self.runs = []
        for system_name, system_data in self.summary.get("systems", {}).items():
            sys_dir = os.path.join(self.results_dir, system_name)
            if not os.path.isdir(sys_dir):
                continue
            for task_id in sorted(os.listdir(sys_dir)):
                task_dir = os.path.join(sys_dir, task_id)
                if not os.path.isdir(task_dir):
                    continue
                for seed_str in os.listdir(task_dir):
                    metrics_path = os.path.join(task_dir, seed_str, "metrics.json")
                    failures_path = os.path.join(task_dir, seed_str, "failures.json")
                    pert_path = os.path.join(task_dir, seed_str, "perturbation_recovery.json")

                    if os.path.exists(metrics_path):
                        with open(metrics_path, "r", encoding="utf-8") as f:
                            m = json.load(f)
                        run = {"system": system_name, **m}

                        if os.path.exists(failures_path):
                            with open(failures_path, "r", encoding="utf-8") as f:
                                run["failures"] = json.load(f)
                        else:
                            run["failures"] = []

                        if os.path.exists(pert_path):
                            with open(pert_path, "r", encoding="utf-8") as f:
                                run["perturbation_recovery"] = json.load(f)
                        else:
                            run["perturbation_recovery"] = {}

                        self.runs.append(run)

        logger.info(f"Loaded {len(self.runs)} runs from {self.results_dir}")

    def generate(self, output_path: str = None) -> str:
        """Generate full Markdown report and return as string."""
        if not self.summary:
            self.load_data()

        sections = [
            self._header(),
            self._comparison_table(),
            self._statistical_tests(),
            self._cost_analysis(),
            self._failure_analysis(),
            self._recovery_analysis(),
            self._per_task_breakdown(),
            self._footer(),
        ]

        report = "\n\n".join(sections)

        if output_path:
            os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
            with open(output_path, "w", encoding="utf-8") as f:
                f.write(report)
            logger.info(f"Report saved: {output_path}")

        return report

    # ---- Section builders ----

    def _header(self) -> str:
        """Report header."""
        meta = self.summary.get("metadata", {})
        return (
            "# LHAB-NF Benchmark Report\n\n"
            f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}  \n"
            f"**Mode:** {meta.get('mode', 'N/A')}  \n"
            f"**Seeds:** {meta.get('num_seeds', 'N/A')} ({meta.get('seeds', [])})  \n"
            f"**Systems:** {len(self.summary.get('systems', {}))}  \n"
            f"**Tasks:** 9 (3 categories × 3 difficulties)"
        )

    def _comparison_table(self) -> str:
        """Main comparison table: NexusFlow vs all baselines."""
        systems = self.summary.get("systems", {})
        if not systems:
            return "## Comparison\n\n_No data available._"

        lines = [
            "## System Comparison",
            "",
            "| System | Score ↑ | TCR ↑ | SSR ↑ | Recovery ↑ | Tokens ↓ | Cost (¥) ↓ | Latency (s) ↓ | Privacy ↓ |",
            "|--------|--------:|------:|------:|-----------:|---------:|-----------:|--------------:|----------:|",
        ]

        # Sort: NexusFlow first, then by score desc
        sorted_names = sorted(systems.keys(), key=lambda n: (0 if n == "NexusFlow" else 1, -systems[n]["avg_score"]))

        for name in sorted_names:
            d = systems[name]
            marker = "🏆" if name == "NexusFlow" else ""
            lines.append(
                f"| {marker} **{name}** "
                f"| {d['avg_score']:.4f} ± {d['std_score']:.4f} "
                f"| {d['avg_tcr']:.2%} "
                f"| {d['avg_ssr']:.2%} "
                f"| {d['avg_recovery_rate']:.2%} "
                f"| {d['avg_tokens']:.0f} "
                f"| {d['avg_cost_cny']:.6f} "
                f"| {d['avg_latency_s']:.3f} "
                f"| {d['total_privacy_violations']} |"
            )

        return "\n".join(lines)

    def _statistical_tests(self) -> str:
        """Statistical significance tests."""
        systems = self.summary.get("systems", {})
        if "NexusFlow" not in systems or len(systems) < 2:
            return "## Statistical Tests\n\n_Insufficient data for statistical analysis._"

        # Collect per-run scores for each system
        system_scores: Dict[str, List[float]] = defaultdict(list)
        for run in self.runs:
            system_scores[run["system"]].append(run["score"])

        nf_scores = system_scores.get("NexusFlow", [])
        if not nf_scores:
            return "## Statistical Tests\n\n_No NexusFlow scores found._"

        lines = [
            "## Statistical Tests",
            "",
            "NexusFlow vs each baseline (Welch's t-test, two-tailed):",
            "",
            "| Comparison | Δ Score | t-stat | p-value | Cohen's d | Effect | Significant? |",
            "|------------|--------:|-------:|--------:|----------:|--------|--------------|",
        ]

        for name in sorted(systems.keys()):
            if name == "NexusFlow":
                continue
            baseline_scores = system_scores.get(name, [])
            if not baseline_scores:
                continue

            delta = statistics.mean(nf_scores) - statistics.mean(baseline_scores)
            t_result = welch_t_test(nf_scores, baseline_scores)
            d = cohens_d(nf_scores, baseline_scores)
            effect = _interpret_effect_size(d)
            sig = "✅ Yes" if t_result["p_value"] < 0.05 else "❌ No"

            lines.append(
                f"| NexusFlow vs {name} "
                f"| {delta:+.4f} "
                f"| {t_result['t_stat']:.4f} "
                f"| {t_result['p_value']:.4f} "
                f"| {d:.4f} "
                f"| {effect} "
                f"| {sig} |"
            )

        return "\n".join(lines)

    def _cost_analysis(self) -> str:
        """Cost analysis: tokens, time, API calls per task."""
        systems = self.summary.get("systems", {})
        if not systems:
            return "## Cost Analysis\n\n_No data._"

        lines = [
            "## Cost Analysis",
            "",
            "### Per-System Cost Summary",
            "",
            "| System | Avg Tokens | Avg Cost (¥) | Avg Latency (s) | Avg API Calls |",
            "|--------|-----------:|-------------:|----------------:|--------------:|",
        ]

        for name in sorted(systems.keys()):
            d = systems[name]
            lines.append(
                f"| {name} "
                f"| {d['avg_tokens']:.0f} "
                f"| {d['avg_cost_cny']:.6f} "
                f"| {d['avg_latency_s']:.3f} "
                f"| {d.get('avg_api_calls', 'N/A')} |"
            )

        # Per-task breakdown for NexusFlow
        nf_runs = [r for r in self.runs if r["system"] == "NexusFlow"]
        if nf_runs:
            lines.extend([
                "",
                "### NexusFlow Per-Task Cost",
                "",
                "| Task | Avg Tokens | Avg Cost (¥) | Avg Latency (s) |",
                "|------|-----------:|-------------:|----------------:|",
            ])

            task_ids = sorted(set(r["task_id"] for r in nf_runs))
            for tid in task_ids:
                tid_runs = [r for r in nf_runs if r["task_id"] == tid]
                avg_tok = statistics.mean([r["total_tokens"] for r in tid_runs])
                avg_cost = statistics.mean([r["total_cost_cny"] for r in tid_runs])
                avg_lat = statistics.mean([r["end_to_end_latency"] for r in tid_runs])
                lines.append(f"| {tid} | {avg_tok:.0f} | {avg_cost:.6f} | {avg_lat:.3f} |")

        return "\n".join(lines)

    def _failure_analysis(self) -> str:
        """Top-5 failure mode analysis."""
        all_failures: List[Dict] = []
        for run in self.runs:
            for f in run.get("failures", []):
                f["system"] = run["system"]
                f["task_id"] = run["task_id"]
                all_failures.append(f)

        if not all_failures:
            return "## Failure Analysis\n\n_No failures recorded._"

        # Categorize failures by error pattern
        error_counter: Counter = Counter()
        error_by_system: Dict[str, Counter] = defaultdict(Counter)
        error_details: Dict[str, List[Dict]] = defaultdict(list)

        for f in all_failures:
            error_msg = f.get("error", "unknown")
            # Simplify error to pattern
            pattern = self._classify_error(error_msg)
            error_counter[pattern] += 1
            error_by_system[f["system"]][pattern] += 1
            if len(error_details[pattern]) < 3:
                error_details[pattern].append(f)

        top5 = error_counter.most_common(5)

        lines = [
            "## Failure Analysis",
            "",
            f"**Total failures:** {len(all_failures)}",
            "",
            "### Top-5 Failure Modes",
            "",
            "| Rank | Failure Mode | Count | % of Total |",
            "|------|-------------|------:|-----------:|",
        ]

        for i, (pattern, count) in enumerate(top5, 1):
            pct = count / len(all_failures) * 100
            lines.append(f"| {i} | {pattern} | {count} | {pct:.1f}% |")

        # Per-system failure distribution
        lines.extend([
            "",
            "### Failure Distribution by System",
            "",
            "| System | " + " | ".join(p for p, _ in top5) + " |",
            "|--------|" + "|".join(["---:"] * len(top5)) + "|",
        ])

        for system_name in sorted(set(r["system"] for r in self.runs)):
            row = f"| {system_name} "
            for pattern, _ in top5:
                cnt = error_by_system[system_name].get(pattern, 0)
                row += f"| {cnt} "
            row += "|"
            lines.append(row)

        return "\n".join(lines)

    def _recovery_analysis(self) -> str:
        """Recovery analysis by perturbation type."""
        # Collect per-perturbation-type recovery rates
        pert_data: Dict[str, Dict[str, List[float]]] = defaultdict(lambda: defaultdict(list))

        for run in self.runs:
            system = run["system"]
            for ptype, rate in run.get("perturbation_recovery", {}).items():
                pert_data[system][ptype].append(rate)

        if not pert_data:
            return "## Recovery Analysis\n\n_No perturbation recovery data._"

        lines = [
            "## Recovery Analysis by Perturbation Type",
            "",
            "| Perturbation Type | " + " | ".join(sorted(pert_data.keys())) + " |",
            "|-------------------|" + "|".join(["---:"] * len(pert_data)) + "|",
        ]

        # Get all perturbation types
        all_pert_types = sorted(set(
            pt for sys_data in pert_data.values() for pt in sys_data
        ))

        for pt in all_pert_types:
            row = f"| {pt} "
            for system_name in sorted(pert_data.keys()):
                vals = pert_data[system_name].get(pt, [])
                if vals:
                    avg = statistics.mean(vals)
                    row += f"| {avg:.2%} "
                else:
                    row += "| N/A "
            row += "|"
            lines.append(row)

        # Overall recovery summary
        lines.extend([
            "",
            "### Overall Recovery Rates",
            "",
            "| System | Avg Recovery Rate |",
            "|--------|------------------:|",
        ])

        systems = self.summary.get("systems", {})
        for name in sorted(systems.keys()):
            rate = systems[name]["avg_recovery_rate"]
            lines.append(f"| {name} | {rate:.2%} |")

        return "\n".join(lines)

    def _per_task_breakdown(self) -> str:
        """Per-task score breakdown."""
        systems = self.summary.get("systems", {})
        if not systems:
            return "## Per-Task Breakdown\n\n_No data._"

        # Collect all task IDs
        all_task_ids = set()
        for sys_data in systems.values():
            all_task_ids.update(sys_data.get("per_task_avg_score", {}).keys())

        if not all_task_ids:
            return "## Per-Task Breakdown\n\n_No per-task data._"

        lines = [
            "## Per-Task Score Breakdown",
            "",
            "| Task | " + " | ".join(sorted(systems.keys())) + " |",
            "|------|" + "|".join(["---:"] * len(systems)) + "|",
        ]

        for tid in sorted(all_task_ids):
            row = f"| {tid} "
            for sys_name in sorted(systems.keys()):
                score = systems[sys_name].get("per_task_avg_score", {}).get(tid, 0)
                row += f"| {score:.4f} "
            row += "|"
            lines.append(row)

        return "\n".join(lines)

    def _footer(self) -> str:
        """Report footer."""
        return (
            "---\n\n"
            "*Report generated by LHAB-NF Report Generator*  \n"
            f"*{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*"
        )

    # ---- Helpers ----

    @staticmethod
    def _classify_error(error_msg: str) -> str:
        """Classify error message into a failure pattern."""
        if not error_msg:
            return "Unknown error"
        msg_lower = error_msg.lower()
        if "upstream" in msg_lower or "dependency" in msg_lower:
            return "Upstream dependency failure"
        elif "simulated" in msg_lower or "mock" in msg_lower:
            return "Simulated step failure"
        elif "skipped" in msg_lower:
            return "Skipped (cascade)"
        elif "timeout" in msg_lower:
            return "Timeout"
        elif "voted" in msg_lower:
            return "Majority vote failure"
        else:
            return f"Other: {error_msg[:40]}"


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(description="LHAB-NF Report Generator")
    parser.add_argument(
        "--results-dir", default="results/",
        help="Path to benchmark results directory"
    )
    parser.add_argument(
        "--output", default=None,
        help="Output report path (default: results/report.md)"
    )
    parser.add_argument("--verbose", "-v", action="store_true")

    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    )

    output_path = args.output or os.path.join(args.results_dir, "report.md")

    gen = ReportGenerator(args.results_dir)
    report = gen.generate(output_path)
    print(report)


if __name__ == "__main__":
    main()
