---
name: tools-framework
description: >
  可扩展工具调用框架。BaseTool基类+ToolManager注册表，支持Pydantic参数校验、
  A2A工具桥接。当需要给Agent添加自定义工具、管理工具权限时使用。
license: MIT
compatibility: Python 3.9+, pydantic optional
metadata:
  version: "3.3.0"
  module: tools/base_tool.py
  lines: ~290
---

# Tools Framework

Agent 可扩展工具系统。

## 核心类

| 类 | 说明 |
|----|------|
| `BaseTool` | 工具基类，定义 name/description/parameters/execute |
| `ToolManager` | 工具注册表，管理工具生命周期和权限 |

## 创建自定义工具

```python
from tools.base_tool import BaseTool, ToolResult

class SearchTool(BaseTool):
    name = "search"
    description = "搜索互联网信息"

    def execute(self, query: str, max_results: int = 5) -> ToolResult:
        # 实现搜索逻辑
        return ToolResult(success=True, output="搜索结果...")
```

## 注册到Agent

```python
agent.register_a2a_action("search", search_tool.execute)
```

## 注意事项

- 工具权限通过 `ToolPermissionGuard` 控制
- ReAct 循环中自动查找已注册工具
