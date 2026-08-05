"""MCP Server Manager - Minimal stub implementation"""
import logging
from typing import Dict, List, Any, Optional

logger = logging.getLogger(__name__)

class MCPServerManager:
    """Minimal MCP server manager for basic functionality"""
    
    def __init__(self, tool_registry=None):
        self.tool_registry = tool_registry
        self.servers: Dict[str, Dict] = {}
        logger.info("[MCPServerManager] Initialized (stub)")
    
    def list_servers(self) -> List[Dict]:
        return list(self.servers.values())
    
    def list_presets(self) -> List[Dict]:
        return [
            {"id": "filesystem", "name": "Filesystem", "description": "File system operations"},
            {"id": "web-search", "name": "Web Search", "description": "Web search capabilities"},
        ]
    
    def add_server(self, config: Dict) -> Dict:
        server_id = config.get("id", f"mcp-{len(self.servers)}")
        server = {
            "id": server_id,
            "name": config.get("name", server_id),
            "url": config.get("url", ""),
            "status": "disconnected",
            "tools": [],
        }
        self.servers[server_id] = server
        logger.info(f"[MCPServerManager] Added server: {server_id}")
        return server
    
    def add_from_preset(self, server_id: str) -> Dict:
        presets = {"filesystem": "Filesystem", "web-search": "Web Search"}
        name = presets.get(server_id, server_id)
        return self.add_server({"id": server_id, "name": name})
    
    def remove_server(self, server_id: str) -> bool:
        if server_id in self.servers:
            del self.servers[server_id]
            return True
        return False
    
    def check_installed(self, server_id: str) -> Dict:
        if server_id in self.servers:
            return {"installed": True, "server": self.servers[server_id]}
        return {"installed": False}
    
    async def connect_server(self, server_id: str) -> bool:
        if server_id in self.servers:
            self.servers[server_id]["status"] = "connected"
            return True
        return False
    
    async def disconnect_server(self, server_id: str) -> bool:
        if server_id in self.servers:
            self.servers[server_id]["status"] = "disconnected"
            return True
        return False
    
    async def call_tool(self, server_id: str, tool_name: str, params: Dict) -> Any:
        if server_id not in self.servers:
            raise ValueError(f"Server {server_id} not found")
        return {"status": "ok", "result": f"Mock result for {tool_name}"}
