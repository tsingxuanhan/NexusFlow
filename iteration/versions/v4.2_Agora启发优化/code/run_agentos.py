#!/usr/bin/env python3
"""AgentOS启动器 — 云电脑模拟部署"""
import os
import sys
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")

# 确保项目根目录在path中
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from agentos import AgentOS
from agents import MemoryManager, SleeptimeEngine, MetaCognition, ContinuousLearningPipeline

def main():
    host = "0.0.0.0"  # 云电脑需要0.0.0.0才能外部访问
    port = 8000
    
    # 初始化核心组件（可选，缺了也能跑，API会返回降级提示）
    memory_manager = None
    sleeptime_engine = None
    meta_cognition = None
    continuous_learning = None
    
    try:
        memory_manager = MemoryManager()
        logging.info("MemoryManager initialized")
    except Exception as e:
        logging.warning(f"MemoryManager init failed: {e}")
    
    try:
        sleeptime_engine = SleeptimeEngine(memory_manager=memory_manager)
        logging.info("SleeptimeEngine initialized")
    except Exception as e:
        logging.warning(f"SleeptimeEngine init failed: {e}")
    
    try:
        meta_cognition = MetaCognition(memory_manager=memory_manager)
        logging.info("MetaCognition initialized")
    except Exception as e:
        logging.warning(f"MetaCognition init failed: {e}")
    
    try:
        continuous_learning = ContinuousLearningPipeline(memory_manager=memory_manager)
        logging.info("ContinuousLearningPipeline initialized")
    except Exception as e:
        logging.warning(f"ContinuousLearningPipeline init failed: {e}")
    
    aos = AgentOS(
        memory_manager=memory_manager,
        sleeptime_engine=sleeptime_engine,
        meta_cognition=meta_cognition,
        continuous_learning=continuous_learning,
        host=host,
        port=port,
    )
    
    logging.info(f"Starting AgentOS on {host}:{port}")
    aos.run(host=host, port=port, mode="http")

if __name__ == "__main__":
    main()
