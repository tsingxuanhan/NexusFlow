# -*- coding: utf-8 -*-
"""
铉枢·炉守 模型路由器
XuanHub Model Router — P2 (Mira-inspired)

根据任务复杂度自动路由到合适的模型，优化成本：
- 简单问答/格式化 → flash（快且便宜）
- 推理/分析/代码 → pro（慢但准确）
- 后台批量 → flash（省钱）

路由策略：基于规则 + LLM自评估
"""

import re
import logging
from typing import Dict, Any, Optional, List
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger("ModelRouter")


class TaskComplexity(Enum):
    """任务复杂度"""
    TRIVIAL = "trivial"      # 极简：问候/确认/格式转换
    SIMPLE = "simple"        # 简单：问答/查词/翻译
    MODERATE = "moderate"    # 中等：总结/比较/短文
    COMPLEX = "complex"      # 复杂：推理/分析/代码生成
    CRITICAL = "critical"    # 关键：科研/决策/多步推理


# 复杂度 → 推荐模型
COMPLEXITY_MODEL_MAP = {
    TaskComplexity.TRIVIAL: "flash",
    TaskComplexity.SIMPLE: "flash",
    TaskComplexity.MODERATE: "flash",     # 中等也用flash，省钱
    TaskComplexity.COMPLEX: "pro",
    TaskComplexity.CRITICAL: "pro",
}


@dataclass
class RoutingResult:
    """路由结果"""
    model: str                          # 推荐模型
    complexity: TaskComplexity           # 任务复杂度
    confidence: float                    # 路由置信度 0-1
    reason: str                         # 路由理由
    fallback: Optional[str] = None      # 降级备选模型


class ModelRouter:
    """
    模型路由器 — 根据任务复杂度自动选择模型
    
    借鉴Mira的模型路由思路：按复杂度路由到small/medium/large优化成本。
    我们简化为 flash/pro 两级，未来可扩展。
    
    用法:
        router = ModelRouter()
        result = router.route("分析SSC水泥的微观结构变化")
        print(result.model)  # "pro"
        
        result = router.route("你好")
        print(result.model)  # "flash"
    """
    
    # 触发pro模型的关键词模式
    PRO_PATTERNS = [
        # 推理/分析
        (r'(分析|推理|推断|论证|证明|推导|解[释决]|为什么|原因|机理|机制)', 'reasoning'),
        # 代码/工程
        (r'(编写|实现|开发|重构|优化|调试|debug|code|函数|类|算法)', 'code'),
        # 科研/学术
        (r'(论文|研究|实验|假设|文献|综述|方法学|数据[分处]|统计)', 'research'),
        # 多步任务
        (r'(步骤|流程|计划|方案|设计|架构|系统|模块)', 'multi_step'),
        # 数学/计算
        (r'(计算|求解|方程|积分|微分|矩阵|优化|最小化|最大化)', 'math'),
    ]
    
    # 触发flash的简单模式
    FLASH_PATTERNS = [
        (r'^(你好|嗨|hello|hi|hey)[\s!！。？?]*$', 'greeting'),
        (r'^(是|否|对|不对|ok|好的|可以|不行|确认|取消)$', 'confirmation'),
        (r'(翻译|translate|convert|格式化|format)', 'simple_transform'),
        (r'(定义|什么是|what is|含义|意思)', 'definition'),
        (r'(多少|几|when|where|who|哪个|哪个)', 'fact_lookup'),
    ]
    
    def __init__(
        self,
        default_model: str = "flash",
        force_model: Optional[str] = None,  # 强制使用某模型（调试用）
    ):
        self.default_model = default_model
        self.force_model = force_model
        self._stats = {"routed_pro": 0, "routed_flash": 0, "total": 0}
    
    def route(self, prompt: str, context: Optional[Dict] = None) -> RoutingResult:
        """
        根据prompt路由到合适的模型
        
        Args:
            prompt: 用户输入
            context: 额外上下文（如当前模式、历史长度等）
            
        Returns:
            RoutingResult
        """
        self._stats["total"] += 1
        
        # 强制模式
        if self.force_model:
            return RoutingResult(
                model=self.force_model,
                complexity=TaskComplexity.MODERATE,
                confidence=1.0,
                reason=f"Force model: {self.force_model}",
            )
        
        # 上下文覆盖（如当前在research模式，强制pro）
        if context and context.get("mode") in ("research", "precise"):
            self._stats["routed_pro"] += 1
            return RoutingResult(
                model="pro",
                complexity=TaskComplexity.COMPLEX,
                confidence=0.9,
                reason=f"Mode override: {context['mode']}",
                fallback="flash",
            )
        
        # 基于规则的路由
        complexity, reason = self._classify_complexity(prompt)
        model = COMPLEXITY_MODEL_MAP[complexity]
        
        # 置信度评估
        confidence = self._estimate_confidence(prompt, complexity)
        
        # fallback
        fallback = "flash" if model == "pro" else None
        
        # 统计
        if model == "pro":
            self._stats["routed_pro"] += 1
        else:
            self._stats["routed_flash"] += 1
        
        return RoutingResult(
            model=model,
            complexity=complexity,
            confidence=confidence,
            reason=reason,
            fallback=fallback,
        )
    
    def _classify_complexity(self, prompt: str) -> tuple:
        """分类任务复杂度"""
        prompt_lower = prompt.lower().strip()
        
        # 极简检测
        if len(prompt_lower) <= 5:
            return TaskComplexity.TRIVIAL, "极短输入"
        
        # Flash模式匹配
        for pattern, category in self.FLASH_PATTERNS:
            if re.search(pattern, prompt_lower):
                return TaskComplexity.SIMPLE, f"简单任务: {category}"
        
        # Pro模式匹配
        pro_hits = []
        for pattern, category in self.PRO_PATTERNS:
            if re.search(pattern, prompt_lower):
                pro_hits.append(category)
        
        if len(pro_hits) >= 2:
            return TaskComplexity.CRITICAL, f"多重复杂: {', '.join(pro_hits)}"
        elif len(pro_hits) == 1:
            return TaskComplexity.COMPLEX, f"复杂任务: {pro_hits[0]}"
        
        # 长度启发式
        if len(prompt) > 500:
            return TaskComplexity.MODERATE, "长输入(>500字符)"
        
        # 默认中等
        return TaskComplexity.MODERATE, "默认中等"
    
    def _estimate_confidence(self, prompt: str, complexity: TaskComplexity) -> float:
        """评估路由置信度"""
        # 模式匹配越明确，置信度越高
        prompt_lower = prompt.lower()
        
        pro_count = sum(1 for p, _ in self.PRO_PATTERNS if re.search(p, prompt_lower))
        flash_count = sum(1 for p, _ in self.FLASH_PATTERNS if re.search(p, prompt_lower))
        
        total_signals = pro_count + flash_count
        if total_signals == 0:
            return 0.5  # 无明确信号，中等置信
        
        if complexity in (TaskComplexity.TRIVIAL, TaskComplexity.SIMPLE):
            return 0.7 + 0.1 * flash_count
        elif complexity in (TaskComplexity.COMPLEX, TaskComplexity.CRITICAL):
            return 0.7 + 0.1 * pro_count
        else:
            return 0.5
    
    def get_stats(self) -> Dict[str, Any]:
        """路由统计"""
        total = self._stats["total"]
        return {
            **self._stats,
            "flash_ratio": self._stats["routed_flash"] / max(total, 1),
            "pro_ratio": self._stats["routed_pro"] / max(total, 1),
        }


def create_model_router(default_model: str = "flash") -> ModelRouter:
    """创建模型路由器"""
    return ModelRouter(default_model=default_model)
