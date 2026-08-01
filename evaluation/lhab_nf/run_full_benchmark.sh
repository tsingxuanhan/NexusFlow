#!/usr/bin/env bash
# =============================================================================
# LHAB-NF Full Benchmark Suite
# =============================================================================
# Usage:
#   # Mock mode - quick validation (3 seeds)
#   ./run_full_benchmark.sh mock 3
#
#   # Real mode - full run (5 seeds, needs server on port 8900)
#   ./run_full_benchmark.sh real 5
#
#   # Generate report only (after a previous run)
#   ./run_full_benchmark.sh report
# =============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RESULTS_DIR="${SCRIPT_DIR}/results"

# Defaults
MODE="${1:-mock}"
SEEDS="${2:-3}"
BASELINES="${3:-all}"
TASK_DIR="${SCRIPT_DIR}/tasks"

echo "============================================================"
echo "  LHAB-NF Full Benchmark Suite"
echo "============================================================"
echo "  Mode:      ${MODE}"
echo "  Seeds:     ${SEEDS}"
echo "  Baselines: ${BASELINES}"
echo "  Tasks:     ${TASK_DIR}"
echo "  Results:   ${RESULTS_DIR}"
echo "============================================================"
echo ""

# ---- Special case: report only ----
if [ "${MODE}" = "report" ]; then
    echo "Generating report from existing results..."
    python "${SCRIPT_DIR}/report_generator.py" \
        --results-dir "${RESULTS_DIR}" \
        --output "${RESULTS_DIR}/report.md"
    echo ""
    echo "Report saved to: ${RESULTS_DIR}/report.md"
    exit 0
fi

# ---- Validate mode ----
if [ "${MODE}" != "mock" ] && [ "${MODE}" != "real" ]; then
    echo "ERROR: Mode must be 'mock', 'real', or 'report'. Got: ${MODE}"
    exit 1
fi

# ---- Validate task directory ----
if [ ! -d "${TASK_DIR}" ]; then
    echo "ERROR: Task directory not found: ${TASK_DIR}"
    exit 1
fi

TASK_COUNT=$(ls "${TASK_DIR}"/*.yaml 2>/dev/null | wc -l)
echo "Found ${TASK_COUNT} task YAMLs"

if [ "${TASK_COUNT}" -eq 0 ]; then
    echo "ERROR: No YAML files found in ${TASK_DIR}"
    exit 1
fi

# ---- Check server for real mode ----
if [ "${MODE}" = "real" ]; then
    echo "Checking NexusFlow server at localhost:8900..."
    if curl -s --connect-timeout 3 http://localhost:8900/api/health > /dev/null 2>&1; then
        echo "  ✅ Server is reachable"
    else
        echo "  ⚠️  Server not reachable at localhost:8900"
        echo "  Continuing in mock mode instead..."
        MODE="mock"
    fi
fi

# ---- Create results directory ----
mkdir -p "${RESULTS_DIR}"

# ---- Run benchmark ----
echo ""
echo "Running comprehensive benchmark..."
echo ""

python "${SCRIPT_DIR}/comprehensive_runner.py" \
    --seeds "${SEEDS}" \
    --mode "${MODE}" \
    --baselines "${BASELINES}" \
    --task-dir "${TASK_DIR}" \
    --output "${RESULTS_DIR}" \
    --verbose

echo ""
echo "============================================================"
echo "  Benchmark complete!"
echo "  Generating report..."
echo "============================================================"
echo ""

# ---- Generate report ----
python "${SCRIPT_DIR}/report_generator.py" \
    --results-dir "${RESULTS_DIR}" \
    --output "${RESULTS_DIR}/report.md"

echo ""
echo "============================================================"
echo "  All done!"
echo "  Results: ${RESULTS_DIR}/"
echo "  Report:  ${RESULTS_DIR}/report.md"
echo "============================================================"
