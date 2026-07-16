# -*- coding: utf-8 -*-
"""
反思循环 (ReflectionLoop) — 执行后反思与经验提取
XuanHub v4.0 Phase 2 — Planning Engine

每次执行后强制反思，这是自主进化的关键。
借鉴 Reflexion (Shinn et al., 2023) + 自我修正范式。

核心流程：
1. 结果与预期对比
2. 识别偏差和错误
3. 提取经验规则
4. 决定是否重规划
5. 局部重规划（不重新分解整棵树）
"""

import json
import logging
import re
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any, Tuple
from datetime import datetime

logger = logging.getLogger("ReflectionLoop")


@dataclass
class Reflection:
    """反思结果"""
    # 评估
    achievement_score: float = 0.0       # 目标达成度 0.0~1.0
    quality_issues: List[str] = field(default_factory=list)
    strengths: List[str] = field(default_factory=list)
    
    # 经验提取
    lessons_learned: List[str] = field(default_factory=list)
    rules_extracted: List[str] = field(default_factory=list)
    
    # 行动建议
    should_replan: bool = False
    replan_scope: str = "none"           # none / local / global
    failed_steps: List[str] = field(default_factory=list)
    improvement_suggestions: List[str] = field(default_factory=list)
    
    # 元数据
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    reflection_depth: int = 0
    
    @property
    def is_positive(self) -> bool:
        return self.achievement_score >= 0.7
    
    @property
    def needs_action(self) -> bool:
        return self.should_replan or len(self.quality_issues) > 2
    
    def to_dict(self) -> Dict:
        return {
            "achievement_score": self.achievement_score,
            "quality_issues": self.quality_issues,
            "strengths": self.strengths,
            "lessons_learned": self.lessons_learned,
            "rules_extracted": self.rules_extracted,
            "should_replan": self.should_replan,
            "replan_scope": self.replan_scope,
            "failed_steps": self.failed_steps,
            "improvement_suggestions": self.improvement_suggestions,
            "timestamp": self.timestamp,
        }
    
    def to_prompt(self) -> str:
        """序列化为可注入prompt的反思摘要"""
        lines = [
            f"## 反思报告 (达成度: {self.achievement_score:.0%})",
        ]
        
        if self.strengths:
            lines.append("### 做对了什么")
            for s in self.strengths:
                lines.append(f"  ✅ {s}")
        
        if self.quality_issues:
            lines.append("### 问题")
            for issue in self.quality_issues:
                lines.append(f"  ⚠️ {issue}")
        
        if self.lessons_learned:
            lines.append("### 经验教训")
            for lesson in self.lessons_learned:
                lines.append(f"  📝 {lesson}")
        
        if self.rules_extracted:
            lines.append("### 提取规则")
            for rule in self.rules_extracted:
                lines.append(f"  📏 {rule}")
        
        if self.should_replan:
            lines.append(f"### 需要{'全局' if self.replan_scope == 'global' else '局部'}重规划")
        
        return "\n".join(lines)


@dataclass
class ExperienceRule:
    """经验规则 — 从反思中提取的可复用知识"""
    id: str = ""
    rule: str = ""
    context: str = ""                    # 适用场景
    confidence: float = 0.5              # 置信度
    source: str = ""                     # 来源任务
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    applied_count: int = 0               # 被应用次数
    success_rate: float = 0.0            # 应用成功率
    
    def to_dict(self) -> Dict:
        return {
            "id": self.id, "rule": self.rule, "context": self.context,
            "confidence": self.confidence, "source": self.source,
            "applied_count": self.applied_count, "success_rate": self.success_rate,
        }


class ReflectionLoop:
    """反思循环 — 执行后反思与经验提取
    
    核心职责：
    1. 对比结果与预期，量化达成度
    2. 识别偏差和错误模式
    3. 提取可复用的经验规则
    4. 决定是否需要重规划
    5. 执行局部重规划
    
    使用方式：
    1. reflection_loop = ReflectionLoop(strategy_chat=pro_chat, flash_chat=flash_chat)
    2. reflection = reflection_loop.reflect(plan=task_tree, results={"T-1": "完成", "T-2": "失败"})
    3. if reflection.should_replan:
    4.     new_tree = reflection_loop.replan(task_tree, "T-2", reflection)
    """
    
    # 重规划阈值
    REPLAN_THRESHOLD = 0.4           # 达成度低于此值触发全局重规划
    LOCAL_REPLAN_THRESHOLD = 0.6     # 达成度低于此值触发局部重规划
    
    def __init__(
        self,
        strategy_chat: callable = None,   # PRO模型chat（用于深度反思）
        flash_chat: callable = None,      # Flash模型chat（用于快速评估）
        experience_store: Dict = None,     # 经验规则存储
    ):
        self.strategy_chat = strategy_chat
        self.flash_chat = flash_chat
        self.experience_store = experience_store or {}
        self._rule_counter = 0
    
    def reflect(
        self,
        plan_summary: str = "",
        results: Dict[str, str] = None,
        expectations: Dict[str, str] = None,
        context: str = "",
    ) -> Reflection:
        """反思执行结果
        
        Args:
            plan_summary: 计划摘要
            results: {task_id: result_text}
            expectations: {task_id: expectation_text}
            context: 额外背景
            
        Returns:
            Reflection对象
        """
        results = results or {}
        expectations = expectations or {}
        
        # 如果有API，用LLM深度反思
        if self.strategy_chat:
            return self._llm_reflect(plan_summary, results, expectations, context)
        
        # Fallback：规则化反思
        return self._rule_based_reflect(plan_summary, results, expectations)
    
    def _llm_reflect(
        self,
        plan_summary: str,
        results: Dict[str, str],
        expectations: Dict[str, str],
        context: str,
    ) -> Reflection:
        """用PRO模型深度反思"""
        # 构建对比表
        comparison = []
        for task_id, result in results.items():
            exp = expectations.get(task_id, "未指定")
            comparison.append(f"- 任务{task_id}:\n  预期: {exp[:200]}\n  实际: {result[:200]}")
        
        comparison_text = "\n".join(comparison)
        experience_context = self._get_relevant_experiences(plan_summary)
        
        prompt = f"""请深度反思以下执行结果：

## 计划摘要
{plan_summary}

## 结果对比
{comparison_text}

{f"## 相关经验\n{experience_context}" if experience_context else ""}

{f"## 背景\n{context}" if context else ""}

## 反思要求
1. **目标达成度**: 整体完成度百分比评估
2. **做对了什么**: 列出成功的做法（可复用的经验）
3. **问题**: 列出质量问题、偏差和错误
4. **经验教训**: 从中可以总结什么规则？
5. **可提取规则**: 格式为 "当...时，应该..." 的显式规则
6. **是否需要重规划**: 如果有关键步骤失败
7. **改进建议**: 下次如何做得更好

输出JSON格式：
{{
  "achievement_score": 0.0-1.0,
  "strengths": ["..."],
  "quality_issues": ["..."],
  "lessons_learned": ["..."],
  "rules_extracted": ["当...时，应该..."],
  "should_replan": true/false,
  "replan_scope": "none/local/global",
  "failed_steps": ["task_id"],
  "improvement_suggestions": ["..."]
}}"""

        try:
            response = self.strategy_chat(prompt)
            reflection = self._parse_reflection(response)
            
            # 存储提取的规则
            for rule_text in reflection.rules_extracted:
                self._store_rule(rule_text, plan_summary)
            
            return reflection
            
        except Exception as e:
            logger.warning(f"LLM反思失败，降级到规则反思: {e}")
            return self._rule_based_reflect(plan_summary, results, expectations)
    
    def _rule_based_reflect(
        self,
        plan_summary: str,
        results: Dict[str, str],
        expectations: Dict[str, str],
    ) -> Reflection:
        """基于规则的快速反思（无API时使用）"""
        reflection = Reflection()
        
        # 基础达成度：有结果的任务比例
        if results:
            success_count = sum(1 for r in results.values() if r and "失败" not in r and "错误" not in r)
            reflection.achievement_score = success_count / len(results) if results else 0.0
        
        # 识别失败步骤
        for task_id, result in results.items():
            if not result or "失败" in result or "错误" in result:
                reflection.failed_steps.append(task_id)
                reflection.quality_issues.append(f"任务{task_id}执行失败: {result[:100] if result else '无结果'}")
        
        # 决定是否重规划
        if reflection.achievement_score < self.REPLAN_THRESHOLD:
            reflection.should_replan = True
            reflection.replan_scope = "global"
        elif reflection.achievement_score < self.LOCAL_REPLAN_THRESHOLD:
            if reflection.failed_steps:
                reflection.should_replan = True
                reflection.replan_scope = "local"
        
        return reflection
    
    def should_replan(self, reflection: Reflection) -> bool:
        """判断是否需要重规划"""
        return reflection.should_replan
    
    def replan(
        self,
        plan_text: str,
        failed_steps: List[str],
        reflection: Reflection,
        context: str = "",
    ) -> str:
        """局部重规划 — 不重新分解整棵树，只修改失败部分
        
        Args:
            plan_text: 原始计划文本
            failed_steps: 失败步骤ID列表
            reflection: 反思结果
            context: 额外背景
            
        Returns:
            新的计划文本（仅修改失败部分）
        """
        if not self.strategy_chat:
            return plan_text  # 无法重规划
        
        failed_text = "\n".join([
            f"- 步骤{step}: {reflection.quality_issues[i] if i < len(reflection.quality_issues) else '失败'}"
            for i, step in enumerate(failed_steps)
        ])
        
        lessons_text = "\n".join([f"- {l}" for l in reflection.lessons_learned])
        suggestions_text = "\n".join([f"- {s}" for s in reflection.improvement_suggestions])
        
        prompt = f"""以下计划的部分步骤执行失败，需要局部重规划。

## 原始计划
{plan_text}

## 失败步骤
{failed_text}

## 经验教训
{lessons_text}

## 改进建议
{suggestions_text}

{f"## 背景\n{context}" if context else ""}

## 要求
1. **只修改失败步骤及其直接后续**，保持已完成步骤不变
2. 提供替代方案，说明为什么新方案能避免之前的失败
3. 评估新方案的风险
4. 保持整体计划的结构和编号

输出修改后的完整计划（只改需要改的部分，其余保持原文）。"""

        try:
            new_plan = self.strategy_chat(prompt)
            return new_plan
        except Exception as e:
            logger.warning(f"重规划失败: {e}")
            return plan_text
    
    def reflect_on_task_tree(
        self,
        tree,  # TaskTree
        context: str = "",
    ) -> Reflection:
        """对整个TaskTree进行反思
        
        从TaskTree中提取各节点的结果，生成结构化反思。
        """
        from .task_tree import TaskTree
        
        results = {}
        expectations = {}
        
        for node in tree.root.flatten():
            if node.is_leaf and node.is_terminal:
                if node.result:
                    results[node.id] = node.result
                expectations[node.id] = node.description
        
        plan_summary = tree.to_prompt()
        return self.reflect(plan_summary, results, expectations, context)
    
    def iterative_reflect(
        self,
        plan_text: str,
        results: Dict[str, str],
        expectations: Dict[str, str],
        max_iterations: int = 3,
        context: str = "",
    ) -> Tuple[Reflection, str]:
        """迭代反思 — 反思→重规划→执行→再反思
        
        Args:
            plan_text: 初始计划
            results: 首次执行结果
            expectations: 预期
            max_iterations: 最大迭代次数
            context: 背景
            
        Returns:
            (最终反思, 最终计划)
        """
        current_plan = plan_text
        current_results = results
        
        for i in range(max_iterations):
            reflection = self.reflect(current_plan, current_results, expectations, context)
            reflection.reflection_depth = i + 1
            
            # 达成度足够高，结束迭代
            if reflection.achievement_score >= 0.7:
                logger.info(f"迭代反思第{i+1}轮: 达成度{reflection.achievement_score:.0%}，满意退出")
                return reflection, current_plan
            
            # 需要重规划
            if reflection.should_replan:
                new_plan = self.replan(current_plan, reflection.failed_steps, reflection, context)
                if new_plan != current_plan:
                    current_plan = new_plan
                    logger.info(f"迭代反思第{i+1}轮: 重规划完成，准备重新执行")
                else:
                    logger.info(f"迭代反思第{i+1}轮: 重规划未能改善，退出")
                    return reflection, current_plan
            else:
                # 不需要重规划但达成度不高，说明可能是预期有问题
                logger.info(f"迭代反思第{i+1}轮: 不需要重规划但达成度不够，退出")
                return reflection, current_plan
        
        return reflection, current_plan
    
    # ---- 经验规则管理 ----
    
    def _store_rule(self, rule_text: str, source: str) -> None:
        """存储经验规则"""
        self._rule_counter += 1
        rule_id = f"RULE-{self._rule_counter:03d}"
        
        rule = ExperienceRule(
            id=rule_id,
            rule=rule_text,
            source=source[:200],
            confidence=0.6,  # 新规则初始置信度
        )
        self.experience_store[rule_id] = rule
        logger.info(f"新经验规则: {rule_id} — {rule_text[:50]}")
    
    def _get_relevant_experiences(self, context: str) -> str:
        """获取与当前上下文相关的经验"""
        if not self.experience_store:
            return ""
        
        # 简单关键词匹配（后续可升级为语义检索）
        relevant = []
        context_lower = context.lower()
        
        for rule in self.experience_store.values():
            # 检查规则的上下文关键词是否在当前上下文中
            rule_keywords = rule.context.split() if rule.context else rule.rule.split()[:5]
            overlap = sum(1 for kw in rule_keywords if kw.lower() in context_lower)
            if overlap >= 1:
                relevant.append(f"- [{rule.id}] {rule.rule} (置信度: {rule.confidence:.0%})")
        
        if not relevant:
            # 没有明确相关的，返回置信度最高的3条
            sorted_rules = sorted(self.experience_store.values(), key=lambda r: -r.confidence)
            for rule in sorted_rules[:3]:
                relevant.append(f"- [{rule.id}] {rule.rule} (置信度: {rule.confidence:.0%})")
        
        return "\n".join(relevant) if relevant else ""
    
    def get_all_rules(self) -> List[ExperienceRule]:
        """获取所有经验规则"""
        return list(self.experience_store.values())
    
    def update_rule_confidence(self, rule_id: str, success: bool) -> None:
        """更新规则置信度（应用后反馈）"""
        rule = self.experience_store.get(rule_id)
        if not rule:
            return
        
        rule.applied_count += 1
        if success:
            rule.success_rate = (rule.success_rate * (rule.applied_count - 1) + 1) / rule.applied_count
        else:
            rule.success_rate = (rule.success_rate * (rule.applied_count - 1)) / rule.applied_count
        
        # 置信度随成功率和应用次数调整
        rule.confidence = rule.success_rate * min(1.0, rule.applied_count / 5)
    
    # ---- 解析 ----
    
    def _parse_reflection(self, response: str) -> Reflection:
        """解析LLM反思回复"""
        reflection = Reflection()
        
        # 尝试提取JSON
        json_match = re.search(r'\{[\s\S]*\}', response)
        if json_match:
            try:
                data = json.loads(json_match.group())
                reflection.achievement_score = float(data.get("achievement_score", 0.5))
                reflection.strengths = data.get("strengths", [])
                reflection.quality_issues = data.get("quality_issues", [])
                reflection.lessons_learned = data.get("lessons_learned", [])
                reflection.rules_extracted = data.get("rules_extracted", [])
                reflection.should_replan = data.get("should_replan", False)
                reflection.replan_scope = data.get("replan_scope", "none")
                reflection.failed_steps = data.get("failed_steps", [])
                reflection.improvement_suggestions = data.get("improvement_suggestions", [])
                return reflection
            except (json.JSONDecodeError, ValueError) as e:
                logger.warning(f"解析反思JSON失败: {e}")
        
        # Fallback：从文本中提取
        reflection.achievement_score = self._extract_score(response)
        reflection.strengths = self._extract_list(response, ["做对了什么", "成功", "strengths"])
        reflection.quality_issues = self._extract_list(response, ["问题", "错误", "issues"])
        reflection.lessons_learned = self._extract_list(response, ["经验", "教训", "lessons"])
        
        if "重规划" in response or "replan" in response.lower():
            reflection.should_replan = True
            if "全局" in response or "global" in response.lower():
                reflection.replan_scope = "global"
            else:
                reflection.replan_scope = "local"
        
        return reflection
    
    def _extract_score(self, text: str) -> float:
        """从文本中提取评分"""
        # 匹配百分比
        match = re.search(r'(\d+)%', text)
        if match:
            return min(1.0, int(match.group(1)) / 100)
        
        # 匹配0-1小数
        match = re.search(r'(\d+\.?\d*)', text)
        if match:
            val = float(match.group(1))
            return min(1.0, val) if val <= 1.0 else min(1.0, val / 100)
        
        return 0.5
    
    def _extract_list(self, text: str, keywords: List[str]) -> List[str]:
        """从文本中提取列表"""
        results = []
        lines = text.split("\n")
        capturing = False
        
        for line in lines:
            # 检查是否进入目标章节
            if any(kw in line for kw in keywords):
                capturing = True
                continue
            
            # 检查是否进入新章节
            if line.startswith("#") or line.startswith("##"):
                capturing = False
                continue
            
            if capturing:
                stripped = line.strip()
                if stripped.startswith("- ") or stripped.startswith("• "):
                    item = stripped[2:].strip()
                    if item:
                        results.append(item)
                elif re.match(r'^\d+[\.\)]', stripped):
                    item = re.sub(r'^\d+[\.\)]\s*', '', stripped)
                    if item:
                        results.append(item)
        
        return results
