# -*- coding: utf-8 -*-
"""
档案师 (Archivist) — 记忆蒸馏·经验归档·知识图谱维护
XuanHub v4.0 Phase 6 — Knowledge Crystallization & Memory Management
"""

from base_agent import BaseAgent, AgentRole, AgentRunMode
from vector_memory import get_vector_memory
from typing import List, Dict, Optional
import logging
import json
import time

logger = logging.getLogger("ArchivistAgent")

ARCHIVIST_SYSTEM_PROMPT = """你是"档案师"，铉枢项目中的知识守护者与记忆管理者。

## 核心职责
你是整个Agent团队的"海马体"——负责将零散的执行经验蒸馏为结构化知识，维护长期记忆与知识图谱，确保团队不会重复犯错、不会遗忘关键洞察。

## 工作范围
1. **记忆蒸馏**: 从Agent执行轨迹中提取可复用的经验（Skill Card）
2. **知识归档**: 将验证过的知识分类入库，维护知识图谱
3. **经验索引**: 为历史经验建立高效检索索引
4. **遗忘曲线**: 管理记忆的新鲜度，低价值记忆逐渐降权
5. **知识融合**: 将多个来源的知识合并去重，消除矛盾

## 知识分级
| 等级 | 名称 | 保留策略 | 示例 |
|------|------|----------|------|
| L1 | 核心事实 | 永久保留 | 物理定律、数学定理 |
| L2 | 已验证经验 | 长期保留，定期复核 | 成功的实验方案、验证过的代码模式 |
| L3 | 工作记忆 | 任务结束后蒸馏 | 当前任务的中间结果 |
| L4 | 临时笔记 | 7天后自动清理 | 临时搜索结果、草稿 |

## 蒸馏流程
1. 收集Agent执行轨迹（输入→推理→输出→结果）
2. 评估执行质量（成功/失败/部分成功）
3. 提取关键决策点和转折点
4. 抽象为可复用的Skill Card或经验规则
5. 存入InsightStore并建立索引

## Skill Card格式
```json
{
  "id": "skill_YYYYMMDD_NNN",
  "title": "技能标题",
  "category": "coding|research|analysis|creative|ops",
  "applicable_scenario": "适用场景描述",
  "preconditions": ["前置条件"],
  "steps": ["步骤1", "步骤2", ...],
  "key_insights": ["关键洞察"],
  "pitfalls": ["常见陷阱"],
  "confidence": 0.0-1.0,
  "usage_count": 0,
  "last_used": "ISO timestamp",
  "source_agent": "产生此经验的Agent名称",
  "source_task_id": "来源任务ID"
}
```

## 知识图谱维护规则
1. **新节点入库**: 经验证的新知识点创建为节点
2. **关系建立**: 识别知识点之间的因果、关联、矛盾关系
3. **冲突消解**: 发现矛盾知识时标记并等待人工裁决
4. **衰减机制**: 长期未被引用的知识节点权重递减
5. **聚类分析**: 定期识别知识热点和空白区域

## 输出规范
- 蒸馏报告：包含原始轨迹摘要 + 提取的Skill Card
- 知识图谱更新：新增/修改/删除的节点和边
- 记忆健康报告：各层级记忆数量、命中率、衰减预警"""


class ArchivistAgent(BaseAgent):
    """档案师 - 知识守护者与记忆管理者（Flash模型，Edge层）"""

    def __init__(self, domain_name: str = None, **kwargs):
        super().__init__(
            name="Archivist",
            model="flash",
            system_prompt=ARCHIVIST_SYSTEM_PROMPT,
            role=AgentRole.ARCHIVIST,
            domain_name=domain_name,
            **kwargs
        )
        self.memory = get_vector_memory()

        # 知识图谱（内存态，实际应持久化）
        self._knowledge_nodes = {}
        self._knowledge_edges = []
        self._skill_cards = {}

        # A2A能力注册
        if self.a2a:
            self.register_a2a_action("distill", self.distill_experience)
            self.register_a2a_action("archive", self.archive_knowledge)
            self.register_a2a_action("index", self.build_index)
            self.register_a2a_action("recall", self.recall_experience)
            self.register_a2a_action("graph_update", self.update_knowledge_graph)
            self.register_a2a_action("health_report", self.memory_health_report)

            self.register_a2a_capability("distill", "经验蒸馏", ["蒸馏", "distill", "提炼"])
            self.register_a2a_capability("archive", "知识归档", ["归档", "archive", "存储"])
            self.register_a2a_capability("index", "经验索引", ["索引", "index", "检索"])
            self.register_a2a_capability("recall", "记忆召回", ["回忆", "recall", "记忆"])
            self.register_a2a_capability("graph_update", "知识图谱更新", ["图谱", "graph", "知识更新"])
            self.register_a2a_capability("health_report", "记忆健康报告", ["健康", "health", "报告"])

    def distill_experience(self, task_trace: str, outcome: str,
                           source_agent: str = "unknown", task_id: str = "") -> str:
        """从执行轨迹中蒸馏经验

        Args:
            task_trace: Agent执行轨迹（输入→推理→输出）
            outcome: 执行结果（成功/失败/部分成功）
            source_agent: 产生经验的Agent
            task_id: 任务ID

        Returns:
            蒸馏出的Skill Card或经验规则
        """
        prompt = f"""## 经验蒸馏任务

### 执行轨迹
{task_trace}

### 执行结果: {outcome}
### 来源Agent: {source_agent}
### 任务ID: {task_id}

请完成以下蒸馏工作：

1. **提取关键决策点**: 哪些决策对结果影响最大？
2. **识别成功模式或失败教训**: 什么做法有效？什么做法要避开？
3. **生成Skill Card**:
   - 标题（简洁概括这个经验）
   - 适用场景
   - 前置条件
   - 关键步骤
   - 关键洞察
   - 常见陷阱
   - 置信度评分 (0-1)
4. **关联建议**: 这个经验与哪些已有知识相关？

输出格式：Skill Card (JSON) + 简短说明"""

        result = self.chat(prompt)

        # 保存蒸馏记忆
        self.memory.add(
            f"蒸馏:{source_agent}/{task_id} → {outcome} → {result[:200]}",
            importance=0.8
        )

        return result

    def archive_knowledge(self, knowledge: str, category: str,
                          confidence: float = 0.8, source: str = "") -> str:
        """将知识归档入库

        Args:
            knowledge: 知识内容
            category: 分类（coding/research/analysis/creative/ops/materials/ai_ml）
            confidence: 置信度
            source: 来源

        Returns:
            归档确认
        """
        prompt = f"""## 知识归档

### 待归档知识
{knowledge}

### 分类: {category}
### 置信度: {confidence}
### 来源: {source}

请执行归档操作：
1. 检查是否与已有知识重复或矛盾
2. 确定知识等级（L1核心/L2经验/L3工作/L4临时）
3. 提取关键词用于索引
4. 识别与已有知识节点的关系
5. 输出归档结果（节点ID、分类、标签、关联边）"""

        result = self.chat(prompt)
        self.memory.add(f"归档:{category} → {knowledge[:100]}", importance=0.6)
        return result

    def build_index(self, topic: str = "") -> str:
        """为知识库构建或更新索引

        Args:
            topic: 特定主题（为空则全量索引）

        Returns:
            索引报告
        """
        scope = f"主题: {topic}" if topic else "全量"

        prompt = f"""## 索引构建任务

### 范围: {scope}

请分析当前知识库，输出：
1. 知识节点总数和分类分布
2. 关键词索引（Top 50 高频关键词）
3. 知识空白区域（应该有但没有的领域）
4. 建议补充的关联关系
5. 检索效率评估"""

        return self.chat(prompt)

    def recall_experience(self, query: str, top_k: int = 5) -> str:
        """根据查询召回相关经验

        Args:
            query: 查询描述
            top_k: 返回条数

        Returns:
            相关经验列表
        """
        # 先从向量记忆中检索
        context = self.memory.get_context_for_llm(query, max_tokens=800)

        prompt = f"""## 经验召回

### 查询: {query}
### 返回条数: {top_k}

### 已检索到的记忆上下文
{context or '无直接匹配'}

请：
1. 从记忆中筛选最相关的经验
2. 按相关度和置信度排序
3. 标注每条经验的来源和适用性
4. 如果有矛盾经验，指出分歧点
5. 给出最终建议"""

        return self.chat(prompt)

    def update_knowledge_graph(self, new_nodes: List[Dict] = None,
                                new_edges: List[Dict] = None) -> str:
        """更新知识图谱

        Args:
            new_nodes: 新节点列表 [{"id": "", "label": "", "category": "", "weight": 1.0}]
            new_edges: 新边列表 [{"from": "", "to": "", "relation": "", "weight": 1.0}]

        Returns:
            图谱更新报告
        """
        nodes_text = json.dumps(new_nodes or [], ensure_ascii=False, indent=2)
        edges_text = json.dumps(new_edges or [], ensure_ascii=False, indent=2)

        prompt = f"""## 知识图谱更新

### 新增节点
{nodes_text}

### 新增边
{edges_text}

请执行图谱更新：
1. 检查新节点是否与已有节点重复
2. 验证边的合理性（关系类型是否匹配节点类别）
3. 检测是否有新的隐含关系可以推断
4. 检测是否有矛盾关系需要标记
5. 输出更新摘要（新增/合并/标记冲突的数量）"""

        result = self.chat(prompt)

        # 更新内存态图谱
        if new_nodes:
            for node in new_nodes:
                self._knowledge_nodes[node["id"]] = node
        if new_edges:
            self._knowledge_edges.extend(new_edges)

        return result

    def memory_health_report(self) -> str:
        """生成记忆系统健康报告"""
        prompt = """## 记忆系统健康检查

请生成以下报告：

### 1. 记忆容量统计
- 各层级(L1-L4)记忆条数
- 总记忆量 vs 容量上限
- 新增/衰减/清理速率

### 2. 检索质量
- 命中率趋势
- 常见检索失败模式
- 索引覆盖度

### 3. 知识图谱健康度
- 节点数/边数/连通分量
- 孤立节点比例
- 知识热点与空白区

### 4. 蒸馏效率
- 成功任务→Skill Card转化率
- Skill Card被复用次数分布
- 低质量蒸馏品识别

### 5. 优化建议
- 需要清理的低价值记忆
- 建议补充的知识领域
- 索引优化方向"""

        return self.chat(prompt)
