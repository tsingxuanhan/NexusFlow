#!/usr/bin/env python3
"""
run_benchmark.py — NexusFlow 统一评测入口
==========================================

一条命令运行 Benchmark、生成报告、记录实验元数据。

使用方式:
    # 运行全部评测
    python scripts/run_benchmark.py

    # 运行特定阶段
    python scripts/run_benchmark.py --stage 7

    # 运行 PinchBench
    python scripts/run_benchmark.py --bench pinchbench

    # 运行消融实验
    python scripts/run_benchmark.py --bench ablation --rounds 4

    # 指定模型和输出
    python scripts/run_benchmark.py --stage 7 --model deepseek-chat --output results/

    # 生成实验报告
    python scripts/run_benchmark.py --stage 7 --report
"""

import argparse
import json
import os
import sys
import subprocess
import hashlib
from datetime import datetime
from pathlib import Path


# Benchmark stages mapping
STAGES = {
    1: ("Stage 1: 单Agent vs 6角色", "examples/stage1_single_vs_6roles/"),
    2: ("Stage 2: 6角色 vs 10角色", "examples/stage2_6roles_vs_10roles/"),
    3: ("Stage 3: 全系统质量门禁", "examples/stage3_full_system/"),
    4: ("Stage 4: 50步全流程", "examples/stage4_fifty_steps/"),
    5: ("Stage 5: 80步真实Benchmark", "examples/stage5_eighty_steps/"),
    6: ("Stage 6: L3认知任务", "examples/stage6_L3_cognitive_tasks/"),
    7: ("Stage 7: PinchBench 25 Hard", "examples/stage7_pinchbench/"),
}

# Benchmark types
BENCHES = {
    "pinchbench": {
        "desc": "PinchBench 25 Hard Cases SA vs NF",
        "cmd": "python examples/demo_e2e_pinchbench.py",
    },
    "ablation": {
        "desc": "CDoL 消融实验（2/3/4轮辩论）",
        "cmd": "python examples/demo_phase2_ablation_v3.py",
    },
    "edge_cloud": {
        "desc": "端边云调度实机验证",
        "cmd": "python examples/edge_cloud_scheduling/edge_cloud_real_verification.py",
    },
    "routing": {
        "desc": "路由策略对比实验",
        "cmd": "python examples/routing_experiments.py",
    },
    "e2e": {
        "desc": "端到端全流程Demo",
        "cmd": "python examples/demo_e2e_pinchbench.py",
    },
}


def get_git_info():
    """Get current git commit and branch."""
    try:
        commit = subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"],
            stderr=subprocess.DEVNULL
        ).decode().strip()
    except Exception:
        commit = "unknown"
    
    try:
        branch = subprocess.check_output(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            stderr=subprocess.DEVNULL
        ).decode().strip()
    except Exception:
        branch = "unknown"
    
    return commit, branch


def get_system_info():
    """Get system information."""
    import platform
    return {
        "os": platform.system(),
        "os_version": platform.version(),
        "python": platform.python_version(),
        "arch": platform.machine(),
        "processor": platform.processor() or "unknown",
    }


def run_command(cmd: str, cwd: str = None, env: dict = None) -> dict:
    """Run a command and capture output."""
    import time
    start = time.time()
    
    merged_env = os.environ.copy()
    if env:
        merged_env.update(env)
    
    try:
        result = subprocess.run(
            cmd,
            shell=True,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=600,  # 10 min timeout
            env=merged_env,
        )
        elapsed = time.time() - start
        
        return {
            "returncode": result.returncode,
            "stdout": result.stdout[-5000:] if result.stdout else "",  # Truncate
            "stderr": result.stderr[-2000:] if result.stderr else "",
            "elapsed_seconds": round(elapsed, 2),
            "success": result.returncode == 0,
        }
    except subprocess.TimeoutExpired:
        return {
            "returncode": -1,
            "stdout": "",
            "stderr": "TIMEOUT (600s)",
            "elapsed_seconds": 600,
            "success": False,
        }
    except Exception as e:
        return {
            "returncode": -1,
            "stdout": "",
            "stderr": str(e),
            "elapsed_seconds": 0,
            "success": False,
        }


def save_experiment_record(args, git_info, sys_info, results, output_dir):
    """Save experiment record as structured JSON + Markdown."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    exp_id = f"exp_{timestamp}"
    
    # JSON record
    record = {
        "experiment_id": exp_id,
        "timestamp": datetime.now().isoformat(),
        "git_commit": git_info[0],
        "git_branch": git_info[1],
        "config": {
            "stage": args.stage,
            "bench": args.bench,
            "model": args.model,
            "temperature": args.temperature,
            "max_tokens": args.max_tokens,
            "max_rounds": args.rounds,
            "random_seed": args.seed,
        },
        "system": sys_info,
        "results": results,
        "metadata": {
            "runner": "scripts/run_benchmark.py",
            "version": "v3.4.0",
        },
    }
    
    # Save JSON
    json_path = os.path.join(output_dir, f"{exp_id}.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(record, f, ensure_ascii=False, indent=2)
    
    # Save Markdown summary
    md_path = os.path.join(output_dir, f"{exp_id}.md")
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(f"# 实验记录: {exp_id}\n\n")
        f.write(f"*时间: {record['timestamp']}*\n\n")
        f.write(f"## 配置\n\n")
        f.write(f"| 参数 | 值 |\n|------|----|\n")
        for k, v in record["config"].items():
            f.write(f"| {k} | {v} |\n")
        f.write(f"\n## 环境\n\n")
        f.write(f"- Git: {git_info[0]} ({git_info[1]})\n")
        f.write(f"- Python: {sys_info['python']}\n")
        f.write(f"- OS: {sys_info['os']} {sys_info['os_version']}\n")
        f.write(f"\n## 结果\n\n")
        for r in results:
            status = "✅" if r.get("success") else "❌"
            f.write(f"### {status} {r.get('name', 'unknown')}\n")
            f.write(f"- 耗时: {r.get('elapsed_seconds', 0)}s\n")
            f.write(f"- 返回码: {r.get('returncode', -1)}\n")
            if r.get("stderr") and not r.get("success"):
                f.write(f"- 错误: {r['stderr'][:200]}\n")
            f.write("\n")
    
    print(f"\n📋 实验记录已保存:")
    print(f"   JSON: {json_path}")
    print(f"   MD:   {md_path}")
    
    return json_path, md_path


def main():
    parser = argparse.ArgumentParser(
        description="NexusFlow 统一评测入口",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python scripts/run_benchmark.py --stage 7              # 运行 Stage 7
  python scripts/run_benchmark.py --bench pinchbench     # PinchBench 对比
  python scripts/run_benchmark.py --bench ablation -r 4  # 4轮消融实验
  python scripts/run_benchmark.py --all                  # 运行全部 Stage
        """
    )
    
    parser.add_argument("--stage", type=int, choices=[1,2,3,4,5,6,7],
                       help="运行指定阶段 (1-7)")
    parser.add_argument("--bench", choices=list(BENCHES.keys()),
                       help="运行指定评测类型")
    parser.add_argument("--all", action="store_true",
                       help="运行全部 Stage 1-7")
    parser.add_argument("--model", default="deepseek-chat",
                       help="LLM 模型 (default: deepseek-chat)")
    parser.add_argument("--temperature", type=float, default=0.7,
                       help="采样温度 (default: 0.7)")
    parser.add_argument("--max-tokens", type=int, default=4096,
                       help="最大 token 数 (default: 4096)")
    parser.add_argument("--rounds", type=int, default=3,
                       help="辩论轮数 (default: 3)")
    parser.add_argument("--seed", type=int, default=42,
                       help="随机种子 (default: 42)")
    parser.add_argument("--output", default="results/",
                       help="输出目录 (default: results/)")
    parser.add_argument("--report", action="store_true",
                       help="生成 HTML 报告")
    parser.add_argument("--dry-run", action="store_true",
                       help="只显示将要执行的命令")
    
    args = parser.parse_args()
    
    # Get metadata
    git_info = get_git_info()
    sys_info = get_system_info()
    
    # Create output directory
    os.makedirs(args.output, exist_ok=True)
    
    print(f"""
╔═══════════════════════════════════════════════════════════╗
║                                                           ║
║   NexusFlow Benchmark Runner v3.4                         ║
║                                                           ║
╚═══════════════════════════════════════════════════════════╝
    
    Git:    {git_info[0]} ({git_info[1]})
    Model:  {args.model}
    Temp:   {args.temperature}
    Seed:   {args.seed}
    Output: {args.output}
""")
    
    results = []
    
    if args.all:
        # Run all stages
        for stage_id, (desc, path) in STAGES.items():
            print(f"\n{'='*60}")
            print(f"  Stage {stage_id}: {desc}")
            print(f"{'='*60}")
            
            # Find the main script
            script = None
            if os.path.exists(path):
                for f in os.listdir(path):
                    if f.endswith('.py') and ('benchmark' in f.lower() or 'run' in f.lower()):
                        script = os.path.join(path, f)
                        break
            
            if script:
                cmd = f"python {script}"
                print(f"  > {cmd}")
                if not args.dry_run:
                    result = run_command(cmd)
                    result["name"] = f"Stage {stage_id}"
                    results.append(result)
                    print(f"  {'✅' if result['success'] else '❌'} ({result['elapsed_seconds']}s)")
            else:
                print(f"  ⚠️  No benchmark script found in {path}")
    
    elif args.stage:
        desc, path = STAGES[args.stage]
        print(f"\n  Stage {args.stage}: {desc}")
        
        # Run stage
        cmd = None
        if args.stage == 3:
            cmd = f"python {path}stage3_full_system.py"
        elif args.stage == 5:
            cmd = f"python {path}run_real_benchmark.py"
        elif args.stage == 6:
            cmd = f"python {path}run_L3_benchmark.py"
        elif args.stage == 7:
            cmd = f"python {path}run_benchmark.py"
        else:
            # Find script
            if os.path.exists(path):
                for f in sorted(os.listdir(path)):
                    if f.endswith('.py'):
                        cmd = f"python {os.path.join(path, f)}"
                        break
        
        if cmd:
            print(f"  > {cmd}")
            if not args.dry_run:
                result = run_command(cmd)
                result["name"] = f"Stage {args.stage}"
                results.append(result)
                print(f"  {'✅' if result['success'] else '❌'} ({result['elapsed_seconds']}s)")
    
    elif args.bench:
        bench = BENCHES[args.bench]
        print(f"\n  Benchmark: {bench['desc']}")
        cmd = bench["cmd"]
        
        if args.bench == "ablation":
            cmd += f" --rounds {args.rounds}"
        
        print(f"  > {cmd}")
        if not args.dry_run:
            result = run_command(cmd)
            result["name"] = bench["desc"]
            results.append(result)
            print(f"  {'✅' if result['success'] else '❌'} ({result['elapsed_seconds']}s)")
    
    else:
        parser.print_help()
        return
    
    # Save results
    if results:
        save_experiment_record(args, git_info, sys_info, results, args.output)
    
    print(f"\n✅ Benchmark run complete.")


if __name__ == "__main__":
    main()
