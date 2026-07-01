# -*- coding: utf-8 -*-
"""
铉枢·炉守 MCP协议支持
XuanHub MCP (Model Context Protocol) Integration
参考: Anthropic MCP SDK + CrewAI MCP Integration
https://modelcontextprotocol.io
"""

import logging
import json
import asyncio
from typing import Any, Optional, Dict, List, Callable, Type, Union
from dataclasses import dataclass, field
from enum import Enum
from abc import ABC, abstractmethod

logger = logging.getLogger("MCPClient")


class MCPError(Exception):
    """MCP相关错误"""
    pass


class MCPConnectionError(MCPError):
    """连接错误"""
    pass


class MCPProtocolError(MCPError):
    """协议错误"""
    pass


class MCPResourceType(Enum):
    """资源类型"""
    TEXT = "text"
    BINARY = "binary"
    PROMPT = "prompt"
    TOOL = "tool"


@dataclass
class MCPResource:
    """MCP资源"""
    uri: str
    name: str
    description: Optional[str] = None
    mime_type: Optional[str] = None
    
    def to_dict(self) -> Dict:
        return {
            "uri": self.uri,
            "name": self.name,
            "description": self.description,
            "mimeType": self.mime_type
        }


@dataclass
class MCPTool:
    """MCP工具定义"""
    name: str
    description: str
    input_schema: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict:
        return {
            "name": self.name,
            "description": self.description,
            "inputSchema": self.input_schema
        }


@dataclass
class MCPPrompt:
    """MCP提示模板"""
    name: str
    description: Optional[str] = None
    arguments: List[Dict[str, str]] = field(default_factory=list)
    template: str = ""
    
    def to_dict(self) -> Dict:
        return {
            "name": self.name,
            "description": self.description,
            "arguments": self.arguments
        }


@dataclass
class MCPMessage:
    """MCP消息"""
    jsonrpc: str = "2.0"
    id: Optional[Union[str, int]] = None
    method: Optional[str] = None
    params: Optional[Dict] = None
    result: Optional[Any] = None
    error: Optional[Dict] = None
    
    def to_dict(self) -> Dict:
        data = {"jsonrpc": self.jsonrpc}
        if self.id is not None:
            data["id"] = self.id
        if self.method is not None:
            data["method"] = self.method
        if self.params is not None:
            data["params"] = self.params
        if self.result is not None:
            data["result"] = self.result
        if self.error is not None:
            data["error"] = self.error
        return data
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'MCPMessage':
        return cls(
            jsonrpc=data.get("jsonrpc", "2.0"),
            id=data.get("id"),
            method=data.get("method"),
            params=data.get("params"),
            result=data.get("result"),
            error=data.get("error")
        )


class MCPTransport(ABC):
    """
    MCP传输层抽象
    
    支持:
    - Stdio (标准输入输出)
    - HTTP/SSE (服务器发送事件)
    - WebSocket
    """
    
    @abstractmethod
    async def connect(self) -> None:
        """建立连接"""
        pass
    
    @abstractmethod
    async def disconnect(self) -> None:
        """断开连接"""
        pass
    
    @abstractmethod
    async def send(self, message: MCPMessage) -> None:
        """发送消息"""
        pass
    
    @abstractmethod
    async def receive(self) -> MCPMessage:
        """接收消息"""
        pass
    
    @abstractmethod
    async def send_request(self, method: str, params: Optional[Dict] = None) -> Any:
        """发送请求并等待响应"""
        pass


class MCPClient:
    """
    MCP客户端
    
    功能:
    - 连接MCP服务器
    - 调用工具
    - 访问资源
    - 执行提示模板
    
    用法:
        client = MCPClient()
        await client.connect_stdio("npx", ["-y", "@playwright/mcp"])
        
        # 调用工具
        result = await client.call_tool("browse", {"url": "https://..."})
        
        # 访问资源
        content = await client.read_resource("file:///path/to/file")
        
        await client.disconnect()
    """
    
    def __init__(self):
        self.transport: Optional[MCPTransport] = None
        self._tools: Dict[str, MCPTool] = {}
        self._resources: Dict[str, MCPResource] = {}
        self._prompts: Dict[str, MCPPrompt] = {}
        self._capabilities: Dict = {}
        self._request_id = 0
        self._pending_requests: Dict[int, asyncio.Future] = {}
        
        logger.info("[MCPClient] Initialized")
    
    async def connect_stdio(
        self,
        command: str,
        args: List[str],
        env: Optional[Dict[str, str]] = None
    ) -> None:
        """
        通过stdio连接MCP服务器
        
        Args:
            command: 命令 (如 "npx", "python")
            args: 命令参数
            env: 环境变量
        """
        from subprocess import Popen, PIPE
        
        logger.info(f"[MCPClient] Connecting via stdio: {command} {' '.join(args)}")
        
        self.transport = StdioTransport(
            command=command,
            args=args,
            env=env
        )
        await self.transport.connect()
        
        # 初始化握手
        await self._initialize()
        
        # 获取可用工具和资源
        await self._list_tools()
        await self._list_resources()
        
        logger.info(f"[MCPClient] Connected. Tools: {len(self._tools)}, Resources: {len(self._resources)}")
    
    async def connect_http(
        self,
        url: str,
        headers: Optional[Dict[str, str]] = None
    ) -> None:
        """
        通过HTTP/SSE连接MCP服务器
        
        Args:
            url: 服务器URL
            headers: HTTP头
        """
        logger.info(f"[MCPClient] Connecting via HTTP: {url}")
        
        self.transport = HTTPSTransport(url=url, headers=headers or {})
        await self.transport.connect()
        
        await self._initialize()
        await self._list_tools()
        await self._list_resources()
    
    async def disconnect(self) -> None:
        """断开连接"""
        if self.transport:
            await self.transport.disconnect()
            self.transport = None
            self._tools.clear()
            self._resources.clear()
            logger.info("[MCPClient] Disconnected")
    
    async def _initialize(self) -> None:
        """初始化握手"""
        result = await self.transport.send_request("initialize", {
            "protocolVersion": "2024-11-05",
            "capabilities": {
                "roots": {"listChanged": True},
                "sampling": {}
            },
            "clientInfo": {
                "name": "xuanshu-agents",
                "version": "1.0.0"
            }
        })
        
        self._capabilities = result.get("capabilities", {})
        logger.info(f"[MCPClient] Server capabilities: {self._capabilities}")
    
    async def _list_tools(self) -> None:
        """列出可用工具"""
        result = await self.transport.send_request("tools/list")
        tools = result.get("tools", [])
        
        for tool_data in tools:
            tool = MCPTool(
                name=tool_data["name"],
                description=tool_data.get("description", ""),
                input_schema=tool_data.get("inputSchema", {})
            )
            self._tools[tool.name] = tool
        
        logger.debug(f"[MCPClient] Listed {len(self._tools)} tools")
    
    async def _list_resources(self) -> None:
        """列出可用资源"""
        result = await self.transport.send_request("resources/list")
        resources = result.get("resources", [])
        
        for res_data in resources:
            resource = MCPResource(
                uri=res_data["uri"],
                name=res_data["name"],
                description=res_data.get("description"),
                mime_type=res_data.get("mimeType")
            )
            self._resources[resource.uri] = resource
        
        logger.debug(f"[MCPClient] Listed {len(self._resources)} resources")
    
    async def call_tool(
        self,
        name: str,
        arguments: Optional[Dict[str, Any]] = None
    ) -> Any:
        """
        调用MCP工具
        
        Args:
            name: 工具名称
            arguments: 工具参数
            
        Returns:
            工具执行结果
        """
        if name not in self._tools:
            raise MCPError(f"Unknown tool: {name}")
        
        logger.info(f"[MCPClient] Calling tool: {name}")
        
        result = await self.transport.send_request("tools/call", {
            "name": name,
            "arguments": arguments or {}
        })
        
        # 解析结果
        content = result.get("content", [])
        if isinstance(content, list) and len(content) > 0:
            first_content = content[0]
            if first_content.get("type") == "text":
                return first_content["text"]
            return content
        
        return result
    
    async def read_resource(self, uri: str) -> Any:
        """
        读取MCP资源
        
        Args:
            uri: 资源URI
            
        Returns:
            资源内容
        """
        if uri not in self._resources:
            raise MCPError(f"Unknown resource: {uri}")
        
        logger.info(f"[MCPClient] Reading resource: {uri}")
        
        result = await self.transport.send_request("resources/read", {
            "uri": uri
        })
        
        content = result.get("contents", [])
        if isinstance(content, list) and len(content) > 0:
            first_content = content[0]
            if first_content.get("mimeType", "").startswith("text"):
                return first_content.get("text", "")
            return first_content
        
        return result
    
    def get_tools(self) -> List[MCPTool]:
        """获取所有工具定义"""
        return list(self._tools.values())
    
    def get_resources(self) -> List[MCPResource]:
        """获取所有资源定义"""
        return list(self._resources.values())
    
    def has_capability(self, capability: str) -> bool:
        """检查服务器是否支持某能力"""
        parts = capability.split(".")
        current = self._capabilities
        
        for part in parts:
            if part not in current:
                return False
            current = current[part]
        
        return True


class StdioTransport(MCPTransport):
    """Stdio传输层"""
    
    def __init__(
        self,
        command: str,
        args: List[str],
        env: Optional[Dict[str, str]] = None
    ):
        from subprocess import Popen, PIPE
        
        self.command = command
        self.args = args
        self.env = env
        self.process: Optional[Popen] = None
        self._request_id = 0
        self._pending: Dict[int, asyncio.Future] = {}
        self._reader_task: Optional[asyncio.Task] = None
    
    async def connect(self) -> None:
        """建立stdio连接"""
        import os
        
        env = os.environ.copy()
        if self.env:
            env.update(self.env)
        
        loop = asyncio.get_event_loop()
        
        self.process = await loop.run_in_executor(
            None,
            lambda: Popen(
                [self.command] + self.args,
                stdin=PIPE,
                stdout=PIPE,
                stderr=PIPE,
                env=env,
                text=False
            )
        )
        
        self._reader_task = asyncio.create_task(self._read_loop())
        logger.info(f"[StdioTransport] Process started (PID: {self.process.pid})")
    
    async def disconnect(self) -> None:
        """断开连接"""
        if self._reader_task:
            self._reader_task.cancel()
            try:
                await self._reader_task
            except asyncio.CancelledError:
                pass
        
        if self.process:
            self.process.terminate()
            await asyncio.sleep(0.5)
            if self.process.poll() is None:
                self.process.kill()
            self.process = None
        
        logger.info("[StdioTransport] Process terminated")
    
    async def send(self, message: MCPMessage) -> None:
        """发送消息"""
        if not self.process or not self.process.stdin:
            raise MCPConnectionError("Process not running")
        
        data = json.dumps(message.to_dict()) + "\n"
        self.process.stdin.write(data.encode("utf-8"))
        self.process.stdin.flush()
    
    async def receive(self) -> MCPMessage:
        """接收消息"""
        # 这个方法在实际实现中由_read_loop处理
        future = asyncio.Future()
        msg_id = self._request_id
        self._pending[msg_id] = future
        
        try:
            return await asyncio.wait_for(future, timeout=60)
        except asyncio.TimeoutError:
            self._pending.pop(msg_id, None)
            raise MCPConnectionError("Timeout waiting for response")
    
    async def send_request(self, method: str, params: Optional[Dict] = None) -> Any:
        """发送请求"""
        msg_id = self._request_id
        self._request_id += 1
        
        future = asyncio.Future()
        self._pending[msg_id] = future
        
        message = MCPMessage(
            id=msg_id,
            method=method,
            params=params
        )
        
        await self.send(message)
        
        try:
            response = await asyncio.wait_for(future, timeout=60)
            if "error" in response:
                raise MCPProtocolError(response["error"].get("message", "Unknown error"))
            return response.get("result", {})
        except asyncio.TimeoutError:
            self._pending.pop(msg_id, None)
            raise MCPConnectionError(f"Timeout for request: {method}")
    
    async def _read_loop(self) -> None:
        """持续读取stdout"""
        if not self.process or not self.process.stdout:
            return
        
        buffer = b""
        
        while True:
            try:
                chunk = await asyncio.get_event_loop().run_in_executor(
                    None,
                    self.process.stdout.read,
                    4096
                )
                
                if not chunk:
                    break
                
                buffer += chunk
                
                while b"\n" in buffer:
                    line, buffer = buffer.split(b"\n", 1)
                    try:
                        data = json.loads(line.decode("utf-8"))
                        message = MCPMessage.from_dict(data)
                        
                        if message.id is not None and message.id in self._pending:
                            future = self._pending.pop(message.id)
                            if not future.done():
                                future.set_result(data)
                        elif message.method and message.method.startswith("notifications/"):
                            # 处理通知消息
                            logger.debug(f"[StdioTransport] Received notification: {message.method}")
                        
                    except json.JSONDecodeError:
                        logger.warning(f"[StdioTransport] Invalid JSON: {line[:100]}")
            
            except Exception as e:
                logger.error(f"[StdioTransport] Read error: {e}")
                break
        
        logger.info("[StdioTransport] Read loop ended")


class HTTPSTransport(MCPTransport):
    """HTTP/SSE传输层"""
    
    def __init__(self, url: str, headers: Dict[str, str]):
        self.url = url
        self.headers = headers
        self._session = None
        self._request_id = 0
    
    async def connect(self) -> None:
        """建立HTTP连接"""
        import aiohttp
        
        self._session = aiohttp.ClientSession(headers=self.headers)
        logger.info(f"[HTTPSTransport] Connected to {self.url}")
    
    async def disconnect(self) -> None:
        """断开连接"""
        if self._session:
            await self._session.close()
            self._session = None
        logger.info("[HTTPSTransport] Disconnected")
    
    async def send(self, message: MCPMessage) -> None:
        """发送消息"""
        if not self._session:
            raise MCPConnectionError("Session not connected")
        
        async with self._session.post(
            self.url,
            json=message.to_dict()
        ) as response:
            response.raise_for_status()
    
    async def receive(self) -> MCPMessage:
        """接收消息 (SSE模式)"""
        if not self._session:
            raise MCPConnectionError("Session not connected")
        
        # SSE接收逻辑
        async with self._session.get(
            self.url,
            headers={"Accept": "text/event-stream"}
        ) as response:
            async for line in response.content:
                if line.startswith(b"data: "):
                    data = json.loads(line[6:])
                    return MCPMessage.from_dict(data)
        
        raise MCPConnectionError("No message received")
    
    async def send_request(self, method: str, params: Optional[Dict] = None) -> Any:
        """发送请求"""
        msg_id = self._request_id
        self._request_id += 1
        
        message = MCPMessage(
            id=msg_id,
            method=method,
            params=params
        )
        
        async with self._session.post(
            self.url,
            json=message.to_dict()
        ) as response:
            response.raise_for_status()
            data = await response.json()
            
            if "error" in data:
                raise MCPProtocolError(data["error"].get("message", "Unknown error"))
            
            return data.get("result", {})


class MCPToolAdapter:
    """
    MCP工具适配器
    
    将MCP工具转换为Agent可调用的函数
    """
    
    def __init__(self, mcp_client: MCPClient):
        self.client = mcp_client
        self._tool_functions: Dict[str, Callable] = {}
        
        # 为每个MCP工具创建Python函数
        for tool in mcp_client.get_tools():
            self._tool_functions[tool.name] = self._create_tool_function(tool)
    
    def _create_tool_function(self, tool: MCPTool) -> Callable:
        """为工具创建Python函数"""
        async def func(**kwargs) -> Any:
            return await self.client.call_tool(tool.name, kwargs)
        
        func.__name__ = tool.name
        func.__doc__ = f"{tool.description}\n\nSchema: {json.dumps(tool.input_schema, indent=2)}"
        
        return func
    
    def get_function(self, name: str) -> Optional[Callable]:
        """获取工具函数"""
        return self._tool_functions.get(name)
    
    def get_all_functions(self) -> Dict[str, Callable]:
        """获取所有工具函数"""
        return self._tool_functions.copy()


# 便捷函数
async def quick_connect(
    command: str,
    args: List[str],
    env: Optional[Dict[str, str]] = None
) -> MCPClient:
    """
    快速连接MCP服务器
    
    用法:
        client = await quick_connect("npx", ["-y", "@playwright/mcp"])
        
        # 调用工具
        result = await client.call_tool("browse", {"url": "https://example.com"})
        
        await client.disconnect()
    """
    client = MCPClient()
    await client.connect_stdio(command, args, env)
    return client
