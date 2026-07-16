#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
NexusFlow v2.8 — 真实端到端 Demo
===================================
用中文研究"低碳水泥的3个关键技术方向"

5 Agent 协作流程：
  Planner → Researcher → Critic → Synthesizer → Assayer

每个 Agent 真实调用 DeepSeek API，
调度器根据 privacy_level / context_window 选择 Edge / Fog / Cloud 层。

运行:  python examples/demo_real_e2e.py
产出:  终端彩色报告 + examples/demo_dashboard_report.html
"""

import json
import os
import sys
import time
import uuid
import requests
from datetime import datetime
from typing import Dict, List, Any, Optional

# ── 路径设置 ──────────────────────────────────────────────────────────────
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO_ROOT)

from nexusflow.core.edge_cloud_scheduler import (
    EdgeCloudScheduler, DeployTier, SchedulingPolicy, TierResource, SchedulingDecision,
)
from nexusflow.core.dynamic_router import (
    DynamicTopologyRouter, AgentCapabilityProfile, TaskRequirement, TaskComplexity,
    AgentLoadState,
)

# ── DeepSeek API 配置 ──────────────────────────────────────────────────────
DEEPSEEK_API_KEY = os.environ.get(
    "DEEPSEEK_API_KEY", ""
)
DEEPSEEK_ENDPOINT = "https://api.deepseek.com/chat/completions"
DEEPSEEK_MODEL = "deepseek-chat"

# ── 终端颜色 ──────────────────────────────────────────────────────────────
class C:
    RESET  = "\033[0m"
    BOLD   = "\033[1m"
    DIM    = "\033[2m"
    RED    = "\033[91m"
    GREEN  = "\033[92m"
    YELLOW = "\033[93m"
    BLUE   = "\033[94m"
    MAGENTA= "\033[95m"
    CYAN   = "\033[96m"
    WHITE  = "\033[97m"
    BG_BLK = "\033[40m"
    BG_BLU = "\033[44m"

def banner(text: str, color: str = C.CYAN):
    width = 72
    print(f"\n{color}{C.BOLD}{'═' * width}{C.RESET}")
    print(f"{color}{C.BOLD}  {text}{C.RESET}")
    print(f"{color}{C.BOLD}{'═' * width}{C.RESET}\n")

def step_banner(idx: int, total: int, agent_name: str, tier: str, color: str = C.CYAN):
    print(f"\n{color}{C.BOLD}┌{'─' * 70}┐{C.RESET}")
    print(f"{color}{C.BOLD}│ Step {idx}/{total}  🤖 {agent_name:<20s}  ☁ Tier: {tier:<8s}   │{C.RESET}")
    print(f"{color}{C.BOLD}└{'─' * 70}┘{C.RESET}")

def kv_line(key: str, value: str, key_color=C.YELLOW, val_color=C.WHITE):
    print(f"  {key_color}{key:<22s}{C.RESET} {val_color}{value}{C.RESET}")

# ── Agent 定义 ──────────────────────────────────────────────────────────────
AGENT_DEFS = [
    {
        "id": "planner",
        "name": "Planner（任务规划师）",
        "role": "planner",
        "tier": "edge",
        "capabilities": ["planning", "task_decomposition", "scheduling"],
        "domains": ["project_management", "research_methodology"],
        "privacy_level": 0,
        "context_window": 2048,        # 小上下文→Edge层可满足
        "reasoning_depth": 0.6,
        "creativity": 0.3,
        "system_prompt": (
            "你是一个任务规划专家。用户会给你一个研究主题，你需要：\n"
            "1. 将主题分解为3个具体的子方向\n"
            "2. 每个子方向用一句话概括核心问题\n"
            "3. 说明这三个方向之间的逻辑关系\n\n"
            "输出格式：\n"
            "## 研究规划\n"
            "### 方向一：[标题]\n[1-2句说明]\n"
            "### 方向二：[标题]\n[1-2句说明]\n"
            "### 方向三：[标题]\n[1-2句说明]\n"
            "### 方向间逻辑\n[1-2句说明]"
        ),
    },
    {
        "id": "researcher",
        "name": "Researcher（文献研究员）",
        "role": "researcher",
        "tier": "cloud",
        "capabilities": ["literature_analysis", "knowledge_synthesis", "evidence_extraction"],
        "domains": ["materials_science", "cement_chemistry", "sustainability"],
        "privacy_level": 0,
        "context_window": 65536,       # 大上下文→仅Cloud层可满足
        "reasoning_depth": 0.8,
        "creativity": 0.4,
        "system_prompt": (
            "你是一位材料科学文献研究员。你会收到一个规划师制定的研究方向，请针对每个方向：\n"
            "1. 阐述当前主流技术路线和关键突破\n"
            "2. 列举1-2个代表性方法/材料\n"
            "3. 简述技术优势与局限性\n\n"
            "输出格式：\n"
            "## 文献分析\n"
            "### 方向一分析\n- 主流路线：...\n- 代表方法：...\n- 优劣势：...\n"
            "（方向二、三同理）"
        ),
    },
    {
        "id": "critic",
        "name": "Critic（批判性审查）",
        "role": "critic",
        "tier": "fog",
        "capabilities": ["critical_thinking", "risk_assessment", "gap_analysis"],
        "domains": ["methodology_critique", "research_evaluation"],
        "privacy_level": 0,
        "context_window": 16384,       # 中等上下文→Fog层可满足
        "reasoning_depth": 0.9,
        "creativity": 0.5,
        "system_prompt": (
            "你是一位批判性审查专家。你会收到规划师和研究员的分析结果，请对每个方向提出：\n"
            "1. 关键质疑点（技术可行性/数据支撑/适用范围）\n"
            "2. 可能被忽略的风险或盲区\n"
            "3. 改进建议（1-2句）\n\n"
            "输出格式：\n"
            "## 批判性审查\n"
            "### 方向一质疑\n- 关键质疑：...\n- 潜在盲区：...\n- 改进建议：...\n"
            "（方向二、三同理）"
        ),
    },
    {
        "id": "synthesizer",
        "name": "Synthesizer（综合整合师）",
        "role": "synthesizer",
        "tier": "cloud",
        "capabilities": ["synthesis", "report_writing", "consensus_building"],
        "domains": ["interdisciplinary_synthesis", "science_communication"],
        "privacy_level": 0,
        "context_window": 65536,       # 大上下文→仅Cloud层可满足
        "reasoning_depth": 0.7,
        "creativity": 0.6,
        "system_prompt": (
            "你是一位综合整合师。你会收到规划师的方向、研究员的分析和审查员的质疑，请：\n"
            "1. 综合三方信息，为每个方向形成最终结论（2-3句）\n"
            "2. 回应审查员的关键质疑\n"
            "3. 给出三个方向的整体优先级排序并说明理由\n\n"
            "输出格式：\n"
            "## 综合报告\n"
            "### 方向一结论\n[综合结论+质疑回应]\n"
            "（方向二、三同理）\n"
            "### 优先级排序\n1. [方向] — 理由\n2. [方向] — 理由\n3. [方向] — 理由"
        ),
    },
    {
        "id": "assayer",
        "name": "Assayer（数据检验）",
        "role": "assayer",
        "tier": "fog",
        "capabilities": ["data_validation", "evidence_assessment", "fact_checking"],
        "domains": ["data_quality", "statistical_analysis"],
        "privacy_level": 0,
        "context_window": 16384,       # 中等上下文→Fog层可满足
        "reasoning_depth": 0.8,
        "creativity": 0.2,
        "system_prompt": (
            "你是一位数据检验专家。你会收到综合整合师的最终报告，请评估：\n"
            "1. 每个方向结论的数据支撑是否充分（充分/一般/不足）\n"
            "2. 是否存在过度推断的逻辑跳跃\n"
            "3. 整体报告的可靠性评级（A/B/C）及一句话总评\n\n"
            "输出格式：\n"
            "## 数据检验报告\n"
            "### 方向一数据评估\n- 支撑充分度：[充分/一般/不足]\n- 逻辑跳跃：...\n"
            "（方向二、三同理）\n"
            "### 整体可靠性\n- 评级：[A/B/C]\n- 总评：[一句话]"
        ),
    },
]

# ── DeepSeek API 调用 ────────────────────────────────────────────────────────
def call_deepseek(system_prompt: str, user_content: str, max_tokens: int = 800) -> Dict[str, Any]:
    """调用 DeepSeek API，返回 {text, usage, latency_ms}"""
    headers = {
        "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": DEEPSEEK_MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user",   "content": user_content},
        ],
        "max_tokens": max_tokens,
        "temperature": 0.7,
    }
    t0 = time.time()
    resp = requests.post(DEEPSEEK_ENDPOINT, headers=headers, json=payload, timeout=60)
    latency = (time.time() - t0) * 1000

    if resp.status_code != 200:
        raise RuntimeError(f"DeepSeek API error {resp.status_code}: {resp.text[:300]}")

    data = resp.json()
    text = data["choices"][0]["message"]["content"]
    usage = data.get("usage", {})

    return {
        "text": text,
        "prompt_tokens": usage.get("prompt_tokens", 0),
        "completion_tokens": usage.get("completion_tokens", 0),
        "total_tokens": usage.get("total_tokens", 0),
        "latency_ms": round(latency, 1),
    }


# ── 调度辅助 ────────────────────────────────────────────────────────────────
def tier_display(tier: DeployTier) -> str:
    mapping = {DeployTier.EDGE: "Edge ⚡", DeployTier.FOG: "Fog 🌫", DeployTier.CLOUD: "Cloud ☁"}
    return mapping.get(tier, str(tier))

def tier_color(tier: DeployTier) -> str:
    mapping = {DeployTier.EDGE: C.GREEN, DeployTier.FOG: C.YELLOW, DeployTier.CLOUD: C.BLUE}
    return mapping.get(tier, C.WHITE)


# ── HTML 报告生成 ────────────────────────────────────────────────────────────
def generate_html_report(exec_data: Dict[str, Any], output_path: str):
    """生成深色科技风格的 Dashboard 可视化报告"""

    agents_json = json.dumps(exec_data["agents"], ensure_ascii=False, indent=2)
    steps_json  = json.dumps(exec_data["steps"], ensure_ascii=False, indent=2)
    stats_json  = json.dumps(exec_data["stats"], ensure_ascii=False, indent=2)
    resources_json = json.dumps(exec_data["resources"], ensure_ascii=False, indent=2)
    final_conclusion = exec_data.get("final_conclusion", "")

    html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>NexusFlow v2.8 — 端边云协作 Dashboard</title>
<style>
  :root {{
    --bg: #0d0d1a;
    --bg2: #1a1a2e;
    --bg3: #16213e;
    --accent: #00d4ff;
    --accent2: #7b2ff7;
    --accent3: #00ff88;
    --text: #e0e0e0;
    --text2: #a0a0b0;
    --border: #2a2a4a;
    --card: rgba(26,26,46,0.9);
  }}
  * {{ margin: 0; padding: 0; box-sizing: border-box; }}
  body {{
    font-family: 'SF Pro Display', -apple-system, 'Segoe UI', Roboto, sans-serif;
    background: var(--bg);
    color: var(--text);
    min-height: 100vh;
  }}
  .header {{
    background: linear-gradient(135deg, #0d0d1a 0%, #1a1a2e 50%, #16213e 100%);
    border-bottom: 1px solid var(--border);
    padding: 24px 40px;
    display: flex;
    align-items: center;
    gap: 20px;
  }}
  .logo {{
    font-size: 28px;
    font-weight: 800;
    background: linear-gradient(90deg, var(--accent), var(--accent2));
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    letter-spacing: 2px;
  }}
  .logo-sub {{ font-size: 13px; color: var(--text2); margin-left: 12px; }}
  .badge {{
    display: inline-block;
    padding: 3px 10px;
    border-radius: 12px;
    font-size: 11px;
    font-weight: 600;
    margin-left: 8px;
  }}
  .badge-edge {{ background: rgba(0,255,136,0.15); color: var(--accent3); }}
  .badge-fog {{ background: rgba(255,200,0,0.15); color: #ffc800; }}
  .badge-cloud {{ background: rgba(0,212,255,0.15); color: var(--accent); }}

  .container {{ max-width: 1400px; margin: 0 auto; padding: 24px; }}

  .tabs {{
    display: flex;
    gap: 4px;
    margin-bottom: 24px;
    border-bottom: 2px solid var(--border);
    padding-bottom: 0;
  }}
  .tab {{
    padding: 10px 24px;
    cursor: pointer;
    font-size: 14px;
    font-weight: 600;
    color: var(--text2);
    border-bottom: 3px solid transparent;
    transition: all 0.2s;
    user-select: none;
  }}
  .tab:hover {{ color: var(--text); }}
  .tab.active {{ color: var(--accent); border-bottom-color: var(--accent); }}

  .panel {{ display: none; }}
  .panel.active {{ display: block; }}

  .card {{
    background: var(--card);
    border: 1px solid var(--border);
    border-radius: 12px;
    padding: 20px;
    margin-bottom: 20px;
  }}
  .card-title {{
    font-size: 16px;
    font-weight: 700;
    color: var(--accent);
    margin-bottom: 16px;
    padding-bottom: 8px;
    border-bottom: 1px solid var(--border);
  }}

  table {{
    width: 100%;
    border-collapse: collapse;
    font-size: 13px;
  }}
  th {{
    background: var(--bg3);
    padding: 10px 14px;
    text-align: left;
    font-weight: 600;
    color: var(--accent);
    border-bottom: 1px solid var(--border);
  }}
  td {{
    padding: 10px 14px;
    border-bottom: 1px solid rgba(42,42,74,0.5);
    color: var(--text);
  }}
  tr:hover {{ background: rgba(0,212,255,0.03); }}

  .metric-grid {{
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
    gap: 16px;
    margin-bottom: 20px;
  }}
  .metric-box {{
    background: linear-gradient(135deg, var(--bg2), var(--bg3));
    border: 1px solid var(--border);
    border-radius: 10px;
    padding: 16px;
    text-align: center;
  }}
  .metric-val {{
    font-size: 28px;
    font-weight: 800;
    background: linear-gradient(90deg, var(--accent), var(--accent2));
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
  }}
  .metric-label {{ font-size: 12px; color: var(--text2); margin-top: 4px; }}

  .timeline {{ position: relative; padding-left: 32px; }}
  .timeline::before {{
    content: '';
    position: absolute;
    left: 12px;
    top: 0;
    bottom: 0;
    width: 2px;
    background: linear-gradient(180deg, var(--accent), var(--accent2));
  }}
  .tl-item {{
    position: relative;
    margin-bottom: 24px;
    padding: 16px;
    background: var(--bg2);
    border: 1px solid var(--border);
    border-radius: 10px;
  }}
  .tl-item::before {{
    content: '';
    position: absolute;
    left: -26px;
    top: 20px;
    width: 12px;
    height: 12px;
    background: var(--accent);
    border-radius: 50%;
    border: 2px solid var(--bg);
  }}
  .tl-agent {{ font-weight: 700; color: var(--accent); font-size: 15px; }}
  .tl-tier {{
    display: inline-block;
    padding: 2px 8px;
    border-radius: 8px;
    font-size: 11px;
    font-weight: 600;
    margin-left: 8px;
  }}
  .tl-output {{
    margin-top: 12px;
    padding: 12px;
    background: var(--bg);
    border-radius: 8px;
    font-size: 12px;
    white-space: pre-wrap;
    color: var(--text2);
    max-height: 240px;
    overflow-y: auto;
    line-height: 1.6;
  }}

  .chart-container {{ position: relative; height: 260px; }}
  .bar-chart {{ display: flex; align-items: flex-end; gap: 8px; height: 220px; padding: 0 8px; }}
  .bar-col {{ display: flex; flex-direction: column; align-items: center; flex: 1; }}
  .bar {{
    width: 100%;
    border-radius: 6px 6px 0 0;
    transition: height 0.6s ease;
    position: relative;
  }}
  .bar-label {{ font-size: 11px; color: var(--text2); margin-top: 6px; text-align: center; }}
  .bar-val {{
    font-size: 11px;
    font-weight: 700;
    color: var(--text);
    margin-bottom: 4px;
  }}

  .pie-chart {{
    width: 200px;
    height: 200px;
    border-radius: 50%;
    position: relative;
    margin: 0 auto;
  }}
  .pie-legend {{ text-align: center; margin-top: 12px; }}
  .pie-legend-item {{ display: inline-block; margin: 0 12px; font-size: 13px; }}
  .pie-dot {{ display: inline-block; width: 10px; height: 10px; border-radius: 50%; margin-right: 4px; }}

  .conclusion-box {{
    background: linear-gradient(135deg, rgba(0,212,255,0.08), rgba(123,47,247,0.08));
    border: 1px solid rgba(0,212,255,0.3);
    border-radius: 12px;
    padding: 20px;
    margin-top: 16px;
    font-size: 14px;
    line-height: 1.8;
    white-space: pre-wrap;
  }}

  .resource-pool {{
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 16px;
    margin-bottom: 20px;
  }}
  .pool-card {{
    background: var(--bg2);
    border: 1px solid var(--border);
    border-radius: 10px;
    padding: 16px;
    text-align: center;
  }}
  .pool-card h4 {{ font-size: 18px; margin-bottom: 8px; }}
  .pool-icon {{ font-size: 32px; margin-bottom: 8px; }}

  @media (max-width: 768px) {{
    .resource-pool {{ grid-template-columns: 1fr; }}
    .metric-grid {{ grid-template-columns: repeat(2, 1fr); }}
  }}
</style>
</head>
<body>

<div class="header">
  <div class="logo">◈ NEXUSFLOW v2.8</div>
  <span class="logo-sub">端边云协作调度 · 动态认知拓扑</span>
  <span class="badge badge-edge">Edge</span>
  <span class="badge badge-fog">Fog</span>
  <span class="badge badge-cloud">Cloud</span>
</div>

<div class="container">
  <!-- Tabs -->
  <div class="tabs" id="tabs">
    <div class="tab active" data-tab="overview">📊 系统概览</div>
    <div class="tab" data-tab="execution">🔄 任务执行记录</div>
    <div class="tab" data-tab="resources">🖥️ 端边云资源</div>
    <div class="tab" data-tab="stats">📈 执行统计</div>
  </div>

  <!-- Tab 1: 系统概览 -->
  <div class="panel active" id="panel-overview">
    <div class="card">
      <div class="card-title">Agent 拓扑状态</div>
      <table>
        <thead>
          <tr>
            <th>Agent</th><th>角色</th><th>层级</th><th>状态</th><th>评分</th><th>能力标签</th>
          </tr>
        </thead>
        <tbody id="agent-table"></tbody>
      </table>
    </div>
    <div class="card">
      <div class="card-title">🔍 最终研究结论</div>
      <div class="conclusion-box" id="conclusion-box"></div>
    </div>
  </div>

  <!-- Tab 2: 任务执行记录 -->
  <div class="panel" id="panel-execution">
    <div class="card">
      <div class="card-title">端到端执行时间线</div>
      <div class="timeline" id="exec-timeline"></div>
    </div>
  </div>

  <!-- Tab 3: 端边云资源 -->
  <div class="panel" id="panel-resources">
    <div class="resource-pool" id="resource-pools"></div>
    <div class="card">
      <div class="card-title">三层资源池详情</div>
      <table>
        <thead>
          <tr><th>层级</th><th>资源名</th><th>GPU</th><th>延迟(ms)</th><th>负载</th><th>可用模型</th></tr>
        </thead>
        <tbody id="resource-table"></tbody>
      </table>
    </div>
    <div class="card">
      <div class="card-title">调度分布</div>
      <div style="display:flex;align-items:center;justify-content:center;gap:48px;flex-wrap:wrap;">
        <div class="pie-chart" id="pie-chart"></div>
        <div class="pie-legend" id="pie-legend"></div>
      </div>
    </div>
  </div>

  <!-- Tab 4: 执行统计 -->
  <div class="panel" id="panel-stats">
    <div class="metric-grid" id="stat-metrics"></div>
    <div class="card">
      <div class="card-title">各 Agent 耗时分布</div>
      <div class="chart-container">
        <div class="bar-chart" id="latency-chart"></div>
      </div>
    </div>
    <div class="card">
      <div class="card-title">各 Agent Token 消耗</div>
      <div class="chart-container">
        <div class="bar-chart" id="token-chart"></div>
      </div>
    </div>
  </div>
</div>

<script>
// ── Data ──
const AGENTS = {agents_json};
const STEPS  = {steps_json};
const STATS  = {stats_json};
const RESOURCES = {resources_json};
const CONCLUSION = {json.dumps(final_conclusion, ensure_ascii=False)};

// ── Tab Switching ──
document.querySelectorAll('.tab').forEach(tab => {{
  tab.addEventListener('click', () => {{
    document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
    document.querySelectorAll('.panel').forEach(p => p.classList.remove('active'));
    tab.classList.add('active');
    document.getElementById('panel-' + tab.dataset.tab).classList.add('active');
  }});
}});

// ── Tab 1: Agent Table ──
(function() {{
  const tbody = document.getElementById('agent-table');
  const tierBadge = t => t==='edge'?'badge-edge':t==='fog'?'badge-fog':'badge-cloud';
  const tierName = t => t==='edge'?'Edge ⚡':t==='fog'?'Fog 🌫':'Cloud ☁';
  AGENTS.forEach(a => {{
    tbody.innerHTML += `<tr>
      <td style="font-weight:700">${{a.name}}</td>
      <td>${{a.role}}</td>
      <td><span class="badge ${{tierBadge(a.tier)}}">${{tierName(a.tier)}}</span></td>
      <td style="color:#00ff88">✓ 在线</td>
      <td>${{a.score.toFixed(2)}}</td>
      <td style="font-size:12px;color:var(--text2)">${{a.capabilities.join(', ')}}</td>
    </tr>`;
  }});
  document.getElementById('conclusion-box').textContent = CONCLUSION;
}})();

// ── Tab 2: Execution Timeline ──
(function() {{
  const tl = document.getElementById('exec-timeline');
  const tierColor = t => t==='edge'?'#00ff88':t==='fog'?'#ffc800':'#00d4ff';
  const tierBg = t => t==='edge'?'rgba(0,255,136,0.15)':t==='fog'?'rgba(255,200,0,0.15)':'rgba(0,212,255,0.15)';
  const tierName = t => t==='edge'?'Edge ⚡':t==='fog'?'Fog 🌫':'Cloud ☁';
  STEPS.forEach((s, i) => {{
    tl.innerHTML += `<div class="tl-item">
      <span class="tl-agent">Step ${{i+1}}: ${{s.agent_name}}</span>
      <span class="tl-tier" style="background:${{tierBg(s.tier)}};color:${{tierColor(s.tier)}}">${{tierName(s.tier)}}</span>
      <div style="margin-top:8px;font-size:12px;color:var(--text2)">
        ⏱ ${{s.latency_ms.toFixed(0)}}ms &nbsp;|&nbsp; 📊 ${{s.total_tokens}} tokens &nbsp;|&nbsp; 🔧 ${{s.model}}
      </div>
      <div style="margin-top:6px;font-size:12px;color:var(--text2)">
        📋 调度原因: ${{s.schedule_reason}}
      </div>
      <div class="tl-output">${{s.output.substring(0, 600)}}${{s.output.length > 600 ? '...' : ''}}</div>
    </div>`;
  }});
}})();

// ── Tab 3: Resources ──
(function() {{
  const pools = document.getElementById('resource-pools');
  const icons = {{edge:'⚡', fog:'🌫', cloud:'☁'}};
  const names = {{edge:'Edge 端侧', fog:'Fog 边缘', cloud:'Cloud 云端'}};
  const colors = {{edge:'#00ff88', fog:'#ffc800', cloud:'#00d4ff'}};
  const counts = {{edge:0, fog:0, cloud:0}};
  STEPS.forEach(s => counts[s.tier]++);
  ['edge','fog','cloud'].forEach(t => {{
    pools.innerHTML += `<div class="pool-card" style="border-color:${{colors[t]}}30">
      <div class="pool-icon">${{icons[t]}}</div>
      <h4 style="color:${{colors[t]}}">${{names[t]}}</h4>
      <div style="font-size:24px;font-weight:800;color:${{colors[t]}}">${{counts[t]}}</div>
      <div style="font-size:12px;color:var(--text2)">本次调度次数</div>
    </div>`;
  }});

  const rt = document.getElementById('resource-table');
  const tierOrder = ['edge','fog','cloud'];
  tierOrder.forEach(tier => {{
    (RESOURCES[tier]||[]).forEach(r => {{
      rt.innerHTML += `<tr>
        <td>${{tier}}</td><td>${{r.name}}</td><td>${{r.gpu}}</td>
        <td>${{r.latency_ms}}</td><td>${{(r.load_factor*100).toFixed(0)}}%</td>
        <td style="font-size:12px;color:var(--text2)">${{r.models.join(', ')}}</td>
      </tr>`;
    }});
  }});

  // Pie chart (CSS conic-gradient)
  const total = counts.edge + counts.fog + counts.cloud || 1;
  const pctE = counts.edge/total*360, pctF = counts.fog/total*360;
  const pie = document.getElementById('pie-chart');
  pie.style.background = `conic-gradient(${{colors.edge}} 0deg ${{pctE}}deg, ${{colors.fog}} ${{pctE}}deg ${{pctE+pctF}}deg, ${{colors.cloud}} ${{pctE+pctF}}deg 360deg)`;
  const legend = document.getElementById('pie-legend');
  legend.innerHTML = `
    <div class="pie-legend-item"><span class="pie-dot" style="background:${{colors.edge}}"></span>Edge ${{(counts.edge/total*100).toFixed(0)}}%</div>
    <div class="pie-legend-item"><span class="pie-dot" style="background:${{colors.fog}}"></span>Fog ${{(counts.fog/total*100).toFixed(0)}}%</div>
    <div class="pie-legend-item"><span class="pie-dot" style="background:${{colors.cloud}}"></span>Cloud ${{(counts.cloud/total*100).toFixed(0)}}%</div>
  `;
}})();

// ── Tab 4: Statistics ──
(function() {{
  const sm = document.getElementById('stat-metrics');
  const metrics = [
    {{label:'总耗时', val: (STATS.total_latency_ms/1000).toFixed(2)+'s', icon:'⏱'}},
    {{label:'总 Token', val: STATS.total_tokens.toLocaleString(), icon:'📊'}},
    {{label:'Agent 数', val: STATS.agent_count, icon:'🤖'}},
    {{label:'跨层调度', val: STATS.cross_tier_count, icon:'🔀'}},
    {{label:'平均延迟', val: (STATS.total_latency_ms/STATS.agent_count).toFixed(0)+'ms', icon:'⚡'}},
    {{label:'拓扑类型', val: STATS.topology_type, icon:'🔗'}},
  ];
  metrics.forEach(m => {{
    sm.innerHTML += `<div class="metric-box">
      <div style="font-size:20px;margin-bottom:4px">${{m.icon}}</div>
      <div class="metric-val">${{m.val}}</div>
      <div class="metric-label">${{m.label}}</div>
    </div>`;
  }});

  // Latency chart
  const lc = document.getElementById('latency-chart');
  const maxLat = Math.max(...STEPS.map(s=>s.latency_ms)) || 1;
  STEPS.forEach(s => {{
    const h = (s.latency_ms / maxLat * 200);
    const c = s.tier==='edge'?'#00ff88':s.tier==='fog'?'#ffc800':'#00d4ff';
    lc.innerHTML += `<div class="bar-col">
      <div class="bar-val">${{s.latency_ms.toFixed(0)}}ms</div>
      <div class="bar" style="height:${{h}}px;background:${{c}}"></div>
      <div class="bar-label">${{s.agent_name.split('（')[0]}}</div>
    </div>`;
  }});

  // Token chart
  const tc = document.getElementById('token-chart');
  const maxTok = Math.max(...STEPS.map(s=>s.total_tokens)) || 1;
  STEPS.forEach(s => {{
    const h = (s.total_tokens / maxTok * 200);
    const c = s.tier==='edge'?'rgba(0,255,136,0.7)':s.tier==='fog'?'rgba(255,200,0,0.7)':'rgba(0,212,255,0.7)';
    tc.innerHTML += `<div class="bar-col">
      <div class="bar-val">${{s.total_tokens}}</div>
      <div class="bar" style="height:${{h}}px;background:${{c}}"></div>
      <div class="bar-label">${{s.agent_name.split('（')[0]}}</div>
    </div>`;
  }});
}})();
</script>
</body>
</html>"""

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"\n{C.GREEN}✅ Dashboard 报告已生成: {output_path}{C.RESET}")


# ══════════════════════════════════════════════════════════════════════════
# Main
# ══════════════════════════════════════════════════════════════════════════
def main():
    t_start = time.time()
    task_description = "低碳水泥的3个关键技术方向"

    banner(f"◈ NEXUSFLOW v2.8 — 真实端到端 Demo", C.MAGENTA)
    print(f"  {C.CYAN}研究主题:{C.RESET} {C.BOLD}{task_description}{C.RESET}")
    print(f"  {C.CYAN}LLM 后端:{C.RESET} DeepSeek API ({DEEPSEEK_MODEL})")
    print(f"  {C.CYAN}Agent 数:{C.RESET} 5 (Planner / Researcher / Critic / Synthesizer / Assayer)")
    print(f"  {C.CYAN}时  间:{C.RESET} {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    # ── 1. 初始化调度器 ────────────────────────────────────────────────────
    banner("Phase 1: 初始化端边云调度器", C.BLUE)
    scheduler = EdgeCloudScheduler(policy=SchedulingPolicy.BALANCED)
    scheduler.setup_default_tiers()
    print(f"  {C.GREEN}✓{C.RESET} 三层资源池已注册 (Edge / Fog / Cloud)")

    # ── 2. 初始化路由器 + 注册 Agent ──────────────────────────────────────
    banner("Phase 2: 注册 Agent 到动态拓扑路由器", C.BLUE)
    router = DynamicTopologyRouter()

    agent_profiles = {}
    for adef in AGENT_DEFS:
        profile = AgentCapabilityProfile(
            agent_id=adef["id"],
            name=adef["name"],
            role=adef["role"],
            capabilities=adef["capabilities"],
            domain_expertise=adef["domains"],
            tier=adef["tier"],
            load_state=AgentLoadState.IDLE,
            reasoning_depth=adef["reasoning_depth"],
            creativity=adef["creativity"],
            context_window=adef["context_window"],
            preferred_partners=[],
        )
        router.register_agent(profile)
        agent_profiles[adef["id"]] = profile
        print(f"  {C.GREEN}✓{C.RESET} {adef['name']:<28s} tier={adef['tier']:<6s} caps={len(adef['capabilities'])}")

    # ── 3. 路由规划 ────────────────────────────────────────────────────────
    banner("Phase 3: 动态拓扑路由规划", C.BLUE)
    task_req = TaskRequirement(
        task_id=str(uuid.uuid4())[:8],
        description=f"研究{task_description}",
        required_capabilities=["planning", "research", "critical_thinking", "synthesis", "validation"],
        required_domains=["materials_science", "cement_chemistry", "sustainability"],
        complexity=TaskComplexity.MODERATE,
        privacy_level=0,
        latency_budget_ms=60000,
    )
    plan = router.route(task_req)
    print(f"  {C.CYAN}路由方案:{C.RESET} {plan.plan_id}")
    print(f"  {C.CYAN}拓扑类型:{C.RESET} {plan.topology_type}")
    print(f"  {C.CYAN}Agent 链:{C.RESET}", " → ".join(
        agent_profiles[a].name.split("（")[0] if a in agent_profiles else a
        for a in plan.agent_chain
    ))
    print(f"  {C.CYAN}置信度:{C.RESET} {plan.confidence:.2f}")

    # 使用我们预定义的顺序（Planner→Researcher→Critic→Synthesizer→Assayer）
    execution_order = [a["id"] for a in AGENT_DEFS]

    # ── 4. 逐 Agent 真实执行 ──────────────────────────────────────────────
    banner("Phase 4: 逐 Agent 真实执行 (DeepSeek API)", C.MAGENTA)

    steps_data = []
    prev_output = ""
    total_tokens = 0
    total_latency = 0.0
    cross_tier_count = 0
    prev_tier = None

    for idx, agent_id in enumerate(execution_order):
        adef = next(a for a in AGENT_DEFS if a["id"] == agent_id)
        profile = agent_profiles[agent_id]

        # 4a. 调度决策
        sched_req = {
            "task_id": f"step-{idx+1}",
            "needs_gpu": False,
            "privacy_level": adef["privacy_level"],
            "context_window": adef["context_window"],
            "latency_budget_ms": 30000,
            "model_name": DEEPSEEK_MODEL,
        }
        decision = scheduler.schedule(sched_req)
        selected_tier = decision.selected_tier

        # 跨层检测
        if prev_tier is not None and selected_tier != prev_tier:
            cross_tier_count += 1
        prev_tier = selected_tier

        # 4b. 构建 user prompt
        if idx == 0:
            user_content = f"研究主题：{task_description}\n\n请制定研究规划。"
        else:
            user_content = (
                f"研究主题：{task_description}\n\n"
                f"上一阶段输出：\n{prev_output}\n\n"
                f"请基于以上信息执行你的角色任务。"
            )

        # 4c. 打印步骤信息
        step_banner(idx + 1, len(execution_order), adef["name"],
                    tier_display(selected_tier), tier_color(selected_tier))
        kv_line("调度层级:", tier_display(selected_tier))
        kv_line("调度原因:", decision.reason)
        kv_line("置信度:", f"{decision.confidence:.3f}")
        print(f"  {C.YELLOW}{'调用 LLM...':<22s}{C.RESET} ", end="", flush=True)

        # 4d. 调用 DeepSeek API
        try:
            result = call_deepseek(adef["system_prompt"], user_content, max_tokens=800)
        except Exception as e:
            print(f"{C.RED}FAILED{C.RESET}")
            print(f"  {C.RED}✗ API 调用失败: {e}{C.RESET}")
            # 用 fallback 内容继续
            result = {
                "text": f"[API调用失败: {e}]",
                "prompt_tokens": 0,
                "completion_tokens": 0,
                "total_tokens": 0,
                "latency_ms": 0,
            }

        print(f"{C.GREEN}OK{C.RESET} ({result['latency_ms']:.0f}ms)")

        # 4e. 打印结果摘要
        output_text = result["text"]
        total_tokens += result["total_tokens"]
        total_latency += result["latency_ms"]

        kv_line("Token 用量:", f"{result['total_tokens']} (prompt:{result['prompt_tokens']} + completion:{result['completion_tokens']})")
        kv_line("响应延迟:", f"{result['latency_ms']:.1f} ms")

        # 显示模型名（根据 tier 模拟不同模型）
        model_display = {
            DeployTier.EDGE: "qwen-7b (simulated)",
            DeployTier.FOG:  "qwen-72b (simulated)",
            DeployTier.CLOUD: "qwen-max (simulated)",
        }.get(selected_tier, DEEPSEEK_MODEL)
        kv_line("模型:", model_display)

        # 简要输出
        output_preview = output_text[:200].replace("\n", " ")
        print(f"\n  {C.DIM}── 输出摘要 ──{C.RESET}")
        print(f"  {C.WHITE}{output_preview}{'...' if len(output_text) > 200 else ''}{C.RESET}")

        # 4f. 记录步骤数据
        steps_data.append({
            "step": idx + 1,
            "agent_id": agent_id,
            "agent_name": adef["name"],
            "tier": selected_tier.value,
            "tier_display": tier_display(selected_tier),
            "model": model_display,
            "actual_model": DEEPSEEK_MODEL,
            "schedule_reason": decision.reason,
            "schedule_confidence": round(decision.confidence, 3),
            "prompt_tokens": result["prompt_tokens"],
            "completion_tokens": result["completion_tokens"],
            "total_tokens": result["total_tokens"],
            "latency_ms": result["latency_ms"],
            "output": output_text,
        })

        prev_output = output_text

    # ── 5. 汇总报告 ───────────────────────────────────────────────────────
    t_total = (time.time() - t_start) * 1000
    banner("Phase 5: 执行汇总", C.GREEN)

    print(f"  {C.BOLD}{'总耗时:':<22s}{C.RESET} {C.CYAN}{t_total/1000:.2f} s{C.RESET}")
    print(f"  {C.BOLD}{'LLM 总延迟:':<22s}{C.RESET} {C.CYAN}{total_latency/1000:.2f} s{C.RESET}")
    print(f"  {C.BOLD}{'总 Token:':<22s}{C.RESET} {C.CYAN}{total_tokens}{C.RESET}")
    print(f"  {C.BOLD}{'Agent 数:':<22s}{C.RESET} {C.CYAN}{len(execution_order)}{C.RESET}")
    print(f"  {C.BOLD}{'跨层调度:':<22s}{C.RESET} {C.CYAN}{cross_tier_count} 次{C.RESET}")
    print(f"  {C.BOLD}{'调度策略:':<22s}{C.RESET} {C.CYAN}BALANCED{C.RESET}")
    print(f"  {C.BOLD}{'拓扑类型:':<22s}{C.RESET} {C.CYAN}{plan.topology_type}{C.RESET}")

    # 最终结论
    final_conclusion = prev_output if prev_output else "（无最终输出）"

    print(f"\n  {C.BOLD}{C.GREEN}════════════════════════════════════════════════════{C.RESET}")
    print(f"  {C.BOLD}{C.GREEN}  最终研究结论（Assayer 输出）{C.RESET}")
    print(f"  {C.BOLD}{C.GREEN}════════════════════════════════════════════════════{C.RESET}")
    print(f"  {C.WHITE}{final_conclusion}{C.RESET}")

    # ── 6. 生成 HTML 报告 ──────────────────────────────────────────────────
    banner("Phase 6: 生成 Dashboard 可视化报告", C.BLUE)

    # 准备 agents 数据
    agents_data = []
    for adef in AGENT_DEFS:
        p = agent_profiles[adef["id"]]
        agents_data.append({
            "id": adef["id"],
            "name": adef["name"],
            "role": adef["role"],
            "tier": adef["tier"],
            "score": p.compute_score(),
            "capabilities": adef["capabilities"],
            "state": "online",
        })

    # 准备 resources 数据
    resources_data = {}
    for tier_name, res_list in scheduler.get_all_resources().items():
        resources_data[tier_name] = res_list

    # 统计数据
    stats_data = {
        "total_latency_ms": round(total_latency, 1),
        "total_tokens": total_tokens,
        "agent_count": len(execution_order),
        "cross_tier_count": cross_tier_count,
        "topology_type": plan.topology_type,
        "schedule_policy": "balanced",
    }

    exec_data = {
        "agents": agents_data,
        "steps": steps_data,
        "stats": stats_data,
        "resources": resources_data,
        "final_conclusion": final_conclusion,
    }

    html_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "demo_dashboard_report.html")
    generate_html_report(exec_data, html_path)

    # 保存 JSON 数据备份
    json_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "demo_execution_data.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(exec_data, f, ensure_ascii=False, indent=2)
    print(f"{C.GREEN}✓ 执行数据已保存: {json_path}{C.RESET}")

    banner("✅ Demo 执行完成!", C.GREEN)
    print(f"  {C.CYAN}打开 HTML 报告查看可视化结果:{C.RESET}")
    print(f"  {C.BOLD}  {html_path}{C.RESET}\n")


if __name__ == "__main__":
    main()
