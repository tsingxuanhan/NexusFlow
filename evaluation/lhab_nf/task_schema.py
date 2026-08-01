"""
LHAB-NF Task Schema Definition
===============================
Defines the structure for benchmark tasks across T1-T3 categories.
"""

from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import List, Dict, Optional, Any
import json
import yaml


class TaskCategory(str, Enum):
    T1_CROSS_DEVICE = "cross_device"       # 跨设备个人生产力
    T2_SOFTWARE_ENG = "software_engineering" # 长程软件工程
    T3_DATA_ANALYSIS = "data_analysis"      # 数据分析与研究


class Difficulty(str, Enum):
    EASY = "easy"
    MEDIUM = "medium"
    HARD = "hard"


class PerturbationType(str, Enum):
    DEVICE_OFFLINE = "device_offline"
    NETWORK_TIMEOUT = "network_timeout"
    TOOL_FAILURE = "tool_failure"
    REQUIREMENT_CHANGE = "requirement_change"
    DATA_CONFLICT = "data_conflict"
    LOW_QUALITY_OUTPUT = "low_quality_output"
    MEMORY_INJECTION = "memory_injection"


class PrivacyLevel(str, Enum):
    PUBLIC = "public"            # 公开数据，可上云
    EDGE_ALLOWED = "edge"        # 可出端，不可上云
    LOCAL_ONLY = "local_only"    # 仅端侧处理


@dataclass
class Step:
    """Single atomic operation in a task."""
    id: str
    description: str
    agent_role: str                    # Which agent should handle this
    input_deps: List[str] = field(default_factory=list)  # Step IDs this depends on
    expected_output_schema: Optional[Dict] = None
    privacy_level: PrivacyLevel = PrivacyLevel.PUBLIC
    device_preference: str = "cloud"   # cloud / edge / terminal
    timeout_seconds: int = 60
    retry_strategy: str = "retry_3"    # retry_3 / fallback / migrate / escalate


@dataclass
class Perturbation:
    """A fault injection event."""
    type: PerturbationType
    trigger_at_step: str               # Step ID where perturbation fires
    target: str                        # Target agent/device/tool
    params: Dict[str, Any] = field(default_factory=dict)
    expected_recovery: str = "auto"    # auto / migrate / rollback / manual


@dataclass
class AcceptanceCriterion:
    """How to verify task completion."""
    name: str
    type: str            # rule / llm_score / test_pass / evidence_chain
    weight: float = 1.0
    threshold: float = 0.7  # Minimum score to pass
    params: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Task:
    """A complete benchmark task."""
    id: str
    category: TaskCategory
    difficulty: Difficulty
    title: str
    description: str
    
    # Structure
    steps: List[Step] = field(default_factory=list)
    
    # Perturbations
    perturbations: List[Perturbation] = field(default_factory=list)
    
    # Validation
    acceptance_criteria: List[AcceptanceCriterion] = field(default_factory=list)
    
    # Constraints
    max_steps: int = 100
    max_rounds: int = 50
    budget_limit_cny: float = 10.0
    privacy_constraints: List[str] = field(default_factory=list)
    
    # Metadata
    version: str = "1.0"
    tags: List[str] = field(default_factory=list)
    
    def to_dict(self) -> dict:
        d = asdict(self)
        # Convert enums to strings
        d["category"] = self.category.value
        d["difficulty"] = self.difficulty.value
        for s in d["steps"]:
            s["privacy_level"] = s["privacy_level"].value if isinstance(s["privacy_level"], PrivacyLevel) else s["privacy_level"]
        for p in d["perturbations"]:
            p["type"] = p["type"].value if isinstance(p["type"], PerturbationType) else p["type"]
        return d
    
    def to_yaml(self) -> str:
        return yaml.dump(self.to_dict(), allow_unicode=True, default_flow_style=False, sort_keys=False)
    
    @classmethod
    def from_dict(cls, data: dict) -> 'Task':
        # Convert string enums back
        data["category"] = TaskCategory(data["category"])
        data["difficulty"] = Difficulty(data["difficulty"])
        
        steps = []
        for s in data.get("steps", []):
            s["privacy_level"] = PrivacyLevel(s.get("privacy_level", "public"))
            steps.append(Step(**s))
        data["steps"] = steps
        
        perturbations = []
        for p in data.get("perturbations", []):
            p["type"] = PerturbationType(p["type"])
            perturbations.append(Perturbation(**p))
        data["perturbations"] = perturbations
        
        criteria = []
        for c in data.get("acceptance_criteria", []):
            criteria.append(AcceptanceCriterion(**c))
        data["acceptance_criteria"] = criteria
        
        return cls(**data)
    
    @classmethod
    def from_yaml(cls, yaml_str: str) -> 'Task':
        data = yaml.safe_load(yaml_str)
        return cls.from_dict(data)
    
    @classmethod
    def from_json_file(cls, path: str) -> 'Task':
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return cls.from_dict(data)


# Example task factory
def create_sample_task() -> Task:
    """Create a sample T1-Medium task for testing."""
    return Task(
        id="T1-M-001",
        category=TaskCategory.T1_CROSS_DEVICE,
        difficulty=Difficulty.MEDIUM,
        title="跨设备日程协调",
        description="从手机收到会议通知，平板读取日程冲突，PC深度分析最优时间，云端检索会议室信息，最终在手机上展示结果。",
        steps=[
            Step(
                id="s1_parse_intent",
                description="解析用户意图：安排会议",
                agent_role="coordinator",
                device_preference="terminal",
                privacy_level=PrivacyLevel.LOCAL_ONLY,
            ),
            Step(
                id="s2_read_calendar",
                description="读取日历数据，检查冲突",
                agent_role="researcher",
                input_deps=["s1_parse_intent"],
                device_preference="edge",
                privacy_level=PrivacyLevel.EDGE_ALLOWED,
            ),
            Step(
                id="s3_analyze_options",
                description="分析最优会议时间",
                agent_role="planner",
                input_deps=["s2_read_calendar"],
                device_preference="cloud",
            ),
            Step(
                id="s4_search_rooms",
                description="检索可用会议室",
                agent_role="executor",
                input_deps=["s3_analyze_options"],
                device_preference="cloud",
            ),
            Step(
                id="s5_review",
                description="审核方案合理性",
                agent_role="reviewer",
                input_deps=["s3_analyze_options", "s4_search_rooms"],
                device_preference="cloud",
            ),
            Step(
                id="s6_format_output",
                description="格式化最终输出",
                agent_role="caster",
                input_deps=["s5_review"],
                device_preference="terminal",
                privacy_level=PrivacyLevel.LOCAL_ONLY,
            ),
        ],
        perturbations=[
            Perturbation(
                type=PerturbationType.DEVICE_OFFLINE,
                trigger_at_step="s3_analyze_options",
                target="edge_device",
                params={"duration_seconds": 30},
                expected_recovery="migrate",
            ),
            Perturbation(
                type=PerturbationType.REQUIREMENT_CHANGE,
                trigger_at_step="s4_search_rooms",
                target="planner",
                params={"new_requirement": "增加视频会议链接"},
                expected_recovery="auto",
            ),
        ],
        acceptance_criteria=[
            AcceptanceCriterion(
                name="output_completeness",
                type="llm_score",
                weight=0.3,
                threshold=0.7,
                params={"dimensions": ["completeness", "accuracy", "format"]},
            ),
            AcceptanceCriterion(
                name="privacy_compliance",
                type="rule",
                weight=0.3,
                threshold=1.0,
                params={"check": "no_private_data_in_cloud"},
            ),
            AcceptanceCriterion(
                name="recovery_success",
                type="rule",
                weight=0.2,
                threshold=1.0,
                params={"check": "all_perturbations_recovered"},
            ),
            AcceptanceCriterion(
                name="time_budget",
                type="rule",
                weight=0.2,
                threshold=1.0,
                params={"max_seconds": 300},
            ),
        ],
        max_steps=80,
        max_rounds=30,
        budget_limit_cny=5.0,
        privacy_constraints=["calendar_data:local_only", "meeting_content:edge_allowed"],
        tags=["cross_device", "calendar", "privacy", "recovery"],
    )


if __name__ == "__main__":
    # Generate sample task
    task = create_sample_task()
    print(task.to_yaml())
