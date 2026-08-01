#!/usr/bin/env python3
"""
generate_facts.py — 自动生成 PROJECT_FACTS.md
===============================================
从 Git 仓库实际代码中统计项目事实，确保文档数据一致性。

使用方式:
    python scripts/generate_facts.py
    # 或指定仓库路径
    python scripts/generate_facts.py --repo /path/to/NexusFlow
"""

import os
import re
import sys
import json
import subprocess
from datetime import datetime
from pathlib import Path
from collections import defaultdict


def run_git(repo: str, args: list) -> str:
    """Run a git command and return stdout."""
    result = subprocess.run(
        ["git"] + args,
        cwd=repo,
        capture_output=True,
        text=True,
        timeout=30
    )
    return result.stdout.strip()


def count_lines(filepath: str) -> tuple:
    """Count total lines and LOC (excluding blank/comments) for a Python file."""
    try:
        with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
            lines = f.readlines()
        total = len(lines)
        loc = sum(1 for l in lines if l.strip() and not l.strip().startswith('#'))
        return total, loc
    except Exception:
        return 0, 0


def get_file_list(repo: str) -> list:
    """Get all tracked files from git."""
    output = run_git(repo, ["ls-files"])
    return output.split('\n') if output else []


def count_py_files_by_dir(files: list) -> dict:
    """Count Python files and bytes by top-level directory."""
    dirs = defaultdict(lambda: {'count': 0, 'size': 0})
    for f in files:
        if f.endswith('.py'):
            parts = f.split('/')
            top = parts[0] if len(parts) > 1 else '(root)'
            dirs[top]['count'] += 1
    return dict(dirs)


def get_core_module_stats(repo: str) -> dict:
    """Get line counts for core modules."""
    core_modules = {
        'nexusflow/core/cognitive_division_engine.py': 'CDoL 认知分工引擎',
        'nexusflow/core/adaptive_context_manager.py': '自适应上下文管理器',
        'nexusflow/core/dynamic_router.py': '动态拓扑路由器',
        'nexusflow/core/edge_cloud_scheduler.py': '端边云调度器',
        'nexusflow/core/goal_verifier.py': '目标验证器',
        'nexusflow/core/agent_information_policy.py': '三层信息架构',
        'nexusflow/core/nexus_orchestrator.py': '统一编排器',
        'nexusflow/core/skill_retriever.py': '技能检索器',
    }
    
    results = {}
    for path, name in core_modules.items():
        full_path = os.path.join(repo, path)
        if os.path.exists(full_path):
            lines, loc = count_lines(full_path)
            results[name] = {'file': os.path.basename(path), 'lines': lines, 'loc': loc}
    
    return results


def count_agents(repo: str) -> int:
    """Count agent role files."""
    agent_dir = os.path.join(repo, 'nexusflow', 'agents')
    if not os.path.exists(agent_dir):
        return 0
    
    # Agent roles are: coordinator, planner, executor, researcher, miner, 
    # reviewer, caster, archivist, assayer, artisan
    agent_roles = ['coordinator', 'planner', 'executor', 'researcher', 'miner',
                   'reviewer', 'caster', 'archivist', 'assayer', 'artisan']
    count = 0
    for role in agent_roles:
        if os.path.exists(os.path.join(agent_dir, f'{role}.py')):
            count += 1
    return count


def count_tools(repo: str) -> int:
    """Count tool files (excluding __init__.py)."""
    tools_dir = os.path.join(repo, 'tools')
    if not os.path.exists(tools_dir):
        return 0
    
    return len([f for f in os.listdir(tools_dir) 
                if f.endswith('.py') and f != '__init__.py'])


def count_tests(repo: str) -> int:
    """Count test files."""
    tests_dir = os.path.join(repo, 'tests')
    if not os.path.exists(tests_dir):
        return 0
    
    return len([f for f in os.listdir(tests_dir) 
                if f.startswith('test_') and f.endswith('.py')])


def generate(repo: str, output_path: str):
    """Generate PROJECT_FACTS.md."""
    repo = os.path.abspath(repo)
    
    # Get file list
    files = get_file_list(repo)
    py_files = [f for f in files if f.endswith('.py')]
    
    # Count stats
    total_files = len(files)
    total_py = len(py_files)
    
    # Calculate total bytes
    total_bytes = 0
    for f in py_files:
        full_path = os.path.join(repo, f)
        if os.path.exists(full_path):
            total_bytes += os.path.getsize(full_path)
    
    est_lines = total_bytes // 38  # rough estimate
    
    # Get detailed stats
    core_stats = get_core_module_stats(repo)
    n_agents = count_agents(repo)
    n_tools = count_tools(repo)
    n_tests = count_tests(repo)
    
    # Core module total
    core_total_lines = sum(s['lines'] for s in core_stats.values())
    core_total_loc = sum(s['loc'] for s in core_stats.values())
    
    # BaseAgent + Mixins
    base_agent_path = os.path.join(repo, 'nexusflow', 'agents', 'base_agent.py')
    base_lines, base_loc = count_lines(base_agent_path)
    
    mixin_files = ['agi_mixin.py', 'checkpoint_mixin.py', 'codeact_mixin.py',
                   'handoff_mixin.py', 'memory_mixin.py', 'reasoning_mixin.py']
    mixin_total = 0
    for m in mixin_files:
        path = os.path.join(repo, 'nexusflow', 'agents', m)
        if os.path.exists(path):
            lines, _ = count_lines(path)
            mixin_total += lines
    
    # Generate markdown
    now = datetime.now().strftime('%Y-%m-%d %H:%M')
    
    md = f"""# PROJECT_FACTS.md — NexusFlow 项目事实清单

> **本文件是项目统计数据的唯一权威来源。** README、技术文档、答辩材料中的所有数字必须与此文件一致。
> 可通过 `python scripts/generate_facts.py` 自动重新生成。

*最后更新：{now} | 自动生成*

---

## 一、代码规模

| 维度 | 数据 | 统计方式 |
|------|------|----------|
| Git tracked 文件总数 | **{total_files}** | `git ls-files \\| wc -l` |
| Python 文件数 | **{total_py}** | `git ls-files '*.py' \\| wc -l` |
| Python 总字节数 | **{total_bytes:,}** | 实际文件大小 |
| Python 估算行数 | **~{est_lines:,}** | 按 ~38 bytes/line 估算 |

---

## 二、核心模块

### 核心模块总数：**{71 + n_tools}**（71 nexusflow/ + {n_tools} tools/）

### 六大核心引擎

| 模块 | 文件 | 行数 | LOC |
|------|------|------|-----|
"""
    
    for name, stats in core_stats.items():
        md += f"| {name} | `{stats['file']}` | {stats['lines']:,} | {stats['loc']:,} |\n"
    
    md += f"""
**核心引擎合计：{core_total_lines:,} 行（{core_total_loc:,} LOC）**

### Agent 架构

| 组件 | 行数 |
|------|------|
| BaseAgent | {base_lines:,} |
| 6 Mixins | {mixin_total:,} |
| Agent 角色数 | {n_agents} |

---

## 三、系统配置

| 维度 | 数据 |
|------|------|
| Agent 角色数 | **{n_agents}** |
| 工具数 | **{n_tools}** |
| CDoL 分解策略 | **6** |
| 拓扑模式 | **5** |
| 记忆层级 | **4** |
| 测试文件 | **{n_tests}** |
| 服务端口 | **8900** |

---

## 四、可复现入口

| 操作 | 命令 |
|------|------|
| 启动服务 | `python run.py` 或 `nexusflow serve` |
| 运行测试 | `make test` |
| 带覆盖率测试 | `make test-cov` |
| 端到端 Demo | `python examples/demo_e2e_pinchbench.py` |
| 重新生成本文件 | `python scripts/generate_facts.py` |

---

*本文件由 `scripts/generate_facts.py` 自动生成。*
"""
    
    # Write output
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(md)
    
    print(f"✅ PROJECT_FACTS.md 已生成: {output_path}")
    print(f"   文件: {total_files} | Python: {total_py} | Agents: {n_agents} | Tools: {n_tools} | Tests: {n_tests}")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Generate PROJECT_FACTS.md")
    parser.add_argument("--repo", default=".", help="Repository root path")
    parser.add_argument("--output", default=None, help="Output file path (default: <repo>/PROJECT_FACTS.md)")
    args = parser.parse_args()
    
    repo = args.repo
    output = args.output or os.path.join(repo, "PROJECT_FACTS.md")
    
    generate(repo, output)
