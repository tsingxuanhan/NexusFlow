# -*- coding: utf-8 -*-
"""
规划者 (Planner) — 策略推理Agent (PRO模型) + StrategyAgent能力
XuanHub v4.0 Phase 2 — Planning Engine + TeLLAgent双Agent分离
"""

from base_agent import BaseAgent, AgentRole, AgentRunMode
from vector_memory import get_vector_memory
import logging

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
    """策略Agent — TeLLAgent双Agent分离的PRO模型端
    
    负责深度推理、任务分解、策略选择。
    与ExecutionAgent配合：Strategy思考→Execution执行→Strategy评估。
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
    
    def decompose(self, goal: str, depth: int = 2):
        """深度目标分解（返回TaskTree）"""
        return self.strategy.decompose(goal, depth)
    
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