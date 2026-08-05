# -*- coding: utf-8 -*-
"""
OfficeCLI Direct Tool
直接通过子进程调用 officecli.exe，无需 MCP 协议。
"""

import os
import json
import subprocess
import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger("OfficeCLI")


class OfficeCLITool:
    """OfficeCLI 直接调用封装"""
    
    def __init__(self, binary_path: str = None):
        self.binary_path = binary_path or self._find_binary()
        self._available = None
        self._version = None
    
    @staticmethod
    def _find_binary() -> str:
        import shutil
        found = shutil.which("officecli")
        if found:
            return found
        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        for name in ["bin/officecli.exe", "bin/officecli"]:
            c = os.path.join(project_root, name)
            if os.path.isfile(c):
                return c
        return "officecli"
    
    def is_available(self) -> bool:
        if self._available is not None:
            return self._available
        try:
            result = subprocess.run(
                [self.binary_path, "--version"],
                capture_output=True, text=True, timeout=10
            )
            self._available = (result.returncode == 0)
            if self._available:
                self._version = result.stdout.strip()
        except Exception as e:
            logger.warning(f"[OfficeCLI] Not available: {e}")
            self._available = False
        return self._available
    
    def get_status(self) -> Dict:
        available = self.is_available()
        return {
            "available": available,
            "binary": self.binary_path,
            "version": self._version if available else None,
            "binary_exists": os.path.isfile(self.binary_path) if self.binary_path else False,
        }
    
    def _run(self, args: List[str], timeout: int = 120, input_data: str = None) -> Dict:
        cmd = [self.binary_path] + args
        logger.info(f"[OfficeCLI] Running: {' '.join(cmd)}")
        try:
            result = subprocess.run(
                cmd, capture_output=True, text=True, timeout=timeout,
                input=input_data,
                cwd=os.path.dirname(self.binary_path) if self.binary_path else None
            )
            return {
                "success": result.returncode == 0,
                "stdout": result.stdout,
                "stderr": result.stderr,
                "returncode": result.returncode,
            }
        except subprocess.TimeoutExpired:
            return {"success": False, "error": f"Timeout ({timeout}s)"}
        except FileNotFoundError:
            return {"success": False, "error": f"Binary not found: {self.binary_path}"}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    # Word
    def word_read(self, file_path: str) -> Dict:
        return self._run(["word", "read", "--file", os.path.abspath(file_path), "--format", "json"])
    
    def word_create(self, output_path: str, title: str = "", content: str = "") -> Dict:
        args = ["word", "create", "--file", os.path.abspath(output_path)]
        if title:
            args += ["--title", title]
        return self._run(args, input_data=content)
    
    def word_edit(self, file_path: str, operations: str) -> Dict:
        return self._run(["word", "edit", "--file", os.path.abspath(file_path)], input_data=operations)
    
    def word_to_pdf(self, file_path: str, output_path: str = None) -> Dict:
        args = ["word", "convert", "--file", os.path.abspath(file_path), "--to", "pdf"]
        if output_path:
            args += ["--output", os.path.abspath(output_path)]
        return self._run(args)
    
    # Excel
    def excel_read(self, file_path: str, sheet: str = None, range: str = None) -> Dict:
        args = ["excel", "read", "--file", os.path.abspath(file_path), "--format", "json"]
        if sheet: args += ["--sheet", sheet]
        if range: args += ["--range", range]
        return self._run(args)
    
    def excel_create(self, output_path: str, data: str = None, headers: List[str] = None) -> Dict:
        args = ["excel", "create", "--file", os.path.abspath(output_path)]
        if headers: args += ["--headers", ",".join(headers)]
        return self._run(args, input_data=data)
    
    def excel_write(self, file_path: str, sheet: str, cell: str, data: str) -> Dict:
        return self._run(
            ["excel", "write", "--file", os.path.abspath(file_path), "--sheet", sheet, "--cell", cell],
            input_data=data
        )
    
    # PPT
    def ppt_read(self, file_path: str) -> Dict:
        return self._run(["ppt", "read", "--file", os.path.abspath(file_path), "--format", "json"])
    
    def ppt_create(self, output_path: str, slides_json: str, template: str = None) -> Dict:
        args = ["ppt", "create", "--file", os.path.abspath(output_path)]
        if template: args += ["--template", template]
        return self._run(args, input_data=slides_json)
    
    # 通用
    def convert(self, file_path: str, to_format: str, output_path: str = None) -> Dict:
        args = ["convert", "--file", os.path.abspath(file_path), "--to", to_format]
        if output_path: args += ["--output", os.path.abspath(output_path)]
        return self._run(args, timeout=180)
    
    def execute_command(self, command: str) -> Dict:
        return self._run(command.split())
    
    def help(self) -> Dict:
        return self._run(["--help"])


# 全局实例
_office_cli: Optional[OfficeCLITool] = None

def get_office_cli(binary_path: str = None) -> OfficeCLITool:
    global _office_cli
    if _office_cli is None:
        _office_cli = OfficeCLITool(binary_path)
    return _office_cli

def reset_office_cli(binary_path: str = None):
    global _office_cli
    _office_cli = OfficeCLITool(binary_path)
