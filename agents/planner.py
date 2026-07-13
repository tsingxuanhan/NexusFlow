# -*- coding: utf-8 -*-
"""
规划者 (Planner) — 策略推理Agent (PRO模型) + StrategyAgent能力
XuanHub v4.0 Phase 2 — Planning Engine + TeLLAgent双Agent分离
"""

from base_agent import BaseAgent, AgentRole, AgentRunMode
from vector_memory import get_vector_memory
import logging
import sys
import os

# 技能蒸馏：SkillRetriever导入
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
try:
    from skill_retriever import SkillRetriever, TaskSkillCard
    SKILL_RETRIEVER_AVAILABLE = True
except ImportError:
    SKILL_RETRIEVER_AVAILABLE = False
    SkillRetriever = None
    TaskSkillCard = None

logger = logging.getLogger("PlannerAgent")

PLANNER_SYSTEM_PROMPT = """你是"规划者"，铉枢项目中的策略推理核心。

## 核心职责
将高层目标分解为可执行的子任务，设计执行策略，评估执行结果。你是大脑，不是手。

## 思维原则
1. **先理解后拆解**: 确保完全理解目标再分解
2. **MECE分解**: 任务之间互斥且完全穷尽
3. **依赖优先**: 识别关键路径，先解决阻塞项
4. **风险前置**: 预判可能失败点，提前准备B计划
5. **经验复用**: 参考以往成功/失败的经验

## 输出规范
- 任务分解：编号+描述+依赖+预估难度
- 策略选择：说明为什么选这个策略而非其他
- 风险评估：概率+影响+应对方案
- 验收标准：如何判断子任务完成

## 任务树格式
使用Markdown层级，支持依赖标记和Agent分配：
1. [Planner] 需求分析与背景调研
2. [Executor] 实现数据处理模块 [依赖: T-1]
3. [Reviewer] 质量审查与测试 [依赖: T-2]"""


class StrategyAgent:
    """⚠️ DEPRECATED: 使用 PlannerAgent 代替。此类保留仅为向后兼容。
    
    策略Agent — TeLLAgent双Agent分离的PRO模型端（旧版实现）
    """
    
    def __init__(self, base_agent: BaseAgent):
        self.agent = base_agent
        self.role = AgentRole.PLANNER
    
    def decompose(self, goal: str, depth: int = 2) -> "TaskTree":
        """将高层目标分解为TaskTree（深度推理）
        
        Args:
            goal: 高层目标
            depth: 分解深度，默认2层
            
        Returns:
            TaskTree对象
        """
        prompt = f"""请对以下目标进行{depth}层深度任务分解：

## 目标
{goal}

要求：
- 第1层：主要阶段（3-5个）
- 第2层：每个阶段的子任务
{"- 第3层：每个子任务的具体步骤" if depth >= 3 else ""}

输出格式：
使用Markdown层级：
1. [阶段标题]
2. [子任务描述] [依赖: T-xxx, T-yyy]
- 支持标记Agent分配：[Planner]/[Researcher]/[Executor]/[Reviewer]"""

        from task_tree import TaskTree
        
        # 切到PLAN模式
        old_mode = self.agent.run_mode
        self.agent.set_run_mode("plan")
        
        try:
            response = self.agent.chat(prompt)
            tree = TaskTree.from_plan_text(response, goal=goal)
            
            logger.info(f"[StrategyAgent] 目标分解完成: {goal} → {tree.stats['total']}个任务")
            return tree
        finally:
            if old_mode:
                self.agent.set_run_mode(old_mode.value)
    
    def select_strategy(self, task) -> str:
        """选择执行策略：sequential/parallel/iterative/codeact"""
        from task_tree import TaskScheduler
        
        # 借鉴TaskScheduler的策略选择逻辑
        scheduler = TaskScheduler(self.agent.todo)
        strategy = scheduler._select_strategy(task)
        return strategy
    
    def evaluate_execution(self, result: str, expectation: str) -> float:
        """评估执行结果是否符合策略预期
        
        Returns:
            0.0~1.0 评分
        """
        prompt = f"""评估执行结果：

## 预期
{expectation}

## 实际结果
{result}

请给出0到1之间的评分：
- 1.0: 完全满足预期
- 0.5: 部分满足
- 0.0: 完全不符合

只输出评分数字:"""

        try:
            old_mode = self.agent.run_mode
            self.agent.set_run_mode("reflect")
            
            response = self.agent.chat(prompt).strip()
            import re
            match = re.search(r'(\d+\.?\d*)', response)
            if match:
                score = float(match.group(1))
                return min(1.0, max(0.0, score))
            
            return 0.5
        finally:
            if old_mode:
                self.agent.set_run_mode(old_mode.value)
    
    def propose_plan(self, goal: str, context: str = "") -> str:
        """提出策略方案（不分解）"""
        ctx = f"\n\n## 背景信息\n{context}" if context else ""
        prompt = f"""请为以下目标提出执行策略：

## 目标
{goal}
{ctx}

输出：
1. 整体策略思路
2. 关键阶段
3. 风险评估
4. 推荐的Agent组合"""
        return self.agent.chat(prompt)


class PlannerAgent(BaseAgent):
    """规划者 - 策略推理核心（PRO模型）"""
    
    def __init__(self, domain_name: str = None, **kwargs):
        super().__init__(
            name="Planner",
            model="pro",
            system_prompt=PLANNER_SYSTEM_PROMPT,
            role=AgentRole.PLANNER,
            domain_name=domain_name,
            **kwargs
        )
        self.memory = get_vector_memory()
        
        # Phase 2: StrategyAgent能力
        self.strategy = StrategyAgent(self)
        
        # 技能蒸馏：SkillRetriever初始化
        if SKILL_RETRIEVER_AVAILABLE:
            self.skill_retriever = SkillRetriever(
                insight_store=None,  # 后续由外部注入
                filepath=os.path.join(
                    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                    "data", "skill_graph.json"
                )
            )
            logger.info("[PlannerAgent] SkillRetriever初始化完成")
        else:
            self.skill_retriever = None
            logger.warning("[PlannerAgent] SkillRetriever导入失败，技能检索功能不可用")
        
        # A2A能力注册
        if self.a2a:
            self.register_a2a_action("plan_task", self.plan_task)
            self.register_a2a_action("decompose", self.decompose)
            self.register_a2a_action("evaluate", self.evaluate)
            self.register_a2a_action("replan", self.replan)
            self.register_a2a_action("propose_plan", self.propose_plan)
            
            self.register_a2a_capability("plan_task", "策略规划与任务分解", ["规划", "plan", "分解"])
            self.register_a2a_capability("decompose", "目标分解", ["分解", "decompose", "拆解"])
            self.register_a2a_capability("evaluate", "评估执行结果", ["评估", "evaluate", "验证"])
            self.register_a2a_capability("replan", "重新规划", ["重规划", "replan", "调整"])
            self.register_a2a_capability("propose_plan", "提出策略方案", ["策略", "propose"])
    
    def plan_task(self, goal: str, context: str = None) -> str:
        """策略规划"""
        ctx = f"\n\n## 背景信息\n{context}" if context else ""
        return self.plan(f"{goal}{ctx}")
    
    def decompose(self, goal: str, depth: int = 2) -> "TaskTree":
        """深度目标分解（返回TaskTree）
        
        Phase 7: 分解后自动标记需要认知分工的节点。
        Phase 8 (技能蒸馏融合): 分解前检索相关Skill Card作为决策先验。
        """
        # 技能蒸馏融合：检索相关技能
        skill_context = ""
        if self.skill_retriever:
            skill_context = self.skill_retriever.retrieve_as_prompt(goal)
            if skill_context:
                logger.info(f"[PlannerAgent] 注入{len(self.skill_retriever.retrieve(goal))}个技能先验")
        
        # 构建增强目标
        enhanced_goal = goal
        if skill_context:
            enhanced_goal = f"{skill_context}\n\n## 任务目标\n{goal}"
        
        tree = self.strategy.decompose(enhanced_goal, depth)
        
        # Phase 7: 自动识别需要认知分工的节点
        for node in tree.root.flatten():
            if self._requires_collaborative_reasoning(node):
                node.execution_mode = "cognitive_division"
                node.decomposition_strategy = self._select_cdol_strategy(node)
                logger.info(
                    f"[PlannerAgent] 节点 {node.id} 标记为认知分工: "
                    f"strategy={node.decomposition_strategy}"
                )
        
        return tree
    
    def _requires_collaborative_reasoning(self, node) -> bool:
        """Phase 7: 判断节点是否需要认知分工"""
        signals = [
            "验证" in node.description or "假设" in node.description,
            "对比" in node.description or "评估" in node.description,
            getattr(node, 'action_type', '') == "review",
            len(node.dependencies) >= 2,
        ]
        return sum(signals) >= 2
    
    def _select_cdol_strategy(self, node) -> str:
        """Phase 7: 为认知分工节点选择分解策略
        Phase 8 (技能蒸馏融合): 优先考虑任务技能经验
        """
        desc = node.description.lower()
        
        # 技能蒸馏融合：检查是否有相关任务技能
        if self.skill_retriever:
            relevant_skills = self.skill_retriever.retrieve(desc, top_k=1)
            if relevant_skills:
                logger.info(f"[PlannerAgent] 检测到相关浏览器技能: {relevant_skills[0].applicable_scenario}")
        
        if any(kw in desc for kw in ["实验", "数据", "文献", "evidence"]):
            return "evidence_split"
        if any(kw in desc for kw in ["假设", "论证", "验证", "hypothesis"]):
            return "role_constraint"
        if any(kw in desc for kw in ["方法", "设计", "架构", "method"]):
            return "layer_separation"
        if any(kw in desc for kw in ["趋势", "演进", "发展", "trend"]):
            return "time_slice"
        if any(kw in desc for kw in ["对比", "评估", "compare"]):
            return "abstraction_level"
        return "evidence_split"
    
    def evaluate(self, result: str, expectation: str) -> str:
        """评估执行结果"""
        return self.reflect(result, expectation)
    
    def replan(self, failed_step: str, reason: str, original_plan: str) -> str:
        """局部重规划"""
        prompt = f"""以下执行步骤失败，需要局部重规划：

## 失败步骤
{failed_step}

## 失败原因
{reason}

## 原始计划
{original_plan}

要求：
1. 只修改失败步骤及其后续依赖
2. 保持已完成步骤不变
3. 提供替代方案
4. 评估替代方案的风险"""
        return self.chat(prompt)
    
    def propose_plan(self, goal: str, context: str = "") -> str:
        """提出策略方案"""
        return self.strategy.propose_plan(goal, context)