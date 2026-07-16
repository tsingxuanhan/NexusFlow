# -*- coding: utf-8 -*-
"""
quality 模块单元测试
覆盖: QualityDials, AgentMode, MODE_PROFILES, ResearchPreset,
      ReviewAction, ReviewResult, ReviewCommand, PatternAuditCommand,
      StructureAuditCommand, PolishCommand, DistillCommand, BolderCommand,
      ReviewPipeline, 工厂函数
"""
import pytest

from nexusflow.agents.quality import (
    QualityDials,
    AgentMode,
    MODE_PROFILES,
    ResearchPreset,
    RESEARCH_PRESETS,
    get_research_preset,
    ReviewAction,
    ReviewResult,
    ReviewCommand,
    PatternAuditCommand,
    StructureAuditCommand,
    PolishCommand,
    DistillCommand,
    BolderCommand,
    ReviewPipeline,
    create_default_pipeline,
    create_strict_pipeline,
    create_quick_pipeline,
)


# ---------------------------------------------------------------------------
# QualityDials
# ---------------------------------------------------------------------------

def test_quality_dials_defaults():
    qd = QualityDials()
    assert qd.creativity == 0.5
    assert qd.precision == 0.7
    assert qd.verbosity == 0.5
    assert qd.caution == 0.5


def test_quality_dials_custom():
    qd = QualityDials(creativity=0.1, precision=0.9, verbosity=0.2, caution=0.8)
    assert qd.creativity == 0.1
    assert qd.precision == 0.9


def test_quality_dials_validation_error_high():
    with pytest.raises(ValueError):
        QualityDials(creativity=1.5)


def test_quality_dials_validation_error_low():
    with pytest.raises(ValueError):
        QualityDials(precision=-0.1)


def test_quality_dials_to_generation_params():
    qd = QualityDials(creativity=0.5, precision=0.5, verbosity=0.5, caution=0.5)
    params = qd.to_generation_params()
    assert "temperature" in params
    assert "top_p" in params
    assert "max_tokens" in params
    assert 0.3 <= params["temperature"] <= 1.2
    assert 0.7 <= params["top_p"] <= 1.0


def test_quality_dials_to_prompt_suffix_high_creativity():
    qd = QualityDials(creativity=0.9)
    suffix = qd.to_prompt_suffix()
    assert "突破常规" in suffix or "大胆" in suffix


def test_quality_dials_to_prompt_suffix_low_creativity():
    qd = QualityDials(creativity=0.1)
    suffix = qd.to_prompt_suffix()
    assert "严格" in suffix or "模板" in suffix


def test_quality_dials_to_dict():
    qd = QualityDials()
    d = qd.to_dict()
    assert set(d.keys()) == {"creativity", "precision", "verbosity", "caution"}


def test_quality_dials_from_dict():
    d = {"creativity": 0.1, "precision": 0.9, "verbosity": 0.3, "caution": 0.8}
    qd = QualityDials.from_dict(d)
    assert qd.creativity == 0.1
    assert qd.precision == 0.9


def test_quality_dials_to_prompt_suffix_balanced():
    qd = QualityDials()  # all defaults: 0.5
    suffix = qd.to_prompt_suffix()
    # balanced dials should produce empty or minimal suffix
    assert isinstance(suffix, str)


# ---------------------------------------------------------------------------
# AgentMode 枚举
# ---------------------------------------------------------------------------

def test_agent_mode_values():
    assert AgentMode.PRECISE.value == "precise"
    assert AgentMode.CREATIVE.value == "creative"
    assert AgentMode.BALANCED.value == "balanced"
    assert AgentMode.RESEARCH.value == "research"
    assert AgentMode.ENGINEERING.value == "engineering"
    assert AgentMode.CASUAL.value == "casual"


def test_agent_mode_all_profiles_present():
    for mode in AgentMode:
        assert mode in MODE_PROFILES, f"{mode} missing from MODE_PROFILES"


# ---------------------------------------------------------------------------
# ResearchPreset / RESEARCH_PRESETS
# ---------------------------------------------------------------------------

def test_research_presets_keys():
    assert AgentMode.RESEARCH in RESEARCH_PRESETS
    assert AgentMode.ENGINEERING in RESEARCH_PRESETS
    assert AgentMode.CASUAL in RESEARCH_PRESETS


def test_research_preset_research_values():
    preset = RESEARCH_PRESETS[AgentMode.RESEARCH]
    assert preset.model == "pro"
    assert preset.review_pipeline == "strict"
    assert preset.auto_review is True
    assert preset.memory_strategy == "full"
    assert preset.guardrails_level == "strict"


def test_research_preset_casual_values():
    preset = RESEARCH_PRESETS[AgentMode.CASUAL]
    assert preset.model == "flash"
    assert preset.review_pipeline == "quick"
    assert preset.auto_review is False
    assert preset.guardrails_level == "relaxed"


def test_get_research_preset_valid():
    preset = get_research_preset("research")
    assert preset is not None
    assert preset.model == "pro"


def test_get_research_preset_invalid():
    preset = get_research_preset("nonexistent")
    assert preset is None


def test_get_research_preset_non_research_mode():
    # BALANCED is not in RESEARCH_PRESETS
    preset = get_research_preset("balanced")
    assert preset is None


# ---------------------------------------------------------------------------
# ReviewAction 枚举
# ---------------------------------------------------------------------------

def test_review_action_values():
    assert ReviewAction.AUDIT.value == "audit"
    assert ReviewAction.CRITIQUE.value == "critique"
    assert ReviewAction.POLISH.value == "polish"
    assert ReviewAction.DISTILL.value == "distill"
    assert ReviewAction.BOLDER.value == "bolder"
    assert ReviewAction.VERIFY.value == "verify"


# ---------------------------------------------------------------------------
# PatternAuditCommand
# ---------------------------------------------------------------------------

def test_pattern_audit_no_issues():
    cmd = PatternAuditCommand()
    result = cmd.execute("This is a clean output with no issues.")
    assert result.passed is True
    assert result.score == 1.0
    assert result.issues == []


def test_pattern_audit_detects_ai_disclaimer():
    cmd = PatternAuditCommand()
    result = cmd.execute("作为一个AI，我认为这个问题很重要。")
    assert len(result.issues) > 0
    assert result.score < 1.0


def test_pattern_audit_auto_fix():
    cmd = PatternAuditCommand()
    result = cmd.execute("作为一个AI，我来回答。")
    assert result.revised_output is not None
    assert "作为AI" not in result.revised_output or result.revised_output != "作为一个AI，我来回答。"


def test_pattern_audit_detects_intensity_inflation():
    cmd = PatternAuditCommand()
    result = cmd.execute("这是非常重要的、至关重要的结论。")
    assert any("intensity_inflation" in iss for iss in result.issues)


# ---------------------------------------------------------------------------
# StructureAuditCommand
# ---------------------------------------------------------------------------

def test_structure_audit_clean():
    cmd = StructureAuditCommand()
    result = cmd.execute("# Title\n\nSome content here.\n\nMore content.")
    assert result.passed is True
    assert result.score >= 0.7


def test_structure_audit_unclosed_code_block():
    cmd = StructureAuditCommand()
    result = cmd.execute("Here is code:\n```python\nprint('hello')\n")
    assert result.score < 1.0
    assert any("代码块" in iss for iss in result.issues)


def test_structure_audit_header_skip():
    cmd = StructureAuditCommand()
    result = cmd.execute("# Title\n\n### Subtitle\n\nContent.")
    assert any("层级跳跃" in iss for iss in result.issues)


# ---------------------------------------------------------------------------
# PolishCommand
# ---------------------------------------------------------------------------

def test_polish_command_multiple_blank_lines():
    cmd = PolishCommand()
    result = cmd.execute("Para1\n\n\n\nPara2")
    assert result.revised_output is not None
    assert "\n\n\n" not in result.revised_output


def test_polish_command_no_change():
    cmd = PolishCommand()
    result = cmd.execute("Clean output with no issues.")
    assert result.revised_output is None  # no changes


# ---------------------------------------------------------------------------
# DistillCommand
# ---------------------------------------------------------------------------

def test_distill_command_with_removable_lines():
    cmd = DistillCommand(target_ratio=0.6)
    text = "核心内容\n需要注意的是，这很重要。\n总而言之，以上是全部。\n更多内容。"
    result = cmd.execute(text)
    assert result.action == ReviewAction.DISTILL
    assert len(result.issues) > 0  # should find removable lines


def test_distill_command_clean():
    cmd = DistillCommand(target_ratio=0.6)
    result = cmd.execute("Short and concise.")
    assert result.score >= 0.7


# ---------------------------------------------------------------------------
# BolderCommand
# ---------------------------------------------------------------------------

def test_bolder_command_no_hedges():
    cmd = BolderCommand()
    result = cmd.execute("这个方案是最好的选择。")
    assert result.passed is True
    assert result.score == 1.0


def test_bolder_command_with_hedges():
    cmd = BolderCommand()
    result = cmd.execute("也许我们可以尝试一下。")
    assert len(result.issues) > 0
    assert result.score < 1.0


# ---------------------------------------------------------------------------
# ReviewPipeline
# ---------------------------------------------------------------------------

def test_pipeline_add_and_run():
    pipeline = ReviewPipeline("test")
    pipeline.add(PatternAuditCommand())
    pipeline.add(StructureAuditCommand())
    results = pipeline.run("Clean output.")
    assert len(results) == 2
    assert all(isinstance(r, ReviewResult) for r in results)


def test_pipeline_remove_command():
    pipeline = ReviewPipeline("test")
    pipeline.add(PatternAuditCommand())
    pipeline.add(PolishCommand())
    assert len(pipeline.commands) == 2
    pipeline.remove(ReviewAction.POLISH)
    assert len(pipeline.commands) == 1


def test_pipeline_run_with_summary():
    pipeline = create_default_pipeline()
    output, score, issues = pipeline.run_with_summary("Clean output.")
    assert isinstance(score, float)
    assert isinstance(issues, list)
    assert isinstance(output, str)


def test_pipeline_auto_fix():
    pipeline = ReviewPipeline("test")
    pipeline.add(PolishCommand())
    results = pipeline.run("A\n\n\n\nB", auto_fix=True)
    # auto_fix should apply revised output
    assert results[0].revised_output is not None


# ---------------------------------------------------------------------------
# Factory functions
# ---------------------------------------------------------------------------

def test_create_default_pipeline():
    p = create_default_pipeline()
    assert p.name == "default"
    assert len(p.commands) == 3


def test_create_strict_pipeline():
    p = create_strict_pipeline()
    assert p.name == "strict"
    assert len(p.commands) == 5


def test_create_quick_pipeline():
    p = create_quick_pipeline()
    assert p.name == "quick"
    assert len(p.commands) == 2


# ---------------------------------------------------------------------------
# ReviewResult
# ---------------------------------------------------------------------------

def test_review_result_defaults():
    rr = ReviewResult(action=ReviewAction.AUDIT)
    assert rr.passed is True
    assert rr.issues == []
    assert rr.score == 1.0
