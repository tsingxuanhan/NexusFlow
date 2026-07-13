# -*- coding: utf-8 -*-
"""
agent_information_policy 模块单元测试
覆盖: AgentInformationPolicy.get_profile / get_tier,
      should_participate_cdol, can_see_agent_output 可见性规则,
      generate_context_mask 输出结构, InformationProfile 属性,
      AgentTier / InfoSliceType 枚举值。
所有测试脱离 LLM。
"""
import pytest

from agent_information_policy import (
    AgentInformationPolicy,
    InformationProfile,
    AgentTier,
    InfoSliceType,
    AGENT_TIER_MAP,
    AGENT_INFORMATION_PROFILES,
    get_information_policy,
    recommend_cdol_config,
)


# ---------------------------------------------------------------------------
# AgentTier 枚举
# ---------------------------------------------------------------------------

def test_agent_tier_values():
    assert AgentTier.GLOBAL.value == "global"
    assert AgentTier.CDOL_PARTICIPANT.value == "cdol"
    assert AgentTier.OBSERVER.value == "observer"


def test_agent_tier_is_str_enum():
    assert isinstance(AgentTier.GLOBAL, str)
    assert AgentTier.GLOBAL == "global"


# ---------------------------------------------------------------------------
# InfoSliceType 枚举
# ---------------------------------------------------------------------------

def test_info_slice_type_values():
    assert InfoSliceType.RAW_EVIDENCE.value == "raw_evidence"
    assert InfoSliceType.FULL_CONTEXT.value == "full_context"
    assert InfoSliceType.INTERMEDIATE_CONCLUSION.value == "intermediate_conclusion"
    assert InfoSliceType.REASONING_CHAIN.value == "reasoning_chain"


# ---------------------------------------------------------------------------
# AGENT_TIER_MAP 完整性
# ---------------------------------------------------------------------------

def test_agent_tier_map_covers_all_agents():
    expected_agents = {"coordinator", "planner", "researcher", "executor",
                       "reviewer", "miner", "assayer", "caster", "artisan", "archivist"}
    assert set(AGENT_TIER_MAP.keys()) == expected_agents


def test_agent_tier_map_values():
    assert AGENT_TIER_MAP["coordinator"] == AgentTier.GLOBAL
    assert AGENT_TIER_MAP["planner"] == AgentTier.GLOBAL
    assert AGENT_TIER_MAP["researcher"] == AgentTier.CDOL_PARTICIPANT
    assert AGENT_TIER_MAP["archivist"] == AgentTier.OBSERVER


# ---------------------------------------------------------------------------
# AgentInformationPolicy.get_profile
# ---------------------------------------------------------------------------

@pytest.fixture
def policy():
    return AgentInformationPolicy()


def test_get_profile_coordinator(policy):
    profile = policy.get_profile("coordinator")
    assert profile.agent_name == "coordinator"
    assert profile.tier == AgentTier.GLOBAL
    assert InfoSliceType.FULL_CONTEXT in profile.allowed_slices


def test_get_profile_researcher(policy):
    profile = policy.get_profile("researcher")
    assert profile.tier == AgentTier.CDOL_PARTICIPANT
    assert InfoSliceType.RAW_EVIDENCE in profile.allowed_slices
    assert InfoSliceType.LITERATURE_FRAGMENT in profile.allowed_slices


def test_get_profile_archivist(policy):
    profile = policy.get_profile("archivist")
    assert profile.tier == AgentTier.OBSERVER
    assert InfoSliceType.INTERMEDIATE_CONCLUSION in profile.allowed_slices


def test_get_profile_case_insensitive(policy):
    profile = policy.get_profile("COORDINATOR")
    assert profile.agent_name == "coordinator"


def test_get_profile_unknown_raises(policy):
    with pytest.raises(ValueError, match="未知Agent"):
        policy.get_profile("nonexistent_agent")


# ---------------------------------------------------------------------------
# AgentInformationPolicy.get_tier
# ---------------------------------------------------------------------------

def test_get_tier_global(policy):
    assert policy.get_tier("coordinator") == AgentTier.GLOBAL
    assert policy.get_tier("planner") == AgentTier.GLOBAL


def test_get_tier_cdol_participant(policy):
    assert policy.get_tier("researcher") == AgentTier.CDOL_PARTICIPANT
    assert policy.get_tier("executor") == AgentTier.CDOL_PARTICIPANT
    assert policy.get_tier("reviewer") == AgentTier.CDOL_PARTICIPANT
    assert policy.get_tier("miner") == AgentTier.CDOL_PARTICIPANT
    assert policy.get_tier("assayer") == AgentTier.CDOL_PARTICIPANT
    assert policy.get_tier("caster") == AgentTier.CDOL_PARTICIPANT
    assert policy.get_tier("artisan") == AgentTier.CDOL_PARTICIPANT


def test_get_tier_observer(policy):
    assert policy.get_tier("archivist") == AgentTier.OBSERVER


# ---------------------------------------------------------------------------
# should_participate_cdol
# ---------------------------------------------------------------------------

def test_should_participate_cdol_true(policy):
    participants = ["researcher", "executor", "reviewer", "miner",
                    "assayer", "caster", "artisan"]
    for name in participants:
        assert policy.should_participate_cdol(name) is True, f"{name} should participate"


def test_should_participate_cdol_false_global(policy):
    assert policy.should_participate_cdol("coordinator") is False
    assert policy.should_participate_cdol("planner") is False


def test_should_participate_cdol_false_observer(policy):
    assert policy.should_participate_cdol("archivist") is False


# ---------------------------------------------------------------------------
# can_see_agent_output 可见性规则
# ---------------------------------------------------------------------------

def test_coordinator_sees_all_agents(policy):
    for target in ["researcher", "executor", "reviewer", "miner",
                    "assayer", "caster", "artisan", "archivist", "planner"]:
        assert policy.can_see_agent_output("coordinator", target) is True


def test_researcher_sees_only_miner(policy):
    assert policy.can_see_agent_output("researcher", "miner") is True
    assert policy.can_see_agent_output("researcher", "executor") is False
    assert policy.can_see_agent_output("researcher", "reviewer") is False


def test_executor_sees_only_planner(policy):
    assert policy.can_see_agent_output("executor", "planner") is True
    assert policy.can_see_agent_output("executor", "researcher") is False


def test_reviewer_sees_executor_and_caster(policy):
    assert policy.can_see_agent_output("reviewer", "executor") is True
    assert policy.can_see_agent_output("reviewer", "caster") is True
    assert policy.can_see_agent_output("reviewer", "researcher") is False


def test_miner_sees_nobody(policy):
    for target in ["researcher", "executor", "reviewer", "coordinator"]:
        assert policy.can_see_agent_output("miner", target) is False


def test_artisan_sees_nobody(policy):
    assert policy.can_see_agent_output("artisan", "researcher") is False
    assert policy.can_see_agent_output("artisan", "executor") is False


def test_archivist_sees_all_except_self(policy):
    for target in ["planner", "researcher", "executor", "reviewer",
                    "miner", "assayer", "caster", "artisan"]:
        assert policy.can_see_agent_output("archivist", target) is True


# ---------------------------------------------------------------------------
# generate_context_mask 输出结构
# ---------------------------------------------------------------------------

def test_generate_context_mask_global_layer(policy):
    mask = policy.generate_context_mask("coordinator", {"task": "test"})
    assert "allowed_evidence" in mask
    assert "blocked_evidence" in mask
    assert "allowed_domains" in mask
    assert "blocked_domains" in mask
    assert "abstraction_level" in mask
    # 全局视野层不限制
    assert "all" in mask["allowed_evidence"]
    assert mask["blocked_evidence"] == []


def test_generate_context_mask_observer_layer(policy):
    mask = policy.generate_context_mask("archivist", {"task": "test"})
    assert "intermediate_conclusions" in mask["allowed_evidence"]
    assert "raw_evidence" in mask["blocked_evidence"]


def test_generate_context_mask_cdol_participant_researcher(policy):
    mask = policy.generate_context_mask("researcher", {"task": "test"})
    assert isinstance(mask["allowed_evidence"], list)
    assert len(mask["allowed_evidence"]) > 0
    # researcher 有 RAW_EVIDENCE → "data", "measurements" 在 allowed 中
    assert "data" in mask["allowed_evidence"]


def test_generate_context_mask_cdol_participant_executor(policy):
    mask = policy.generate_context_mask("executor", {"task": "test"})
    # executor 只看具体实现
    assert mask["abstraction_level"] == "concrete"
    assert "task_description" in mask["allowed_evidence"]


def test_generate_context_mask_cdol_participant_reviewer(policy):
    mask = policy.generate_context_mask("reviewer", {"task": "test"})
    assert mask["abstraction_level"] == "abstract"
    assert "output" in mask["allowed_evidence"]


def test_generate_context_mask_unknown_agent_raises(policy):
    with pytest.raises(ValueError):
        policy.generate_context_mask("unknown_agent", {})


# ---------------------------------------------------------------------------
# InformationProfile properties
# ---------------------------------------------------------------------------

def test_information_profile_is_cdol_participant():
    p = AGENT_INFORMATION_PROFILES["researcher"]
    assert p.is_cdol_participant is True
    assert p.has_global_vision is False


def test_information_profile_has_global_vision():
    p = AGENT_INFORMATION_PROFILES["coordinator"]
    assert p.has_global_vision is True
    assert p.is_cdol_participant is False


def test_information_profile_observer():
    p = AGENT_INFORMATION_PROFILES["archivist"]
    assert p.is_cdol_participant is False
    assert p.has_global_vision is False


# ---------------------------------------------------------------------------
# get_visible_agents
# ---------------------------------------------------------------------------

def test_get_visible_agents(policy):
    visible = policy.get_visible_agents("researcher")
    assert "miner" in visible
    assert "executor" not in visible


# ---------------------------------------------------------------------------
# get_cdol_participants
# ---------------------------------------------------------------------------

def test_get_cdol_participants_full(policy):
    participants = policy.get_cdol_participants("full_cdol")
    assert len(participants) == 7
    assert "researcher" in participants


def test_get_cdol_participants_evidence_split(policy):
    participants = policy.get_cdol_participants("evidence_split")
    assert participants == ["researcher", "executor"]


def test_get_cdol_participants_unknown_defaults_to_full(policy):
    participants = policy.get_cdol_participants("nonexistent_strategy")
    assert len(participants) == 7  # 降级到 full_cdol


# ---------------------------------------------------------------------------
# get_recommended_participants
# ---------------------------------------------------------------------------

def test_recommended_participants_research(policy):
    rec = policy.get_recommended_participants("文献检索与论文分析")
    assert "miner" in rec
    assert "researcher" in rec


def test_recommended_participants_coding(policy):
    rec = policy.get_recommended_participants("代码开发与实现")
    assert "caster" in rec
    assert "executor" in rec


def test_recommended_participants_verification(policy):
    rec = policy.get_recommended_participants("验证和评估结果")
    assert "reviewer" in rec


def test_recommended_participants_design(policy):
    rec = policy.get_recommended_participants("系统设计与规划")
    assert "planner" in rec


def test_recommended_participants_generic(policy):
    rec = policy.get_recommended_participants("随便做个任务")
    assert "researcher" in rec
    assert "executor" in rec


def test_recommended_participants_max_count(policy):
    rec = policy.get_recommended_participants("文献检索论文", max_count=2)
    assert len(rec) <= 2


# ---------------------------------------------------------------------------
# get_policy_summary
# ---------------------------------------------------------------------------

def test_get_policy_summary(policy):
    summary = policy.get_policy_summary()
    assert "全局视野层" in summary
    assert "CDoL参与层" in summary
    assert "旁观记录层" in summary
    assert "coordinator" in summary
    assert "archivist" in summary


# ---------------------------------------------------------------------------
# 便捷函数
# ---------------------------------------------------------------------------

def test_get_information_policy():
    p = get_information_policy()
    assert isinstance(p, AgentInformationPolicy)


def test_recommend_cdol_config():
    config = recommend_cdol_config("文献检索与分析")
    assert "participants" in config
    assert "strategy" in config
    assert "information_masks" in config
    assert config["strategy"] == "evidence_split"
