# -*- coding: utf-8 -*-
"""
铉枢·炉守 MCP Server模式
XuanHub MCP Server — Phase 3

将NexusFlow的能力暴露为MCP Server，被其他Agent/框架调用。
"""

import json
import logging
from typing import Any, Dict, List, Optional, Callable
from dataclasses import dataclass, field

logger = logging.getLogger("MCPServer")


@dataclass
class MCPServerTool:
    """MCP Server工具定义"""
    name: str
    description: str
    handler: Callable
    input_schema: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict:
        return {
            "name": self.name,
            "description": self.description,
            "inputSchema": self.input_schema,
        }


@dataclass
class MCPServerResource:
    """MCP Server资源定义"""
    uri: str
    name: str
    description: str = ""
    mime_type: str = "text/plain"
    handler: Optional[Callable] = None
    
    def to_dict(self) -> Dict:
        return {
            "uri": self.uri,
            "name": self.name,
            "description": self.description,
            "mimeType": self.mime_type,
        }


class XuanshuMCPServer:
    """
    将NexusFlow的能力暴露为MCP Server
    
    功能:
    - 注册Agent能力为MCP工具
    - 注册知识库为MCP资源
    - 处理MCP协议请求（JSON-RPC 2.0）
    - FastAPI/stdio运行模式
    
    对外暴露:
    - research_topic: 文献研究
    - verify_claim: 交叉验证
    - generate_code: 代码生成
    - answer_question: 领域问答
    - plan_task: 任务分解
    - codeact_exec: CodeAct代码执行
    """
    
    def __init__(self, name: str = "nexusflow", version: str = "2.7.0"):
        self.name = name
        self.version = version
        self._tools: Dict[str, MCPServerTool] = {}
        self._resources: Dict[str, MCPServerResource] = {}
        self._request_handlers: Dict[str, Callable] = {}
        
        # 注册标准MCP请求处理器
        self._request_handlers = {
            "initialize": self._handle_initialize,
            "tools/list": self._handle_tools_list,
            "tools/call": self._handle_tools_call,
            "resources/list": self._handle_resources_list,
            "resources/read": self._handle_resources_read,
        }
        
        logger.info(f"[MCPServer] {name} v{version} initialized")
    
    # ============ 工具注册 ============
    
    def register_tool(
        self,
        name: str,
        description: str,
        handler: Callable,
        input_schema: Optional[Dict] = None,
    ) -> None:
        """注册MCP工具"""
        tool = MCPServerTool(
            name=name,
            description=description,
            handler=handler,
            input_schema=input_schema or {
                "type": "object",
                "properties": {},
                "required": []
            },
        )
        self._tools[name] = tool
        logger.info(f"[MCPServer] Registered tool: {name}")
    
    def register_resource(
        self,
        uri: str,
        name: str,
        description: str = "",
        handler: Optional[Callable] = None,
        mime_type: str = "text/plain",
    ) -> None:
        """注册MCP资源"""
        resource = MCPServerResource(
            uri=uri,
            name=name,
            description=description,
            mime_type=mime_type,
            handler=handler,
        )
        self._resources[uri] = resource
        logger.info(f"[MCPServer] Registered resource: {name}")
    
    def register_agent_capabilities(self, agent: Any) -> None:
        """
        从Agent实例自动注册能力为MCP工具
        
        Args:
            agent: BaseAgent实例
        """
        # 注册chat能力
        if hasattr(agent, 'chat'):
            self.register_tool(
                name=f"{agent.name}_chat",
                description=f"Chat with {agent.name} agent",
                handler=lambda msg: agent.chat(msg),
                input_schema={
                    "type": "object",
                    "properties": {
                        "message": {"type": "string", "description": "Message to send"}
                    },
                    "required": ["message"]
                },
            )
        
        # 注册plan能力
        if hasattr(agent, 'plan'):
            self.register_tool(
                name=f"{agent.name}_plan",
                description=f"Plan a task using {agent.name}",
                handler=lambda task: agent.plan(task),
                input_schema={
                    "type": "object",
                    "properties": {
                        "task": {"type": "string", "description": "Task description"}
                    },
                    "required": ["task"]
                },
            )
        
        logger.info(f"[MCPServer] Registered capabilities from {agent.name}")
    
    # ============ MCP协议处理 ============
    
    def handle_request(self, request: Dict) -> Dict:
        """
        处理MCP JSON-RPC请求
        
        Args:
            request: JSON-RPC请求
            
        Returns:
            JSON-RPC响应
        """
        method = request.get("method", "")
        params = request.get("params", {})
        req_id = request.get("id")
        
        handler = self._request_handlers.get(method)
        if not handler:
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "error": {"code": -32601, "message": f"Method not found: {method}"}
            }
        
        try:
            result = handler(params)
            return {"jsonrpc": "2.0", "id": req_id, "result": result}
        except Exception as e:
            logger.error(f"[MCPServer] Error handling {method}: {e}")
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "error": {"code": -32603, "message": str(e)}
            }
    
    def _handle_initialize(self, params: Dict) -> Dict:
        """处理initialize请求"""
        return {
            "protocolVersion": "2026-07-01",
            "capabilities": {
                "tools": {"listChanged": False},
                "resources": {"subscribe": False, "listChanged": False},
            },
            "serverInfo": {
                "name": self.name,
                "version": self.version,
            }
        }
    
    def _handle_tools_list(self, params: Dict) -> Dict:
        """处理tools/list请求"""
        return {
            "tools": [t.to_dict() for t in self._tools.values()]
        }
    
    def _handle_tools_call(self, params: Dict) -> Dict:
        """处理tools/call请求"""
        tool_name = params.get("name", "")
        arguments = params.get("arguments", {})
        
        tool = self._tools.get(tool_name)
        if not tool:
            return {
                "content": [{"type": "text", "text": f"Unknown tool: {tool_name}"}],
                "isError": True,
            }
        
        try:
            result = tool.handler(**arguments)
            content = str(result) if result is not None else ""
            return {
                "content": [{"type": "text", "text": content}],
                "isError": False,
            }
        except Exception as e:
            return {
                "content": [{"type": "text", "text": f"Error: {e}"}],
                "isError": True,
            }
    
    def _handle_resources_list(self, params: Dict) -> Dict:
        """处理resources/list请求"""
        return {
            "resources": [r.to_dict() for r in self._resources.values()]
        }
    
    def _handle_resources_read(self, params: Dict) -> Dict:
        """处理resources/read请求"""
        uri = params.get("uri", "")
        resource = self._resources.get(uri)
        if not resource:
            return {"contents": []}
        
        content = ""
        if resource.handler:
            content = str(resource.handler())
        elif resource.mime_type == "text/plain":
            content = resource.description
        
        return {
            "contents": [{
                "uri": uri,
                "mimeType": resource.mime_type,
                "text": content,
            }]
        }
    
    # ============ FastAPI模式 ============
    
    def create_fastapi_app(self):
        """创建FastAPI应用"""
        try:
            from fastapi import FastAPI, Request
            from fastapi.responses import JSONResponse
        except ImportError:
            raise ImportError("FastAPI required: pip install fastapi uvicorn")
        
        app = FastAPI(title=f"{self.name} MCP Server", version=self.version)
        server = self
        
        @app.post("/mcp")
        async def mcp_endpoint(request: Request):
            body = await request.json()
            response = server.handle_request(body)
            return JSONResponse(content=response)
        
        @app.get("/health")
        async def health():
            return {"status": "ok", "name": server.name, "version": server.version}
        
        @app.get("/tools")
        async def list_tools():
            return server._handle_tools_list({})
        
        logger.info(f"[MCPServer] FastAPI app created")
        return app
    
    # ============ Stdio模式 ============
    
    def run_stdio(self) -> None:
        """以stdio模式运行MCP Server"""
        import sys
        
        logger.info(f"[MCPServer] Running in stdio mode")
        
        for line in sys.stdin:
            line = line.strip()
            if not line:
                continue
            
            try:
                request = json.loads(line)
                response = self.handle_request(request)
                print(json.dumps(response), flush=True)
            except json.JSONDecodeError:
                error_resp = {
                    "jsonrpc": "2.0",
                    "id": None,
                    "error": {"code": -32700, "message": "Parse error"}
                }
                print(json.dumps(error_resp), flush=True)
    
    def get_stats(self) -> Dict:
        """获取服务器统计"""
        return {
            "name": self.name,
            "version": self.version,
            "tools": len(self._tools),
            "resources": len(self._resources),
            "tool_names": list(self._tools.keys()),
        }
