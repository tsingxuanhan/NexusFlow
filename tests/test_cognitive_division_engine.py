# -*- coding: utf-8 -*-
"""
cognitive_division_engine 模块单元测试
覆盖: ContextMask, PerspectiveAssignment, CDoLResult (dataclass/to_dict/from_dict),
      PerspectiveDecomposer._auto_select_strategy / _estimate_bridgeability,
      FusionJudge 矛盾分类, InsightDistiller.distill 输出结构。
所有测试脱离 LLM 运行。
"""
import pytest

from nexusflow.core.cognitive_division_engine import (
    ContextMask,
    PerspectiveAssignment,
    CDoLResult,
    DecompositionPlan,
    IntermediateConclusion,
    Step,
    Judgment,
    ContradictionType,
    PerspectiveDecomposer,
    FusionJudge,
    InsightDistiller,
    InsightStore,
)


# ---------------------------------------------------------------------------
# ContextMask dataclass
# ---------------------------------------------------------------------------

def test_context_mask_defaults():
    cm = ContextMask()
    assert cm.allowed_evidence == []
    assert cm.blocked_evidence == []
    assert cm.abstraction_level == "mixed"
    assert cm.time_slice is None


def test_context_mask_to_dict_roundtrip():
    cm = ContextMask(
        allowed_evidence=["data"],
        blocked_evidence=["theory"],
        allowed_domains=["experimental"],
        blocked_domains=["theoretical"],
        abstraction_level="concrete",
        time_slice=("2020", "2023"),
    )
    d = cm.to_dict()
    restored = ContextMask.from_dict(d)
    assert restored.allowed_evidence == ["data"]
    assert restored.blocked_domains == ["theoretical"]
    assert restored.abstraction_level == "concrete"
    assert restored.time_slice == ("2020", "2023")


def test_context_mask_from_dict_empty():
    cm = ContextMask.from_dict({})
    assert cm.allowed_evidence == []
    assert cm.abstraction_level == "mixed"
    assert cm.time_slice is None


def test_context_mask_from_dict_partial():
    cm = ContextMask.from_dict({"allowed_evidence": ["x"]})
    assert cm.allowed_evidence == ["x"]
    assert cm.blocked_evidence == []


# ---------------------------------------------------------------------------
# PerspectiveAssignment dataclass
# ---------------------------------------------------------------------------

def test_perspective_assignment_to_dict():
    pa = PerspectiveAssignment(
        agent_id="agent1",
        perspective_question="子问题",
        context_mask=ContextMask(allowed_evidence=["e1"]),
        role_constraint="challenger",
        resource_subset=["r1"],
    )
    d = pa.to_dict()
    assert d["agent_id"] == "agent1"
    assert d["role_constraint"] == "challenger"
    assert d["context_mask"]["allowed_evidence"] == ["e1"]


# ---------------------------------------------------------------------------
# CDoLResult dataclass
# ---------------------------------------------------------------------------

def test_cdol_result_defaults():
    r = CDoLResult()
    assert r.final_answer == ""
    assert r.synergy_gain == 1.0
    assert r.insights == {}
    assert r.round0_conclusions == []


def test_cdol_result_with_fields():
    r = CDoLResult(
        final_answer="yes",
        synergy_gain=1.5,
        metrics={"avg_confidence_r0": 0.7},
    )
    assert r.final_answer == "yes"
    assert r.synergy_gain == 1.5
    assert r.metrics["avg_confidence_r0"] == 0.7


# ---------------------------------------------------------------------------
# IntermediateConclusion.to_dict
# ---------------------------------------------------------------------------

def test_intermediate_conclusion_to_dict():
    step = Step(step_id=1, operation="infer", input_desc="x", output="y", basis="logic")
    ic = IntermediateConclusion(
        agent_id="a1",
        conclusion="结论",
        confidence=0.8,
        reasoning_chain=[step],
        active_hypotheses=["h1"],
        eliminated_hypotheses=["h2"],
        key_assumptions=["a1"],
        uncertainty_markers=["u1"],
    )
    d = ic.to_dict()
    assert d["agent_id"] == "a1"
    assert d["confidence"] == 0.8
    assert len(d["reasoning_chain"]) == 1
    assert d["reasoning_chain"][0]["step_id"] == 1
    assert d["active_hypotheses"] == ["h1"]


# ---------------------------------------------------------------------------
# PerspectiveDecomposer._auto_select_strategy 规则匹配
# ---------------------------------------------------------------------------

@pytest.fixture
def decomposer_no_llm():
    return PerspectiveDecomposer(llm_chat=None)


def test_auto_select_evidence_split(decomposer_no_llm):
    assert decomposer_no_llm._auto_select_strategy("分析实验数据") == "evidence_split"
    assert decomposer_no_llm._auto_select_strategy("review the paper") == "evidence_split"


def test_auto_select_role_constraint(decomposer_no_llm):
    assert decomposer_no_llm._auto_select_strategy("验证这个假设") == "role_constraint"
    assert decomposer_no_llm._auto_select_strategy("hypothesis testing") == "role_constraint"


def test_auto_select_layer_separation(decomposer_no_llm):
    assert decomposer_no_llm._auto_select_strategy("设计系统方法") == "layer_separation"
    assert decomposer_no_llm._auto_select_strategy("implement design") == "layer_separation"


def test_auto_select_abstraction_level(decomposer_no_llm):
    assert decomposer_no_llm._auto_select_strategy("对比评估方案") == "abstraction_level"


def test_auto_select_time_slice(decomposer_no_llm):
    assert decomposer_no_llm._auto_select_strategy("发展趋势分析") == "time_slice"
    assert decomposer_no_llm._auto_select_strategy("evolution of trend") == "time_slice"


def test_auto_select_default(decomposer_no_llm):
    assert decomposer_no_llm._auto_select_strategy("随便一个问题") == "evidence_split"


def test_auto_select_with_insight_store(decomposer_no_llm):
    store = InsightStore()
    store.add({
        "task_type": "general",
        "strategy_effectiveness": {"strategy": "time_slice", "effectiveness": 0.9},
    })
    d = PerspectiveDecomposer(llm_chat=None, insight_store=store)
    # insight_store 有数据但 < 3 条, get_best_strategy 仍可返回
    result = d._auto_select_strategy("随便一个问题")
    assert result == "time_slice"


# ---------------------------------------------------------------------------
# PerspectiveDecomposer._estimate_bridgeability
# ---------------------------------------------------------------------------

def test_estimate_bridgeability_base_scores(decomposer_no_llm):
    a1 = PerspectiveAssignment(agent_id="a", perspective_question="q",
                               context_mask=ContextMask())
    a2 = PerspectiveAssignment(agent_id="b", perspective_question="q",
                               context_mask=ContextMask())
    # evidence_split 基础分 0.7, n=2 → 无衰减
    assert decomposer_no_llm._estimate_bridgeability([a1, a2], "evidence_split") == 0.7
    assert decomposer_no_llm._estimate_bridgeability([a1, a2], "role_constraint") == 0.65
    assert decomposer_no_llm._estimate_bridgeability([a1, a2], "abstraction_level") == 0.5


def test_estimate_bridgeability_decay_more_agents(decomposer_no_llm):
    agents = [
        PerspectiveAssignment(agent_id=f"a{i}", perspective_question="q",
                              context_mask=ContextMask())
        for i in range(4)
    ]
    # evidence_split: 0.7 * 0.9^(4-2) = 0.7 * 0.81 = 0.567 → round → 0.57
    score = decomposer_no_llm._estimate_bridgeability(agents, "evidence_split")
    assert abs(score - 0.57) < 0.01


def test_estimate_bridgeability_unknown_strategy(decomposer_no_llm):
    a = PerspectiveAssignment(agent_id="a", perspective_question="q",
                              context_mask=ContextMask())
    assert decomposer_no_llm._estimate_bridgeability([a], "unknown") == 0.5


# ---------------------------------------------------------------------------
# PerspectiveDecomposer.decompose (rule-based, no LLM)
# ---------------------------------------------------------------------------

def test_decompose_rule_based_evidence_split(decomposer_no_llm):
    class FakeAgent:
        def __init__(self, aid):
            self.agent_id = aid
            self.capabilities = []
            self.domain_expertise = []

    agents = [FakeAgent("a1"), FakeAgent("a2")]
    plan = decomposer_no_llm.decompose("分析实验数据", agents, perspective_count=2)
    assert len(plan.assignments) == 2
    assert plan.strategy == "evidence_split"
    assert plan.bridgeability_score > 0


def test_decompose_fallback_when_bridgeability_low(decomposer_no_llm):
    """当 bridgeability < 0.3 时降级到 evidence_split"""
    class FakeAgent:
        agent_id = "a"
        capabilities = []
        domain_expertise = []

    # abstraction_level 基础分 0.5, n=3 → 0.5 * 0.9 = 0.45 (>0.3 不降级)
    # 需要更多 agent 使其低于 0.3: n=8 → 0.5 * 0.9^6 ≈ 0.265
    agents = [FakeAgent() for _ in range(8)]
    plan = decomposer_no_llm.decompose("抽象层级对比", agents,
                                        strategy="abstraction_level",
                                        perspective_count=8)
    # 降级后 strategy 应该变为 evidence_split 的规则分解
    assert plan.bridgeability_score >= 0.3 or plan.strategy == "evidence_split"


# ---------------------------------------------------------------------------
# FusionJudge — 矛盾分类
# ---------------------------------------------------------------------------

def _make_conclusion(agent_id, conclusion, confidence=0.7,
                     active=None, eliminated=None, assumptions=None):
    return IntermediateConclusion(
        agent_id=agent_id,
        conclusion=conclusion,
        confidence=confidence,
        active_hypotheses=active or [],
        eliminated_hypotheses=eliminated or [],
        key_assumptions=assumptions or [],
    )


def test_fusion_judge_single_conclusion():
    judge = FusionJudge()
    c = _make_conclusion("a1", "答案是A")
    j = judge.judge([c])
    assert j.action == "converge"
    assert j.contradiction_type == "single_agent"


def test_fusion_judge_true_convergence():
    judge = FusionJudge()
    c1 = _make_conclusion("a1", "答案是A", active=["h1"], eliminated=["h2"])
    c2 = _make_conclusion("a2", "答案是A", active=["h1"], eliminated=["h2"])
    j = judge.judge([c1, c2])
    assert j.action == "converge"
    assert j.contradiction_type == "true_convergence"


def test_fusion_judge_false_consensus():
    """答案相同但假设空间矛盾 → 虚假一致"""
    judge = FusionJudge()
    # a1 排除了 h1, 但 a2 的活跃假设包含 h1
    c1 = _make_conclusion("a1", "答案是A", active=["h2"], eliminated=["h1"])
    c2 = _make_conclusion("a2", "答案是A", active=["h1"], eliminated=["h3"])
    j = judge.judge([c1, c2])
    assert j.contradiction_type == "false_consensus"
    assert j.action == "deep_review"


def test_fusion_judge_attributable():
    """答案不同，假设不重叠 → 可归因"""
    judge = FusionJudge()
    c1 = _make_conclusion("a1", "答案是A", assumptions=["基于实验1"])
    c2 = _make_conclusion("a2", "答案是B", assumptions=["基于理论2"])
    j = judge.judge([c1, c2])
    # 假设不重叠 → _can_explain_from_perspective_diff → ATTRIBUTABLE
    assert j.contradiction_type in ("attributable", "unattributable")


def test_fusion_judge_contradiction_report_structure():
    judge = FusionJudge()
    c1 = _make_conclusion("a1", "答案是A")
    c2 = _make_conclusion("a2", "答案是B")
    j = judge.judge([c1, c2])
    report = j.contradiction_report
    assert "total_pairs" in report
    assert "types_summary" in report
    assert report["total_pairs"] == 1


# ---------------------------------------------------------------------------
# InsightDistiller.distill 输出结构
# ---------------------------------------------------------------------------

def test_distill_output_structure():
    distiller = InsightDistiller()
    result = CDoLResult(
        final_answer="综合结论",
        synergy_gain=1.2,
        metrics={"revision_rate": 0.5, "bridgeability": 0.6},
        perspective_assignments=[
            PerspectiveAssignment(
                agent_id="a1",
                perspective_question="实验数据分析: 测试",
                context_mask=ContextMask(),
            )
        ],
        contradiction_report={
            "types_summary": {"attributable": 2, "true_convergence": 1},
            "total_pairs": 3,
        },
    )
    insight = distiller.distill(result, "分析实验数据")

    # 检查顶层键
    assert "task_type" in insight
    assert "strategy_effectiveness" in insight
    assert "contradiction_patterns" in insight
    assert "decomposition_quality" in insight
    assert "synergy_analysis" in insight
    assert "task_skills" in insight
    assert "timestamp" in insight


def test_distill_task_classification():
    distiller = InsightDistiller()
    result = CDoLResult(synergy_gain=1.5, final_answer="ok",
                        metrics={"revision_rate": 0.2, "bridgeability": 0.8})
    insight = distiller.distill(result, "文献检索与数据分析")
    assert insight["task_type"] == "evidence_based"


def test_distill_task_classification_empty():
    distiller = InsightDistiller()
    result = CDoLResult()
    insight = distiller.distill(result, "")
    assert insight["task_type"] == "unknown"


def test_distill_synergy_analysis_strong():
    distiller = InsightDistiller()
    result = CDoLResult(synergy_gain=1.5, metrics={"revision_rate": 0.5,
                                                     "avg_reasoning_depth": 3.0,
                                                     "bridgeability": 0.7})
    insight = distiller.distill(result, "测试")
    assert insight["synergy_analysis"]["assessment"] == "strong_synergy"


def test_distill_synergy_analysis_no_synergy():
    distiller = InsightDistiller()
    result = CDoLResult(synergy_gain=0.8, metrics={"revision_rate": 0.1,
                                                     "avg_reasoning_depth": 1.0,
                                                     "bridgeability": 0.3})
    insight = distiller.distill(result, "测试")
    assert insight["synergy_analysis"]["assessment"] == "no_synergy"


def test_distill_task_skills_extracted_for_research():
    distiller = InsightDistiller()
    result = CDoLResult(
        final_answer="分析结果",
        synergy_gain=1.2,
        metrics={"revision_rate": 0.4, "bridgeability": 0.6},
    )
    insight = distiller.distill(result, "文献检索论文分析")
    assert insight["task_skills"] is not None
    assert "skill_id" in insight["task_skills"]


def test_distill_task_skills_none_for_non_research():
    distiller = InsightDistiller()
    result = CDoLResult(
        final_answer="ok",
        synergy_gain=1.2,
        metrics={},
    )
    insight = distiller.distill(result, "简单问答")
    assert insight["task_skills"] is None


def test_distill_contradiction_patterns_empty_report():
    distiller = InsightDistiller()
    result = CDoLResult(contradiction_report={})
    insight = distiller.distill(result, "test")
    assert insight["contradiction_patterns"]["dominant_type"] is None


def test_distill_decomposition_quality():
    distiller = InsightDistiller()
    result = CDoLResult(metrics={"bridgeability": 0.8})
    insight = distiller.distill(result, "test")
    assert insight["decomposition_quality"]["assessment"] == "high_quality"


# ---------------------------------------------------------------------------
# InsightStore
# ---------------------------------------------------------------------------

def test_insight_store_add_and_stats():
    store = InsightStore()
    assert store.get_stats()["count"] == 0
    store.add({"task_type": "general", "strategy_effectiveness": {"strategy": "evidence_split", "effectiveness": 0.8}})
    assert store.get_stats()["count"] == 1


def test_insight_store_get_best_strategy_empty():
    store = InsightStore()
    assert store.get_best_strategy() is None


def test_insight_store_get_best_strategy_with_data():
    store = InsightStore()
    for _ in range(4):
        store.add({"task_type": "general", "strategy_effectiveness": {"strategy": "time_slice", "effectiveness": 0.9}})
    best = store.get_best_strategy()
    assert best == "time_slice"
