#!/usr/bin/env python3
"""
NexusFlow Phase 2 Ablation Experiment Runner v3
================================================
运行 demo_phase2_ablation_v3.py 并报告结果。
"""
import asyncio
import subprocess
import os
import sys
import json

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
NEXUSFLOW_DIR = os.path.dirname(os.path.dirname(SCRIPT_DIR))

async def main():
    from codeact_sdk import CodeActSDK
    sdk = CodeActSDK()

    api_key = os.environ.get("DEEPSEEK_API_KEY", "")
    if not api_key:
        raise RuntimeError(
            "DEEPSEEK_API_KEY environment variable is not set. "
            "Export it before running this script."
        )
    work_dir = NEXUSFLOW_DIR
    script_path = os.path.join(work_dir, "examples", "demo_phase2_ablation_v3.py")

    env = os.environ.copy()
    env["DEEPSEEK_API_KEY"] = api_key

    print(f"Working directory: {work_dir}")
    print(f"Script path: {script_path}")
    print(f"API key set: {api_key[:8]}...")

    # Run the experiment script using subprocess
    result = subprocess.run(
        [sys.executable, script_path],
        cwd=work_dir,
        env=env,
        capture_output=True,
        text=True,
        timeout=3600,
    )

    print("=== STDOUT ===")
    print(result.stdout[-5000:] if len(result.stdout) > 5000 else result.stdout)
    print("=== STDERR ===")
    print(result.stderr[-3000:] if len(result.stderr) > 3000 else result.stderr)
    print(f"=== Exit code: {result.returncode} ===")

    # Check output files
    json_path = os.path.join(work_dir, "examples", "phase2_ablation_results_v3.json")
    html_path = os.path.join(work_dir, "examples", "phase2_ablation_report_v3.html")

    json_exists = os.path.exists(json_path)
    html_exists = os.path.exists(html_path)

    print(f"\nJSON results: {json_path} exists={json_exists}")
    print(f"HTML report: {html_path} exists={html_exists}")

    # Parse and report key findings
    key_findings = {}
    if json_exists:
        with open(json_path, "r") as f:
            data = json.load(f)
        
        # Route ablation
        route = data.get("route_ablation", {})
        for mode in ["oracle", "auto", "reverse"]:
            stats = route.get(mode, {}).get("stats", {})
            key_findings[f"route_{mode}"] = f"{stats.get('mean', 0):.3f}±{stats.get('std', 0):.3f}"
        key_findings["route_direction_consistent"] = route.get("direction_consistent", False)
        
        # Round ablation
        round_data = data.get("round_ablation", {})
        for key in ["round_2", "round_3", "round_4"]:
            stats = round_data.get(key, {}).get("stats", {})
            key_findings[key] = f"{stats.get('mean', 0):.3f}±{stats.get('std', 0):.3f}"
        key_findings["inverted_u"] = round_data.get("inverted_u_verified", False)
        
        # Topology switch cost
        topo = data.get("topology_switch_cost", {})
        for key in ["sequential", "hybrid", "dynamic"]:
            stats = topo.get(key, {}).get("stats", {})
            key_findings[f"topo_{key}"] = f"{stats.get('mean', 0):.3f}±{stats.get('std', 0):.3f}"
        key_findings["dynamic_better"] = topo.get("dynamic_better", False)
        
        print("\n=== KEY FINDINGS ===")
        for k, v in key_findings.items():
            print(f"  {k}: {v}")

    # Build summary message
    if result.returncode == 0 and json_exists:
        msg_lines = ["Phase 2 方差控制实验(v3)完成！", ""]
        
        route = key_findings
        msg_lines.append("📊 实验1-路由ablation:")
        msg_lines.append(f"  Oracle={route.get('route_oracle','N/A')}, Auto={route.get('route_auto','N/A')}, Reverse={route.get('route_reverse','N/A')}")
        msg_lines.append(f"  方向一致性: {'✓' if route.get('route_direction_consistent') else '✗'}")
        msg_lines.append("")
        msg_lines.append("📊 实验2-轮次ablation(核心):")
        msg_lines.append(f"  2轮={route.get('round_2','N/A')}, 3轮={route.get('round_3','N/A')}, 4轮={route.get('round_4','N/A')}")
        msg_lines.append(f"  倒U型验证: {'✓ 3轮最优' if route.get('inverted_u') else '✗ 未成立'}")
        msg_lines.append("")
        msg_lines.append("📊 实验3-拓扑切换成本:")
        msg_lines.append(f"  Sequential={route.get('topo_sequential','N/A')}, Hybrid={route.get('topo_hybrid','N/A')}, Dynamic={route.get('topo_dynamic','N/A')}")
        msg_lines.append(f"  动态优于固定: {'✓' if route.get('dynamic_better') else '✗'}")
        
        message = "\n".join(msg_lines)
        status = "success"
        result_mode = "display_only"
    else:
        message = f"实验执行异常。Exit code: {result.returncode}, JSON exists: {json_exists}"
        status = "error"
        result_mode = "notify"

    await sdk.submit_result(
        message=message,
        status=status,
        result_mode=result_mode,
        data={"exit_code": result.returncode, "json_exists": json_exists, "html_exists": html_exists, "findings": key_findings}
    )

if __name__ == "__main__":
    asyncio.run(main())
