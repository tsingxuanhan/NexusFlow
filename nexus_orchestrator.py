# -*- coding: utf-8 -*-
"""
NexusFlow 编排器 — 统一入口
XuanHub v4.0 Phase 7

将 Agent注册表 + 信息策略 + CDoL引擎 + 自适应上下文 + 记忆系统
串联成完整的执行管线。
"""

import logging
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Callable

from agent_information_policy import (
    AgentInformationPolicy,
    AgentTier,
    get_information_policy,
    recommend_cdol_config,
)

logger = logging.getLogger("NexusOrchestrator")


# ============================================================================
# 任务路由类型
# ============================================================================

class TaskRoute(str):
    SIMPLE = "simple"          # 单Agent直接处理
    CDOL = "cdol"              # CDoL多Agent协作
    RESEARCH = "research"      # 文献研究任务
    CODING = "coding"          # 代码开发任务


# 任务复杂度评估关键词
COMPLEX_KEYWORDS = [
    "分析", "对比", "综合", "评估", "优化", "设计", "规划",
    "analyze", "compare", "evaluate", "optimize", "design", "plan",
    "多步骤", "复杂", "cross-domain", "multi-step",
]

RESEARCH_KEYWORDS = [
    "文献", "论文", "检索", "搜索", "调研",
    "paper", "literature", "search", "survey",
]

CODING_KEYWORDS = [
    "代码", "编程", "实现", "开发", "脚本", "debug",
    "code", "implement", "develop", "script", "program",
]

# 各任务类型对应的推荐Agent组合
DEFAULT_AGENT_MAP = {
    TaskRoute.RESEARCH: ["miner", "researcher", "assayer"],
    TaskRoute.CODING: ["caster", "executor", "reviewer"],
    TaskRoute.CDOL: ["researcher", "executor", "reviewer"],
    TaskRoute.SIMPLE: ["executor"],
}


@dataclass
class TaskResult:
    """任务执行结果"""
    task_id: str = ""
    task_description: str = ""
    route: str = "simple"
    status: str = "pending"       # pending | running | completed | failed
    result: Any = None
    participants: List[str] = field(default_factory=list)
    duration_seconds: float = 0.0
    error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


# ============================================================================
# NexusOrchestrator — 统一编排器
# ============================================================================

class NexusOrchestrator:
    """NexusFlow 统一编排器
    
    职责：
    1. 初始化所有组件（Agent注册、信息策略、CDoL引擎、记忆池）
    2. 接收高层任务，自动选择执行模式
    3. 简单任务 → 直接分配给单个Agent
    4. 复杂任务 → CDoL多Agent协作（信息不对称）
    5. 任务完成后触发 Archivist 蒸馏
    
    使用方式：
        orchestrator = NexusOrchestrator()
        result = orchestrator.execute("分析这批实验数据的异常值")
    """
    
    def __init__(
        self,
        agents: Optional[Dict[str, Any]] = None,
        information_policy: Optional[AgentInformationPolicy] = None,
        llm_chat: Optional[Callable] = None,
        config: Optional[Dict[str, Any]] = None,
    ):
        """
        Args:
            agents: 预构建的Agent字典（None时从注册表自动创建）
            information_policy: 信息策略实例（None时自动创建默认策略）
            llm_chat: LLM调用函数
            config: 额外配置
        """
        self.config = config or {}
        self.llm_chat = llm_chat
        self._task_counter = 0
        self._task_history: List[TaskResult] = []
        
        # 1. 初始化信息策略
        self.information_policy = information_policy or get_information_policy()
        
        # 2. 初始化Agent注册表
        self._agents = agents or {}
        
        # 3. 初始化全局记忆池
        from adaptive_context_manager import GlobalMemoryPool, create_context_manager
        
        self.global_memory = GlobalMemoryPool()
        
        # 4. 初始化自适应上下文管理器（集成信息策略）
        self.context_manager = create_context_manager(
            information_policy=self.information_policy,
            llm_chat=llm_chat,
        )
        
        # 5. 初始化CDoL引擎（集成信息策略）
        from cognitive_division_engine import CognitiveDivisionEngine
        
        self.cdol_engine = CognitiveDivisionEngine(
            agents=self._agents,
            memory_pool=self.global_memory,
            llm_chat=llm_chat,
            information_policy=self.information_policy,
        )
        
        logger.info(
            f"[NexusOrchestrator] 初始化完成: "
            f"agents={len(self._agents)}, "
            f"policy={'enabled' if self.information_policy else 'disabled'}"
        )
    
    def set_agents(self, agents: Dict[str, Any]):
        """更新Agent集合（用于运行时动态注册）"""
        self._agents = agents
        # 同步更新CDoL引擎的Agent池
        self.cdol_engine.agents = agents
    
    def execute(self, task_description: str, **kwargs) -> TaskResult:
        """执行任务的主入口
        
        自动判断任务复杂度并路由到对应执行模式：
        - 简单任务 → 单Agent直接执行
        - 复杂任务 → CDoL多Agent协作
        
        Args:
            task_description: 任务描述
            **kwargs: 额外参数（force_route, max_agents, etc.）
            
        Returns:
            TaskResult: 任务执行结果
        """
        start_time = time.time()
        self._task_counter += 1
        task_id = f"task_{self._task_counter:04d}"
        
        result = TaskResult(
            task_id=task_id,
            task_description=task_description,
            status="running",
        )
        
        try:
            # 判断任务路由
            force_route = kwargs.get("force_route")
            route = force_route or self._route_task(task_description)
            result.route = route
            
            logger.info(
                f"[NexusOrchestrator] 任务 {task_id}: "
                f"route={route}, desc={task_description[:60]}..."
            )
            
            # 根据路由选择执行模式
            if route == TaskRoute.SIMPLE:
                agents_for_task = DEFAULT_AGENT_MAP[TaskRoute.SIMPLE]
                exec_result = self._execute_simple(task_description, agents_for_task[0])
            elif route in (TaskRoute.CDOL, TaskRoute.RESEARCH, TaskRoute.CODING):
                # 根据任务类型选择最合适的Agent组合
                max_agents = kwargs.get("max_agents", 4)
                participants = self._select_participants(task_description, route, max_agents)
                result.participants = participants
                exec_result = self._execute_cdol(task_description, participants)
            else:
                exec_result = self._execute_simple(task_description, "executor")
            
            result.result = exec_result
            result.status = "completed"
            
            # 任务后处理：Archivist蒸馏
            self._post_task_hook(result, task_description)
            
        except Exception as e:
            result.status = "failed"
            result.error = str(e)
            logger.error(f"[NexusOrchestrator] 任务 {task_id} 失败: {e}")
        
        result.duration_seconds = time.time() - start_time
        self._task_history.append(result)
        
        return result
    
    def _route_task(self, task_description: str) -> str:
        """判断任务路由：simple / cdol / research / coding
        
        基于关键词匹配进行初步分类，后续可升级为LLM分类。
        
        Args:
            task_description: 任务描述
            
        Returns:
            路由类型字符串
        """
        desc = task_description.lower()
        
        # 计算各类型匹配得分
        research_score = sum(1 for kw in RESEARCH_KEYWORDS if kw in desc)
        coding_score = sum(1 for kw in CODING_KEYWORDS if kw in desc)
        complexity_score = sum(1 for kw in COMPLEX_KEYWORDS if kw in desc)
        
        # 研究类任务
        if research_score >= 2:
            return TaskRoute.RESEARCH
        
        # 编码类任务
        if coding_score >= 2:
            return TaskRoute.CODING
        
        # 复杂任务需要CDoL
        if complexity_score >= 2 or (research_score + coding_score >= 2):
            return TaskRoute.CDOL
        
        # 默认简单任务
        return TaskRoute.SIMPLE
    
    def _select_participants(
        self,
        task_description: str,
        route: str,
        max_agents: int = 4,
    ) -> List[str]:
        """根据任务类型选择最合适的Agent参与者
        
        利用信息策略的推荐机制，结合任务类型默认映射。
        
        Args:
            task_description: 任务描述
            route: 路由类型
            max_agents: 最大参与Agent数
            
        Returns:
            Agent名称列表
        """
        # 优先使用信息策略推荐
        if self.information_policy:
            recommended = self.information_policy.get_recommended_participants(
                task_description, max_count=max_agents
            )
            # 确保推荐的Agent都在实际Agent池中
            available = [a for a in recommended if a in self._agents]
            if available:
                return available
        
        # 降级：使用默认映射
        default_agents = DEFAULT_AGENT_MAP.get(route, DEFAULT_AGENT_MAP[TaskRoute.CDOL])
        available = [a for a in default_agents if a in self._agents]
        
        return available[:max_agents] if available else default_agents[:max_agents]
    
    def _execute_simple(
        self,
        task_description: str,
        assigned_agent: str,
    ) -> Dict[str, Any]:
        """简单任务：单Agent执行
        
        Args:
            task_description: 任务描述
            assigned_agent: 分配的Agent名称
            
        Returns:
            执行结果字典
        """
        logger.info(
            f"[NexusOrchestrator] 简单任务分配给 {assigned_agent}: "
            f"{task_description[:50]}..."
        )
        
        # 获取Agent为该任务裁剪的上下文
        context = self.context_manager.get_filtered_context_for_agent(
            assigned_agent, top_k=5
        )
        
        # 返回结构化结果（实际执行由Agent自行完成）
        return {
            "mode": "simple",
            "assigned_agent": assigned_agent,
            "task": task_description,
            "context_items": len(context),
            "instruction": f"Agent '{assigned_agent}' 请处理任务: {task_description}",
        }
    
    def _execute_cdol(
        self,
        task_description: str,
        participants: List[str],
    ) -> Dict[str, Any]:
        """CDoL任务：多Agent信息不对称协作
        
        Args:
            task_description: 任务描述
            participants: 参与Agent列表
            
        Returns:
            执行结果字典
        """
        logger.info(
            f"[NexusOrchestrator] CDoL任务启动: "
            f"participants={participants}, task={task_description[:50]}..."
        )
        
        # 使用CDoL引擎执行（已集成信息策略）
        cdol_result = self.cdol_engine.execute(
            task_description=task_description,
            perspective_count=len(participants),
        )
        
        return {
            "mode": "cdol",
            "participants": participants,
            "task": task_description,
            "cdol_result": {
                "final_answer": cdol_result.final_answer,
                "synergy_gain": cdol_result.synergy_gain,
                "metrics": cdol_result.metrics,
                "policy_summary": cdol_result.information_policy_summary,
                "num_rounds": 3,  # Round 0/1/2
            },
        }
    
    def _post_task_hook(self, result: TaskResult, task_description: str):
        """任务后处理：Archivist蒸馏 + 记忆更新
        
        任务完成后，将执行过程中的关键信息通知Archivist进行蒸馏归档。
        
        Args:
            result: 任务执行结果
            task_description: 原始任务描述
        """
        try:
            # 将任务结果写入全局记忆
            summary = (
                f"任务[{result.task_id}]完成: {task_description[:80]}... "
                f"route={result.route}, status={result.status}, "
                f"duration={result.duration_seconds:.1f}s"
            )
            
            if result.participants:
                summary += f", participants={result.participants}"
            
            # 通知Archivist归档
            self.context_manager.notify_archivist(
                conclusion=summary,
                agent_id="orchestrator",
                task_context={
                    "task_id": result.task_id,
                    "route": result.route,
                    "participants": result.participants,
                    "status": result.status,
                },
            )
            
            logger.info(
                f"[NexusOrchestrator] 后处理完成: task={result.task_id}"
            )
        except Exception as e:
            logger.warning(f"[NexusOrchestrator] 后处理失败: {e}")
    
    def get_status(self) -> Dict[str, Any]:
        """获取系统状态（Dashboard用）
        
        Returns:
            系统状态字典
        """
        return {
            "orchestrator": {
                "total_tasks": self._task_counter,
                "task_history_count": len(self._task_history),
                "recent_tasks": [
                    {
                        "id": t.task_id,
                        "route": t.route,
                        "status": t.status,
                        "duration": t.duration_seconds,
                        "participants": t.participants,
                    }
                    for t in self._task_history[-10:]
                ],
            },
            "agents": {
                name: {
                    "available": True,
                    "tier": (
                        self.information_policy.get_tier(name).value
                        if self.information_policy else "unknown"
                    ),
                }
                for name in self._agents
            },
            "context_manager": self.context_manager.get_stats(),
            "information_policy": (
                self.information_policy.get_policy_summary()
                if self.information_policy else "disabled"
            ),
        }
    
    def get_roster(self) -> List[Dict[str, Any]]:
        """获取Agent花名册（Dashboard用）
        
        Returns:
            Agent信息列表
        """
        roster = []
        for name, agent in self._agents.items():
            tier = "unknown"
            if self.information_policy:
                try:
                    tier = self.information_policy.get_tier(name).value
                except (ValueError, KeyError):
                    tier = "unknown"
            
            roster.append({
                "name": name,
                "display_name": getattr(agent, 'display_name', name),
                "tier": tier,
                "capabilities": getattr(agent, 'capabilities', []),
            })
        return roster


# ============================================================================
# 便捷函数
# ============================================================================

def create_orchestrator(
    agents: Optional[Dict[str, Any]] = None,
    llm_chat: Optional[Callable] = None,
    config: Optional[Dict[str, Any]] = None,
) -> NexusOrchestrator:
    """创建NexusOrchestrator的工厂函数
    
    Args:
        agents: 预构建的Agent字典
        llm_chat: LLM调用函数
        config: 额外配置
        
    Returns:
        NexusOrchestrator实例
    """
    return NexusOrchestrator(
        agents=agents,
        llm_chat=llm_chat,
        config=config,
    )
