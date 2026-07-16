# -*- coding: utf-8 -*-
"""
铉枢·炉守 Cross-Domain Transfer — 跨领域知识迁移
XuanHub Cross-Domain Knowledge Transfer

将A领域的经验/知识迁移到B领域：
1. 类比发现 — 识别领域间的结构相似性
2. 规则迁移 — 通过类比映射行为规则
3. 概念桥接 — 建立跨领域概念映射
4. 迁移验证 — 检验迁移结果的有效性
5. 迁移记忆 — 记录成功的迁移模式供复用

灵感来源：
- "材料相变" ↔ "神经网络相变"
- "晶体缺陷工程" ↔ "对抗样本防御"
- "复合材料界面" ↔ "多Agent协作接口"
"""

import json
import re
import time
import logging
from typing import Any, Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger("CrossDomain")


class AnalogyType(Enum):
    """类比类型"""
    STRUCTURAL = "structural"      # 结构相似（如层级结构、网络拓扑）
    FUNCTIONAL = "functional"      # 功能相似（如优化、搜索、过滤）
    PROCESS = "process"            # 过程相似（如相变、演化、迭代）
    MECHANISM = "mechanism"        # 机制相似（如反馈、衰减、增强）


@dataclass
class Analogy:
    """类比关系"""
    source_domain: str
    target_domain: str
    source_concept: str
    target_concept: str
    analogy_type: AnalogyType
    similarity: float             # 相似度 0-1
    reasoning: str                # 类比推理说明
    transferable: bool = True     # 是否可迁移

    def to_dict(self) -> Dict:
        return {
            "source_domain": self.source_domain,
            "target_domain": self.target_domain,
            "source_concept": self.source_concept,
            "target_concept": self.target_concept,
            "analogy_type": self.analogy_type.value,
            "similarity": round(self.similarity, 3),
            "reasoning": self.reasoning,
            "transferable": self.transferable,
        }


@dataclass
class TransferResult:
    """迁移结果"""
    source_domain: str
    target_domain: str
    analogies: List[Analogy]
    transferred_rules: List[Dict]
    validation_score: float       # 迁移验证分数
    notes: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict:
        return {
            "source_domain": self.source_domain,
            "target_domain": self.target_domain,
            "analogies": [a.to_dict() for a in self.analogies],
            "transferred_rules": self.transferred_rules,
            "validation_score": round(self.validation_score, 3),
            "notes": self.notes,
        }


class CrossDomainTransfer:
    """
    跨领域知识迁移 — 将A领域经验迁移到B领域

    核心流程：
    1. find_analogy — 用PRO模型发现领域间类比
    2. transfer_rule — 通过类比映射迁移规则
    3. validate_transfer — 验证迁移有效性
    4. store_transfer_pattern — 记录成功迁移模式

    用法：
        xfer = CrossDomainTransfer(memory_manager=mm)
        analogies = xfer.find_analogy("materials", "ai_ml")
        result = xfer.transfer(analogies)
    """

    # 预定义的领域间常见类比（种子知识）
    SEED_ANALOGIES = [
        Analogy(
            source_domain="materials", target_domain="ai_ml",
            source_concept="相变", target_concept="神经网络相变",
            analogy_type=AnalogyType.PROCESS,
            similarity=0.75,
            reasoning="材料相变（有序↔无序）类似神经网络训练中的相变现象（泛化↔过拟合临界点）",
        ),
        Analogy(
            source_domain="materials", target_domain="ai_ml",
            source_concept="晶体缺陷工程", target_concept="对抗样本防御",
            analogy_type=AnalogyType.MECHANISM,
            similarity=0.65,
            reasoning="控制缺陷提升材料性能 ↔ 控制扰动增强模型鲁棒性",
        ),
        Analogy(
            source_domain="materials", target_domain="ai_ml",
            source_concept="复合材料界面", target_concept="多Agent协作接口",
            analogy_type=AnalogyType.STRUCTURAL,
            similarity=0.70,
            reasoning="界面决定复合材料整体性能 ↔ 接口协议决定多Agent系统协作效率",
        ),
        Analogy(
            source_domain="materials", target_domain="cs",
            source_concept="梯度材料", target_concept="微服务渐进式架构",
            analogy_type=AnalogyType.FUNCTIONAL,
            similarity=0.55,
            reasoning="梯度材料性能连续变化 ↔ 微服务渐进式部署和灰度发布",
        ),
        Analogy(
            source_domain="physics", target_domain="ai_ml",
            source_concept="能量最小化", target_concept="损失函数优化",
            analogy_type=AnalogyType.MECHANISM,
            similarity=0.85,
            reasoning="物理系统趋向能量最低态 ↔ 神经网络趋向损失最小化",
        ),
        Analogy(
            source_domain="physics", target_domain="ai_ml",
            source_concept="退火", target_concept="模拟退火/学习率调度",
            analogy_type=AnalogyType.PROCESS,
            similarity=0.80,
            reasoning="物理退火过程 ↔ 学习率衰减策略",
        ),
        Analogy(
            source_domain="biology", target_domain="ai_ml",
            source_concept="自然选择", target_concept="进化算法/模型选择",
            analogy_type=AnalogyType.PROCESS,
            similarity=0.75,
            reasoning="适者生存 ↔ 模型选择保留最优个体",
        ),
        Analogy(
            source_domain="economics", target_domain="ai_ml",
            source_concept="供需均衡", target_concept="GAN纳什均衡",
            analogy_type=AnalogyType.MECHANISM,
            similarity=0.70,
            reasoning="供需平衡点 ↔ 生成器与判别器的纳什均衡",
        ),
    ]

    def __init__(
        self,
        memory_manager: Any = None,
        api_endpoint: Optional[str] = None,
        api_key: Optional[str] = None,
    ):
        self.memory_manager = memory_manager
        self.api_endpoint = api_endpoint
        self.api_key = api_key

        # 迁移历史
        self._transfer_history: List[TransferResult] = []

        # 领域概念缓存
        self._domain_concepts: Dict[str, List[str]] = {}

        # 统计
        self._stats = {
            "analogies_found": 0,
            "rules_transferred": 0,
            "transfers_validated": 0,
            "successful_transfers": 0,
        }

    # ============ 核心方法 ============

    def find_analogy(
        self,
        source_domain: str,
        target_domain: str,
        concept: Optional[str] = None,
        use_llm: bool = True,
    ) -> List[Analogy]:
        """
        发现两个领域间的类比关系

        Args:
            source_domain: 源领域
            target_domain: 目标领域
            concept: 限定某个具体概念的类比（可选）
            use_llm: 是否使用LLM增强类比发现
        """
        analogies = []

        # 1. 从种子类比中查找
        for seed in self.SEED_ANALOGIES:
            if (seed.source_domain == source_domain and seed.target_domain == target_domain) or \
               (seed.source_domain == target_domain and seed.target_domain == source_domain):
                if concept is None or concept in seed.source_concept or concept in seed.target_concept:
                    analogies.append(seed)

        # 2. 从记忆系统中查找已有迁移模式
        if self.memory_manager:
            memory_analogies = self._find_memory_analogies(source_domain, target_domain)
            analogies.extend(memory_analogies)

        # 3. LLM增强类比发现
        if use_llm and len(analogies) < 3:
            llm_analogies = self._llm_find_analogy(source_domain, target_domain, concept)
            analogies.extend(llm_analogies)

        # 4. 基于领域概念的自动类比（无LLM降级）
        if len(analogies) < 2:
            auto_analogies = self._auto_find_analogy(source_domain, target_domain)
            analogies.extend(auto_analogies)

        # 去重
        seen = set()
        unique = []
        for a in analogies:
            key = f"{a.source_concept}->{a.target_concept}"
            if key not in seen:
                seen.add(key)
                unique.append(a)

        self._stats["analogies_found"] += len(unique)
        return unique

    def transfer(self, analogies: List[Analogy]) -> TransferResult:
        """
        执行跨领域迁移

        对每个类比：
        1. 从源领域提取相关规则
        2. 通过类比映射转换到目标领域
        3. 验证迁移结果
        """
        if not analogies:
            return TransferResult(
                source_domain="",
                target_domain="",
                analogies=[],
                transferred_rules=[],
                validation_score=0.0,
                notes=["无可用类比，无法执行迁移"],
            )

        source_domain = analogies[0].source_domain
        target_domain = analogies[0].target_domain

        transferred_rules = []
        notes = []

        for analogy in analogies:
            if not analogy.transferable:
                notes.append(f"跳过不可迁移类比: {analogy.source_concept}→{analogy.target_concept}")
                continue

            # 从源领域提取规则
            source_rules = self._extract_source_rules(analogy.source_domain, analogy.source_concept)

            # 通过类比映射转换
            for rule in source_rules:
                transferred = self._map_rule(rule, analogy)
                if transferred:
                    transferred_rules.append(transferred)

            notes.append(
                f"迁移 {analogy.source_concept}→{analogy.target_concept} "
                f"(相似度={analogy.similarity:.0%}, 类型={analogy.analogy_type.value})"
            )

        # 验证迁移
        validation_score = self._validate_transfer(transferred_rules, target_domain)

        result = TransferResult(
            source_domain=source_domain,
            target_domain=target_domain,
            analogies=analogies,
            transferred_rules=transferred_rules,
            validation_score=validation_score,
            notes=notes,
        )

        self._transfer_history.append(result)
        self._stats["rules_transferred"] += len(transferred_rules)
        self._stats["transfers_validated"] += 1
        if validation_score >= 0.5:
            self._stats["successful_transfers"] += 1

        # 记录成功的迁移模式
        if validation_score >= 0.5 and self.memory_manager:
            self._store_transfer_pattern(result)

        return result

    def transfer_rule(self, rule: Dict, analogy: Analogy) -> Optional[Dict]:
        """
        通过类比迁移单条规则

        Args:
            rule: 源领域规则 {condition, action, confidence}
            analogy: 类比关系

        Returns:
            迁移后的规则（target_domain版本）
        """
        return self._map_rule(rule, analogy)

    def get_transfer_history(self, domain: Optional[str] = None) -> List[Dict]:
        """获取迁移历史"""
        if domain:
            return [
                r.to_dict() for r in self._transfer_history
                if r.source_domain == domain or r.target_domain == domain
            ]
        return [r.to_dict() for r in self._transfer_history]

    # ============ 内部方法 ============

    def _find_memory_analogies(self, source: str, target: str) -> List[Analogy]:
        """从记忆中查找迁移模式"""
        analogies = []
        if not self.memory_manager:
            return analogies

        try:
            results = self.memory_manager.archival.search(
                f"跨领域迁移 {source} {target}", top_k=3
            )
            for entry in results:
                if "迁移" in entry.content or "类比" in entry.content:
                    analogies.append(Analogy(
                        source_domain=source,
                        target_domain=target,
                        source_concept="记忆迁移模式",
                        target_concept="记忆迁移模式",
                        analogy_type=AnalogyType.FUNCTIONAL,
                        similarity=0.5,
                        reasoning=entry.content[:200],
                    ))
        except Exception:
            pass

        return analogies

    def _llm_find_analogy(
        self, source: str, target: str, concept: Optional[str] = None
    ) -> List[Analogy]:
        """用LLM发现类比"""
        if not self.api_endpoint or not self.api_key:
            return []

        concept_hint = f"，特别关注概念「{concept}」" if concept else ""

        prompt = f"""发现{source}领域和{target}领域之间的类比关系{concept_hint}。

请列出3-5个类比，每个包含：
- 源概念（{source}领域）
- 目标概念（{target}领域）
- 类比类型（structural/functional/process/mechanism）
- 相似度（0.0-1.0）
- 推理说明

用JSON数组返回:
[{{"source_concept": "...", "target_concept": "...", "type": "structural", "similarity": 0.7, "reasoning": "..."}}]

只返回JSON数组。"""

        try:
            import urllib.request
            data = json.dumps({
                "model": "deepseek-v4-pro",
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 1.0,
                "max_tokens": 1024,
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
                content = result["choices"][0]["message"]["content"]

                json_match = re.search(r'\[[\s\S]*\]', content)
                if json_match:
                    items = json.loads(json_match.group())
                    analogies = []
                    for item in items[:5]:
                        try:
                            atype = AnalogyType(item.get("type", "functional"))
                        except ValueError:
                            atype = AnalogyType.FUNCTIONAL
                        analogies.append(Analogy(
                            source_domain=source,
                            target_domain=target,
                            source_concept=item.get("source_concept", ""),
                            target_concept=item.get("target_concept", ""),
                            analogy_type=atype,
                            similarity=min(1.0, max(0.0, float(item.get("similarity", 0.5)))),
                            reasoning=item.get("reasoning", ""),
                        ))
                    return analogies
        except Exception as e:
            logger.warning(f"[CrossDomain] LLM analogy search failed: {e}")

        return []

    def _auto_find_analogy(self, source: str, target: str) -> List[Analogy]:
        """自动基于领域概念发现类比（降级方案）"""
        # 通用跨领域模式
        common_patterns = {
            ("materials", "physics"): [
                ("力学性能", "力学定律", AnalogyType.FUNCTIONAL, 0.8),
                ("微观结构", "量子态", AnalogyType.STRUCTURAL, 0.6),
            ],
            ("ai_ml", "math_stats"): [
                ("神经网络", "函数逼近", AnalogyType.FUNCTIONAL, 0.85),
                ("优化算法", "梯度下降", AnalogyType.MECHANISM, 0.9),
            ],
            ("cs", "ai_ml"): [
                ("数据结构", "特征表示", AnalogyType.STRUCTURAL, 0.65),
                ("算法复杂度", "模型容量", AnalogyType.FUNCTIONAL, 0.6),
            ],
        }

        analogies = []
        key = (source, target)
        reverse_key = (target, source)

        for pattern_key in [key, reverse_key]:
            if pattern_key in common_patterns:
                for src_concept, tgt_concept, atype, sim in common_patterns[pattern_key]:
                    if pattern_key == reverse_key:
                        src_concept, tgt_concept = tgt_concept, src_concept
                    analogies.append(Analogy(
                        source_domain=source,
                        target_domain=target,
                        source_concept=src_concept,
                        target_concept=tgt_concept,
                        analogy_type=atype,
                        similarity=sim,
                        reasoning=f"通用跨领域模式: {src_concept} ↔ {tgt_concept}",
                    ))

        return analogies

    def _extract_source_rules(self, domain: str, concept: str) -> List[Dict]:
        """从源领域提取相关规则"""
        rules = []

        if self.memory_manager:
            try:
                recall_rules = self.memory_manager.recall.get_rules(min_confidence=0.3)
                for rule in recall_rules:
                    if domain in rule.condition.lower() or concept.lower() in rule.condition.lower():
                        rules.append({
                            "condition": rule.condition,
                            "action": rule.action,
                            "confidence": rule.confidence,
                            "source": "recall",
                        })
            except Exception:
                pass

        # 如果没找到，生成通用规则
        if not rules:
            rules = self._generate_generic_rules(domain, concept)

        return rules[:5]  # 最多5条

    def _generate_generic_rules(self, domain: str, concept: str) -> List[Dict]:
        """生成通用领域规则（无记忆时降级）"""
        generic_rules = {
            "materials": [
                {"condition": "材料性能不佳", "action": "检查微观结构和界面", "confidence": 0.7},
                {"condition": "复合材料失效", "action": "分析界面结合和应力分布", "confidence": 0.7},
            ],
            "ai_ml": [
                {"condition": "模型过拟合", "action": "增加正则化或数据增强", "confidence": 0.8},
                {"condition": "训练不稳定", "action": "调整学习率或使用梯度裁剪", "confidence": 0.7},
            ],
            "physics": [
                {"condition": "系统不稳定", "action": "寻找能量最小化路径", "confidence": 0.75},
            ],
        }
        return generic_rules.get(domain, [])

    def _map_rule(self, rule: Dict, analogy: Analogy) -> Optional[Dict]:
        """通过类比映射规则"""
        if not analogy.transferable:
            return None

        # 简单概念替换映射
        source_terms = analogy.source_concept.split()
        target_terms = analogy.target_concept.split()

        mapped_condition = rule.get("condition", "")
        mapped_action = rule.get("action", "")

        # 术语替换
        for src, tgt in zip(source_terms, target_terms):
            if src in mapped_condition:
                mapped_condition = mapped_condition.replace(src, tgt)
            if src in mapped_action:
                mapped_action = mapped_action.replace(src, tgt)

        # 添加领域上下文
        mapped_condition = f"[{analogy.target_domain}] {mapped_condition}"
        mapped_action = f"[类比自{analogy.source_domain}] {mapped_action}"

        return {
            "condition": mapped_condition,
            "action": mapped_action,
            "original_confidence": rule.get("confidence", 0.5),
            "adjusted_confidence": rule.get("confidence", 0.5) * analogy.similarity * 0.8,
            "source_analogy": analogy.to_dict(),
            "transfer_type": "cross_domain",
        }

    def _validate_transfer(self, rules: List[Dict], target_domain: str) -> float:
        """验证迁移有效性"""
        if not rules:
            return 0.0

        # 启发式验证：
        # 1. 规则数量越多越好（但diminishing returns）
        quantity_score = min(1.0, len(rules) / 5.0) * 0.3

        # 2. 平均置信度
        avg_conf = sum(r.get("adjusted_confidence", 0) for r in rules) / max(len(rules), 1)
        confidence_score = avg_conf * 0.4

        # 3. 术语替换率（被替换的术语越多说明映射越充分）
        mapped_count = sum(1 for r in rules if "类比自" in r.get("action", ""))
        mapping_score = min(1.0, mapped_count / max(len(rules), 1)) * 0.3

        return quantity_score + confidence_score + mapping_score

    def _store_transfer_pattern(self, result: TransferResult) -> None:
        """记录成功的迁移模式到记忆系统"""
        try:
            content = (
                f"跨领域迁移: {result.source_domain}→{result.target_domain}, "
                f"验证分数={result.validation_score:.2f}, "
                f"规则数={len(result.transferred_rules)}"
            )
            for analogy in result.analogies[:3]:
                content += f"\n  类比: {analogy.source_concept}↔{analogy.target_concept} (相似度={analogy.similarity:.0%})"

            self.memory_manager.remember(
                content=content,
                memory_type="archival",
                domain="cross_domain",
                source="transfer_engine",
                importance=0.6,
            )
        except Exception as e:
            logger.warning(f"[CrossDomain] Failed to store transfer pattern: {e}")

    def get_stats(self) -> Dict:
        """获取统计信息"""
        return self._stats.copy()

    def to_codeact_globals(self) -> Dict[str, Any]:
        """导出为CodeAct全局函数"""
        return {
            "find_analogy": self.find_analogy,
            "cross_domain_transfer": self.transfer,
        }
