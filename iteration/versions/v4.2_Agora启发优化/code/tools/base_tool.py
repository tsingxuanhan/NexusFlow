# -*- coding: utf-8 -*-
"""
铉枢·炉守 工具调用框架
XuanHub Tool Framework - Base classes for extensible tools
"""

import logging
from typing import Dict, Any, Optional, List, Callable
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
import json

logger = logging.getLogger("ToolFramework")


@dataclass
class ToolResult:
    """工具执行结果"""
    success: bool
    output: Any = None
    error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


class BaseTool(ABC):
    """
    工具基类
    
    所有工具必须继承此类并实现 execute 方法
    """
    
    def __init__(
        self,
        name: str,
        description: str,
        parameters: Dict[str, Any] = None
    ):
        """
        初始化工具
        
        Args:
            name: 工具名称(英文, 用于函数调用)
            description: 工具描述(告诉LLM何时使用)
            parameters: JSON Schema格式的参数定义
        """
        self.name = name
        self.description = description
        self.parameters = parameters or {
            "type": "object",
            "properties": {},
            "required": []
        }
        
        logger.debug(f"[BaseTool] Registered tool: {name}")
    
    @abstractmethod
    def execute(self, **kwargs) -> ToolResult:
        """
        执行工具
        
        Returns:
            ToolResult: 执行结果
        """
        pass
    
    def validate(self, **kwargs) -> bool:
        """
        验证参数是否有效
        
        Returns:
            bool: 参数是否有效
        """
        required = self.parameters.get("required", [])
        for param in required:
            if param not in kwargs:
                logger.warning(f"[{self.name}] Missing required parameter: {param}")
                return False
        return True
    
    def to_openai_function(self) -> Dict[str, Any]:
        """转换为OpenAI函数调用格式"""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters
            }
        }
    
    def __repr__(self) -> str:
        return f"<{self.__class__.__name__}(name={self.name})>"


class ToolManager:
    """
    工具管理器
    
    功能:
    - 注册和发现工具
    - 参数验证
    - 执行追踪
    """
    
    def __init__(self):
        self.tools: Dict[str, BaseTool] = {}
        self._execution_history: List[Dict] = []
    
    def register(self, tool: BaseTool) -> None:
        """注册工具"""
        self.tools[tool.name] = tool
        logger.info(f"[ToolManager] Registered tool: {tool.name} (total: {len(self.tools)})")
    
    def unregister(self, name: str) -> bool:
        """注销工具"""
        if name in self.tools:
            del self.tools[name]
            logger.info(f"[ToolManager] Unregistered tool: {name}")
            return True
        return False
    
    def get(self, name: str) -> Optional[BaseTool]:
        """获取工具"""
        return self.tools.get(name)
    
    def list_tools(self) -> List[str]:
        """列出所有工具"""
        return list(self.tools.keys())
    
    def execute(self, name: str, **kwargs) -> ToolResult:
        """执行工具"""
        tool = self.get(name)
        if not tool:
            return ToolResult(
                success=False,
                error=f"Tool '{name}' not found"
            )
        
        # 验证参数
        if not tool.validate(**kwargs):
            return ToolResult(
                success=False,
                error="Parameter validation failed"
            )
        
        # 执行
        try:
            result = tool.execute(**kwargs)
            self._execution_history.append({
                "tool": name,
                "params": kwargs,
                "success": result.success,
                "timestamp": __import__('datetime').datetime.now().isoformat()
            })
            return result
        except Exception as e:
            logger.error(f"[ToolManager] Tool {name} execution failed: {e}")
            return ToolResult(
                success=False,
                error=str(e)
            )
    
    def get_all_functions(self) -> List[Dict[str, Any]]:
        """获取所有工具的OpenAI函数定义"""
        return [tool.to_openai_function() for tool in self.tools.values()]
    
    def get_history(self, limit: int = 100) -> List[Dict]:
        """获取执行历史"""
        return self._execution_history[-limit:]


# ============ 内置工具示例 ============

class WebSearchTool(BaseTool):
    """网络搜索工具 (示例)"""
    
    def __init__(self):
        super().__init__(
            name="web_search",
            description="Search the web for information. Use this when you need current events or facts not in your training data.",
            parameters={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The search query"
                    },
                    "max_results": {
                        "type": "integer",
                        "description": "Maximum number of results to return",
                        "default": 5
                    }
                },
                "required": ["query"]
            }
        )
    
    def execute(self, query: str, max_results: int = 5) -> ToolResult:
        """执行搜索"""
        # 这里需要接入实际的搜索API
        logger.info(f"[WebSearchTool] Searching for: {query}")
        
        return ToolResult(
            success=True,
            output=f"[Demo] Search results for '{query}': Found {max_results} results",
            metadata={"query": query, "max_results": max_results}
        )


class FileReaderTool(BaseTool):
    """文件读取工具 (示例)"""
    
    def __init__(self):
        super().__init__(
            name="file_reader",
            description="Read content from a file in the local filesystem.",
            parameters={
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Path to the file to read"
                    },
                    "max_lines": {
                        "type": "integer",
                        "description": "Maximum number of lines to read",
                        "default": 1000
                    }
                },
                "required": ["path"]
            }
        )
    
    def execute(self, path: str, max_lines: int = 1000) -> ToolResult:
        """读取文件"""
        try:
            with open(path, 'r', encoding='utf-8') as f:
                lines = []
                for i, line in enumerate(f):
                    if i >= max_lines:
                        break
                    lines.append(line.rstrip('\n'))
            
            content = '\n'.join(lines)
            return ToolResult(
                success=True,
                output=content,
                metadata={"path": path, "lines_read": len(lines)}
            )
        except FileNotFoundError:
            return ToolResult(success=False, error=f"File not found: {path}")
        except Exception as e:
            return ToolResult(success=False, error=str(e))


class CalculatorTool(BaseTool):
    """计算器工具 (示例)"""
    
    def __init__(self):
        super().__init__(
            name="calculator",
            description="Perform mathematical calculations.",
            parameters={
                "type": "object",
                "properties": {
                    "expression": {
                        "type": "string",
                        "description": "Mathematical expression to evaluate (e.g., '2 + 2' or 'sqrt(16)')"
                    }
                },
                "required": ["expression"]
            }
        )
    
    def execute(self, expression: str) -> ToolResult:
        """执行计算"""
        try:
            # 安全评估 (只支持基本运算)
            allowed = set("0123456789+-*/.() ")
            if not all(c in allowed for c in expression):
                return ToolResult(success=False, error="Invalid characters in expression")
            
            result = eval(expression)
            return ToolResult(
                success=True,
                output=result,
                metadata={"expression": expression}
            )
        except Exception as e:
            return ToolResult(success=False, error=str(e))
