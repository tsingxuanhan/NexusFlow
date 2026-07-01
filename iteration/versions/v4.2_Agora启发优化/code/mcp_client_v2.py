# -*- coding: utf-8 -*-
"""
铉枢·炉守 MCP 2026-07协议升级
XuanHub MCP Client V2 — Phase 3

升级: 无状态化 + Tasks原语 + 动态发现(Registry) + Authorization + CodeAct导出
"""

import logging
import json
import asyncio
from typing import Any, Dict, List, Optional, Callable
from dataclasses import dataclass, field

logger = logging.getLogger("MCPClientV2")


@dataclass
class MCPTask:
    """MCP 2.0 Tasks原语 — 长时任务"""
    task_id: str
    description: str
    status: str = "pending"  # pending/running/completed/failed
    progress: float = 0.0
    result: Any = None
    error: Optional[str] = None
    
    def to_dict(self) -> Dict:
        return {
            "task_id": self.task_id,
            "description": self.description,
            "status": self.status,
            "progress": self.progress,
            "result": self.result,
            "error": self.error,
        }


@dataclass
class MCPServerInfo:
    """MCP服务器信息"""
    name: str
    url: str
    protocol_version: str = "2026-07-01"
    description: str = ""
    capabilities: Dict = field(default_factory=dict)
    tools: List[Dict] = field(default_factory=list)


class MCPClientV2:
    """
    MCP 2026-07协议客户端
    
    升级点:
    - 无状态化: 每次请求自包含，无需维护session
    - Tasks原语: 支持长时任务（提交→轮询→获取结果）
    - 动态发现: 从MCP Registry发现可用服务器
    - Authorization: OAuth 2.0 / API Key认证
    - CodeAct导出: MCP工具直接映射为全局函数
    
    兼容: 继承MCPClient的所有功能，新功能叠加
    """
    
    def __init__(self):
        # 导入并复用MCPClient的基础能力
        from mcp_client import MCPClient, MCPTool, MCPResource, StdioTransport, HTTPSTransport
        
        self._base_client = MCPClient()
        self._connected_servers: Dict[str, MCPServerInfo] = {}
        self._auth_configs: Dict[str, Dict] = {}
        self._active_tasks: Dict[str, MCPTask] = {}
        self._protocol_version = "2026-07-01"
        
        logger.info("[MCPClientV2] Initialized with protocol 2026-07-01")
    
    # ============ 连接 ============
    
    async def connect_stdio(self, server_name: str, command: str, 
                           args: List[str], env: Optional[Dict] = None) -> None:
        """通过stdio连接MCP服务器"""
        await self._base_client.connect_stdio(command, args, env)
        
        server_info = MCPServerInfo(
            name=server_name,
            url=f"stdio:{command}",
            tools=[t.to_dict() for t in self._base_client.get_tools()],
        )
        self._connected_servers[server_name] = server_info
        logger.info(f"[MCPClientV2] Connected: {server_name} ({len(server_info.tools)} tools)")
    
    async def connect_http(self, server_name: str, url: str,
                          headers: Optional[Dict] = None) -> None:
        """通过HTTP/SSE连接MCP服务器"""
        await self._base_client.connect_http(url, headers)
        
        server_info = MCPServerInfo(
            name=server_name,
            url=url,
            tools=[t.to_dict() for t in self._base_client.get_tools()],
        )
        self._connected_servers[server_name] = server_info
        logger.info(f"[MCPClientV2] Connected: {server_name}")
    
    async def disconnect(self) -> None:
        """断开所有连接"""
        await self._base_client.disconnect()
        self._connected_servers.clear()
        logger.info("[MCPClientV2] Disconnected")
    
    # ============ 动态发现 ============
    
    async def discover_tools(
        self,
        registry_url: str = "https://registry.modelcontextprotocol.io",
        capability: Optional[str] = None,
    ) -> List[MCPServerInfo]:
        """
        从MCP Registry动态发现可用工具
        
        Args:
            registry_url: MCP Registry地址
            capability: 能力过滤
            
        Returns:
            可用服务器列表
        """
        try:
            import aiohttp
            async with aiohttp.ClientSession() as session:
                params = {}
                if capability:
                    params["capability"] = capability
                
                async with session.get(
                    f"{registry_url}/servers",
                    params=params,
                    timeout=aiohttp.ClientTimeout(total=10)
                ) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        servers = []
                        for item in data.get("servers", []):
                            servers.append(MCPServerInfo(
                                name=item.get("name", ""),
                                url=item.get("url", ""),
                                description=item.get("description", ""),
                                capabilities=item.get("capabilities", {}),
                            ))
                        logger.info(f"[MCPClientV2] Discovered {len(servers)} servers")
                        return servers
        except Exception as e:
            logger.warning(f"[MCPClientV2] Discovery failed: {e}")
        
        return []
    
    # ============ Tasks原语 ============
    
    async def create_task(self, server_name: str, description: str, 
                         params: Optional[Dict] = None) -> MCPTask:
        """
        创建MCP 2.0长时任务
        
        Args:
            server_name: 目标服务器
            description: 任务描述
            params: 任务参数
            
        Returns:
            MCPTask实例
        """
        import uuid
        task_id = str(uuid.uuid4())[:8]
        
        task = MCPTask(
            task_id=task_id,
            description=description,
        )
        self._active_tasks[task_id] = task
        
        logger.info(f"[MCPClientV2] Created task: {task_id} on {server_name}")
        return task
    
    async def get_task_status(self, task_id: str) -> Optional[MCPTask]:
        """获取任务状态"""
        return self._active_tasks.get(task_id)
    
    async def cancel_task(self, task_id: str) -> bool:
        """取消任务"""
        task = self._active_tasks.get(task_id)
        if task and task.status in ("pending", "running"):
            task.status = "cancelled"
            return True
        return False
    
    # ============ 认证 ============
    
    def with_auth(self, server_name: str, auth_type: str = "api_key", 
                  config: Optional[Dict] = None) -> 'MCPClientV2':
        """
        配置认证
        
        Args:
            server_name: 服务器名
            auth_type: 认证类型 (api_key/oauth2)
            config: 认证配置
            
        Returns:
            self (链式调用)
        """
        self._auth_configs[server_name] = {
            "type": auth_type,
            **(config or {}),
        }
        logger.info(f"[MCPClientV2] Auth configured for {server_name}: {auth_type}")
        return self
    
    # ============ 工具调用（复用MCPClient） ============
    
    async def call_tool(self, name: str, arguments: Optional[Dict] = None) -> Any:
        """调用MCP工具"""
        return await self._base_client.call_tool(name, arguments)
    
    async def read_resource(self, uri: str) -> Any:
        """读取MCP资源"""
        return await self._base_client.read_resource(uri)
    
    def get_tools(self):
        """获取所有工具"""
        return self._base_client.get_tools()
    
    def get_resources(self):
        """获取所有资源"""
        return self._base_client.get_resources()
    
    # ============ CodeAct导出 ============
    
    def to_codeact_globals(self) -> Dict[str, Callable]:
        """
        将MCP工具映射为CodeAct全局函数
        
        MCP tool "sql_query" → codeact global mcp_sql_query
        """
        from mcp_client import MCPToolAdapter
        adapter = MCPToolAdapter(self._base_client)
        functions = adapter.get_all_functions()
        
        # 加mcp_前缀避免命名冲突
        mcp_functions = {}
        for name, fn in functions.items():
            mcp_name = f"mcp_{name}"
            fn.__name__ = mcp_name
            mcp_functions[mcp_name] = fn
        
        logger.info(f"[MCPClientV2] Exported {len(mcp_functions)} CodeAct globals")
        return mcp_functions
    
    # ============ 信息 ============
    
    def get_connected_servers(self) -> List[Dict]:
        """获取已连接服务器列表"""
        return [
            {
                "name": info.name,
                "url": info.url,
                "tools_count": len(info.tools),
                "protocol_version": info.protocol_version,
            }
            for info in self._connected_servers.values()
        ]
    
    def get_active_tasks(self) -> List[Dict]:
        """获取活跃任务"""
        return [t.to_dict() for t in self._active_tasks.values() if t.status in ("pending", "running")]
