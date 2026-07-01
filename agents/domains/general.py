# -*- coding: utf-8 -*-
"""
通用领域配置 — 无领域偏重的默认配置
"""
from .base import DomainProfile

GeneralDomain = DomainProfile(
    name="general",
    display_name="通用",
    description="通用知识问答与任务执行，不限定特定领域",
    knowledge_dirs=["./knowledge"],
    system_prompt_template="""你是{role}，一个通用型智能体。

## 领域
{domain} — {domain_description}

## 验证规则
{validation_rules}

## 可用工具
{preferred_tools}

{role_description}""",
    validation_rules=[
        "不确定的信息必须标注置信度",
        "事实性声明必须有来源支撑",
        "多步骤任务需要明确追踪进度",
    ],
    preferred_tools=["search", "read_file", "write_file", "calculate", "http_get"],
    keywords=[],
)
