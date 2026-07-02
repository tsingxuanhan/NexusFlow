#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
NexusFlow Dashboard Server v3.1 — Refactored with Real Core Engine
===================================================================
Full-stack AGI task execution server, now using agent4science_nexus/ core modules.

Key integrations:
- CognitiveDivisionEngine: True 3-round CDoL protocol (Round 0/1/2 + FusionJudge)
- NexusOrchestrator: Unified task routing (simple/research/coding/cdol)
- AdaptiveContextManager: Dynamic context management with LazinessDetector
- AgentInformationPolicy: 3-tier information architecture with ContextMask
- InsightStore: Cross-task learning and strategy recommendation

Architecture:
  Dashboard (HTML) ←WebSocket→ API Server ←→ NexusFlow Core Engine
                                                  ↓
                              LLM Router → Ollama (local) / DeepSeek (cloud)
                              Per-agent model assignment + system prompts

Usage:
    # Install deps
    pip install fastapi uvicorn aiohttp websockets

    # Set environment variables (optional)
    export DEEPSEEK_API_KEY="sk-xxx"
    export DEEPSEEK_ENDPOINT="https://api.deepseek.com/v1/chat/completions"
    export OLLAMA_URL="http://localhost:11434"

    # Run
    python nexusflow_server.py

    # Open http://localhost:8900
"""

import asyncio
import json
import logging
import time
import uuid
import os
import re
import traceback
import sys
from datetime import datetime
from typing import Any, Dict, List, Optional, Set, Callable, Awaitable
from dataclasses import dataclass, field, asdict
from enum import Enum

import aiohttp
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, FileResponse
import uvicorn

# 输出目录：任务完成后自动保存报告
OUTPUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "outputs")
os.makedirs(OUTPUT_DIR, exist_ok=True)

# ============================================================================
# Web Search (DuckDuckGo) for Researcher Agent
# ============================================================================
async def web_search(query: str, max_results: int = 5) -> str:
    """使用 DuckDuckGo HTML 版进行搜索，返回搜索结果摘要文本。无需 API Key。"""
    results = []
    try:
        async with aiohttp.ClientSession() as session:
            url = "https://html.duckduckgo.com/html/"
            headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
            async with session.post(url, data={"q": query}, headers=headers, timeout=aiohttp.ClientTimeout(total=15)) as resp:
                if resp.status != 200:
                    return f"[搜索失败: HTTP {resp.status}]"
                html = await resp.text()
        # 解析搜索结果（DuckDuckGo HTML lite）
        from html.parser import HTMLParser
        class DDGParser(HTMLParser):
            def __init__(self):
                super().__init__()
                self.results = []
                self._in_result = False
                self._in_snippet = False
                self._current = {}
                self._text_buf = ""
            def handle_starttag(self, tag, attrs):
                attrs_dict = dict(attrs)
                if tag == "a" and "result__a" in attrs_dict.get("class", ""):
                    self._in_result = True
                    self._current = {"title": "", "url": attrs_dict.get("href", ""), "snippet": ""}
                    self._text_buf = ""
                elif tag == "a" and self._in_result and not self._current.get("url", "").startswith("http"):
                    self._current["url"] = attrs_dict.get("href", "")
                elif tag == "td" and "result__snippet" in attrs_dict.get("class", ""):
                    self._in_snippet = True
                    self._text_buf = ""
            def handle_data(self, data):
                if self._in_result:
                    self._text_buf += data
                if self._in_snippet:
                    self._text_buf += data
            def handle_endtag(self, tag):
                if tag == "a" and self._in_result:
                    self._current["title"] = self._text_buf.strip()
                    self._text_buf = ""
                    self._in_result = False
                if tag == "td" and self._in_snippet:
                    self._current["snippet"] = self._text_buf.strip()
                    self._in_snippet = False
                    if self._current.get("title"):
                        self.results.append(self._current)
                    self._current = {}
        parser = DDGParser()
        parser.feed(html)
        for r in parser.results[:max_results]:
            results.append(f"- [{r['title']}]({r['url']})\n  {r['snippet']}")
    except Exception as e:
        logger.warning(f"Web search failed: {e}")
        return f"[搜索出错: {e}]"
    if not results:
        return f"[搜索 '{query}' 未找到结果]"
    return "\n".join(results)

# ============================================================================
# Add agent4science_nexus to path for imports
# ============================================================================
AGENT4SCIENCE_NEXUS_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "agent4science_nexus")
if AGENT4SCIENCE_NEXUS_PATH not in sys.path:
    sys.path.insert(0, AGENT4SCIENCE_NEXUS_PATH)

# ============================================================================
# Import Real Core Engine Modules from agent4science_nexus
# ============================================================================
try:
    from cognitive_division_engine import (
        CognitiveDivisionEngine,
        CDoLResult,
        PerspectiveDecomposer,
        DecompositionPlan,
        PerspectiveAssignment,
        ContextMask,
        CommunicationLayer,
        FusionJudge,
        IntermediateConclusion,
        DifferenceAttribution,
        Step,
        Contradiction,
        ContradictionType,
        InsightDistiller,
    )
    from adaptive_context_manager import (
        AdaptiveContextManager,
        GlobalMemoryPool,
        LazinessDetector,
    )
    from agent_information_policy import (
        AgentInformationPolicy,
        AgentTier,
        get_information_policy,
        recommend_cdol_config,
    )
    from nexus_orchestrator import (
        NexusOrchestrator,
        TaskResult as NexusTaskResult,
    )
    CORE_ENGINE_AVAILABLE = True
    print("[NexusFlow] ✓ Real Core Engine modules loaded successfully")
except ImportError as e:
    CORE_ENGINE_AVAILABLE = False
    print(f"[NexusFlow] ⚠ Core Engine not available: {e}")
    print("[NexusFlow] Falling back to simplified inline implementations")

# ============================================================================
# Configuration
# ============================================================================

OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://localhost:11434")
DEEPSEEK_API_KEY = os.environ.get("DEEPSEEK_API_KEY", "")
DEEPSEEK_ENDPOINT = os.environ.get("DEEPSEEK_ENDPOINT", "https://api.deepseek.com/v1/chat/completions")

SERVER_HOST = os.environ.get("NEXUSFLOW_HOST", "0.0.0.0")
SERVER_PORT = int(os.environ.get("NEXUSFLOW_PORT", "8900"))

OLLAMA_PRO_MODEL = os.environ.get("OLLAMA_PRO_MODEL", "deepseek-r1:14b")
OLLAMA_FLASH_MODEL = os.environ.get("OLLAMA_FLASH_MODEL", "qwen3.5:9b")
DEEPSEEK_PRO_MODEL = os.environ.get("DEEPSEEK_PRO_MODEL", "deepseek-chat")
DEEPSEEK_FLASH_MODEL = os.environ.get("DEEPSEEK_FLASH_MODEL", "deepseek-chat")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("NexusFlow")


# ============================================================================
# LLM Provider Abstraction
# ============================================================================

class LLMProvider:
    name: str = "base"
    
    async def chat(self, messages: List[Dict], model: str = "", 
                   temperature: float = 0.7, max_tokens: int = 2048) -> Dict:
        raise NotImplementedError
    
    async def is_available(self) -> bool:
        raise NotImplementedError


class OllamaProvider(LLMProvider):
    name = "ollama"
    
    def __init__(self, base_url: str = OLLAMA_URL):
        self.base_url = base_url
        self.session: Optional[aiohttp.ClientSession] = None
        self.models: List[str] = []
    
    async def start(self):
        self.session = aiohttp.ClientSession()
        await self.refresh_models()
    
    async def stop(self):
        if self.session:
            await self.session.close()
    
    async def refresh_models(self):
        try:
            async with self.session.get(f"{self.base_url}/api/tags") as resp:
                if resp.status == 200:
                    data = await resp.json()
                    self.models = [m["name"] for m in data.get("models", [])]
                    logger.info(f"[Ollama] Models: {self.models}")
        except Exception as e:
            logger.warning(f"[Ollama] Unreachable: {e}")
            self.models = []
    
    async def is_available(self) -> bool:
        return len(self.models) > 0
    
    async def chat(self, messages, model="", temperature=0.7, max_tokens=2048):
        if not model:
            model = self.models[0] if self.models else "qwen3.5:9b"
        
        payload = {
            "model": model,
            "messages": messages,
            "stream": False,
            "options": {"temperature": temperature, "num_predict": max_tokens}
        }
        
        start = time.time()
        async with self.session.post(
            f"{self.base_url}/api/chat", json=payload,
            timeout=aiohttp.ClientTimeout(total=300)
        ) as resp:
            if resp.status != 200:
                raise Exception(f"Ollama error {resp.status}")
            data = await resp.json()
            return {
                "content": data.get("message", {}).get("content", ""),
                "model": model,
                "provider": "ollama",
                "tokens": data.get("eval_count", 0),
                "duration_ms": data.get("total_duration", 0) / 1_000_000,
            }


class DeepSeekProvider(LLMProvider):
    name = "deepseek"
    
    def __init__(self, api_key: str = "", endpoint: str = DEEPSEEK_ENDPOINT):
        self.api_key = api_key
        self.endpoint = endpoint
        self.session: Optional[aiohttp.ClientSession] = None
    
    async def start(self):
        self.session = aiohttp.ClientSession()
    
    async def stop(self):
        if self.session:
            await self.session.close()
    
    async def is_available(self) -> bool:
        return bool(self.api_key and self.api_key != "sk-xxx")
    
    async def chat(self, messages, model="", temperature=0.7, max_tokens=2048):
        if not model:
            model = DEEPSEEK_PRO_MODEL
        
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        
        start = time.time()
        async with self.session.post(
            self.endpoint, json=payload, headers=headers,
            timeout=aiohttp.ClientTimeout(total=300)
        ) as resp:
            if resp.status != 200:
                text = await resp.text()
                raise Exception(f"DeepSeek error {resp.status}: {text[:200]}")
            data = await resp.json()
            choice = data.get("choices", [{}])[0]
            usage = data.get("usage", {})
            return {
                "content": choice.get("message", {}).get("content", ""),
                "model": model,
                "provider": "deepseek",
                "tokens": usage.get("total_tokens", 0),
                "duration_ms": (time.time() - start) * 1000,
            }


class LLMRouter:
    def __init__(self):
        self.providers: Dict[str, LLMProvider] = {}
        self.agent_model_map: Dict[str, str] = {}
    
    def register(self, name: str, provider: LLMProvider):
        self.providers[name] = provider
    
    def assign_model(self, agent_id: str, provider: str, model: str):
        self.agent_model_map[agent_id] = f"{provider}:{model}"
    
    def get_mapping(self, agent_id: str) -> tuple:
        mapping = self.agent_model_map.get(agent_id, "")
        if ":" in mapping:
            prov_name, model = mapping.split(":", 1)
            return prov_name, model
        return "", ""
    
    def get_provider(self, agent_id: str) -> tuple:
        prov_name, model = self.get_mapping(agent_id)
        if prov_name in self.providers:
            return self.providers[prov_name], model
        for p in self.providers.values():
            return p, ""
        raise Exception("No LLM provider available")


# ============================================================================
# Agent Definitions (10 Agent Roles as per Technical Doc v2.4)
# ============================================================================

PROVIDER_DISPLAY_NAMES = {
    "deepseek": "DeepSeek Cloud",
    "ollama": "本地 Ollama",
}

# 端边云三层架构标签
EDGE_CLOUD_LAYERS = {
    "cloud": {"label": "☁️ 云端", "desc": "DeepSeek API — 高质量推理 + 广知识"},
    "edge": {"label": "🖥️ 边端", "desc": "本地大模型 (R1 14B) — 计算密集任务"},
    "endpoint": {"label": "📱 终端", "desc": "本地小模型 (Qwen3.5 9B) — 轻量监控"},
}

MODEL_DISPLAY_NAMES = {
    "deepseek-chat": "DeepSeek-V3",
    "deepseek-reasoner": "DeepSeek-R1",
    "deepseek-r1:14b": "DeepSeek-R1 14B (本地)",
    "qwen3:8b": "Qwen3 8B (本地)",
    "qwen3.5:9b": "Qwen3.5 9B (本地)",
    "llama3.1:8b": "Llama3.1 8B (本地)",
    "gemma3:4b": "Gemma3 4B (本地)",
}

TIER_LABELS = {
    "global": "🌐 全局层",
    "cdol": "🔗 CDoL 层",
    "observer": "👁 观察层",
}

# Map Dashboard agent IDs to NexusOrchestrator agent names
AGENT_ID_MAP = {
    "coordinator": "coordinator",
    "strategist": "strategist", 
    "coder": "coder",
    "researcher": "researcher",
    "analyst": "analyst",
    "critic": "critic",
    "synthesizer": "synthesizer",
    "archivist": "archivist",
    "observer": "observer",
    "monitor": "monitor",
}

AGENT_DEFS = [
    {
        "id": "coordinator",
        "name": "Coordinator",
        "label": "编排者",
        "icon": "🧭",
        "tier": "global",
        "provider": "deepseek",
        "model": "pro",
        "edge_cloud_layer": "cloud",
        "description": "接收任务，评估复杂度，决定路由（单Agent vs CDoL），分配资源，追踪进度",
        "capabilities": ["task_routing", "complexity_assessment", "resource_allocation", "progress_tracking"],
        "system_prompt": """你是 NexusFlow 多智能体协作系统的 **Coordinator（编排者）**。

## 核心职责
1. 接收用户任务，评估复杂度和所需资源
2. 决定执行路由：简单任务→单Agent直接处理；复杂任务→启动CDoL多Agent协作
3. 选择合适的拓扑结构（星形/树形/网状/链式/汇聚）
4. 分配参与者Agent，监控执行进度
5. 异常处理和任务重路由

## 决策原则
- 任务涉及2个以上领域 → CDoL模式
- 任务步骤超过5步 → 多拓扑切换
- 优先利用已有经验（记忆系统）
- 保持全局视野，不陷入细节

## 输出格式
请用结构化JSON回复，包含：route（simple/cdol）、topology（star/tree/mesh/chain/converge）、participants（agent列表）、steps（执行计划）、reason（决策理由）"""
    },
    {
        "id": "archivist",
        "name": "Archivist",
        "label": "档案师",
        "icon": "📚",
        "tier": "global",
        "provider": "deepseek",
        "model": "pro",
        "edge_cloud_layer": "cloud",
        "description": "任务完成后蒸馏经验，写入全局记忆，跨任务知识复用",
        "capabilities": ["memory_distillation", "knowledge_indexing", "experience_retrieval", "pattern_extraction"],
        "system_prompt": """你是 NexusFlow 的 **Archivist（档案师）**。

## 核心职责
1. 任务完成后提取关键经验和教训
2. 将经验蒸馏为可复用的知识条目
3. 维护全局记忆池，确保跨任务知识传承
4. 识别反复出现的模式，升级为系统性知识

## 蒸馏规则
- 每条经验必须包含：情境、行动、结果、教训
- 区分"技术经验"和"流程经验"
- 高置信度经验自动归档，低置信度标记待验证
- 定期合并相似经验，去除冗余

## 输出格式
JSON数组，每条包含：lesson（经验描述）、category（技术/流程/协作）、confidence（0-1）、tags（标签列表）"""
    },
    {
        "id": "strategist",
        "name": "Strategist",
        "label": "策略师",
        "icon": "🧩",
        "tier": "cdol",
        "provider": "deepseek",
        "model": "pro",
        "edge_cloud_layer": "cloud",
        "description": "分析任务本质，分解为多视角子问题，设计信息不对称方案",
        "capabilities": ["task_decomposition", "perspective_design", "strategy_planning", "evidence_partition"],
        "system_prompt": """你是 NexusFlow CDoL引擎的 **Strategist（策略师）**。

## 核心职责
1. 分析任务的本质和核心挑战
2. 将任务分解为多个认知视角（perspective）
3. 为每个视角设计 ContextMask（信息不对称方案）
4. 确定哪些Agent最适合回答哪些子问题

## 分解策略（6种）
- evidence_split: 按证据类型拆分（实验数据 vs 理论分析）
- role_constraint: 注入对抗角色（质疑者 vs 辩护者）
- layer_separation: 分层（抽象原理 vs 具体实现）
- modality_split: 按模态拆分（结构化数据 vs 非结构化文本）
- time_slice: 时序切片（前期 vs 后期）
- abstraction_level: 抽象层级（具体实例 vs 抽象规则）

## 输出格式
JSON包含：summary（分解策略简述）、perspectives（对象，key=agent_id, value=子问题描述）、rationale（分解理由）、bridgeability（视角间可桥接性评分0-1）"""
    },
    {
        "id": "coder",
        "name": "Coder",
        "label": "编码师",
        "icon": "💻",
        "tier": "cdol",
        "provider": "ollama",
        "model": "pro",  # 边端：本地大模型 deepseek-r1:14b
        "edge_cloud_layer": "edge",
        "description": "编写代码、调试工具、实现自动化方案",
        "capabilities": ["code_generation", "debugging", "tool_development", "automation"],
        "system_prompt": """你是 NexusFlow 的 **Coder（编码师）**。

## 核心职责
1. 根据任务需求编写高质量代码
2. 设计工具接口和自动化方案
3. 调试和修复代码问题
4. 提供代码审查意见

## 编码原则
- 代码必须可运行，不写伪代码
- 包含必要的注释和错误处理
- 遵循项目现有代码风格
- 优先使用标准库，减少外部依赖

## 输出格式
代码块用```lang```包裹，附带简要说明。复杂实现先给架构说明再给代码。"""
    },
    {
        "id": "researcher",
        "name": "Researcher",
        "label": "研究员",
        "icon": "🔍",
        "tier": "cdol",
        "provider": "deepseek",  # 云端：需要强知识 + 联网搜索
        "model": "pro",
        "edge_cloud_layer": "cloud",
        "description": "联网搜索、信息检索、文献分析、提供事实依据",
        "capabilities": ["web_search", "literature_analysis", "data_collection", "evidence_synthesis"],
        "system_prompt": """你是 NexusFlow 的 **Researcher（研究员）**。

## 核心职责
1. 检索和整理相关信息（可联网搜索获取最新数据）
2. 分析文献和数据源
3. 提供事实依据和证据支撑
4. 识别信息缺口和研究空白

## 研究原则
- 引用必须标注来源
- 区分事实和推测
- 多角度交叉验证
- 注意信息的时效性
- 优先使用搜索结果中的最新数据，而非仅依赖训练知识

## 输出格式
结构化报告：背景、关键发现（附来源链接）、证据列表、研究空白、建议方向"""
    },
    {
        "id": "analyst",
        "name": "Analyst",
        "label": "分析师",
        "icon": "📊",
        "tier": "cdol",
        "provider": "ollama",
        "model": "pro",  # 边端：本地大模型 deepseek-r1:14b
        "edge_cloud_layer": "edge",
        "description": "数据分析、模式识别、量化洞察",
        "capabilities": ["data_analysis", "pattern_recognition", "statistical_modeling", "insight_generation"],
        "system_prompt": """你是 NexusFlow 的 **Analyst（分析师）**。

## 核心职责
1. 结构化分析数据和信息
2. 识别隐藏模式和趋势
3. 生成量化洞察和可视化建议
4. 提供数据驱动的决策依据

## 分析原则
- 用数据说话，不做主观判断
- 标注置信度和不确定性
- 发现异常值要特别说明
- 给出可操作的建议

## 输出格式
分析报告：数据摘要、关键发现（按重要性排序）、模式识别结果、量化指标、建议"""
    },
    {
        "id": "critic",
        "name": "Critic",
        "label": "批评家",
        "icon": "🔥",
        "tier": "cdol",
        "provider": "deepseek",
        "model": "pro",
        "edge_cloud_layer": "cloud",
        "description": "对抗质疑、发现盲点、确保结论鲁棒",
        "capabilities": ["adversarial_review", "assumption_challenging", "edge_case_detection", "quality_gate"],
        "system_prompt": """你是 NexusFlow 的 **Critic（批评家）**。

## 核心职责
1. 质疑其他Agent的假设和结论
2. 发现论证中的逻辑漏洞
3. 探索边界情况和反例
4. 确保最终结论的鲁棒性

## 批评原则
- 质疑要有建设性，不是为反对而反对
- 指出问题的同时给出改进方向
- 区分"致命缺陷"和"可接受的局限"
- 关注可证伪性——结论是否可被验证

## 输出格式
评审报告：总体评价（通过/需修改/驳回）、具体问题列表（每条含严重程度1-5）、改进建议、残余风险评估"""
    },
    {
        "id": "synthesizer",
        "name": "Synthesizer",
        "label": "整合师",
        "icon": "🔬",
        "tier": "cdol",
        "provider": "deepseek",
        "model": "pro",
        "edge_cloud_layer": "cloud",
        "description": "多视角融合、解决矛盾、生成统一方案",
        "capabilities": ["multi_view_fusion", "conflict_resolution", "conclusion_synthesis", "report_generation"],
        "system_prompt": """你是 NexusFlow 的 **Synthesizer（整合师）**。

## 核心职责
1. 综合多个Agent的独立分析结论
2. 识别共识和分歧
3. 解决矛盾——区分"可归因矛盾"（可解释）和"不可归因矛盾"（需进一步研究）
4. 生成统一的最终答案

## 融合原则
- 不丢弃任何有价值的洞察
- 矛盾是信息，不是噪声
- 最终答案必须自洽
- 标注每个结论的来源Agent和置信度

## 输出格式
综合报告：共识列表、分歧列表（及解决方式）、最终结论、置信度评分、来源溯源"""
    },
    {
        "id": "observer",
        "name": "Observer",
        "label": "旁观者",
        "icon": "👁",
        "tier": "observer",
        "provider": "ollama",
        "model": "flash",
        "edge_cloud_layer": "endpoint",
        "description": "仅观察中间结论，发现跨视角隐藏模式",
        "capabilities": ["meta_observation", "cross_pattern_detection", "bias_detection"],
        "system_prompt": """你是 NexusFlow 的 **Observer（旁观者）**。

## 核心职责
你不参与直接推理，而是旁观整个协作过程：
1. 观察各Agent的推理路径和中间结论
2. 发现跨视角的隐藏模式和关联
3. 检测可能的认知偏见
4. 提供元层面的观察报告

## 输出格式
观察报告：过程摘要、发现的跨视角模式、潜在偏见提醒、建议关注点"""
    },
    {
        "id": "monitor",
        "name": "Monitor",
        "label": "监控者",
        "icon": "📡",
        "tier": "observer",
        "provider": "ollama",
        "model": "flash",
        "edge_cloud_layer": "endpoint",
        "description": "监控Agent负载与系统健康，检测异常",
        "capabilities": ["health_monitoring", "load_tracking", "anomaly_detection", "reroute_trigger"],
        "system_prompt": """你是 NexusFlow 的 **Monitor（监控者）**。

## 核心职责
1. 监控各Agent的执行状态和资源消耗
2. 检测异常行为（超时、重复、死循环）
3. 评估系统整体健康度
4. 触发拓扑重路由建议

## 输出格式
监控报告：系统健康度（0-100）、各Agent状态、异常告警（如有）、资源使用摘要、优化建议"""
    },
]


# ============================================================================
# Data Structures
# ============================================================================

class TaskStatus(str, Enum):
    PENDING = "pending"
    PLANNING = "planning"
    RUNNING = "running"
    REVIEWING = "reviewing"
    COMPLETED = "completed"
    FAILED = "failed"

@dataclass
class AgentState:
    id: str
    state: str = "idle"
    current_task: str = ""
    tokens_used: int = 0
    tasks_completed: int = 0
    avg_latency_ms: float = 0.0
    last_output: str = ""
    last_active: str = ""
    cdol_round: int = 0  # CDoL轮次跟踪

@dataclass
class TaskExecution:
    id: str
    description: str
    max_steps: int = 5
    status: str = "pending"
    route: str = ""
    topology: str = ""
    participants: List[str] = field(default_factory=list)
    current_step: int = 0
    total_steps: int = 0
    step_results: List[Dict] = field(default_factory=list)
    final_result: str = ""
    summary: str = ""
    created_at: str = ""
    started_at: str = ""
    completed_at: str = ""
    tokens_total: int = 0
    duration_seconds: float = 0.0
    synergy_gain: float = 0.0
    error: str = ""
    # CDoL tracking
    cdol_strategy: str = ""
    cdol_rounds_completed: int = 0
    false_consensus_warnings: List[Dict] = field(default_factory=list)
    laziness_alerts: List[Dict] = field(default_factory=list)
    output_path: str = ""


# ============================================================================
# Event Bus
# ============================================================================

class EventBus:
    def __init__(self):
        self.connections: Set[WebSocket] = set()
        self._log: List[Dict] = []
        self._max = 500
    
    async def connect(self, ws: WebSocket):
        await ws.accept()
        self.connections.add(ws)
        logger.info(f"Dashboard connected ({len(self.connections)} clients)")
        await ws.send_json({"type": "history", "events": self._log[-50:]})
    
    def disconnect(self, ws: WebSocket):
        self.connections.discard(ws)
    
    async def emit(self, event_type: str, data: Dict):
        event = {"type": event_type, "data": data, "ts": datetime.now().isoformat()}
        self._log.append(event)
        if len(self._log) > self._max:
            self._log = self._log[-self._max:]
        dead = set()
        for ws in self.connections:
            try:
                await ws.send_json(event)
            except:
                dead.add(ws)
        self.connections -= dead
    
    async def log(self, msg: str, level: str = "info"):
        await self.emit("log", {"message": msg, "level": level})


# ============================================================================
# Topology Router
# ============================================================================

TOPOLOGY_CONFIGS = {
    "star": {"name": "星形", "desc": "Coordinator中心分发，所有Agent并行",
             "active": ["coordinator", "strategist", "coder", "researcher", "analyst", "critic", "synthesizer", "observer", "monitor"]},
    "tree": {"name": "树形", "desc": "分层委托，逐级传递",
             "active": ["coordinator", "strategist", "researcher", "coder", "analyst", "observer"]},
    "mesh": {"name": "网状", "desc": "全连接对等协商",
             "active": ["strategist", "coder", "researcher", "analyst", "critic", "synthesizer", "observer", "monitor"]},
    "chain": {"name": "链式", "desc": "流水线顺序处理",
              "active": ["researcher", "coder", "critic", "synthesizer", "observer", "monitor"]},
    "converge": {"name": "汇聚", "desc": "多路结果汇聚到Synthesizer",
                 "active": ["researcher", "analyst", "coder", "synthesizer", "archivist", "observer", "monitor"]},
}

def select_topology(task_desc: str) -> str:
    desc = task_desc.lower()
    scores = {
        "converge": sum(1 for kw in ["文献","调研","搜索","论文","综述","分析"] if kw in desc),
        "chain": sum(1 for kw in ["代码","编程","实现","开发","debug","code"] if kw in desc),
        "mesh": sum(1 for kw in ["对比","争议","评估","优化","debate","compare"] if kw in desc),
        "tree": sum(1 for kw in ["规划","架构","设计","plan","design"] if kw in desc),
        "star": 0,
    }
    best = max(scores, key=scores.get)
    return best if scores[best] > 0 else "star"


# ============================================================================
# 6 Decomposition Strategies (from Technical Doc v2.4)
# ============================================================================

DECOMPOSITION_STRATEGIES = {
    "evidence_split": {
        "name": "证据拆分",
        "desc": "Agent₁看证据集A，Agent₂看证据集B，必须通信才能拼出完整证据链",
        "keywords": ["数据", "实验", "证据", "测量", "实验数据", "理论分析"],
        "suitable_for": ["research", "analysis", "verification"],
    },
    "role_constraint": {
        "name": "角色约束",
        "desc": "Agent₁=质疑者，Agent₂=辩护者，对抗性视角消除confirmation bias",
        "keywords": ["论证", "评估", "决策", "争议", "方案", "假设", "验证"],
        "suitable_for": ["evaluation", "decision", "debate"],
    },
    "layer_separation": {
        "name": "层级分离",
        "desc": "Agent₁高层策略，Agent₂底层验证，策略Agent不被琐碎约束束缚",
        "keywords": ["架构", "设计", "实现", "系统", "模块", "方法论"],
        "suitable_for": ["architecture", "design", "implementation"],
    },
    "modality_split": {
        "name": "模态拆分",
        "desc": "Agent₁结构化数据，Agent₂非结构化描述，互补格式促进交叉验证",
        "keywords": ["数据", "报告", "表格", "描述", "文档", "数值"],
        "suitable_for": ["report", "documentation", "data_analysis"],
    },
    "time_slice": {
        "name": "时序切片",
        "desc": "Agent₁看时序前半段，Agent₂看后半段，必须推断对方因果上下文",
        "keywords": ["演化", "历史", "趋势", "阶段", "时间", "发展", "演进"],
        "suitable_for": ["temporal", "evolution", "trend"],
    },
    "abstraction_level": {
        "name": "抽象层级",
        "desc": "Agent₁看具体实例，Agent₂看抽象规则，实例↔规则双向验证",
        "keywords": ["理论", "实践", "原理", "案例", "抽象", "规则"],
        "suitable_for": ["theory", "validation", "generalization"],
    },
}


def select_decomposition_strategy(task_desc: str, history: List[Dict] = None) -> Dict:
    """根据任务描述和历史经验选择最优分解策略，返回策略+选择依据
    
    Returns:
        Dict with keys: strategy, reasoning, confidence, factors
    """
    desc_lower = task_desc.lower()
    
    # 1. 历史经验优先（Insight驱动）
    if history:
        import math
        strategy_stats = {}
        for h in history:
            strat = h.get("strategy", "")
            success = h.get("success", False)
            if strat not in strategy_stats:
                strategy_stats[strat] = {"total": 0, "success": 0}
            strategy_stats[strat]["total"] += 1
            if success:
                strategy_stats[strat]["success"] += 1
        
        best_score = -1
        best_strategy = None
        for strat, stats in strategy_stats.items():
            if stats["total"] > 0:
                success_rate = stats["success"] / stats["total"]
                exploration_bonus = 0.1 / math.sqrt(stats["total"])
                score = success_rate + exploration_bonus
                if score > best_score:
                    best_score = score
                    best_strategy = strat
        
        if best_strategy and best_strategy in DECOMPOSITION_STRATEGIES:
            success_rate = strategy_stats[best_strategy]["success"] / max(1, strategy_stats[best_strategy]["total"])
            return {
                "strategy": best_strategy,
                "reasoning": f"基于历史经验选择：该策略在过往 {strategy_stats[best_strategy]['total']} 次使用中成功率 {success_rate:.0%}",
                "confidence": min(0.9, success_rate),
                "factors": ["历史成功率", "探索-利用平衡"],
            }
    
    # 2. 规则兜底：关键词匹配
    scores = {}
    matched_keywords = {}
    for strat_id, strat_info in DECOMPOSITION_STRATEGIES.items():
        matched = [kw for kw in strat_info["keywords"] if kw in desc_lower]
        scores[strat_id] = len(matched)
        matched_keywords[strat_id] = matched
    
    best = max(scores, key=scores.get)
    
    if scores[best] > 0:
        strat_info = DECOMPOSITION_STRATEGIES[best]
        keywords_found = matched_keywords[best]
        return {
            "strategy": best,
            "reasoning": f"任务描述包含关键特征词：{', '.join(keywords_found[:5])}，匹配「{strat_info['name']}」策略",
            "confidence": min(0.8, 0.3 + 0.1 * scores[best]),
            "factors": ["关键词匹配", f"匹配度 {scores[best]}"] + ([f"适用场景: {strat_info.get('when', '')}"] if strat_info.get('when') else []),
        }
    
    # 3. 默认策略
    return {
        "strategy": "abstraction_level",
        "reasoning": "未检测到明确特征，使用默认策略：抽象层级分析（适用于大多数复杂问题）",
        "confidence": 0.5,
        "factors": ["默认策略", "通用性"],
    }


# ============================================================================
# InsightStore: Cross-task Learning (Integrated from Technical Doc v2.4)
# ============================================================================

class InsightStore:
    """
    存储跨执行的结构化经验，支持策略推荐。
    五维Insight结构：strategy_effectiveness / contradiction_patterns / 
    decomposition_quality / synergy_analysis / task_type
    """
    
    def __init__(self, max_insights: int = 100):
        self.insights: List[Dict] = []
        self.max_insights = max_insights
    
    def record(self, insight: Dict):
        self.insights.append({
            "timestamp": datetime.now().isoformat(),
            "id": f"insight_{uuid.uuid4().hex[:8]}",
            **insight,
        })
        if len(self.insights) > self.max_insights:
            self.insights = self.insights[-self.max_insights:]
    
    def get_history(self, task_type: str = None) -> List[Dict]:
        if task_type:
            return [i for i in self.insights if i.get("task_type") == task_type]
        return self.insights
    
    def get_best_strategy(self) -> Optional[str]:
        """获取历史表现最好的策略"""
        stats = self.get_strategy_effectiveness()
        if not stats:
            return None
        best = max(stats.items(), key=lambda x: x[1]["success"] / max(x[1]["total"], 1))
        return best[0] if best[1]["total"] >= 2 else None
    
    def get_strategy_effectiveness(self) -> Dict[str, Dict]:
        stats = {}
        for insight in self.insights:
            strat = insight.get("strategy", "")
            if not strat:
                continue
            if strat not in stats:
                stats[strat] = {"total": 0, "success": 0, "avg_synergy": 0}
            stats[strat]["total"] += 1
            if insight.get("success", False):
                stats[strat]["success"] += 1
            n = stats[strat]["total"]
            stats[strat]["avg_synergy"] = (
                (stats[strat]["avg_synergy"] * (n - 1) + insight.get("synergy_gain", 0)) / n
            )
        return stats
    
    def get_task_execution_history(self) -> List[Dict]:
        return [
            {
                "strategy": i.get("strategy", ""),
                "success": i.get("success", False),
                "synergy_gain": i.get("synergy_gain", 0),
                "task_type": i.get("task_type", ""),
            }
            for i in self.insights
        ]


# ============================================================================
# LazinessDetector: 4-Dimension Laziness Detection (Technical Doc v2.4)
# ============================================================================

class LazinessDetector:
    """
    监控四个核心指标判断Agent是否正在"偷懒"：
    1. 检索频率：Agent主动查询记忆系统的频率
    2. 纠错率：Agent自我修正的频率
    3. 置信度趋势：Agent输出置信度的变化方向
    4. 信息源多样性：Agent引用信息来源的分散度
    """
    
    def __init__(self):
        self.metrics_history: Dict[str, List[Dict]] = {}
        self.alerts: List[Dict] = []
    
    def record_step_metrics(self, agent_id: str, step: int, metrics: Dict):
        if agent_id not in self.metrics_history:
            self.metrics_history[agent_id] = []
        
        self.metrics_history[agent_id].append({
            "step": step,
            "retrieval_count": metrics.get("retrieval_count", 0),
            "self_correction_count": metrics.get("self_correction_count", 0),
            "confidence": metrics.get("confidence", 0.5),
            "source_diversity": metrics.get("source_diversity", 0.5),
            "output_length": metrics.get("output_length", 0),
            "timestamp": datetime.now().isoformat(),
        })
    
    def detect_laziness(self, agent_id: str) -> Dict:
        """检测某Agent是否出现懒惰迹象"""
        history = self.metrics_history.get(agent_id, [])
        if len(history) < 3:
            return {"is_lazy": False, "score": 0.0, "signals": []}
        
        signals = []
        lazy_score = 0.0
        recent = history[-3:]
        
        # Signal 1: Retrieval frequency declining
        retrievals = [m["retrieval_count"] for m in recent]
        if all(retrievals[i] >= retrievals[i+1] for i in range(len(retrievals)-1)) and retrievals[0] > 0:
            signals.append("检索频率持续下降")
            lazy_score += 0.25
        
        # Signal 2: Low self-correction rate
        corrections = [m["self_correction_count"] for m in recent]
        avg_correction = sum(corrections) / len(corrections)
        if avg_correction < 0.1:
            signals.append("纠错率过低，缺乏自我审视")
            lazy_score += 0.25
        
        # Signal 3: Confidence rising but output quality not improving
        confidences = [m["confidence"] for m in recent]
        lengths = [m["output_length"] for m in recent]
        if all(confidences[i] <= confidences[i+1] for i in range(len(confidences)-1)):
            if lengths[-1] <= lengths[0] * 1.2:
                signals.append("置信度上升但输出未改善，可能过度自信")
                lazy_score += 0.25
        
        # Signal 4: Source diversity declining
        diversities = [m["source_diversity"] for m in recent]
        if all(diversities[i] >= diversities[i+1] for i in range(len(diversities)-1)) and diversities[0] > 0.3:
            signals.append("信息源多样性下降，可能陷入信息茧房")
            lazy_score += 0.25
        
        is_lazy = lazy_score >= 0.5
        
        if is_lazy:
            self.alerts.append({
                "agent_id": agent_id,
                "step": history[-1]["step"],
                "score": lazy_score,
                "signals": signals,
                "timestamp": datetime.now().isoformat(),
            })
        
        return {"is_lazy": is_lazy, "score": lazy_score, "signals": signals}
    
    def compute_laziness_metrics(self, agent_id: str, output: str,
                                  has_retrieval: bool = False,
                                  has_correction: bool = False,
                                  confidence: float = 0.5) -> Dict:
        """从Agent输出中提取懒惰检测指标"""
        source_markers = len(set(re.findall(r'\[来源[^\]]*\]|\[Source[^\]]*\]|arXiv:\d+', output, re.I)))
        source_diversity = min(1.0, source_markers / 5.0)
        
        confident_words = ["确定", "肯定", "显然", "必然", "clearly", "obviously", "definitely"]
        uncertain_words = ["可能", "或许", "不确定", "需要验证", "maybe", "perhaps", "uncertain"]
        
        output_lower = output.lower()
        conf_count = sum(1 for w in confident_words if w in output_lower)
        unc_count = sum(1 for w in uncertain_words if w in output_lower)
        
        estimated_confidence = 0.5 + (conf_count - unc_count) * 0.1
        estimated_confidence = max(0.1, min(0.95, estimated_confidence))
        
        return {
            "retrieval_count": 1 if has_retrieval else 0,
            "self_correction_count": 1 if has_correction else 0,
            "confidence": confidence if confidence != 0.5 else estimated_confidence,
            "source_diversity": source_diversity,
            "output_length": len(output),
        }


# ============================================================================
# FusionJudge: False Consensus Detection (Technical Doc v2.4)
# ============================================================================

class FusionJudge:
    """
    四类矛盾分类与虚假一致检测。
    
    矛盾类型：
    1. ATTRIBUTABLE: 可归因矛盾 → 触发双向通信修正
    2. UNATTRIBUTABLE: 不可归因矛盾 → 回溯到视角分解器
    3. FALSE_CONSENSUS: 虚假一致 → 比较推理链，拒绝合并
    4. TRUE_CONVERGENCE: 真实收敛 → 输出最终答案
    """
    
    ATTRIBUTABLE = "attributable"
    UNATTRIBUTABLE = "unattributable"
    FALSE_CONSENSUS = "false_consensus"
    TRUE_CONVERGENCE = "true_convergence"
    
    def __init__(self):
        self.warnings: List[Dict] = []
    
    async def detect_conflicts(self, conclusions: Dict[str, str],
                                agent_defs_map: Dict[str, Dict],
                                llm_call: Callable) -> Dict:
        """检测Agent结论之间的矛盾类型"""
        if len(conclusions) < 2:
            return {"conflict_type": self.TRUE_CONVERGENCE, "details": [], 
                    "merged_conclusion": None, "warnings": []}
        
        analysis_tasks = []
        for agent_id, conclusion in conclusions.items():
            adef = agent_defs_map.get(agent_id, {})
            analysis_tasks.append({
                "agent_id": agent_id,
                "role": adef.get("label", agent_id),
                "tier": adef.get("tier", "unknown"),
                "conclusion_preview": conclusion[:500],
            })
        
        analysis_text = "\n\n".join([
            f"【{t['role']}({t['agent_id']})】层级:{t['tier']}\n结论: {t['conclusion_preview']}"
            for t in analysis_tasks
        ])
        
        prompt = f"""请分析以下多个Agent的结论之间的矛盾关系。

{analysis_text}

请判断：
1. 各Agent的结论是否一致？（结论层面的共识/分歧）
2. 各Agent的推理路径是否一致？（即使结论相同，推理过程可能完全不同）
3. 如果结论相同但推理路径不同，说明存在"虚假一致"风险——它们可能因为完全不同的错误理由得出了相同答案。

请以JSON格式回复：
{{
    "conclusions_agree": true/false,
    "reasoning_paths_agree": true/false,
    "conflict_type": "attributable"/"unattributable"/"false_consensus"/"true_convergence",
    "explanation": "分析说明",
    "key_contradictions": ["矛盾点1", "矛盾点2"],
    "recommendation": "建议如何处理"
}}"""
        
        try:
            resp = await llm_call("fusion_judge", [
                {"role": "system", "content": "你是NexusFlow的FusionJudge，专门负责检测多Agent结论之间的矛盾类型，特别关注虚假一致。"},
                {"role": "user", "content": prompt}
            ], temperature=0.3, max_tokens=1000)
            
            content = resp.get("content", "")
            json_match = re.search(r'\{[\s\S]*\}', content)
            if json_match:
                analysis = json.loads(json_match.group())
                conflict_type = analysis.get("conflict_type", self.TRUE_CONVERGENCE)
                
                if conflict_type == self.FALSE_CONSENSUS:
                    warning = {
                        "type": "false_consensus",
                        "agents": list(conclusions.keys()),
                        "explanation": analysis.get("explanation", ""),
                        "contradictions": analysis.get("key_contradictions", []),
                        "recommendation": analysis.get("recommendation", "分离为条件方案，不合并"),
                        "timestamp": datetime.now().isoformat(),
                    }
                    self.warnings.append(warning)
                
                return {
                    "conflict_type": conflict_type,
                    "details": [analysis],
                    "merged_conclusion": None if conflict_type == self.FALSE_CONSENSUS else content,
                    "warnings": self.warnings[-1:] if conflict_type == self.FALSE_CONSENSUS else [],
                }
        except Exception as e:
            logger.warning(f"FusionJudge analysis failed: {e}")
        
        return self._fallback_detect(conclusions)
    
    def _fallback_detect(self, conclusions: Dict[str, str]) -> Dict:
        """降级检测：基于关键词重叠度"""
        if len(conclusions) < 2:
            return {"conflict_type": self.TRUE_CONVERGENCE, "details": [], 
                    "merged_conclusion": None, "warnings": []}
        
        all_texts = list(conclusions.values())
        word_sets = [set(t.lower().split()) for t in all_texts]
        
        overlaps = []
        for i in range(len(word_sets)):
            for j in range(i+1, len(word_sets)):
                intersection = len(word_sets[i] & word_sets[j])
                union = len(word_sets[i] | word_sets[j])
                overlaps.append(intersection / union if union > 0 else 0)
        
        avg_overlap = sum(overlaps) / len(overlaps) if overlaps else 0
        
        if avg_overlap > 0.5:
            return {
                "conflict_type": "uncertain",
                "details": [{"avg_overlap": avg_overlap}],
                "merged_conclusion": None,
                "warnings": [],
            }
        else:
            return {
                "conflict_type": self.ATTRIBUTABLE,
                "details": [{"avg_overlap": avg_overlap, "note": "结论差异较大，可能可归因"}],
                "merged_conclusion": None,
                "warnings": [],
            }


# ============================================================================
# NexusFlow Execution Engine (with Real Core Engine Integration)
# ============================================================================

class NexusFlowEngine:
    """
    Full CDoL execution engine with real core module integration.
    
    Key features:
    - True 3-round CDoL communication protocol (Round 0/1/2)
    - FusionJudge false consensus detection
    - InsightStore cross-task learning
    - LazinessDetector 4-dimension monitoring
    - 6 decomposition strategies
    - 10 Agent roles properly invoked
    """
    
    def __init__(self, llm_router: LLMRouter, events: EventBus):
        self.llm = llm_router
        self.events = events
        self.agent_states: Dict[str, AgentState] = {
            a["id"]: AgentState(id=a["id"]) for a in AGENT_DEFS
        }
        self.agent_defs_map: Dict[str, Dict] = {a["id"]: a for a in AGENT_DEFS}
        
        # Initialize core engine components
        self._init_core_engine()
        
        # Insight store for cross-task learning
        self.insight_store = InsightStore()
        
        # Laziness detector
        self.laziness_detector = LazinessDetector()
        
        # FusionJudge
        self.fusion_judge = FusionJudge()
        
        logger.info(f"[NexusFlow] Engine initialized (Core Engine: {CORE_ENGINE_AVAILABLE})")
    
    def _init_core_engine(self):
        """Initialize real core engine if available"""
        self.cdol_engine = None
        self.cdol_available = False
        
        if CORE_ENGINE_AVAILABLE:
            try:
                # Create wrapper LLM function for core engine
                async def core_llm_call(agent_id: str, messages: List[Dict], 
                                        temperature: float = 0.7, max_tokens: int = 2048) -> Dict:
                    return await self._call_llm(agent_id, messages, temperature, max_tokens)
                
                # Initialize CDoL engine with real modules
                self.cdol_engine = CognitiveDivisionEngine(
                    agents={a["id"]: _AgentWrapper(a["id"], self) for a in AGENT_DEFS},
                    llm_chat=core_llm_call,
                    insight_store=self.insight_store if hasattr(self, 'insight_store') else None,
                )
                self.cdol_available = True
                logger.info("[NexusFlow] ✓ Real CognitiveDivisionEngine loaded")
            except Exception as e:
                logger.warning(f"[NexusFlow] Failed to initialize core engine: {e}")
                self.cdol_engine = None
                self.cdol_available = False
    
    def get_agent_def(self, agent_id: str) -> Dict:
        return self.agent_defs_map.get(agent_id, {})
    
    def get_all_agents(self) -> List[Dict]:
        result = []
        for adef in AGENT_DEFS:
            state = self.agent_states.get(adef["id"], AgentState(id=adef["id"]))
            prov_name, model_name = self.llm.get_mapping(adef["id"])
            result.append({
                **adef,
                "state": state.state,
                "current_task": state.current_task,
                "tokens_used": state.tokens_used,
                "tasks_completed": state.tasks_completed,
                "avg_latency_ms": round(state.avg_latency_ms, 1),
                "last_output": state.last_output[:200] if state.last_output else "",
                "last_active": state.last_active,
                "display_provider": PROVIDER_DISPLAY_NAMES.get(prov_name, prov_name),
                "display_model": MODEL_DISPLAY_NAMES.get(model_name, model_name),
                "tier_label": TIER_LABELS.get(adef.get("tier", ""), adef.get("tier", "")),
                "edge_cloud_layer": adef.get("edge_cloud_layer", ""),
                "edge_cloud_label": EDGE_CLOUD_LAYERS.get(adef.get("edge_cloud_layer", ""), {}).get("label", ""),
                "cdol_round": state.cdol_round,
            })
        return result
    
    def reset_agent_states(self):
        for s in self.agent_states.values():
            s.state = "idle"
            s.current_task = ""
            s.cdol_round = 0
    
    async def _call_llm(self, agent_id: str, messages: List[Dict],
                        temperature: float = 0.7, max_tokens: int = 2048) -> Dict:
        """Call LLM for a specific agent with model routing"""
        adef = self.agent_defs_map.get(agent_id, {})
        prov_name = adef.get("provider", "ollama")
        model_tier = adef.get("model", "flash")
        
        provider = None
        model_name = ""
        
        if prov_name == "deepseek" and "deepseek" in self.llm.providers:
            ds = self.llm.providers["deepseek"]
            if await ds.is_available():
                provider = ds
                model_name = DEEPSEEK_PRO_MODEL if model_tier == "pro" else DEEPSEEK_FLASH_MODEL
        
        if not provider and prov_name == "ollama" and "ollama" in self.llm.providers:
            ol = self.llm.providers["ollama"]
            if await ol.is_available():
                provider = ol
                model_name = OLLAMA_PRO_MODEL if model_tier == "pro" else OLLAMA_FLASH_MODEL
                if model_name not in ol.models and ol.models:
                    model_name = ol.models[0]
        
        if not provider:
            for p in self.llm.providers.values():
                if await p.is_available():
                    provider = p
                    break
        
        if not provider or not await provider.is_available():
            return {"content": f"[模拟] {agent_id} 无可用LLM", "provider": "none", "tokens": 0, "duration_ms": 0}
        
        try:
            result = await provider.chat(messages, model=model_name, 
                                         temperature=temperature, max_tokens=max_tokens)
            return result
        except Exception as e:
            logger.error(f"LLM call failed for {agent_id}: {e}")
            return {"content": f"[LLM Error] {e}", "provider": "error", "tokens": 0, "duration_ms": 0}
    
    async def _update_agent(self, agent_id: str, state: str, task: str = "", 
                           output: str = "", cdol_round: int = 0):
        s = self.agent_states.get(agent_id)
        if s:
            s.state = state
            if task: s.current_task = task
            if output: s.last_output = output
            s.last_active = datetime.now().isoformat()
            if cdol_round > 0:
                s.cdol_round = cdol_round
        
        await self.events.emit("agent_state", {
            "agent_id": agent_id, "state": state, 
            "current_task": task, "last_output": output[:200] if output else "",
            "cdol_round": cdol_round,
        })
    
    async def execute_task(self, task: TaskExecution):
        """Main execution loop with true CDoL 3-round protocol"""
        start_time = time.time()
        
        try:
            # === PHASE 0: Planning ===
            task.status = "planning"
            task.started_at = datetime.now().isoformat()
            await self.events.emit("task_update", {"task_id": task.id, "status": "planning"})
            await self.events.log(f"🚀 任务启动: \"{task.description[:60]}\"")
            await self.events.log(f"📋 计划执行 {task.max_steps} 步")
            
            # === PHASE 1: Coordinator routes ===
            await self._update_agent("coordinator", "thinking", "评估任务")
            await self.events.log("🧭 Coordinator 评估任务...")
            
            route, topology, participants = await self._plan_task(task.description, task.max_steps)
            task.route = route
            task.topology = topology
            task.participants = participants
            task.total_steps = task.max_steps
            
            # Select CDoL decomposition strategy
            # Use user's choice if provided and not "auto", otherwise auto-select
            if task.cdol_strategy and task.cdol_strategy != "auto":
                cdol_strategy = task.cdol_strategy
                strategy_reasoning = "用户手动指定"
                strategy_confidence = 1.0
                strategy_factors = ["用户选择"]
                await self.events.log(f"📋 使用用户选择的策略: {cdol_strategy}")
            else:
                strategy_result = select_decomposition_strategy(
                    task.description, 
                    self.insight_store.get_task_execution_history()
                )
                cdol_strategy = strategy_result["strategy"]
                strategy_reasoning = strategy_result["reasoning"]
                strategy_confidence = strategy_result["confidence"]
                strategy_factors = strategy_result["factors"]
            task.cdol_strategy = cdol_strategy
            
            await self.events.emit("task_plan", {
                "task_id": task.id,
                "route": route,
                "topology": topology,
                "participants": participants,
                "max_steps": task.max_steps,
                "cdol_strategy": cdol_strategy,
                "strategy_desc": DECOMPOSITION_STRATEGIES.get(cdol_strategy, {}).get("name", cdol_strategy),
                "strategy_reasoning": strategy_reasoning,
                "strategy_confidence": strategy_confidence,
                "strategy_factors": strategy_factors,
            })
            await self.events.emit("topology_change", {
                "topology": topology,
                "config": TOPOLOGY_CONFIGS.get(topology, {}),
            })
            await self.events.log(f"📡 路由: {route} | 拓扑: {topology} | CDoL策略: {cdol_strategy}")
            await self.events.log(f"🎯 策略依据: {strategy_reasoning}")
            await self.events.log(f"👥 参与者: {participants}")
            
            await self._update_agent("coordinator", "complete", output="路由完成")
            
            # === PHASE 2: CDoL Step-by-step execution ===
            task.status = "running"
            await self.events.emit("task_update", {"task_id": task.id, "status": "running"})
            
            context = {"task": task.description, "previous_steps": []}
            
            for step_num in range(1, task.max_steps + 1):
                task.current_step = step_num
                await self.events.emit("task_update", {
                    "task_id": task.id, "status": "running",
                    "current_step": step_num, "total_steps": task.max_steps,
                })
                await self.events.log(f"━━━ Step {step_num}/{task.max_steps} ━━━")
                
                # Dynamic topology per step
                step_topology = self._step_topology(step_num, task.max_steps, topology)
                if step_topology != task.topology:
                    task.topology = step_topology
                    await self.events.emit("topology_change", {
                        "topology": step_topology,
                        "config": TOPOLOGY_CONFIGS.get(step_topology, {}),
                        "step": step_num,
                    })
                    await self.events.log(f"🔄 拓扑切换 → {TOPOLOGY_CONFIGS.get(step_topology, {}).get('name', step_topology)}")
                
                # Execute CDoL step with true 3-round protocol
                step_result = await self._execute_cdol_step(
                    task, step_num, participants, step_topology, context, cdol_strategy
                )
                task.step_results.append(step_result)
                task.tokens_total += step_result.get("tokens", 0)
                task.cdol_rounds_completed += step_result.get("cdol_rounds", 0)
                
                # Update laziness detection metrics
                for agent_id, metrics in step_result.get("laziness_metrics", {}).items():
                    self.laziness_detector.record_step_metrics(agent_id, step_num, metrics)
                    laziness = self.laziness_detector.detect_laziness(agent_id)
                    if laziness["is_lazy"]:
                        task.laziness_alerts.append(laziness)
                        await self.events.log(f"  ⚠️ {agent_id} 懒惰检测: {', '.join(laziness['signals'])}")
                
                # Store false consensus warnings
                task.false_consensus_warnings.extend(step_result.get("false_consensus_warnings", []))
                
                # Update context for next step
                context["previous_steps"].append({
                    "step": step_num,
                    "summary": step_result.get("summary", "")[:200],
                })
                
                await self.events.emit("step_complete", {
                    "step": step_num,
                    "total_steps": task.max_steps,
                    "summary": step_result.get("summary", ""),
                    "cdol_rounds": step_result.get("cdol_rounds", 0),
                })
                
                await asyncio.sleep(0.5)
            
            # === PHASE 3: Final synthesis with FusionJudge ===
            task.status = "reviewing"
            await self.events.emit("task_update", {"task_id": task.id, "status": "reviewing"})
            await self.events.log("🔬 最终综合 (FusionJudge)...")
            
            final = await self._final_synthesis(task)
            task.final_result = final.get("answer", "")
            task.summary = final.get("summary", "")
            task.synergy_gain = await self._compute_synergy(task)
            
            # === 保存最终报告到输出目录 ===
            output_filename = f"{task.id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
            output_path = os.path.join(OUTPUT_DIR, output_filename)
            with open(output_path, "w", encoding="utf-8") as f:
                f.write(f"# {task.description[:80]}\n\n")
                f.write(f"> **NexusFlow CDoL Engine** | {task.max_steps} steps | {task.cdol_rounds_completed} CDoL rounds | {task.tokens_total:,} tokens | synergy {task.synergy_gain:.1f}\n\n")
                f.write(task.final_result)
            task.output_path = output_path
            await self.events.log(f"📄 报告已保存: {output_filename}")
            
            # === PHASE 4: Archivist distillation + InsightStore ===
            await self._update_agent("archivist", "thinking", "记忆蒸馏")
            await self.events.log("📚 Archivist 蒸馏经验...")
            
            # Record insight for future strategy selection
            self.insight_store.record({
                "task_type": task.route,
                "strategy": task.cdol_strategy,
                "success": task.status == "completed",
                "synergy_gain": task.synergy_gain,
                "participants": task.participants,
                "steps": task.max_steps,
            })
            
            await self._distill(task)
            await self._update_agent("archivist", "complete")
            
            # === DONE ===
            task.status = "completed"
            task.completed_at = datetime.now().isoformat()
            task.duration_seconds = time.time() - start_time
            
            output_filename = os.path.basename(task.output_path) if task.output_path else ""
            await self.events.emit("task_complete", {
                "task_id": task.id,
                "duration": task.duration_seconds,
                "tokens": task.tokens_total,
                "synergy_gain": task.synergy_gain,
                "result_preview": task.final_result[:300],
                "final_result": task.final_result,
                "output_file": output_filename,
                "steps": task.max_steps,
                "cdol_rounds_total": task.cdol_rounds_completed,
                "false_consensus_warnings": len(task.false_consensus_warnings),
                "laziness_alerts": len(task.laziness_alerts),
            })
            await self.events.log(f"✅ 任务完成 | {task.duration_seconds:.1f}s | {task.tokens_total} tokens")
            await self.events.log(f"   📊 协同增益: {task.synergy_gain:.2f} | CDoL轮次: {task.cdol_rounds_completed}")
            if task.false_consensus_warnings:
                await self.events.log(f"   ⚠️ 虚假一致警告: {len(task.false_consensus_warnings)}次")
            if task.laziness_alerts:
                await self.events.log(f"   ⚠️ 懒惰检测: {len(task.laziness_alerts)}次")
            
        except Exception as e:
            task.status = "failed"
            task.error = str(e)
            task.completed_at = datetime.now().isoformat()
            task.duration_seconds = time.time() - start_time
            await self.events.log(f"❌ 任务失败: {e}", level="error")
            await self.events.emit("task_failed", {"task_id": task.id, "error": str(e)})
            logger.error(f"Task failed: {e}\n{traceback.format_exc()}")
        
        finally:
            self.reset_agent_states()
            await self.events.emit("agents_reset", {})
    
    async def _plan_task(self, description: str, max_steps: int):
        """Coordinator: plan task execution with LLM routing"""
        if self.llm.providers:
            coord_def = self.agent_defs_map["coordinator"]
            try:
                resp = await self._call_llm("coordinator", [
                    {"role": "system", "content": coord_def["system_prompt"]},
                    {"role": "user", "content": f"请规划以下任务的执行方案（{max_steps}步）:\n\n{description}\n\n可用Agent: {', '.join(a['id'] for a in AGENT_DEFS)}"}
                ], temperature=0.3, max_tokens=800)
                
                content = resp["content"]
                json_match = re.search(r'\{[\s\S]*\}', content)
                if json_match:
                    plan = json.loads(json_match.group())
                    route = plan.get("route", "cdol" if max_steps > 2 else "simple")
                    topology = plan.get("topology", select_topology(description))
                    participants = plan.get("participants", TOPOLOGY_CONFIGS.get(topology, {}).get("active", []))
                    valid_ids = {a["id"] for a in AGENT_DEFS}
                    participants = [p for p in participants if p in valid_ids]
                    if not participants:
                        participants = TOPOLOGY_CONFIGS.get(topology, {}).get("active", ["coordinator"])
                    return route, topology, participants
            except Exception as e:
                logger.warning(f"LLM planning failed: {e}")
        
        topology = select_topology(description)
        participants = TOPOLOGY_CONFIGS.get(topology, {}).get("active", ["coordinator"])
        route = "cdol" if max_steps > 2 else "simple"
        return route, topology, participants
    
    def _step_topology(self, step: int, total: int, base_topology: str) -> str:
        """Dynamic topology per step"""
        if total <= 2:
            return base_topology
        
        progress = step / total
        if progress < 0.2:
            return "star"
        elif progress < 0.4:
            return "tree"
        elif progress < 0.6:
            return "mesh"
        elif progress < 0.8:
            return "chain"
        else:
            return "converge"
    
    async def _execute_cdol_step(self, task: TaskExecution, step_num: int,
                                  participants: List[str], topology: str,
                                  context: Dict, cdol_strategy: str) -> Dict:
        """
        Execute one step using TRUE CDoL 3-round protocol:
        Round 0: Independent reasoning → conclusions
        Round 1: Difference attribution (see others' conclusions, infer context)
        Round 2: Revised conclusions
        FusionJudge: Detect conflicts and merge
        """
        step_start = time.time()
        step_tokens = 0
        cdol_rounds_completed = 0
        false_consensus_warnings = []
        laziness_metrics = {}
        
        # Get step participants based on topology
        topology_config = TOPOLOGY_CONFIGS.get(topology, {})
        step_participants = topology_config.get("active", participants)
        valid_ids = {a["id"] for a in AGENT_DEFS}
        step_participants = [p for p in step_participants if p in valid_ids]
        if not step_participants:
            step_participants = participants
        
        # Build step context
        step_context = f"Step {step_num}/{task.total_steps}: "
        if context["previous_steps"]:
            prev = context["previous_steps"][-1]
            step_context += f"上一步结果: {prev['summary'][:100]}。"
        step_context += f"\n\n任务: {task.description}"
        
        # Agents for reasoning (exclude global/observer agents)
        reasoning_agents = [p for p in step_participants 
                           if p not in ("coordinator", "archivist", "observer", "monitor")]
        
        # === ROUND 0: Independent Reasoning ===
        await self.events.log(f"  🔄 CDoL Round 0: 独立推理 ({len(reasoning_agents)}个Agent)")
        cdol_rounds_completed += 1
        
        # Strategist decomposes perspective
        agent_tasks = {}
        if "strategist" in reasoning_agents:
            await self._update_agent("strategist", "thinking", f"Step {step_num} 视角分解", cdol_round=0)
            strategist_def = self.agent_defs_map["strategist"]
            resp = await self._call_llm("strategist", [
                {"role": "system", "content": strategist_def["system_prompt"]},
                {"role": "user", "content": f"使用'{cdol_strategy}'策略为以下步骤分解视角:\n{step_context}\n\n参与Agent: {reasoning_agents}\n\n{DECOMPOSITION_STRATEGIES.get(cdol_strategy, {}).get('desc', '')}"}
            ], temperature=0.4, max_tokens=800)
            step_tokens += resp.get("tokens", 0)
            
            try:
                json_match = re.search(r'\{[\s\S]*\}', resp["content"])
                if json_match:
                    strat_plan = json.loads(json_match.group())
                    perspectives = strat_plan.get("perspectives", {})
                    if isinstance(perspectives, dict) and perspectives:
                        agent_tasks = {k: str(v) for k, v in perspectives.items() if k in reasoning_agents}
                        await self.events.log(f"  🧩 Strategist 分解完成: {len(agent_tasks)}个视角")
            except Exception as e:
                logger.warning(f"Strategist parse failed: {e}")
            
            await self._update_agent("strategist", "waiting", output=resp["content"][:200], cdol_round=0)
        
        # Round 0: All reasoning agents independently infer
        round0_conclusions = {}
        non_critic_agents = [a for a in reasoning_agents if a != "strategist" and a != "critic"]
        
        for agent_id in non_critic_agents:
            adef = self.agent_defs_map.get(agent_id)
            if not adef:
                continue
            
            specific_task = agent_tasks.get(agent_id, "")
            prompt = f"{step_context}"
            if specific_task:
                prompt += f"\n\n【Strategist分配的专项任务】\n{specific_task}"
            else:
                prompt += f"\n\n请从{adef.get('label', agent_id)}的角度独立分析。"
            
            # 🔍 Researcher 联网搜索增强
            if agent_id == "researcher" and step_num <= 3:  # 前3步搜索，避免重复
                search_query = task.description[:100]
                if specific_task:
                    search_query = specific_task[:80]
                await self.events.log(f"  🔍 Researcher 联网搜索: \"{search_query}\"")
                search_results = await web_search(search_query, max_results=5)
                prompt += f"\n\n【联网搜索结果】\n{search_results}"
            
            await self._update_agent(agent_id, "thinking", f"Round 0 独立推理", cdol_round=0)
            await self.events.log(f"  {adef['icon']} {adef['label']} Round 0 推理中...")
            
            resp = await self._call_llm(agent_id, [
                {"role": "system", "content": adef["system_prompt"]},
                {"role": "user", "content": prompt}
            ], temperature=0.7, max_tokens=1500)
            
            round0_conclusions[agent_id] = resp["content"]
            step_tokens += resp.get("tokens", 0)
            
            # Record laziness metrics
            laziness_metrics[agent_id] = self.laziness_detector.compute_laziness_metrics(
                agent_id, resp["content"]
            )
            
            await self._update_agent(agent_id, "waiting", output=resp["content"][:200], cdol_round=0)
            await self.events.emit("agent_output", {
                "agent_id": agent_id,
                "step": step_num,
                "round": 0,
                "output": resp["content"][:400],
                "provider": resp.get("provider", "unknown"),
            })
        
        # Critic executes after Round 0 (as per Fix 5)
        if "critic" in reasoning_agents:
            critic_def = self.agent_defs_map.get("critic")
            if critic_def:
                await self._update_agent("critic", "thinking", f"Round 0 对抗质疑", cdol_round=0)
                await self.events.log(f"  🔥 Critic Round 0 对抗质疑...")
                
                crit_text = "\n\n".join([
                    f"[{aid}]: {c[:400]}" for aid, c in round0_conclusions.items()
                ])
                resp = await self._call_llm("critic", [
                    {"role": "system", "content": critic_def["system_prompt"]},
                    {"role": "user", "content": f"请质疑以下结论的假设、逻辑漏洞:\n{crit_text}"}
                ], temperature=0.5, max_tokens=1500)
                
                round0_conclusions["critic"] = resp["content"]
                step_tokens += resp.get("tokens", 0)
                laziness_metrics["critic"] = self.laziness_detector.compute_laziness_metrics(
                    "critic", resp["content"]
                )
                
                await self._update_agent("critic", "waiting", output=resp["content"][:200], cdol_round=0)
                await self.events.log(f"  🔥 Critic 完成")
        
        # === ROUND 1: Difference Attribution ===
        await self.events.log(f"  🔄 CDoL Round 1: 差异归因")
        cdol_rounds_completed += 1
        
        round1_attributions = {}
        for agent_id in reasoning_agents:
            if agent_id not in round0_conclusions:
                continue
            
            adef = self.agent_defs_map.get(agent_id)
            if not adef:
                continue
            
            # Build "other conclusions" text (STRICTLY no original perspective info)
            other_conclusions_text = "\n\n".join([
                f"### Agent {aid} 的结论:\n{con[:500]}"
                for aid, con in round0_conclusions.items() if aid != agent_id
            ])
            
            my_conclusion = round0_conclusions[agent_id]
            
            attr_prompt = f"""你的结论:\n{my_conclusion[:500]}

其他Agent的结论:\n{other_conclusions_text}

任务: 
1. 识别你与其他Agent结论之间的矛盾
2. 对每个矛盾进行归因：差异是因为你们看到了不同的证据？还是推理方法不同？
3. 尝试推断其他Agent可能拥有什么你没看到的信息
4. 如果必要，修正你的结论

请按JSON格式输出: {{"contradictions": [...], "attributions": [...], "revision": "...", "revision_reason": "..."}}"""
            
            await self._update_agent(agent_id, "thinking", f"Round 1 差异归因", cdol_round=1)
            resp = await self._call_llm(agent_id, [
                {"role": "system", "content": f"你是NexusFlow中{adef.get('label', agent_id)}，现在执行Round 1差异归因。"},
                {"role": "user", "content": attr_prompt}
            ], temperature=0.5, max_tokens=1000)
            
            round1_attributions[agent_id] = resp["content"]
            step_tokens += resp.get("tokens", 0)
            
            await self._update_agent(agent_id, "waiting", cdol_round=1)
            await self.events.log(f"  {adef['icon']} {adef['label']} Round 1 归因完成")
        
        # === ROUND 2: Revised Conclusions ===
        await self.events.log(f"  🔄 CDoL Round 2: 修正收敛")
        cdol_rounds_completed += 1
        
        round2_conclusions = {}
        for agent_id in reasoning_agents:
            if agent_id not in round1_attributions:
                round2_conclusions[agent_id] = round0_conclusions.get(agent_id, "")
                continue
            
            adef = self.agent_defs_map.get(agent_id)
            if not adef:
                continue
            
            my_attr = round1_attributions[agent_id]
            my_orig = round0_conclusions.get(agent_id, "")
            
            # Parse revision from attribution
            revision = None
            try:
                json_match = re.search(r'\{[\s\S]*\}', my_attr)
                if json_match:
                    attr_data = json.loads(json_match.group())
                    revision = attr_data.get("revision")
                    revision_reason = attr_data.get("revision_reason", "")
                    if revision:
                        await self.events.log(f"  ✏️ {adef['label']} Round 2 修正: {revision_reason[:50]}...")
            except:
                pass
            
            # Use revised conclusion if available
            round2_conclusions[agent_id] = revision if revision else my_orig
            
            await self._update_agent(agent_id, "waiting", cdol_round=2)
        
        # === FusionJudge: Conflict Detection ===
        await self.events.log(f"  ⚖️ FusionJudge: 矛盾检测与融合")
        
        fusion_result = await self.fusion_judge.detect_conflicts(
            round2_conclusions,
            self.agent_defs_map,
            self._call_llm
        )
        
        conflict_type = fusion_result.get("conflict_type", "")
        await self.events.log(f"  📊 冲突类型: {conflict_type}")
        
        if conflict_type == "false_consensus":
            warnings = fusion_result.get("warnings", [])
            false_consensus_warnings.extend(warnings)
            await self.events.log(f"  ⚠️ 虚假一致警告: {len(warnings)}个")
        
        # === Synthesis for this step ===
        step_summary = ""
        if round2_conclusions:
            if "synthesizer" in step_participants:
                await self._update_agent("synthesizer", "thinking", f"Step {step_num} 融合", cdol_round=2)
                synth_def = self.agent_defs_map["synthesizer"]
                
                conc_text = "\n\n".join([
                    f"### {self.agent_defs_map.get(aid, {}).get('label', aid)} (Round 2):\n{c[:800]}"
                    for aid, c in round2_conclusions.items() if aid in self.agent_defs_map
                ])
                
                fusion_note = ""
                if conflict_type == "false_consensus":
                    fusion_note = f"\n\n⚠️ FusionJudge检测到虚假一致，请分离为条件方案。警告: {fusion_result.get('details', [{}])[0].get('explanation', '')}"
                
                resp = await self._call_llm("synthesizer", [
                    {"role": "system", "content": synth_def["system_prompt"]},
                    {"role": "user", "content": f"任务: {task.description}\n步骤 {step_num}\n\n{conc_text}{fusion_note}\n\n请综合以上结论，给出统一结果。"}
                ], temperature=0.5, max_tokens=1500)
                
                step_summary = resp["content"]
                step_tokens += resp.get("tokens", 0)
                await self._update_agent("synthesizer", "complete", output=step_summary[:200], cdol_round=2)
            else:
                step_summary = "\n".join(round2_conclusions.values())
        
        # === Observer Meta-observation ===
        observer_note = ""
        if "observer" in step_participants and step_summary:
            obs_def = self.agent_defs_map.get("observer", {})
            if obs_def:
                await self._update_agent("observer", "thinking", f"Step {step_num} 元观察", cdol_round=2)
                conc_text = "\n\n".join([
                    f"[{aid}]: {c[:300]}" for aid, c in round2_conclusions.items()
                ])
                obs_prompt = f"本步CDoL三轮完成:\n{conc_text}\n\n融合结果:\n{step_summary[:800]}\n\n请从旁观者角度分析: 1)是否有认知偏见？2)是否有跨视角隐藏模式？"
                resp = await self._call_llm("observer", [
                    {"role": "system", "content": obs_def["system_prompt"]},
                    {"role": "user", "content": obs_prompt}
                ], temperature=0.5, max_tokens=800)
                observer_note = resp["content"][:1000]
                step_tokens += resp.get("tokens", 0)
                await self._update_agent("observer", "complete", output=observer_note[:200], cdol_round=2)
                await self.events.log(f"  👁 Observer 完成元观察")
        
        # === Monitor Health Check ===
        step_duration = time.time() - step_start
        monitor_metrics = {
            "duration_s": round(step_duration, 1),
            "tokens": step_tokens,
            "agents_active": len(round2_conclusions),
            "health": "ok" if step_duration < 120 else "slow"
        }
        
        if "monitor" in step_participants:
            mon_def = self.agent_defs_map.get("monitor", {})
            if mon_def:
                await self._update_agent("monitor", "thinking", f"Step {step_num} 健康检查", cdol_round=2)
                metrics_text = json.dumps(monitor_metrics, ensure_ascii=False)
                mon_prompt = f"系统指标: {metrics_text}\n\nCDoL轮次: {cdol_rounds_completed}\n冲突类型: {conflict_type}"
                resp = await self._call_llm("monitor", [
                    {"role": "system", "content": mon_def["system_prompt"]},
                    {"role": "user", "content": mon_prompt}
                ], temperature=0.3, max_tokens=500)
                monitor_report = resp["content"][:500]
                step_tokens += resp.get("tokens", 0)
                await self._update_agent("monitor", "complete", output=monitor_report[:200], cdol_round=2)
                await self.events.log(f"  📡 Monitor 健康度: {monitor_metrics['health']}")
        
        # Mark all agents complete
        for agent_id in reasoning_agents:
            await self._update_agent(agent_id, "complete", cdol_round=2)
        
        await self.events.log(f"  ✅ Step {step_num} 完成 (CDoL轮次: {cdol_rounds_completed})")
        
        return {
            "step": step_num,
            "round0_conclusions": {k: v[:2000] for k, v in round0_conclusions.items()},
            "round1_attributions": {k: v[:1000] for k, v in round1_attributions.items()},
            "round2_conclusions": {k: v[:2000] for k, v in round2_conclusions.items()},
            "conclusions": round2_conclusions,  # Use Round 2 conclusions as final
            "summary": step_summary[:3000],
            "tokens": step_tokens,
            "cdol_rounds": cdol_rounds_completed,
            "topology": topology,
            "participants": step_participants,
            "observer_note": observer_note,
            "conflict_type": conflict_type,
            "fusion_warnings": fusion_result.get("warnings", []),
            "false_consensus_warnings": false_consensus_warnings,
            "laziness_metrics": laziness_metrics,
        }
    
    async def _final_synthesis(self, task: TaskExecution) -> Dict:
        """Generate final answer from all CDoL step results"""
        if not task.step_results:
            return {"answer": "无执行结果", "summary": ""}
        
        all_summaries = "\n\n".join([
            f"### Step {s['step']}:\n{s['summary'][:2000]}"
            for s in task.step_results
        ])
        
        # FusionJudge final check
        final_conclusions = {}
        for s in task.step_results:
            if "round2_conclusions" in s:
                for aid, conc in s["round2_conclusions"].items():
                    final_conclusions[aid] = conc
        
        fusion_result = await self.fusion_judge.detect_conflicts(
            final_conclusions,
            self.agent_defs_map,
            self._call_llm
        )
        
        fusion_note = ""
        if fusion_result.get("conflict_type") == "false_consensus":
            fusion_note = f"\n\n⚠️ 最终FusionJudge检测: {fusion_result.get('details', [{}])[0].get('explanation', '')}"
        
        synth_def = self.agent_defs_map.get("synthesizer", {})
        resp = await self._call_llm("synthesizer", [
            {"role": "system", "content": synth_def.get("system_prompt", "综合所有步骤的结果，给出最终答案。")},
            {"role": "user", "content": f"原始任务: {task.description}\n\n{all_summaries}{fusion_note}\n\n请综合所有步骤的结果，给出完整、连贯的最终答案。"}
        ], temperature=0.4, max_tokens=4096)
        
        return {
            "answer": resp["content"],
            "summary": resp["content"][:200],
        }
    
    async def _compute_synergy(self, task: TaskExecution) -> float:
        """Calculate true synergy gain"""
        import math
        if not task.step_results:
            return 0.0
        
        total_synergy = 0.0
        valid_steps = 0
        
        for step in task.step_results:
            conclusions = step.get("round2_conclusions", step.get("conclusions", {}))
            summary = step.get("summary", "")
            
            if len(conclusions) < 2 or not summary:
                continue
            
            # Calculate uniqueness
            unique_fragments = set()
            for c in conclusions.values():
                words = c.lower().split()[:20]
                unique_fragments.update(words)
            
            coverage = len(unique_fragments) / max(sum(len(c.split()) for c in conclusions.values()), 1)
            synergy = (1.0 + math.log1p(len( conclusions))) * coverage
            total_synergy += synergy
            valid_steps += 1
        
        if valid_steps == 0:
            return 0.0
        
        return total_synergy / valid_steps
    
    async def _distill(self, task: TaskExecution):
        """Archivist distillation - distill experience from task execution"""
        archivist_def = self.agent_defs_map["archivist"]
        
        # Build comprehensive distillation prompt
        distill_prompt = f"""任务: {task.description}
路由: {task.route}
拓扑: {task.topology}
CDoL策略: {task.cdol_strategy}
参与者: {task.participants}
执行步数: {task.max_steps}
CDoL轮次: {task.cdol_rounds_completed}

协同增益: {task.synergy_gain:.2f}

最终结果:
{task.final_result[:2000]}

请从以上执行过程提取关键经验和教训，写入记忆系统。
"""
        
        resp = await self._call_llm("archivist", [
            {"role": "system", "content": archivist_def["system_prompt"]},
            {"role": "user", "content": distill_prompt}
        ], temperature=0.5, max_tokens=1500)
        
        await self.events.emit("archivist_distill", {
            "task_id": task.id,
            "distilled": resp["content"][:1000],
        })


# ============================================================================
# Agent Wrapper for Core Engine Integration
# ============================================================================

class _AgentWrapper:
    """Wrapper to make Dashboard agents compatible with core engine"""
    
    def __init__(self, agent_id: str, engine: 'NexusFlowEngine'):
        self.agent_id = agent_id
        self.engine = engine
    
    async def chat(self, prompt: str) -> str:
        """Simple chat wrapper for core engine"""
        adef = self.engine.agent_defs_map.get(self.agent_id, {})
        resp = await self.engine._call_llm(self.agent_id, [
            {"role": "system", "content": adef.get("system_prompt", "")},
            {"role": "user", "content": prompt}
        ])
        return resp.get("content", "")


# ============================================================================
# FastAPI Application
# ============================================================================

app = FastAPI(title="NexusFlow Dashboard", version="3.1")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

llm_router = LLMRouter()
engine: Optional[NexusFlowEngine] = None
events = EventBus()
tasks: Dict[str, TaskExecution] = {}
task_history: List[TaskExecution] = []
DASHBOARD_DIR = os.path.dirname(os.path.abspath(__file__))


@app.on_event("startup")
async def startup():
    global engine
    
    logger.info("=" * 50)
    logger.info("  NexusFlow Server v3.1 starting...")
    logger.info(f"  Core Engine: {'Enabled' if CORE_ENGINE_AVAILABLE else 'Disabled (Fallback)'}")
    logger.info("=" * 50)
    
    # Initialize LLM providers
    ollama = OllamaProvider()
    await ollama.start()
    llm_router.register("ollama", ollama)
    
    if DEEPSEEK_API_KEY and DEEPSEEK_API_KEY != "sk-xxx":
        deepseek = DeepSeekProvider(api_key=DEEPSEEK_API_KEY)
        await deepseek.start()
        llm_router.register("deepseek", deepseek)
        logger.info("✅ DeepSeek connected")
    else:
        logger.warning("⚠️  DeepSeek API key not set. Using Ollama only.")
    
    if await ollama.is_available():
        logger.info(f"✅ Ollama connected: {ollama.models}")
    else:
        logger.warning(f"⚠️  Ollama unreachable at {OLLAMA_URL}")
    
    # Assign models to agents
    for adef in AGENT_DEFS:
        prov = adef.get("provider", "ollama")
        model = adef.get("model", "flash")
        if prov == "deepseek":
            actual_model = DEEPSEEK_PRO_MODEL if model == "pro" else DEEPSEEK_FLASH_MODEL
        else:
            actual_model = OLLAMA_PRO_MODEL if model == "pro" else OLLAMA_FLASH_MODEL
        llm_router.assign_model(adef["id"], prov, actual_model)
    
    engine = NexusFlowEngine(llm_router, events)
    
    logger.info(f"📡 Dashboard: http://localhost:{SERVER_PORT}")
    logger.info(f"📡 API Docs:  http://localhost:{SERVER_PORT}/docs")
    logger.info("=" * 50)
    
    await events.emit("system_status", {
        "status": "online",
        "core_engine": CORE_ENGINE_AVAILABLE,
        "ollama": await ollama.is_available(),
        "ollama_models": ollama.models,
        "deepseek": bool(DEEPSEEK_API_KEY and DEEPSEEK_API_KEY != "sk-xxx"),
        "agents": engine.get_all_agents(),
    })


@app.on_event("shutdown")
async def shutdown():
    for p in llm_router.providers.values():
        await p.stop()


@app.get("/", response_class=HTMLResponse)
async def serve_dashboard():
    for fname in ["nexusflow-dashboard-v4.html", "nexusflow-dashboard-v3.html", "nexusflow-dashboard-v2.html"]:
        path = os.path.join(DASHBOARD_DIR, fname)
        if os.path.exists(path):
            return FileResponse(path, media_type="text/html")
    return HTMLResponse("<h1>Dashboard not found</h1>")


@app.get("/api/agents")
async def api_agents():
    return {"agents": engine.get_all_agents() if engine else AGENT_DEFS}

@app.get("/api/tasks")
async def api_tasks(limit: int = 20):
    return {"tasks": [asdict(t) for t in reversed(task_history[-limit:])]}

@app.get("/api/tasks/{task_id}")
async def api_task(task_id: str):
    if task_id not in tasks:
        raise HTTPException(404, "Not found")
    return asdict(tasks[task_id])

@app.get("/api/tasks/{task_id}/download")
async def api_download_output(task_id: str):
    """下载任务输出报告"""
    if task_id not in tasks:
        raise HTTPException(404, "Task not found")
    task = tasks[task_id]
    if not task.output_path or not os.path.exists(task.output_path):
        raise HTTPException(404, "No output file available")
    return FileResponse(
        task.output_path,
        media_type="text/markdown",
        filename=os.path.basename(task.output_path),
        headers={"Content-Disposition": f'attachment; filename="{os.path.basename(task.output_path)}"'}
    )

@app.get("/api/outputs")
async def api_list_outputs():
    """列出所有任务输出文件"""
    files = []
    if os.path.exists(OUTPUT_DIR):
        for f in sorted(os.listdir(OUTPUT_DIR), reverse=True):
            if f.endswith('.md'):
                fp = os.path.join(OUTPUT_DIR, f)
                files.append({
                    "filename": f,
                    "size": os.path.getsize(fp),
                    "created": datetime.fromtimestamp(os.path.getmtime(fp)).isoformat(),
                })
    return {"outputs": files}

@app.post("/api/tasks")
async def api_create_task(body: Dict):
    desc = body.get("description", "").strip()
    if not desc:
        raise HTTPException(400, "description required")
    
    max_steps = body.get("max_steps", 5)
    max_steps = max(1, min(1000, int(max_steps)))
    
    # Accept user-selected strategy (default: auto)
    strategy = body.get("strategy", "auto")
    
    task_id = f"task_{uuid.uuid4().hex[:8]}"
    task = TaskExecution(
        id=task_id,
        description=desc,
        max_steps=max_steps,
        created_at=datetime.now().isoformat(),
        cdol_strategy=strategy,  # Store user's choice
    )
    tasks[task_id] = task
    task_history.append(task)
    
    await events.emit("task_created", {"task_id": task_id, "description": desc, "max_steps": max_steps, "strategy": strategy})
    
    asyncio.create_task(engine.execute_task(task))
    
    return {"task_id": task_id, "status": "pending", "max_steps": max_steps, "strategy": strategy}

@app.get("/api/topology")
async def api_topology():
    return {"topologies": TOPOLOGY_CONFIGS}

@app.get("/api/strategies")
async def api_strategies():
    """Return 6 decomposition strategies"""
    return {"strategies": DECOMPOSITION_STRATEGIES}

@app.get("/api/system/status")
async def api_status():
    ollama = llm_router.providers.get("ollama")
    return {
        "status": "online",
        "core_engine": CORE_ENGINE_AVAILABLE,
        "ollama": await ollama.is_available() if ollama else False,
        "ollama_models": ollama.models if ollama else [],
        "deepseek": bool(DEEPSEEK_API_KEY and DEEPSEEK_API_KEY != "sk-xxx"),
        "agents": engine.get_all_agents() if engine else [],
        "active_tasks": sum(1 for t in tasks.values() if t.status in ("pending", "running", "planning", "reviewing")),
        "completed_tasks": sum(1 for t in tasks.values() if t.status == "completed"),
    }

@app.post("/api/system/refresh-models")
async def api_refresh_models():
    ollama = llm_router.providers.get("ollama")
    if ollama:
        await ollama.refresh_models()
    return {"ollama_models": ollama.models if ollama else [], "deepseek": bool(DEEPSEEK_API_KEY)}


@app.websocket("/ws/events")
async def ws_events(ws: WebSocket):
    await events.connect(ws)
    try:
        while True:
            data = await ws.receive_text()
            if data == "ping":
                await ws.send_json({"type": "pong"})
    except WebSocketDisconnect:
        events.disconnect(ws)
    except:
        events.disconnect(ws)


# ============================================================================
# Entry
# ============================================================================

if __name__ == "__main__":
    print(f"""
╔══════════════════════════════════════════════════════╗
║       NexusFlow Server v3.1 — Real Core Engine       ║
╠══════════════════════════════════════════════════════╣
║  Dashboard : http://localhost:{SERVER_PORT:<6}               ║
║  API Docs  : http://localhost:{SERVER_PORT}/docs          ║
║  Core Engine: {'Enabled' if CORE_ENGINE_AVAILABLE else 'Disabled (Fallback)':<37}║
║  Ollama    : {OLLAMA_URL:<36}     ║
║  DeepSeek  : {'configured' if DEEPSEEK_API_KEY else 'not set (Ollama only)':<36}     ║
╚══════════════════════════════════════════════════════╝
""")
    uvicorn.run(app, host=SERVER_HOST, port=SERVER_PORT, log_level="info")
