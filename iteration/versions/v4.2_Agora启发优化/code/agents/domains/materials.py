# -*- coding: utf-8 -*-
"""
建材领域配置 — v3.3兼容默认领域
"""
from .base import DomainProfile

MaterialsDomain = DomainProfile(
    name="materials",
    display_name="低碳建筑材料",
    description="超硫水泥(SSC)、磷酸镁水泥(MBCMs)、石灰石煅烧粘土水泥(LC3)、纳米改性混凝土、混凝土耐久性",
    knowledge_dirs=["./knowledge/materials"],
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
        "配方建议必须符合热力学可行性",
        "数值数据必须标注来源，无法确认标注'需要查证'",
        "多源验证：每个知识点至少从2个角度验证",
        "发现冲突必须明确标注",
    ],
    preferred_tools=["search", "read_file", "read_pdf", "query_data"],
    keywords=["SSC", "MBCMs", "LC3", "纳米改性", "混凝土耐久性", "低碳水泥", "水化动力学", "固废利用"],
)
