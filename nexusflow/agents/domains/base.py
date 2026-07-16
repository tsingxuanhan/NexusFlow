# -*- coding: utf-8 -*-
"""
DomainProfile 基类 — 与领域和角色正交的可插拔配置
"""
from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class DomainProfile:
    """领域配置 — 与Agent角色正交，可插拔"""
    name: str
    display_name: str
    description: str
    knowledge_dirs: List[str]
    system_prompt_template: str
    validation_rules: List[str] = field(default_factory=list)
    preferred_tools: List[str] = field(default_factory=list)
    keywords: List[str] = field(default_factory=list)
    
    def format_system_prompt(self, role: str, role_description: str) -> str:
        """根据角色+领域生成system prompt"""
        return self.system_prompt_template.format(
            role=role,
            role_description=role_description,
            domain=self.display_name,
            domain_description=self.description,
            keywords=", ".join(self.keywords),
            validation_rules="\n".join(f"- {r}" for r in self.validation_rules),
            preferred_tools=", ".join(self.preferred_tools),
        )
