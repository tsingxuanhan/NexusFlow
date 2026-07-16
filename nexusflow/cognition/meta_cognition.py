# -*- coding: utf-8 -*-
"""
铉枢·炉守 Meta-Cognition — 元认知模块
XuanHub Meta-Cognition Module

Agent的自我认知能力：
1. 置信度评估 — 知道自己"知道什么"和"不知道什么"
2. 知识盲区识别 — 基于Archival Memory覆盖率分析
3. 自我改进 — 针对盲区主动学习
4. 能力边界感知 — 评估自己是否能完成某类任务
5. 策略自适应 — 根据元认知结果调整执行策略
"""

import json
import os
import re
import time
import logging
from typing import Any, Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger("MetaCognition")


class ConfidenceLevel(Enum):
    """置信度级别"""
    HIGH = "high"          # >0.8 → 直接回答
    MEDIUM = "medium"      # 0.4-0.8 → 回答+标注不确定性+建议搜索
    LOW = "low"            # <0.4 → 主动搜索/求助/触发学习


class GapType(Enum):
    """知识盲区类型"""
    DOMAIN_MISSING = "domain_missing"        # 整个领域缺失
    TOPIC_SHALLOW = "topic_shallow"          # 话题覆盖浅
    KNOWLEDGE_OUTDATED = "knowledge_outdated"  # 知识过时
    SKILL_MISSING = "skill_missing"          # 缺少某项技能
    EXPERIENCE_LACKING = "experience_lacking"  # 缺少相关经验


@dataclass
class ConfidenceAssessment:
    """置信度评估结果"""
    query: str
    overall_confidence: float
    level: ConfidenceLevel
    archival_coverage: float = 0.0     # Archival知识覆盖率
    recall_relevance: float = 0.0      # Recall经验相关性
    rule_coverage: float = 0.0         # 规则覆盖度
    known_aspects: List[str] = field(default_factory=list)
    unknown_aspects: List[str] = field(default_factory=list)
    suggestions: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict:
        return {
            "query": self.query,
            "overall_confidence": round(self.overall_confidence, 3),
            "level": self.level.value,
            "archival_coverage": round(self.archival_coverage, 3),
            "recall_relevance": round(self.recall_relevance, 3),
            "rule_coverage": round(self.rule_coverage, 3),
            "known_aspects": self.known_aspects,
            "unknown_aspects": self.unknown_aspects,
            "suggestions": self.suggestions,
        }


@dataclass
class KnowledgeGap:
    """知识盲区"""
    gap_type: GapType
    domain: str
    description: str
    severity: float          # 0-1, 越高越严重
    remediation: str         # 补救措施
    priority: str = "P2"     # P0/P1/P2

    def to_dict(self) -> Dict:
        return {
            "gap_type": self.gap_type.value,
            "domain": self.domain,
            "description": self.description,
            "severity": round(self.severity, 3),
            "remediation": self.remediation,
            "priority": self.priority,
        }


@dataclass
class SelfAssessment:
    """自我评估结果"""
    task_type: str
    can_handle: bool
    confidence: float
    capability_match: float     # 能力匹配度
    experience_match: float     # 经验匹配度
    risks: List[str] = field(default_factory=list)
    recommendations: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict:
        return {
            "task_type": self.task_type,
            "can_handle": self.can_handle,
            "confidence": round(self.confidence, 3),
            "capability_match": round(self.capability_match, 3),
            "experience_match": round(self.experience_match, 3),
            "risks": self.risks,
            "recommendations": self.recommendations,
        }


class MetaCognition:
    """
    元认知模块 — Agent知道自己"知道什么"和"不知道什么"

    核心能力：
    1. assess_confidence — 评估对某问题的置信度
    2. identify_knowledge_gaps — 识别知识盲区
    3. self_improve — 针对盲区主动学习
    4. assess_capability — 评估自身能否完成某类任务
    5. adaptive_strategy — 根据元认知结果调整执行策略

    用法：
        meta = MetaCognition(memory_manager=mm)
        assessment = meta.assess_confidence("纳米SiO2对SSC的影响")
        if assessment.level == ConfidenceLevel.LOW:
            meta.self_improve(assessment.unknown_aspects)
    """

    def __init__(
        self,
        memory_manager: Any = None,
        api_endpoint: Optional[str] = None,
        api_key: Optional[str] = None,
        confidence_threshold_high: float = 0.8,
        confidence_threshold_low: float = 0.4,
    ):
        self.memory_manager = memory_manager
        self.api_endpoint = api_endpoint
        self.api_key = api_key
        self.confidence_threshold_high = confidence_threshold_high
        self.confidence_threshold_low = confidence_threshold_low

        # 缓存
        self._gap_cache: List[KnowledgeGap] = []
        self._assessment_cache: Dict[str, ConfidenceAssessment] = {}

        # 统计
        self._stats = {
            "assessments": 0,
            "gaps_identified": 0,
            "improvements_triggered": 0,
            "strategy_adjustments": 0,
        }

    # ============ 核心方法 ============

    def assess_confidence(self, query: str, use_llm: bool = True) -> ConfidenceAssessment:
        """
        评估对某问题的置信度

        三级判断：
        - HIGH(>0.8) → 直接回答，高置信
        - MEDIUM(0.4-0.8) → 回答+标注不确定性+建议搜索
        - LOW(<0.4) → 主动搜索/求助/触发学习
        """
        self._stats["assessments"] += 1

        # 缓存检查
        cache_key = query[:100]
        if cache_key in self._assessment_cache:
            return self._assessment_cache[cache_key]

        archival_coverage = 0.0
        recall_relevance = 0.0
        rule_coverage = 0.0
        known_aspects = []
        unknown_aspects = []

        # 1. 检查Archival Memory中的知识覆盖
        if self.memory_manager:
            try:
                archival_results = self.memory_manager.archival.search(query, top_k=5)
                if archival_results:
                    archival_coverage = min(1.0, len(archival_results) / 3.0)
                    for entry in archival_results[:3]:
                        known_aspects.append(f"{entry.domain}: {entry.content[:80]}")
            except Exception:
                pass

            # 2. 检查Recall Memory中的相关经验
            try:
                recall_results = self.memory_manager.recall.recall(query, top_k=5)
                if recall_results:
                    recall_relevance = min(1.0, len(recall_results) / 3.0)
                    for ep in recall_results[:2]:
                        if ep.lessons:
                            known_aspects.append(f"经验: {ep.lessons[:80]}")
            except Exception:
                pass

            # 3. 检查Procedural Rules
            try:
                rules = self.memory_manager.recall.get_rules(min_confidence=0.5)
                query_words = set(query.lower().split())
                matching_rules = []
                for rule in rules:
                    rule_words = set(rule.condition.lower().split())
                    overlap = len(query_words & rule_words) / max(len(query_words | rule_words), 1)
                    if overlap > 0.2:
                        matching_rules.append(rule)
                rule_coverage = min(1.0, len(matching_rules) / 2.0)
            except Exception:
                pass

        # 4. LLM增强评估（可选）
        if use_llm and (archival_coverage + recall_relevance) < 1.0:
            llm_assessment = self._llm_assess_confidence(query)
            if llm_assessment:
                unknown_aspects = llm_assessment.get("unknown_aspects", [])

        # 综合置信度计算
        overall = self._compute_overall_confidence(
            archival_coverage, recall_relevance, rule_coverage
        )

        # 判断级别
        if overall >= self.confidence_threshold_high:
            level = ConfidenceLevel.HIGH
        elif overall >= self.confidence_threshold_low:
            level = ConfidenceLevel.MEDIUM
        else:
            level = ConfidenceLevel.LOW

        # 生成建议
        suggestions = self._generate_suggestions(level, archival_coverage, recall_relevance)

        assessment = ConfidenceAssessment(
            query=query,
            overall_confidence=overall,
            level=level,
            archival_coverage=archival_coverage,
            recall_relevance=recall_relevance,
            rule_coverage=rule_coverage,
            known_aspects=known_aspects[:5],
            unknown_aspects=unknown_aspects[:5],
            suggestions=suggestions,
        )

        self._assessment_cache[cache_key] = assessment
        return assessment

    def identify_knowledge_gaps(self, domain: Optional[str] = None) -> List[KnowledgeGap]:
        """
        识别知识盲区 — 基于Archival Memory覆盖率分析

        对每个注册领域：
        1. 检查文档数量 vs 目标数量
        2. 检查文档的时间新鲜度
        3. 检查经验规则的覆盖度
        """
        gaps = []

        if not self.memory_manager:
            return gaps

        # 获取领域配置
        # 加载 KNOWLEDGE_DOMAINS — 优先 YAML > config.py > 默认空字典
        domains_config = {}
        _mc_cfg_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'config', 'config.yaml')
        if os.path.exists(_mc_cfg_path):
            try:
                import yaml as _yaml
                with open(_mc_cfg_path, 'r', encoding='utf-8') as _f:
                    _mc_cfg = _yaml.safe_load(_f) or {}
                domains_config = _mc_cfg.get('knowledge_domains', {})
            except Exception:
                pass
        if not domains_config:
            try:
                from config import KNOWLEDGE_DOMAINS  # noqa: F401 — 向后兼容
                domains_config = KNOWLEDGE_DOMAINS
            except ImportError:
                domains_config = {}

        for domain_key, config in domains_config.items():
            if domain and domain_key != domain:
                continue

            target_docs = config.get("target_docs", 10)
            priority = config.get("priority", "P2")

            # 统计当前文档数
            try:
                domain_entries = [
                    e for e in self.memory_manager.archival.entries.values()
                    if e.domain == domain_key
                ]
                current_count = len(domain_entries)
            except Exception:
                current_count = 0

            # 覆盖率
            coverage = current_count / max(target_docs, 1)

            if coverage < 0.3:
                # 严重缺失
                gaps.append(KnowledgeGap(
                    gap_type=GapType.DOMAIN_MISSING,
                    domain=domain_key,
                    description=f"领域「{config.get('display_name', domain_key)}」知识严重不足: "
                               f"{current_count}/{target_docs}文档",
                    severity=1.0 - coverage,
                    remediation=f"需要补充{target_docs - current_count}篇以上的领域文档",
                    priority="P0" if priority == "P0" else "P1",
                ))
            elif coverage < 0.7:
                # 部分缺失
                gaps.append(KnowledgeGap(
                    gap_type=GapType.TOPIC_SHALLOW,
                    domain=domain_key,
                    description=f"领域「{config.get('display_name', domain_key)}」知识覆盖不足: "
                               f"{current_count}/{target_docs}文档",
                    severity=0.7 - coverage,
                    remediation=f"建议补充{target_docs - current_count}篇领域文档以提升覆盖",
                    priority=priority,
                ))

            # 检查知识时效性
            try:
                for entry in domain_entries[:5]:
                    if hasattr(entry, 'timestamp') and entry.timestamp:
                        age_days = (time.time() - entry.timestamp) / 86400
                        if age_days > 180:  # 超过6个月
                            gaps.append(KnowledgeGap(
                                gap_type=GapType.KNOWLEDGE_OUTDATED,
                                domain=domain_key,
                                description=f"领域「{config.get('display_name', domain_key)}」部分知识已过时 "
                                           f"(超过{int(age_days)}天)",
                                severity=0.4,
                                remediation="需要更新过时知识或添加新文献",
                                priority="P1" if priority == "P0" else "P2",
                            ))
                            break
            except Exception:
                pass

        # 检查经验规则覆盖
        try:
            rules = self.memory_manager.recall.get_rules(min_confidence=0.3)
            if len(rules) < 5:
                gaps.append(KnowledgeGap(
                    gap_type=GapType.EXPERIENCE_LACKING,
                    domain="general",
                    description=f"行为规则不足: 只有{len(rules)}条规则，建议通过更多交互积累",
                    severity=0.3,
                    remediation="增加Agent交互频率，让Sleeptime Engine提炼更多规则",
                    priority="P2",
                ))
        except Exception:
            pass

        self._gap_cache = gaps
        self._stats["gaps_identified"] = len(gaps)
        return gaps

    def self_improve(self, gaps: Optional[List[str]] = None, domain: Optional[str] = None) -> Dict:
        """
        针对知识盲区主动学习

        1. 生成搜索查询
        2. 搜索并整理结果
        3. 摄入知识库

        Args:
            gaps: 要补的盲区描述列表（None则自动识别）
            domain: 限定领域

        Returns:
            学习结果摘要
        """
        self._stats["improvements_triggered"] += 1

        result = {
            "gaps_addressed": 0,
            "knowledge_ingested": 0,
            "search_queries": [],
            "errors": [],
        }

        # 确定要补的盲区
        if gaps:
            gap_descriptions = gaps
        else:
            knowledge_gaps = self.identify_knowledge_gaps(domain=domain)
            gap_descriptions = [g.description for g in knowledge_gaps]

        if not gap_descriptions:
            result["gaps_addressed"] = 0
            return result

        # 针对每个盲区生成搜索策略
        for gap_desc in gap_descriptions[:3]:  # 最多处理3个
            try:
                # 生成搜索查询
                search_queries = self._generate_search_queries(gap_desc)
                result["search_queries"].extend(search_queries)

                # 如果有web_search工具，执行搜索
                try:
                    from tools.web_search import WebSearchTool
                    search_tool = WebSearchTool()
                    for query in search_queries[:2]:
                        search_result = search_tool.search(query, limit=3)
                        if search_result and self.memory_manager:
                            # 摄入搜索结果
                            content = json.dumps(search_result, ensure_ascii=False) if isinstance(search_result, (list, dict)) else str(search_result)
                            self.memory_manager.remember(
                                content=content[:2000],
                                memory_type="archival",
                                domain=domain or "general",
                                source=f"self_improve:{query}",
                                importance=0.5,
                            )
                            result["knowledge_ingested"] += 1
                except ImportError:
                    logger.info("[MetaCognition] Web search tool not available, skipping search")

                result["gaps_addressed"] += 1

            except Exception as e:
                result["errors"].append(str(e))
                logger.warning(f"[MetaCognition] Self-improve failed for '{gap_desc[:50]}': {e}")

        return result

    def assess_capability(self, task_description: str) -> SelfAssessment:
        """
        评估自身能否完成某类任务

        基于以下维度：
        1. 知识覆盖 — 是否有足够的领域知识
        2. 经验匹配 — 是否完成过类似任务
        3. 工具可用 — 是否有必要的工具
        4. 资源约束 — 时间/计算资源是否足够
        """
        # 知识覆盖评估
        confidence = self.assess_confidence(task_description, use_llm=False)
        capability_match = confidence.archival_coverage * 0.6 + confidence.rule_coverage * 0.4

        # 经验匹配评估
        experience_match = confidence.recall_relevance

        # 工具可用性检查
        available_tools = self._check_available_tools()
        task_needs = self._infer_tool_needs(task_description)
        tool_coverage = len(task_needs & available_tools) / max(len(task_needs), 1) if task_needs else 1.0

        # 综合评估
        overall_confidence = (
            capability_match * 0.35
            + experience_match * 0.25
            + tool_coverage * 0.25
            + confidence.overall_confidence * 0.15
        )

        can_handle = overall_confidence >= self.confidence_threshold_low

        # 风险识别
        risks = []
        if capability_match < 0.3:
            risks.append("领域知识不足，结果可能不准确")
        if experience_match < 0.2:
            risks.append("缺乏相关经验，执行效率可能较低")
        if tool_coverage < 0.5:
            risks.append("必要工具缺失，可能无法完成部分步骤")

        # 建议
        recommendations = []
        if not can_handle:
            if capability_match < 0.3:
                recommendations.append("建议先搜索补充领域知识")
            if tool_coverage < 0.5:
                recommendations.append("建议配置必要的工具后再执行")
            recommendations.append("可以考虑降级为辅助模式，由用户引导执行")

        return SelfAssessment(
            task_type=task_description[:50],
            can_handle=can_handle,
            confidence=overall_confidence,
            capability_match=capability_match,
            experience_match=experience_match,
            risks=risks,
            recommendations=recommendations,
        )

    def adaptive_strategy(self, query: str) -> Dict[str, Any]:
        """
        根据元认知结果调整执行策略

        Returns:
            {
                "strategy": "direct/assisted/learning/delegated",
                "model": "pro/flash",
                "needs_search": bool,
                "needs_verification": bool,
                "confidence_note": str,
                "context_boost": List[str],  # 需要额外注入的上下文
            }
        """
        self._stats["strategy_adjustments"] += 1
        assessment = self.assess_confidence(query)

        if assessment.level == ConfidenceLevel.HIGH:
            return {
                "strategy": "direct",
                "model": "flash",
                "needs_search": False,
                "needs_verification": False,
                "confidence_note": "高置信度，直接回答",
                "context_boost": [],
            }

        elif assessment.level == ConfidenceLevel.MEDIUM:
            boost = assessment.unknown_aspects[:3]
            return {
                "strategy": "assisted",
                "model": "pro",
                "needs_search": True,
                "needs_verification": True,
                "confidence_note": f"中等置信度({assessment.overall_confidence:.0%})，回答将标注不确定性",
                "context_boost": boost,
            }

        else:  # LOW
            return {
                "strategy": "learning",
                "model": "pro",
                "needs_search": True,
                "needs_verification": True,
                "confidence_note": f"低置信度({assessment.overall_confidence:.0%})，建议先学习或搜索",
                "context_boost": assessment.unknown_aspects[:5],
            }

    # ============ 内部方法 ============

    def _compute_overall_confidence(
        self, archival: float, recall: float, rules: float
    ) -> float:
        """综合计算置信度"""
        # 加权：知识权重最高，经验次之，规则辅助
        raw = archival * 0.50 + recall * 0.30 + rules * 0.20

        # 如果全部为0，给一个基础置信度（通用知识）
        if raw == 0.0:
            raw = 0.15  # LLM自带通用知识

        return min(1.0, raw)

    def _generate_suggestions(
        self, level: ConfidenceLevel, archival: float, recall: float
    ) -> List[str]:
        """根据置信度级别生成建议"""
        suggestions = []

        if level == ConfidenceLevel.LOW:
            if archival < 0.3:
                suggestions.append("建议搜索补充相关知识后再回答")
            suggestions.append("回答中应明确标注不确定性")
            if recall < 0.2:
                suggestions.append("缺乏相关经验，建议谨慎参考")

        elif level == ConfidenceLevel.MEDIUM:
            if archival < 0.5:
                suggestions.append("部分知识可能不完整，建议搜索验证关键点")
            suggestions.append("回答中建议附上置信度标注")

        return suggestions

    def _llm_assess_confidence(self, query: str) -> Optional[Dict]:
        """用LLM评估置信度（增强评估）"""
        if not self.api_endpoint or not self.api_key:
            return None

        try:
            import urllib.request
            data = json.dumps({
                "model": "deepseek-v4-flash",
                "messages": [{
                    "role": "user",
                    "content": f"对于问题「{query}」，AI助手可能在哪些方面知识不足？列出最多3个方面。用JSON返回: {{\"unknown_aspects\": [\"方面1\", \"方面2\"]}}"
                }],
                "temperature": 0.3,
                "max_tokens": 256,
            }).encode("utf-8")

            req = urllib.request.Request(
                self.api_endpoint,
                data=data,
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {self.api_key}",
                },
            )
            with urllib.request.urlopen(req, timeout=30) as resp:
                result = json.loads(resp.read().decode("utf-8"))
                content = result["choices"][0]["message"]["content"]
                json_match = re.search(r'\{[\s\S]*\}', content)
                if json_match:
                    return json.loads(json_match.group())
        except Exception:
            pass

        return None

    def _generate_search_queries(self, gap_description: str) -> List[str]:
        """为知识盲区生成搜索查询"""
        # 简单提取关键词
        keywords = re.findall(r'[\u4e00-\u9fff]+|[a-zA-Z]+', gap_description)
        queries = []

        if keywords:
            core = " ".join(keywords[:4])
            queries.append(f"{core} 最新进展 综述")
            queries.append(f"{core} 核心概念 入门")

        return queries[:3]

    def _check_available_tools(self) -> set:
        """检查可用工具集"""
        available = {"chat", "react", "codeact"}
        tool_modules = [
            ("tools.web_search", "web_search"),
            ("tools.file_ops", "file_ops"),
            ("tools.data_query", "data_query"),
            ("tools.calculator", "calculator"),
            ("tools.api_caller", "api_caller"),
        ]
        for module, tool_name in tool_modules:
            try:
                __import__(module)
                available.add(tool_name)
            except ImportError:
                pass
        return available

    def _infer_tool_needs(self, task: str) -> set:
        """推断任务需要哪些工具"""
        needs = {"chat"}  # 基础对话总是需要的
        task_lower = task.lower()

        if any(kw in task_lower for kw in ["搜索", "查询", "最新", "调研", "search"]):
            needs.add("web_search")
        if any(kw in task_lower for kw in ["文件", "读取", "写入", "file"]):
            needs.add("file_ops")
        if any(kw in task_lower for kw in ["计算", "分析", "统计", "calculate"]):
            needs.add("calculator")
        if any(kw in task_lower for kw in ["API", "接口", "请求", "http"]):
            needs.add("api_caller")
        if any(kw in task_lower for kw in ["数据", "表格", "dataset"]):
            needs.add("data_query")

        return needs

    def get_stats(self) -> Dict:
        """获取统计信息"""
        return self._stats.copy()

    def get_gap_summary(self) -> str:
        """获取知识盲区摘要"""
        if not self._gap_cache:
            self.identify_knowledge_gaps()

        if not self._gap_cache:
            return "知识盲区: 无明显盲区"

        lines = ["知识盲区:"]
        for gap in self._gap_cache:
            lines.append(f"  [{gap.priority}] {gap.domain}: {gap.description[:80]}")
        return "\n".join(lines)

    def to_codeact_globals(self) -> Dict[str, Any]:
        """导出为CodeAct全局函数"""
        return {
            "assess_confidence": self.assess_confidence,
            "identify_gaps": self.identify_knowledge_gaps,
            "self_improve": self.self_improve,
        }
