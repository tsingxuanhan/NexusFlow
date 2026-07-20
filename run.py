#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
NexusFlow 主入口点
==================
启动 NexusFlow Dashboard + Server

使用方式:
    # 1. 配置环境变量
    cp .env.example .env
    # 编辑 .env 填入 DeepSeek API Key

    # 2. 安装依赖
    pip install -r requirements.txt

    # 3. 启动
    python run.py
    
    # 或指定端口
    python run.py --port 8900
"""

import argparse
import os
import sys
import logging

def setup_logging(level: str = "INFO"):
    """配置日志"""
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )

def check_dependencies():
    """检查关键依赖"""
    missing = []
    try:
        import requests
    except ImportError:
        missing.append("requests")
    try:
        import fastapi
    except ImportError:
        missing.append("fastapi")
    try:
        import uvicorn
    except ImportError:
        missing.append("uvicorn")
    
    if missing:
        print(f"❌ 缺少依赖包: {', '.join(missing)}")
        print(f"   请运行: pip install -r requirements.txt")
        sys.exit(1)

def check_config():
    """检查配置"""
    try:
        from dotenv import load_dotenv
        # 从项目根目录加载 .env（而非依赖 CWD）
        dotenv_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '.env')
        load_dotenv(dotenv_path)
    except ImportError:
        pass  # python-dotenv 可选
    
    api_key = os.environ.get("DEEPSEEK_API_KEY", "")
    if not api_key or api_key == "sk-your-deepseek-key-here":
        print("⚠️  未配置 DEEPSEEK_API_KEY")
        print("   请复制 .env.example 为 .env 并填入 API Key")
        print("   cp .env.example .env")
        sys.exit(1)

def start_server(port: int = 8900):
    """启动 Server"""
    logger = logging.getLogger("nexusflow")
    logger.info(f"🚀 启动 NexusFlow Server (端口: {port})")
    
    try:
        import uvicorn
        # 直接启动 server 模块
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'server'))
        os.environ['SERVER_PORT'] = str(port)
        import nexusflow_server
        uvicorn.run(nexusflow_server.app, host="0.0.0.0", port=port, log_level="info")
    except ImportError as e:
        logger.error(f"Server 模块导入失败: {e}")
        logger.info("尝试启动 Gradio Dashboard...")
        try:
            from server.dashboard import NexusFlowDashboard
            dashboard = NexusFlowDashboard()
            dashboard.launch(server_port=port)
        except Exception as e2:
            logger.error(f"Dashboard 启动也失败: {e2}")
            sys.exit(1)

def main():
    parser = argparse.ArgumentParser(description="NexusFlow - 群体智能引擎")
    parser.add_argument("--port", type=int, default=8900, help="服务端口 (默认: 8900)")
    parser.add_argument("--log-level", default="INFO", choices=["DEBUG", "INFO", "WARNING", "ERROR"])
    args = parser.parse_args()
    
    setup_logging(args.log_level)
    logger = logging.getLogger("nexusflow")
    
    print("""
    ╔═══════════════════════════════════════════════════════════╗
    ║                                                           ║
    ║   NexusFlow v2.9 — 基于动态认知拓扑的超长程群体智能引擎    ║
    ║                                                           ║
    ╚═══════════════════════════════════════════════════════════╝
    """)
    
    logger.info("检查依赖...")
    check_dependencies()
    
    logger.info("检查配置...")
    check_config()
    
    logger.info("启动服务...")
    start_server(args.port)

if __name__ == "__main__":
    main()
