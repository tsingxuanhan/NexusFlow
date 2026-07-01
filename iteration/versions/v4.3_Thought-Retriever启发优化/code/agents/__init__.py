# -*- coding: utf-8 -*-
"""
铉枢·炉守 Agent模块
XuanHub Agents Package
v4.0 Phase 5 — AGI Core: Autonomous + Meta-Cognition + Cross-Domain + Continuous Learning + AgentOS
"""

# v4.0 泛化角色
from .planner import PlannerAgent
from .researcher import ResearcherAgent
from .executor import ExecutorAgent
from .reviewer import ReviewerAgent

# v3.3 旧角色（向后兼容，内部转为泛化角色的领域特化）
from .miner import MinerAgent
from .assayer import AssayerAgent
from .caster import CasterAgent
from .artisan import ArtisanAgent

# Phase 2: 规划引擎核心模块
from task_tree import TaskNode, TaskTree, TaskScheduler
from tot import TreeOfThought, GraphOfThought
from reflection import ReflectionLoop, Reflection, ExperienceRule

from a2a_protocol import A2AProtocol, get_a2a_network

# 创建全局A2A网络
a2a_network = get_a2a_network()


def create_team(domain: str = "materials") -> dict:
    """创建v4.0泛化团队并注册到A2A网络
    
    Args:
        domain: 领域名称，默认"materials"（建材）
        
    Returns:
        dict: 四个泛化Agent + 规划引擎组件
    """
    planner = PlannerAgent(domain_name=domain)
    researcher = ResearcherAgent(domain_name=domain)
    executor = ExecutorAgent(domain_name=domain)
    reviewer = ReviewerAgent(domain_name=domain)
    
    # 注册到A2A网络
    for agent in [planner, researcher, executor, reviewer]:
        if agent.a2a:
            a2a_network.register(agent.a2a)
    
    # Phase 2: 创建规划引擎组件
    strategy_chat = planner.chat  # PRO模型
    flash_chat = executor.chat    # Flash模型
    
    tot = TreeOfThought(
        strategy_chat=strategy_chat,
        evaluation_chat=flash_chat,
    )
    
    reflection_loop = ReflectionLoop(
        strategy_chat=strategy_chat,
        flash_chat=flash_chat,
    )
    
    return {
        "planner": planner,
        "researcher": researcher,
        "executor": executor,
        "reviewer": reviewer,
        # Phase 2 规划引擎
        "tot": tot,
        "reflection": reflection_loop,
        # Phase 3 工具生态（懒初始化，首次调用时创建）
        # "codeact": planner.init_codeact()  — 用 agent.execute_codeact(code) 触发
        # Phase 4 记忆系统（懒初始化，首次调用时创建）
        # "memory": planner.init_memory()    — 用 agent.remember/recall/dream 触发
    }


def create_legacy_team() -> dict:
    """创建v3.3兼容团队（旧版4-Agent）
    
    Returns:
        dict: 四个旧版Agent
    """
    miner = MinerAgent()
    assayer = AssayerAgent()
    caster = CasterAgent()
    artisan = ArtisanAgent()
    
    for agent in [miner, assayer, caster, artisan]:
        if agent.a2a:
            a2a_network.register(agent.a2a)
    
    return {
        "miner": miner,
        "assayer": assayer,
        "caster": caster,
        "artisan": artisan,
    }


def get_agent_protocol(agent_name: str) -> A2AProtocol | None:
    """获取Agent的A2A协议实例"""
    protocol = a2a_network.get_agent(agent_name.lower())
    if protocol:
        return protocol
    return a2a_network.find_agent_by_capability(agent_name)



# Phase 3: 工具生态模块
from tools.code_exec import CodeActExecutor
from tools.tool_registry import ToolRegistry
from a2a_gateway import A2AGateway

# Phase 4: 知识记忆模块
from core_memory import CoreMemory
from archival_memory import ArchivalMemory
from recall_memory import RecallMemory
from memory_manager import MemoryManager
from sleeptime import SleeptimeEngine
from multi_hop_rag import MultiHopRAG

# Phase 5: AGI核心能力模块
from autonomous import AutonomousGoalHandler, GoalStatus, GoalResult
from meta_cognition import MetaCognition, ConfidenceLevel, ConfidenceAssessment, KnowledgeGap
from cross_domain import CrossDomainTransfer, Analogy, AnalogyType
from continuous_learning import ContinuousLearningPipeline, InteractionOutcome


__all__ = [
    # v4.0 角色
    "PlannerAgent", "ResearcherAgent", "ExecutorAgent", "ReviewerAgent",
    "create_team",
    # Phase 2 规划引擎
    "TaskNode", "TaskTree", "TaskScheduler",
    "TreeOfThought", "GraphOfThought",
    "ReflectionLoop", "Reflection", "ExperienceRule",
    # Phase 3 工具生态
    "CodeActExecutor", "ToolRegistry", "A2AGateway",
    # Phase 4 知识记忆
    "CoreMemory", "ArchivalMemory", "RecallMemory",
    "MemoryManager", "SleeptimeEngine", "MultiHopRAG",
    # Phase 5 AGI核心能力
    "AutonomousGoalHandler", "GoalStatus", "GoalResult",
    "MetaCognition", "ConfidenceLevel", "ConfidenceAssessment",
    "CrossDomainTransfer", "Analogy", "AnalogyType",
    "ContinuousLearningPipeline", "InteractionOutcome",
    # v3.3 兼容
    "MinerAgent", "AssayerAgent", "CasterAgent", "ArtisanAgent",
    "create_legacy_team",
    # 通用
    "a2a_network", "get_agent_protocol",
]