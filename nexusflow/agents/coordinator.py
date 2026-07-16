# -*- coding: utf-8 -*-
"""
编排者 (Coordinator) — 任务调度·Agent仲裁·负载均衡
XuanHub v4.0 Phase 6 — Multi-Agent Orchestration
"""

from nexusflow.agents.base_agent import BaseAgent, AgentRole, AgentRunMode
from nexusflow.memory.vector_memory import get_vector_memory
from typing import List, Dict, Optional
import logging
import time

logger = logging.getLogger("CoordinatorAgent")

COORDINATOR_SYSTEM_PROMPT = """你是"编排者"，铉枢项目中的多Agent协作调度中枢。

## 核心职责
你是整个Agent团队的大脑中枢——决定"谁在什么时候做什么"。你不直接执行任务，而是编排其他Agent协同工作。

## 可调度的Agent池
| Agent | 角色 | 特长 | 运行层 |
|-------|------|------|--------|
| Planner | 规划者 | 策略推理、任务分解 | Cloud |
| Researcher | 研究者 | 信息检索、事实验证 | Edge |
| Executor | 执行者 | 代码生成、工具调用 | Edge |
| Reviewer | 审查者 | 质量审查、问题发现 | Edge |
| Miner | 矿工 | 文献深度挖掘 | Cloud |
| Assayer | 试金 | 知识交叉验证 | Cloud |
| Caster | 铸师 | 代码/脚本生成 | Cloud |
| Artisan | 匠人 | 领域专家问答 | Edge |
| Archivist | 档案师 | 记忆蒸馏、经验归档 | Edge |

## 调度原则
1. **能力匹配**: 任务分配给最擅长的Agent，不做无谓的跨域调度
2. **负载均衡**: 监控各Agent负载，避免单点瓶颈
3. **依赖排序**: 识别任务间依赖关系，关键路径优先
4. **冲突仲裁**: 多Agent意见分歧时，基于证据质量做最终裁决
5. **降级容错**: Agent失败时自动切换备选方案或降级到更简单的策略
6. **成本感知**: 简单任务优先用Edge本地模型，复杂任务才走Cloud

## 编排模式
- **串行流水线**: A→B→C，前一个输出是后一个输入
- **并行扇出**: 多个Agent同时执行独立子任务，最后汇总
- **辩论模式**: 多个Agent对同一问题给出方案，由Reviewer评判
- **迭代精炼**: Agent输出→Reviewer审查→反馈修改→循环直到达标
- **层级委派**: Coordinator→Planner分解→各Agent执行→Reviewer验收

## 调度决策输出格式
```json
{
  "task_id": "任务唯一标识",
  "strategy": "serial|parallel|debate|iterative|hierarchical",
  "assignments": [
    {
      "agent": "Agent名称",
      "subtask": "子任务描述",
      "priority": "high|medium|low",
      "depends_on": ["前置任务ID"],
      "timeout_seconds": 300,
      "fallback_agent": "备选Agent"
    }
  ],
  "merge_strategy": "如何合并多个Agent的输出",
  "quality_gate": "验收标准"
}
```

## 冲突仲裁规则
1. 事实性冲突 → 以Researcher/Assayer的验证结果为准
2. 质量争议 → 以Reviewer的评审为准
3. 策略分歧 → Coordinator综合各Agent论据后裁决
4. 资源冲突 → 优先级高的任务先执行，低优先级排队"""


class CoordinatorAgent(BaseAgent):
    """编排者 - 多Agent协作调度中枢（PRO模型，Cloud层）"""

    def __init__(self, domain_name: str = None, **kwargs):
        super().__init__(
            name="Coordinator",
            model="pro",
            system_prompt=COORDINATOR_SYSTEM_PROMPT,
            role=AgentRole.COORDINATOR,
            domain_name=domain_name,
            **kwargs
        )
        self.memory = get_vector_memory()

        # Agent注册表 — 调度时查询
        self._agent_registry = {}
        self._agent_load = {}  # 简易负载追踪

        # A2A能力注册
        if self.a2a:
            self.register_a2a_action("orchestrate", self.orchestrate)
            self.register_a2a_action("dispatch", self.dispatch_task)
            self.register_a2a_action("arbitrate", self.arbitrate_conflict)
            self.register_a2a_action("rebalance", self.rebalance_load)
            self.register_a2a_action("monitor", self.monitor_agents)

            self.register_a2a_capability("orchestrate", "任务编排与调度", ["编排", "调度", "orchestrate"])
            self.register_a2a_capability("dispatch", "任务分发", ["分发", "dispatch", "分配"])
            self.register_a2a_capability("arbitrate", "冲突仲裁", ["仲裁", "arbitrate", "冲突"])
            self.register_a2a_capability("rebalance", "负载均衡", ["负载", "balance", "rebalance"])
            self.register_a2a_capability("monitor", "Agent状态监控", ["监控", "monitor", "状态"])

    def register_agent(self, agent_name: str, capabilities: List[str],
                       layer: str = "edge", model_tier: str = "flash"):
        """注册Agent到编排池

        Args:
            agent_name: Agent名称
            capabilities: 能力标签列表
            layer: 运行层 edge/cloud
            model_tier: 模型等级 pro/flash
        """
        self._agent_registry[agent_name] = {
            "capabilities": capabilities,
            "layer": layer,
            "model_tier": model_tier,
            "status": "idle",
        }
        self._agent_load[agent_name] = 0

    def orchestrate(self, goal: str, context: str = "", constraints: str = "") -> str:
        """接收高层目标，生成编排方案

        Args:
            goal: 用户的高层目标
            context: 背景信息
            constraints: 约束条件

        Returns:
            编排方案JSON
        """
        # 构建当前Agent池状态
        agent_pool = "\n".join([
            f"- {name}: {info['capabilities']} [{info['layer']}/{info['model_tier']}] 状态:{info['status']} 负载:{self._agent_load.get(name, 0)}"
            for name, info in self._agent_registry.items()
        ])

        ctx = f"\n## 背景\n{context}" if context else ""
        cons = f"\n## 约束\n{constraints}" if constraints else ""

        prompt = f"""## 目标
{goal}
{ctx}{cons}

## 当前可用Agent池
{agent_pool}

## 历史调度经验
{self.memory.get_context_for_llm(goal, max_tokens=500) or '无'}

请制定编排方案：
1. 选择最优编排模式（串行/并行/辩论/迭代/层级）
2. 将目标分解为子任务并分配给合适的Agent
3. 标注依赖关系和优先级
4. 设定质量验收门
5. 预判风险并准备降级方案

输出完整的调度决策（JSON格式）。"""

        result = self.chat(prompt)
        self.memory.add(f"编排:{goal[:80]} → {result[:200]}", importance=0.7)
        return result

    def dispatch_task(self, agent_name: str, task: str, priority: str = "medium") -> str:
        """向指定Agent分发任务

        Args:
            agent_name: 目标Agent
            task: 任务描述
            priority: 优先级

        Returns:
            分发确认
        """
        if agent_name not in self._agent_registry:
            return f"❌ Agent '{agent_name}' 未注册，无法分发"

        self._agent_load[agent_name] = self._agent_load.get(agent_name, 0) + 1
        self._agent_registry[agent_name]["status"] = "busy"

        prompt = f"""接收调度指令：

## 任务
{task}

## 优先级: {priority}
## 调度者: Coordinator

请立即执行此任务并返回结果。"""

        return prompt  # 实际执行时由A2A协议转发

    def arbitrate_conflict(self, agent_a: str, result_a: str,
                           agent_b: str, result_b: str, topic: str) -> str:
        """仲裁两个Agent的输出冲突

        Args:
            agent_a: Agent A 名称
            result_a: Agent A 的输出
            agent_b: Agent B 名称
            result_b: Agent B 的输出
            topic: 争议主题

        Returns:
            仲裁结果
        """
        prompt = f"""## 冲突仲裁

### 争议主题
{topic}

### {agent_a} 的观点
{result_a}

### {agent_b} 的观点
{result_b}

请基于证据质量和逻辑严密性做出裁决：
1. 哪方的论证更可靠？依据是什么？
2. 是否存在双方都没考虑到的盲点？
3. 最终结论是什么？
4. 后续建议"""

        return self.chat(prompt)

    def rebalance_load(self) -> str:
        """检查并重新平衡Agent负载"""
        load_report = "\n".join([
            f"- {name}: 负载={load}, 状态={self._agent_registry[name]['status']}"
            for name, load in self._agent_load.items()
        ])

        prompt = f"""## Agent负载报告
{load_report}

分析当前负载分布：
1. 是否有Agent过载？
2. 是否有Agent闲置？
3. 建议的任务重分配方案"""

        return self.chat(prompt)

    def monitor_agents(self) -> str:
        """生成Agent团队状态报告"""
        status_lines = []
        for name, info in self._agent_registry.items():
            load = self._agent_load.get(name, 0)
            status_lines.append(
                f"| {name} | {info['status']} | {load} | {info['layer']} | {info['model_tier']} |"
            )

        return "\n".join([
            "| Agent | 状态 | 负载 | 运行层 | 模型 |",
            "|-------|------|------|--------|------|",
            *status_lines
        ])
