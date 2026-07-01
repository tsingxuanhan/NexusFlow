# -*- coding: utf-8 -*-
"""
NexusFlow.crew package

Multi-agent orchestration for materials science research.
"""

__version__ = "0.1.0"

from .agents import MinerAgent, GeneratorAgent, ValidatorAgent, ReporterAgent
from .tasks import (
    literature_mining_task,
    hypothesis_generation_task,
    validation_task,
    report_task,
)
from .crew import ResearchCrew

__all__ = [
    "MinerAgent",
    "GeneratorAgent",
    "ValidatorAgent",
    "ReporterAgent",
    "literature_mining_task",
    "hypothesis_generation_task",
    "validation_task",
    "report_task",
    "ResearchCrew",
]
