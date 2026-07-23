#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
NexusFlow CLI
=============
命令行入口，支持以下子命令:

    nexusflow serve          启动 Dashboard + Server
    nexusflow run "<task>"   直接提交任务给 NexusFlow 执行
    nexusflow demo           运行演示 Demo
    nexusflow doctor         检查环境与依赖
    nexusflow version        显示版本信息
"""

import argparse
import os
import sys
import logging


def _setup_logging(level: str = "INFO"):
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


def _load_dotenv():
    """尝试加载 .env 文件"""
    try:
        from dotenv import load_dotenv
        # 优先从当前工作目录加载，其次从包所在目录加载
        env_path = os.path.join(os.getcwd(), ".env")
        if not os.path.exists(env_path):
            env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env")
        if os.path.exists(env_path):
            load_dotenv(env_path)
    except ImportError:
        pass


def _check_dependencies():
    """检查关键依赖是否已安装"""
    missing = []
    deps = {
        "requests": "requests",
        "fastapi": "fastapi",
        "uvicorn": "uvicorn",
        "numpy": "numpy",
        "networkx": "networkx",
        "gradio": "gradio",
        "yaml": "PyYAML",
        "pydantic": "pydantic",
    }
    for mod, pkg in deps.items():
        try:
            __import__(mod)
        except ImportError:
            missing.append(pkg)
    return missing


# ── 子命令实现 ──────────────────────────────────────────────

def cmd_version(args):
    """显示版本信息"""
    from nexusflow import __version__
    print(f"NexusFlow v{__version__}")


def cmd_doctor(args):
    """环境检查"""
    from nexusflow import __version__
    print(f"NexusFlow v{__version__} — 环境检查")
    print("=" * 50)

    # Python 版本
    py_ver = sys.version.split()[0]
    ok = sys.version_info >= (3, 10)
    print(f"  Python {py_ver}  {'✅' if ok else '❌ 需要 >= 3.10'}")

    # 依赖检查
    missing = _check_dependencies()
    if missing:
        print(f"  依赖包:  ❌ 缺少 {', '.join(missing)}")
        print(f"           请运行: pip install nexusflow[all]")
    else:
        print(f"  依赖包:  ✅ 全部就绪")

    # API Key 检查
    _load_dotenv()
    api_key = os.environ.get("DEEPSEEK_API_KEY", "")
    if api_key and api_key != "sk-your-deepseek-key-here":
        print(f"  DEEPSEEK_API_KEY:  ✅ 已配置")
    else:
        print(f"  DEEPSEEK_API_KEY:  ⚠️  未配置（运行任务前需设置）")
        print(f"                     export DEEPSEEK_API_KEY=your-key")

    # 可选：Ollama
    ollama_url = os.environ.get("OLLAMA_BASE_URL", "")
    if ollama_url:
        print(f"  OLLAMA_BASE_URL:   ✅ {ollama_url}")
    else:
        print(f"  OLLAMA_BASE_URL:   — 未配置（可选，用于端侧推理）")

    print("=" * 50)
    if not missing:
        print("✅ NexusFlow 已就绪！运行 `nexusflow demo` 开始体验")
    else:
        print("❌ 请先安装缺少的依赖")
        return 1
    return 0


def cmd_serve(args):
    """启动 Server / Dashboard"""
    _setup_logging(args.log_level)
    _load_dotenv()
    logger = logging.getLogger("nexusflow")

    from nexusflow import __version__
    print(f"""
    ╔═══════════════════════════════════════════════════════════╗
    ║                                                           ║
    ║   NexusFlow v{__version__} — 群体智能引擎                          ║
    ║                                                           ║
    ╚═══════════════════════════════════════════════════════════╝
    """)

    # 检查 API Key
    api_key = os.environ.get("DEEPSEEK_API_KEY", "")
    if not api_key or api_key == "sk-your-deepseek-key-here":
        logger.warning("⚠️  DEEPSEEK_API_KEY 未配置，Agent 调用将失败")
        logger.warning("   请设置: export DEEPSEEK_API_KEY=your-key")

    port = args.port or int(os.environ.get("DASHBOARD_PORT", "8900"))
    logger.info(f"🚀 启动 NexusFlow Dashboard (端口: {port})")

    try:
        import uvicorn
        # 尝试启动 FastAPI Server
        repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        server_dir = os.path.join(repo_root, "server")
        if os.path.isdir(server_dir):
            sys.path.insert(0, server_dir)
        try:
            import nexusflow_server
            uvicorn.run(nexusflow_server.app, host="0.0.0.0", port=port, log_level="info")
            return
        except ImportError:
            logger.info("FastAPI Server 模块未找到，尝试 Gradio Dashboard...")

        from server.dashboard import NexusFlowDashboard
        dashboard = NexusFlowDashboard()
        dashboard.launch(server_port=port)
    except ImportError as e:
        logger.error(f"启动失败: {e}")
        logger.info("请确认已安装全部依赖: pip install nexusflow[all]")
        sys.exit(1)


def cmd_run(args):
    """直接提交任务"""
    _setup_logging(args.log_level)
    _load_dotenv()
    logger = logging.getLogger("nexusflow")

    api_key = os.environ.get("DEEPSEEK_API_KEY", "")
    if not api_key or api_key == "sk-your-deepseek-key-here":
        print("❌ 请先配置 DEEPSEEK_API_KEY")
        print("   export DEEPSEEK_API_KEY=your-key")
        sys.exit(1)

    task = args.task
    logger.info(f"📋 提交任务: {task}")

    try:
        from nexusflow.core.nexus_orchestrator import NexusOrchestrator
        orchestrator = NexusOrchestrator()
        result = orchestrator.execute(task)
        print("\n" + "=" * 60)
        print("执行结果:")
        print("=" * 60)
        if isinstance(result, dict):
            import json
            print(json.dumps(result, ensure_ascii=False, indent=2))
        else:
            print(result)
    except Exception as e:
        logger.error(f"任务执行失败: {e}")
        sys.exit(1)


def cmd_demo(args):
    """运行演示"""
    _setup_logging(args.log_level)

    from nexusflow import __version__
    print(f"🎮 NexusFlow v{__version__} Demo")
    print("=" * 50)

    try:
        from nexusflow.core.dynamic_router import DynamicTopologyRouter
        from nexusflow.core.cognitive_division_engine import CognitiveDivisionEngine
        from nexusflow.core.agent_information_policy import AgentInformationPolicy
        from nexusflow.core.adaptive_context_manager import AdaptiveContextManager

        # 1. 动态路由演示
        print("\n📡 [1/4] 动态拓扑路由演示")
        from nexusflow.core.dynamic_router import TaskRequirement
        router = DynamicTopologyRouter()
        task = TaskRequirement(
            task_id="demo-001",
            description="分析全球气候变化趋势并撰写研究报告",
            required_capabilities=["research", "analysis", "writing"],
            required_domains=["climate", "environment"],
            execution_mode="cognitive_division",
        )
        topology = router.route(task)
        print(f"  任务: {task.description}")
        print(f"  拓扑类型: {topology.topology_type}")
        print(f"  Agent 链: {' → '.join(topology.agent_chain) if topology.agent_chain else '(未匹配到候选)'}")
        print(f"  置信度: {topology.confidence:.2f}")

        # 2. 信息不对称策略演示
        print("\n🔐 [2/4] CDoL 信息不对称策略演示")
        policy = AgentInformationPolicy()
        roles = ["coordinator", "planner", "researcher", "executor",
                 "reviewer", "miner", "assayer", "caster", "artisan", "archivist"]
        for role in roles[:6]:
            try:
                profile = policy.get_profile(role)
                tier_name = profile.tier.value if hasattr(profile.tier, 'value') else str(profile.tier)
                slices = [s.value if hasattr(s, 'value') else str(s) for s in profile.allowed_slices]
                print(f"  {role}: 层级={tier_name}, 可见切片={len(slices)}种")
            except (ValueError, KeyError):
                print(f"  {role}: (未配置画像)")

        # 3. 认知分工演示
        print("\n🧠 [3/4] 认知分工引擎 (CDoL) 演示")
        engine = CognitiveDivisionEngine()
        print(f"  组件: PerspectiveDecomposer + CommunicationLayer + FusionJudge")
        print(f"  默认最大轮次: 3 (Round 0 → Round 1/2 → Judge)")
        print(f"  Insight 蒸馏: 已集成")

        # 4. 自适应上下文管理
        print("\n📦 [4/4] 自适应上下文管理器演示")
        ctx_mgr = AdaptiveContextManager(initial_window=8192, sync_interval=10)
        print(f"  组件: WindowController + LazinessDetector + ForcedGlobalSync + RetrievalHead")
        print(f"  初始窗口: {ctx_mgr.window_controller.initial_window if hasattr(ctx_mgr.window_controller, 'initial_window') else 8192} tokens")
        print(f"  同步间隔: 每 {ctx_mgr.sync_engine.sync_interval if hasattr(ctx_mgr.sync_engine, 'sync_interval') else 10} 步")

        print("\n" + "=" * 50)
        print("✅ Demo 完成！以上展示了 NexusFlow 的核心能力")
        print("   完整任务执行请运行: nexusflow run \"你的任务\"")

    except ImportError as e:
        print(f"❌ 导入失败: {e}")
        print("   请确认已安装: pip install nexusflow[all]")
        sys.exit(1)


# ── 主入口 ──────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        prog="nexusflow",
        description="NexusFlow — 面向超长程复杂任务的群体智能引擎",
    )
    parser.add_argument(
        "--log-level", default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="日志级别 (默认: INFO)",
    )
    subparsers = parser.add_subparsers(dest="command", help="子命令")

    # version
    subparsers.add_parser("version", help="显示版本信息")

    # doctor
    subparsers.add_parser("doctor", help="检查环境与依赖")

    # serve
    p_serve = subparsers.add_parser("serve", help="启动 Dashboard + Server")
    p_serve.add_argument("--port", type=int, help="服务端口 (默认: 8900)")

    # run
    p_run = subparsers.add_parser("run", help="提交任务给 NexusFlow 执行")
    p_run.add_argument("task", help="任务描述")

    # demo
    subparsers.add_parser("demo", help="运行核心功能演示")

    args = parser.parse_args()

    if args.command is None:
        parser.print_help()
        sys.exit(0)

    dispatch = {
        "version": cmd_version,
        "doctor": cmd_doctor,
        "serve": cmd_serve,
        "run": cmd_run,
        "demo": cmd_demo,
    }
    sys.exit(dispatch[args.command](args) or 0)


if __name__ == "__main__":
    main()
