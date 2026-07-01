# -*- coding: utf-8 -*-
"""
铉枢·炉守 Git操作工具
XuanHub Git Operations Tool — Phase 3

双重接口: BaseTool JSON调用 + CodeAct全局函数 git_op()
安全封装git命令，防止危险操作
"""

import os
import subprocess
import logging
from typing import Any, Dict, List, Optional
from .base_tool import BaseTool, ToolResult

logger = logging.getLogger("GitOps")


# 允许的git子命令
ALLOWED_COMMANDS = {
    "status", "log", "diff", "branch", "tag",
    "add", "commit", "push", "pull", "fetch",
    "checkout", "merge", "rebase", "stash",
    "remote", "show", "describe", "rev-parse",
    "shortlog", "whatchanged",
}

# 禁止的git子命令（危险操作）
BLOCKED_COMMANDS = {
    "reset", "clean", "reflog", "filter-branch",
    "submodule", "cherry-pick", "bisect",
}


def git_op(command: str, args: str = "", repo_path: str = ".") -> Dict[str, Any]:
    """
    执行Git操作 — CodeAct全局函数
    
    Args:
        command: git子命令 (status/log/add/commit/push/pull等)
        args: 命令参数
        repo_path: 仓库路径
    
    Returns:
        {"success": bool, "output": str, "error": str}
    
    CodeAct用法:
        result = git_op("status")
        result = git_op("log", "--oneline -10")
        result = git_op("add", "new_file.py")
        result = git_op("commit", '-m "feat: add new feature"')
    """
    # 安全检查
    cmd_parts = command.strip().split()
    subcmd = cmd_parts[0].lower()
    
    if subcmd in BLOCKED_COMMANDS:
        return {"success": False, "output": "", "error": f"Blocked git command: {subcmd}"}
    
    if subcmd not in ALLOWED_COMMANDS:
        return {"success": False, "output": "", "error": f"Unknown git command: {subcmd}"}
    
    # 构建完整命令
    full_cmd = f"git {command} {args}".strip()
    
    try:
        result = subprocess.run(
            full_cmd,
            shell=True,
            cwd=repo_path,
            capture_output=True,
            text=True,
            timeout=60,
        )
        
        return {
            "success": result.returncode == 0,
            "output": result.stdout[:5000],
            "error": result.stderr[:2000] if result.stderr else "",
        }
    except subprocess.TimeoutExpired:
        return {"success": False, "output": "", "error": "Git command timed out"}
    except Exception as e:
        return {"success": False, "output": "", "error": str(e)}


class GitOpsTool(BaseTool):
    """Git操作工具 — BaseTool JSON兼容"""
    
    def __init__(self):
        super().__init__(
            name="git_ops",
            description="Execute safe Git operations (status, log, add, commit, push, pull, etc.). Dangerous commands like reset and clean are blocked.",
            parameters={
                "type": "object",
                "properties": {
                    "command": {
                        "type": "string",
                        "description": "Git subcommand (e.g., 'status', 'log', 'add', 'commit')"
                    },
                    "args": {
                        "type": "string",
                        "description": "Command arguments",
                        "default": ""
                    },
                    "repo_path": {
                        "type": "string",
                        "description": "Repository path",
                        "default": "."
                    }
                },
                "required": ["command"]
            }
        )
    
    def execute(self, command: str, args: str = "", repo_path: str = ".", **kwargs) -> ToolResult:
        result = git_op(command, args=args, repo_path=repo_path)
        return ToolResult(
            success=result["success"],
            output=result["output"],
            error=result.get("error"),
        )
