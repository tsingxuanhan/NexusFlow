# -*- coding: utf-8 -*-
"""
审查者 (Reviewer) — 质量审查Agent (Flash模型)
XuanHub v4.0 - Generalized Agent Role
"""

from nexusflow.agents.base_agent import BaseAgent, AgentRole, AgentRunMode
from nexusflow.memory.vector_memory import get_vector_memory
from typing import List, Dict, Optional

REVIEWER_SYSTEM_PROMPT = """你是"审查者"，铉枢项目中的质量守门员。

## 核心职责
验证结果、发现问题、提供反馈。你是最后一道门，质量不通过不放行。

## 审查原则
1. **宁可标⚠️不可标错✅**: 不确定时必须标记警告
2. **多维度审查**: 正确性/完整性/一致性/可维护性
3. **可追溯**: 所有问题标注依据
4. **建设性**: 发现问题的同时提供改进方案
5. **不妥协**: 质量标准不因进度压力降低

## 审查维度
- ✅ 通过 / ⚠️ 存疑 / ❌ 不通过
- 正确性：逻辑、数据、引用
- 完整性：遗漏、边界情况
- 一致性：内部矛盾、格式统一
- 可维护性：可读性、扩展性

## 输出规范
- 审查报告：逐项检查+总体评分+改进建议
- 评分标准：A(可发布) / B(需小改) / C(需大改) / D(需重做)"""


class ReviewerAgent(BaseAgent):
    """审查者 - 质量守门员（Flash模型）"""
    
    def __init__(self, domain_name: str = None, **kwargs):
        super().__init__(
            name="Reviewer",
            model="flash",
            system_prompt=REVIEWER_SYSTEM_PROMPT,
            role=AgentRole.REVIEWER,
            domain_name=domain_name,
            **kwargs
        )
        self.memory = get_vector_memory()
        
        # A2A能力注册
        if self.a2a:
            self.register_a2a_action("review", self.review_output)
            self.register_a2a_action("verify_result", self.verify_result)
            self.register_a2a_action("check_quality", self.check_quality)
            self.register_a2a_action("cross_validate", self.cross_validate)
            
            self.register_a2a_capability("review", "审查输出", ["审查", "review"])
            self.register_a2a_capability("verify_result", "验证结果", ["验证", "verify"])
            self.register_a2a_capability("check_quality", "质量检查", ["质量", "quality"])
            self.register_a2a_capability("cross_validate", "交叉验证", ["交叉", "cross"])
    
    def review_output(self, content: str, criteria: str = None) -> str:
        """审查输出内容"""
        criteria_section = f"\n审查标准：{criteria}" if criteria else ""
        
        prompt = f"""请审查以下内容：

{content}
{criteria_section}

审查维度：
1. 正确性：逻辑和数据是否准确
2. 完整性：是否有遗漏
3. 一致性：内部是否矛盾
4. 格式：是否符合规范

输出：逐项评分 + 总体评级(A/B/C/D) + 改进建议"""
        return self.chat(prompt)
    
    def verify_result(self, result: str, expectation: str) -> str:
        """验证执行结果是否达到预期"""
        prompt = f"""验证执行结果：

## 预期
{expectation}

## 实际结果
{result}

逐项对比：哪些达到？哪些未达到？差距多大？"""
        return self.chat(prompt)
    
    def check_quality(self, content: str, quality_type: str = "general") -> str:
        """质量检查"""
        type_map = {
            "code": "代码质量（正确性/安全性/性能/风格）",
            "text": "文本质量（准确性/完整性/可读性）",
            "data": "数据质量（完整性/一致性/时效性）",
            "general": "综合质量（正确性/完整性/一致性）",
        }
        
        prompt = f"""{type_map.get(quality_type, type_map["general"])}检查：

{content}

输出问题清单（按严重程度排序）+ 改进建议。"""
        return self.chat(prompt)
    
    def cross_validate(self, sources: List[str], topic: str) -> str:
        """交叉验证多个来源"""
        sources_text = "\n\n---\n\n".join([f"来源{i+1}:\n{s}" for i, s in enumerate(sources)])
        
        prompt = f"""交叉验证关于"{topic}"的多个来源：

{sources_text}

找出：
1. 所有来源一致的观点
2. 存在分歧的观点
3. 各来源独有的信息
4. 最可信的结论"""
        return self.chat(prompt)
