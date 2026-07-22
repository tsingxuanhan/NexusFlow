# -*- coding: utf-8 -*-
"""
NexusFlow Orchestrator Runner — NF 完整管线模式

通过 NexusOrchestrator + CDoL 多 Agent 协作执行 PinchBench 任务。
与 SA 模式（单 Agent 基线）形成对比，体现框架的多 Agent 协作优势。

核心流程:
1. 根据任务 category 选择 Agent 子集
2. 创建 BaseAgent 实例（使用真实模型名 deepseek-chat / deepseek-reasoner）
3. 构建 NexusOrchestrator(agents=agent_dict)
4. 调用 orchestrator.execute(prompt, force_route="cdol")
5. 从 result.result 提取 final_answer
6. 写入文件 & 返回 AgentRunResult
"""

from __future__ import annotations

import json
import logging
import os
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

# 确保 nexusflow 包可导入
_NEXUSFLOW_ROOT = str(Path(__file__).resolve().parent.parent.parent.parent)
if _NEXUSFLOW_ROOT not in sys.path:
    sys.path.insert(0, _NEXUSFLOW_ROOT)

from .config import (
    DEEPSEEK_API_KEY,
    DEEPSEEK_ENDPOINT,
    NEXUSFLOW_REPO_ROOT,
)
from .task_parser import PinchBenchTask
from .nf_agent_runner import AgentRunResult, build_user_prompt, _extract_expected_output_files
from .grade_bridge import build_transcript

logger = logging.getLogger("pinchbench.nf_orchestrator_runner")


# ============================================================================
# Agent 子集映射 — 按任务 category 选择合适的 Agent 组合
# ============================================================================

# 任务 category → Agent 名称列表
NF_AGENT_SELECTION: dict[str, list[str]] = {
    # 研究类: miner(PRO) + researcher(FLASH) + assayer(FLASH)
    "research": ["miner", "researcher", "assayer"],
    # 编码类: caster(PRO) + executor(FLASH) + reviewer(FLASH)
    "coding": ["caster", "executor", "reviewer"],
    # CDoL 通用: researcher + executor + reviewer
    "cdol_general": ["researcher", "executor", "reviewer"],
    # CSV/数据分析: executor + researcher + reviewer
    "csv_analysis": ["executor", "researcher", "reviewer"],
    # 日志分析: executor + researcher
    "log_analysis": ["executor", "researcher"],
    # 会议分析: researcher + coordinator
    "meeting_analysis": ["researcher", "coordinator"],
    # 分析类: researcher + reviewer
    "analysis": ["researcher", "reviewer"],
    # 生产力: researcher + coordinator
    "productivity": ["researcher", "coordinator"],
    # 写作类: researcher + reviewer
    "writing": ["researcher", "reviewer"],
}

# Agent 名称 → Cloud 模型映射
CLOUD_MODEL_MAP = {
    "miner": "deepseek-reasoner",      # PRO
    "planner": "deepseek-reasoner",    # PRO
    "caster": "deepseek-reasoner",     # PRO
    "coordinator": "deepseek-reasoner", # PRO
    "researcher": "deepseek-chat",     # FLASH
    "executor": "deepseek-chat",       # FLASH
    "reviewer": "deepseek-chat",       # FLASH
    "assayer": "deepseek-chat",        # FLASH
    "artisan": "deepseek-chat",        # FLASH
    "archivist": "deepseek-chat",      # FLASH
}

# 任务路由映射
CATEGORY_ROUTE_MAP: dict[str, str] = {
    "research": "cdol",
    "coding": "coding",
    "csv_analysis": "cdol",
    "log_analysis": "cdol",
    "meeting_analysis": "cdol",
    "analysis": "cdol",
    "productivity": "cdol",
    "writing": "cdol",
}


# ============================================================================
# Agent 创建
# ============================================================================

def _create_agent_for_nf(agent_name: str) -> Any:
    """创建用于 NF 模式的 BaseAgent 实例。

    使用 CLOUD_MODEL_MAP 中的真实模型名（deepseek-chat / deepseek-reasoner），
    而非抽象的 "flash"/"pro"。

    Args:
        agent_name: Agent 名称

    Returns:
        BaseAgent 实例
    """
    from nexusflow.agents.base_agent import BaseAgent
    from nexusflow.agents.agent_registry import AGENT_REGISTRY

    spec = AGENT_REGISTRY.get(agent_name)
    if not spec:
        raise ValueError(f"未知 Agent: {agent_name}，可用: {list(AGENT_REGISTRY.keys())}")

    model = CLOUD_MODEL_MAP.get(agent_name, "deepseek-chat")
    system_prompt = spec.system_prompt

    agent = BaseAgent(
        name=agent_name,
        model=model,
        system_prompt=system_prompt,
        api_key=DEEPSEEK_API_KEY,
        endpoint=DEEPSEEK_ENDPOINT,
        enable_checkpoint=False,
        enable_compactor=True,
    )

    # PinchBench 任务需要处理大输入，禁用 guardrails 避免误拦截
    agent.guardrails = None

    logger.info("NF Agent 已创建: %s (model=%s)", agent_name, model)
    return agent


def _select_agents_for_task(task: PinchBenchTask) -> list[str]:
    """根据任务 category 选择合适的 Agent 子集。

    Args:
        task: PinchBench 任务对象

    Returns:
        Agent 名称列表
    """
    category = task.category.lower().replace(" ", "_")
    agents = NF_AGENT_SELECTION.get(category, NF_AGENT_SELECTION["cdol_general"])
    return agents


def _get_route_for_task(task: PinchBenchTask) -> str:
    """根据任务 category 确定路由类型。

    Args:
        task: PinchBench 任务对象

    Returns:
        路由类型字符串 ("cdol" / "coding")
    """
    category = task.category.lower().replace(" ", "_")
    return CATEGORY_ROUTE_MAP.get(category, "cdol")


# ============================================================================
# NFOrchestratorRunner
# ============================================================================

class NFOrchestratorRunner:
    """NexusFlow 完整管线执行器

    通过 NexusOrchestrator + CDoL 多 Agent 协作执行 PinchBench 任务。
    每个任务创建独立的 Agent 实例，避免跨任务上下文污染。
    """

    def __init__(self, api_key: str | None = None, endpoint: str | None = None) -> None:
        self.api_key = api_key or DEEPSEEK_API_KEY
        self.endpoint = endpoint or DEEPSEEK_ENDPOINT

    def run_task(
        self,
        task: PinchBenchTask,
        workspace_path: Path,
    ) -> AgentRunResult:
        """执行单个 PinchBench 任务（NF 完整管线模式）。

        流程:
        1. 选择 Agent 子集
        2. 创建 BaseAgent 实例
        3. 创建 NexusOrchestrator
        4. 构造 prompt
        5. 调用 orchestrator.execute()
        6. 提取 final_answer
        7. 写入文件
        8. 返回 AgentRunResult

        Args:
            task: 已解析的任务对象
            workspace_path: 工作区路径

        Returns:
            AgentRunResult
        """
        start = time.time()
        result = AgentRunResult(task_id=task.id)

        # 0. 多 Session 任务处理策略
        #    - 编码类多Session任务：保留 CDoL（CDoL 能看到全部 session 并协作生成代码）
        #    - 非编码类多Session任务：降级为 SA 模式（CDoL 无法处理结构化 sequential JSON 输出）
        if task.multi_session and task.sessions:
            cat = task.category.lower().replace(" ", "_")
            if cat not in ("coding",):
                logger.info("任务 %s 为非编码类多Session任务(category=%s)，降级为 SA 模式", task.id, cat)
                from .nf_agent_runner import NFAgentRunner
                sa_runner = NFAgentRunner(api_key=self.api_key, endpoint=self.endpoint)
                sa_result = sa_runner.run_task(task, workspace_path)
                sa_result.agent_used = f"nf_sa_mode({sa_result.agent_used})"
                return sa_result
            else:
                logger.info("任务 %s 为编码类多Session任务，保留 CDoL 模式", task.id)

        # 1. 选择 Agent 子集
        agent_names = _select_agents_for_task(task)
        result.agent_used = "+".join(agent_names)
        logger.info("任务 %s 选择 Agent: %s", task.id, agent_names)

        # 2. 创建 BaseAgent 实例
        agent_dict: dict[str, Any] = {}
        try:
            for name in agent_names:
                agent_dict[name] = _create_agent_for_nf(name)
            logger.info("已创建 %d 个 Agent 实例", len(agent_dict))
        except Exception as exc:
            result.status = "failed"
            result.error = f"Agent 创建失败: {exc}"
            result.duration_seconds = time.time() - start
            return result

        # 3. 创建 NexusOrchestrator
        try:
            from nexusflow.core.nexus_orchestrator import NexusOrchestrator, TaskRoute
            orchestrator = NexusOrchestrator(agents=agent_dict)
            logger.info("NexusOrchestrator 已创建")
        except Exception as exc:
            result.status = "failed"
            result.error = f"NexusOrchestrator 创建失败: {exc}"
            result.duration_seconds = time.time() - start
            return result

        # 4. 构造 prompt
        user_prompt = build_user_prompt(task, workspace_path)

        # 5. 调用 orchestrator.execute()
        route = _get_route_for_task(task)
        try:
            if route == "coding":
                force_route = TaskRoute.CODING
            else:
                force_route = TaskRoute.CDOL

            logger.info("执行 orchestrator.execute (force_route=%s)", force_route)

            orch_result = orchestrator.execute(
                user_prompt,
                force_route=force_route,
                max_agents=len(agent_names),
            )

            # 6. 提取 CDoL 分析结果
            cdol_analysis = self._extract_cdol_full_context(orch_result)
            result.status = "completed"

            logger.info(
                "任务 %s CDoL 分析完成: mode=%s, participants=%s, analysis_len=%d",
                task.id,
                orch_result.route if hasattr(orch_result, 'route') else 'unknown',
                orch_result.participants if hasattr(orch_result, 'participants') else [],
                len(cdol_analysis),
            )

        except Exception as exc:
            result.status = "failed"
            result.error = f"Orchestrator 执行失败: {exc}"
            logger.error("任务 %s 执行失败: %s", task.id, exc)
            result.duration_seconds = time.time() - start
            return result

        # 7. 用 Producer Agent 把 CDoL 分析结果合成完整交付物
        #    关键修复：Producer 必须能读取工作区输入文件（和 SA 一样的 prompt），
        #    同时附加 CDoL 多Agent分析作为额外上下文，避免幻觉输出。
        try:
            producer = _create_agent_for_nf(self._select_producer_agent(task))
            producer.guardrails = None

            # 使用与 SA 相同的 build_user_prompt（包含工作区文件内容）
            # 然后附加 CDoL 分析结论作为团队协作的额外上下文
            base_prompt = build_user_prompt(task, workspace_path)

            # 截断过长的 CDoL 分析，避免超出上下文窗口
            max_cdol_len = 4000
            cdol_context = cdol_analysis
            if len(cdol_context) > max_cdol_len:
                cdol_context = cdol_context[:max_cdol_len] + "\n...(分析内容已截断)"

            synthesis_prompt = base_prompt + "\n\n## 多Agent协作分析参考\n"
            synthesis_prompt += "以下是你的团队通过多Agent协作（CDoL协议）得到的分析结论，可作为你生成交付物的参考：\n\n"
            synthesis_prompt += cdol_context
            synthesis_prompt += "\n\n请基于工作区文件和以上分析，生成完整的任务交付物。"

            final_output = producer.chat(synthesis_prompt)
            result.response = final_output
            logger.info("任务 %s Producer 合成完成: output_len=%d", task.id, len(final_output))
        except Exception as exc:
            logger.warning("Producer 合成失败: %s, 降级使用 CDoL final_answer", exc)
            result.response = cdol_analysis
            result.status = "completed"

        # 8. 从响应中提取文件内容并写入工作区
        result.workspace_files_written = self._extract_and_write_files(
            task, workspace_path, result.response
        )

        # 9. 构建 transcript（包含多 Agent 对话记录）
        transcript_parts = self._build_nf_transcript(orch_result, result.response)
        result.transcript = build_transcript(
            result.response,
            result.workspace_files_written,
        )
        # 增强 transcript，加入多 Agent 信息
        if hasattr(orch_result, 'participants') and orch_result.participants:
            result.transcript.insert(0, {
                "type": "system",
                "message": {
                    "role": "system",
                    "content": f"NF 模式: 参与 Agent = {orch_result.participants}, route = {orch_result.route}"
                }
            })

        result.duration_seconds = time.time() - start
        return result

    def _extract_cdol_full_context(self, orch_result: Any) -> str:
        """从 CDoL 结果中提取完整分析上下文（不只是 final_answer）。

        提取所有轮次的中间结论、矛盾报告、推理树等，
        作为 Producer Agent 合成完整交付物的输入。

        Returns:
            完整的 CDoL 分析上下文文本
        """
        result_data = orch_result.result if hasattr(orch_result, 'result') else None
        if not result_data or not isinstance(result_data, dict):
            return self._extract_final_answer(orch_result)

        cdol_data = result_data.get("cdol_result", {})
        if not cdol_data:
            return str(result_data)

        parts = []

        # 1. Final answer from FusionJudge
        final_answer = cdol_data.get("final_answer", "")
        if final_answer:
            parts.append(f"## FusionJudge 融合结论\n{final_answer}")

        # 2. Metrics
        metrics = cdol_data.get("metrics", {})
        if metrics:
            parts.append(f"## CDoL 分析指标\n```json\n{json.dumps(metrics, ensure_ascii=False, indent=2)}\n```")

        # 3. Policy summary
        policy = cdol_data.get("policy_summary", "")
        if policy:
            parts.append(f"## 信息策略摘要\n{policy}")

        # 4. Participants info
        participants = result_data.get("participants", [])
        if participants:
            parts.append(f"## 参与分析的多Agent视角\n视角: {', '.join(participants)}")

        # 5. If we have round history from the CDoL engine, include it
        # (This might be in the orch_result if available)
        if hasattr(orch_result, 'cdol_engine') and hasattr(orch_result.cdol_engine, 'comm_layer'):
            comm = orch_result.cdol_engine.comm_layer
            if hasattr(comm, 'round_history'):
                for rh in comm.round_history:
                    round_num = rh.get('round', '?')
                    conclusions = rh.get('conclusions', [])
                    for c in conclusions:
                        agent_id = c.get('agent_id', 'unknown')
                        conclusion = c.get('conclusion', '')
                        if conclusion:
                            parts.append(f"### Round {round_num} - {agent_id} 的结论\n{conclusion}")

        # 6. The original task for reference
        task_text = result_data.get("task", "")
        if task_text and len(task_text) < 5000:
            parts.insert(0, f"## 原始任务\n{task_text}")

        full_context = "\n\n".join(parts) if parts else final_answer
        logger.info("CDoL 完整上下文提取: %d 部分, %d 字符", len(parts), len(full_context))
        return full_context

    def _select_producer_agent(self, task: PinchBenchTask) -> str:
        """根据任务类型选择最合适的 Producer Agent。

        Producer Agent 负责把 CDoL 分析结果合成为完整交付物。
        """
        cat = task.category.lower().replace(" ", "_")
        if cat in ("coding", "test_generation", "iterative_code_refine"):
            return "caster"  # PRO model for code generation
        elif cat in ("csv_analysis", "log_analysis", "spreadsheet"):
            return "executor"  # FLASH for data processing
        else:
            return "researcher"  # FLASH for report generation

    def _build_synthesis_prompt(self, task: PinchBenchTask, cdol_analysis: str, workspace_path: Path) -> str:
        """构建合成提示词：将 CDoL 分析结果 + 原始任务要求 → 完整交付物。

        这是 NF 管线的关键步骤：把多Agent协作的分析结论转化为符合评分要求的输出文件。
        """
        # 解析期望输出文件
        expected_files = _extract_expected_output_files(task)
        file_list = ", ".join(expected_files) if expected_files else "对应的输出文件"

        prompt = f"""你是一个专业的任务交付物生成器。你的团队已经通过多Agent协作完成了深度分析。

## 原始任务
{task.prompt}

## 团队多Agent分析结果
以下是你的团队从多个视角协作分析得到的完整结论：

{cdol_analysis}

## 你的任务
基于以上分析结果，生成完整的任务交付物。

### 要求：
1. **不要**输出简短摘要——你需要生成**完整的、详细的**交付物内容
2. 充分利用分析结果中的所有发现、数据、代码片段和结论
3. 输出格式必须严格符合任务要求

### 输出文件格式要求：
你需要生成以下文件: {file_list}

请用以下格式输出每个文件：
```
### 文件名.ext
（文件完整内容）
```

如果是代码文件，用对应的语言代码块：
```
### filename.yaml
（YAML完整内容）
```

**重要**：
- 每个文件必须包含完整内容，不要省略或用"..."代替
- 代码文件必须可直接运行/使用
- 报告文件必须包含完整的分析、发现和建议
- 基于团队分析中的具体数据和发现，不要编造数据
"""
        return prompt

    def _extract_final_answer(self, orch_result: Any) -> str:
        """从 NexusOrchestrator 执行结果中提取 final_answer。

        支持两种模式:
        - CDoL 模式: result.result["cdol_result"]["final_answer"]
        - Simple 模式: result.result.get("instruction", "")（降级）

        Args:
            orch_result: NexusOrchestrator.execute() 返回的 TaskResult

        Returns:
            final_answer 字符串
        """
        if orch_result.status == "failed":
            return f"[ERROR] {orch_result.error}"

        result_data = orch_result.result
        if not result_data:
            return ""

        if isinstance(result_data, dict):
            mode = result_data.get("mode", "")

            if mode == "cdol":
                cdol_data = result_data.get("cdol_result", {})
                final_answer = cdol_data.get("final_answer", "")
                if final_answer:
                    logger.info("CDoL final_answer 长度: %d", len(final_answer))
                    return final_answer
                logger.warning("CDoL 结果中 final_answer 为空")

            if mode == "simple":
                instruction = result_data.get("instruction", "")
                logger.warning("降级到 simple 模式, instruction: %s", instruction[:100])
                return instruction

            # 尝试其他可能的键
            for key in ("final_answer", "answer", "result", "output"):
                if key in result_data:
                    val = result_data[key]
                    if isinstance(val, str):
                        return val
                    elif isinstance(val, dict) and "final_answer" in val:
                        return val["final_answer"]

        # 兜底: 尝试字符串化
        return str(result_data) if result_data else ""

    def _build_nf_transcript(self, orch_result: Any, final_answer: str) -> list[dict]:
        """构建 NF 模式的 transcript。

        包含所有参与 Agent 的对话记录。

        Args:
            orch_result: NexusOrchestrator 执行结果
            final_answer: 最终答案

        Returns:
            transcript 列表
        """
        transcript: list[dict] = []

        # 添加系统消息
        participants = []
        if hasattr(orch_result, 'participants'):
            participants = orch_result.participants

        route = orch_result.route if hasattr(orch_result, 'route') else 'unknown'
        transcript.append({
            "type": "system",
            "message": {
                "role": "system",
                "content": f"[NF Mode] route={route}, participants={participants}"
            }
        })

        # 如果有 CDoL 详细结果，添加各 Agent 的贡献
        result_data = orch_result.result if hasattr(orch_result, 'result') else None
        if isinstance(result_data, dict) and result_data.get("mode") == "cdol":
            cdol_data = result_data.get("cdol_result", {})

            # 添加 CDoL 元数据
            metrics = cdol_data.get("metrics", {})
            if metrics:
                transcript.append({
                    "type": "system",
                    "message": {
                        "role": "system",
                        "content": f"[CDoL Metrics] {json.dumps(metrics, ensure_ascii=False)[:500]}"
                    }
                })

        # 添加最终答案
        transcript.append({
            "type": "message",
            "message": {"role": "user", "content": "[PinchBench Task Prompt]"},
        })
        transcript.append({
            "type": "message",
            "message": {"role": "assistant", "content": final_answer},
        })

        return transcript

    def _extract_and_write_files(
        self,
        task: PinchBenchTask,
        workspace_path: Path,
        response: str,
    ) -> list[str]:
        """从 Agent 响应中提取文件内容并写入工作区。

        复用 nf_agent_runner.py 中的逻辑。
        """
        import re
        written: list[str] = []

        if not response:
            return written

        # ---- 策略1: 从响应中提取 ### filename + code block ----
        pattern1 = re.findall(
            r'''###\s+([\w._/-]+\.[\w]+)\s*\n```(?:\w+)?\s*\n(.*?)```''',
            response, re.DOTALL
        )
        pattern2 = re.findall(
            r'''\*\*([\w._/-]+\.[\w]+)\*\*\s*\n```(?:\w+)?\s*\n(.*?)```''',
            response, re.DOTALL
        )

        all_matches = {}
        for fname, code in pattern1 + pattern2:
            clean_name = fname.strip()
            if clean_name not in all_matches:
                all_matches[clean_name] = code.strip()

        for fname, code_content in all_matches.items():
            target_path = workspace_path / fname
            target_path.parent.mkdir(parents=True, exist_ok=True)
            try:
                target_path.write_text(code_content, encoding="utf-8")
                written.append(fname)
                logger.info("NF: 从响应提取并写入: %s (%d bytes)", fname, len(code_content))
            except Exception as exc:
                logger.warning("NF: 写入失败: %s - %s", fname, exc)

        if written:
            return written

        # ---- 策略2: 从任务 prompt 解析期望输出文件名 ----
        expected_files = _extract_expected_output_files(task)
        content = response.strip()

        # 尝试提取 markdown 代码块中的纯内容
        md_match = re.search(r'''```(?:markdown|md)\s*\n(.*?)```''', response, re.DOTALL)
        if md_match:
            content = md_match.group(1).strip()

        if expected_files:
            if len(expected_files) == 1:
                fname = expected_files[0]
                target_path = workspace_path / fname
                target_path.parent.mkdir(parents=True, exist_ok=True)
                try:
                    target_path.write_text(content, encoding="utf-8")
                    written.append(fname)
                    logger.info("NF: 写入期望输出文件: %s (%d bytes)", fname, len(content))
                except Exception as exc:
                    logger.warning("NF: 写入失败: %s - %s", fname, exc)
            else:
                # 全量写入所有期望文件
                for fname in expected_files:
                    target_path = workspace_path / fname
                    target_path.parent.mkdir(parents=True, exist_ok=True)
                    try:
                        target_path.write_text(content, encoding="utf-8")
                        written.append(fname)
                        logger.info("NF: 全量写入期望文件: %s (%d bytes)", fname, len(content))
                    except Exception as exc:
                        logger.warning("NF: 写入失败: %s - %s", fname, exc)

        # ---- 兜底: 写入 report.md ----
        if not written and task.category not in ("coding",):
            report_path = workspace_path / "report.md"
            try:
                report_path.write_text(content, encoding="utf-8")
                written.append("report.md")
                logger.info("NF: Fallback 写入 report.md (%d bytes)", len(content))
            except Exception as exc:
                logger.warning("NF: Fallback 写入失败: %s", exc)

        return written
