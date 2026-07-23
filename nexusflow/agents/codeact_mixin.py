# -*- coding: utf-8 -*-
"""
CodeAct Mixin — 工具执行与注册
CodeActMixin extracted from base_agent.py
"""

import logging
from typing import Dict, Optional, Any

logger = logging.getLogger("BaseAgent")


class CodeActMixin:
    """CodeAct工具执行相关方法：init_codeact / execute_codeact / get_tool_registry / register_tool / codeact_status"""

    def init_codeact(self, extra_tools: Optional[Dict] = None) -> None:
        """
        初始化CodeAct执行器和工具注册中心

        Args:
            extra_tools: 额外工具函数字典 {name: callable}
        """
        from tools.code_exec import CodeActExecutor
        from tools.tool_registry import create_default_registry

        # 创建执行器
        self._codeact = CodeActExecutor(
            timeout=CODEACT_CONFIG.get("timeout", 15),
            max_output_length=CODEACT_CONFIG.get("max_output_length", 10000),
            enable_guardrails=CODEACT_CONFIG.get("enable_guardrails", True),
            persist_locals=CODEACT_CONFIG.get("persist_locals", True),
        )

        # 创建工具注册中心
        self._tool_registry = create_default_registry()

        # 注入工具到CodeAct执行环境
        globals_dict = self._tool_registry.to_codeact_globals()
        self._codeact.add_globals(globals_dict)

        # 注册CodeAct覆盖（直接使用工具函数而非BaseTool包装）
        from tools.web_search import search
        from tools.file_ops import read_file as _read_file, write_file as _write_file, list_dir
        from tools.data_query import query_data, register_dataset
        from tools.api_caller import http_get, http_post
        from tools.calculator import calculate, linear_regression
        from tools.git_ops import git_op
        from tools.pdf_reader import read_pdf
        from tools.browser import browse
        from tools.scheduler import schedule_task, cancel_task, list_scheduled_tasks

        codeact_globals = {
            "search": search,
            "read_file": _read_file,
            "write_file": _write_file,
            "list_dir": list_dir,
            "query_data": query_data,
            "register_dataset": register_dataset,
            "http_get": http_get,
            "http_post": http_post,
            "calculate": calculate,
            "linear_regression": linear_regression,
            "git_op": git_op,
            "read_pdf": read_pdf,
            "browse": browse,
            "schedule_task": schedule_task,
            "cancel_task": cancel_task,
            "list_scheduled_tasks": list_scheduled_tasks,
        }
        self._codeact.add_globals(codeact_globals)

        # 额外工具
        if extra_tools:
            self._codeact.add_globals(extra_tools)

        logger.info(f"[{self.name}] CodeAct initialized with {len(self._codeact.available_globals())} globals")

    def execute_codeact(self, code: str, extra_globals: Optional[Dict] = None) -> Any:
        """
        执行CodeAct代码

        Args:
            code: Python代码字符串
            extra_globals: 额外全局变量

        Returns:
            CodeActResult
        """
        if not hasattr(self, '_codeact'):
            self.init_codeact()

        result = self._codeact.execute(code, extra_globals=extra_globals)

        # 更新统计
        self.stats["codeact_executions"] = self.stats.get("codeact_executions", 0) + 1
        if not result.success:
            self.stats["codeact_failures"] = self.stats.get("codeact_failures", 0) + 1

        return result

    def get_tool_registry(self):
        """获取工具注册中心"""
        if not hasattr(self, '_tool_registry'):
            self.init_codeact()
        return self._tool_registry

    def register_tool(self, tool) -> None:
        """
        注册自定义工具

        Args:
            tool: BaseTool实例
        """
        if not hasattr(self, '_tool_registry'):
            self.init_codeact()
        self._tool_registry.register(tool)
        # 同时更新CodeAct环境
        globals_dict = self._tool_registry.to_codeact_globals()
        self._codeact.add_globals(globals_dict)

    def codeact_status(self) -> Dict[str, Any]:
        """获取CodeAct执行状态"""
        if not hasattr(self, '_codeact'):
            return {"initialized": False}

        return {
            "initialized": True,
            "codeact_stats": self._codeact.get_stats(),
            "tool_registry_stats": self._tool_registry.get_stats(),
        }
