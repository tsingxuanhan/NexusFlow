# -*- coding: utf-8 -*-
"""
铉枢·炉守 工具注册中心
XuanHub Tool Registry — Phase 3

统一管理本地工具(BaseTool) + MCP远程工具 + CodeAct全局函数
提供发现、执行、CodeAct导出一体化入口。
"""

import logging
from typing import Any, Dict, List, Optional, Union, Callable
from dataclasses import dataclass, field

from .base_tool import BaseTool, ToolResult

logger = logging.getLogger("ToolRegistry")


class ToolRegistry:
    """
    工具注册中心
    
    功能:
    - 注册本地工具(BaseTool)和MCP远程工具
    - 按能力发现工具
    - 统一执行入口(带Guardrail检查)
    - 导出所有工具为CodeAct全局函数
    
    用法:
        registry = ToolRegistry()
        
        # 注册本地工具
        registry.register(WebSearchTool())
        registry.register(FileOpsTool())
        
        # 注册MCP远程工具
        registry.register_mcp("playwright", mcp_client)
        
        # 发现工具
        tools = registry.discover("search")
        
        # 执行工具
        result = registry.execute("web_search", {"query": "SSC cement"})
        
        # 导出CodeAct全局函数
        globals_dict = registry.to_codeact_globals()
        executor.add_globals(globals_dict)
    """
    
    def __init__(self, enable_guardrails: bool = True):
        self._local_tools: Dict[str, BaseTool] = {}
        self._mcp_tools: Dict[str, Dict[str, Any]] = {}  # server_name -> {tool_name: MCPTool}
        self._codeact_overrides: Dict[str, Callable] = {}  # CodeAct全局函数覆盖
        self._execution_log: List[Dict] = []
        self._enable_guardrails = enable_guardrails
        
        logger.info("[ToolRegistry] Initialized")
    
    # ============ 注册 ============
    
    def register(self, tool: BaseTool) -> None:
        """注册本地工具"""
        self._local_tools[tool.name] = tool
        logger.info(f"[ToolRegistry] Registered local tool: {tool.name} (total: {len(self._local_tools)})")
    
    def register_many(self, tools: List[BaseTool]) -> None:
        """批量注册本地工具"""
        for tool in tools:
            self.register(tool)
    
    def register_mcp(self, server_name: str, mcp_client: Any) -> None:
        """
        注册MCP远程工具
        
        Args:
            server_name: MCP服务器名称
            mcp_client: MCPClient实例
        """
        mcp_tools = {}
        for tool in mcp_client.get_tools():
            mcp_tools[tool.name] = {
                "tool": tool,
                "server": server_name,
                "client": mcp_client,
            }
            logger.debug(f"[ToolRegistry] Registered MCP tool: {tool.name} from {server_name}")
        
        self._mcp_tools[server_name] = mcp_tools
        logger.info(f"[ToolRegistry] Registered MCP server: {server_name} ({len(mcp_tools)} tools)")
    
    def register_codeact_override(self, name: str, fn: Callable) -> None:
        """
        注册CodeAct全局函数覆盖
        
        当工具同时有BaseTool和CodeAct全局函数时，
        CodeAct模式使用覆盖函数，JSON模式使用BaseTool。
        """
        self._codeact_overrides[name] = fn
        logger.debug(f"[ToolRegistry] Registered CodeAct override: {name}")
    
    def unregister(self, name: str) -> bool:
        """注销工具"""
        if name in self._local_tools:
            del self._local_tools[name]
            self._codeact_overrides.pop(name, None)
            logger.info(f"[ToolRegistry] Unregistered: {name}")
            return True
        return False
    
    # ============ 发现 ============
    
    def discover(self, capability: str) -> List[Dict[str, Any]]:
        """
        按能力发现工具
        
        Args:
            capability: 能力关键词(如"search", "file", "data")
            
        Returns:
            匹配的工具信息列表
        """
        results = []
        keyword = capability.lower()
        
        # 搜索本地工具
        for name, tool in self._local_tools.items():
            if (keyword in name.lower() or 
                keyword in tool.description.lower()):
                results.append({
                    "name": name,
                    "type": "local",
                    "description": tool.description,
                })
        
        # 搜索MCP工具
        for server_name, tools in self._mcp_tools.items():
            for tool_name, tool_info in tools.items():
                if (keyword in tool_name.lower() or
                    keyword in tool_info["tool"].description.lower()):
                    results.append({
                        "name": tool_name,
                        "type": "mcp",
                        "server": server_name,
                        "description": tool_info["tool"].description,
                    })
        
        logger.debug(f"[ToolRegistry] Discover '{capability}': {len(results)} matches")
        return results
    
    def get(self, name: str) -> Optional[BaseTool]:
        """获取本地工具"""
        return self._local_tools.get(name)
    
    def list_tools(self) -> List[Dict[str, str]]:
        """列出所有工具"""
        tools = []
        for name, tool in self._local_tools.items():
            tools.append({"name": name, "type": "local", "description": tool.description})
        for server_name, mcp_tools in self._mcp_tools.items():
            for tool_name, tool_info in mcp_tools.items():
                tools.append({"name": tool_name, "type": "mcp", "server": server_name,
                              "description": tool_info["tool"].description})
        return tools
    
    def get_all_functions(self) -> List[Dict[str, Any]]:
        """获取所有工具的OpenAI函数定义"""
        functions = []
        for tool in self._local_tools.values():
            functions.append(tool.to_openai_function())
        for server_name, mcp_tools in self._mcp_tools.items():
            for tool_name, tool_info in mcp_tools.items():
                mcp_tool = tool_info["tool"]
                functions.append({
                    "type": "function",
                    "function": {
                        "name": f"mcp_{tool_name}",
                        "description": f"[{server_name}] {mcp_tool.description}",
                        "parameters": mcp_tool.input_schema,
                    }
                })
        return functions
    
    # ============ 执行 ============
    
    def execute(
        self,
        tool_name: str,
        params: Dict[str, Any],
        guardrails: bool = True,
    ) -> ToolResult:
        """
        统一执行入口
        
        Args:
            tool_name: 工具名
            params: 参数
            guardrails: 是否检查Guardrail
            
        Returns:
            ToolResult
        """
        # 1. 查找本地工具
        tool = self._local_tools.get(tool_name)
        if tool:
            # Guardrail检查
            if guardrails and self._enable_guardrails:
                from guardrails import ToolGuardrail
                # 简化: 只做参数验证
                if not tool.validate(**params):
                    return ToolResult(success=False, error="Parameter validation failed")
            
            result = tool.execute(**params)
            self._execution_log.append({
                "tool": tool_name,
                "params": params,
                "success": result.success,
            })
            return result
        
        # 2. 查找MCP工具
        for server_name, mcp_tools in self._mcp_tools.items():
            if tool_name in mcp_tools:
                tool_info = mcp_tools[tool_name]
                try:
                    import asyncio
                    client = tool_info["client"]
                    loop = asyncio.get_event_loop()
                    if loop.is_running():
                        # 已在async上下文中，用ensure_future
                        import concurrent.futures
                        with concurrent.futures.ThreadPoolExecutor() as pool:
                            future = pool.submit(
                                asyncio.run,
                                client.call_tool(tool_name, params)
                            )
                            output = future.result(timeout=60)
                    else:
                        output = loop.run_until_complete(client.call_tool(tool_name, params))
                    
                    self._execution_log.append({
                        "tool": tool_name,
                        "type": "mcp",
                        "server": server_name,
                        "success": True,
                    })
                    return ToolResult(success=True, output=output)
                except Exception as e:
                    self._execution_log.append({
                        "tool": tool_name,
                        "type": "mcp",
                        "server": server_name,
                        "success": False,
                    })
                    return ToolResult(success=False, error=f"MCP error: {e}")
        
        return ToolResult(success=False, error=f"Tool not found: {tool_name}")
    
    # ============ CodeAct导出 ============
    
    def to_codeact_globals(self) -> Dict[str, Callable]:
        """
        导出所有工具为CodeAct全局函数
        
        优先使用codeact_overrides，否则从BaseTool自动包装。
        MCP工具统一加"mcp_"前缀。
        """
        globals_dict = {}
        
        # 本地工具
        for name, tool in self._local_tools.items():
            if name in self._codeact_overrides:
                globals_dict[name] = self._codeact_overrides[name]
            else:
                # 从BaseTool自动包装为Python函数
                globals_dict[name] = self._wrap_base_tool(tool)
        
        # MCP工具
        for server_name, mcp_tools in self._mcp_tools.items():
            for tool_name, tool_info in mcp_tools.items():
                globals_dict[f"mcp_{tool_name}"] = self._wrap_mcp_tool(
                    tool_name, tool_info["client"]
                )
        
        logger.info(f"[ToolRegistry] Exported {len(globals_dict)} CodeAct globals")
        return globals_dict
    
    def _wrap_base_tool(self, tool: BaseTool) -> Callable:
        """将BaseTool包装为CodeAct可调用的Python函数"""
        def codeact_fn(**kwargs) -> Any:
            result = tool.execute(**kwargs)
            if result.success:
                return result.output
            else:
                raise RuntimeError(f"Tool {tool.name} failed: {result.error}")
        
        codeact_fn.__name__ = tool.name
        codeact_fn.__doc__ = tool.description
        return codeact_fn
    
    def _wrap_mcp_tool(self, tool_name: str, client: Any) -> Callable:
        """将MCP工具包装为CodeAct可调用的Python函数"""
        def codeact_fn(**kwargs) -> Any:
            try:
                import asyncio
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    import concurrent.futures
                    with concurrent.futures.ThreadPoolExecutor() as pool:
                        future = pool.submit(
                            asyncio.run,
                            client.call_tool(tool_name, kwargs)
                        )
                        return future.result(timeout=60)
                else:
                    return loop.run_until_complete(client.call_tool(tool_name, kwargs))
            except Exception as e:
                raise RuntimeError(f"MCP tool {tool_name} failed: {e}")
        
        codeact_fn.__name__ = f"mcp_{tool_name}"
        codeact_fn.__doc__ = f"MCP tool: {tool_name}"
        return codeact_fn
    
    # ============ 统计 ============
    
    def get_stats(self) -> Dict[str, Any]:
        """获取注册统计"""
        mcp_count = sum(len(tools) for tools in self._mcp_tools.values())
        return {
            "local_tools": len(self._local_tools),
            "mcp_tools": mcp_count,
            "mcp_servers": len(self._mcp_tools),
            "codeact_overrides": len(self._codeact_overrides),
            "total_executions": len(self._execution_log),
            "tool_names": list(self._local_tools.keys()),
        }
    
    def get_execution_log(self, limit: int = 100) -> List[Dict]:
        """获取执行日志"""
        return self._execution_log[-limit:]


def create_default_registry() -> ToolRegistry:
    """
    创建默认工具注册中心（预注册所有内置工具）
    
    Returns:
        配置好的ToolRegistry
    """
    registry = ToolRegistry()
    
    # 导入并注册内置工具
    try:
        from .web_search import WebSearchTool
        registry.register(WebSearchTool())
    except ImportError:
        logger.warning("[ToolRegistry] WebSearchTool not available")
    
    try:
        from .file_ops import FileOpsTool
        registry.register(FileOpsTool())
    except ImportError:
        logger.warning("[ToolRegistry] FileOpsTool not available")
    
    try:
        from .data_query import DataQueryTool
        registry.register(DataQueryTool())
    except ImportError:
        logger.warning("[ToolRegistry] DataQueryTool not available")
    
    try:
        from .api_caller import APICallerTool
        registry.register(APICallerTool())
    except ImportError:
        logger.warning("[ToolRegistry] APICallerTool not available")
    
    try:
        from .calculator import CalculatorTool
        registry.register(CalculatorTool())
    except ImportError:
        logger.warning("[ToolRegistry] CalculatorTool not available")
    
    return registry
