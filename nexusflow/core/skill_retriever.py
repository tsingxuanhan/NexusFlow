# -*- coding: utf-8 -*-
"""
SkillRetriever — 基于任务描述检索相关Skill Card
借鉴技能卡(Skill Card)范式，为Planner提供决策先验。
"""

import os
import json
import time
import math
import logging
from typing import List, Dict, Optional, Any, Tuple
from dataclasses import dataclass, field

logger = logging.getLogger("SkillRetriever")


@dataclass
class TaskSkillCard:
    """自然语言技能卡（通用科研任务格式）
    
    与MCP工具的区别：
    - MCP工具 = 执行层（精确的原子操作）
    - TaskSkillCard = 决策层（任务级的"该怎么做"指导）
    """
    skill_id: str
    applicable_scenario: str  # 适用场景
    task_description: str  # 任务描述
    execution_steps: List[str]  # 执行步骤（自然语言）
    completion_criteria: List[str]  # 完成标准
    failure_handling: str = ""  # 失败处理建议
    source: str = "unknown"  # 来源：human_recording / auto_extraction
    timestamp: float = 0.0
    model_compatible: bool = True  # 跨模型兼容
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_prompt_fragment(self) -> str:
        """转换为可注入Prompt的文本片段"""
        lines = [
            f"### 参考技能：{self.applicable_scenario}",
            f"**任务**: {self.task_description}",
            "**执行步骤**:",
        ]
        for i, step in enumerate(self.execution_steps, 1):
            lines.append(f"{i}. {step}")
        lines.append("**完成标准**:")
        for c in self.completion_criteria:
            lines.append(f"- {c}")
        if self.failure_handling:
            lines.append(f"**失败处理**: {self.failure_handling}")
        return "\n".join(lines)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "skill_id": self.skill_id,
            "applicable_scenario": self.applicable_scenario,
            "task_description": self.task_description,
            "execution_steps": self.execution_steps,
            "completion_criteria": self.completion_criteria,
            "failure_handling": self.failure_handling,
            "source": self.source,
            "timestamp": self.timestamp,
            "model_compatible": self.model_compatible,
            "metadata": self.metadata,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TaskSkillCard":
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


class SkillGraph:
    """技能图 — 按场景类型组织Skill Card的索引结构
    
    借鉴技能图索引概念，但适配NexusFlow的通用任务场景：
    - 节点 = Skill Card
    - 边 = 技能间的依赖/组合关系
    - 按场景类型分桶，支持快速检索
    """
    
    def __init__(self):
        self.skills: Dict[str, TaskSkillCard] = {}  # skill_id -> TaskSkillCard
        self.scenario_index: Dict[str, List[str]] = {}  # scenario -> [skill_ids]
        self.task_type_index: Dict[str, List[str]] = {}  # task_type -> [skill_ids]
    
    def add_skill(self, skill: TaskSkillCard) -> None:
        """添加技能卡到图中"""
        self.skills[skill.skill_id] = skill
        
        # 更新场景索引
        scenario = skill.applicable_scenario
        self.scenario_index.setdefault(scenario, [])
        if skill.skill_id not in self.scenario_index[scenario]:
            self.scenario_index[scenario].append(skill.skill_id)
        
        # 更新任务类型索引
        for tag in skill.metadata.get("tags", []):
            self.task_type_index.setdefault(tag, [])
            if skill.skill_id not in self.task_type_index[tag]:
                self.task_type_index[tag].append(skill.skill_id)
        
        logger.info(f"[SkillGraph] 添加技能: {skill.skill_id} ({scenario})")
    
    def remove_skill(self, skill_id: str) -> bool:
        """移除技能卡"""
        if skill_id not in self.skills:
            return False
        skill = self.skills.pop(skill_id)
        # 清理索引
        scenario = skill.applicable_scenario
        if scenario in self.scenario_index:
            self.scenario_index[scenario] = [
                s for s in self.scenario_index[scenario] if s != skill_id
            ]
        return True
    
    def get_skills_by_scenario(self, scenario: str) -> List[TaskSkillCard]:
        """按场景检索技能"""
        skill_ids = self.scenario_index.get(scenario, [])
        return [self.skills[sid] for sid in skill_ids if sid in self.skills]
    
    def get_skills_by_tag(self, tag: str) -> List[TaskSkillCard]:
        """按标签检索技能"""
        skill_ids = self.task_type_index.get(tag, [])
        return [self.skills[sid] for sid in skill_ids if sid in self.skills]
    
    def all_skills(self) -> List[TaskSkillCard]:
        return list(self.skills.values())
    
    def stats(self) -> Dict[str, Any]:
        return {
            "total_skills": len(self.skills),
            "scenarios": list(self.scenario_index.keys()),
            "tags": list(self.task_type_index.keys()),
        }


class SkillRetriever:
    """技能检索器 — 根据任务描述检索最相关的Skill Card
    
    为Planner提供"决策先验"：这类任务通常怎么做、有哪些经验可复用。
    检索策略：关键词匹配 + 场景分类 + 时间衰减
    
    与VectorMemory的区别：
    - VectorMemory: 语义相似度检索（基于TF-IDF）
    - SkillRetriever: 任务级技能检索（基于场景+关键词+时效性）
    """
    # 预定义的科研任务场景关键词
    SCENARIO_KEYWORDS = {
        "文献综述/学术检索": ["文献", "论文", "学术", "检索", "搜索", "review", "paper", "literature", "scholar", "arxiv", "pubmed", "citation"],
        "数据分析/实验处理": ["数据", "分析", "实验", "统计", "处理", "data", "analysis", "experiment", "statistic", "process", "结果"],
        "实验设计/方案规划": ["设计", "方案", "规划", "配方", "材料", "design", "experiment", "plan", "formula", "material", "protocol"],
        "代码开发/工程实现": ["代码", "编程", "开发", "实现", "调试", "code", "programming", "develop", "implement", "debug", "函数"],
        "信息检索/知识查询": ["查询", "信息", "知识", "报告", "总结", "query", "information", "knowledge", "report", "summary", "文档"],
        "通用": ["任务", "目标", "完成", "task", "goal", "achieve", "完成", "执行", "操作"],
    }
    
    def __init__(self, skill_graph: Optional[SkillGraph] = None, 
                 insight_store=None, filepath: Optional[str] = None):
        """
        Args:
            skill_graph: 技能图实例。None则创建空图。
            insight_store: InsightStore实例，用于从历史经验中提取技能
            filepath: 持久化文件路径。None则仅内存存储。
        """
        self.graph = skill_graph or SkillGraph()
        self.insight_store = insight_store
        self.filepath = filepath
        
        if filepath:
            self._load()
        
        # 从InsightStore同步已有技能
        if self.insight_store:
            self._sync_from_insights()
        
        # Nemotron 语义检索（延迟启用）
        self._nemotron_provider = None
        self._skill_embeddings: Dict[str, List[float]] = {}  # skill_name -> embedding
    
    def enable_semantic_search(self, embedding_provider) -> None:
        """
        启用语义检索
        
        Args:
            embedding_provider: NemotronEmbeddingProvider 实例
        
        启用后，retrieve() 将融合规则匹配和语义匹配的结果
        """
        self._nemotron_provider = embedding_provider
        # 预计算所有 Skill Card 的语义向量
        for skill in self.graph.all_skills():
            tags = ' '.join(skill.metadata.get('tags', []))
            text = f"{skill.skill_id} {skill.applicable_scenario} {skill.task_description} {tags}"
            self._skill_embeddings[skill.skill_id] = embedding_provider.embed_document(text)
        logger.info(
            f"[SkillRetriever] Semantic search enabled, "
            f"embedded {len(self._skill_embeddings)} skills"
        )

    def retrieve(self, task_description: str, top_k: int = 3) -> List[TaskSkillCard]:
        """检索与任务最相关的Skill Card
        
        Args:
            task_description: 任务描述
            top_k: 返回最相关的k个技能
            
        Returns:
            按相关性排序的TaskSkillCard列表
        """
        if not self.graph.skills:
            return []
        
        # 1. 确定任务场景
        scenario = self._classify_scenario(task_description)
        
        # 2. 从场景索引和全局索引中收集候选
        candidates = []
        
        # 优先场景匹配
        scenario_skills = self.graph.get_skills_by_scenario(scenario)
        candidates.extend([(s, 1.0) for s in scenario_skills])
        
        # 补充关键词匹配
        desc_lower = task_description.lower()
        for skill in self.graph.all_skills():
            if skill not in [c[0] for c in candidates]:
                score = self._compute_relevance(skill, desc_lower)
                if score > 0.1:
                    candidates.append((skill, score))
        
        # 3. 按相关性排序，应用时间衰减
        now = time.time()
        scored = []
        for skill, relevance in candidates:
            age_days = (now - skill.timestamp) / 86400 if skill.timestamp else 0
            decay = 0.95 ** age_days  # 每天衰减5%
            final_score = relevance * decay
            scored.append((skill, final_score))
        
        # 4. 语义检索融合（如果启用）
        if self._nemotron_provider and self._skill_embeddings:
            query_vec = self._nemotron_provider.embed_query(task_description)
            semantic_scores = {}
            for sid, skill_vec in self._skill_embeddings.items():
                dot = sum(a * b for a, b in zip(query_vec, skill_vec))
                na = sum(a * a for a in query_vec) ** 0.5
                nb = sum(b * b for b in skill_vec) ** 0.5
                sim = dot / (na * nb) if na > 0 and nb > 0 else 0.0
                semantic_scores[sid] = sim
            
            # RRF 融合规则匹配和语义匹配
            rule_ranked = sorted(scored, key=lambda x: -x[1])
            rule_id_to_skill = {s.skill_id: (s, sc) for s, sc in rule_ranked}
            
            sem_ranked = sorted(semantic_scores.items(), key=lambda x: -x[1])
            
            rrf_scores: Dict[str, float] = {}
            k = 60
            for rank, (skill, _) in enumerate(rule_ranked):
                rrf_scores[skill.skill_id] = rrf_scores.get(skill.skill_id, 0) + 1.0 / (k + rank + 1)
            for rank, (sid, _) in enumerate(sem_ranked):
                rrf_scores[sid] = rrf_scores.get(sid, 0) + 1.0 / (k + rank + 1)
            
            fused_sorted = sorted(rrf_scores.items(), key=lambda x: -x[1])
            result = []
            for sid, _ in fused_sorted:
                if sid in rule_id_to_skill:
                    result.append(rule_id_to_skill[sid][0])
                elif sid in self.graph.skills:
                    result.append(self.graph.skills[sid])
                if len(result) >= top_k:
                    break
            return result
        
        scored.sort(key=lambda x: -x[1])
        return [s for s, _ in scored[:top_k]]
    
    def retrieve_as_prompt(self, task_description: str, top_k: int = 3) -> str:
        """检索技能并格式化为Prompt片段，可直接注入Planner
        
        Returns:
            格式化的技能文本，无匹配时返回空字符串
        """
        skills = self.retrieve(task_description, top_k)
        if not skills:
            return ""
        
        lines = ["[参考技能 — 以下经验可能有助于任务规划]"]
        for skill in skills:
            lines.append(skill.to_prompt_fragment())
            lines.append("")  # 空行分隔
        
        return "\n".join(lines)
    
    def add_skill(self, skill: TaskSkillCard) -> None:
        """添加技能卡"""
        self.graph.add_skill(skill)
        if self.filepath:
            self._save()
    
    def add_skill_from_insight(self, insight: Dict[str, Any]) -> Optional[str]:
        """从InsightDistiller的输出中提取技能卡并添加
        
        Returns:
            添加的skill_id，无任务技能时返回None
        """
        task_skill = insight.get("task_skills")
        if not task_skill:
            return None
        
        skill = TaskSkillCard(
            skill_id=task_skill.get("skill_id", f"skill_{int(time.time())}"),
            applicable_scenario=task_skill.get("applicable_scenario", "通用任务"),
            task_description=task_skill.get("task_description", ""),
            execution_steps=task_skill.get("execution_steps", []),
            completion_criteria=task_skill.get("completion_criteria", []),
            failure_handling=task_skill.get("failure_handling", ""),
            source=task_skill.get("source", "auto_extraction"),
            timestamp=task_skill.get("timestamp", time.time()),
            model_compatible=task_skill.get("model_compatible", True),
        )
        self.add_skill(skill)
        return skill.skill_id
    
    def _classify_scenario(self, task_desc: str) -> str:
        """将任务描述分类到预定义场景"""
        desc_lower = task_desc.lower()
        best_scenario, best_count = "通用网页导航", 0
        
        for scenario, keywords in self.SCENARIO_KEYWORDS.items():
            count = sum(1 for kw in keywords if kw in desc_lower)
            if count > best_count:
                best_count = count
                best_scenario = scenario
        
        return best_scenario
    
    def _compute_relevance(self, skill: TaskSkillCard, desc_lower: str) -> float:
        """计算技能与任务描述的相关性分数"""
        score = 0.0
        
        # 场景匹配
        if skill.applicable_scenario.lower() in desc_lower:
            score += 0.5
        
        # 任务描述关键词重叠
        skill_words = set(skill.task_description.lower().split())
        task_words = set(desc_lower.split())
        overlap = len(skill_words & task_words)
        if skill_words:
            score += 0.3 * (overlap / len(skill_words))
        
        # 执行步骤关键词匹配
        for step in skill.execution_steps:
            step_lower = step.lower()
            if any(kw in step_lower for kw in desc_lower.split() if len(kw) > 2):
                score += 0.1
        
        return min(1.0, score)
    
    def _sync_from_insights(self) -> int:
        """从InsightStore同步已有任务技能"""
        if not self.insight_store:
            return 0
        
        count = 0
        for insight in self.insight_store.insights:
            if insight.get("task_skills"):
                self.add_skill_from_insight(insight)
                count += 1
        
        if count > 0:
            logger.info(f"[SkillRetriever] 从InsightStore同步了{count}个任务技能")
        return count
    
    def _load(self) -> None:
        """从JSON文件加载技能图"""
        try:
            with open(self.filepath, "r", encoding="utf-8") as f:
                data = json.load(f)
            for skill_data in data.get("skills", []):
                skill = TaskSkillCard.from_dict(skill_data)
                self.graph.add_skill(skill)
            logger.info(f"[SkillRetriever] 加载了{len(self.graph.skills)}个技能")
        except (FileNotFoundError, json.JSONDecodeError):
            pass
    
    def _save(self) -> None:
        """保存技能图到JSON文件"""
        try:
            data = {
                "skills": [s.to_dict() for s in self.graph.all_skills()],
                "stats": self.graph.stats(),
                "updated_at": time.time(),
            }
            with open(self.filepath, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except OSError as e:
            logger.warning(f"[SkillRetriever] 保存失败: {e}")
    
    def stats(self) -> Dict[str, Any]:
        """获取检索器统计信息"""
        return {
            "graph_stats": self.graph.stats(),
            "has_insight_store": self.insight_store is not None,
            "persistent": self.filepath is not None,
        }
