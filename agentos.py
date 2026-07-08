# -*- coding: utf-8 -*-
"""
铉枢·炉守 AgentOS — FastAPI运行时
XuanHub AgentOS Runtime

借鉴 Agno AgentOS + MCP Server 的生产运行时层：
1. 对话接口 — /chat, /chat/stream
2. 异步任务 — /task, /task/{id}
3. 记忆管理 — /memory/stats, /memory/core, /memory/recall
4. 工具发现 — /tools (MCP兼容)
5. Sleeptime触发 — /sleeptime/dream
6. 元认知 — /meta/confidence, /meta/gaps
7. 健康检查 — /health
8. 热更新 — /config/reload

支持FastAPI(HTTP)和stdio两种运行模式。
"""

import json
import time
import uuid
import logging
import threading
from typing import Any, Dict, List, Optional
from dataclasses import dataclass, field

logger = logging.getLogger("AgentOS")

# FastAPI可选依赖
try:
    from fastapi import FastAPI, HTTPException, BackgroundTasks
    from fastapi.responses import StreamingResponse, JSONResponse
    from fastapi.middleware.cors import CORSMiddleware
    from pydantic import BaseModel
    FASTAPI_AVAILABLE = True
except ImportError:
    FASTAPI_AVAILABLE = False
    # 提供基类替代
    class BaseModel:
        pass


# ============ 请求/响应模型 ============

if FASTAPI_AVAILABLE:
    class ChatRequest(BaseModel):
        message: str
        agent: Optional[str] = None
        model: Optional[str] = None
        context: Optional[str] = None
        stream: bool = False

    class TaskRequest(BaseModel):
        goal: str
        strategy: str = "auto"
        domain: Optional[str] = None
        max_steps: int = 20

    class CoreMemoryUpdateRequest(BaseModel):
        block: str
        content: str

    class ToolExecuteRequest(BaseModel):
        tool_name: str
        parameters: Dict[str, Any] = {}

    class RecallRequest(BaseModel):
        query: str
        top_k: int = 5
        multi_hop: bool = False

    class ConfidenceRequest(BaseModel):
        query: str

    class ConfigReloadRequest(BaseModel):
        config_key: Optional[str] = None
else:
    ChatRequest = None
    TaskRequest = None
    CoreMemoryUpdateRequest = None
    ToolExecuteRequest = None
    RecallRequest = None
    ConfidenceRequest = None
    ConfigReloadRequest = None


@dataclass
class AsyncTask:
    """异步任务"""
    task_id: str
    goal: str
    status: str = "pending"  # pending/running/completed/failed
    result: Optional[Dict] = None
    created_at: float = field(default_factory=time.time)
    completed_at: Optional[float] = None

    def to_dict(self) -> Dict:
        return {
            "task_id": self.task_id,
            "goal": self.goal,
            "status": self.status,
            "result": self.result,
            "created_at": self.created_at,
            "completed_at": self.completed_at,
            "elapsed": (self.completed_at or time.time()) - self.created_at,
        }


class AgentOS:
    """
    NexusFlow AgentOS 运行时

    将Agent能力暴露为HTTP API，支持：
    - 对话交互
    - 异步任务执行
    - 记忆管理
    - 工具发现（MCP兼容）
    - 元认知查询
    - Sleeptime触发
    - 配置热更新

    用法：
        # 启动HTTP服务
        aos = AgentOS(agent=base_agent, memory_manager=mm, ...)
        aos.run(host="127.0.0.1", port=9090)

        # 或获取FastAPI app用于自定义部署
        app = aos.create_app()
    """

    def __init__(
        self,
        agent: Any = None,
        memory_manager: Any = None,
        sleeptime_engine: Any = None,
        meta_cognition: Any = None,
        continuous_learning: Any = None,
        autonomous_handler: Any = None,
        cross_domain: Any = None,
        host: str = "127.0.0.1",
        port: int = 9090,
    ):
        self.agent = agent
        self.memory_manager = memory_manager
        self.sleeptime_engine = sleeptime_engine
        self.meta_cognition = meta_cognition
        self.continuous_learning = continuous_learning
        self.autonomous_handler = autonomous_handler
        self.cross_domain = cross_domain
        self.host = host
        self.port = port

        # 异步任务管理
        self._tasks: Dict[str, AsyncTask] = {}
        self._task_lock = threading.Lock()

        # 运行统计
        self._stats = {
            "total_requests": 0,
            "chat_requests": 0,
            "task_requests": 0,
            "memory_requests": 0,
            "tool_requests": 0,
            "start_time": None,
        }

        # FastAPI app
        self._app: Optional[Any] = None

    # ============ FastAPI App创建 ============

    def create_app(self) -> Any:
        """创建FastAPI应用"""
        if not FASTAPI_AVAILABLE:
            raise ImportError(
                "FastAPI未安装，请运行: pip install fastapi uvicorn"
            )

        app = FastAPI(
            title="NexusFlow AgentOS",
            description="铉枢·炉守 Agent运行时API",
            version="4.0.0",
        )

        # CORS: 允许Hub控制面板等前端访问
        app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

        self._register_routes(app)
        self._app = app
        return app

    def _register_routes(self, app: Any) -> None:
        """注册所有API路由"""

        # ---- 健康检查 ----
        @app.get("/health")
        async def health_check():
            self._stats["total_requests"] += 1
            return {
                "status": "ok",
                "version": "4.0.0",
                "uptime": time.time() - self._stats["start_time"] if self._stats["start_time"] else 0,
                "agent": self.agent.name if self.agent else "none",
                "memory": self.memory_manager.get_summary() if self.memory_manager else "none",
            }

        # ---- 对话接口 ----
        @app.post("/chat")
        async def chat(request: ChatRequest):
            self._stats["total_requests"] += 1
            self._stats["chat_requests"] += 1

            if not self.agent:
                raise HTTPException(status_code=503, detail="Agent未初始化")

            try:
                # 元认知：自适应策略
                if self.meta_cognition:
                    strategy = self.meta_cognition.adaptive_strategy(request.message)
                    if strategy.get("context_boost"):
                        boosted_msg = request.message + "\n\n补充上下文: " + "; ".join(strategy["context_boost"])
                    else:
                        boosted_msg = request.message
                else:
                    boosted_msg = request.message
                    strategy = {}

                # 记忆增强上下文
                memory_context = ""
                if self.memory_manager:
                    memory_context = self.memory_manager.get_context_for_prompt(
                        request.message, max_tokens=1000
                    )

                # 执行对话
                full_message = boosted_msg
                if memory_context:
                    full_message = f"相关记忆:\n{memory_context}\n\n用户问题: {boosted_msg}"

                response = self.agent.chat(full_message)

                # 持续学习
                if self.continuous_learning:
                    outcome = self.continuous_learning.auto_evaluate_outcome(
                        request.message, response
                    )
                    self.continuous_learning.on_interaction(
                        query=request.message,
                        response=response,
                        outcome=outcome,
                        domain=request.context or "general",
                    )

                return {
                    "response": response,
                    "strategy": strategy,
                    "model": self.agent.model if self.agent else "unknown",
                }

            except Exception as e:
                logger.error(f"[AgentOS] Chat error: {e}")
                raise HTTPException(status_code=500, detail=str(e))

        @app.post("/chat/stream")
        async def chat_stream(request: ChatRequest):
            """流式对话（占位，需配合SSE）"""
            self._stats["total_requests"] += 1
            if not self.agent:
                raise HTTPException(status_code=503, detail="Agent未初始化")

            # 简化实现：返回完整响应
            try:
                response = self.agent.chat(request.message)
                return JSONResponse(content={"response": response})
            except Exception as e:
                raise HTTPException(status_code=500, detail=str(e))

        # ---- 异步任务 ----
        @app.post("/task")
        async def submit_task(request: TaskRequest, background_tasks: BackgroundTasks):
            self._stats["total_requests"] += 1
            self._stats["task_requests"] += 1

            task_id = str(uuid.uuid4())[:8]
            task = AsyncTask(task_id=task_id, goal=request.goal)
            with self._task_lock:
                self._tasks[task_id] = task

            # 后台执行
            background_tasks.add_task(self._execute_task, task_id, request)

            return {"task_id": task_id, "status": "pending", "goal": request.goal}

        @app.get("/task/{task_id}")
        async def get_task_status(task_id: str):
            with self._task_lock:
                task = self._tasks.get(task_id)
            if not task:
                raise HTTPException(status_code=404, detail="任务不存在")
            return task.to_dict()

        @app.get("/tasks")
        async def list_tasks():
            with self._task_lock:
                return [t.to_dict() for t in self._tasks.values()]

        # ---- 记忆管理 ----
        @app.get("/memory/stats")
        async def memory_stats():
            self._stats["total_requests"] += 1
            self._stats["memory_requests"] += 1
            if not self.memory_manager:
                raise HTTPException(status_code=503, detail="Memory Manager未初始化")
            return self.memory_manager.get_stats()

        @app.get("/memory/core")
        async def get_core_memory():
            if not self.memory_manager:
                raise HTTPException(status_code=503, detail="Memory Manager未初始化")
            return {
                "prompt": self.memory_manager.core.to_system_prompt(),
                "stats": self.memory_manager.core.get_stats(),
            }

        @app.post("/memory/core/update")
        async def update_core_memory(request: CoreMemoryUpdateRequest):
            if not self.memory_manager:
                raise HTTPException(status_code=503, detail="Memory Manager未初始化")
            self.memory_manager.core.update(request.block, request.content)
            return {"status": "ok", "block": request.block}

        @app.post("/memory/recall")
        async def recall_memory(request: RecallRequest):
            if not self.memory_manager:
                raise HTTPException(status_code=503, detail="Memory Manager未初始化")
            result = self.memory_manager.recall_memory(
                query=request.query,
                top_k=request.top_k,
                multi_hop=request.multi_hop,
            )
            # 序列化
            serializable = {}
            for key, items in result.items():
                if isinstance(items, list):
                    serializable[key] = [
                        item.to_dict() if hasattr(item, 'to_dict') else str(item)
                        for item in items
                    ]
                else:
                    serializable[key] = items
            return serializable

        @app.post("/memory/remember")
        async def remember(request: Dict):
            """通用记忆写入"""
            if not self.memory_manager:
                raise HTTPException(status_code=503, detail="Memory Manager未初始化")
            content = request.get("content", "")
            memory_type = request.get("memory_type", "auto")
            result = self.memory_manager.remember(content, memory_type=memory_type)
            return {"status": "ok", "location": result}

        # ---- 工具发现（MCP兼容） ----
        @app.get("/tools")
        async def list_tools():
            self._stats["total_requests"] += 1
            self._stats["tool_requests"] += 1

            tools = []
            # 内置工具
            builtin_tools = [
                {"name": "web_search", "description": "搜索互联网信息", "category": "search"},
                {"name": "file_ops", "description": "文件读写操作", "category": "io"},
                {"name": "data_query", "description": "数据集查询", "category": "data"},
                {"name": "api_caller", "description": "HTTP API调用", "category": "network"},
                {"name": "calculator", "description": "数学计算", "category": "math"},
                {"name": "git_ops", "description": "Git操作", "category": "vcs"},
                {"name": "pdf_reader", "description": "PDF文档读取", "category": "io"},
                {"name": "browser", "description": "浏览器操作", "category": "web"},
                {"name": "scheduler", "description": "任务调度", "category": "system"},
                {"name": "codeact", "description": "CodeAct代码执行沙箱", "category": "execution"},
            ]
            tools.extend(builtin_tools)

            # CodeAct全局函数
            codeact_funcs = [
                {"name": "search", "description": "搜索互联网"},
                {"name": "read_file", "description": "读取文件"},
                {"name": "write_file", "description": "写入文件"},
                {"name": "list_dir", "description": "列出目录"},
                {"name": "query_data", "description": "查询数据集"},
                {"name": "http_get", "description": "HTTP GET请求"},
                {"name": "http_post", "description": "HTTP POST请求"},
                {"name": "calculate", "description": "数学计算"},
                {"name": "git_op", "description": "Git操作"},
                {"name": "read_pdf", "description": "读取PDF"},
                {"name": "browse", "description": "浏览器访问"},
                {"name": "schedule_task", "description": "调度任务"},
            ]
            tools.extend([{"name": f, **t} for f, t in [
                (t["name"], {"description": t["description"], "category": "codeact"})
                for t in codeact_funcs
            ]])

            return {"tools": tools, "total": len(tools)}

        @app.post("/tools/{tool_name}/execute")
        async def execute_tool(tool_name: str, request: ToolExecuteRequest):
            if not self.agent or not hasattr(self.agent, '_tool_registry'):
                raise HTTPException(status_code=503, detail="工具注册中心未初始化")

            try:
                result = self.agent._tool_registry.execute(
                    tool_name=tool_name,
                    parameters=request.parameters,
                )
                return {"tool": tool_name, "result": result}
            except Exception as e:
                raise HTTPException(status_code=500, detail=str(e))

        # ---- Sleeptime ----
        @app.post("/sleeptime/dream")
        async def trigger_dream():
            if not self.sleeptime_engine:
                if self.memory_manager:
                    # 降级到memory_manager的consolidate
                    result = self.memory_manager.sleeptime_consolidate()
                    return {"status": "ok", "consolidation": result}
                raise HTTPException(status_code=503, detail="Sleeptime Engine未初始化")

            result = self.sleeptime_engine.dream(force=True)
            return {
                "status": "ok",
                "dream": result.to_dict() if hasattr(result, 'to_dict') else str(result),
            }

        # ---- 元认知 ----
        @app.post("/meta/confidence")
        async def assess_confidence(request: ConfidenceRequest):
            if not self.meta_cognition:
                raise HTTPException(status_code=503, detail="MetaCognition未初始化")
            assessment = self.meta_cognition.assess_confidence(request.query)
            return assessment.to_dict()

        @app.get("/meta/gaps")
        async def identify_gaps(domain: Optional[str] = None):
            if not self.meta_cognition:
                raise HTTPException(status_code=503, detail="MetaCognition未初始化")
            gaps = self.meta_cognition.identify_knowledge_gaps(domain=domain)
            return {"gaps": [g.to_dict() for g in gaps], "total": len(gaps)}

        @app.post("/meta/self-improve")
        async def self_improve(request: Dict):
            if not self.meta_cognition:
                raise HTTPException(status_code=503, detail="MetaCognition未初始化")
            gaps = request.get("gaps")
            domain = request.get("domain")
            result = self.meta_cognition.self_improve(gaps=gaps, domain=domain)
            return result

        # ---- 跨领域迁移 ----
        @app.post("/transfer/analogy")
        async def find_analogy(request: Dict):
            if not self.cross_domain:
                raise HTTPException(status_code=503, detail="CrossDomainTransfer未初始化")
            source = request.get("source_domain", "")
            target = request.get("target_domain", "")
            concept = request.get("concept")
            analogies = self.cross_domain.find_analogy(source, target, concept)
            return {
                "analogies": [a.to_dict() for a in analogies],
                "total": len(analogies),
            }

        @app.post("/transfer/execute")
        async def execute_transfer(request: Dict):
            if not self.cross_domain:
                raise HTTPException(status_code=503, detail="CrossDomainTransfer未初始化")
            source = request.get("source_domain", "")
            target = request.get("target_domain", "")
            analogies = self.cross_domain.find_analogy(source, target)
            result = self.cross_domain.transfer(analogies)
            return result.to_dict()

        # ---- 配置热更新 ----
        @app.post("/config/reload")
        async def reload_config(request: Dict):
            config_key = request.get("config_key")
            try:
                # 重新导入config
                import importlib
                import config as cfg
                importlib.reload(cfg)
                return {"status": "ok", "reloaded": config_key or "all"}
            except Exception as e:
                raise HTTPException(status_code=500, detail=str(e))

        # ---- 统计 ----
        @app.get("/stats")
        async def get_stats():
            return {
                "agent_os": self._stats,
                "agent": self.agent.get_stats() if self.agent and hasattr(self.agent, 'get_stats') else {},
                "memory": self.memory_manager.get_stats() if self.memory_manager else {},
                "tasks": {
                    "total": len(self._tasks),
                    "pending": sum(1 for t in self._tasks.values() if t.status == "pending"),
                    "running": sum(1 for t in self._tasks.values() if t.status == "running"),
                    "completed": sum(1 for t in self._tasks.values() if t.status == "completed"),
                },
            }

    # ============ 异步任务执行 ============

    def _execute_task(self, task_id: str, request: Any) -> None:
        """后台执行异步任务"""
        with self._task_lock:
            task = self._tasks.get(task_id)
            if not task:
                return
            task.status = "running"

        try:
            if self.autonomous_handler:
                result = self.autonomous_handler.handle(
                    goal=request.goal,
                    context=f"策略: {request.strategy}, 领域: {request.domain or 'auto'}",
                )
                task.result = result.to_dict()
                task.status = "completed"
            elif self.agent:
                # 降级：直接用agent chat
                response = self.agent.chat(request.goal)
                task.result = {"response": response, "strategy": "direct_chat"}
                task.status = "completed"
            else:
                task.result = {"error": "无可用的执行引擎"}
                task.status = "failed"

        except Exception as e:
            task.result = {"error": str(e)}
            task.status = "failed"

        task.completed_at = time.time()

    # ============ stdio模式 ============

    def run_stdio(self) -> None:
        """stdio模式运行 — 适合MCP Server集成"""
        import sys
        logger.info("[AgentOS] Running in stdio mode")

        for line in sys.stdin:
            line = line.strip()
            if not line:
                continue

            try:
                request = json.loads(line)
                response = self._handle_stdio_request(request)
                print(json.dumps(response, ensure_ascii=False), flush=True)
            except json.JSONDecodeError:
                print(json.dumps({"error": "Invalid JSON"}, ensure_ascii=False), flush=True)
            except Exception as e:
                print(json.dumps({"error": str(e)}, ensure_ascii=False), flush=True)

    def _handle_stdio_request(self, request: Dict) -> Dict:
        """处理stdio请求"""
        method = request.get("method", "")
        params = request.get("params", {})
        req_id = request.get("id", 0)

        handlers = {
            "chat": self._stdio_chat,
            "task": self._stdio_task,
            "memory.stats": self._stdio_memory_stats,
            "health": self._stdio_health,
        }

        handler = handlers.get(method)
        if handler:
            result = handler(params)
        else:
            result = {"error": f"Unknown method: {method}"}

        return {"id": req_id, "result": result}

    def _stdio_chat(self, params: Dict) -> Dict:
        if not self.agent:
            return {"error": "Agent未初始化"}
        message = params.get("message", "")
        response = self.agent.chat(message)
        return {"response": response}

    def _stdio_task(self, params: Dict) -> Dict:
        if not self.autonomous_handler:
            return {"error": "AutonomousHandler未初始化"}
        goal = params.get("goal", "")
        result = self.autonomous_handler.handle(goal)
        return result.to_dict()

    def _stdio_memory_stats(self, params: Dict) -> Dict:
        if not self.memory_manager:
            return {"error": "MemoryManager未初始化"}
        return self.memory_manager.get_stats()

    def _stdio_health(self, params: Dict) -> Dict:
        return {"status": "ok", "version": "4.0.0"}

    # ============ 启动 ============

    def run(self, host: Optional[str] = None, port: Optional[int] = None, mode: str = "http") -> None:
        """
        启动AgentOS

        Args:
            host: 监听地址
            port: 监听端口
            mode: "http" 或 "stdio"
        """
        self._stats["start_time"] = time.time()
        actual_host = host or self.host
        actual_port = port or self.port

        if mode == "stdio":
            self.run_stdio()
            return

        if not FASTAPI_AVAILABLE:
            logger.error("[AgentOS] FastAPI not installed, falling back to stdio mode")
            self.run_stdio()
            return

        import uvicorn
        app = self.create_app()
        logger.info(f"[AgentOS] Starting on {actual_host}:{actual_port}")
        uvicorn.run(app, host=actual_host, port=actual_port, log_level="info")

    def get_stats(self) -> Dict:
        """获取AgentOS统计"""
        return self._stats.copy()

    def to_codeact_globals(self) -> Dict[str, Any]:
        """导出为CodeAct全局函数"""
        return {
            "agentos_health": lambda: {"status": "ok", "version": "4.0.0"} if self._stats["start_time"] else {"status": "not_started"},
        }
