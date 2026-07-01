# -*- coding: utf-8 -*-
"""
Domain Profile 模块 — 角色与领域正交设计
v4.0: Agent角色(Planner/Researcher/Executor/Reviewer) × 领域(Materials/AI-ML/General)
"""

from .base import DomainProfile

# 子模块导入DomainProfile（已通过.base导入，不再循环）
from .materials import MaterialsDomain
from .ai_ml import AI_MLDomain
from .general import GeneralDomain

from typing import Dict, Optional, List


# 领域注册表
_DOMAIN_REGISTRY: Dict[str, DomainProfile] = {}


def register_domain(profile: DomainProfile) -> None:
    _DOMAIN_REGISTRY[profile.name] = profile


def get_domain(name: str) -> Optional[DomainProfile]:
    return _DOMAIN_REGISTRY.get(name)


def list_domains() -> List[str]:
    return list(_DOMAIN_REGISTRY.keys())


def get_default_domain() -> DomainProfile:
    return _DOMAIN_REGISTRY.get("general", GeneralDomain)


# 自动注册
register_domain(MaterialsDomain)
register_domain(AI_MLDomain)
register_domain(GeneralDomain)


__all__ = [
    "DomainProfile", "register_domain", "get_domain", 
    "list_domains", "get_default_domain",
    "MaterialsDomain", "AI_MLDomain", "GeneralDomain",
]
