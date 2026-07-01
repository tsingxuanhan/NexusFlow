---
name: mcp-integration
description: >
  MCP(Model Context Protocol)集成模块。支持工具发现、调用和资源管理，
  可桥接A2A协议实现跨协议Agent通信。当需要接入MCP生态工具、
  桥接MCP与A2A时使用。
license: MIT
compatibility: Python 3.9+, mcp-sdk optional
metadata:
  version: "3.3.0"
  module: mcp_client.py
  lines: ~674
---

# MCP Integration

MCP 协议客户端，连接外部工具生态。

## 核心能力

- MCP 服务器发现和连接
- 工具列表获取和调用
- 资源读取
- A2A 协议桥接（规划中）

## 使用

```python
from mcp_client import MCPClient

client = MCPClient()
tools = client.list_tools()
result = client.call_tool("tool_name", params={"key": "value"})
```

## 注意事项

- MCP + A2A 桥接尚未完成，`mcp_client.py` 与 `a2a_protocol.py` 的打通待实现
- 需要 MCP 服务器运行中才能连接
