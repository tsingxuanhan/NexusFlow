# -*- coding: utf-8 -*-
"""
铉枢·炉守 Open Design MCP桥接工具
XuanHub × Open Design — Phase 1 MCP互连

将Open Design的10个MCP设计工具桥接到NexusFlow工具系统
通过MCP Client V2连接open-design-mcp stdio服务器
"""

import logging
import json
import asyncio
import os
from typing import Dict, Any, Optional, List
from tools.base_tool import BaseTool, ToolResult

logger = logging.getLogger("ODDesignTool")


# ============ MCP工具定义 ============

OD_MCP_TOOLS = {
    "od_list_projects": {
        "description": "列出所有Open Design项目",
        "parameters": {
            "type": "object",
            "properties": {},
            "required": []
        },
        "requires_daemon": True,
    },
    "od_get_project": {
        "description": "获取Open Design项目详情及制品文件",
        "parameters": {
            "type": "object",
            "properties": {
                "project_id": {
                    "type": "string",
                    "description": "项目ID"
                }
            },
            "required": ["project_id"]
        },
        "requires_daemon": True,
    },
    "od_create_project": {
        "description": "创建新的Open Design项目",
        "parameters": {
            "type": "object",
            "properties": {
                "name": {
                    "type": "string",
                    "description": "项目名称"
                },
                "description": {
                    "type": "string",
                    "description": "项目描述"
                }
            },
            "required": ["name"]
        },
        "requires_daemon": True,
    },
    "od_update_project": {
        "description": "更新Open Design项目元数据",
        "parameters": {
            "type": "object",
            "properties": {
                "project_id": {
                    "type": "string",
                    "description": "项目ID"
                },
                "name": {
                    "type": "string",
                    "description": "新项目名称"
                },
                "description": {
                    "type": "string",
                    "description": "新项目描述"
                }
            },
            "required": ["project_id"]
        },
        "requires_daemon": True,
    },
    "od_delete_project": {
        "description": "永久删除Open Design项目",
        "parameters": {
            "type": "object",
            "properties": {
                "project_id": {
                    "type": "string",
                    "description": "项目ID"
                }
            },
            "required": ["project_id"]
        },
        "requires_daemon": True,
    },
    "od_save_artifact": {
        "description": "将HTML制品持久化到全局制品库",
        "parameters": {
            "type": "object",
            "properties": {
                "name": {
                    "type": "string",
                    "description": "制品名称"
                },
                "html": {
                    "type": "string",
                    "description": "HTML内容"
                },
                "description": {
                    "type": "string",
                    "description": "制品描述"
                }
            },
            "required": ["name", "html"]
        },
        "requires_daemon": True,
    },
    "od_save_project_file": {
        "description": "持久化文件到Open Design项目内",
        "parameters": {
            "type": "object",
            "properties": {
                "project_id": {
                    "type": "string",
                    "description": "项目ID"
                },
                "path": {
                    "type": "string",
                    "description": "项目内文件路径"
                },
                "content": {
                    "type": "string",
                    "description": "文件内容"
                }
            },
            "required": ["project_id", "path", "content"]
        },
        "requires_daemon": True,
    },
    "od_lint_artifact": {
        "description": "检查HTML制品的设计质量",
        "parameters": {
            "type": "object",
            "properties": {
                "html": {
                    "type": "string",
                    "description": "要检查的HTML内容"
                }
            },
            "required": ["html"]
        },
        "requires_daemon": True,
    },
    "od_compose_brief": {
        "description": "组合设计需求简报（不需要Daemon连接）",
        "parameters": {
            "type": "object",
            "properties": {
                "title": {
                    "type": "string",
                    "description": "设计标题"
                },
                "description": {
                    "type": "string",
                    "description": "设计需求描述"
                },
                "style": {
                    "type": "string",
                    "description": "风格要求（如liquid-glass, minimal, corporate）"
                },
                "target": {
                    "type": "string",
                    "description": "目标平台（web, mobile, desktop）"
                }
            },
            "required": ["title", "description"]
        },
        "requires_daemon": False,
    },
    "od_generate_design": {
        "description": "通过BYOK管线生成品牌级UI设计（原型/演示文稿/模板）",
        "parameters": {
            "type": "object",
            "properties": {
                "skill_id": {
                    "type": "string",
                    "description": "OD Skill ID（如prototype, deck, template）"
                },
                "prompt": {
                    "type": "string",
                    "description": "设计需求描述"
                },
                "design_system_id": {
                    "type": "string",
                    "description": "设计系统ID（可选，如stripe, vercel, linear）"
                },
                "mode": {
                    "type": "string",
                    "enum": ["prototype", "deck", "template"],
                    "description": "生成模式"
                },
                "project_name": {
                    "type": "string",
                    "description": "项目名称（可选，自动创建项目）"
                }
            },
            "required": ["prompt", "mode"]
        },
        "requires_daemon": True,
    },
}


# ============ MCP连接管理 ============

class ODMCPConnection:
    """
    Open Design MCP连接管理器
    
    管理与open-design-mcp stdio服务器的连接生命周期
    支持懒加载：首次调用时自动连接，空闲超时自动断开
    """
    
    def __init__(self, config_path: str = None):
        self._client = None
        self._connected = False
        self._config = self._load_config(config_path)
        self._idle_count = 0
        self._max_idle = 10  # 10次空闲后断开
    
    def _load_config(self, config_path: str = None) -> Dict:
        """加载MCP配置"""
        if config_path is None:
            # 默认路径
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            config_path = os.path.join(base_dir, "config", "open_design_mcp.json")
        
        try:
            with open(config_path, 'r') as f:
                config = json.load(f)
            return config.get("mcpServers", {}).get("open-design", {})
        except FileNotFoundError:
            logger.warning(f"[ODMCP] Config not found: {config_path}, using defaults")
            return {
                "command": "npx",
                "args": ["-y", "open-design-mcp@0.16.1"],
                "env": {
                    "OD_DAEMON_URL": "http://localhost:7456",
                }
            }
    
    def _resolve_env(self) -> Dict[str, str]:
        """解析环境变量引用"""
        raw_env = self._config.get("env", {})
        resolved = {}
        for key, value in raw_env.items():
            if isinstance(value, str) and value.startswith("${") and value.endswith("}"):
                env_name = value[2:-1]
                resolved[key] = os.environ.get(env_name, "")
            else:
                resolved[key] = value
        return resolved
    
    async def connect(self) -> bool:
        """建立MCP连接"""
        if self._connected and self._client:
            return True
        
        try:
            from mcp_client_v2 import MCPClientV2
            
            self._client = MCPClientV2()
            env = self._resolve_env()
            command = self._config.get("command", "npx")
            args = self._config.get("args", ["-y", "open-design-mcp@0.16.1"])
            
            await self._client.connect_stdio(
                server_name="open-design",
                command=command,
                args=args,
                env=env if env else None
            )
            
            self._connected = True
            self._idle_count = 0
            logger.info("[ODMCP] Connected to open-design-mcp")
            return True
            
        except Exception as e:
            logger.error(f"[ODMCP] Connection failed: {e}")
            self._connected = False
            self._client = None
            return False
    
    async def disconnect(self) -> None:
        """断开MCP连接"""
        if self._client and self._connected:
            try:
                await self._client.disconnect()
            except Exception as e:
                logger.warning(f"[ODMCP] Disconnect error: {e}")
            finally:
                self._connected = False
                self._client = None
                logger.info("[ODMCP] Disconnected")
    
    async def call_tool(self, name: str, arguments: Dict = None) -> Any:
        """调用MCP工具"""
        if not self._connected:
            ok = await self.connect()
            if not ok:
                return None
        
        try:
            result = await self._client.call_tool(name, arguments or {})
            self._idle_count = 0
            return result
        except Exception as e:
            logger.error(f"[ODMCP] Tool call failed ({name}): {e}")
            # 连接断开时重连一次
            if "connection" in str(e).lower() or "timeout" in str(e).lower():
                self._connected = False
                ok = await self.connect()
                if ok:
                    return await self._client.call_tool(name, arguments or {})
            return None
    
    @property
    def is_connected(self) -> bool:
        return self._connected
    
    @property
    def available_tools(self) -> List[str]:
        """获取可用工具列表"""
        return list(OD_MCP_TOOLS.keys())


# ============ 桥接工具类 ============

class ODDesignTool(BaseTool):
    """
    Open Design桥接工具
    
    将OD的10个MCP设计工具映射为NexusFlow BaseTool
    Agent通过name参数指定要调用的OD子工具
    
    用法:
        tool = ODDesignTool()
        result = tool.execute(
            action="od_generate_design",
            prompt="创建一个液态玻璃风格的仪表盘",
            mode="prototype"
        )
    """
    
    def __init__(self, config_path: str = None):
        super().__init__(
            name="od_design",
            description=(
                "Open Design品牌级UI/演示文稿生成工具。"
                "支持10个设计子工具：创建/列出/获取/更新/删除项目、"
                "保存制品/文件、质量校验、生成设计、组合简报。"
                "通过MCP协议连接Open Design Daemon。"
            ),
            parameters={
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "enum": list(OD_MCP_TOOLS.keys()),
                        "description": "要调用的OD子工具名称"
                    },
                    **self._build_action_params()
                },
                "required": ["action"]
            }
        )
        self._connection = ODMCPConnection(config_path)
    
    @staticmethod
    def _build_action_params() -> Dict:
        """构建所有子工具的合并参数定义"""
        all_params = {}
        for tool_name, tool_def in OD_MCP_TOOLS.items():
            props = tool_def["parameters"].get("properties", {})
            for param_name, param_def in props.items():
                if param_name not in all_params:
                    all_params[param_name] = {
                        **param_def,
                        "description": (
                            param_def.get("description", "") + 
                            f" [{tool_name}]"
                        )
                    }
        return all_params
    
    def execute(self, **kwargs) -> ToolResult:
        """执行OD设计工具（同步包装）"""
        action = kwargs.get("action")
        if not action:
            return ToolResult(success=False, error="Missing 'action' parameter")
        
        if action not in OD_MCP_TOOLS:
            return ToolResult(
                success=False,
                error=f"Unknown action: {action}. Available: {list(OD_MCP_TOOLS.keys())}"
            )
        
        # 提取子工具参数
        tool_def = OD_MCP_TOOLS[action]
        tool_params = tool_def["parameters"].get("properties", {})
        required = tool_def["parameters"].get("required", [])
        
        arguments = {}
        for param_name in tool_params:
            if param_name in kwargs:
                arguments[param_name] = kwargs[param_name]
        
        # 验证必填参数
        missing = [p for p in required if p not in arguments]
        if missing:
            return ToolResult(
                success=False,
                error=f"Missing required params for {action}: {missing}"
            )
        
        # 异步调用
        loop = None
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # 在已有事件循环中，创建任务
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as pool:
                    result = pool.submit(
                        asyncio.run,
                        self._async_execute(action, arguments)
                    ).result()
            else:
                result = loop.run_until_complete(
                    self._async_execute(action, arguments)
                )
        except RuntimeError:
            result = asyncio.run(self._async_execute(action, arguments))
        
        if result is None:
            return ToolResult(
                success=False,
                error=f"OD MCP call failed: {action}. Check Daemon is running on port 7456."
            )
        
        return ToolResult(
            success=True,
            output=result,
            metadata={"action": action, "params": arguments}
        )
    
    async def _async_execute(self, action: str, arguments: Dict) -> Any:
        """异步执行MCP工具调用"""
        return await self._connection.call_tool(action, arguments)
    
    async def connect_daemon(self) -> bool:
        """手动建立连接"""
        return await self._connection.connect()
    
    async def disconnect_daemon(self) -> None:
        """手动断开连接"""
        await self._connection.disconnect()
    
    def get_sub_tools(self) -> List[Dict]:
        """获取所有子工具的描述列表"""
        return [
            {"name": name, **defn}
            for name, defn in OD_MCP_TOOLS.items()
        ]


# ============ 高级便捷工具 ============

class ODQuickPrototype(BaseTool):
    """快速生成UI原型的便捷工具"""
    
    def __init__(self, config_path: str = None):
        super().__init__(
            name="od_quick_prototype",
            description="快速生成品牌级UI原型。一行描述即可，自动创建项目并调用OD生成。",
            parameters={
                "type": "object",
                "properties": {
                    "prompt": {
                        "type": "string",
                        "description": "设计需求描述（如'液态玻璃风格数据仪表盘'）"
                    },
                    "design_system": {
                        "type": "string",
                        "description": "设计系统ID（如stripe, vercel, linear）",
                        "default": "linear"
                    },
                    "save_to_project": {
                        "type": "string",
                        "description": "保存到指定项目名（可选）"
                    }
                },
                "required": ["prompt"]
            }
        )
        self._od_tool = ODDesignTool(config_path)
    
    def execute(self, **kwargs) -> ToolResult:
        prompt = kwargs.get("prompt", "")
        design_system = kwargs.get("design_system", "linear")
        save_to = kwargs.get("save_to_project")
        
        # Step 1: 组合设计简报
        brief_result = self._od_tool.execute(
            action="od_compose_brief",
            title=save_to or "Quick Prototype",
            description=prompt,
            style="liquid-glass",
            target="web"
        )
        
        if not brief_result.success:
            return ToolResult(
                success=False,
                error=f"Brief composition failed: {brief_result.error}"
            )
        
        # Step 2: 生成设计
        gen_args = {
            "action": "od_generate_design",
            "prompt": prompt,
            "mode": "prototype",
        }
        if design_system:
            gen_args["design_system_id"] = design_system
        if save_to:
            gen_args["project_name"] = save_to
        
        gen_result = self._od_tool.execute(**gen_args)
        
        if not gen_result.success:
            return ToolResult(
                success=False,
                error=f"Design generation failed: {gen_result.error}"
            )
        
        return ToolResult(
            success=True,
            output=gen_result.output,
            metadata={
                "prompt": prompt,
                "design_system": design_system,
                "project": save_to,
                "brief": brief_result.output
            }
        )


class ODQuickDeck(BaseTool):
    """快速生成演示文稿的便捷工具"""
    
    def __init__(self, config_path: str = None):
        super().__init__(
            name="od_quick_deck",
            description="快速生成品牌级演示文稿（可导出PPTX）。",
            parameters={
                "type": "object",
                "properties": {
                    "prompt": {
                        "type": "string",
                        "description": "演示文稿内容描述"
                    },
                    "design_system": {
                        "type": "string",
                        "description": "设计系统ID",
                        "default": "stripe"
                    },
                    "slides_count": {
                        "type": "integer",
                        "description": "预估幻灯片数量",
                        "default": 10
                    }
                },
                "required": ["prompt"]
            }
        )
        self._od_tool = ODDesignTool(config_path)
    
    def execute(self, **kwargs) -> ToolResult:
        prompt = kwargs.get("prompt", "")
        design_system = kwargs.get("design_system", "stripe")
        
        gen_result = self._od_tool.execute(
            action="od_generate_design",
            prompt=prompt,
            mode="deck",
            design_system_id=design_system
        )
        
        if not gen_result.success:
            return ToolResult(
                success=False,
                error=f"Deck generation failed: {gen_result.error}"
            )
        
        return ToolResult(
            success=True,
            output=gen_result.output,
            metadata={"prompt": prompt, "mode": "deck", "design_system": design_system}
        )


# ============ 自动注册 ============

def register_od_tools(tool_manager, config_path: str = None):
    """
    注册所有OD工具到ToolManager
    
    Args:
        tool_manager: ToolManager实例
        config_path: MCP配置文件路径（可选）
    """
    tool_manager.register(ODDesignTool(config_path))
    tool_manager.register(ODQuickPrototype(config_path))
    tool_manager.register(ODQuickDeck(config_path))
    logger.info("[ODDesign] Registered 3 OD tools (od_design, od_quick_prototype, od_quick_deck)")
