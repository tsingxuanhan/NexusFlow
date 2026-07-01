# -*- coding: utf-8 -*-
"""
铉枢·炉守 Abstraction Hierarchy — 抽象层级系统
XuanHub Abstraction Hierarchy v4.3

基于 Thought-Retriever (TMLR 2026) 的 Recursive Abstraction 设计。

核心功能：
1. 给每个记忆条目/思想结晶标注抽象层级 (L1-L4)
2. 检索时按任务复杂度匹配对应层级
3. 实现"简单问题用浅思想，复杂问题用深思想"
4. 规则判定 + 简单启发式（不依赖 embedding / HuggingFace）
5. 与 v4.2 KnowledgeLibrary 集成

层级定义：
- L1_FACT:      事实层 — 具体数据点、观测值
- L2_INFERENCE: 推理层 — 基于事实的直接推论
- L3_STRATEGY:  策略层 — 跨场景可复用的方法论
- L4_META_RULE: 元规则层 — 关于如何思考的高阶原则
"""

import logging
import re
from enum import IntEnum
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger("AbstractionHierarchy")


# ============================================================================
# 层级定义
# ============================================================================

class AbstractionLevel(IntEnum):
    """
    抽象层级定义 — 4 级

    对应 Thought-Retriever 论文中的 Abstraction Level：
    - L1: 具体事实（"实验数据显示 X = 5.2"）
    - L2: 直接推论（"因为 X > 5，所以温度偏高"）
    - L3: 可复用策略（"遇到温度偏高时，应先检查传感器再调参数"）
    - L4: 元规则（"当多个传感器矛盾时，优先相信冗余度最高的那个"）
    """
    L1_FACT = 1
    L2_INFERENCE = 2
    L3_STRATEGY = 3
    L4_META_RULE = 4


# ============================================================================
# 层级特征词典
# ============================================================================

# L4 元规则特征词
_META_RULE_PATTERNS: List[str] = [
    # 中文
    "原则", "当.*时.*应该", "优先", "总是", "必须",
    "核心思想", "根本", "本质", "元规则", "高阶",
    "方法论", "策略.*选择", "何时.*适用", "如何.*判断",
    "权衡", "trade-off", "tradeoff",
    "通用规律", "普适", "放之四海",
    # 英文
    "principle", "rule of thumb", "always", "never",
    "meta-rule", "fundamental", "in general",
    "when.*should", "how to decide", "tradeoff",
    "methodology", "heuristic", "guideline",
]

# L3 策略特征词
_STRATEGY_PATTERNS: List[str] = [
    # 中文
    "方法", "策略", "步骤", "流程", "方案",
    "建议", "推荐", "可以采用", "应该.*先.*然后",
    "可复用", "跨.*应用", "迁移", "泛化",
    "最佳实践", "经验", "技巧", "模式",
    "适用于", "在.*场景下", "当.*时",
    # 英文
    "method", "strategy", "approach", "procedure",
    "recommend", "suggest", "best practice",
    "reusable", "transferable", "generalizable",
    "applicable", "in.*scenario", "when.*then",
    "workflow", "pipeline", "technique",
]

# L2 推理特征词
_INFERENCE_PATTERNS: List[str] = [
    # 中文
    "因此", "所以", "由此", "说明", "表明",
    "意味着", "可以推断", "得出结论", "推论",
    "因为.*所以", "由于.*因此", "如果.*那么",
    "因果", "关联", "相关", "导致",
    "从.*看出", "根据.*可知",
    # 英文
    "therefore", "thus", "hence", "so",
    "implies", "indicates", "suggests",
    "because", "since", "consequently",
    "inference", "conclude", "deduce",
    "if.*then", "causes", "leads to",
]

# L1 事实特征词（默认层级，但可以用来增强判定）
_FACT_PATTERNS: List[str] = [
    # 中文
    "数据", "结果", "数值", "测量", "观测",
    "实验.*显示", "记录", "报告",
    "是", "为", "等于", "有",
    # 英文
    "data", "result", "value", "measured", "observed",
    "experiment shows", "record", "report",
    "is", "equals", "has",
]

# 任务复杂度评估关键词
_COMPLEXITY_MULTI_STEP: List[str] = [
    "多步", "multi-step", "pipeline", "流程",
    "依次", "按序", "chain", "sequential",
    "阶段", "phase", "stage",
]

_COMPLEXITY_CROSS_DOMAIN: List[str] = [
    "跨域", "cross-domain", "跨领域",
    "多领域", "multi-domain", "综合",
    "结合", "combine", "integrate", "融合",
]

_COMPLEXITY_META: List[str] = [
    "策略选择", "method selection", "元认知",
    "优化.*方案", "trade-off", "权衡",
    "最佳.*方案", "optimal", "设计.*方法",
]


# ============================================================================
# AbstractionHierarchy — 抽象层级系统
# ============================================================================

class AbstractionHierarchy:
    """
    抽象层级系统

    职责：
    1. classify()：判定文本内容的抽象层级
    2. retrieve_by_complexity()：按任务复杂度匹配层级检索
    3. assess_task_complexity()：评估任务复杂度
    4. tag_batch()：批量标注
    """

    def __init__(self):
        """初始化抽象层级系统"""
        self._stats: Dict[str, Any] = {
            "total_classified": 0,
            "by_level": {level.name: 0 for level in AbstractionLevel},
            "total_retrievals": 0,
            "total_complexity_assessments": 0,
        }
        logger.info("[AbstractionHierarchy] Initialized")

    # ====================================================================
    # 核心 API：层级分类
    # ====================================================================

    def classify(self, content: str, context: Optional[Dict[str, Any]] = None) -> AbstractionLevel:
        """
        判定内容的抽象层级

        判定策略（从高到低）：
        1. 先检测 L4 元规则特征（最高优先级）
        2. 再检测 L3 策略泛化性
        3. 再检测 L2 推理特征
        4. 默认 L1 事实

        Args:
            content: 待分类的文本内容
            context: 可选上下文信息

        Returns:
            AbstractionLevel 枚举值
        """
        self._stats["total_classified"] += 1

        if not content or not content.strip():
            level = AbstractionLevel.L1_FACT
            self._stats["by_level"][level.name] += 1
            return level

        content_lower = content.lower()

        # L4 检测：元规则特征
        if self._has_meta_pattern(content_lower):
            level = AbstractionLevel.L4_META_RULE
            self._stats["by_level"][level.name] += 1
            return level

        # L3 检测：策略泛化性
        if self._is_generalizable(content_lower, context):
            level = AbstractionLevel.L3_STRATEGY
            self._stats["by_level"][level.name] += 1
            return level

        # L2 检测：推理特征
        if self._is_inference(content_lower):
            level = AbstractionLevel.L2_INFERENCE
            self._stats["by_level"][level.name] += 1
            return level

        # L1 默认
        level = AbstractionLevel.L1_FACT
        self._stats["by_level"][level.name] += 1
        return level

    def _has_meta_pattern(self, content: str) -> bool:
        """
        L4 元规则特征检测

        元规则的特征：包含"当...时应该..."、"原则"、"优先"、
        "核心思想"、"方法论"、"trade-off"等表述
        """
        match_count = 0
        for pattern in _META_RULE_PATTERNS:
            try:
                if re.search(pattern, content, re.IGNORECASE):
                    match_count += 1
            except re.error:
                # 简单字符串匹配兜底
                if pattern in content:
                    match_count += 1

        # 需要至少 2 个特征词匹配才判定为 L4（避免误判）
        return match_count >= 2

    def _is_generalizable(self, content: str, context: Optional[Dict] = None) -> bool:
        """
        L3 策略特征检测

        策略的特征：
        - 包含方法/步骤/流程描述
        - 提到可复用/跨场景/泛化
        - 有"建议"、"推荐"等指导性语言
        """
        match_count = 0
        for pattern in _STRATEGY_PATTERNS:
            try:
                if re.search(pattern, content, re.IGNORECASE):
                    match_count += 1
            except re.error:
                if pattern in content:
                    match_count += 1

        # 策略判定：需要 2+ 特征
        return match_count >= 2

    def _is_inference(self, content: str) -> bool:
        """
        L2 推理特征检测

        推理的特征：
        - 包含因果连接词（因此、所以、由于）
        - 包含推断性动词（推断、表明、说明）
        """
        match_count = 0
        for pattern in _INFERENCE_PATTERNS:
            try:
                if re.search(pattern, content, re.IGNORECASE):
                    match_count += 1
            except re.error:
                if pattern in content:
                    match_count += 1

        return match_count >= 1

    # ====================================================================
    # 层级匹配检索
    # ====================================================================

    def retrieve_by_complexity(
        self,
        query: str,
        task_complexity: int,
        memory_provider: Any = None,
    ) -> List[Any]:
        """
        按任务复杂度匹配层级检索

        策略：
        - 任务复杂度 1 → 优先 L1，降级 L2
        - 任务复杂度 2 → 优先 L2，降级 L1
        - 任务复杂度 3 → 优先 L3，降级 L2, L1
        - 任务复杂度 4 → 优先 L4，降级 L3, L2, L1

        Args:
            query: 检索查询
            task_complexity: 任务复杂度 (1-4)
            memory_provider: 记忆提供者（StructuredPatternMemory 或 ThoughtCrystallizer）

        Returns:
            匹配的结果列表
        """
        self._stats["total_retrievals"] += 1
        target_level = min(max(task_complexity, 1), 4)
        max_results = 20

        results: List[Any] = []

        # 按优先级顺序检索：目标层级 → 逐级降低
        for level_offset in range(4):
            check_level = target_level - level_offset
            if check_level < 1:
                break

            level_results = self._retrieve_at_level(
                query, AbstractionLevel(check_level), memory_provider
            )
            results.extend(level_results)

            if len(results) >= max_results:
                break

        return results[:max_results]

    def _retrieve_at_level(
        self,
        query: str,
        level: AbstractionLevel,
        memory_provider: Any,
    ) -> List[Any]:
        """在指定层级检索"""
        if memory_provider is None:
            return []

        results: List[Any] = []

        # 尝试从 ThoughtCrystallizer 获取
        if hasattr(memory_provider, "get_recent_thoughts"):
            thoughts = memory_provider.get_recent_thoughts(n=50)
            for t in thoughts:
                if t.abstraction_level == level.value:
                    # 简单的关键词相关性过滤
                    if self._is_relevant(query, t.text_repr):
                        results.append(t)

        # 尝试从 StructuredPatternMemory 获取
        if hasattr(memory_provider, "retrieve_similar"):
            try:
                patterns = memory_provider.retrieve_similar(max_results=20)
                for p in patterns:
                    # Pattern 没有 abstraction_level，用 classify 推断
                    inferred_level = self.classify(p.description)
                    if inferred_level == level:
                        results.append(p)
            except Exception:
                pass

        return results

    # ====================================================================
    # 任务复杂度评估
    # ====================================================================

    def assess_task_complexity(self, task_description: str) -> int:
        """
        评估任务复杂度，返回 1-4

        评估维度：
        - 基础分 = 1
        - 多步骤推理 → +1
        - 跨领域知识 → +1
        - 需要元认知/策略选择 → +1

        Args:
            task_description: 任务描述文本

        Returns:
            复杂度 1-4
        """
        self._stats["total_complexity_assessments"] += 1

        if not task_description:
            return 1

        desc_lower = task_description.lower()
        score = 1

        # 多步骤推理检测
        if self._has_keywords(desc_lower, _COMPLEXITY_MULTI_STEP):
            score += 1

        # 跨领域检测
        if self._has_keywords(desc_lower, _COMPLEXITY_CROSS_DOMAIN):
            score += 1

        # 元认知/策略选择检测
        if self._has_keywords(desc_lower, _COMPLEXITY_META):
            score += 1

        # 文本长度也是一个线索（长任务通常更复杂）
        if len(task_description) > 500:
            score += 1
        elif len(task_description) > 1000:
            score += 1  # 额外加分

        return min(score, 4)

    # ====================================================================
    # 批量标注
    # ====================================================================

    def tag_batch(
        self, items: List[Any]
    ) -> List[Tuple[Any, AbstractionLevel]]:
        """
        批量标注抽象层级

        Args:
            items: 待标注项列表（可以是 ThoughtDiamond、Pattern 等）

        Returns:
            [(item, AbstractionLevel), ...] 列表
        """
        results: List[Tuple[Any, AbstractionLevel]] = []

        for item in items:
            # 提取文本内容
            content = self._extract_content_text(item)
            level = self.classify(content)
            results.append((item, level))

        return results

    # ====================================================================
    # 工具方法
    # ====================================================================

    @staticmethod
    def _has_keywords(text: str, keywords: List[str]) -> bool:
        """检查文本是否包含关键词列表中的任意词"""
        for kw in keywords:
            try:
                if re.search(kw, text, re.IGNORECASE):
                    return True
            except re.error:
                if kw in text:
                    return True
        return False

    @staticmethod
    def _is_relevant(query: str, text: str) -> bool:
        """简单的关键词相关性判断"""
        if not query or not text:
            return True  # 无 query 时默认相关

        query_words = set(query.lower().split())
        text_words = set(text.lower().split())

        if not query_words or not text_words:
            return True

        overlap = len(query_words & text_words)
        return overlap >= 1

    @staticmethod
    def _extract_content_text(item: Any) -> str:
        """从各种对象中提取文本内容"""
        # ThoughtDiamond
        if hasattr(item, "conclusion") and hasattr(item, "reasoning_chain"):
            parts = [item.conclusion]
            if item.reasoning_chain:
                parts.extend(item.reasoning_chain)
            return " ".join(parts)

        # Pattern (from structured_pattern_memory)
        if hasattr(item, "description") and hasattr(item, "title"):
            return f"{item.title} {item.description}"

        # KnowledgeEntry
        if hasattr(item, "description") and hasattr(item, "title"):
            return f"{item.title} {item.description}"

        # 字典
        if isinstance(item, dict):
            parts = []
            for key in ["title", "description", "conclusion", "content", "text"]:
                if key in item and isinstance(item[key], str):
                    parts.append(item[key])
            return " ".join(parts)

        # 字符串
        if isinstance(item, str):
            return item

        return str(item) if item else ""

    def get_stats(self) -> Dict[str, Any]:
        """返回统计信息"""
        return self._stats.copy()
