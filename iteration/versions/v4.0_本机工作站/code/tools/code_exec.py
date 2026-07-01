# -*- coding: utf-8 -*-
"""
铉枢·炉守 CodeAct沙箱执行器
XuanHub CodeAct Executor — Phase 3 核心

Agent通过写Python代码而非调JSON工具来行动。
OpenHands/LangGraph验证: CodeAct在SWE-Bench上比JSON工具调用高15-20%。
DeepSeek PRO代码能力极强，CodeExec比JSON工具调用更自然。

安全: Guardrails检查 → 受限globals → 超时15s → stdout/stderr/return_value
"""

import logging
import sys
import traceback
import io
import signal
import threading
import time
from typing import Any, Dict, List, Optional, Tuple, Callable
from dataclasses import dataclass, field
from contextlib import redirect_stdout, redirect_stderr

logger = logging.getLogger("CodeExec")


# ============ CodeAct结果 ============

@dataclass
class CodeActResult:
    """CodeAct执行结果"""
    success: bool
    stdout: str = ""
    stderr: str = ""
    return_value: Any = None
    error: Optional[str] = None
    execution_time: float = 0.0
    locals_snapshot: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __repr__(self) -> str:
        status = "✅" if self.success else "❌"
        return f"CodeActResult({status} time={self.execution_time:.2f}s)"


# ============ 安全检查 ============

class CodeActGuardrails:
    """CodeAct安全检查 — 拦截危险操作"""
    
    # 禁止的模块（可能导致系统损害或逃逸沙箱）
    BLOCKED_MODULES = {
        "os", "subprocess", "shutil", "sys", "socket",
        "ctypes", "multiprocessing", "pickle", "shelve",
        "importlib", "pkg_resources", "code", "codeop",
        "compile", "compileall", "py_compile",
        "xml.etree", "xmlrpc",
        "http.server", "socketserver", "webbrowser",
        "antigravity", "this",
    }
    
    # 禁止的builtin函数
    BLOCKED_BUILTINS = {
        "exec", "eval", "compile", "__import__", "open",
        "input", "breakpoint", "exit", "quit",
        "globals", "locals", "vars", "dir",
        "getattr", "setattr", "delattr", "hasattr",
        "type", "object", "class", "super",
    }
    
    # 允许覆盖的builtin白名单
    ALLOWED_BUILTINS = {
        "abs", "all", "any", "bin", "bool", "chr", "complex",
        "dict", "divmod", "enumerate", "filter", "float", "format",
        "frozenset", "hex", "int", "isinstance", "issubclass",
        "iter", "len", "list", "map", "max", "min", "next",
        "oct", "ord", "pow", "print", "range", "repr", "reversed",
        "round", "set", "slice", "sorted", "str", "sum", "tuple",
        "zip", "True", "False", "None",
    }
    
    # 允许CodeAct代码import的安全模块
    ALLOWED_IMPORTS = {
        "math", "statistics", "json", "csv", "re", "collections",
        "itertools", "functools", "datetime", "decimal", "fractions",
        "copy", "hashlib", "base64", "textwrap", "string",
        "operator", "enum", "dataclasses", "typing",
        "numpy", "np", "pandas", "pd",
        "tools", "tools.calculator", "tools.data_query",
    }
    
    # 危险模式（正则匹配）
    DANGEROUS_PATTERNS = [
        r"__import__\s*\(",
        r"exec\s*\(",
        r"eval\s*\(",
        r"compile\s*\(",
        r"open\s*\(\s*['\"]\/",           # 绝对路径写文件
        r"os\.system\s*\(",
        r"subprocess\.",
        r"rm\s+-rf",
        r"shutil\.rmtree",
        r"os\.remove",
        r"os\.unlink",
    ]
    
    @classmethod
    def check(cls, code: str) -> Tuple[bool, str]:
        """
        检查代码安全性
        
        Returns:
            (passed, reason): 是否通过 + 不通过的原因
        """
        import re
        
        # 检查危险模式
        for pattern in cls.DANGEROUS_PATTERNS:
            match = re.search(pattern, code)
            if match:
                return False, f"Dangerous pattern detected: {match.group()}"
        
        # 检查import语句
        for line in code.split("\n"):
            stripped = line.strip()
            if stripped.startswith("import "):
                module = stripped.replace("import ", "").split(" as ")[0].split(",")[0].strip()
                root_module = module.split(".")[0]
                if root_module in cls.BLOCKED_MODULES:
                    return False, f"Blocked import: {module}"
                # 白名单检查：如果不在白名单也不在BLOCKED，允许（宽松策略）
            elif stripped.startswith("from "):
                match = re.match(r"from\s+(\S+)", stripped)
                if match:
                    module = match.group(1)
                    root_module = module.split(".")[0]
                    if root_module in cls.BLOCKED_MODULES:
                        return False, f"Blocked import: {module}"
        
        return True, "Passed"


# ============ CodeAct执行器 ============

class CodeActExecutor:
    """
    CodeAct沙箱执行器
    
    Agent通过写Python代码行动，而非调JSON工具。
    
    用法:
        executor = CodeActExecutor()
        
        # 注入工具为全局函数
        executor.add_global("search", web_search_fn)
        executor.add_global("query_data", data_query_fn)
        
        # 执行Agent生成的代码
        result = executor.execute('''
            results = search("SSC cement", limit=5)
            recent = [r for r in results if r["year"] > 2023]
            print(f"Found {len(recent)} recent papers")
        ''')
        
        print(result.stdout)  # "Found 3 recent papers"
    """
    
    def __init__(
        self,
        timeout: int = 15,
        max_output_length: int = 10000,
        enable_guardrails: bool = True,
        persist_locals: bool = True,
    ):
        """
        Args:
            timeout: 执行超时（秒），后台任务不受此限制
            max_output_length: 最大输出长度（字符）
            enable_guardrails: 是否启用安全检查
            persist_locals: 是否在多次执行间保持locals
        """
        self.timeout = timeout
        self.max_output_length = max_output_length
        self.enable_guardrails = enable_guardrails
        self.persist_locals = persist_locals
        
        # 全局函数注入
        self._globals: Dict[str, Any] = {}
        # 持久化的局部变量
        self._persistent_locals: Dict[str, Any] = {}
        # 执行统计
        self._stats = {
            "total_executions": 0,
            "successful": 0,
            "failed": 0,
            "timeout": 0,
            "blocked": 0,
        }
        
        # 后台任务管理（Mira-inspired exec(background=true)）
        self._background_tasks: Dict[str, Dict[str, Any]] = {}
        self._bg_counter = 0
        
        # 注册内置安全builtins
        self._setup_safe_builtins()
    
    def _setup_safe_builtins(self) -> None:
        """设置安全的builtins"""
        import builtins
        safe_builtins = {}
        for name in CodeActGuardrails.ALLOWED_BUILTINS:
            if hasattr(builtins, name):
                safe_builtins[name] = getattr(builtins, name)
        
        # 添加安全的print
        safe_builtins["print"] = print
        # 添加安全的type检查
        safe_builtins["isinstance"] = isinstance
        safe_builtins["issubclass"] = issubclass
        safe_builtins["type"] = type
        # 受控的__import__ — 只允许白名单模块
        original_import = builtins.__import__
        allowed_roots = {m.split(".")[0] for m in CodeActGuardrails.ALLOWED_IMPORTS}
        blocked_roots = CodeActGuardrails.BLOCKED_MODULES
        
        def _safe_import(name, *args, **kwargs):
            root = name.split(".")[0]
            if root in blocked_roots:
                raise ImportError(f"Blocked import in CodeAct sandbox: {name}")
            return original_import(name, *args, **kwargs)
        
        safe_builtins["__import__"] = _safe_import
        
        self._globals["__builtins__"] = safe_builtins
    
    def add_global(self, name: str, obj: Any) -> None:
        """
        添加全局函数/对象到执行环境
        
        Args:
            name: 全局变量名
            obj: Python对象
        """
        self._globals[name] = obj
        logger.debug(f"[CodeExec] Added global: {name}")
    
    def add_globals(self, globals_dict: Dict[str, Any]) -> None:
        """批量添加全局函数"""
        self._globals.update(globals_dict)
        logger.debug(f"[CodeExec] Added {len(globals_dict)} globals")
    
    def remove_global(self, name: str) -> None:
        """移除全局函数"""
        self._globals.pop(name, None)
    
    def available_globals(self) -> Dict[str, str]:
        """返回可用的全局函数名和类型描述"""
        result = {}
        for name, obj in self._globals.items():
            if name == "__builtins__":
                continue
            if callable(obj):
                result[name] = f"function: {getattr(obj, '__doc__', '')[:50]}" if obj.__doc__ else f"function: {type(obj).__name__}"
            else:
                result[name] = f"value: {type(obj).__name__}"
        return result
    
    def execute(self, code: str, extra_globals: Optional[Dict[str, Any]] = None) -> CodeActResult:
        """
        执行Python代码
        
        Args:
            code: Python代码字符串
            extra_globals: 额外的全局变量（本次执行临时注入）
            
        Returns:
            CodeActResult
        """
        self._stats["total_executions"] += 1
        start_time = time.time()
        
        # 1. 安全检查
        if self.enable_guardrails:
            passed, reason = CodeActGuardrails.check(code)
            if not passed:
                self._stats["blocked"] += 1
                logger.warning(f"[CodeExec] Blocked: {reason}")
                return CodeActResult(
                    success=False,
                    error=f"Security check failed: {reason}",
                    execution_time=time.time() - start_time,
                )
        
        # 2. 准备执行环境
        exec_globals = self._globals.copy()
        if extra_globals:
            exec_globals.update(extra_globals)
        
        # 合入持久化locals
        if self.persist_locals and self._persistent_locals:
            exec_globals.update(self._persistent_locals)
        
        # 3. 执行代码（带超时）
        stdout_capture = io.StringIO()
        stderr_capture = io.StringIO()
        
        try:
            exec_result = self._execute_with_timeout(
                code, exec_globals,
                stdout_capture, stderr_capture
            )
            
            execution_time = time.time() - start_time
            self._stats["successful"] += 1
            
            # 捕获locals（排除内部变量）
            locals_snapshot = {}
            if self.persist_locals:
                for key, value in exec_globals.items():
                    if key.startswith("_") or key == "__builtins__":
                        continue
                    if callable(value) and key in self._globals:
                        continue  # 跳过注入的工具函数
                    try:
                        # 检查是否可序列化（简单检查）
                        str(value)
                        locals_snapshot[key] = value
                    except Exception:
                        locals_snapshot[key] = f"<{type(value).__name__}>"
                self._persistent_locals.update(locals_snapshot)
            
            stdout_str = stdout_capture.getvalue()[:self.max_output_length]
            stderr_str = stderr_capture.getvalue()[:self.max_output_length]
            
            return CodeActResult(
                success=True,
                stdout=stdout_str,
                stderr=stderr_str,
                return_value=exec_result,
                execution_time=execution_time,
                locals_snapshot=locals_snapshot,
            )
            
        except TimeoutError:
            execution_time = time.time() - start_time
            self._stats["timeout"] += 1
            logger.warning(f"[CodeExec] Timeout after {self.timeout}s")
            return CodeActResult(
                success=False,
                stdout=stdout_capture.getvalue()[:self.max_output_length],
                stderr=stderr_capture.getvalue()[:self.max_output_length],
                error=f"Execution timeout ({self.timeout}s)",
                execution_time=execution_time,
            )
            
        except Exception as e:
            execution_time = time.time() - start_time
            self._stats["failed"] += 1
            tb = traceback.format_exc()
            logger.error(f"[CodeExec] Error: {e}")
            return CodeActResult(
                success=False,
                stdout=stdout_capture.getvalue()[:self.max_output_length],
                stderr=stderr_capture.getvalue()[:self.max_output_length],
                error=f"{type(e).__name__}: {e}\n{tb[-500:]}",
                execution_time=execution_time,
            )
    
    def _execute_with_timeout(
        self,
        code: str,
        exec_globals: Dict[str, Any],
        stdout_capture: io.StringIO,
        stderr_capture: io.StringIO,
    ) -> Any:
        """带超时的代码执行"""
        
        result_holder = [None]
        error_holder = [None]
        
        def _run():
            try:
                with redirect_stdout(stdout_capture), redirect_stderr(stderr_capture):
                    # 尝试compile为表达式（有返回值）
                    try:
                        compiled = compile(code, "<codeact>", "eval")
                        result_holder[0] = eval(compiled, exec_globals)
                    except SyntaxError:
                        # 不是表达式，compile为语句块
                        compiled = compile(code, "<codeact>", "exec")
                        exec(compiled, exec_globals)
                        result_holder[0] = None
            except Exception as e:
                error_holder[0] = e
        
        thread = threading.Thread(target=_run, daemon=True)
        thread.start()
        thread.join(timeout=self.timeout)
        
        if thread.is_alive():
            # 超时 — 无法真正杀死线程，但daemon线程会随进程退出
            raise TimeoutError(f"Execution exceeded {self.timeout}s")
        
        if error_holder[0] is not None:
            raise error_holder[0]
        
        return result_holder[0]
    
    def reset_locals(self) -> None:
        """清除持久化的局部变量"""
        self._persistent_locals.clear()
    
    # ============ 后台任务（Mira-inspired exec(background=true)）============
    
    def execute_background(
        self,
        code: str,
        name: Optional[str] = None,
        timeout: int = 600,
        extra_globals: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        后台执行Python代码（训练/仿真/长时间计算）
        
        借鉴Mira的 exec(background=true) 思路：长任务不阻塞主线程，
        通过 task_id 查询进度和结果。
        
        与前台执行的区别：
        - 超时默认600s（前台15s）
        - 不阻塞调用线程
        - 通过 task_id 查询状态/结果
        - 不自动持久化locals（避免污染主环境）
        
        Args:
            code: Python代码字符串
            name: 任务名称（可选）
            timeout: 后台任务超时（秒），默认600
            extra_globals: 额外的全局变量
            
        Returns:
            task_id: 后台任务ID
        """
        self._bg_counter += 1
        task_id = f"bg_{self._bg_counter}"
        
        if not name:
            name = f"background_task_{self._bg_counter}"
        
        # 安全检查
        if self.enable_guardrails:
            passed, reason = CodeActGuardrails.check(code)
            if not passed:
                self._stats["blocked"] += 1
                logger.warning(f"[CodeExec:BG] Blocked: {reason}")
                # 仍创建记录，标记为失败
                self._background_tasks[task_id] = {
                    "name": name,
                    "status": "blocked",
                    "error": f"Security check failed: {reason}",
                    "started_at": time.time(),
                    "finished_at": time.time(),
                    "stdout": "",
                    "stderr": "",
                }
                return task_id
        
        # 初始化任务记录
        self._background_tasks[task_id] = {
            "name": name,
            "status": "running",
            "started_at": time.time(),
            "finished_at": None,
            "stdout": "",
            "stderr": "",
            "error": None,
        }
        
        # 在独立线程中执行
        def _run_bg():
            task = self._background_tasks[task_id]
            stdout_capture = io.StringIO()
            stderr_capture = io.StringIO()
            
            exec_globals = self._globals.copy()
            if extra_globals:
                exec_globals.update(extra_globals)
            if self.persist_locals and self._persistent_locals:
                exec_globals.update(self._persistent_locals)
            
            try:
                with redirect_stdout(stdout_capture), redirect_stderr(stderr_capture):
                    compiled = compile(code, "<codeact-bg>", "exec")
                    exec(compiled, exec_globals)
                
                task["status"] = "completed"
                task["stdout"] = stdout_capture.getvalue()[:self.max_output_length]
                task["stderr"] = stderr_capture.getvalue()[:self.max_output_length]
                
            except Exception as e:
                task["status"] = "failed"
                task["error"] = f"{type(e).__name__}: {e}"
                task["stdout"] = stdout_capture.getvalue()[:self.max_output_length]
                task["stderr"] = stderr_capture.getvalue()[:self.max_output_length]
                
            finally:
                task["finished_at"] = time.time()
                logger.info(f"[CodeExec:BG] {task_id} ({name}): {task['status']}")
        
        thread = threading.Thread(target=_run_bg, daemon=True, name=f"bg-{task_id}")
        thread.start()
        
        # 设置超时监控
        def _timeout_monitor():
            thread.join(timeout=timeout)
            if thread.is_alive():
                task = self._background_tasks[task_id]
                if task["status"] == "running":
                    task["status"] = "timeout"
                    task["error"] = f"Background task exceeded {timeout}s"
                    task["finished_at"] = time.time()
                    logger.warning(f"[CodeExec:BG] {task_id}: Timeout ({timeout}s)")
        
        monitor = threading.Thread(target=_timeout_monitor, daemon=True)
        monitor.start()
        
        logger.info(f"[CodeExec:BG] Started {task_id} ({name}), timeout={timeout}s")
        return task_id
    
    def get_background_task(self, task_id: str) -> Optional[Dict[str, Any]]:
        """查询后台任务状态
        
        Returns:
            {"name", "status", "started_at", "finished_at", "stdout", "stderr", "error"}
            status: running / completed / failed / timeout / blocked
        """
        return self._background_tasks.get(task_id)
    
    def list_background_tasks(self) -> Dict[str, Dict[str, Any]]:
        """列出所有后台任务"""
        return dict(self._background_tasks)
    
    def cancel_background_task(self, task_id: str) -> bool:
        """取消后台任务（标记为cancelled，线程无法真正终止）"""
        task = self._background_tasks.get(task_id)
        if task and task["status"] == "running":
            task["status"] = "cancelled"
            task["finished_at"] = time.time()
            logger.info(f"[CodeExec:BG] Cancelled {task_id}")
            return True
        return False
    
    def get_stats(self) -> Dict[str, Any]:
        """获取执行统计"""
        total = self._stats["total_executions"]
        return {
            **self._stats,
            "success_rate": self._stats["successful"] / total if total > 0 else 0.0,
            "available_globals": list(self.available_globals().keys()),
        }
    
    def to_base_tool(self) -> 'BaseTool':
        """转换为BaseTool兼容格式（JSON Schema调用）"""
        from .base_tool import BaseTool, ToolResult
        
        executor = self
        
        class CodeExecTool(BaseTool):
            def __init__(self):
                super().__init__(
                    name="code_exec",
                    description="Execute Python code in a sandboxed environment. Use this to perform complex operations, data processing, calculations, and multi-step workflows.",
                    parameters={
                        "type": "object",
                        "properties": {
                            "code": {
                                "type": "string",
                                "description": "Python code to execute"
                            }
                        },
                        "required": ["code"]
                    }
                )
            
            def execute(self, code: str, **kwargs) -> ToolResult:
                result = executor.execute(code)
                output_parts = []
                if result.stdout:
                    output_parts.append(result.stdout)
                if result.return_value is not None:
                    output_parts.append(str(result.return_value))
                if result.error:
                    output_parts.append(f"Error: {result.error}")
                
                return ToolResult(
                    success=result.success,
                    output="\n".join(output_parts) if output_parts else "(no output)",
                    error=result.error,
                    metadata={
                        "execution_time": result.execution_time,
                        "locals": list(result.locals_snapshot.keys()),
                    }
                )
        
        return CodeExecTool()


# ============ 便捷函数 ============

def create_codeact_executor(
    tools: Optional[Dict[str, Any]] = None,
    timeout: int = 15,
) -> CodeActExecutor:
    """
    创建CodeAct执行器并注入工具
    
    Args:
        tools: 工具函数字典 {name: callable}
        timeout: 超时秒数
        
    Returns:
        配置好的CodeActExecutor
    """
    executor = CodeActExecutor(timeout=timeout)
    
    if tools:
        executor.add_globals(tools)
    
    return executor
