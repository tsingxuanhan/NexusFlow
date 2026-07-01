# -*- coding: utf-8 -*-
"""
铉枢·炉守 Thought Crystallization Engine — 思想结晶引擎
XuanHub Thought Crystallization v4.3

基于 Thought-Retriever (TMLR 2026) 的 Thought Diamond 设计，适配 AI4Science 场景。

核心功能：
1. 在每次 Agent 完成推理后，即时提炼一条"思想结晶"(ThoughtDiamond)
2. 思想结晶 = 结论 + 推理路径 + 关键决策点 + 适用条件
3. 让未来的相似问题能复用整条推理路径，而非只复用结论
4. 与 StructuredPatternMemory 集成，结晶后自动存入模式记忆
5. JSON 持久化，路径可配置

设计灵感：
> "记忆不是数据的堆砌，而是思想的沉淀；智能不是静态的能力，而是动态的进化。"
"""

import hashlib
import json
import logging
import re
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

logger = logging.getLogger("ThoughtCrystallization")


# ============================================================================
# 数据结构
# ============================================================================

@dataclass
class ThoughtDiamond:
    """
    思想结晶 — 验证过的推理链浓缩单元

    对应 Thought-Retriever 论文中的 Thought Diamond 概念。
    每个 ThoughtDiamond 封装了：
    - 结论（一句话）
    - 推理路径（步骤序列）
    - 关键决策点（为什么选A不选B）
    - 适用条件（约束 + 假设）
    - 元数据（置信度、抽象层级、来源等）
    """

    # ── 基础标识 ──
    thought_id: str
    timestamp: float

    # ── 核心内容 ──
    conclusion: str                  # 最终结论（一句话摘要）
    reasoning_chain: List[str]       # 推理步骤序列（每步一句话）
    key_decisions: List[str]         # 关键决策点（为什么选A不选B）

    # ── 适用条件（绑定上下文）──
    problem_type: str                # 问题类型标签
    constraints: List[str]           # 约束条件
    assumptions: List[str]           # 假设前提

    # ── 元数据 ──
    confidence: float                # 置信度 0.0-1.0
    abstraction_level: int           # 抽象层级 1-4（由 AbstractionHierarchy 标注）
    source_task_id: str              # 来源任务 ID
    source_agent: str                # 来源 Agent 角色（miner/assayer/caster/artisan）
    verification_status: str         # "verified" / "pending" / "rejected"

    # ── 关联 ──
    related_thoughts: List[str] = field(default_factory=list)   # 相关思想 ID 列表
    parent_thought_id: Optional[str] = None                     # 父思想（演化来源）

    def to_dict(self) -> Dict:
        """序列化为字典"""
        return {
            "thought_id": self.thought_id,
            "timestamp": self.timestamp,
            "conclusion": self.conclusion,
            "reasoning_chain": self.reasoning_chain,
            "key_decisions": self.key_decisions,
            "problem_type": self.problem_type,
            "constraints": self.constraints,
            "assumptions": self.assumptions,
            "confidence": self.confidence,
            "abstraction_level": self.abstraction_level,
            "source_task_id": self.source_task_id,
            "source_agent": self.source_agent,
            "verification_status": self.verification_status,
            "related_thoughts": self.related_thoughts,
            "parent_thought_id": self.parent_thought_id,
        }

    @classmethod
    def from_dict(cls, data: Dict) -> "ThoughtDiamond":
        """从字典反序列化"""
        return cls(
            thought_id=data["thought_id"],
            timestamp=data.get("timestamp", time.time()),
            conclusion=data.get("conclusion", ""),
            reasoning_chain=data.get("reasoning_chain", []),
            key_decisions=data.get("key_decisions", []),
            problem_type=data.get("problem_type", "general"),
            constraints=data.get("constraints", []),
            assumptions=data.get("assumptions", []),
            confidence=data.get("confidence", 0.5),
            abstraction_level=data.get("abstraction_level", 1),
            source_task_id=data.get("source_task_id", ""),
            source_agent=data.get("source_agent", "unknown"),
            verification_status=data.get("verification_status", "pending"),
            related_thoughts=data.get("related_thoughts", []),
            parent_thought_id=data.get("parent_thought_id"),
        )

    @property
    def text_repr(self) -> str:
        """用于相似度比较的文本表示"""
        parts = [
            self.conclusion,
            " ".join(self.reasoning_chain),
            self.problem_type,
        ]
        return " ".join(parts).lower().strip()


# ============================================================================
# ThoughtCrystallizer — 思想结晶引擎
# ============================================================================

class ThoughtCrystallizer:
    """
    思想结晶引擎

    职责：
    1. 从 Agent 推理过程中提炼 ThoughtDiamond
    2. 判断何时值得结晶（should_crystallize）
    3. 管理结晶历史（最近 N 条）
    4. 与 StructuredPatternMemory 集成
    """

    # ── 触发阈值 ──
    MIN_REASONING_STEPS: int = 3           # 最少推理步数（低于此值不结晶）
    SIMILARITY_THRESHOLD: float = 0.8      # 与最近思想的相似度阈值（高于则跳过）
    MAX_RECENT: int = 100                  # 内存中保留的最近结晶数量

    # ── 关键词模式（用于推理链提取）──
    _STEP_MARKERS: List[str] = [
        "第一步", "第二步", "第三步", "第四步", "第五步",
        "step 1", "step 2", "step 3", "step 4", "step 5",
        "首先", "其次", "然后", "接着", "最后",
        "因为", "所以", "因此", "由于", "由此可见",
        "分析", "发现", "证明", "推断", "得出",
        "first", "second", "then", "next", "finally",
        "because", "therefore", "thus", "hence", "so",
    ]

    _DECISION_MARKERS: List[str] = [
        "选择", "决定", "放弃", "排除", "优先",
        "而非", "而不是", "相比", "优于", "采用",
        "choose", "decide", "select", "prefer", "reject",
        "rather than", "instead of", "prioritize",
        "原因", "理由是", "考虑到", "权衡",
    ]

    def __init__(
        self,
        storage_dir: str = "./thought_crystals",
        pattern_memory: Any = None,
    ):
        """
        初始化结晶引擎

        Args:
            storage_dir: JSON 持久化目录
            pattern_memory: StructuredPatternMemory 实例（可选，用于集成）
        """
        self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(parents=True, exist_ok=True)

        self._pattern_memory = pattern_memory  # v4.2 StructuredPatternMemory

        # 内存中的思想结晶缓存
        self._crystals: List[ThoughtDiamond] = []
        self._crystal_index: Dict[str, ThoughtDiamond] = {}  # thought_id → diamond

        # 文件路径
        self._data_file = self.storage_dir / "thought_diamonds.json"

        # 统计
        self._stats: Dict[str, Any] = {
            "total_crystallized": 0,
            "total_skipped_short": 0,
            "total_skipped_duplicate": 0,
            "total_failed": 0,
        }

        # 加载已有数据
        self._load_from_disk()
        logger.info(
            f"[ThoughtCrystallizer] Initialized with {len(self._crystals)} existing crystals"
        )

    # ====================================================================
    # 公开 API
    # ====================================================================

    def crystallize(
        self,
        task_context: Dict[str, Any],
        reasoning_trace: str,
        result: Dict[str, Any],
    ) -> Optional[ThoughtDiamond]:
        """
        从推理过程提炼思想结晶

        Args:
            task_context: 任务上下文，包含 task_id, agent_role, problem_type 等
            reasoning_trace: 推理过程文本（Agent 的完整推理链文本）
            result: 任务结果字典，包含 success, conclusion, summary 等

        Returns:
            ThoughtDiamond 或 None（不值得结晶时）
        """
        try:
            # 0. 前置检查：是否值得结晶
            if not self.should_crystallize({"trace": reasoning_trace, "result": result}):
                return None

            # 1. 提取推理步骤链
            reasoning_chain = self._extract_reasoning_chain(reasoning_trace)

            # 2. 识别关键决策点
            key_decisions = self._identify_decision_points(reasoning_trace)

            # 3. 生成结论摘要
            conclusion = self._summarize_conclusion(result)

            # 4. 提取约束和假设
            constraints, assumptions = self._extract_conditions(task_context)

            # 5. 计算初始置信度
            confidence = self._calculate_confidence(result)

            # 6. 确定问题类型
            problem_type = task_context.get("problem_type", "general")

            # 7. 生成唯一 ID
            thought_id = self._generate_id(conclusion, reasoning_chain)

            # 8. 组装思想结晶
            thought = ThoughtDiamond(
                thought_id=thought_id,
                timestamp=time.time(),
                conclusion=conclusion,
                reasoning_chain=reasoning_chain,
                key_decisions=key_decisions,
                problem_type=problem_type,
                constraints=constraints,
                assumptions=assumptions,
                confidence=confidence,
                abstraction_level=1,  # 默认 L1，后续由 AbstractionHierarchy 更新
                source_task_id=task_context.get("task_id", ""),
                source_agent=task_context.get("agent_role", "unknown"),
                verification_status="verified" if result.get("success") else "pending",
                related_thoughts=[],
                parent_thought_id=None,
            )

            # 9. 存储
            self._store_crystal(thought)

            # 10. 与 StructuredPatternMemory 集成
            self._integrate_with_pattern_memory(thought)

            self._stats["total_crystallized"] += 1
            logger.info(
                f"[ThoughtCrystallizer] Crystallized: {thought_id[:12]}... "
                f"(confidence={confidence:.2f}, steps={len(reasoning_chain)})"
            )
            return thought

        except Exception as e:
            self._stats["total_failed"] += 1
            logger.error(f"[ThoughtCrystallizer] Crystallization failed: {e}")
            return None

    def should_crystallize(self, task_result: Dict[str, Any]) -> bool:
        """
        判断是否值得结晶

        触发条件：
        - 推理步骤 >= MIN_REASONING_STEPS（简单问题不结晶）
        - 非重复任务（与最近思想相似度 < SIMILARITY_THRESHOLD）
        - 任务成功（失败的任务不提炼经验）

        Args:
            task_result: 包含 trace（推理文本）和 result（结果）的字典

        Returns:
            是否值得结晶
        """
        trace = task_result.get("trace", "")
        result = task_result.get("result", {})

        # 条件1：任务必须成功
        if not result.get("success", False):
            return False

        # 条件2：推理步骤 >= MIN_REASONING_STEPS
        steps = self._extract_reasoning_chain(trace)
        if len(steps) < self.MIN_REASONING_STEPS:
            self._stats["total_skipped_short"] += 1
            return False

        # 条件3：非重复（与最近思想比较）
        conclusion = self._summarize_conclusion(result)
        if self._is_duplicate(conclusion, steps):
            self._stats["total_skipped_duplicate"] += 1
            return False

        return True

    def get_recent_thoughts(self, n: int = 10) -> List[ThoughtDiamond]:
        """获取最近 N 条思想结晶"""
        return self._crystals[-n:] if self._crystals else []

    def get_thought_by_id(self, thought_id: str) -> Optional[ThoughtDiamond]:
        """按 ID 查找思想结晶"""
        return self._crystal_index.get(thought_id)

    def update_abstraction_level(self, thought_id: str, level: int) -> None:
        """更新思想结晶的抽象层级（由 AbstractionHierarchy 调用）"""
        if thought_id in self._crystal_index:
            self._crystal_index[thought_id].abstraction_level = level
            self._persist()

    def get_stats(self) -> Dict[str, Any]:
        """返回统计信息"""
        stats = self._stats.copy()
        stats["current_crystals"] = len(self._crystals)
        return stats

    # ====================================================================
    # 推理链提取
    # ====================================================================

    def _extract_reasoning_chain(self, trace: str) -> List[str]:
        """
        从推理文本中提取推理步骤序列

        策略：
        1. 按段落/句子分割
        2. 识别包含步骤标记的句子
        3. 过滤掉无关内容
        4. 返回有序步骤列表
        """
        if not trace or not trace.strip():
            return []

        steps: List[str] = []
        lines = trace.split("\n")

        for line in lines:
            line = line.strip()
            if not line:
                continue

            # 检查是否包含步骤标记
            lower_line = line.lower()
            is_step = False

            for marker in self._STEP_MARKERS:
                if marker in lower_line:
                    is_step = True
                    break

            # 编号列表也视为步骤（"1." "2." 等）
            if re.match(r"^\s*\d+[\.\)、]", line):
                is_step = True

            if is_step:
                # 清理并截断
                clean_step = self._clean_text(line, max_len=200)
                if clean_step and len(clean_step) > 5:
                    steps.append(clean_step)

        # 如果没找到明确的步骤标记，按句子分割取有意义的句子
        if not steps:
            sentences = re.split(r"[。！？\.\!\?]+", trace)
            for sent in sentences:
                sent = sent.strip()
                if 10 < len(sent) < 300:
                    steps.append(sent)
                if len(steps) >= 10:
                    break

        return steps[:15]  # 最多保留15步

    def _identify_decision_points(self, trace: str) -> List[str]:
        """
        从推理文本中识别关键决策点

        决策点特征：包含"选择"、"决定"、"排除"、"而非"等词汇
        """
        if not trace:
            return []

        decisions: List[str] = []
        lines = trace.split("\n")

        for line in lines:
            line = line.strip()
            if not line:
                continue

            lower_line = line.lower()
            for marker in self._DECISION_MARKERS:
                if marker in lower_line:
                    clean = self._clean_text(line, max_len=200)
                    if clean and len(clean) > 5:
                        decisions.append(clean)
                    break

            if len(decisions) >= 5:
                break

        return decisions

    # ====================================================================
    # 结论与条件提取
    # ====================================================================

    def _summarize_conclusion(self, result: Dict[str, Any]) -> str:
        """
        从任务结果生成结论摘要

        优先使用 result 中已有的摘要字段，否则截取关键内容
        """
        # 优先使用 summary / conclusion 字段
        for key in ["summary", "conclusion", "result", "answer", "output"]:
            val = result.get(key)
            if val and isinstance(val, str) and val.strip():
                return self._clean_text(val, max_len=300)

        # 如果 result 有 message 字段
        msg = result.get("message", "")
        if msg and isinstance(msg, str):
            return self._clean_text(msg, max_len=300)

        return "任务完成（无详细结论）"

    def _extract_conditions(
        self, context: Dict[str, Any]
    ) -> Tuple[List[str], List[str]]:
        """
        从任务上下文提取约束条件和假设

        Returns:
            (constraints, assumptions) 元组
        """
        constraints: List[str] = []
        assumptions: List[str] = []

        # 从 context 提取
        if "constraints" in context:
            c = context["constraints"]
            if isinstance(c, list):
                constraints.extend(str(x) for x in c)
            elif isinstance(c, str) and c.strip():
                constraints.append(c)

        if "assumptions" in context:
            a = context["assumptions"]
            if isinstance(a, list):
                assumptions.extend(str(x) for x in a)
            elif isinstance(a, str) and a.strip():
                assumptions.append(a)

        # 从 domain 推断隐含约束
        domain = context.get("domain", "")
        if domain:
            constraints.append(f"领域: {domain}")

        # 从 agent_role 推断
        agent_role = context.get("agent_role", "")
        if agent_role:
            assumptions.append(f"执行角色: {agent_role}")

        return constraints, assumptions

    # ====================================================================
    # 置信度计算
    # ====================================================================

    def _calculate_confidence(self, result: Dict[str, Any]) -> float:
        """
        计算思想结晶的初始置信度

        考量因素：
        - 任务是否成功（必须）
        - 是否有验证通过标记
        - 推理步骤数量（更多步骤 = 更完整 = 更高置信）
        """
        score = 0.5  # 基础分

        # 任务成功
        if result.get("success"):
            score += 0.2

        # 验证通过
        if result.get("verified"):
            score += 0.15

        # 推理步骤数量加成
        trace = result.get("trace", "")
        if trace:
            step_count = len(self._extract_reasoning_chain(trace))
            if step_count >= 5:
                score += 0.1
            elif step_count >= 3:
                score += 0.05

        return min(1.0, max(0.0, score))

    # ====================================================================
    # 去重与相似度
    # ====================================================================

    def _is_duplicate(self, conclusion: str, steps: List[str]) -> bool:
        """
        检查是否与最近的思想结晶重复

        使用简单的关键词重叠相似度（不依赖 embedding）
        """
        if not self._crystals:
            return False

        new_text = f"{conclusion} {' '.join(steps)}".lower()
        new_words = set(new_text.split())

        # 只检查最近 20 条
        recent = self._crystals[-20:]

        for crystal in recent:
            existing_text = crystal.text_repr
            existing_words = set(existing_text.split())

            if not new_words or not existing_words:
                continue

            overlap = len(new_words & existing_words)
            similarity = overlap / max(1, min(len(new_words), len(existing_words)))

            if similarity >= self.SIMILARITY_THRESHOLD:
                return True

        return False

    # ====================================================================
    # 持久化
    # ====================================================================

    def _store_crystal(self, thought: ThoughtDiamond) -> None:
        """存储一条思想结晶"""
        self._crystals.append(thought)
        self._crystal_index[thought.thought_id] = thought

        # 内存限制：保留最近 MAX_RECENT 条
        while len(self._crystals) > self.MAX_RECENT:
            old = self._crystals.pop(0)
            self._crystal_index.pop(old.thought_id, None)

        self._persist()

    def _persist(self) -> None:
        """持久化到 JSON 文件"""
        try:
            data = [c.to_dict() for c in self._crystals]
            with open(self._data_file, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"[ThoughtCrystallizer] Persist failed: {e}")

    def _load_from_disk(self) -> None:
        """从 JSON 文件加载"""
        if not self._data_file.exists():
            return
        try:
            with open(self._data_file, "r", encoding="utf-8") as f:
                data = json.load(f)

            for item in data:
                try:
                    crystal = ThoughtDiamond.from_dict(item)
                    self._crystals.append(crystal)
                    self._crystal_index[crystal.thought_id] = crystal
                except Exception as e:
                    logger.warning(f"[ThoughtCrystallizer] Failed to load crystal: {e}")

            self._stats["total_crystallized"] = len(self._crystals)
        except Exception as e:
            logger.error(f"[ThoughtCrystallizer] Load failed: {e}")

    # ====================================================================
    # 与 StructuredPatternMemory 集成
    # ====================================================================

    def _integrate_with_pattern_memory(self, thought: ThoughtDiamond) -> None:
        """
        结晶后自动通知 StructuredPatternMemory

        将思想结晶的关键信息同步到模式记忆中，
        便于 Dream/Distill 周期进一步整理。
        """
        if self._pattern_memory is None:
            return

        try:
            # 检查 pattern_memory 是否有 store_pattern 方法
            if not hasattr(self._pattern_memory, "store_pattern"):
                return

            # 动态导入以避免循环依赖
            try:
                from structured_pattern_memory import Pattern, PatternCategory, PatternConfidence
            except ImportError:
                logger.debug("StructuredPatternMemory not available for integration")
                return

            # 映射问题类型到 PatternCategory
            category_map = {
                "experiment": PatternCategory.EXPERIMENT_DESIGN,
                "experiment_design": PatternCategory.EXPERIMENT_DESIGN,
                "literature": PatternCategory.LITERATURE_ANALYSIS,
                "literature_analysis": PatternCategory.LITERATURE_ANALYSIS,
                "validation": PatternCategory.DATA_VALIDATION,
                "data_validation": PatternCategory.DATA_VALIDATION,
                "error": PatternCategory.ERROR_RECOVERY,
                "error_recovery": PatternCategory.ERROR_RECOVERY,
            }
            category = category_map.get(
                thought.problem_type, PatternCategory.CROSS_DOMAIN
            )

            # 构建 Pattern 对象
            pattern = Pattern(
                pattern_id=f"thought_{thought.thought_id}",
                category=category,
                domain=thought.problem_type or "general_science",
                title=thought.conclusion[:80],
                description=thought.conclusion,
                trigger_conditions=thought.constraints,
                solution_template=" → ".join(thought.reasoning_chain[:5]),
                anti_patterns=[],
                confidence=PatternConfidence.OBSERVED,
                occurrence_count=1,
                source_episode_ids=[thought.thought_id],
            )

            self._pattern_memory.store_pattern(pattern)
            logger.debug(
                f"[ThoughtCrystallizer] Synced to PatternMemory: {pattern.pattern_id[:20]}..."
            )

        except Exception as e:
            logger.warning(f"[ThoughtCrystallizer] PatternMemory integration failed: {e}")

    # ====================================================================
    # 工具方法
    # ====================================================================

    @staticmethod
    def _generate_id(conclusion: str, steps: List[str]) -> str:
        """基于内容生成唯一 ID"""
        content = f"{conclusion}|{'|'.join(steps[:3])}|{time.time()}"
        hash_val = hashlib.sha256(content.encode("utf-8")).hexdigest()[:16]
        ts = int(time.time() * 1000)
        return f"thought_{ts}_{hash_val}"

    @staticmethod
    def _clean_text(text: str, max_len: int = 200) -> str:
        """清理文本：去除多余空白、截断"""
        text = re.sub(r"\s+", " ", text).strip()
        if len(text) > max_len:
            text = text[:max_len - 3] + "..."
        return text
