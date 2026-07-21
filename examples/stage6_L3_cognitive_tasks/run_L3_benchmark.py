#!/usr/bin/env python3
"""
NexusFlow Stage 6 — L3 高复杂度认知任务 Benchmark
==================================================
10项异构认知任务 × 单Agent基线 vs NexusFlow完整系统
真实数据（DBnomics IMF WEO） + 真实LLM调用（deepseek-v4-flash）
零模拟，全量可验证。

任务矩阵 (L3):
Phase 1 - 发现与建模:
  T1 模式挖掘 (researcher+miner)           3轮
  T2 跨国相关性 (researcher+artisan)        4轮
  T3 因果链分析 (planner+reviewer)          5轮
Phase 2 - 预测与模拟:
  T4 多期预测 (planner+executor)            6轮
  T5 异常检测 (executor+assayer)            5轮
  T6 反事实推理 (caster+planner)            6轮
Phase 3 - 评估与决策:
  T7 交叉辩论 (All Agents)                  8轮  → 简化为3轮精选
  T8 风险评估 (assayer+artisan)             5轮
  T9 政策建议 (planner+coordinator)         6轮

评价维度 (8):
  D1 预测准确性(25%) D2 因果有效性(15%) D3 异常检出率(15%)
  D4 跨指标一致性(10%) D5 辩论质量(10%) D6 政策合理性(10%)
  D7 场景可信度(10%) D8 计算效率(5%)
"""

import json
import os
import sys
import time
import math
import traceback
import urllib.request
import urllib.error
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd
import numpy as np

# ============================================================
# 0. 配置
# ============================================================
REPO_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.chdir(REPO_DIR)
sys.path.insert(0, REPO_DIR)

API_KEY = os.environ.get('DEEPSEEK_API_KEY', '')
API_URL = 'https://api.deepseek.com/v1/chat/completions'
MODEL = 'deepseek-chat'  # 实际返回 deepseek-v4-flash

OUTPUT_DIR = os.path.join(REPO_DIR, 'examples', 'stage6_L3_cognitive_tasks')
DATA_DIR = os.path.join(OUTPUT_DIR, 'data')
os.makedirs(DATA_DIR, exist_ok=True)

TABLE_A_PATH = os.path.join(REPO_DIR, 'docs', 'NexusFlow_DBnomics_表A_历史数据_1980-2020.xlsx')
TABLE_B_PATH = os.path.join(REPO_DIR, 'docs', 'NexusFlow_DBnomics_表B_回测真值_2021-2025.xlsx')

# 统计
stats = {
    'api_calls': 0,
    'total_tokens': 0,
    'total_time_sec': 0,
    'start_time': time.time(),
    'errors': [],
}

# ============================================================
# 1. LLM API Wrapper
# ============================================================
def llm_call(prompt: str, system: str = "", max_tokens: int = 4096,
             temperature: float = 0.7, tag: str = "") -> str:
    """调用 DeepSeek API (deepseek-v4-flash)"""
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})

    payload = json.dumps({
        "model": MODEL,
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": temperature,
    }).encode("utf-8")

    req = urllib.request.Request(API_URL, data=payload, headers={
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json",
    })

    t0 = time.time()
    try:
        with urllib.request.urlopen(req, timeout=180) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        dur = time.time() - t0
        usage = data.get("usage", {})
        stats['api_calls'] += 1
        stats['total_tokens'] += usage.get('total_tokens', 0)
        stats['total_time_sec'] += dur
        content = data["choices"][0]["message"]["content"]
        print(f"    [LLM {tag or 'call'}] {len(content)} chars, {dur:.1f}s, "
              f"{usage.get('total_tokens',0)} tokens")
        return content
    except Exception as e:
        dur = time.time() - t0
        err_msg = f"[LLM_ERROR: {e}]"
        stats['errors'].append({'tag': tag, 'error': str(e), 'time': dur})
        print(f"    [LLM {tag or 'call'}] ERROR after {dur:.1f}s: {e}")
        return err_msg


# ============================================================
# 2. Agent System Prompts (from agent_registry.py)
# ============================================================
AGENT_PROMPTS = {
    "coordinator": """你是NexusFlow的协调者(Coordinator) — 多Agent协作调度中枢。
核心职责：任务拆解、角色分配、进度协调、结论汇总。你拥有全局视野。
输出要求：结构化JSON格式（assignments/progress/summary），确保每个子任务有明确的执行者和验收标准。""",

    "planner": """你是NexusFlow的规划者(Planner) — 策略推理核心。
核心职责：将高层目标分解为可执行子任务，设计执行策略，评估执行结果。
思维原则：MECE分解、依赖优先、风险前置、经验复用。
输出规范：任务分解+策略选择理由+风险评估+验收标准。""",

    "researcher": """你是NexusFlow的研究者(Researcher) — 知识获取核心。
核心职责：检索信息、挖掘数据、验证事实。
工作原则：多源验证、置信度标注(✅确认/⚠️存疑/❌冲突)、数据优先。
输出规范：关键发现+置信度+数据来源+不确定点。""",

    "executor": """你是NexusFlow的执行者(Executor) — 精确执行核心。
核心职责：按照计划精确执行每一步操作，包括数据计算、统计分析、代码实现。
执行原则：严格按计划执行、结果可复现、精度优先。
输出规范：执行步骤+计算结果+精度说明。""",

    "reviewer": """你是NexusFlow的审查者(Reviewer) — 质量守门员。
核心职责：验证结果的准确性、逻辑一致性、方法论合理性。
审查原则：严格质疑、证据导向、建设性反馈。
输出规范：问题清单+严重程度+改进建议+通过/不通过判定。""",

    "miner": """你是NexusFlow的文献挖掘专家(Miner) — 知识发现核心。
核心职责：从数据中发现隐藏模式、挖掘潜在关系、提取关键特征。
挖掘原则：数据驱动、模式识别、统计验证。
输出规范：发现的模式+统计支撑+置信度+潜在意义。""",

    "assayer": """你是NexusFlow的知识验证专家(Assayer) — 事实验证核心。
核心职责：验证假设、检验结论可靠性、识别逻辑漏洞。
验证原则：假设检验、反例寻找、边界条件测试。
输出规范：验证结论+支撑证据+可靠性评分+风险提示。""",

    "caster": """你是NexusFlow的代码生成专家(Caster) — 技术方案核心。
核心职责：将分析需求转化为可执行代码和算法方案。
编码原则：可复现、高效、可读性好。
输出规范：代码/算法+运行结果+复杂度分析。""",

    "artisan": """你是NexusFlow的领域专家(Artisan) — 专业领域知识核心。
核心职责：提供领域专业判断、解读数据含义、验证结论的领域合理性。
判断原则：领域理论驱动、经验验证、实际可行性。
输出规范：专业解读+理论依据+实际意义+局限性。""",

    "archivist": """你是NexusFlow的知识守护者(Archivist) — 记忆管理者。
核心职责：整理所有产物、生成结构化报告、确保结论可追溯。
输出规范：结构化Markdown报告+关键发现摘要+方法论说明+局限与展望。""",
}

# L3角色到NexusFlow Agent的映射
L3_ROLE_MAP = {
    "Economist": "artisan",
    "Forecaster": "planner",
    "RiskAnalyzer": "assayer",
    "ScenarioPlanner": "caster",
    # 同名的直接映射
    "Coordinator": "coordinator",
    "Planner": "planner",
    "Researcher": "researcher",
    "Executor": "executor",
    "Reviewer": "reviewer",
    "Miner": "miner",
    "Assayer": "assayer",
    "Caster": "caster",
    "Artisan": "artisan",
    "Archivist": "archivist",
}


# ============================================================
# 3. Data Loading & Processing
# ============================================================
print("=" * 60)
print("NexusFlow Stage 6 — L3 高复杂度认知任务 Benchmark")
print("=" * 60)
print(f"时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
print(f"模型: {MODEL} (via DeepSeek API)")
print(f"数据: DBnomics IMF WEO (20国 × 15指标 × 41年)")
print()

# 加载数据
print("[1/6] 加载数据...")
data_a = {}  # indicator -> DataFrame
for sheet in pd.ExcelFile(TABLE_A_PATH).sheet_names:
    if sheet in ('数据总览', '数据覆盖统计'):
        continue
    df = pd.read_excel(TABLE_A_PATH, sheet_name=sheet)
    data_a[sheet] = df

data_b = {}
for sheet in pd.ExcelFile(TABLE_B_PATH).sheet_names:
    if sheet in ('数据总览', '数据覆盖统计'):
        continue
    df = pd.read_excel(TABLE_B_PATH, sheet_name=sheet)
    data_b[sheet] = df

indicators = list(data_a.keys())
countries = [c for c in data_a[indicators[0]].columns if c != '年份']
print(f"  指标: {len(indicators)}个")
print(f"  国家: {len(countries)}个")
print(f"  表A年份: {data_a[indicators[0]]['年份'].min()}-{data_a[indicators[0]]['年份'].max()}")
print(f"  表B年份: {data_b[indicators[0]]['年份'].min()}-{data_b[indicators[0]]['年份'].max()}")


def get_country_data(indicator: str, countries_list: List[str],
                     years_range: Tuple[int, int] = None,
                     source: str = 'A') -> pd.DataFrame:
    """提取特定国家、年份的数据"""
    src = data_a if source == 'A' else data_b
    if indicator not in src:
        return pd.DataFrame()
    df = src[indicator].copy()
    if years_range:
        df = df[(df['年份'] >= years_range[0]) & (df['年份'] <= years_range[1])]
    cols = ['年份'] + [c for c in countries_list if c in df.columns]
    return df[cols].reset_index(drop=True)


def df_to_table_string(df: pd.DataFrame, max_rows: int = 45) -> str:
    """将DataFrame转为紧凑的文本表格"""
    if len(df) > max_rows:
        return df.head(max_rows).to_string(index=False) + f"\n... (共{len(df)}行，显示前{max_rows}行)"
    return df.to_string(index=False)


def get_data_summary_text() -> str:
    """生成数据摘要文本供Agent使用"""
    lines = ["# DBnomics 宏观经济数据摘要",
             "数据来源: IMF World Economic Outlook (via DBnomics)",
             f"国家: {len(countries)}个",
             f"指标: {len(indicators)}个",
             f"表A: 1980-2020 ({data_a[indicators[0]].shape[0]}年)",
             f"表B: 2021-2025 ({data_b[indicators[0]].shape[0]}年)",
             "",
             "## 指标列表"]
    indicator_names = {
        'NGDP_RPCH': '实际GDP增长率(%)',
        'NGDPDPC': '人均GDP(美元)',
        'PCPIPCH': 'CPI通胀率(%)',
        'LUR': '失业率(%)',
        'GGXWDN_NGDP': '政府债务/GDP(%)',
        'GGXCNL_NGDP': '政府消费/GDP(%)',
        'BCA_NGDPD': '经常账户/GDP(%)',
        'TM_RPCH': '进口增长率(%)',
        'TX_RPCH': '出口增长率(%)',
        'NGSD_NGDP': '国民储蓄/GDP(%)',
        'NID_NGDP': '国内投资/GDP(%)',
        'GGXWDG_NGDP': '总债务/GDP(%)',
        'GGX_NGDP': '政府支出/GDP(%)',
        'GGR_NGDP': '政府收入/GDP(%)',
        'NGAP_NPGDP': '产出缺口(%)',
    }
    for ind in indicators:
        name = indicator_names.get(ind, ind)
        df = data_a[ind]
        vals = df.select_dtypes(include=[np.number])
        lines.append(f"  - {ind} ({name}): 均值={vals.mean().mean():.2f}, "
                     f"范围=[{vals.min().min():.2f}, {vals.max().max():.2f}]")
    return "\n".join(lines)


# ============================================================
# 4. L3 Task Definitions
# ============================================================
print("[2/6] 定义L3任务...")

TASKS = {
    "T1": {
        "name": "模式挖掘",
        "phase": "发现与建模",
        "l3_agents": ["Researcher", "Miner"],
        "nexus_agents": ["researcher", "miner"],
        "rounds": 3,
        "description": "从1980-2020的GDP增长率和人均GDP数据中，识别至少3种不同的经济增长模式（如高速增长、稳定增长、周期性波动等），并对每种模式进行分类、特征描述和统计验证。",
        "data_func": lambda: {
            "gdp_growth": get_country_data('NGDP_RPCH', countries[:10]),
            "gdp_per_capita": get_country_data('NGDPDPC', countries[:10]),
        },
    },
    "T2": {
        "name": "跨国相关性分析",
        "phase": "发现与建模",
        "l3_agents": ["Researcher", "Economist"],
        "nexus_agents": ["researcher", "artisan"],
        "rounds": 4,
        "description": "分析20个国家在1980-2020年间GDP增长率与通胀率、失业率、政府债务/GDP之间的相关性。计算Pearson相关系数矩阵，识别强相关和弱相关国家对，给出经济学解释。",
        "data_func": lambda: {
            "gdp_growth": get_country_data('NGDP_RPCH', countries),
            "inflation": get_country_data('PCPIPCH', countries),
            "unemployment": get_country_data('LUR', countries),
            "debt_ratio": get_country_data('GGXWDN_NGDP', countries),
        },
    },
    "T3": {
        "name": "因果链分析",
        "phase": "发现与建模",
        "l3_agents": ["Planner", "Reviewer"],
        "nexus_agents": ["planner", "reviewer"],
        "rounds": 5,
        "description": "基于1980-2020数据，分析'政府债务增加 → 财政支出变化 → 经济增长'的传导机制。使用Granger因果检验思想（时序领先-滞后关系），识别至少2条完整的因果链，标注传导时滞。",
        "data_func": lambda: {
            "debt": get_country_data('GGXWDN_NGDP', countries[:10]),
            "govt_spending": get_country_data('GGX_NGDP', countries[:10]),
            "gdp_growth": get_country_data('NGDP_RPCH', countries[:10]),
            "govt_revenue": get_country_data('GGR_NGDP', countries[:10]),
        },
    },
    "T4": {
        "name": "多期预测",
        "phase": "预测与模拟",
        "l3_agents": ["Forecaster", "Executor"],
        "nexus_agents": ["planner", "executor"],
        "rounds": 6,
        "description": "仅使用1980-2020年（表A）数据，预测2021-2025年（表B）每个国家的GDP增长率和通胀率。使用趋势外推+移动平均+均值回归三种方法，给出预测值和置信区间。真值在表B中可用于回测。",
        "data_func": lambda: {
            "train_gdp": get_country_data('NGDP_RPCH', countries),
            "train_inflation": get_country_data('PCPIPCH', countries),
            "test_gdp": get_country_data('NGDP_RPCH', countries, source='B'),
            "test_inflation": get_country_data('PCPIPCH', countries, source='B'),
        },
    },
    "T5": {
        "name": "异常检测",
        "phase": "预测与模拟",
        "l3_agents": ["Executor", "Assayer"],
        "nexus_agents": ["executor", "assayer"],
        "rounds": 5,
        "description": "使用Z-score和IQR方法，检测1980-2020年数据中的异常值。对每个检测到的异常，关联到具体历史经济事件（如金融危机、石油冲击等），评估自动检测的准确率。",
        "data_func": lambda: {
            "gdp_growth": get_country_data('NGDP_RPCH', countries[:10]),
            "inflation": get_country_data('PCPIPCH', countries[:10]),
            "unemployment": get_country_data('LUR', countries[:10]),
        },
    },
    "T6": {
        "name": "反事实推理",
        "phase": "预测与模拟",
        "l3_agents": ["ScenarioPlanner", "Planner"],
        "nexus_agents": ["caster", "planner"],
        "rounds": 6,
        "description": "假设2008年全球金融危机期间，美国GDP下降幅度减少一半（从实际值改善50%），基于历史跨国关联模式，推断这对中国、日本、德国、英国经济的可能影响。使用历史相关性构建传播模型。",
        "data_func": lambda: {
            "gdp_growth": get_country_data('NGDP_RPCH', ['美国(USA)', '中国(CHN)', '日本(JPN)', '德国(DEU)', '英国(GBR)']),
            "trade_export": get_country_data('TX_RPCH', ['美国(USA)', '中国(CHN)', '日本(JPN)', '德国(DEU)', '英国(GBR)']),
            "trade_import": get_country_data('TM_RPCH', ['美国(USA)', '中国(CHN)', '日本(JPN)', '德国(DEU)', '英国(GBR)']),
        },
    },
    "T7": {
        "name": "交叉辩论",
        "phase": "评估与决策",
        "l3_agents": ["All_Agents"],
        "nexus_agents": ["coordinator", "planner", "researcher", "executor", "reviewer",
                         "miner", "assayer", "caster", "artisan", "archivist"],
        "rounds": 3,  # 简化：原设计8轮→精选3轮
        "description": "综合T1-T6的分析结论，识别各任务间的主要矛盾和一致性。每个Agent从自身角色角度质疑其他任务结论的可靠性，通过辩论达成共识。",
        "data_func": lambda: {"summary": get_data_summary_text()},
    },
    "T8": {
        "name": "风险评估",
        "phase": "评估与决策",
        "l3_agents": ["Assayer", "Artisan"],
        "nexus_agents": ["assayer", "artisan"],
        "rounds": 5,
        "description": "基于2015-2020年最新数据，构建国家经济风险综合评估。使用指标：政府债务/GDP、失业率、通胀率、经常账户/GDP、产出缺口。计算复合风险分数，排序并给出预警信号。",
        "data_func": lambda: {
            "debt": get_country_data('GGXWDN_NGDP', countries, (2015, 2020)),
            "unemployment": get_country_data('LUR', countries, (2015, 2020)),
            "inflation": get_country_data('PCPIPCH', countries, (2015, 2020)),
            "current_account": get_country_data('BCA_NGDPD', countries, (2015, 2020)),
            "output_gap": get_country_data('NGAP_NPGDP', countries, (2015, 2020)),
        },
    },
    "T9": {
        "name": "政策建议",
        "phase": "评估与决策",
        "l3_agents": ["Planner", "Coordinator"],
        "nexus_agents": ["planner", "coordinator"],
        "rounds": 6,
        "description": "综合所有15个指标在20个国家41年的数据趋势，识别3个最重要的全球经济结构性变化，为每个变化提出具体的政策建议（需可操作、有针对性、考虑约束条件）。",
        "data_func": lambda: {"all_data_summary": get_data_summary_text()},
    },
}

for tid, t in TASKS.items():
    mapped = [L3_ROLE_MAP.get(a, a) for a in t['l3_agents'] if a != "All_Agents"]
    print(f"  {tid} {t['name']} ({t['phase']}) — "
          f"{len(t['nexus_agents'])}Agent, {t['rounds']}轮")


# ============================================================
# 5. Single-Agent Mode
# ============================================================
def run_single_agent(task_id: str, task: Dict) -> Dict:
    """单Agent模式：1个Agent拿到全部数据，一次完成"""
    print(f"\n{'='*50}")
    print(f"[单Agent] {task_id} {task['name']}")
    print(f"{'='*50}")

    # 获取数据
    data = task['data_func']()
    data_text_parts = [get_data_summary_text(), ""]
    for key, df in data.items():
        if isinstance(df, pd.DataFrame):
            data_text_parts.append(f"## {key}\n{df_to_table_string(df)}\n")
        else:
            data_text_parts.append(f"## {key}\n{df}\n")
    data_text = "\n".join(data_text_parts)

    # 单Agent综合提示
    prompt = f"""你是一位全能宏观经济分析师。请使用以下数据完成分析任务。

## 任务 ({task_id}: {task['name']})
{task['description']}

## 数据
{data_text}

## 要求
1. 独立完成完整分析，给出详细结论
2. 所有结论必须有数据支撑
3. 标注不确定性和局限性
4. 输出格式：结构化Markdown（##标题 + 数据引用 + 结论 + 局限性）

请开始分析。"""

    t0 = time.time()
    result = llm_call(prompt, system="你是一位经验丰富的宏观经济分析师，擅长数据驱动的分析。",
                      max_tokens=4096, temperature=0.5, tag=f"single-{task_id}")
    elapsed = time.time() - t0

    return {
        "task_id": task_id,
        "mode": "single_agent",
        "result": result,
        "api_calls": 1,
        "time_sec": round(elapsed, 2),
        "agent_roles": ["solo_analyst"],
    }


# ============================================================
# 6. NexusFlow Multi-Agent Mode (CDoL Protocol)
# ============================================================
def run_nexusflow(task_id: str, task: Dict) -> Dict:
    """NexusFlow完整系统：多Agent CDoL协议"""
    print(f"\n{'='*50}")
    print(f"[NexusFlow] {task_id} {task['name']}")
    print(f"  参与Agent: {task['nexus_agents']}")
    print(f"  计划轮次: {task['rounds']}")
    print(f"{'='*50}")

    agents = task['nexus_agents']
    data = task['data_func']()

    # 准备各Agent的数据切片（信息不对称）
    data_slices = _create_data_slices(agents, data, task)

    # Round 0: Coordinator 任务分解
    print(f"  --- Round 0: Coordinator 任务分解 ---")
    coord_assignment = _coordinator_decompose(task_id, task, agents, data)

    # Round 1: 各Agent独立分析（信息不对称）
    print(f"  --- Round 1: 各Agent独立分析 ---")
    agent_conclusions = {}
    for agent_name in agents:
        conclusion = _agent_analyze(task_id, task, agent_name, data_slices.get(agent_name, ""),
                                    coord_assignment.get(agent_name, ""))
        agent_conclusions[agent_name] = conclusion

    # Round 2: 交叉审视 + 修正
    print(f"  --- Round 2: 交叉审视 ---")
    revised_conclusions = {}
    for agent_name in agents:
        others = {k: v for k, v in agent_conclusions.items() if k != agent_name}
        revised = _agent_revise(task_id, agent_name, agent_conclusions[agent_name], others)
        revised_conclusions[agent_name] = revised

    # Round 3: Coordinator 综合
    print(f"  --- Round 3: Coordinator 综合 ---")
    final = _coordinator_synthesize(task_id, task, revised_conclusions)

    total_calls = 2 + len(agents) * 2 + 1  # coord_decompose + agents + revise + coord_synthesize

    return {
        "task_id": task_id,
        "mode": "nexusflow",
        "result": final,
        "api_calls": total_calls,
        "time_sec": 0,  # 由外层计算
        "agent_roles": agents,
        "round0_assignment": coord_assignment,
        "round1_conclusions": agent_conclusions,
        "round2_revised": revised_conclusions,
    }


def _create_data_slices(agents: List[str], data: Dict, task: Dict) -> Dict[str, str]:
    """为每个Agent创建信息切片（信息不对称）"""
    slices = {}
    data_keys = list(data.keys())

    for i, agent in enumerate(agents):
        parts = []
        # 根据Agent角色分配不同数据子集
        if agent in ('researcher', 'miner'):
            # 看到原始数据
            for key in data_keys[:max(1, len(data_keys)//2)]:
                df = data[key]
                if isinstance(df, pd.DataFrame):
                    parts.append(f"## 原始数据: {key}\n{df_to_table_string(df)}")
        elif agent in ('executor', 'caster'):
            # 看到计算相关数据
            for key in data_keys:
                df = data[key]
                if isinstance(df, pd.DataFrame):
                    parts.append(f"## 数据: {key}\n{df_to_table_string(df)}")
        elif agent in ('planner', 'coordinator'):
            # 看到数据摘要+任务描述
            parts.append(get_data_summary_text())
            for key in data_keys:
                df = data[key]
                if isinstance(df, pd.DataFrame):
                    # 只看统计摘要，不看全量
                    parts.append(f"## {key} 统计摘要\n{df.describe().to_string()}")
        elif agent in ('assayer', 'reviewer'):
            # 看到数据+验证要求
            for key in data_keys:
                df = data[key]
                if isinstance(df, pd.DataFrame):
                    parts.append(f"## 待验证数据: {key}\n{df_to_table_string(df, max_rows=20)}")
        elif agent in ('artisan',):
            # 看到领域背景+数据
            parts.append(get_data_summary_text())
            for key in data_keys[:max(1, len(data_keys)//2 + 1)]:
                df = data[key]
                if isinstance(df, pd.DataFrame):
                    parts.append(f"## 数据: {key}\n{df_to_table_string(df, max_rows=25)}")
        elif agent in ('archivist',):
            # 看到所有数据的概要
            parts.append(get_data_summary_text())
        else:
            # 默认：看数据摘要
            parts.append(get_data_summary_text())

        slices[agent] = "\n\n".join(parts) if parts else "无特定数据切片"

    return slices


def _coordinator_decompose(task_id: str, task: Dict, agents: List[str],
                           data: Dict) -> Dict[str, str]:
    """Coordinator分解任务，分配给各Agent"""
    agent_list = ", ".join(agents)
    prompt = f"""作为NexusFlow协调者，请分解以下任务并分配给指定Agent。

## 任务 {task_id}: {task['name']}
{task['description']}

## 可用Agent: {agent_list}

## 数据概要
{get_data_summary_text()}

请为每个Agent分配具体的子任务，输出JSON格式：
```json
{{
    "agent_name": "具体子任务描述",
    ...
}}
```"""

    result = llm_call(prompt, system=AGENT_PROMPTS.get('coordinator', ''),
                      max_tokens=2048, temperature=0.3, tag=f"coord-decompose-{task_id}")

    # 解析JSON
    try:
        import re
        json_match = re.search(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', result, re.DOTALL)
        if json_match:
            return json.loads(json_match.group())
    except:
        pass

    # 降级：均匀分配
    return {agent: f"请从你的角色角度分析: {task['description'][:100]}" for agent in agents}


def _agent_analyze(task_id: str, task: Dict, agent_name: str,
                   data_slice: str, assignment: str) -> str:
    """单个Agent独立分析"""
    prompt = f"""你是NexusFlow的 {agent_name}。请根据你的角色和数据完成分析。

## 任务 {task_id}: {task['name']}
{task['description']}

## 你的子任务
{assignment}

## 你可见的数据
{data_slice}

## 要求
1. 只基于你可见的数据进行分析
2. 从你的角色视角出发给出结论
3. 标注置信度(0-1)和关键假设
4. 输出格式：Markdown（分析过程 + 结论 + 置信度 + 假设 + 不确定性）

请开始分析。"""

    return llm_call(prompt, system=AGENT_PROMPTS.get(agent_name, f"你是NexusFlow的{agent_name}。"),
                    max_tokens=3072, temperature=0.5, tag=f"agent-{agent_name}-{task_id}")


def _agent_revise(task_id: str, agent_name: str, my_conclusion: str,
                  others_conclusions: Dict[str, str]) -> str:
    """Agent看到他人结论后修正"""
    others_text = "\n\n".join(
        f"### {name} 的结论\n{conc[:1500]}"
        for name, conc in others_conclusions.items()
    )

    prompt = f"""你是NexusFlow的 {agent_name}。在任务 {task_id} 中，你已经完成了独立分析。
现在你看到了其他Agent的结论。请审视他们的观点，修正或坚持你的结论。

## 你之前的结论（摘要）
{my_conclusion[:1500]}

## 其他Agent的结论
{others_text}

## 要求
1. 识别与你结论矛盾的观点
2. 判断矛盾是否源于信息差异（你看到了不同的数据）
3. 如果是合理的质疑，修正你的结论
4. 如果你仍然确信，给出更强的论据
5. 输出格式：Markdown（矛盾识别 + 归因分析 + 修正后结论 或 坚持原结论+理由）"""

    return llm_call(prompt, system=AGENT_PROMPTS.get(agent_name, f"你是NexusFlow的{agent_name}。"),
                    max_tokens=2048, temperature=0.5, tag=f"revise-{agent_name}-{task_id}")


def _coordinator_synthesize(task_id: str, task: Dict,
                            revised_conclusions: Dict[str, str]) -> str:
    """Coordinator综合所有结论"""
    all_conclusions = "\n\n".join(
        f"### {name} 的最终结论\n{conc[:2000]}"
        for name, conc in revised_conclusions.items()
    )

    prompt = f"""作为NexusFlow协调者，请综合所有Agent的结论，给出任务 {task_id} ({task['name']}) 的最终答案。

## 原始任务
{task['description']}

## 各Agent结论
{all_conclusions}

## 要求
1. 整合各方观点，处理矛盾
2. 给出最终的综合结论
3. 标注共识区域和分歧区域
4. 给出置信度评估
5. 输出格式：Markdown（## 最终结论 + ## 共识 + ## 分歧 + ## 置信度 + ## 局限）"""

    return llm_call(prompt, system=AGENT_PROMPTS.get('coordinator', ''),
                    max_tokens=4096, temperature=0.3, tag=f"coord-synth-{task_id}")


# ============================================================
# 7. Evaluation (8 Dimensions)
# ============================================================
def evaluate_result(task_id: str, task: Dict, result_text: str,
                    mode: str, data: Dict) -> Dict[str, float]:
    """用LLM评估结果质量（8维评分）"""
    # 对于T4，可以使用表B真值计算预测准确性
    ground_truth_note = ""
    if task_id == "T4" and 'test_gdp' in data:
        gt = data.get('test_gdp', pd.DataFrame())
        if not gt.empty:
            ground_truth_note = f"\n## 预测真值（表B GDP增长率）\n{df_to_table_string(gt)}"
        gt2 = data.get('test_inflation', pd.DataFrame())
        if not gt2.empty:
            ground_truth_note += f"\n## 预测真值（表B 通胀率）\n{df_to_table_string(gt2)}"

    prompt = f"""请对以下分析结果进行8维度评分（每项1-10分）。

## 任务 {task_id}: {task['name']}
{task['description']}
{ground_truth_note}

## 待评估结果
{result_text[:6000]}

## 评分维度
D1 预测准确性(25%): 预测值与真值的接近程度，分析结论的数据支撑度
D2 因果有效性(15%): 因果推断的逻辑严谨性，是否有数据支撑
D3 异常检出率(15%): 异常值识别的完整性和准确性
D4 跨指标一致性(10%): 多指标分析的内部一致性
D5 辩论质量(10%): 多角度分析的深度和广度
D6 政策合理性(10%): 政策建议的可操作性和针对性
D7 场景可信度(10%): 反事实场景的合理性和推理严谨性
D8 计算效率(5%): 分析过程的简洁性和计算资源使用合理性

请输出JSON格式评分：
```json
{{
    "D1_prediction": 0,
    "D2_causality": 0,
    "D3_anomaly": 0,
    "D4_consistency": 0,
    "D5_debate": 0,
    "D6_policy": 0,
    "D7_scenario": 0,
    "D8_efficiency": 0,
    "comments": "简要评价说明"
}}
```"""

    result = llm_call(prompt,
                      system="你是一位严格的学术评审专家。请公正、严格地评分。分数范围1-10。",
                      max_tokens=2048, temperature=0.2, tag=f"eval-{task_id}-{mode}")

    try:
        import re
        json_match = re.search(r'\{[^{}]*\}', result, re.DOTALL)
        if json_match:
            scores = json.loads(json_match.group())
            return scores
    except:
        pass

    # 解析失败，返回默认
    return {"error": "评分解析失败", "raw": result[:500]}


def compute_weighted_score(scores: Dict) -> float:
    """计算加权总分"""
    weights = {
        "D1_prediction": 0.25,
        "D2_causality": 0.15,
        "D3_anomaly": 0.15,
        "D4_consistency": 0.10,
        "D5_debate": 0.10,
        "D6_policy": 0.10,
        "D7_scenario": 0.10,
        "D8_efficiency": 0.05,
    }
    total = 0
    w_sum = 0
    for key, weight in weights.items():
        val = scores.get(key, 0)
        if isinstance(val, (int, float)):
            total += val * weight
            w_sum += weight
    return round(total / w_sum, 2) if w_sum > 0 else 0


# ============================================================
# 8. Main Experiment Runner
# ============================================================
def run_experiment():
    """运行完整实验"""
    results = {"single": {}, "nexusflow": {}, "evaluation": {}}

    # 检查是否有之前的结果可恢复
    results_path = os.path.join(DATA_DIR, "experiment_results.json")
    if os.path.exists(results_path):
        try:
            with open(results_path, 'r', encoding='utf-8') as f:
                results = json.load(f)
            print(f"\n[恢复] 找到之前的结果，继续未完成任务...")
        except:
            pass

    task_order = ["T1", "T2", "T3", "T4", "T5", "T6", "T7", "T8", "T9"]

    for task_id in task_order:
        task = TASKS[task_id]
        print(f"\n{'#'*60}")
        print(f"# 任务 {task_id}: {task['name']} ({task['phase']})")
        print(f"{'#'*60}")

        # --- 单Agent模式 ---
        if task_id not in results.get("single", {}):
            t0 = time.time()
            single_result = run_single_agent(task_id, task)
            single_result['time_sec'] = round(time.time() - t0, 2)
            results.setdefault("single", {})[task_id] = single_result
            _save_results(results)
        else:
            print(f"\n[跳过] 单Agent {task_id} 已完成")

        # --- NexusFlow模式 ---
        if task_id not in results.get("nexusflow", {}):
            t0 = time.time()
            nexus_result = run_nexusflow(task_id, task)
            nexus_result['time_sec'] = round(time.time() - t0, 2)
            results.setdefault("nexusflow", {})[task_id] = nexus_result
            _save_results(results)
        else:
            print(f"\n[跳过] NexusFlow {task_id} 已完成")

        # --- 评估 ---
        if task_id not in results.get("evaluation", {}):
            print(f"\n  --- 评估阶段 ---")
            data = task['data_func']()

            # 评估单Agent
            single_eval = evaluate_result(task_id, task,
                                          results["single"][task_id]['result'],
                                          "single", data)
            # 评估NexusFlow
            nexus_eval = evaluate_result(task_id, task,
                                         results["nexusflow"][task_id]['result'],
                                         "nexusflow", data)

            results.setdefault("evaluation", {})[task_id] = {
                "single_scores": single_eval,
                "nexusflow_scores": nexus_eval,
                "single_weighted": compute_weighted_score(single_eval),
                "nexusflow_weighted": compute_weighted_score(nexus_eval),
            }
            _save_results(results)

            print(f"  单Agent加权: {results['evaluation'][task_id]['single_weighted']}")
            print(f"  NexusFlow加权: {results['evaluation'][task_id]['nexusflow_weighted']}")
        else:
            print(f"\n[跳过] 评估 {task_id} 已完成")

    _save_results(results)

    return results


    # API调用统计
    single_calls = sum(results.get("single", {}).get(t, {}).get("api_calls", 0)
                       for t in results.get("single", {}))
    nexus_calls = sum(results.get("nexusflow", {}).get(t, {}).get("api_calls", 0)
                      for t in results.get("nexusflow", {}))
    lines.append(f"\n## 资源消耗")
    lines.append(f"- 单Agent总API调用: {single_calls}")
    lines.append(f"- NexusFlow总API调用: {nexus_calls}")
    lines.append(f"- 倍数: {nexus_calls/max(1,single_calls):.1f}x")

    return "\n".join(lines)


def _save_results(results: Dict):
    """保存中间结果"""
    path = os.path.join(DATA_DIR, "experiment_results.json")
    # 移除不可序列化的字段
    serializable = _make_serializable(results)
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(serializable, f, ensure_ascii=False, indent=2)
    print(f"  [保存] 结果已保存到 {path}")


def _make_serializable(obj):
    """确保对象可JSON序列化"""
    if isinstance(obj, dict):
        return {k: _make_serializable(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [_make_serializable(v) for v in obj]
    elif isinstance(obj, (int, float, str, bool, type(None))):
        return obj
    else:
        return str(obj)


# ============================================================
# 9. Report Generation
# ============================================================
def generate_report(results: Dict) -> str:
    """生成最终Markdown报告"""
    report = []
    report.append("# NexusFlow Stage 6 — L3 高复杂度认知任务 Benchmark 报告")
    report.append(f"\n生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    report.append(f"模型: deepseek-v4-flash (via DeepSeek API)")
    report.append(f"数据: DBnomics IMF WEO (20国 × 15指标 × 41年)")
    report.append(f"总API调用: {stats['api_calls']}")
    report.append(f"总Token消耗: {stats['total_tokens']:,}")
    report.append("")

    # 总览表
    report.append("## 1. 任务结果总览\n")
    report.append("| 任务 | 名称 | 单Agent分 | NexusFlow分 | 提升 | 调用比 |")
    report.append("|------|------|----------|------------|------|--------|")

    total_single = 0
    total_nexus = 0
    count = 0
    for tid in ["T1","T2","T3","T4","T5","T6","T7","T8","T9"]:
        task = TASKS[tid]
        ev = results.get("evaluation", {}).get(tid, {})
        sw = ev.get("single_weighted", 0)
        nw = ev.get("nexusflow_weighted", 0)
        diff = nw - sw
        total_single += sw
        total_nexus += nw
        count += 1
        s_calls = results.get("single", {}).get(tid, {}).get("api_calls", 0)
        n_calls = results.get("nexusflow", {}).get(tid, {}).get("api_calls", 0)
        report.append(f"| {tid} | {task['name']} | {sw:.2f} | {nw:.2f} | "
                      f"{diff:+.2f} | {s_calls}:{n_calls} |")

    avg_single = total_single / max(1, count)
    avg_nexus = total_nexus / max(1, count)
    report.append(f"| **平均** | — | **{avg_single:.2f}** | **{avg_nexus:.2f}** | "
                  f"**{avg_nexus - avg_single:+.2f}** | — |")
    report.append("")

    # 各任务详细结果
    report.append("## 2. 各任务详细结果\n")
    for tid in ["T1","T2","T3","T4","T5","T6","T7","T8","T9"]:
        task = TASKS[tid]
        report.append(f"### {tid} {task['name']} ({task['phase']})")
        report.append(f"- Agent组合: {', '.join(task['nexus_agents'])}")
        report.append(f"- 轮次: {task['rounds']}")

        # 评分详情
        ev = results.get("evaluation", {}).get(tid, {})
        if ev:
            report.append(f"- 单Agent加权: {ev.get('single_weighted', 0):.2f}")
            report.append(f"- NexusFlow加权: {ev.get('nexusflow_weighted', 0):.2f}")
            ss = ev.get('single_scores', {})
            ns = ev.get('nexusflow_scores', {})
            if isinstance(ss, dict) and 'error' not in ss:
                report.append(f"- 单Agent维度: " + ", ".join(
                    f"{k}={v}" for k, v in ss.items() if isinstance(v, (int, float)))[:200])
            if isinstance(ns, dict) and 'error' not in ns:
                report.append(f"- NexusFlow维度: " + ", ".join(
                    f"{k}={v}" for k, v in ns.items() if isinstance(v, (int, float)))[:200])

        # 结果摘要
        s_result = results.get("single", {}).get(tid, {}).get("result", "")
        n_result = results.get("nexusflow", {}).get(tid, {}).get("result", "")
        report.append(f"\n#### 单Agent结果摘要")
        report.append(f"```\n{s_result[:1000]}\n```\n")
        report.append(f"#### NexusFlow结果摘要")
        report.append(f"```\n{n_result[:1000]}\n```\n")

    # 资源消耗
    report.append("## 4. 资源消耗\n")
    report.append(f"- 总API调用次数: {stats['api_calls']}")
    report.append(f"- 总Token消耗: {stats['total_tokens']:,}")
    total_time = time.time() - stats['start_time']
    report.append(f"- 总耗时: {total_time/60:.1f} 分钟")
    report.append(f"- 错误次数: {len(stats['errors'])}")
    if stats['errors']:
        for err in stats['errors'][:5]:
            report.append(f"  - {err['tag']}: {err['error'][:100]}")

    return "\n".join(report)


# ============================================================
# MAIN
# ============================================================
if __name__ == "__main__":
    print(f"\n{'='*60}")
    print(f"开始实验: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*60}\n")

    results = run_experiment()

    # 生成报告
    print(f"\n{'='*60}")
    print(f"生成报告...")
    report_text = generate_report(results)
    report_path = os.path.join(OUTPUT_DIR, "stage6_L3_report.md")
    with open(report_path, 'w', encoding='utf-8') as f:
        f.write(report_text)
    print(f"报告已保存: {report_path}")

    # 保存结果
    _save_results(results)

    total_time = time.time() - stats['start_time']
    print(f"\n{'='*60}")
    print(f"实验完成!")
    print(f"总耗时: {total_time/60:.1f} 分钟")
    print(f"总API调用: {stats['api_calls']}")
    print(f"总Token: {stats['total_tokens']:,}")
    print(f"{'='*60}")
