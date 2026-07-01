# -*- coding: utf-8 -*-
"""
研究者 (Researcher) — 检索验证Agent (Flash模型)
XuanHub v4.0 - Generalized Agent Role
"""

from base_agent import BaseAgent, AgentRole, AgentRunMode
from vector_memory import get_vector_memory
from typing import List, Dict, Optional

RESEARCHER_SYSTEM_PROMPT = """你是"研究者"，铉枢项目中的知识获取与验证核心。

## 核心职责
检索信息、挖掘数据、验证事实。你是眼睛和耳朵，负责获取和验证知识。

## 工作原则
1. **多源验证**: 每个关键事实至少从2个独立来源验证
2. **置信度标注**: ✅确认 / ⚠️存疑 / ❌冲突 / 🔍待查
3. **溯源追踪**: 所有信息标注来源（论文/标准/URL）
4. **不编造**: 无法确认的明确标注"需要查证"
5. **时效性**: 标注信息的更新时间

## 输出规范
- 研究报告：结构化Markdown，含来源标注
- 验证报告：条目+结果+依据+建议
- 数据表：统一格式，含单位和置信度"""


class ResearcherAgent(BaseAgent):
    """研究者 - 知识获取与验证核心（Flash模型）"""
    
    def __init__(self, domain_name: str = None, **kwargs):
        super().__init__(
            name="Researcher",
            model="flash",
            system_prompt=RESEARCHER_SYSTEM_PROMPT,
            role=AgentRole.RESEARCHER,
            domain_name=domain_name,
            **kwargs
        )
        self.memory = get_vector_memory()
        
        # A2A能力注册
        if self.a2a:
            self.register_a2a_action("search", self.search_topic)
            self.register_a2a_action("verify", self.verify_claim)
            self.register_a2a_action("batch_verify", self.batch_verify)
            self.register_a2a_action("check_consistency", self.check_consistency)
            self.register_a2a_action("extract", self.extract_knowledge)
            
            self.register_a2a_capability("search", "主题检索", ["检索", "search", "搜索"])
            self.register_a2a_capability("verify", "事实验证", ["验证", "verify"])
            self.register_a2a_capability("batch_verify", "批量验证", ["批量", "batch"])
            self.register_a2a_capability("check_consistency", "一致性检查", ["一致性", "冲突"])
            self.register_a2a_capability("extract", "知识提取", ["提取", "extract", "挖掘"])
    
    def search_topic(self, topic: str, depth: str = "medium") -> str:
        """主题检索"""
        depth_map = {
            "quick": "快速概览，列出核心要点",
            "medium": "中等深度，含关键细节和来源",
            "deep": "深度研究，全面覆盖含争议观点",
        }
        
        prompt = f"""请对以下主题进行{depth_map.get(depth, depth_map["medium"])}：

## 主题
{topic}

要求：
1. 信息按重要性排序
2. 标注每个信息的来源和置信度
3. 识别当前共识和争议点
4. 指出知识空白"""
        return self.chat(prompt)
    
    def verify_claim(self, claim: str, expected_range: str = None) -> str:
        """验证具体说法"""
        range_info = f"\n预期合理范围: {expected_range}" if expected_range else ""
        
        prompt = f"""验证以下说法：

**说法**: {claim}
{range_info}

验证维度：
1. 事实准确性
2. 数值合理性
3. 来源可靠性
4. 逻辑一致性

输出：✅/⚠️/❌ + 依据 + 建议"""
        return self.chat(prompt)
    
    def batch_verify(self, entries: List[Dict]) -> str:
        """批量验证"""
        entries_text = "\n".join([
            f"{i+1}. [{e.get('id', f'ID-{i}')}] {e.get('content', '')}"
            for i, e in enumerate(entries)
        ])
        
        prompt = f"""批量验证以下条目：

{entries_text}

输出：Markdown表格（ID / 结果 / 问题摘要 / 建议）"""
        return self.chat(prompt)
    
    def check_consistency(self, statements: List[str], topic: str) -> str:
        """一致性检查"""
        stmts = "\n".join([f"- {s}" for s in statements])
        prompt = f"""检查关于"{topic}"的陈述一致性：

{stmts}

检查维度：数值、逻辑、结论、前提"""
        return self.chat(prompt)
    
    def extract_knowledge(self, text: str, schema: str = None) -> str:
        """从文本中提取结构化知识"""
        schema_section = f"\n提取格式：{schema}" if schema else "\n提取格式：标题/作者/年份/核心发现/置信度"
        
        prompt = f"""从以下文本中提取结构化知识：

{text}
{schema_section}

要求：
1. 每个知识点独立成条
2. 标注来源和置信度
3. 去除冗余和重复"""
        return self.chat(prompt)
