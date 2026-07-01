# -*- coding: utf-8 -*-
"""
AI/ML领域配置
"""
from .base import DomainProfile

AI_MLDomain = DomainProfile(
    name="ai_ml",
    display_name="AI与机器学习",
    description="深度学习、NLP、计算机视觉、强化学习、LLM、Agent框架、RAG、多模态",
    knowledge_dirs=["./knowledge/ai_ml"],
    system_prompt_template="""你是{role}，专注于{domain}领域。

## 领域知识
{domain_description}

## 关键词
{keywords}

## 验证规则
{validation_rules}

## 推荐工具
{preferred_tools}

{role_description}""",
    validation_rules=[
        "模型性能数据必须标注基准和数据集",
        "架构设计必须有论文或开源项目支撑",
        "代码建议必须可直接运行",
        "API调用需注意版本兼容性",
    ],
    preferred_tools=["search", "http_get", "calculate", "read_file", "write_file"],
    keywords=["深度学习", "LLM", "Agent", "RAG", "多模态", "Transformer", "RLHF", "CodeAct", "MCP", "A2A"],
)
