#!/usr/bin/env python3
"""
NexusFlow vs Single-Agent 公平对比 Benchmark (80步 vs 80步)
============================================================
两种模式使用相同分析维度，步数完全相同（各80步）。
每步真实API调用 + 独立质量评估 = 共320次API调用。
零模拟，全量可验证。

任务: 中国大宗商品市场深度分析
"""

import json, os, sys, time, urllib.request, traceback
from datetime import datetime

# ============================================================
# 配置
# ============================================================
API_KEY = os.environ.get('DEEPSEEK_API_KEY', 'sk-your-key-here')
API_URL = 'https://api.deepseek.com/v1/chat/completions'
MODEL = 'deepseek-chat'
OUTPUT_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(OUTPUT_DIR, 'data')
os.makedirs(DATA_DIR, exist_ok=True)

# ============================================================
# API 调用（真实）
# ============================================================
def call_llm(system_prompt: str, user_prompt: str, max_tokens: int = 2048, temperature: float = 0.7) -> dict:
    """调用 DeepSeek API，返回 {content, tokens, time_sec}"""
    payload = json.dumps({
        'model': MODEL,
        'messages': [
            {'role': 'system', 'content': system_prompt},
            {'role': 'user', 'content': user_prompt}
        ],
        'max_tokens': max_tokens,
        'temperature': temperature
    }).encode('utf-8')

    req = urllib.request.Request(API_URL, data=payload, headers={
        'Content-Type': 'application/json',
        'Authorization': f'Bearer {API_KEY}'
    })

    t0 = time.time()
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            result = json.loads(resp.read().decode('utf-8'))
        dur = time.time() - t0
        usage = result.get('usage', {})
        return {
            'content': result['choices'][0]['message']['content'],
            'prompt_tokens': usage.get('prompt_tokens', 0),
            'completion_tokens': usage.get('completion_tokens', 0),
            'total_tokens': usage.get('total_tokens', 0),
            'time_sec': round(dur, 2),
            'error': None
        }
    except Exception as e:
        dur = time.time() - t0
        return {
            'content': '',
            'prompt_tokens': 0,
            'completion_tokens': 0,
            'total_tokens': 0,
            'time_sec': round(dur, 2),
            'error': str(e)
        }

# ============================================================
# 数据加载
# ============================================================
def load_data_summary() -> str:
    """加载之前采集的大宗商品数据摘要"""
    summary_path = os.path.join(OUTPUT_DIR, '..', 'commodity_benchmark', 'data', 'full_data_summary.txt')
    if os.path.exists(summary_path):
        with open(summary_path, 'r') as f:
            return f.read()
    return generate_data_summary()

def generate_data_summary() -> str:
    """从已采集的数据文件生成摘要"""
    data_dir = os.path.join(OUTPUT_DIR, '..', 'commodity_benchmark', 'data')
    parts = []

    elec_path = os.path.join(data_dir, 'electricity_parsed.json')
    if os.path.exists(elec_path):
        with open(elec_path) as f:
            elec = json.load(f)
        parts.append(f"【社会用电量】\n{json.dumps(elec[-10:], ensure_ascii=False, indent=1)}")

    spot_path = os.path.join(data_dir, 'spot_parsed.json')
    if os.path.exists(spot_path):
        with open(spot_path) as f:
            spot = json.load(f)
        parts.append(f"【现货基差（前20品种）】\n{json.dumps(spot[:20], ensure_ascii=False, indent=1)}")

    for exchange, fname in [('SHFE', 'contract_shfe.json'), ('INE', 'contract_ine.json'), ('GFEX', 'contract_gfex.json')]:
        cpath = os.path.join(data_dir, fname)
        if os.path.exists(cpath):
            with open(cpath) as f:
                contracts = json.load(f)
            sample = contracts[:5] if isinstance(contracts, list) else str(contracts)[:500]
            parts.append(f"【{exchange}合约（示例）】\n{json.dumps(sample, ensure_ascii=False, indent=1)[:1500]}")

    if parts:
        return "\n\n".join(parts)
    return "（无可用数据，请确保 commodity_benchmark/data/ 目录包含采集数据）"

# ============================================================
# 质量评估（独立LLM调用，judge模式）
# ============================================================
def evaluate_quality(step_desc: str, output: str, context: str = "") -> dict:
    """用独立LLM调用评估输出质量，返回 {score, reasoning}"""
    if not output or len(output) < 20:
        return {'score': 1, 'reasoning': '输出为空或过短'}

    judge_prompt = """你是一个严格的分析质量评审专家。请评估以下分析的质量。

评分标准（1-10）：
- 9-10: 深度专业分析，有数据支撑，逻辑严密，见解独到
- 7-8: 较好的分析，覆盖主要维度，有合理推理
- 5-6: 一般分析，有基本内容但缺乏深度
- 3-4: 浅层分析，大量泛泛而谈
- 1-2: 无关或严重错误

请严格按JSON格式回复，不要有其他内容。"""

    user_prompt = f"""分析任务: {step_desc}
{"上下文: " + context[:300] if context else ""}

待评估分析:
{output[:2000]}

请回复JSON: {{"score": 数字, "reasoning": "一句话评价"}}"""

    result = call_llm(judge_prompt, user_prompt, max_tokens=200, temperature=0.1)
    if result['error']:
        return basic_quality(output)

    try:
        content = result['content'].strip()
        if content.startswith('```'):
            content = content.split('\n', 1)[-1].rsplit('```', 1)[0]
        score_data = json.loads(content)
        score = int(score_data.get('score', 5))
        return {'score': max(1, min(10, score)), 'reasoning': score_data.get('reasoning', '')}
    except Exception:
        return basic_quality(output)

def basic_quality(output: str) -> dict:
    """基于文本特征的基础质量评估（无LLM调用）"""
    length = len(output)
    if length < 50: return {'score': 2, 'reasoning': '输出过短'}
    if length < 150: return {'score': 4, 'reasoning': '输出较短'}
    if length < 400: return {'score': 5, 'reasoning': '长度一般'}
    if length < 800: return {'score': 6, 'reasoning': '长度足够'}
    has_numbers = any(c.isdigit() for c in output)
    has_logic = any(w in output for w in ['因此', '由于', '但是', '然而', '首先', '其次', '最后', '综上'])
    has_special = any(w in output for w in ['%', '同比', '环比', '上涨', '下跌', '供应', '需求'])
    score = 5
    if has_numbers: score += 1
    if has_logic: score += 1
    if has_special: score += 1
    if length > 1200: score += 1
    return {'score': min(9, score), 'reasoning': f'基于文本特征评估(长度{length})'}

# ============================================================
# NexusFlow Agent 角色定义（10个角色）
# ============================================================
NEXUSFLOW_AGENTS = {
    'Coordinator': {
        'system': '你是NexusFlow多Agent系统的协调者。负责统筹分析任务、分配工作、主持讨论、确保分析的一致性和完整性。你不直接分析品种，而是协调各专业Agent。',
    },
    'MacroAnalyst': {
        'system': '你是NexusFlow的宏观经济分析师。专长：GDP、PMI、CPI、货币政策、财政政策对大宗商品的影响。你关注宏观因子如何传导到商品需求。',
    },
    'DataEngineer': {
        'system': '你是NexusFlow的数据工程师。负责数据质量审查、缺失数据识别、数据预处理建议。你确保所有分析基于可靠数据。',
    },
    'EnergyAnalyst': {
        'system': '你是NexusFlow的能源分析师。专长：原油、燃料油、LPG。你关注OPEC+、库存、地缘政治、需求季节性。',
    },
    'MetalsAnalyst': {
        'system': '你是NexusFlow的金属分析师。专长：黑色系（螺纹/热卷/铁矿）和有色金属（铜/铝/锌/镍）。你关注产业链利润、库存周期、供需平衡。',
    },
    'PreciousAnalyst': {
        'system': '你是NexusFlow的贵金属分析师。专长：黄金、白银。你关注实际利率、央行购金、地缘风险、金银比。',
    },
    'ChemicalAnalyst': {
        'system': '你是NexusFlow的化工品分析师。专长：甲醇、PTA、PE、PP。你关注产业链利润传导、开工率、成本曲线。',
    },
    'AgroAnalyst': {
        'system': '你是NexusFlow的农产品分析师。专长：豆粕、棕榈油等。你关注天气、种植周期、进出口、生物柴油政策。',
    },
    'QuantStrategist': {
        'system': '你是NexusFlow的量化策略师。专长：相关性分析、套利组合、CTA策略、风险预算、统计特征分析。你用量化思维分析品种间关系。',
    },
    'RiskManager': {
        'system': '你是NexusFlow的风险管理师。专长：压力测试、仓位管理、黑天鹅应对、套保方案。你从风险角度审视所有策略。',
    },
}

# ============================================================
# Single-Agent 80步任务定义
# ============================================================
def get_sa_tasks(data_summary: str) -> list:
    """Single-Agent 80步：P1(6) + P2(24) + P3(6) + P4(8) + P5(14) + P6(7) + P7(9) = 74 → 补齐到80"""
    tasks = []
    ds = data_summary  # 简写

    # ===================== P1-数据解读: 6步 =====================
    tasks.append({
        'id': 1, 'phase': 'P1-数据解读',
        'system': '你是宏观经济分析师，专注中国实体经济研究。',
        'desc': '分析社会用电量数据，解读经济活跃度信号',
        'user': f'以下是中国2024-2026年社会用电量月度数据:\n{ds[:1500]}\n\n请分析：1.用电量趋势和拐点 2.季节性规律 3.与经济周期的关系 4.对大宗商品需求的指引'
    })
    tasks.append({
        'id': 2, 'phase': 'P1-数据解读',
        'system': '你是期货市场数据分析师。',
        'desc': '分析现货基差结构，解读市场供需信号',
        'user': f'以下是53个品种的现货基差数据:\n{ds[1500:3500]}\n\n请分析：1.基差最大和最小的品种 2.Backwardation和Contango结构 3.反映的供需紧张程度 4.套利机会'
    })
    tasks.append({
        'id': 3, 'phase': 'P1-数据解读',
        'system': '你是期货合约研究员。',
        'desc': '分析合约流动性和交易参数',
        'user': f'以下是SHFE+INE+GFEX合约信息:\n{ds[3500:5500]}\n\n请分析：1.各品种合约流动性（成交量/持仓量）2.主力合约切换特征 3.交易成本对比 4.适合不同策略的品种筛选'
    })
    tasks.append({
        'id': 4, 'phase': 'P1-数据解读',
        'system': '你是仓单数据分析师。',
        'desc': '分析仓单数据，解读交割信号',
        'user': f'以下是上期所和广期所仓单数据:\n{ds[5500:7500]}\n\n请分析：1.各品种仓单变动趋势 2.交割月压力 3.库存周期位置 4.对价格的指引意义'
    })
    tasks.append({
        'id': 5, 'phase': 'P1-数据解读',
        'system': '你是期货持仓分析师。',
        'desc': '分析持仓排名和资金流向',
        'user': f'基于合约数据:\n{ds[3500:5000]}\n\n请分析：1.主要品种持仓集中度 2.多空持仓比变化 3.主力资金流向信号 4.持仓结构与趋势判断'
    })
    tasks.append({
        'id': 6, 'phase': 'P1-数据解读',
        'system': '你是大宗商品数据工程师。',
        'desc': '评估数据质量和完整性',
        'user': f'以下是已采集的全部数据摘要:\n{ds[:4000]}\n\n请评估：1.数据覆盖率 2.缺失维度 3.数据质量问题（异常值/缺失值）4.对后续分析的影响 5.补充建议'
    })

    # ===================== P2-单品种: 24步 =====================
    # 原油(2)
    tasks.append({
        'id': 7, 'phase': 'P2-单品种',
        'system': '你是能源市场高级分析师，10年从业经验。',
        'desc': '原油市场供需深度分析',
        'user': f'用电分析(反映工业需求):\n{ds[:800]}\n基差数据(能化品种):\n{ds[1500:2200]}\n\n请深度分析原油市场：1.OPEC+产量政策影响 2.中国原油进口需求 3.库存周期 4.价格走势判断和关键价位'
    })
    tasks.append({
        'id': 8, 'phase': 'P2-单品种',
        'system': '你是能源市场策略分析师。',
        'desc': '原油技术面与资金面分析',
        'user': f'原油基差与合约:\n{ds[1500:2000]}\n\n请分析：1.原油期限结构（Back/Contango信号）2.内外盘价差（SC-Brent）3.持仓与资金面 4.技术面关键位'
    })
    # 燃料油(1)
    tasks.append({
        'id': 9, 'phase': 'P2-单品种',
        'system': '你是能源化工分析师。',
        'desc': '燃料油与LPG分析',
        'user': f'能源相关基差:\n{ds[1500:2000]}\n合约信息:\n{ds[3500:4200]}\n\n请分析：1.燃料油供需（航运需求+发电需求）2.LPG供需（化工需求+民用需求）3.与原油的联动关系 4.价差策略'
    })
    # 螺纹(2)
    tasks.append({
        'id': 10, 'phase': 'P2-单品种',
        'system': '你是黑色金属首席分析师。',
        'desc': '螺纹钢供需与利润分析',
        'user': f'用电数据(反映钢铁行业开工):\n{ds[:600]}\n基差数据(黑色品种):\n{ds[1500:2000]}\n\n请深度分析：1.钢厂利润与产能利用率 2.下游地产+基建+制造业需求 3.库存去化节奏 4.价格判断与逻辑'
    })
    tasks.append({
        'id': 11, 'phase': 'P2-单品种',
        'system': '你是黑色金属策略分析师。',
        'desc': '螺纹钢与热卷价差及季节性分析',
        'user': f'黑色品种基差:\n{ds[1500:1800]}\n\n请分析：1.螺纹-热卷价差逻辑 2.季节性需求节奏 3.区域价差 4.电炉vs高炉成本差异 5.价格弹性分析'
    })
    # 铁矿(1)
    tasks.append({
        'id': 12, 'phase': 'P2-单品种',
        'system': '你是铁矿石分析师。',
        'desc': '铁矿石供需与估值分析',
        'user': f'黑色品种基差:\n{ds[1500:1800]}\n\n请分析：1.全球铁矿供应（澳洲/巴西发运）2.中国港口库存 3.钢厂补库节奏 4.价格中枢与估值 5.非主流矿供应弹性'
    })
    # 铜(2)
    tasks.append({
        'id': 13, 'phase': 'P2-单品种',
        'system': '你是有色金属首席分析师。',
        'desc': '铜市场供需深度分析',
        'user': f'用电数据(铜消费与电力相关):\n{ds[:500]}\n基差:\n{ds[1500:1900]}\n仓单数据:\n{ds[5500:6500]}\n\n请深度分析：1.全球铜矿供应（智利/秘鲁/刚果金）2.中国冶炼产能与利润 3.下游需求（电网/新能源/空调）4.库存与基差信号 5.价格判断'
    })
    tasks.append({
        'id': 14, 'phase': 'P2-单品种',
        'system': '你是铜市场策略分析师。',
        'desc': '铜的宏观与资金面分析',
        'user': f'铜基差与合约:\n{ds[1500:1900]}\n\n请分析：1.全球铜的宏观需求驱动（中国/印度/欧美）2.铜的金融属性与资金面 3.期限结构 4.内外盘比价 5.铜的长期供需缺口展望'
    })
    # 铝(1)
    tasks.append({
        'id': 15, 'phase': 'P2-单品种',
        'system': '你是铝市场分析师。',
        'desc': '铝市场深度分析',
        'user': f'有色基差:\n{ds[1600:1900]}\n用电数据(电解铝成本核心):\n{ds[:400]}\n\n请分析：1.电解铝产能天花板与运行产能 2.电力成本（水电/火电）3.下游需求（建筑/汽车/光伏）4.氧化铝成本 5.价格判断'
    })
    # 锌镍(1)
    tasks.append({
        'id': 16, 'phase': 'P2-单品种',
        'system': '你是锌镍分析师。',
        'desc': '锌镍市场分析',
        'user': f'有色基差:\n{ds[1600:1900]}\n\n请分析：1.锌矿供应+冶炼利润+镀锌需求 2.镍的供应（印尼NPI）+不锈钢需求+新能源三元材料 3.两品种的库存与基差信号'
    })
    # 黄金(2)
    tasks.append({
        'id': 17, 'phase': 'P2-单品种',
        'system': '你是贵金属与宏观策略分析师。',
        'desc': '黄金深度分析',
        'user': f'宏观数据:\n{ds[:600]}\n基差:\n{ds[1500:1700]}\n\n请深度分析：1.美联储货币政策路径 2.全球央行购金趋势 3.地缘政治风险溢价 4.实际利率与金价关系 5.配置建议'
    })
    tasks.append({
        'id': 18, 'phase': 'P2-单品种',
        'system': '你是贵金属量化分析师。',
        'desc': '黄金技术面与资金流分析',
        'user': f'黄金基差与持仓:\n{ds[1500:1700]}\n\n请分析：1.黄金期限结构 2.CFTC持仓变化 3.ETF持仓与资金流 4.技术分析关键位 5.央行购金数据解读'
    })
    # 白银(1)
    tasks.append({
        'id': 19, 'phase': 'P2-单品种',
        'system': '你是贵金属分析师。',
        'desc': '白银分析+金银比策略',
        'user': f'贵金属基差:\n{ds[1500:1700]}\n\n请分析：1.白银工业属性（光伏用银）vs货币属性 2.金银比历史与当前水平 3.白银供需平衡 4.金银比策略建议'
    })
    # 甲醇(1)
    tasks.append({
        'id': 20, 'phase': 'P2-单品种',
        'system': '你是化工品分析师。',
        'desc': '甲醇市场分析',
        'user': f'化工基差:\n{ds[1800:2400]}\n合约:\n{ds[4000:4800]}\n\n请分析：1.煤化工vs气化工成本曲线 2.MTO需求与利润 3.港口库存 4.进口依存度 5.价格判断'
    })
    # PTA(1)
    tasks.append({
        'id': 21, 'phase': 'P2-单品种',
        'system': '你是聚酯产业链分析师。',
        'desc': 'PTA产业链分析',
        'user': f'化工基差:\n{ds[1800:2400]}\n\n请分析：1.PX-PTA-聚酯产业链利润分配 2.PTA开工率与库存 3.聚酯终端需求（纺服/包装）4.新产能投放节奏'
    })
    # PE(1)
    tasks.append({
        'id': 22, 'phase': 'P2-单品种',
        'system': '你是聚烯烃分析师。',
        'desc': 'PE市场分析',
        'user': f'化工基差:\n{ds[1800:2200]}\n\n请分析：1.聚乙烯（油制vs煤制成本+新增产能）2.农膜/包装需求季节性 3.进口依存度 4.价格判断'
    })
    # PP(1)
    tasks.append({
        'id': 23, 'phase': 'P2-单品种',
        'system': '你是聚烯烃分析师。',
        'desc': 'PP市场分析',
        'user': f'化工基差:\n{ds[1800:2200]}\n\n请分析：1.聚丙烯（PDH利润+纤维/注塑需求）2.PP-PE价差逻辑 3.新增产能 4.价格判断'
    })
    # 豆粕(1)
    tasks.append({
        'id': 24, 'phase': 'P2-单品种',
        'system': '你是农产品分析师。',
        'desc': '豆粕市场分析',
        'user': f'农产品基差:\n{ds[2000:2600]}\n\n请分析：1.美豆种植与出口 2.中国压榨利润 3.生猪需求与饲料产量 4.USDA库存报告解读 5.价格判断'
    })
    # 棕榈油(1)
    tasks.append({
        'id': 25, 'phase': 'P2-单品种',
        'system': '你是油脂分析师。',
        'desc': '棕榈油市场分析',
        'user': f'农产品基差:\n{ds[2000:2600]}\n\n请分析：1.东南亚产量与出口 2.中国进口节奏 3.生物柴油政策（印尼B35）4.油脂油料联动 5.价格判断'
    })
    # 跨品种价差(2)
    tasks.append({
        'id': 26, 'phase': 'P2-单品种',
        'system': '你是量化价差分析师。',
        'desc': '能化跨品种价差分析',
        'user': f'能化品种基差:\n{ds[1500:2400]}\n\n请分析：1.裂解价差（原油→成品油→化工品）2.甲醇-PE/PP利润链 3.PTA-聚酯利润 4.能化品种间的替代与联动 5.最佳价差策略'
    })
    tasks.append({
        'id': 27, 'phase': 'P2-单品种',
        'system': '你是量化价差分析师。',
        'desc': '黑色有色跨品种价差分析',
        'user': f'黑色有色基差:\n{ds[1500:2000]}\n\n请分析：1.螺矿比（钢厂利润信号）2.卷螺差 3.铜铝比 4.金银比 5.各价差的均值回归特征与当前偏离度'
    })
    # 持仓分析(2)
    tasks.append({
        'id': 28, 'phase': 'P2-单品种',
        'system': '你是持仓与资金流分析师。',
        'desc': '主力合约持仓结构分析',
        'user': f'基于合约数据:\n{ds[3500:5500]}\n\n请分析：1.各板块主力合约持仓集中度 2.前20多空持仓比 3.主力资金进出信号 4.对短期走势的指引'
    })
    tasks.append({
        'id': 29, 'phase': 'P2-单品种',
        'system': '你是资金流分析师。',
        'desc': '跨品种资金流向比较',
        'user': f'基于合约持仓数据:\n{ds[3500:5500]}\n\n请分析：1.资金从哪些板块流出/流入 2.主力合约换月对资金流的影响 3.各品种成交量与持仓量变化趋势 4.异常信号'
    })
    # 补充P2到24步：再加一个跨品种价差分析和一个品种分析
    tasks.append({
        'id': 30, 'phase': 'P2-单品种',
        'system': '你是价差策略师。',
        'desc': '跨期价差与月差分析',
        'user': f'基于合约数据:\n{ds[3500:5500]}\n\n请分析：1.各品种近远月价差结构（Back/Contango）2.月差变化趋势 3.反映的供需预期 4.跨期套利机会'
    })

    # ===================== P3-产业链: 6步 =====================
    tasks.append({
        'id': 31, 'phase': 'P3-产业链',
        'system': '你是产业链研究专家。',
        'desc': '能源-化工产业链利润传导',
        'user': f'请基于前面分析结果，梳理能源→化工的利润传导链:\n原油→石脑油→PX→PTA→聚酯\n原油→甲醇→烯烃→终端\n\n重点分析：1.各环节利润分配 2.利润压缩/扩张的触发条件 3.当前产业链最脆弱的环节 4.与历史对比'
    })
    tasks.append({
        'id': 32, 'phase': 'P3-产业链',
        'system': '你是产业链研究专家。',
        'desc': '黑色产业链利润传导',
        'user': f'请梳理黑色金属产业链利润传导:\n铁矿石+焦煤→生铁→粗钢→螺纹钢/热卷→终端(地产/基建/汽车)\n\n重点：1.钢厂利润与产量弹性 2.铁矿vs焦炭的博弈 3.终端需求的季节性节奏 4.产业链利润分配的当前状态'
    })
    tasks.append({
        'id': 33, 'phase': 'P3-产业链',
        'system': '你是产业链研究专家。',
        'desc': '有色新能源产业链关联分析',
        'user': f'请分析有色金属产业链与新能源的交叉:\n铜→电网/新能源车/光伏\n铝→建筑/汽车轻量化/光伏边框\n镍→不锈钢/三元电池\n\n重点：1.新能源对有色需求的增量贡献 2.各品种的新能源含量对比 3.能源转型对有色格局的长期影响'
    })
    tasks.append({
        'id': 34, 'phase': 'P3-产业链',
        'system': '你是产业链比较研究专家。',
        'desc': '跨产业链比较分析',
        'user': f'请对比分析三大产业链:\n1.能源化工链 vs 黑色链 vs 有色链 的利润周期位置 2.哪条产业链利润最丰厚/最承压 3.产业链间的联动（能源成本→全产业链） 4.哪个产业链的投资机会最多'
    })
    tasks.append({
        'id': 35, 'phase': 'P3-产业链',
        'system': '你是利润周期研究专家。',
        'desc': '产业链利润周期与拐点判断',
        'user': f'请分析当前各产业链的利润周期:\n1.能源化工链利润处于周期什么位置 2.黑色链利润拐点信号 3.有色链新能源红利还能持续多久 4.哪个产业链利润有扩张/压缩空间 5.产业链利润的领先指标'
    })
    tasks.append({
        'id': 36, 'phase': 'P3-产业链',
        'system': '你是供应链风险分析师。',
        'desc': '产业链脆弱性与断链风险',
        'user': f'请评估各产业链的脆弱性:\n1.能源链对中东地缘的敏感度 2.黑色链对地产政策的依赖度 3.有色链对海外矿端的依存度 4.化工链对进口原油的敞口 5.最可能的断链风险点和传导路径'
    })

    # ===================== P4-宏观: 8步 =====================
    tasks.append({
        'id': 37, 'phase': 'P4-宏观',
        'system': '你是中国宏观经济策略师。',
        'desc': '中国GDP与大宗商品需求弹性',
        'user': f'基于用电量数据和各品种分析，请分析:\n1.GDP增速与大宗商品需求的弹性关系 2.房地产下行对黑色系的影响量化 3.基建投资对建材的拉动效果 4.制造业PMI与有色/化工的领先滞后关系'
    })
    tasks.append({
        'id': 38, 'phase': 'P4-宏观',
        'system': '你是美联储政策研究专家。',
        'desc': '美联储货币政策对大宗的传导',
        'user': f'请分析：1.美联储降息周期对大宗商品的传导路径（美元/流动性/需求）2.当前美联储政策立场 3.市场预期与现实的偏差 4.对贵金属/有色/能源的差异化影响'
    })
    tasks.append({
        'id': 39, 'phase': 'P4-宏观',
        'system': '你是全球流动性分析师。',
        'desc': '美元流动性与大宗商品定价',
        'user': f'请分析：1.美元指数走势与大宗商品的关系 2.全球M2增速与商品价格的领先滞后关系 3.中美利差与资金流向 4.离岸美元流动性紧张的影响'
    })
    tasks.append({
        'id': 40, 'phase': 'P4-宏观',
        'system': '你是通胀研究专家。',
        'desc': '全球通胀与商品定价',
        'user': f'请分析：1.中国CPI/PPI走势与商品的关系 2.美国CPI与美联储政策 3.大宗商品价格在通胀中的角色 4.通胀预期对各类商品的影响差异 5.滞涨风险'
    })
    tasks.append({
        'id': 41, 'phase': 'P4-宏观',
        'system': '你是全球制造业研究专家。',
        'desc': '全球制造业PMI与商品需求',
        'user': f'请分析：1.中国/美国/欧洲/印度制造业PMI对比 2.全球制造业共振的可能性 3.PMI新订单与商品需求的领先关系 4.哪些国家的制造业复苏最利好商品'
    })
    tasks.append({
        'id': 42, 'phase': 'P4-宏观',
        'system': '你是地缘政治风险分析师。',
        'desc': '地缘政治风险与商品溢价',
        'user': f'请分析：1.中东局势对原油的风险溢价 2.俄乌冲突对能源和粮食的影响 3.中美关系对农产品/有色的影响 4.全球贸易摩擦对供应链的冲击 5.地缘风险量化评估'
    })
    tasks.append({
        'id': 43, 'phase': 'P4-宏观',
        'system': '你是中国经济转型研究专家。',
        'desc': '中国经济结构转型对商品需求的影响',
        'user': f'请分析：1.房地产→制造业的经济转型对品种需求结构的变化 2.新能源对传统能源的替代节奏 3.消费升级对农产品/贵金属的影响 4.双碳目标对各品种的长期影响'
    })
    tasks.append({
        'id': 44, 'phase': 'P4-宏观',
        'system': '你是宏观-商品映射策略师。',
        'desc': '宏观因子→商品映射与配置建议',
        'user': f'请构建宏观到商品的完整映射:\n1.各宏观因子（GDP/PMI/CPI/美联储/美元/地缘）对各品种的影响方向和强度 2.当前宏观环境最利好的品种 3.当前宏观环境最不利的品种 4.宏观拐点预警信号'
    })

    # ===================== P5-策略: 14步 =====================
    tasks.append({
        'id': 45, 'phase': 'P5-策略',
        'system': '你是大宗商品投资总监，管理10亿级商品基金。',
        'desc': '多空方向判断汇总',
        'user': f'基于前面所有分析，请给出各品种的多空判断:\n格式：品种 | 方向(多/空/中性) | 信心(高/中/低) | 核心逻辑(一句话)\n\n要求：必须考虑产业链逻辑一致性，不能出现上下游矛盾的信号'
    })
    # 跨品种套利(5)
    tasks.append({
        'id': 46, 'phase': 'P5-策略',
        'system': '你是套利策略专家。',
        'desc': '能化套利组合',
        'user': f'请设计2个能化板块跨品种套利组合:\n要求：多空方向、入场逻辑、风险点、止损条件、预期收益风险比\n考虑：裂解价差、甲醇-烯烃利润链、PTA利润'
    })
    tasks.append({
        'id': 47, 'phase': 'P5-策略',
        'system': '你是套利策略专家。',
        'desc': '黑色套利组合',
        'user': f'请设计1个黑色系跨品种套利组合:\n要求：多空方向、入场逻辑、风险点、止损条件、预期收益风险比\n考虑：螺矿比、卷螺差、钢厂利润回归'
    })
    tasks.append({
        'id': 48, 'phase': 'P5-策略',
        'system': '你是套利策略专家。',
        'desc': '有色贵金属套利组合',
        'user': f'请设计1个有色/贵金属跨品种套利组合:\n要求：多空方向、入场逻辑、风险点、止损条件、预期收益风险比\n考虑：铜铝比、金银比、新能源需求差异'
    })
    tasks.append({
        'id': 49, 'phase': 'P5-策略',
        'system': '你是跨板块套利专家。',
        'desc': '跨板块宏观对冲组合',
        'user': f'请设计1个跨板块宏观对冲组合:\n要求：多空方向、入场逻辑、宏观假设、风险点、止损条件\n考虑：宏观因子驱动、板块轮动、风险对冲'
    })
    # 期现套利(3)
    tasks.append({
        'id': 50, 'phase': 'P5-策略',
        'system': '你是期现套利专家。',
        'desc': '能化期现套利',
        'user': f'请设计1个能化品种期现套利:\n要求：品种选择、基差条件、入场逻辑、交割流程、预期收益、风险点\n基于当前基差结构和库存成本'
    })
    tasks.append({
        'id': 51, 'phase': 'P5-策略',
        'system': '你是期现套利专家。',
        'desc': '黑色期现套利',
        'user': f'请设计1个黑色品种期现套利:\n要求：品种选择、基差条件、入场逻辑、交割流程、预期收益、风险点\n考虑钢厂交割能力和贸易商角色'
    })
    tasks.append({
        'id': 52, 'phase': 'P5-策略',
        'system': '你是期现套利专家。',
        'desc': '有色期现套利',
        'user': f'请设计1个有色品种期现套利:\n要求：品种选择、基差条件、入场逻辑、交割流程、预期收益、风险点\n考虑仓单变动和进口窗口'
    })
    # 期权策略(1)
    tasks.append({
        'id': 53, 'phase': 'P5-策略',
        'system': '你是期权策略专家。',
        'desc': '期权策略设计',
        'user': f'请设计2个期权策略:\n1.趋势型期权策略（方向性买入期权或价差）2.波动率策略（卖出跨式/宽跨式或蝶式）\n要求：品种选择、策略逻辑、入场条件、最大亏损、预期收益'
    })
    # 趋势跟踪(2)
    tasks.append({
        'id': 54, 'phase': 'P5-策略',
        'system': '你是CTA趋势策略师。',
        'desc': '趋势跟踪策略-做多',
        'user': f'请设计2个趋势跟踪做多策略:\n要求：品种选择理由、入场信号（技术+基本面）、加仓逻辑、止盈目标、止损条件\n基于供需矛盾最紧张的品种'
    })
    tasks.append({
        'id': 55, 'phase': 'P5-策略',
        'system': '你是CTA趋势策略师。',
        'desc': '趋势跟踪策略-做空',
        'user': f'请设计1个趋势跟踪做空策略:\n要求：品种选择理由、入场信号、加仓逻辑、止盈目标、止损条件\n基于供需最过剩的品种'
    })
    # 反转策略(1)
    tasks.append({
        'id': 56, 'phase': 'P5-策略',
        'system': '你是反转策略专家。',
        'desc': '均值回归/反转策略',
        'user': f'请设计2个反转/均值回归策略:\n要求：品种选择理由、超买/超卖条件、入场时机、止损、目标位\n基于价差偏离历史均值最大的品种'
    })
    # 风险预算(1)
    tasks.append({
        'id': 57, 'phase': 'P5-策略',
        'system': '你是风险管理系统专家。',
        'desc': '组合风险预算分配',
        'user': f'假设总资金1亿元，请设计风险预算:\n1.各策略资金分配比例 2.最大回撤控制（总体和各策略）3.VaR和CVaR估算 4.相关性调整后的仓位 5.动态再平衡规则'
    })
    # 压力测试(1)
    tasks.append({
        'id': 58, 'phase': 'P5-策略',
        'system': '你是风险管理系统专家。',
        'desc': '压力测试与黑天鹅应对',
        'user': f'请设计压力测试方案:\n1.原油暴涨50%情景 2.地产崩盘情景 3.全球衰退情景 4.中美脱钩情景 5.各情景下的组合损益 6.黑天鹅应对预案'
    })
    # 实体套保(1)
    tasks.append({
        'id': 59, 'phase': 'P5-策略',
        'system': '你是套保专家。',
        'desc': '实体企业套保方案设计',
        'user': f'请为以下实体企业设计套保方案:\n1.铜矿企业（年产5万吨）2.钢贸商（月均贸易10万吨）3.聚酯工厂（年产能50万吨PTA）\n要求：套保比例、合约选择、入场时机、动态调整规则'
    })
    # 核心矛盾(1)
    tasks.append({
        'id': 60, 'phase': 'P5-策略',
        'system': '你是大宗商品首席策略师。',
        'desc': '核心矛盾提炼与关键变量',
        'user': f'请提炼当前大宗商品市场的核心矛盾:\n1.每个板块的核心矛盾是什么 2.哪些矛盾最可能激化 3.关键跟踪变量（数据指标）4.矛盾缓解/激化的信号 5.矛盾传导链'
    })
    # 年度配置(1)
    tasks.append({
        'id': 61, 'phase': 'P5-策略',
        'system': '你是FOF配置专家。',
        'desc': '年度大宗商品配置建议',
        'user': f'请给出年度大宗商品配置建议:\n1.各板块配置权重 2.看好的品种及理由 3.看空的品种及理由 4.中性观望的品种 5.配置调整触发条件 6.年度收益预期和风险预期'
    })

    # ===================== P6-自我迭代: 7步 =====================
    tasks.append({
        'id': 62, 'phase': 'P6-自我迭代',
        'system': '你是严格的自我批判者。',
        'desc': '自我挑战：找出分析中的弱点',
        'user': f'请对前面所有分析和策略进行自我挑战:\n1.最薄弱的3个分析环节 2.最可能有偏差的判断 3.被忽视的重要信息 4.过度自信的结论 5.需要补充的数据'
    })
    tasks.append({
        'id': 63, 'phase': 'P6-自我迭代',
        'system': '你是假设检验专家。',
        'desc': '假设检验：验证核心逻辑',
        'user': f'请逐一检验前面分析的核心假设:\n1.列出所有关键假设 2.每个假设的验证标准 3.哪些假设已被数据支持 4.哪些假设可能被证伪 5.证伪后的应对'
    })
    tasks.append({
        'id': 64, 'phase': 'P6-自我迭代',
        'system': '你是逻辑一致性审查专家。',
        'desc': '逻辑一致性检查',
        'user': f'请检查所有分析和策略的逻辑一致性:\n1.宏观判断与品种方向是否一致 2.产业链上下游逻辑是否自洽 3.套利组合间是否矛盾 4.风险预算与策略规模是否匹配 5.发现的矛盾点及修正建议'
    })
    tasks.append({
        'id': 65, 'phase': 'P6-自我迭代',
        'system': '你是盲点分析专家。',
        'desc': '补充分析：寻找遗漏维度',
        'user': f'请找出分析中的盲点:\n1.哪些重要维度没有被覆盖 2.哪些品种的联动被忽略 3.哪些风险因子未被纳入 4.哪些时间节点可能被忽视 5.补充分析建议'
    })
    tasks.append({
        'id': 66, 'phase': 'P6-自我迭代',
        'system': '你是策略修正专家。',
        'desc': '策略修正：基于自我审视的改进',
        'user': f'基于前面的自我挑战、假设检验和逻辑一致性检查，请修正策略:\n1.哪些方向需要调整 2.哪些仓位需要增减 3.哪些止损需要收紧 4.哪些新机会被识别 5.修正后的核心策略'
    })
    tasks.append({
        'id': 67, 'phase': 'P6-自我迭代',
        'system': '你是再评估专家。',
        'desc': '再评估：修正后策略质量评分',
        'user': f'请对修正后的所有策略进行再评估:\n1.每个策略的改进程度 2.仍然存在的风险 3.整体策略组合的质量评分(1-10) 4.可执行性评估 5.信息完备度评估'
    })
    tasks.append({
        'id': 68, 'phase': 'P6-自我迭代',
        'system': '你是最终确认专家。',
        'desc': '最终确认：策略定稿',
        'user': f'这是最终确认环节。请:\n1.确认最终保留的策略 2.标注经过迭代后的信心变化 3.最终的核心矛盾总结 4.最重要的3个跟踪指标 5.下一次策略审视的时间节点'
    })

    # ===================== P7-报告: 12步（补充到80） =====================
    tasks.append({
        'id': 69, 'phase': 'P7-报告',
        'system': '你是首席大宗商品策略师。请写一份专业的执行摘要。',
        'desc': '执行摘要',
        'user': f'请用800字写出本次大宗商品研究的核心结论:\n1.宏观判断（3句话）2.最看好的3个品种及理由 3.最不看好的3个品种 4.最重要的3个风险 5.最推荐的2个策略'
    })
    tasks.append({
        'id': 70, 'phase': 'P7-报告',
        'system': '你是宏观经济报告撰写专家。',
        'desc': '宏观篇报告',
        'user': f'请撰写报告宏观篇:\n1.中国经济展望 2.美联储政策解读 3.全球流动性分析 4.通胀与商品 5.地缘风险评估 6.宏观结论与商品映射\n要求：专业、有数据支撑、逻辑清晰'
    })
    tasks.append({
        'id': 71, 'phase': 'P7-报告',
        'system': '你是能源板块报告撰写专家。',
        'desc': '能源篇报告',
        'user': f'请撰写报告能源篇:\n1.原油供需与价格 2.燃料油/LPG 3.能化产业链利润 4.能源板块策略 5.风险提示\n要求：有数据、有逻辑、有结论'
    })
    tasks.append({
        'id': 72, 'phase': 'P7-报告',
        'system': '你是黑色板块报告撰写专家。',
        'desc': '黑色篇报告',
        'user': f'请撰写报告黑色篇:\n1.螺纹/热卷供需 2.铁矿石 3.黑色产业链利润 4.黑色板块策略 5.风险提示\n要求：有数据、有逻辑、有结论'
    })
    tasks.append({
        'id': 73, 'phase': 'P7-报告',
        'system': '你是有色板块报告撰写专家。',
        'desc': '有色篇报告',
        'user': f'请撰写报告有色篇:\n1.铜供需与价格 2.铝供需与价格 3.锌镍 4.新能源对有色影响 5.有色板块策略 6.风险提示'
    })
    tasks.append({
        'id': 74, 'phase': 'P7-报告',
        'system': '你是贵金属报告撰写专家。',
        'desc': '贵金属篇报告',
        'user': f'请撰写报告贵金属篇:\n1.黄金分析与价格 2.白银分析与价格 3.金银比策略 4.央行购金趋势 5.贵金属板块策略 6.风险提示'
    })
    tasks.append({
        'id': 75, 'phase': 'P7-报告',
        'system': '你是化工农产品报告撰写专家。',
        'desc': '化工+农产品篇报告',
        'user': f'请撰写报告化工+农产品篇:\n1.甲醇/PTA/PE/PP 2.豆粕/棕榈油 3.化工产业链利润 4.板块策略 5.风险提示'
    })
    tasks.append({
        'id': 76, 'phase': 'P7-报告',
        'system': '你是策略报告撰写专家。',
        'desc': '策略篇报告',
        'user': f'请撰写报告策略篇:\n1.多空方向汇总 2.套利组合详述 3.期现套利 4.期权策略 5.趋势与反转策略 6.套保方案 7.风险预算'
    })
    tasks.append({
        'id': 77, 'phase': 'P7-报告',
        'system': '你是风险分析报告撰写专家。',
        'desc': '风险情景篇报告',
        'user': f'请撰写报告风险篇:\n1.牛市情景 2.熊市情景 3.震荡情景 4.黑天鹅情景 5.各情景概率与应对 6.压力测试结果'
    })
    # 补充3步到80
    tasks.append({
        'id': 78, 'phase': 'P7-报告',
        'system': '你是报告编辑。',
        'desc': '跨板块关联与综合结论',
        'user': f'请撰写跨板块关联分析:\n1.三大产业链的交汇点 2.能源成本对全品种的影响路径 3.宏观因子如何统一影响各板块 4.综合结论（一段话总结当前市场状态）'
    })
    tasks.append({
        'id': 79, 'phase': 'P7-报告',
        'system': '你是投资建议撰写专家。',
        'desc': '投资者行动指南',
        'user': f'请撰写面向投资者的行动指南:\n1.短期（1个月）行动清单 2.中期（3个月）布局方向 3.年度配置建议 4.不同类型投资者的建议（激进/稳健/保守）5.需要关注的日历事件'
    })
    tasks.append({
        'id': 80, 'phase': 'P7-报告',
        'system': '你是报告总监。',
        'desc': '最终质量审核与报告定稿',
        'user': f'请做最终质量审核:\n1.全报告逻辑一致性检查 2.数据引用准确性 3.策略可执行性 4.风险覆盖完整性 5.语言专业性 6.总体评分(1-10) 7.需要修改的地方 8.定稿确认'
    })

    assert len(tasks) == 80, f"SA任务应为80步，实际{len(tasks)}步"
    return tasks


# ============================================================
# NexusFlow 80步任务定义
# ============================================================
def get_nf_tasks(data_summary: str) -> list:
    """NexusFlow 80步：P1(5) + P2(12) + P3(8) + P4(10) + P5-CDoL(8) + P6(12) + P7(5) + P8(10) + 补齐 = 80"""
    tasks = []
    ds = data_summary
    AG = NEXUSFLOW_AGENTS

    # ===================== P1-数据审查: 5步 =====================
    tasks.append({
        'id': 1, 'phase': 'P1-数据审查', 'agent': 'MacroAnalyst',
        'system': AG['MacroAnalyst']['system'],
        'desc': '【MacroAnalyst】用电量宏观经济解读',
        'user': f'作为NexusFlow宏观分析师，请分析用电量数据:\n{ds[:1500]}\n\n重点：1.经济活跃度信号 2.对大宗商品需求的宏观指引 3.领先指标含义 4.季节性特征 5.对后续分析的宏观框架建议'
    })
    tasks.append({
        'id': 2, 'phase': 'P1-数据审查', 'agent': 'DataEngineer',
        'system': AG['DataEngineer']['system'],
        'desc': '【DataEngineer】数据质量审查',
        'user': f'数据摘要:\n{ds[:4000]}\n\n作为数据工程师，请审查：1.数据完整性（覆盖率、缺失项）2.数据质量（异常值、一致性）3.数据时效性 4.对分析结论可靠性的影响 5.建议补充的数据源'
    })
    tasks.append({
        'id': 3, 'phase': 'P1-数据审查', 'agent': 'Coordinator',
        'system': AG['Coordinator']['system'],
        'desc': '【Coordinator】任务分配与分析规划',
        'user': f'数据摘要:\n{ds[:2000]}\nMacroAnalyst已给出宏观解读，DataEngineer已给出数据质量报告。\n\n作为协调者，请：1.评估数据覆盖情况 2.识别关键分析维度 3.将分析任务分配给各专业Agent 4.制定分析优先级和时间线'
    })
    tasks.append({
        'id': 4, 'phase': 'P1-数据审查', 'agent': 'QuantStrategist',
        'system': AG['QuantStrategist']['system'],
        'desc': '【QuantStrategist】数据统计特征分析',
        'user': f'基差数据:\n{ds[1500:3500]}\n合约数据:\n{ds[3500:5500]}\n\n作为量化策略师，请分析：1.各品种基差的统计分布 2.期限结构特征 3.波动率特征 4.极端值识别 5.为后续套利分析提供统计基础'
    })
    tasks.append({
        'id': 5, 'phase': 'P1-数据审查', 'agent': 'RiskManager',
        'system': AG['RiskManager']['system'],
        'desc': '【RiskManager】数据风险初评',
        'user': f'数据摘要:\n{ds[:3000]}\n\n作为风险管理师，请从数据角度评估：1.数据偏差风险 2.缺失数据对结论的影响 3.需要特别注意的数据陷阱 4.数据时效性风险'
    })

    # ===================== P2-专业分析: 12步 =====================
    # EnergyAnalyst 原油(2)
    tasks.append({
        'id': 6, 'phase': 'P2-专业分析', 'agent': 'EnergyAnalyst',
        'system': AG['EnergyAnalyst']['system'],
        'desc': '【EnergyAnalyst】原油供需深度分析',
        'user': f'用电(工业需求):\n{ds[:600]}\n基差:\n{ds[1500:2200]}\n\n请深度分析原油：1.OPEC+产量政策 2.中国进口需求 3.库存周期 4.地缘溢价 5.价格判断与关键位'
    })
    tasks.append({
        'id': 7, 'phase': 'P2-专业分析', 'agent': 'EnergyAnalyst',
        'system': AG['EnergyAnalyst']['system'],
        'desc': '【EnergyAnalyst】燃料油+LPG分析',
        'user': f'能源基差:\n{ds[1500:2000]}\n合约:\n{ds[3500:4200]}\n\n请分析：1.燃料油（航运+发电需求）2.LPG（化工+民用需求）3.与原油联动 4.价差策略'
    })
    # MetalsAnalyst 黑色(2)+有色(2)
    tasks.append({
        'id': 8, 'phase': 'P2-专业分析', 'agent': 'MetalsAnalyst',
        'system': AG['MetalsAnalyst']['system'],
        'desc': '【MetalsAnalyst】螺纹钢深度分析',
        'user': f'用电(钢铁开工):\n{ds[:600]}\n黑色基差:\n{ds[1500:2000]}\n\n请深度分析：1.钢厂利润与产能利用率 2.下游需求（地产+基建+制造业）3.库存去化 4.价格判断'
    })
    tasks.append({
        'id': 9, 'phase': 'P2-专业分析', 'agent': 'MetalsAnalyst',
        'system': AG['MetalsAnalyst']['system'],
        'desc': '【MetalsAnalyst】铁矿+热卷分析',
        'user': f'黑色基差:\n{ds[1500:1800]}\n\n请分析：1.铁矿供应（澳洲/巴西发运）2.港口库存 3.钢厂补库节奏 4.铁矿估值 5.热卷需求与卷螺差'
    })
    tasks.append({
        'id': 10, 'phase': 'P2-专业分析', 'agent': 'MetalsAnalyst',
        'system': AG['MetalsAnalyst']['system'],
        'desc': '【MetalsAnalyst】铜深度分析',
        'user': f'用电(电力=铜需求):\n{ds[:500]}\n有色基差:\n{ds[1500:1900]}\n仓单:\n{ds[5500:6500]}\n\n请深度分析：1.全球铜矿供应 2.中国冶炼利润 3.下游需求（电网/新能源/空调）4.库存与基差 5.价格判断'
    })
    tasks.append({
        'id': 11, 'phase': 'P2-专业分析', 'agent': 'MetalsAnalyst',
        'system': AG['MetalsAnalyst']['system'],
        'desc': '【MetalsAnalyst】铝+锌镍分析',
        'user': f'有色基差:\n{ds[1600:1900]}\n用电(电解铝成本):\n{ds[:400]}\n\n请分析：1.铝（产能天花板+电力成本+光伏/汽车需求）2.锌（矿供应+冶炼+镀锌）3.镍（印尼+不锈钢+三元电池）4.有色整体判断'
    })
    # PreciousAnalyst(2)
    tasks.append({
        'id': 12, 'phase': 'P2-专业分析', 'agent': 'PreciousAnalyst',
        'system': AG['PreciousAnalyst']['system'],
        'desc': '【PreciousAnalyst】黄金深度分析',
        'user': f'宏观数据:\n{ds[:600]}\n贵金属基差:\n{ds[1500:1700]}\n\n请深度分析：1.美联储政策路径 2.央行购金趋势 3.地缘风险溢价 4.实际利率与金价 5.CFTC持仓 6.配置建议'
    })
    tasks.append({
        'id': 13, 'phase': 'P2-专业分析', 'agent': 'PreciousAnalyst',
        'system': AG['PreciousAnalyst']['system'],
        'desc': '【PreciousAnalyst】白银+金银比分析',
        'user': f'贵金属基差:\n{ds[1500:1700]}\n\n请分析：1.白银工业属性（光伏用银）2.货币属性 3.金银比历史与策略 4.白银供需平衡 5.价格弹性'
    })
    # ChemicalAnalyst(2)
    tasks.append({
        'id': 14, 'phase': 'P2-专业分析', 'agent': 'ChemicalAnalyst',
        'system': AG['ChemicalAnalyst']['system'],
        'desc': '【ChemicalAnalyst】甲醇+PTA分析',
        'user': f'化工基差:\n{ds[1800:2400]}\n合约:\n{ds[4000:4800]}\n\n请分析：1.甲醇（煤化工vs气化工成本+MTO需求+港口库存）2.PTA（PX-PTA-聚酯利润+开工率）3.两品种联动'
    })
    tasks.append({
        'id': 15, 'phase': 'P2-专业分析', 'agent': 'ChemicalAnalyst',
        'system': AG['ChemicalAnalyst']['system'],
        'desc': '【ChemicalAnalyst】PE+PP分析',
        'user': f'化工基差:\n{ds[1800:2200]}\n\n请分析：1.PE（油制vs煤制成本+产能+农膜/包装需求）2.PP（PDH利润+纤维/注塑需求）3.PP-PE价差 4.化工整体判断'
    })
    # AgroAnalyst(1)
    tasks.append({
        'id': 16, 'phase': 'P2-专业分析', 'agent': 'AgroAnalyst',
        'system': AG['AgroAnalyst']['system'],
        'desc': '【AgroAnalyst】豆粕+棕榈油分析',
        'user': f'农产品基差:\n{ds[2000:2600]}\n\n请分析：1.豆粕（美豆+压榨利润+生猪需求+库存）2.棕榈油（东南亚产量+进口+生柴政策）3.油脂油料联动'
    })
    # QuantStrategist(1)
    tasks.append({
        'id': 17, 'phase': 'P2-专业分析', 'agent': 'QuantStrategist',
        'system': AG['QuantStrategist']['system'],
        'desc': '【QuantStrategist】基差信号与价差扫描',
        'user': f'全品种基差:\n{ds[1500:3000]}\n\n作为量化策略师，请扫描基差信号：1.基差偏离历史均值最大的品种 2.期限结构异常信号 3.跨品种价差机会 4.期现套利机会初筛'
    })

    # ===================== P3-产业链: 8步 =====================
    tasks.append({
        'id': 18, 'phase': 'P3-产业链', 'agent': 'Coordinator',
        'system': AG['Coordinator']['system'],
        'desc': '【Coordinator】主持能源产业链讨论',
        'user': f'作为协调者，请主持能源产业链讨论:\n原油→石脑油→PX→PTA→聚酯\n原油→甲醇→烯烃→终端\n\n请整合EnergyAnalyst和ChemicalAnalyst的分析，梳理：1.各环节利润分配 2.最脆弱环节 3.利润回归机会'
    })
    tasks.append({
        'id': 19, 'phase': 'P3-产业链', 'agent': 'EnergyAnalyst',
        'system': AG['EnergyAnalyst']['system'],
        'desc': '【EnergyAnalyst】能源链利润分析',
        'user': f'请从能源角度分析产业链利润:\n1.原油→成品油裂解价差 2.原油→燃料油/LPG 3.能源成本对下游化工的传导 4.能源链利润分配的可持续性'
    })
    tasks.append({
        'id': 20, 'phase': 'P3-产业链', 'agent': 'Coordinator',
        'system': AG['Coordinator']['system'],
        'desc': '【Coordinator】主持黑色产业链讨论',
        'user': f'请主持黑色产业链讨论:\n铁矿+焦煤→生铁→粗钢→螺纹/热卷→终端\n\n整合MetalsAnalyst分析：1.钢厂利润位置 2.铁矿vs焦炭博弈 3.终端需求节奏 4.产业链利润分配状态'
    })
    tasks.append({
        'id': 21, 'phase': 'P3-产业链', 'agent': 'MetalsAnalyst',
        'system': AG['MetalsAnalyst']['system'],
        'desc': '【MetalsAnalyst】黑色链+有色新能源链分析',
        'user': f'请分析两条产业链:\n\n黑色链：铁矿+焦煤→粗钢→螺纹/热卷→终端\n有色链：铜矿→精铜→电网/新能源；铝→汽车/光伏\n\n1.各产业链利润分配 2.新能源对有色需求增量 3.各品种新能源含量对比'
    })
    tasks.append({
        'id': 22, 'phase': 'P3-产业链', 'agent': 'ChemicalAnalyst',
        'system': AG['ChemicalAnalyst']['system'],
        'desc': '【ChemicalAnalyst】化工下游产业链分析',
        'user': f'请分析化工下游产业链:\n1.PTA→聚酯→纺服/包装的需求传导 2.甲醇→MTO→烯烃→终端 3.PE/PP→农膜/包装/汽车 4.化工品与终端消费的利润传导'
    })
    tasks.append({
        'id': 23, 'phase': 'P3-产业链', 'agent': 'AgroAnalyst',
        'system': AG['AgroAnalyst']['system'],
        'desc': '【AgroAnalyst】农产品产业链分析',
        'user': f'请分析农产品产业链:\n1.大豆→豆粕→饲料→养殖→终端消费 2.棕榈油→食品工业/生物柴油 3.油脂油料间的替代与联动 4.产业链利润最丰厚的环节'
    })
    tasks.append({
        'id': 24, 'phase': 'P3-产业链', 'agent': 'Coordinator',
        'system': AG['Coordinator']['system'],
        'desc': '【Coordinator】跨产业链综合利润图',
        'user': f'请综合所有Agent的产业链分析:\n1.三大产业链（能源/黑色/有色）利润周期对比 2.哪个产业链利润最丰厚 3.跨产业链联动（能源成本→全链） 4.投资机会排序'
    })
    tasks.append({
        'id': 25, 'phase': 'P3-产业链', 'agent': 'RiskManager',
        'system': AG['RiskManager']['system'],
        'desc': '【RiskManager】产业链风险评估',
        'user': f'请评估产业链风险:\n1.各产业链最脆弱的环节 2.断链风险点 3.地缘政治对产业链的冲击 4.产业链利润反转的触发条件'
    })

    # ===================== P4-宏观: 10步 =====================
    # MacroAnalyst×6
    tasks.append({
        'id': 26, 'phase': 'P4-宏观', 'agent': 'MacroAnalyst',
        'system': AG['MacroAnalyst']['system'],
        'desc': '【MacroAnalyst】中国GDP与商品需求',
        'user': f'请分析：1.GDP增速与大宗商品需求弹性 2.地产下行对黑色系的影响量化 3.基建投资拉动效果 4.PMI与有色/化工的领先滞后关系'
    })
    tasks.append({
        'id': 27, 'phase': 'P4-宏观', 'agent': 'MacroAnalyst',
        'system': AG['MacroAnalyst']['system'],
        'desc': '【MacroAnalyst】美联储政策传导',
        'user': f'请分析：1.美联储降息周期→美元→商品传导链 2.当前政策立场与市场预期差 3.对贵金属/有色/能源的差异化影响'
    })
    tasks.append({
        'id': 28, 'phase': 'P4-宏观', 'agent': 'MacroAnalyst',
        'system': AG['MacroAnalyst']['system'],
        'desc': '【MacroAnalyst】美元流动性分析',
        'user': f'请分析：1.美元指数走势与商品关系 2.全球M2增速与商品价格 3.中美利差与资金流向 4.离岸美元流动性影响'
    })
    tasks.append({
        'id': 29, 'phase': 'P4-宏观', 'agent': 'MacroAnalyst',
        'system': AG['MacroAnalyst']['system'],
        'desc': '【MacroAnalyst】全球通胀分析',
        'user': f'请分析：1.中国CPI/PPI与商品关系 2.美国CPI与美联储政策 3.大宗商品在通胀中的角色 4.滞涨风险评估'
    })
    tasks.append({
        'id': 30, 'phase': 'P4-宏观', 'agent': 'MacroAnalyst',
        'system': AG['MacroAnalyst']['system'],
        'desc': '【MacroAnalyst】全球制造业PMI',
        'user': f'请分析：1.中美欧印制造业PMI对比 2.全球制造业共振可能性 3.PMI新订单与商品需求 4.哪些国家复苏最利好商品'
    })
    tasks.append({
        'id': 31, 'phase': 'P4-宏观', 'agent': 'MacroAnalyst',
        'system': AG['MacroAnalyst']['system'],
        'desc': '【MacroAnalyst】地缘政治风险',
        'user': f'请分析：1.中东→原油溢价 2.俄乌→能源/粮食 3.中美→农产品/有色 4.贸易摩擦→供应链 5.地缘风险量化'
    })
    # QuantStrategist×2
    tasks.append({
        'id': 32, 'phase': 'P4-宏观', 'agent': 'QuantStrategist',
        'system': AG['QuantStrategist']['system'],
        'desc': '【QuantStrategist】宏观-商品相关性分析',
        'user': f'请构建宏观因子与商品的相关性:\n1.各宏观因子对各品种的影响方向和强度 2.领先滞后关系量化 3.宏观因子敏感度排序 4.最佳配对交易'
    })
    tasks.append({
        'id': 33, 'phase': 'P4-宏观', 'agent': 'QuantStrategist',
        'system': AG['QuantStrategist']['system'],
        'desc': '【QuantStrategist】品种间相关性与配对',
        'user': f'基于18品种分析，请：\n1.品种相关性矩阵 2.最佳配对交易机会（多A空B）3.产业链上下游领先滞后关系 4.当前最佳对冲组合'
    })
    # Coordinator×1
    tasks.append({
        'id': 34, 'phase': 'P4-宏观', 'agent': 'Coordinator',
        'system': AG['Coordinator']['system'],
        'desc': '【Coordinator】宏观共识形成',
        'user': f'请综合MacroAnalyst的6个维度分析和QuantStrategist的相关性分析:\n1.形成宏观共识判断 2.识别分析师间的分歧 3.宏观因子重要性排序 4.对商品配置的宏观指引'
    })
    # RiskManager×1
    tasks.append({
        'id': 35, 'phase': 'P4-宏观', 'agent': 'RiskManager',
        'system': AG['RiskManager']['system'],
        'desc': '【RiskManager】宏观风险评估',
        'user': f'请从风险角度评估宏观判断:\n1.宏观判断中最大的不确定性 2.可能颠覆当前共识的情景 3.宏观风险的尾部概率 4.需要设置的宏观对冲'
    })

    # ===================== P5-CDoL讨论: 8步 =====================
    tasks.append({
        'id': 36, 'phase': 'P5-CDoL', 'agent': 'Coordinator',
        'system': AG['Coordinator']['system'],
        'desc': '【CDoL-R1】各Agent亮出核心观点',
        'user': f'这是NexusFlow CDoL(认知分工信息不对称)协议第一轮。\n\n各专业Agent已完成分析。请各Agent亮出核心观点:\n1.EnergyAnalyst的能源判断 2.MetalsAnalyst的金属判断 3.PreciousAnalyst的贵金属判断 4.ChemicalAnalyst的化工判断 5.AgroAnalyst的农产品判断\n\n作为Coordinator，请总结共识与分歧。'
    })
    tasks.append({
        'id': 37, 'phase': 'P5-CDoL', 'agent': 'Coordinator',
        'system': AG['Coordinator']['system'],
        'desc': '【CDoL-R2】跨板块质疑',
        'user': f'CDoL第二轮——跨板块质疑。\n\n请主持跨板块质疑：\n1.MetalsAnalyst对EnergyAnalyst判断的质疑 2.ChemicalAnalyst对MetalsAnalyst判断的质疑 3.QuantStrategist对各板块数据的质疑 4.RiskManager对乐观判断的挑战'
    })
    tasks.append({
        'id': 38, 'phase': 'P5-CDoL', 'agent': 'QuantStrategist',
        'system': AG['QuantStrategist']['system'],
        'desc': '【CDoL-R3】数据检验',
        'user': f'CDoL第三轮——数据检验。\n\n作为量化策略师，请用数据检验各Agent的定性判断:\n1.哪些判断有数据支持 2.哪些判断缺乏数据支撑 3.数据与判断的矛盾点 4.需要额外验证的假设'
    })
    tasks.append({
        'id': 39, 'phase': 'P5-CDoL', 'agent': 'RiskManager',
        'system': AG['RiskManager']['system'],
        'desc': '【CDoL-R4】挑战最强假设',
        'user': f'CDoL第四轮——挑战最强假设。\n\n请找出讨论中最强的3个假设并挑战:\n1.每个假设的逻辑漏洞 2.什么条件下会失败 3.失败的后果 4.备选方案'
    })
    tasks.append({
        'id': 40, 'phase': 'P5-CDoL', 'agent': 'Coordinator',
        'system': AG['Coordinator']['system'],
        'desc': '【CDoL-R5】补充盲点',
        'user': f'CDoL第五轮——补充盲点。\n\n请补充讨论中的盲点:\n1.哪些重要维度被忽视 2.哪些品种的联动被忽略 3.哪些风险未被纳入 4.需要补充的分析'
    })
    tasks.append({
        'id': 41, 'phase': 'P5-CDoL', 'agent': 'Coordinator',
        'system': AG['Coordinator']['system'],
        'desc': '【CDoL-R6】修正方向',
        'user': f'CDoL第六轮——修正方向。\n\n基于前5轮讨论，请修正判断:\n1.哪些方向需要调整 2.哪些信心需要降低 3.哪些新机会被识别 4.哪些风险需要加码对冲'
    })
    tasks.append({
        'id': 42, 'phase': 'P5-CDoL', 'agent': 'Coordinator',
        'system': AG['Coordinator']['system'],
        'desc': '【CDoL-R7】策略融合',
        'user': f'CDoL第七轮——策略融合。\n\n请将讨论成果融入策略:\n1.综合各Agent的观点形成统一策略框架 2.解决分歧 3.标注信心等级 4.确定核心交易主题'
    })
    tasks.append({
        'id': 43, 'phase': 'P5-CDoL', 'agent': 'Coordinator',
        'system': AG['Coordinator']['system'],
        'desc': '【CDoL-R8】共识收敛',
        'user': f'CDoL第八轮——共识收敛。\n\n最终收敛:\n1.确认最终共识（所有Agent同意）2.保留的分歧（部分Agent保留意见）3.最终推荐的投资组合 4.关键假设与验证条件'
    })

    # ===================== P6-策略: 12步 =====================
    # QuantStrategist×3
    tasks.append({
        'id': 44, 'phase': 'P6-策略', 'agent': 'QuantStrategist',
        'system': AG['QuantStrategist']['system'],
        'desc': '【QuantStrategist】多空方向判断',
        'user': f'基于CDoL讨论成果，请给出各品种多空判断:\n格式：品种|方向|信心|核心逻辑\n要求：体现讨论共识，标注分歧'
    })
    tasks.append({
        'id': 45, 'phase': 'P6-策略', 'agent': 'QuantStrategist',
        'system': AG['QuantStrategist']['system'],
        'desc': '【QuantStrategist】套利组合设计',
        'user': f'请设计5个套利组合:\n1.能化套利×2 2.黑色套利×1 3.有色贵金属套利×1 4.跨板块宏观对冲×1\n每个：多空方向+入场逻辑+止损+预期盈亏比'
    })
    tasks.append({
        'id': 46, 'phase': 'P6-策略', 'agent': 'QuantStrategist',
        'system': AG['QuantStrategist']['system'],
        'desc': '【QuantStrategist】趋势+反转+期权策略',
        'user': f'请设计：\n1.2个趋势跟踪策略（做多/做空）2.1个反转策略 3.2个期权策略（趋势型+波动率型）\n每个：品种+入场信号+止损+目标'
    })
    # RiskManager×3
    tasks.append({
        'id': 47, 'phase': 'P6-策略', 'agent': 'RiskManager',
        'system': AG['RiskManager']['system'],
        'desc': '【RiskManager】压力测试',
        'user': f'请对策略组合压力测试:\n1.原油+50%/-50%情景 2.地产崩盘 3.全球衰退 4.中美脱钩 5.各情景组合损益 6.最大回撤估算'
    })
    tasks.append({
        'id': 48, 'phase': 'P6-策略', 'agent': 'RiskManager',
        'system': AG['RiskManager']['system'],
        'desc': '【RiskManager】仓位管理',
        'user': f'假设总资金1亿元，请设计:\n1.各策略资金分配 2.VaR/CVaR估算 3.仓位管理规则 4.动态再平衡 5.止损纪律'
    })
    tasks.append({
        'id': 49, 'phase': 'P6-策略', 'agent': 'RiskManager',
        'system': AG['RiskManager']['system'],
        'desc': '【RiskManager】黑天鹅应对',
        'user': f'请设计黑天鹅应对方案:\n1.极端情景识别 2.应急预案 3.对冲工具 4.流动性风险管理 5.通信与决策流程'
    })
    # Coordinator×2
    tasks.append({
        'id': 50, 'phase': 'P6-策略', 'agent': 'Coordinator',
        'system': AG['Coordinator']['system'],
        'desc': '【Coordinator】策略整合',
        'user': f'请整合QuantStrategist和RiskManager的策略:\n1.形成统一策略方案 2.解决策略间冲突 3.确定优先级 4.策略间的相关性管理'
    })
    tasks.append({
        'id': 51, 'phase': 'P6-策略', 'agent': 'Coordinator',
        'system': AG['Coordinator']['system'],
        'desc': '【Coordinator】核心矛盾与配置建议',
        'user': f'请提炼核心矛盾并给出配置:\n1.各板块核心矛盾 2.关键跟踪变量 3.年度配置权重 4.配置调整触发条件'
    })
    # RiskManager套保×2
    tasks.append({
        'id': 52, 'phase': 'P6-策略', 'agent': 'RiskManager',
        'system': AG['RiskManager']['system'],
        'desc': '【RiskManager】实体套保方案',
        'user': f'请为实体企业设计套保:\n1.铜矿企业（年产5万吨）2.钢贸商（月均10万吨）3.聚酯工厂（年产能50万吨PTA）\n要求：套保比例、合约选择、入场时机、动态调整'
    })
    tasks.append({
        'id': 53, 'phase': 'P6-策略', 'agent': 'RiskManager',
        'system': AG['RiskManager']['system'],
        'desc': '【RiskManager】期现套利方案',
        'user': f'请设计3个期现套利方案:\n1.能化品种期现套利 2.黑色品种期现套利 3.有色品种期现套利\n每个：品种+基差条件+入场逻辑+交割流程+预期收益+风险'
    })
    # QuantStrategist期权×2
    tasks.append({
        'id': 54, 'phase': 'P6-策略', 'agent': 'QuantStrategist',
        'system': AG['QuantStrategist']['system'],
        'desc': '【QuantStrategist】期权组合策略',
        'user': f'请设计期权组合:\n1.方向性期权策略（bull/bear spread）2.波动率策略（straddle/strangle/butterfly）3.期权与期货组合策略\n每个：品种+策略+入场+最大亏损+预期收益'
    })
    tasks.append({
        'id': 55, 'phase': 'P6-策略', 'agent': 'QuantStrategist',
        'system': AG['QuantStrategist']['system'],
        'desc': '【QuantStrategist】量化信号与执行清单',
        'user': f'请生成量化执行清单:\n1.各策略的精确入场信号 2.仓位计算公式 3.止损止盈规则 4.执行日历（关注重要数据发布）5.监控指标'
    })

    # ===================== P7-策略审核: 5步 =====================
    tasks.append({
        'id': 56, 'phase': 'P7-策略审核', 'agent': 'Coordinator',
        'system': AG['Coordinator']['system'],
        'desc': '【Coordinator】策略质量审核',
        'user': f'请对所有策略做质量审核:\n1.逻辑一致性（各板块判断是否矛盾）2.数据引用准确性 3.策略可执行性 4.风险覆盖完整性 5.需要修改的地方'
    })
    tasks.append({
        'id': 57, 'phase': 'P7-策略审核', 'agent': 'RiskManager',
        'system': AG['RiskManager']['system'],
        'desc': '【RiskManager】风险视角反馈',
        'user': f'请从风险角度反馈:\n1.策略中仍存在的风险盲点 2.压力测试是否充分 3.仓位建议是否合理 4.需要增加的风控措施'
    })
    tasks.append({
        'id': 58, 'phase': 'P7-策略审核', 'agent': 'QuantStrategist',
        'system': AG['QuantStrategist']['system'],
        'desc': '【QuantStrategist】量化视角反馈',
        'user': f'请从量化角度反馈:\n1.策略的收益风险比评估 2.相关性是否被低估 3.入场信号是否可量化 4.需要补充的量化验证'
    })
    tasks.append({
        'id': 59, 'phase': 'P7-策略审核', 'agent': 'Coordinator',
        'system': AG['Coordinator']['system'],
        'desc': '【Coordinator】策略修正定稿',
        'user': f'基于RiskManager和QuantStrategist反馈，请修正策略:\n1.最终修正项 2.信心调整 3.新增风控措施 4.策略定稿确认'
    })
    tasks.append({
        'id': 60, 'phase': 'P7-策略审核', 'agent': 'Coordinator',
        'system': AG['Coordinator']['system'],
        'desc': '【Coordinator】最终确认',
        'user': f'最终确认:\n1.确认保留的策略 2.信心等级（高/中/低）3.核心跟踪指标 4.下一次审视时间节点 5.策略版本号标记'
    })

    # ===================== P8-报告: 20步（补齐到80） =====================
    # ReportWriter×7（各板块报告）
    tasks.append({
        'id': 61, 'phase': 'P8-报告', 'agent': 'Coordinator',
        'system': AG['Coordinator']['system'],
        'desc': '【Coordinator】执行摘要',
        'user': f'请撰写执行摘要（800字）:\n1.宏观判断（3句话）2.最看好3品种 3.最不看好3品种 4.最重要的3个风险 5.最推荐2个策略'
    })
    tasks.append({
        'id': 62, 'phase': 'P8-报告', 'agent': 'Coordinator',
        'system': AG['Coordinator']['system'],
        'desc': '【Coordinator】宏观篇报告',
        'user': f'请撰写宏观篇:\n1.中国经济展望 2.美联储政策 3.全球流动性 4.通胀 5.地缘风险 6.宏观→商品映射'
    })
    tasks.append({
        'id': 63, 'phase': 'P8-报告', 'agent': 'EnergyAnalyst',
        'system': AG['EnergyAnalyst']['system'],
        'desc': '【EnergyAnalyst】能源篇报告',
        'user': f'请撰写能源篇:\n1.原油供需与价格 2.燃料油/LPG 3.能化利润链 4.能源策略 5.风险提示'
    })
    tasks.append({
        'id': 64, 'phase': 'P8-报告', 'agent': 'MetalsAnalyst',
        'system': AG['MetalsAnalyst']['system'],
        'desc': '【MetalsAnalyst】黑色篇报告',
        'user': f'请撰写黑色篇:\n1.螺纹/热卷 2.铁矿石 3.黑色产业链利润 4.策略 5.风险提示'
    })
    tasks.append({
        'id': 65, 'phase': 'P8-报告', 'agent': 'MetalsAnalyst',
        'system': AG['MetalsAnalyst']['system'],
        'desc': '【MetalsAnalyst】有色篇报告',
        'user': f'请撰写有色篇:\n1.铜 2.铝 3.锌镍 4.新能源影响 5.策略 6.风险提示'
    })
    tasks.append({
        'id': 66, 'phase': 'P8-报告', 'agent': 'PreciousAnalyst',
        'system': AG['PreciousAnalyst']['system'],
        'desc': '【PreciousAnalyst】贵金属篇报告',
        'user': f'请撰写贵金属篇:\n1.黄金 2.白银 3.金银比 4.央行购金 5.策略 6.风险提示'
    })
    tasks.append({
        'id': 67, 'phase': 'P8-报告', 'agent': 'ChemicalAnalyst',
        'system': AG['ChemicalAnalyst']['system'],
        'desc': '【ChemicalAnalyst】化工+农产品篇报告',
        'user': f'请撰写化工+农产品篇:\n1.甲醇/PTA/PE/PP 2.豆粕/棕榈油 3.化工链利润 4.策略 5.风险提示'
    })
    # Coordinator补充报告步骤
    tasks.append({
        'id': 68, 'phase': 'P8-报告', 'agent': 'Coordinator',
        'system': AG['Coordinator']['system'],
        'desc': '【Coordinator】策略篇报告',
        'user': f'请撰写策略篇:\n1.多空汇总 2.套利组合 3.期现套利 4.期权策略 5.趋势与反转 6.套保方案 7.风险预算'
    })
    tasks.append({
        'id': 69, 'phase': 'P8-报告', 'agent': 'RiskManager',
        'system': AG['RiskManager']['system'],
        'desc': '【RiskManager】风险情景篇报告',
        'user': f'请撰写风险篇:\n1.牛市情景 2.熊市情景 3.震荡情景 4.黑天鹅 5.概率估计 6.压力测试结果'
    })
    tasks.append({
        'id': 70, 'phase': 'P8-报告', 'agent': 'Coordinator',
        'system': AG['Coordinator']['system'],
        'desc': '【Coordinator】跨板块关联分析',
        'user': f'请撰写跨板块关联:\n1.三大产业链交汇点 2.能源成本对全品种路径 3.宏观因子统一影响 4.综合结论'
    })
    tasks.append({
        'id': 71, 'phase': 'P8-报告', 'agent': 'Coordinator',
        'system': AG['Coordinator']['system'],
        'desc': '【Coordinator】投资者行动指南',
        'user': f'请撰写行动指南:\n1.短期（1个月）清单 2.中期（3个月）布局 3.年度配置 4.不同类型投资者建议 5.关注日历事件'
    })
    tasks.append({
        'id': 72, 'phase': 'P8-报告', 'agent': 'QuantStrategist',
        'system': AG['QuantStrategist']['system'],
        'desc': '【QuantStrategist】量化附录',
        'user': f'请撰写量化附录:\n1.品种相关性矩阵 2.基差统计表 3.各策略盈亏比 4.入场信号汇总表 5.监控指标清单'
    })
    tasks.append({
        'id': 73, 'phase': 'P8-报告', 'agent': 'MacroAnalyst',
        'system': AG['MacroAnalyst']['system'],
        'desc': '【MacroAnalyst】宏观附录',
        'user': f'请撰写宏观附录:\n1.关键宏观指标时间表 2.各指标对商品的传导路径图 3.宏观情景概率分布 4.宏观拐点信号清单'
    })
    tasks.append({
        'id': 74, 'phase': 'P8-报告', 'agent': 'DataEngineer',
        'system': AG['DataEngineer']['system'],
        'desc': '【DataEngineer】数据附录',
        'user': f'请撰写数据附录:\n1.数据来源清单 2.数据质量评级 3.缺失数据说明 4.数据更新频率 5.后续数据采集建议'
    })
    # 最终审核步骤
    tasks.append({
        'id': 75, 'phase': 'P8-报告', 'agent': 'Coordinator',
        'system': AG['Coordinator']['system'],
        'desc': '【Coordinator】全报告逻辑一致性检查',
        'user': f'请对全报告做逻辑一致性检查:\n1.宏观→品种方向一致性 2.产业链上下游逻辑自洽 3.策略间无矛盾 4.风险覆盖完整 5.发现的矛盾点'
    })
    tasks.append({
        'id': 76, 'phase': 'P8-报告', 'agent': 'RiskManager',
        'system': AG['RiskManager']['system'],
        'desc': '【RiskManager】风险提示终审',
        'user': f'请做风险提示终审:\n1.是否有遗漏的风险 2.风险描述是否充分 3.应对措施是否到位 4.需要增加的风险警示'
    })
    tasks.append({
        'id': 77, 'phase': 'P8-报告', 'agent': 'Coordinator',
        'system': AG['Coordinator']['system'],
        'desc': '【Coordinator】报告修正',
        'user': f'基于审核反馈，请修正报告:\n1.修正项列表 2.修正内容 3.质量提升评估 4.最终版本确认'
    })
    tasks.append({
        'id': 78, 'phase': 'P8-报告', 'agent': 'Coordinator',
        'system': AG['Coordinator']['system'],
        'desc': '【Coordinator】总体质量评分',
        'user': f'请给报告最终评分:\n1.分析深度(1-10) 2.数据支撑(1-10) 3.逻辑一致性(1-10) 4.策略可执行性(1-10) 5.风险覆盖(1-10) 6.综合评分(1-10)'
    })
    tasks.append({
        'id': 79, 'phase': 'P8-报告', 'agent': 'Coordinator',
        'system': AG['Coordinator']['system'],
        'desc': '【Coordinator】最终定稿声明',
        'user': f'请写最终定稿声明:\n1.确认报告定稿 2.核心结论总结（5句话）3.免责声明 4.下次审视时间 5.报告版本信息'
    })
    tasks.append({
        'id': 80, 'phase': 'P8-报告', 'agent': 'Coordinator',
        'system': AG['Coordinator']['system'],
        'desc': '【Coordinator】NexusFlow系统总结',
        'user': f'请总结NexusFlow多Agent协作效果:\n1.各Agent贡献度评估 2.CDoL讨论的价值（哪些判断因讨论而改善）3.多Agent vs 单Agent的定性比较 4.改进建议'
    })

    assert len(tasks) == 80, f"NF任务应为80步，实际{len(tasks)}步"
    return tasks


# ============================================================
# 执行引擎
# ============================================================
class BenchmarkExecutor:
    def __init__(self, mode: str):
        self.mode = mode  # 'single_agent' or 'nexusflow'
        self.results = []
        self.total_tokens = 0
        self.total_time = 0
        self.total_quality = 0
        self.all_outputs = {}  # step_id -> output text

    def execute_step(self, task: dict) -> dict:
        """执行单步分析（含真实API调用 + 独立质量评估）"""
        step_id = task['id']
        phase = task['phase']

        # 构建上下文（同Phase + 前Phase输出）
        context = self._build_context(task)
        user_prompt = task['user']
        if context:
            user_prompt = f"前序分析上下文:\n{context}\n\n{user_prompt}"

        # ① 真实API调用（分析）
        result = call_llm(task['system'], user_prompt, max_tokens=2048)
        output = result['content']
        self.all_outputs[step_id] = output

        # ② 独立LLM调用（质量评估）
        quality_result = evaluate_quality(task['desc'], output, context)

        step_result = {
            'step_id': step_id,
            'phase': phase,
            'agent': task.get('agent', 'SingleAgent'),
            'desc': task['desc'],
            'output': output,
            'output_length': len(output),
            'prompt_tokens': result['prompt_tokens'],
            'completion_tokens': result['completion_tokens'],
            'total_tokens': result['total_tokens'],
            'time_sec': result['time_sec'],
            'quality_score': quality_result['score'],
            'quality_reasoning': quality_result['reasoning'],
            'error': result['error'],
            'timestamp': datetime.now().isoformat()
        }

        self.total_tokens += result['total_tokens']
        self.total_time += result['time_sec']
        self.total_quality += quality_result['score']
        self.results.append(step_result)

        status = '✅' if not result['error'] else '❌'
        agent_tag = f"[{task.get('agent', 'SA')}]" if self.mode == 'nexusflow' else '[SA]'
        print(f"  {status} [{phase}] S{step_id:02d} {agent_tag} {task['desc'][:25]}... "
              f"| {result['time_sec']:.1f}s | {result['total_tokens']}tok "
              f"| Q={quality_result['score']}/10")

        return step_result

    def _build_context(self, task: dict) -> str:
        """收集同Phase+前Phase输出，限制3000字符"""
        task_phase = task['phase'][:2]
        context_parts = []

        # 同Phase前序输出
        for step in self.results:
            if step['phase'][:2] == task_phase and step['output']:
                context_parts.append(f"[{step['desc'][:20]}]: {step['output'][:300]}")

        # 前Phase摘要
        phase_order = ['P1', 'P2', 'P3', 'P4', 'P5', 'P6', 'P7', 'P8']
        current_idx = phase_order.index(task_phase) if task_phase in phase_order else -1
        if current_idx > 0:
            prev_phase = phase_order[current_idx - 1]
            for step in self.results:
                if step['phase'].startswith(prev_phase) and step['output']:
                    context_parts.append(f"[{step['desc'][:20]}]: {step['output'][:200]}")

        full_context = "\n".join(context_parts)
        if len(full_context) > 3000:
            full_context = full_context[:3000] + "\n...(上下文已截断)"
        return full_context

    def run(self, tasks: list) -> dict:
        """执行所有步骤"""
        print(f"\n{'='*60}")
        print(f"  {self.mode.upper()} 模式 - 开始执行")
        print(f"  步骤数: {len(tasks)}")
        print(f"{'='*60}")

        for task in tasks:
            self.execute_step(task)
            self._save_intermediate()

        return self._generate_summary()

    def _save_intermediate(self):
        """每步自动保存到JSON"""
        fname = f"{self.mode}_results.json"
        filepath = os.path.join(DATA_DIR, fname)
        data = {
            'mode': self.mode,
            'total_steps': len(self.results),
            'total_tokens': self.total_tokens,
            'total_time': round(self.total_time, 1),
            'avg_quality': round(self.total_quality / len(self.results), 2) if self.results else 0,
            'results': self.results
        }
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def _generate_summary(self) -> dict:
        n = len(self.results)
        if n == 0:
            return {'error': 'No steps executed'}

        qualities = [r['quality_score'] for r in self.results]
        times = [r['time_sec'] for r in self.results]
        tokens = [r['total_tokens'] for r in self.results]
        errors = sum(1 for r in self.results if r['error'])

        summary = {
            'mode': self.mode,
            'total_steps': n,
            'success_steps': n - errors,
            'error_steps': errors,
            'total_tokens': self.total_tokens,
            'total_time_sec': round(self.total_time, 1),
            'total_time_min': round(self.total_time / 60, 1),
            'avg_quality': round(sum(qualities) / n, 2),
            'max_quality': max(qualities),
            'min_quality': min(qualities),
            'avg_time_per_step': round(sum(times) / n, 2),
            'avg_tokens_per_step': round(sum(tokens) / n, 1),
            'quality_distribution': {
                '9-10': sum(1 for q in qualities if q >= 9),
                '7-8': sum(1 for q in qualities if 7 <= q < 9),
                '5-6': sum(1 for q in qualities if 5 <= q < 7),
                '3-4': sum(1 for q in qualities if 3 <= q < 5),
                '1-2': sum(1 for q in qualities if q < 3),
            },
            'phase_summary': {},
        }

        phases = {}
        for r in self.results:
            p = r['phase'][:2]
            if p not in phases:
                phases[p] = {'steps': 0, 'tokens': 0, 'time': 0, 'quality': 0}
            phases[p]['steps'] += 1
            phases[p]['tokens'] += r['total_tokens']
            phases[p]['time'] += r['time_sec']
            phases[p]['quality'] += r['quality_score']

        for p, v in phases.items():
            summary['phase_summary'][p] = {
                'steps': v['steps'],
                'tokens': v['tokens'],
                'time_sec': round(v['time'], 1),
                'avg_quality': round(v['quality'] / v['steps'], 2)
            }

        return summary


# ============================================================
# 主流程
# ============================================================
def main():
    print("=" * 60)
    print("  NexusFlow vs Single-Agent 公平对比 Benchmark")
    print("  80步 vs 80步 | 共160步 | 320次API调用")
    print("  日期:", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    print("  所有数据来自真实API调用，零模拟")
    print("=" * 60)

    # 1. 加载数据
    print("\n[1/4] 加载数据...")
    data_summary = load_data_summary()
    print(f"  数据摘要长度: {len(data_summary)} 字符")

    with open(os.path.join(DATA_DIR, 'data_summary_used.txt'), 'w') as f:
        f.write(data_summary)

    # 2. 定义任务
    print("\n[2/4] 定义分析任务...")
    sa_tasks = get_sa_tasks(data_summary)
    nf_tasks = get_nf_tasks(data_summary)
    print(f"  Single-Agent: {len(sa_tasks)} 步")
    print(f"  NexusFlow:    {len(nf_tasks)} 步")
    print(f"  总计:         {len(sa_tasks) + len(nf_tasks)} 步")
    print(f"  API调用:      {(len(sa_tasks) + len(nf_tasks)) * 2} 次 (含质量评估)")

    # 3. 执行 Single-Agent
    print("\n[3/4] 执行 Single-Agent 模式 (80步)...")
    sa_executor = BenchmarkExecutor('single_agent')
    sa_summary = sa_executor.run(sa_tasks)

    # 4. 执行 NexusFlow
    print("\n[4/4] 执行 NexusFlow 模式 (80步)...")
    nf_executor = BenchmarkExecutor('nexusflow')
    nf_summary = nf_executor.run(nf_tasks)

    # 5. 生成对比报告
    print("\n" + "=" * 60)
    print("  生成对比报告...")
    print("=" * 60)

    comparison = {
        'experiment_date': datetime.now().isoformat(),
        'experiment_type': '公平对比: 80步 vs 80步',
        'total_steps': 160,
        'total_api_calls': 320,
        'data_source': 'AKShare大宗商品数据（14个接口真实采集）',
        'llm': f'{MODEL} (DeepSeek API)',
        'single_agent': sa_summary,
        'nexusflow': nf_summary,
        'deltas': {}
    }

    if sa_summary.get('avg_quality') and nf_summary.get('avg_quality'):
        comparison['deltas'] = {
            'quality_diff': round(nf_summary['avg_quality'] - sa_summary['avg_quality'], 2),
            'quality_pct': round((nf_summary['avg_quality'] - sa_summary['avg_quality']) / sa_summary['avg_quality'] * 100, 1),
            'time_diff': round(nf_summary['total_time_sec'] - sa_summary['total_time_sec'], 1),
            'time_pct': round((nf_summary['total_time_sec'] - sa_summary['total_time_sec']) / sa_summary['total_time_sec'] * 100, 1),
            'token_diff': nf_summary['total_tokens'] - sa_summary['total_tokens'],
            'token_pct': round((nf_summary['total_tokens'] - sa_summary['total_tokens']) / sa_summary['total_tokens'] * 100, 1),
        }

    # 保存所有产物
    with open(os.path.join(DATA_DIR, 'comparison.json'), 'w') as f:
        json.dump(comparison, f, ensure_ascii=False, indent=2)

    with open(os.path.join(DATA_DIR, 'full_outputs_single_agent.json'), 'w') as f:
        json.dump({'single_agent': sa_executor.results}, f, ensure_ascii=False, indent=2)

    with open(os.path.join(DATA_DIR, 'full_outputs_nexusflow.json'), 'w') as f:
        json.dump({'nexusflow': nf_executor.results}, f, ensure_ascii=False, indent=2)

    # 打印对比摘要
    print(f"\n{'='*60}")
    print("  实验完成！核心对比 (80步 vs 80步):")
    print(f"{'='*60}")
    print(f"  {'指标':<20} {'Single-Agent':>15} {'NexusFlow':>15} {'差异':>10}")
    print(f"  {'-'*60}")
    print(f"  {'步骤数':<20} {sa_summary['total_steps']:>15} {nf_summary['total_steps']:>15}")
    print(f"  {'平均质量分':<18} {sa_summary['avg_quality']:>15} {nf_summary['avg_quality']:>15} {comparison['deltas'].get('quality_pct',0):>+9.1f}%")
    print(f"  {'总耗时(s)':<18} {sa_summary['total_time_sec']:>15.1f} {nf_summary['total_time_sec']:>15.1f} {comparison['deltas'].get('time_pct',0):>+9.1f}%")
    print(f"  {'总Token':<18} {sa_summary['total_tokens']:>15} {nf_summary['total_tokens']:>15} {comparison['deltas'].get('token_pct',0):>+9.1f}%")
    print(f"  {'每步平均Token':<16} {sa_summary['avg_tokens_per_step']:>15.1f} {nf_summary['avg_tokens_per_step']:>15.1f}")
    print(f"  {'错误数':<20} {sa_summary['error_steps']:>15} {nf_summary['error_steps']:>15}")

    # 分Phase对比
    print(f"\n  分Phase质量对比:")
    for p in ['P1','P2','P3','P4','P5','P6','P7','P8']:
        sa_q = sa_summary.get('phase_summary',{}).get(p,{}).get('avg_quality',0)
        nf_q = nf_summary.get('phase_summary',{}).get(p,{}).get('avg_quality',0)
        if sa_q or nf_q:
            print(f"    {p}: SA={sa_q:.1f} | NF={nf_q:.1f} | diff={nf_q-sa_q:+.1f}")

    print(f"\n  产物保存在: {DATA_DIR}/")
    print(f"  - comparison.json: 对比数据")
    print(f"  - full_outputs_single_agent.json: SA完整LLM输出")
    print(f"  - full_outputs_nexusflow.json: NF完整LLM输出")
    print(f"  - single_agent_results.json: SA逐步结果")
    print(f"  - nexusflow_results.json: NF逐步结果")

    return comparison

if __name__ == '__main__':
    main()
