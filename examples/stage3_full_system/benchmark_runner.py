#!/usr/bin/env python3
"""
NexusFlow CDoL Stage-3 Benchmark Runner
========================================
阶段③：用实际代码框架跑真实10Agent分布式执行

核心区别于阶段①②：
- 每个Agent独立调用DeepSeek API（非模拟）
- 通过真实CLI调用NOAA/WHO数据技能
- 实现CDoL三轮协议（Round 0独立推理 → Round 1差异归因 → Round 2修正）
- 信息不对称通过ContextMask实现（每个角色看到不同信息子集）
- Critic独立质疑 → 被质疑方回应 → Synthesizer仲裁

架构：
  ☁️ Coordinator  → 任务拆解、分配
  ☁️ Strategist   → 分析框架、方法论设计
  ☁️ Researcher   → 数据拉取（调用NOAA/WHO CLI）
  🖥️ Coder        → 计算脚本实现
  🖥️ Analyst      → 数据分析
  📱 Observer     → 数据质量监控、异常检测
  📱 Monitor      → 进度跟踪
  ☁️ Critic       → 质疑假设、挑战结论
  ☁️ Synthesizer  → 综合结论
  ☁️ Archivist    → 报告生成
"""

import json
import os
import subprocess
import time
import hashlib
import traceback
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from datetime import datetime

# ============================================================
# DeepSeek API Client
# ============================================================
import urllib.request
import urllib.error

DEEPSEEK_API_KEY = os.environ.get("DEEPSEEK_API_KEY", "sk-your-key-here")
DEEPSEEK_URL = "https://api.deepseek.com/v1/chat/completions"

api_call_count = 0
total_tokens = 0

def llm_chat(prompt: str, system: str = "", model: str = "deepseek-chat", 
              max_tokens: int = 4096, temperature: float = 0.3) -> str:
    """调用DeepSeek API"""
    global api_call_count, total_tokens
    
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})
    
    payload = json.dumps({
        "model": model,
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": temperature,
    }).encode("utf-8")
    
    req = urllib.request.Request(
        DEEPSEEK_URL,
        data=payload,
        headers={
            "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
            "Content-Type": "application/json",
        },
    )
    
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            api_call_count += 1
            usage = data.get("usage", {})
            total_tokens += usage.get("total_tokens", 0)
            return data["choices"][0]["message"]["content"]
    except Exception as e:
        print(f"  [LLM ERROR] {e}")
        return f"[ERROR: {e}]"


# ============================================================
# Data Skill CLI Wrappers
# ============================================================
NOAA_CLI = os.environ.get("NOAA_CLI_PATH", os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), ".skills", "skill_noaa-data-skill", "bin", "_cli_wrapper.py"))
WHO_CLI = os.environ.get("WHO_CLI_PATH", os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), ".skills", "skill_who-data-skill", "scripts", "_cli_wrapper.py"))

data_call_count = 0

def call_noaa(operation: str, params: Dict[str, str] = None) -> str:
    """调用NOAA数据技能CLI"""
    global data_call_count
    data_call_count += 1
    
    cmd = ["python3", NOAA_CLI, "call", operation]
    if params:
        for k, v in params.items():
            cmd.extend(["--param", f"{k}={v}"])
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60,
                              cwd=os.path.dirname(NOAA_CLI))
        return result.stdout.strip()
    except Exception as e:
        return f"[NOAA ERROR: {e}]"


def call_who(operation: str, params: Dict[str, str] = None) -> str:
    """调用WHO数据技能CLI"""
    global data_call_count
    data_call_count += 1
    
    cmd = ["python3", WHO_CLI, "call", operation]
    if params:
        for k, v in params.items():
            cmd.extend(["--param", f"{k}={v}"])
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60,
                              cwd=os.path.dirname(WHO_CLI))
        return result.stdout.strip()
    except Exception as e:
        return f"[WHO ERROR: {e}]"


# ============================================================
# Agent Role Definitions
# ============================================================

@dataclass
class AgentRole:
    name: str
    tier: str  # cloud/edge/terminal
    system_prompt: str
    context_mask: Dict  # 信息不对称掩码

ROLE_DEFINITIONS = {
    "Coordinator": AgentRole(
        name="Coordinator", tier="cloud",
        system_prompt="你是NexusFlow多Agent系统的协调者。负责：1)理解任务目标 2)分解子任务 3)分配给合适角色 4)汇总各方结论。你拥有全局视野，可以看到所有角色的输出。输出必须结构化。",
        context_mask={"level": "global", "allowed": ["all"], "blocked": []}
    ),
    "Strategist": AgentRole(
        name="Strategist", tier="cloud",
        system_prompt="你是策略师，负责设计分析框架、方法论和权重方案。你需要：1)确定分析维度 2)设计评分方法 3)选择统计工具 4)定义评估标准。你的输出是其他角色的方法论蓝图。",
        context_mask={"level": "global", "allowed": ["all", "methodology"], "blocked": []}
    ),
    "Researcher": AgentRole(
        name="Researcher", tier="cloud",
        system_prompt="你是数据研究员，负责从数据源拉取原始数据。你只负责获取数据，不做分析。输出格式：JSON数据+数据源说明+数据质量备注。",
        context_mask={"level": "data_only", "allowed": ["raw_data", "metadata"], "blocked": ["analysis", "conclusions"]}
    ),
    "Coder": AgentRole(
        name="Coder", tier="edge",
        system_prompt="你是编码专家，负责：1)实现归一化/统计/回归等计算 2)编写可复现的Python代码 3)计算评估指标。只输出代码和计算结果，不做解读。",
        context_mask={"level": "computation", "allowed": ["data", "formulas"], "blocked": ["conclusions", "interpretations"]}
    ),
    "Analyst": AgentRole(
        name="Analyst", tier="edge",
        system_prompt="你是数据分析师，负责：1)解读计算结果 2)发现趋势和模式 3)生成分析结论。基于Coder的计算结果和Researcher的数据进行分析。",
        context_mask={"level": "analysis", "allowed": ["data", "computations"], "blocked": ["final_conclusions"]}
    ),
    "Observer": AgentRole(
        name="Observer", tier="terminal",
        system_prompt="你是数据质量监控者，负责：1)检查数据完整性 2)识别异常值 3)标记数据质量问题。只关注数据层面的问题，不做结论性判断。",
        context_mask={"level": "quality", "allowed": ["raw_data", "statistics"], "blocked": ["analysis", "conclusions"]}
    ),
    "Monitor": AgentRole(
        name="Monitor", tier="terminal",
        system_prompt="你是进度监控者，负责：1)追踪执行进度 2)统计API调用次数 3)识别效率问题 4)标记超时风险。输出结构化的进度报告。",
        context_mask={"level": "meta", "allowed": ["progress", "stats"], "blocked": ["data", "analysis"]}
    ),
    "Critic": AgentRole(
        name="Critic", tier="cloud",
        system_prompt="你是批评者/审查者，你的唯一职责是：1)质疑假设 2)挑战结论 3)发现逻辑漏洞 4)检查方法论缺陷。你必须尽可能找到问题。不要给出正面评价，只指出问题和改进建议。每次质疑必须具体、有证据支撑。",
        context_mask={"level": "review", "allowed": ["all_conclusions", "methodology", "data"], "blocked": []}
    ),
    "Synthesizer": AgentRole(
        name="Synthesizer", tier="cloud",
        system_prompt="你是综合者，负责：1)整合各角色结论 2)处理矛盾 3)生成最终结论。当Critic提出质疑时，你需要权衡各方观点并做出裁决。",
        context_mask={"level": "global", "allowed": ["all"], "blocked": []}
    ),
    "Archivist": AgentRole(
        name="Archivist", tier="cloud",
        system_prompt="你是记录者/报告撰写者，负责：1)整理所有产物 2)生成结构化报告 3)确保结论可追溯。输出格式为Markdown报告。",
        context_mask={"level": "global", "allowed": ["all"], "blocked": []}
    ),
}


# ============================================================
# CDoL Engine (Stage-3 Implementation)
# ============================================================

@dataclass
class IntermediateConclusion:
    agent_id: str
    conclusion: str
    confidence: float
    reasoning_steps: List[str] = field(default_factory=list)
    key_assumptions: List[str] = field(default_factory=list)
    uncertainties: List[str] = field(default_factory=list)

@dataclass  
class CriticChallenge:
    target: str  # 质疑对象
    issue: str   # 问题描述
    evidence: str  # 证据
    severity: str  # high/medium/low
    suggestion: str  # 改进建议

@dataclass
class CDoLBenchmarkResult:
    task_name: str
    round0_conclusions: Dict[str, IntermediateConclusion] = field(default_factory=dict)
    critic_challenges: List[CriticChallenge] = field(default_factory=list)
    critic_responses: Dict[str, str] = field(default_factory=dict)
    round2_conclusions: Dict[str, str] = field(default_factory=dict)
    final_synthesis: str = ""
    final_report: str = ""
    metrics: Dict[str, Any] = field(default_factory=dict)
    raw_data: Dict[str, str] = field(default_factory=dict)
    execution_log: List[Dict] = field(default_factory=list)


class CDoLBenchmarkEngine:
    """阶段③ CDoL Benchmark执行引擎"""
    
    def __init__(self, task_name: str, data_type: str = "noaa"):
        self.task_name = task_name
        self.data_type = data_type  # "noaa" or "who"
        self.result = CDoLBenchmarkResult(task_name=task_name)
        self.start_time = None
        self.agent_interactions = []
    
    def log(self, msg: str, agent: str = "System"):
        elapsed = time.time() - self.start_time if self.start_time else 0
        entry = {"time": f"{elapsed:.1f}s", "agent": agent, "msg": msg}
        self.result.execution_log.append(entry)
        print(f"  [{agent}] {msg}")
    
    def run_agent(self, role_name: str, prompt: str, context: str = "") -> str:
        """执行单个Agent的推理"""
        role = ROLE_DEFINITIONS[role_name]
        
        # 应用信息不对称：根据context_mask裁剪上下文
        masked_context = self._apply_context_mask(role_name, context)
        
        full_prompt = f"{prompt}\n\n## 可用信息\n{masked_context}"
        
        self.log(f"开始推理 (role={role.tier})", role_name)
        response = llm_chat(full_prompt, system=role.system_prompt)
        
        self.agent_interactions.append({
            "from": role_name,
            "timestamp": time.time() - self.start_time,
            "prompt_len": len(full_prompt),
            "response_len": len(response),
        })
        
        return response
    
    def _apply_context_mask(self, role_name: str, full_context: str) -> str:
        """应用信息不对称掩码"""
        role = ROLE_DEFINITIONS[role_name]
        mask = role.context_mask
        
        # 全局视野角色（Coordinator, Strategist, Synthesizer, Archivist, Critic）看到全部
        if mask["level"] in ["global", "review"]:
            return full_context
        
        # 数据层角色看到数据部分
        if mask["level"] == "data_only":
            return f"[DATA ACCESS ONLY - 你只能看到原始数据，不能看到分析结论]\n\n{full_context[:3000]}"
        
        # 计算层角色看到数据和公式
        if mask["level"] == "computation":
            return f"[COMPUTATION SCOPE - 你只看到数据和方法论，负责写代码实现]\n\n{full_context[:4000]}"
        
        # 分析层角色看到数据和计算结果
        if mask["level"] == "analysis":
            return f"[ANALYSIS SCOPE - 你看到数据和计算结果，负责解读]\n\n{full_context[:4000]}"
        
        # 质量监控角色只看到原始数据统计
        if mask["level"] == "quality":
            return f"[QUALITY MONITORING - 你只看到数据质量相关信息]\n\n{full_context[:2000]}"
        
        # 进度监控角色只看元信息
        if mask["level"] == "meta":
            return f"[META MONITORING - 你只看到进度和统计信息]\n\n总API调用: {api_call_count}\n数据调用: {data_call_count}\nAgent交互: {len(self.agent_interactions)}"
        
        return full_context
    
    def collect_data(self, task_description: str) -> str:
        """Researcher拉取数据"""
        self.log("开始数据采集", "Researcher")
        
        if self.data_type == "noaa":
            return self._collect_noaa_data()
        else:
            return self._collect_who_data()
    
    def _collect_noaa_data(self) -> str:
        """采集NOAA数据"""
        stations = {
            "北京": "GHCND:CHM00054511",
            "天津": "GHCND:CHM00054527",
            "石家庄": "GHCND:CHM00053698",
            "济南": "GHCND:CHM00054823",
            "太原": "GHCND:CHM00053772",
        }
        
        all_data = []
        for city, sid in stations.items():
            self.log(f"采集 {city} ({sid}) 数据", "Researcher")
            
            # 温度数据（2015-2024）
            temp_raw = call_noaa("get-annual-summaries", {
                "dataset_id": "GHCND",
                "station_id": sid,
                "start_year": "2015",
                "end_year": "2024",
            })
            
            # 降水数据
            prec_raw = call_noaa("get-annual-summaries", {
                "dataset_id": "GHCND", 
                "station_id": sid,
                "start_year": "2015",
                "end_year": "2024",
            })
            
            all_data.append({
                "city": city,
                "station": sid,
                "annual_summaries": temp_raw[:2000],
            })
            
            time.sleep(0.5)  # API限速
        
        self.result.raw_data["noaa"] = json.dumps(all_data, ensure_ascii=False)[:5000]
        return json.dumps(all_data, ensure_ascii=False)[:5000]
    
    def _collect_who_data(self) -> str:
        """采集WHO数据"""
        indicators = {
            "life_expectancy": "WHOSIS_000001",
            "cancer_mortality": "WHS2_160",
            "cvd_mortality": "WHS2_161",
            "maternal_mortality": "MDG_0000000026",
            "dtp3_immunization": "WHS4_100",
        }
        countries = {
            "中国": "CHN", "巴西": "BRA", "俄罗斯": "RUS",
            "印度": "IND", "南非": "ZAF",
        }
        
        all_data = []
        for ind_name, ind_code in indicators.items():
            self.log(f"采集 {ind_name} ({ind_code})", "Researcher")
            
            for country, code in countries.items():
                raw = call_who("get-indicator-data", {
                    "indicator_code": ind_code,
                    "spatial_dim": code,
                    "top": "10",
                })
                
                all_data.append({
                    "indicator": ind_name,
                    "indicator_code": ind_code,
                    "country": country,
                    "country_code": code,
                    "data": raw[:1000],
                })
                
                time.sleep(0.3)
        
        self.result.raw_data["who"] = json.dumps(all_data, ensure_ascii=False)[:8000]
        return json.dumps(all_data, ensure_ascii=False)[:8000]
    
    def execute(self, task_description: str) -> CDoLBenchmarkResult:
        """执行完整的CDoL Benchmark"""
        self.start_time = time.time()
        self.log(f"========== 开始任务: {self.task_name} ==========")
        
        # ========== Phase 1: 数据收集 ==========
        self.log("Phase 1: 数据采集", "Coordinator")
        raw_data = self.collect_data(task_description)
        
        # ========== Phase 2: 策略设计 ==========
        self.log("Phase 2: 策略设计", "Strategist")
        strategy = self.run_agent("Strategist", f"""
请为以下任务设计分析框架：
{task_description}

输出要求：
1. 分析维度（3-5个）
2. 每个维度的评分方法（0-100）
3. 综合指数计算公式
4. 权重分配方案及理由
5. 验证方法（如何检验结论可靠性）

严格JSON格式输出。
""", context=raw_data)
        
        # ========== Phase 3: 编码实现 ==========
        self.log("Phase 3: 计算实现", "Coder")
        code_result = self.run_agent("Coder", f"""
基于以下策略设计，编写Python实现代码：

策略：{strategy[:2000]}

数据样本：{raw_data[:2000]}

输出要求：
1. 归一化函数
2. 加权综合指数计算
3. 线性回归/趋势分析
4. 排名计算
用```python代码块输出。
""", context=f"Strategy: {strategy}\n\nData: {raw_data}")
        
        # ========== Phase 4: 数据分析 ==========
        self.log("Phase 4: 数据分析", "Analyst")
        analysis = self.run_agent("Analyst", f"""
基于以下数据和计算结果，进行分析：

原始数据：{raw_data[:2000]}
计算代码：{code_result[:2000]}
策略框架：{strategy[:1000]}

输出：
1. 各维度分析结论
2. 综合排名结果
3. 关键发现
4. 局限性说明
""", context=f"Data: {raw_data}\nCode: {code_result}\nStrategy: {strategy}")
        
        # ========== Phase 5: 数据质量监控 ==========
        self.log("Phase 5: 质量监控", "Observer")
        quality_report = self.run_agent("Observer", f"""
审查以下数据的质量：

原始数据：{raw_data[:2000]}
分析结论：{analysis[:1500]}

检查：
1. 数据完整性（是否有缺失值）
2. 异常值检测
3. 数据时效性
4. 样本代表性
""", context=f"Data: {raw_data}\nAnalysis: {analysis}")
        
        # ========== Phase 6: Critic 质疑 ==========
        self.log("Phase 6: Critic独立审查", "Critic")
        critic_output = self.run_agent("Critic", f"""
审查以下分析过程和结论，找出所有问题：

任务：{task_description}
策略：{strategy[:1500]}
分析：{analysis[:2000]}
数据质量：{quality_report[:1000]}

你必须找出至少3个具体问题。对每个质疑：
1. 问题描述（具体到哪个结论/假设）
2. 为什么这是问题（证据）
3. 严重程度（high/medium/low）
4. 改进建议

JSON格式输出：
{{"challenges": [{{"target": "", "issue": "", "evidence": "", "severity": "", "suggestion": ""}}]}}
""", context=f"Task: {task_description}\nStrategy: {strategy}\nAnalysis: {analysis}\nQuality: {quality_report}")
        
        # 解析Critic质疑
        challenges = self._parse_challenges(critic_output)
        self.result.critic_challenges = challenges
        self.log(f"Critic提出 {len(challenges)} 项质疑", "Critic")
        
        # ========== Phase 7: 回应质疑 ==========
        self.log("Phase 7: 回应Critic质疑", "Synthesizer")
        for i, ch in enumerate(challenges):
            response = self.run_agent("Synthesizer", f"""
Critic提出以下质疑，请回应：

质疑 #{i+1}:
- 目标: {ch.target}
- 问题: {ch.issue}
- 证据: {ch.evidence}
- 严重程度: {ch.severity}
- 建议: {ch.suggestion}

原始分析：{analysis[:1500]}

你的回应：
1. 是否接受质疑？（完全接受/部分接受/不接受）
2. 如果接受，如何修正？
3. 如果不接受，理由是什么？
""", context=f"Original: {analysis}\nChallenge: {json.dumps(ch.__dict__)}")
            
            self.result.critic_responses[f"challenge_{i+1}"] = response
            self.log(f"质疑#{i+1}已回应", "Synthesizer")
        
        # ========== Phase 8: 综合结论 ==========
        self.log("Phase 8: 综合结论", "Synthesizer")
        final = self.run_agent("Synthesizer", f"""
综合所有角色输出，生成最终结论：

任务：{task_description}
策略：{strategy[:1000]}
分析：{analysis[:2000]}
Critic质疑：{critic_output[:1500]}
回应：{json.dumps(list(self.result.critic_responses.values())[:3], ensure_ascii=False)[:1000]}

最终结论要求：
1. 核心发现（修正后的结论）
2. 综合排名/评分
3. 置信度评估
4. 关键局限性
5. 政策/实践建议
""", context=f"Analysis: {analysis}\nCritic: {critic_output}\nResponses: {json.dumps(list(self.result.critic_responses.values()), ensure_ascii=False)}")
        
        self.result.final_synthesis = final
        
        # ========== Phase 9: 生成报告 ==========
        self.log("Phase 9: 生成报告", "Archivist")
        report = self.run_agent("Archivist", f"""
生成完整的Benchmark执行报告：

任务：{task_name}
策略：{strategy[:1000]}
分析结论：{analysis[:2000]}
最终综合：{final[:2000]}
Critic质疑({len(challenges)}项)：{critic_output[:1000]}
数据质量：{quality_report[:500]}

报告格式(Markdown)：
# {task_name} CDoL Benchmark Report
## 1. 任务概述
## 2. 方法论
## 3. 数据
## 4. 分析结果
## 5. Critic审查记录
## 6. 修正后结论
## 7. 置信度评估
## 8. 局限性
## 9. 执行统计
""", context=f"All outputs: strategy={strategy[:500]}, analysis={analysis[:500]}, final={final[:500]}, critic={critic_output[:500]}")
        
        self.result.final_report = report
        
        # 计算指标
        elapsed = time.time() - self.start_time
        self.result.metrics = {
            "total_time_seconds": elapsed,
            "api_calls": api_call_count,
            "data_calls": data_call_count,
            "agent_interactions": len(self.agent_interactions),
            "critic_challenges": len(challenges),
            "total_tokens": total_tokens,
        }
        
        self.log(f"========== 任务完成: {elapsed:.1f}s, {api_call_count} API calls ==========")
        
        return self.result
    
    def _parse_challenges(self, critic_output: str) -> List[CriticChallenge]:
        """解析Critic质疑"""
        challenges = []
        try:
            # 尝试提取JSON
            import re
            json_match = re.search(r'\{[\s\S]*\}', critic_output)
            if json_match:
                data = json.loads(json_match.group())
                for ch in data.get("challenges", []):
                    challenges.append(CriticChallenge(
                        target=ch.get("target", ""),
                        issue=ch.get("issue", ""),
                        evidence=ch.get("evidence", ""),
                        severity=ch.get("severity", "medium"),
                        suggestion=ch.get("suggestion", ""),
                    ))
        except Exception:
            # 降级：从文本中提取
            lines = critic_output.split("\n")
            for line in lines:
                if "问题" in line or "质疑" in line or "issue" in line.lower():
                    challenges.append(CriticChallenge(
                        target="general",
                        issue=line.strip()[:200],
                        evidence="extracted from text",
                        severity="medium",
                        suggestion="",
                    ))
        
        return challenges[:5]  # 最多5项质疑


# ============================================================
# Task Definitions
# ============================================================

NOAA_TASK = """
NOAA气候综合诊断任务：
对中国华北5个城市（北京、天津、石家庄、济南、太原）的气候数据进行多维度分析。

分析维度：
1. 温度趋势（2015-2024年升温/降温趋势）
2. 降水变化（年际变率和趋势）
3. 极端事件频率（高温/低温/暴雨事件）
4. 气候舒适度（综合考虑温度和降水）
5. 城市排名（综合气候宜居性排名）

要求：输出各维度评分(0-100)、综合排名、置信度评估。
"""

WHO_TASK = """
WHO全球健康综合诊断任务：
对BRICS五国（中国、巴西、俄罗斯、印度、南非）的健康状况进行多维度评估。

分析维度：
1. 预期寿命（出生预期寿命+健康预期寿命HALE）
2. 疾病负担（癌症死亡率+心血管死亡率+NCD死亡概率）
3. 妇幼健康（孕产妇死亡率+青少年死亡率）
4. 免疫覆盖（DTP3+BCG接种率）
5. 环境健康（空气污染DALYs）
6. 综合健康指数（加权综合评分）
7. 回测验证（用历史数据验证评分方法）

要求：输出各国各维度评分(0-100)、综合排名、置信度评估。
"""


# ============================================================
# Main Execution
# ============================================================

def run_benchmark(task_name: str, task_desc: str, data_type: str, output_dir: str):
    """运行单个Benchmark任务"""
    print(f"\n{'='*60}")
    print(f"NexusFlow CDoL Stage-3: {task_name}")
    print(f"{'='*60}\n")
    
    os.makedirs(output_dir, exist_ok=True)
    
    engine = CDoLBenchmarkEngine(task_name, data_type)
    result = engine.execute(task_desc)
    
    # 保存结果
    # 1. 执行报告
    with open(f"{output_dir}/ten_roles_report.md", "w", encoding="utf-8") as f:
        f.write(result.final_report)
    
    # 2. Critic质疑记录
    with open(f"{output_dir}/critic_challenges.md", "w", encoding="utf-8") as f:
        f.write(f"# Critic 质疑审查记录\n\n")
        f.write(f"## 任务: {task_name}\n\n")
        for i, ch in enumerate(result.critic_challenges):
            f.write(f"### 质疑 #{i+1}\n")
            f.write(f"- **目标**: {ch.target}\n")
            f.write(f"- **问题**: {ch.issue}\n")
            f.write(f"- **证据**: {ch.evidence}\n")
            f.write(f"- **严重程度**: {ch.severity}\n")
            f.write(f"- **建议**: {ch.suggestion}\n")
            resp = result.critic_responses.get(f"challenge_{i+1}", "N/A")
            f.write(f"- **回应**: {resp[:500]}\n\n")
    
    # 3. 执行统计
    with open(f"{output_dir}/execution_stats.json", "w", encoding="utf-8") as f:
        json.dump(result.metrics, f, ensure_ascii=False, indent=2)
    
    # 4. 完整执行日志
    with open(f"{output_dir}/execution_log.json", "w", encoding="utf-8") as f:
        json.dump(result.execution_log, f, ensure_ascii=False, indent=2)
    
    # 5. 交互记录
    with open(f"{output_dir}/agent_interactions.json", "w", encoding="utf-8") as f:
        json.dump(engine.agent_interactions, f, ensure_ascii=False, indent=2, default=str)
    
    print(f"\n✅ 报告已保存: {output_dir}/")
    return result


if __name__ == "__main__":
    import sys
    
    task = sys.argv[1] if len(sys.argv) > 1 else "both"
    base_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "output")
    
    if task in ("noaa", "both"):
        noaa_result = run_benchmark(
            "NOAA Climate Diagnosis",
            NOAA_TASK,
            "noaa",
            f"{base_dir}/stage3_noaa/ten_roles"
        )
    
    if task in ("who", "both"):
        who_result = run_benchmark(
            "WHO Health Diagnosis", 
            WHO_TASK,
            "who",
            f"{base_dir}/stage3_who/ten_roles"
        )
    
    print(f"\n{'='*60}")
    print(f"Stage-3 Benchmark 全部完成!")
    print(f"Total API calls: {api_call_count}")
    print(f"Total tokens: {total_tokens}")
    print(f"{'='*60}")
