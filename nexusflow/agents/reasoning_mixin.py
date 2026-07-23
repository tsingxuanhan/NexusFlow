# -*- coding: utf-8 -*-
"""
推理Mixin — 策略规划、执行、反思、Tree-of-Thought
ReasoningMixin extracted from base_agent.py
"""

import re
import logging
from typing import List, Dict, Optional, Any

from .models import AgentRole, AgentRunMode

logger = logging.getLogger("BaseAgent")


class ReasoningMixin:
    """推理相关方法：plan / execute_step / reflect / plan_with_tree / reflect_on_results / think_with_tot / execute_tree"""

    def plan(self, goal: str) -> str:
        """策略规划 — 用PRO模型分解目标

        Args:
            goal: 高层目标描述

        Returns:
            任务分解和策略方案
        """
        old_mode = self.run_mode
        self._apply_run_mode(AgentRunMode.PLAN)

        todo_context = self.todo.to_context()
        todo_section = f"\n\n{todo_context}" if todo_context else ""

        prompt = f"""请对以下目标进行策略性分析和任务分解：

## 目标
{goal}
{todo_section}

## 要求
1. 将目标分解为可执行的子任务
2. 识别子任务间的依赖关系
3. 为每个子任务指定最合适的执行策略
4. 评估潜在风险和备选方案

输出格式：
### 任务分解
[子任务列表，含依赖关系]

### 执行策略
[每个子任务的策略选择]

### 风险评估
[潜在问题与应对]"""

        result = self.chat(prompt)

        # 自动添加子任务到TodoProvider
        self._parse_plan_to_todos(result)

        # 恢复原模式
        if old_mode:
            self._apply_run_mode(old_mode)

        return result

    def execute_step(self, step: str) -> str:
        """精确执行 — 用Flash模型执行步骤

        Args:
            step: 要执行的具体步骤

        Returns:
            执行结果
        """
        old_mode = self.run_mode
        self._apply_run_mode(AgentRunMode.EXECUTE)

        todo_context = self.todo.to_context()
        todo_section = f"\n\n{todo_context}" if todo_context else ""

        prompt = f"""请精确执行以下步骤：

## 步骤
{step}
{todo_section}

## 要求
1. 严格按照步骤描述执行
2. 输出具体的、可验证的结果
3. 如果需要工具调用，明确说明
4. 如果遇到问题，记录问题并尝试替代方案"""

        result = self.chat(prompt)

        # 恢复原模式
        if old_mode:
            self._apply_run_mode(old_mode)

        return result

    def reflect(self, result: str, expectation: str = "") -> str:
        """反思评估 — 用PRO模型评估执行结果

        Args:
            result: 执行结果
            expectation: 预期目标

        Returns:
            反思评估报告
        """
        old_mode = self.run_mode
        self._apply_run_mode(AgentRunMode.REFLECT)

        prompt = f"""请评估以下执行结果：

## 预期目标
{expectation or "（未指定）"}

## 实际结果
{result}

## 评估维度
1. **目标达成度**: 结果是否满足预期？百分比评估。
2. **质量问题**: 有无错误、遗漏或不一致？
3. **改进空间**: 如何优化？
4. **经验提炼**: 从中可以总结什么规则或经验？

输出格式：
- 达成度: X%
- 问题: [列表]
- 改进: [建议]
- 经验: [可复用规则]"""

        reflection = self.chat(prompt)

        # 恢复原模式
        if old_mode:
            self._apply_run_mode(old_mode)

        return reflection

    def _parse_plan_to_todos(self, plan_text: str) -> None:
        """从规划文本中提取子任务添加到TodoProvider"""
        # 简单提取：找数字开头的行作为子任务
        lines = plan_text.split("\n")
        for line in lines:
            stripped = line.strip()
            # 匹配 "1." "1)" "步骤1" 等模式
            if re.match(r'^(\d+[\.\)、]|步骤\d+|Step\s*\d+)', stripped):
                # 去掉序号前缀
                task_text = re.sub(r'^(\d+[\.\)、]|步骤\d+[:：]?|Step\s*\d+[:：]?)\s*', '', stripped)
                if task_text and len(task_text) > 3:
                    self.todo.add(task_text, priority=0)

    # ============ v4.0 Phase 2: 规划引擎集成 ============

    def plan_with_tree(self, goal: str, depth: int = 2) -> Any:
        """用TaskTree进行层次化规划

        Phase 2核心方法：plan→decompose→TaskTree

        Args:
            goal: 高层目标
            depth: 分解深度

        Returns:
            TaskTree对象
        """
        from nexusflow.cognition.task_tree import TaskTree

        # 切到PLAN模式
        old_mode = self.run_mode
        self._apply_run_mode(AgentRunMode.PLAN)

        try:
            prompt = f"""请对以下目标进行{depth}层深度任务分解：

## 目标
{goal}

## 要求
- 第1层：主要阶段（3-5个），每个用编号标注
- 第2层：每个阶段的子任务
{"- 第3层：每个子任务的具体步骤" if depth >= 3 else ""}
- 标注依赖关系：[依赖: T-xxx]
- 标注分配Agent：[Planner]/[Researcher]/[Executor]/[Reviewer]

输出Markdown层级格式。"""

            response = self.chat(prompt)
            tree = TaskTree.from_plan_text(response, goal=goal)

            # 将叶子节点添加到TodoProvider
            for node in tree.root.flatten():
                if node.is_leaf and node.status == "pending":
                    self.todo.add(node.description, priority=0)

            logger.info(f"[{self.name}] TaskTree规划完成: {tree.stats['total']}个任务, 进度基线0%")
            return tree

        finally:
            if old_mode:
                self._apply_run_mode(old_mode)

    def reflect_on_results(
        self,
        results: Dict[str, str],
        expectations: Dict[str, str] = None,
        plan_summary: str = "",
    ) -> Any:
        """对执行结果进行反思

        Phase 2核心方法：reflect→经验提取→重规划决策

        Args:
            results: {task_id: result_text}
            expectations: {task_id: expectation_text}
            plan_summary: 计划摘要

        Returns:
            Reflection对象
        """
        from nexusflow.cognition.reflection import ReflectionLoop

        # 创建反思循环（使用当前agent的chat函数）
        reflection_loop = ReflectionLoop(
            strategy_chat=self.chat,
            flash_chat=None,  # 用规则化快速评估
        )

        # 如果是PRO角色，用自身做深度反思
        if self.agent_role == AgentRole.PLANNER:
            reflection_loop.flash_chat = self.chat

        reflection = reflection_loop.reflect(
            plan_summary=plan_summary,
            results=results,
            expectations=expectations or {},
        )

        # 将经验规则记录到TodoProvider
        for lesson in reflection.lessons_learned:
            self.todo.add(f"📝 经验: {lesson}", priority=-1)

        logger.info(f"[{self.name}] 反思完成: 达成度{reflection.achievement_score:.0%}, "
                     f"重规划={'需要' if reflection.should_replan else '不需要'}")

        return reflection

    def think_with_tot(self, problem: str, context: str = "") -> Dict[str, Any]:
        """用Tree of Thought推理复杂问题

        Phase 2核心方法：ToT推理→最优路径→解答

        Args:
            problem: 复杂问题
            context: 背景信息

        Returns:
            ToT搜索结果（含solution, path, score等）
        """
        from nexusflow.cognition.tot import TreeOfThought

        tot = TreeOfThought(
            strategy_chat=self.chat,
            evaluation_chat=None,  # 用自身快速评估
            branch_factor=3,
            max_depth=4,
        )

        result = tot.search(problem, context)

        logger.info(f"[{self.name}] ToT推理完成: 探索{result['branches_explored']}个分支, "
                     f"最优评分{result['best_score']:.1f}")

        return result

    def execute_tree(self, tree, executor_agent=None) -> Dict[str, str]:
        """执行TaskTree中的所有就绪任务

        Phase 2核心方法：调度→执行→更新状态

        Args:
            tree: TaskTree对象
            executor_agent: 执行Agent（None则用自身）

        Returns:
            {task_id: result_text}
        """
        from nexusflow.cognition.task_tree import TaskScheduler

        results = {}
        executor = executor_agent or self

        # 生成调度计划
        scheduler = TaskScheduler(tree)
        steps = scheduler.schedule()

        for step in steps:
            task_id = step["task_id"]
            task_node = tree.find(task_id)
            if not task_node:
                continue

            # 标记为运行中
            task_node.update_status("running")

            # 执行
            if hasattr(executor, 'execution') and hasattr(executor.execution, 'execute_task_node'):
                result = executor.execution.execute_task_node(task_node)
            else:
                result = executor.execute_step(task_node.description)
                task_node.update_status("done", result=result)

            results[task_id] = result

        # 汇总统计
        stats = tree.stats
        logger.info(f"[{self.name}] TaskTree执行完成: {stats['done']}/{stats['total']}成功, "
                     f"{stats['failed']}失败, 进度{tree.progress:.0%}")

        return results
