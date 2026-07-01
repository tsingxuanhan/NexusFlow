# -*- coding: utf-8 -*-
"""
铉枢·炉守 Autonomous Goal Handler — 自主目标分解
XuanHub Autonomous Goal Handler

从模糊用户意图到可执行任务树的自主分解引擎：
1. StrategyAgent(PRO) 解析意图 → TaskTree
2. StrategyAgent 分配 Agent + 策略
3. ExecutionAgent(Flash) 逐步执行
4. StrategyAgent 评估结果质量
5. ReflectionLoop 提取经验
6. SleeptimeEngine 更新规则
"""

import json
import re
import time
import logging
from typing import Any, Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger("AutonomousGoal")


class GoalStatus(Enum):
    """目标执行状态"""
    PENDING = "pending"
    DECOMPOSING = "decomposing"
    EXECUTING = "executing"
    EVALUATING = "evaluating"
    REFLECTING = "reflecting"
    COMPLETED = "completed"
    FAILED = "failed"
    PARTIAL = "partial"


@dataclass
class GoalResult:
    """目标执行结果"""
    goal: str
    status: GoalStatus
    task_tree: Optional[Dict] = None
    execution_log: List[Dict] = field(default_factory=list)
    final_output: str = ""
    confidence: float = 0.0
    lessons_learned: List[str] = field(default_factory=list)
    elapsed_seconds: float = 0.0
    total_tokens: int = 0

    def to_dict(self) -> Dict:
        return {
            "goal": self.goal,
            "status": self.status.value,
            "task_tree": self.task_tree,
            "execution_log": self.execution_log,
            "final_output": self.final_output,
            "confidence": self.confidence,
            "lessons_learned": self.lessons_learned,
            "elapsed_seconds": round(self.elapsed_seconds, 2),
            "total_tokens": self.total_tokens,
        }


class AutonomousGoalHandler:
    """
    自主目标处理器 — 从模糊意图到结构化执行

    核心流程：
    1. 意图解析 (PRO) — 理解用户真正要什么
    2. 任务分解 (PRO) — 拆成可执行的TaskTree
    3. Agent分配 — 自动分配最合适的Agent
    4. 逐步执行 (Flash) — ExecutionAgent执行CodeAct
    5. 结果评估 (PRO) — StrategyAgent评估质量
    6. 经验提取 — ReflectionLoop提炼规则

    用法：
        handler = AutonomousGoalHandler(strategy_chat=planner.chat, execution_chat=executor.chat)
        result = handler.handle("调研2026年最有潜力的3个AI Agent框架")
    """

    def __init__(
        self,
        strategy_chat: Any = None,
        execution_chat: Any = None,
        memory_manager: Any = None,
        sleeptime_engine: Any = None,
        max_decomposition_depth: int = 3,
        max_execution_steps: int = 20,
        confidence_threshold: float = 0.6,
        api_endpoint: Optional[str] = None,
        api_key: Optional[str] = None,
    ):
        self.strategy_chat = strategy_chat
        self.execution_chat = execution_chat
        self.memory_manager = memory_manager
        self.sleeptime_engine = sleeptime_engine
        self.max_decomposition_depth = max_decomposition_depth
        self.max_execution_steps = max_execution_steps
        self.confidence_threshold = confidence_threshold
        self.api_endpoint = api_endpoint
        self.api_key = api_key

        # 执行统计
        self._stats = {
            "goals_processed": 0,
            "goals_completed": 0,
            "goals_failed": 0,
            "avg_confidence": 0.0,
            "total_tasks_generated": 0,
        }

    # ============ 核心入口 ============

    def handle(self, goal: str, context: str = "") -> GoalResult:
        """
        处理自主目标 — 从模糊意图到完整结果

        Args:
            goal: 用户的高层目标（可以是模糊的）
            context: 额外上下文（如之前的对话、约束条件等）

        Returns:
            GoalResult: 包含执行结果、任务树、经验等
        """
        start_time = time.time()
        result = GoalResult(goal=goal, status=GoalStatus.PENDING)
        self._stats["goals_processed"] += 1

        try:
            # Phase 1: 意图解析
            logger.info(f"[AutonomousGoal] Phase 1: Parsing intent — {goal[:80]}")
            parsed_intent = self._parse_intent(goal, context)
            result.execution_log.append({"phase": "parse_intent", "result": parsed_intent})

            # Phase 2: 任务分解
            logger.info("[AutonomousGoal] Phase 2: Decomposing into task tree")
            result.status = GoalStatus.DECOMPOSING
            task_tree = self._decompose(parsed_intent, goal)
            result.task_tree = task_tree
            task_count = self._count_tasks(task_tree)
            self._stats["total_tasks_generated"] += task_count
            result.execution_log.append({"phase": "decompose", "tasks": task_count})

            # Phase 3: Agent分配
            agent_assignments = self._assign_agents(task_tree)
            result.execution_log.append({"phase": "assign_agents", "assignments": agent_assignments})

            # Phase 4: 逐步执行
            logger.info(f"[AutonomousGoal] Phase 4: Executing {task_count} tasks")
            result.status = GoalStatus.EXECUTING
            exec_results = self._execute_tree(task_tree, agent_assignments)
            result.execution_log.append({"phase": "execute", "results": exec_results})

            # Phase 5: 结果评估
            logger.info("[AutonomousGoal] Phase 5: Evaluating results")
            result.status = GoalStatus.EVALUATING
            evaluation = self._evaluate(goal, exec_results)
            result.confidence = evaluation.get("confidence", 0.0)
            result.execution_log.append({"phase": "evaluate", "confidence": result.confidence})

            # Phase 6: 经验提取
            logger.info("[AutonomousGoal] Phase 6: Extracting lessons")
            result.status = GoalStatus.REFLECTING
            lessons = self._extract_lessons(goal, exec_results, evaluation)
            result.lessons_learned = lessons

            # 生成最终输出
            result.final_output = self._synthesize_output(goal, exec_results, evaluation)

            # 判断最终状态
            if result.confidence >= self.confidence_threshold:
                result.status = GoalStatus.COMPLETED
                self._stats["goals_completed"] += 1
            elif result.confidence >= 0.3:
                result.status = GoalStatus.PARTIAL
                self._stats["goals_completed"] += 1
            else:
                result.status = GoalStatus.FAILED
                self._stats["goals_failed"] += 1

            # 记录到记忆系统
            if self.memory_manager:
                self._record_to_memory(goal, result)

        except Exception as e:
            logger.error(f"[AutonomousGoal] Failed: {e}")
            result.status = GoalStatus.FAILED
            result.final_output = f"执行失败: {str(e)}"
            self._stats["goals_failed"] += 1

        result.elapsed_seconds = time.time() - start_time

        # 更新统计
        completed = self._stats["goals_completed"]
        total = self._stats["goals_processed"]
        if total > 0:
            running_avg = self._stats["avg_confidence"]
            self._stats["avg_confidence"] = (
                running_avg * (total - 1) + result.confidence
            ) / total

        logger.info(
            f"[AutonomousGoal] Result: {result.status.value}, "
            f"confidence={result.confidence:.2f}, "
            f"elapsed={result.elapsed_seconds:.1f}s"
        )
        return result

    # ============ Phase 1: 意图解析 ============

    def _parse_intent(self, goal: str, context: str = "") -> Dict:
        """
        解析用户意图 — 从模糊目标中提取：
        - 核心意图 (what)
        - 期望输出 (deliverable)
        - 约束条件 (constraints)
        - 领域 (domain)
        - 紧急度 (urgency)
        """
        prompt = f"""分析以下用户目标，提取结构化意图信息：

用户目标: {goal}
额外上下文: {context or "无"}

请用JSON格式返回：
{{
  "core_intent": "核心意图的一句话概括",
  "deliverable": "期望的交付物（报告/代码/数据/方案）",
  "domain": "涉及的领域（materials/ai_ml/cs/general等）",
  "constraints": ["约束1", "约束2"],
  "urgency": "high/medium/low",
  "needs_research": true/false,
  "needs_code": true/false,
  "needs_analysis": true/false,
  "estimated_complexity": "simple/medium/complex",
  "suggested_strategy": "sequential/parallel/iterative"
}}

只返回JSON，不要其他内容。"""

        response = self._call_strategy(prompt)
        try:
            # 提取JSON
            json_match = re.search(r'\{[\s\S]*\}', response)
            if json_match:
                return json.loads(json_match.group())
        except json.JSONDecodeError:
            pass

        # 降级：启发式解析
        return self._heuristic_parse(goal)

    def _heuristic_parse(self, goal: str) -> Dict:
        """启发式意图解析（无LLM时降级）"""
        goal_lower = goal.lower()

        # 领域推断
        domain = "general"
        domain_keywords = {
            "materials": ["材料", "水泥", "混凝土", "纳米", "建材", "SSC", "LC3"],
            "ai_ml": ["AI", "模型", "训练", "深度学习", "Agent", "LLM", "RAG"],
            "cs": ["代码", "编程", "算法", "数据库", "服务器"],
        }
        for d, keywords in domain_keywords.items():
            if any(kw in goal_lower for kw in keywords):
                domain = d
                break

        needs_research = any(kw in goal_lower for kw in ["调研", "研究", "最新", "进展", "调研"])
        needs_code = any(kw in goal_lower for kw in ["实现", "开发", "写", "代码", "编程"])
        needs_analysis = any(kw in goal_lower for kw in ["分析", "对比", "评估", "比较"])

        return {
            "core_intent": goal[:100],
            "deliverable": "综合报告" if needs_research else "执行结果",
            "domain": domain,
            "constraints": [],
            "urgency": "medium",
            "needs_research": needs_research,
            "needs_code": needs_code,
            "needs_analysis": needs_analysis,
            "estimated_complexity": "medium",
            "suggested_strategy": "parallel" if needs_research else "sequential",
        }

    # ============ Phase 2: 任务分解 ============

    def _decompose(self, parsed_intent: Dict, original_goal: str) -> Dict:
        """
        将意图分解为任务树 — 使用StrategyAgent(PRO)

        返回嵌套字典格式的任务树：
        {
            "task": "主任务",
            "status": "pending",
            "agent": "planner",
            "subtasks": [
                {"task": "子任务1", "status": "pending", "agent": "researcher"},
                ...
            ]
        }
        """
        prompt = f"""将以下目标分解为可执行的任务树。

核心意图: {parsed_intent.get('core_intent', original_goal)}
领域: {parsed_intent.get('domain', 'general')}
需要研究: {parsed_intent.get('needs_research', False)}
需要代码: {parsed_intent.get('needs_code', False)}
需要分析: {parsed_intent.get('needs_analysis', False)}
建议策略: {parsed_intent.get('suggested_strategy', 'sequential')}

请用JSON格式返回任务树（最多{self.max_decomposition_depth}层）：
{{
  "task": "主任务描述",
  "agent": "planner",
  "strategy": "sequential/parallel/iterative",
  "subtasks": [
    {{
      "task": "子任务1",
      "agent": "researcher/executor/reviewer",
      "action_type": "research/execute/review/analyze",
      "dependencies": []
    }}
  ]
}}

每个子任务应该：
1. 可独立执行（有明确的输入和预期输出）
2. 分配给合适的Agent角色
3. 标注依赖关系（如果有的话）

只返回JSON，不要其他内容。"""

        response = self._call_strategy(prompt)
        try:
            json_match = re.search(r'\{[\s\S]*\}', response)
            if json_match:
                tree = json.loads(json_match.group())
                self._normalize_tree(tree)
                return tree
        except json.JSONDecodeError:
            pass

        # 降级：自动生成简单任务树
        return self._auto_decompose(parsed_intent, original_goal)

    def _auto_decompose(self, parsed_intent: Dict, original_goal: str) -> Dict:
        """自动生成简单任务树（无LLM时降级）"""
        subtasks = []

        if parsed_intent.get("needs_research"):
            subtasks.append({
                "task": f"搜索和收集与「{parsed_intent.get('core_intent', original_goal)[:30]}」相关的信息",
                "agent": "researcher",
                "action_type": "research",
                "dependencies": [],
            })

        if parsed_intent.get("needs_analysis"):
            subtasks.append({
                "task": "分析收集到的信息，提取关键发现",
                "agent": "planner",
                "action_type": "analyze",
                "dependencies": [0] if subtasks else [],
            })

        subtasks.append({
            "task": "整合结果并生成最终交付物",
            "agent": "executor",
            "action_type": "execute",
            "dependencies": list(range(len(subtasks))),
        })

        subtasks.append({
            "task": "审查最终输出的质量和完整性",
            "agent": "reviewer",
            "action_type": "review",
            "dependencies": [len(subtasks) - 1],
        })

        return {
            "task": original_goal,
            "agent": "planner",
            "strategy": parsed_intent.get("suggested_strategy", "sequential"),
            "subtasks": subtasks,
        }

    def _normalize_tree(self, tree: Dict) -> None:
        """规范化任务树 — 确保必要字段存在"""
        tree.setdefault("agent", "planner")
        tree.setdefault("strategy", "sequential")
        tree.setdefault("subtasks", [])
        for sub in tree.get("subtasks", []):
            sub.setdefault("agent", "executor")
            sub.setdefault("action_type", "execute")
            sub.setdefault("dependencies", [])
            sub.setdefault("status", "pending")

    # ============ Phase 3: Agent分配 ============

    def _assign_agents(self, task_tree: Dict) -> Dict[str, str]:
        """
        为任务树中的每个任务分配Agent

        返回: {task_description: agent_name}
        """
        assignments = {}

        # 主任务
        main_task = task_tree.get("task", "main")
        main_agent = task_tree.get("agent", "planner")
        assignments[main_task] = main_agent

        # 子任务
        for sub in task_tree.get("subtasks", []):
            task_desc = sub.get("task", "unknown")
            agent = sub.get("agent", "executor")
            assignments[task_desc] = agent

        return assignments

    # ============ Phase 4: 逐步执行 ============

    def _execute_tree(self, task_tree: Dict, assignments: Dict) -> List[Dict]:
        """
        按顺序/并行执行任务树

        Returns:
            执行结果列表
        """
        results = []
        subtasks = task_tree.get("subtasks", [])
        strategy = task_tree.get("strategy", "sequential")

        if strategy == "parallel":
            # 并行：先执行所有无依赖的，再执行有依赖的
            results = self._execute_parallel(subtasks, assignments)
        elif strategy == "iterative":
            # 迭代：循环执行直到达标
            results = self._execute_iterative(subtasks, assignments)
        else:
            # 顺序：按顺序执行
            results = self._execute_sequential(subtasks, assignments)

        return results

    def _execute_sequential(self, subtasks: List[Dict], assignments: Dict) -> List[Dict]:
        """顺序执行"""
        results = []
        for i, sub in enumerate(subtasks):
            task_desc = sub.get("task", f"subtask_{i}")
            agent = sub.get("agent", "executor")
            action_type = sub.get("action_type", "execute")

            logger.info(f"[AutonomousGoal] Executing [{i+1}/{len(subtasks)}] {task_desc[:60]}")

            # 构建执行prompt
            context_from_prev = ""
            if results:
                prev_summary = "; ".join(
                    r.get("output", "")[:100] for r in results[-2:] if r.get("output")
                )
                context_from_prev = f"前置任务结果摘要: {prev_summary}"

            exec_prompt = self._build_exec_prompt(task_desc, action_type, context_from_prev)
            output = self._call_execution(exec_prompt)

            results.append({
                "task": task_desc,
                "agent": agent,
                "action_type": action_type,
                "output": output,
                "status": "completed" if output else "failed",
            })

        return results

    def _execute_parallel(self, subtasks: List[Dict], assignments: Dict) -> List[Dict]:
        """
        并行执行 — 简化实现：按依赖层级顺序执行
        同层内顺序执行（真并行需要异步框架）
        """
        results = []
        completed_indices = set()

        # 拓扑排序
        for i, sub in enumerate(subtasks):
            deps = sub.get("dependencies", [])
            # 等待依赖完成
            for dep_idx in deps:
                if dep_idx < len(results) and results[dep_idx].get("status") == "completed":
                    completed_indices.add(dep_idx)

            task_desc = sub.get("task", f"subtask_{i}")
            agent = sub.get("agent", "executor")
            action_type = sub.get("action_type", "execute")

            # 收集依赖结果作为上下文
            dep_context = ""
            for dep_idx in deps:
                if dep_idx < len(results):
                    dep_context += f"依赖任务结果: {results[dep_idx].get('output', '')[:200]}\n"

            exec_prompt = self._build_exec_prompt(task_desc, action_type, dep_context)
            output = self._call_execution(exec_prompt)

            results.append({
                "task": task_desc,
                "agent": agent,
                "action_type": action_type,
                "output": output,
                "status": "completed" if output else "failed",
            })
            completed_indices.add(i)

        return results

    def _execute_iterative(self, subtasks: List[Dict], assignments: Dict) -> List[Dict]:
        """迭代执行 — 循环执行直到达标"""
        results = []
        max_iterations = 3

        for iteration in range(max_iterations):
            iteration_results = self._execute_sequential(subtasks, assignments)

            # 评估本轮结果
            if iteration_results:
                last_output = iteration_results[-1].get("output", "")
                quality = self._quick_quality_check(last_output)

                if quality >= self.confidence_threshold:
                    results = iteration_results
                    break

                # 未达标：修改子任务描述加入反馈
                feedback = f"第{iteration+1}轮结果不够好(质量={quality:.1f})，需要改进。"
                for sub in subtasks:
                    if sub.get("action_type") == "execute":
                        sub["task"] = f"{sub['task']} (注意: {feedback})"

                results = iteration_results
            else:
                break

        return results

    def _build_exec_prompt(self, task: str, action_type: str, context: str = "") -> str:
        """构建执行prompt"""
        type_instructions = {
            "research": "搜索和收集信息，列出关键发现和来源。",
            "execute": "执行具体任务，给出明确的结果和交付物。",
            "review": "审查内容的质量、准确性和完整性，指出问题和改进建议。",
            "analyze": "深入分析数据或信息，提取洞察和结论。",
        }

        instruction = type_instructions.get(action_type, "完成以下任务。")

        prompt = f"""{instruction}

任务: {task}
"""
        if context:
            prompt += f"\n上下文:\n{context}\n"

        prompt += "\n请给出详细、结构化的结果。"
        return prompt

    # ============ Phase 5: 结果评估 ============

    def _evaluate(self, original_goal: str, exec_results: List[Dict]) -> Dict:
        """
        评估执行结果的质量 — StrategyAgent(PRO)
        """
        # 汇总执行结果
        outputs_summary = "\n".join(
            f"[{r.get('agent', '?')}] {r.get('output', '')[:200]}"
            for r in exec_results
        )

        prompt = f"""评估以下任务执行结果的质量。

原始目标: {original_goal}

执行结果:
{outputs_summary}

请评估：
1. 目标达成度 (0.0-1.0)
2. 结果完整性 (0.0-1.0)
3. 信息准确性 (0.0-1.0)
4. 综合置信度 (0.0-1.0)
5. 缺失项（如果有）
6. 改进建议

用JSON返回:
{{
  "goal_achievement": 0.0,
  "completeness": 0.0,
  "accuracy": 0.0,
  "confidence": 0.0,
  "missing_items": [],
  "improvement_suggestions": []
}}

只返回JSON。"""

        response = self._call_strategy(prompt)
        try:
            json_match = re.search(r'\{[\s\S]*\}', response)
            if json_match:
                return json.loads(json_match.group())
        except json.JSONDecodeError:
            pass

        # 降级：基于结果长度和数量启发式评估
        avg_output_len = sum(len(r.get("output", "")) for r in exec_results) / max(len(exec_results), 1)
        confidence = min(1.0, avg_output_len / 500) * 0.7  # 粗略估计
        completed_count = sum(1 for r in exec_results if r.get("status") == "completed")
        confidence += 0.3 * (completed_count / max(len(exec_results), 1))

        return {
            "goal_achievement": confidence,
            "completeness": confidence * 0.9,
            "accuracy": 0.6,
            "confidence": min(confidence, 1.0),
            "missing_items": [],
            "improvement_suggestions": [],
        }

    def _quick_quality_check(self, output: str) -> float:
        """快速质量检查（不调LLM）"""
        if not output:
            return 0.0
        # 启发式：长度+结构化程度
        score = 0.0
        score += min(0.3, len(output) / 1000)  # 长度
        score += 0.2 if any(kw in output for kw in ["结论", "总结", "结果", "发现"]) else 0
        score += 0.2 if any(kw in output for kw in ["1.", "2.", "一、", "二、"]) else 0  # 有编号
        score += 0.3 if len(output) > 300 else 0
        return min(score, 1.0)

    # ============ Phase 6: 经验提取 ============

    def _extract_lessons(self, goal: str, exec_results: List[Dict], evaluation: Dict) -> List[str]:
        """从执行过程中提取经验教训"""
        lessons = []

        confidence = evaluation.get("confidence", 0.0)

        if confidence >= 0.8:
            lessons.append(f"「{goal[:30]}」类型任务执行成功，当前策略有效")
        elif confidence >= 0.5:
            lessons.append(f"「{goal[:30]}」部分达成，可能需要更多研究步骤")
        else:
            lessons.append(f"「{goal[:30]}」执行不佳，需要调整分解策略或增加执行步骤")

        # 从执行结果中提取模式
        failed_tasks = [r for r in exec_results if r.get("status") == "failed"]
        if failed_tasks:
            lessons.append(f"{len(failed_tasks)}个子任务失败，需要检查Agent分配和执行策略")

        # 建议改进
        for suggestion in evaluation.get("improvement_suggestions", [])[:2]:
            lessons.append(suggestion)

        return lessons

    # ============ 记忆记录 ============

    def _record_to_memory(self, goal: str, result: GoalResult) -> None:
        """将执行结果记录到记忆系统"""
        try:
            # Recall: 记录交互经验
            outcome = "success" if result.status == GoalStatus.COMPLETED else "partial"
            self.memory_manager.remember(
                content=f"自主目标: {goal} → {result.status.value} (置信度={result.confidence:.2f})",
                memory_type="recall",
                episode_type=EpisodeType.INTERACTION if hasattr(EpisodeType, "INTERACTION") else None,
                importance=0.5 + result.confidence * 0.3,
                outcome=outcome,
                lessons="; ".join(result.lessons_learned[:3]),
                tags=["autonomous", "goal"],
            )

            # Core: 更新活跃上下文
            if result.status == GoalStatus.COMPLETED:
                self.memory_manager.remember(
                    content=f"最近完成的自主目标: {goal[:60]} (置信度={result.confidence:.2f})",
                    memory_type="core",
                    block="active_context",
                )
        except Exception as e:
            logger.warning(f"[AutonomousGoal] Failed to record to memory: {e}")

    # ============ 输出合成 ============

    def _synthesize_output(self, goal: str, exec_results: List[Dict], evaluation: Dict) -> str:
        """合成最终输出"""
        parts = [f"# {goal}\n"]

        for r in exec_results:
            agent = r.get("agent", "?")
            task = r.get("task", "")
            output = r.get("output", "")
            parts.append(f"## [{agent}] {task}\n{output}\n")

        # 添加评估摘要
        confidence = evaluation.get("confidence", 0.0)
        parts.append(f"\n---\n置信度: {confidence:.0%}")

        missing = evaluation.get("missing_items", [])
        if missing:
            parts.append(f"缺失项: {', '.join(missing)}")

        return "\n".join(parts)

    # ============ 工具方法 ============

    def _count_tasks(self, tree: Dict) -> int:
        """计算任务树中的任务总数"""
        count = 1  # 主任务
        for sub in tree.get("subtasks", []):
            count += 1
            count += self._count_tasks(sub) if isinstance(sub, dict) and "subtasks" in sub else 0
        return count

    def _call_strategy(self, prompt: str) -> str:
        """调用StrategyAgent(PRO)"""
        if self.strategy_chat:
            try:
                return self.strategy_chat(prompt)
            except Exception as e:
                logger.warning(f"[AutonomousGoal] Strategy call failed: {e}")
        return self._call_api(prompt, model="pro")

    def _call_execution(self, prompt: str) -> str:
        """调用ExecutionAgent(Flash)"""
        if self.execution_chat:
            try:
                return self.execution_chat(prompt)
            except Exception as e:
                logger.warning(f"[AutonomousGoal] Execution call failed: {e}")
        return self._call_api(prompt, model="flash")

    def _call_api(self, prompt: str, model: str = "flash") -> str:
        """直接调用API（无Agent时的降级）"""
        if not self.api_endpoint or not self.api_key:
            return ""

        try:
            import urllib.request
            model_name = "deepseek-v4-pro" if model == "pro" else "deepseek-v4-flash"
            data = json.dumps({
                "model": model_name,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 1.0 if model == "pro" else 0.3,
                "max_tokens": 2048,
            }).encode("utf-8")

            req = urllib.request.Request(
                self.api_endpoint,
                data=data,
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {self.api_key}",
                },
            )
            with urllib.request.urlopen(req, timeout=60) as resp:
                result = json.loads(resp.read().decode("utf-8"))
                return result["choices"][0]["message"]["content"]
        except Exception as e:
            logger.warning(f"[AutonomousGoal] API call failed: {e}")
            return ""

    def get_stats(self) -> Dict:
        """获取统计信息"""
        return self._stats.copy()

    def to_codeact_globals(self) -> Dict[str, Any]:
        """导出为CodeAct全局函数"""
        return {
            "autonomous_goal": self.handle,
        }
