# -*- coding: utf-8 -*-
"""
铉枢·炉守 文件操作工具
XuanHub File Operations Tool — Phase 3

双重接口: BaseTool JSON调用 + CodeAct全局函数 read_file/write_file()
沙箱化: 限制在允许的目录内操作
"""

import os
import json
import logging
from typing import Any, Dict, List, Optional
from pathlib import Path
from .base_tool import BaseTool, ToolResult

logger = logging.getLogger("FileOps")


# ============ 安全路径检查 ============

class FileOpsSecurity:
    """文件操作安全策略"""
    
    # 允许的根目录
    ALLOWED_ROOTS = [
        "/app/data",
        "./output",
        "./knowledge",
        "./data",
        "./reports",
        "/tmp/xuanshu",
    ]
    
    # 禁止访问的路径模式
    BLOCKED_PATTERNS = [
        "/etc/", "/root/", "/home/", "/var/",
        ".ssh/", ".gnupg/", ".env",
        "__pycache__", ".git/",
    ]
    
    @classmethod
    def is_path_allowed(cls, path: str) -> tuple:
        """
        检查路径是否允许访问
        
        Returns:
            (allowed, reason)
        """
        abs_path = os.path.abspath(path)
        
        # 检查禁止模式
        for pattern in cls.BLOCKED_PATTERNS:
            if pattern in abs_path:
                return False, f"Path contains blocked pattern: {pattern}"
        
        # 检查允许的根目录
        normalized = os.path.normpath(abs_path)
        for root in cls.ALLOWED_ROOTS:
            root_abs = os.path.abspath(root)
            if normalized.startswith(root_abs):
                return True, "Allowed"
        
        # 相对路径在当前工作目录下也允许
        if not os.path.isabs(path):
            cwd = os.getcwd()
            full_path = os.path.normpath(os.path.join(cwd, path))
            for root in cls.ALLOWED_ROOTS:
                root_abs = os.path.abspath(root)
                if full_path.startswith(root_abs):
                    return True, "Allowed"
        
        return False, f"Path outside allowed roots: {abs_path}"


# ============ CodeAct全局函数 ============

def read_file(path: str, encoding: str = "utf-8", max_lines: int = 1000) -> str:
    """
    读取文件内容 — CodeAct全局函数
    
    Args:
        path: 文件路径
        encoding: 编码
        max_lines: 最大读取行数
    
    Returns:
        文件内容字符串
    
    CodeAct用法:
        content = read_file("knowledge/materials/ssc-overview.md")
        lines = content.split("\\n")
        print(f"Total lines: {len(lines)}")
    """
    allowed, reason = FileOpsSecurity.is_path_allowed(path)
    if not allowed:
        raise PermissionError(f"Access denied: {reason}")
    
    try:
        with open(path, 'r', encoding=encoding) as f:
            lines = []
            for i, line in enumerate(f):
                if i >= max_lines:
                    lines.append(f"... (truncated at line {max_lines})")
                    break
                lines.append(line.rstrip('\n'))
        return '\n'.join(lines)
    except FileNotFoundError:
        raise FileNotFoundError(f"File not found: {path}")
    except Exception as e:
        raise IOError(f"Read error: {e}")


def write_file(path: str, content: str, encoding: str = "utf-8", append: bool = False) -> str:
    """
    写入文件 — CodeAct全局函数
    
    Args:
        path: 文件路径
        content: 写入内容
        encoding: 编码
        append: 是否追加模式
    
    Returns:
        操作结果描述
    
    CodeAct用法:
        write_file("output/report.md", "# Report\\nContent here")
        write_file("output/log.txt", "new entry\\n", append=True)
    """
    allowed, reason = FileOpsSecurity.is_path_allowed(path)
    if not allowed:
        raise PermissionError(f"Access denied: {reason}")
    
    try:
        # 自动创建目录
        dir_path = os.path.dirname(path)
        if dir_path:
            os.makedirs(dir_path, exist_ok=True)
        
        mode = 'a' if append else 'w'
        with open(path, mode, encoding=encoding) as f:
            f.write(content)
        
        return f"Written {len(content)} chars to {path}"
    except Exception as e:
        raise IOError(f"Write error: {e}")


def list_dir(path: str = ".", pattern: str = "*") -> List[str]:
    """
    列出目录内容 — CodeAct全局函数
    
    Args:
        path: 目录路径
        pattern: 文件名通配符
    
    Returns:
        文件/目录名列表
    """
    import glob
    allowed, reason = FileOpsSecurity.is_path_allowed(path)
    if not allowed:
        raise PermissionError(f"Access denied: {reason}")
    
    try:
        search_path = os.path.join(path, pattern)
        entries = glob.glob(search_path)
        return [os.path.basename(e) for e in sorted(entries)]
    except Exception as e:
        raise IOError(f"List error: {e}")


# ============ BaseTool兼容 ============

class FileOpsTool(BaseTool):
    """文件操作工具 — BaseTool JSON兼容"""
    
    def __init__(self):
        super().__init__(
            name="file_ops",
            description="Read, write, and list files. Operations are sandboxed to allowed directories.",
            parameters={
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "enum": ["read", "write", "append", "list"],
                        "description": "File operation type"
                    },
                    "path": {
                        "type": "string",
                        "description": "File or directory path"
                    },
                    "content": {
                        "type": "string",
                        "description": "Content to write (for write/append)"
                    },
                    "max_lines": {
                        "type": "integer",
                        "description": "Max lines to read",
                        "default": 1000
                    }
                },
                "required": ["action", "path"]
            }
        )
    
    def execute(
        self,
        action: str,
        path: str,
        content: str = "",
        max_lines: int = 1000,
        **kwargs
    ) -> ToolResult:
        try:
            if action == "read":
                result = read_file(path, max_lines=max_lines)
                return ToolResult(success=True, output=result, metadata={"path": path})
            
            elif action in ("write", "append"):
                if not content:
                    return ToolResult(success=False, error="Content required for write/append")
                append = action == "append"
                result = write_file(path, content, append=append)
                return ToolResult(success=True, output=result, metadata={"path": path, "action": action})
            
            elif action == "list":
                result = list_dir(path)
                return ToolResult(success=True, output=result, metadata={"path": path, "count": len(result)})
            
            else:
                return ToolResult(success=False, error=f"Unknown action: {action}")
        
        except PermissionError as e:
            return ToolResult(success=False, error=str(e))
        except FileNotFoundError as e:
            return ToolResult(success=False, error=str(e))
        except Exception as e:
            return ToolResult(success=False, error=str(e))
