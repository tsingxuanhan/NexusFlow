#!/usr/bin/env python3
"""
用 LLM Quality Scorer 对所有横向对比输出进行统一评分
确保评分标准一致、可复现
"""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from llm_quality_scorer import score_output
import json
import time

# 任务描述
SIMPLE_TASK = """查询WHO GHO数据库，获取BRICS五国（巴西、俄罗斯、印度、中国、南非）的以下三项指标的最新数据：
1. 出生时预期寿命 (Life expectancy at birth)
2. 婴儿死亡率 (Infant mortality rate)
3. 人均医疗卫生支出 (Health expenditure per capita)

然后计算各国综合健康指数并排名，给出分析结论。

已知 WHO GHO API 真实数据（作为基准验证）：
- 预期寿命(2021): 中国77.6 > 巴西72.4 > 俄罗斯70.0 > 印度67.3 > 南非61.5
- 婴儿死亡率(2023): 俄罗斯3.3 < 中国4.5 < 巴西13.8 < 南非24.4 < 印度24.5
- 人均卫生支出(2023): 巴西1009.84 > 俄罗斯1003.33 > 中国763.38 > 南非536.59 > 印度84.69

请完成：
1. 确认并列出上述数据
2. 使用排名求和法计算综合健康指数（各指标5国排名1-5分，求和）
3. 给出综合排名
4. 对各国医疗卫生体系进行深度分析
5. 指出数据局限性"""

COMPLEX_TASK = """对全球5个主要经济体（中国、美国、德国、印度、巴西）的能源转型进展进行综合评估，生成一份包含现状分析、政策评估、未来预测和具体建议的完整报告。

评估维度（6个维度）：
1. 能源结构现状（权重20%）：可再生能源发电占比、化石能源依赖度、核能占比、能源强度
2. 碳排放与气候承诺（权重20%）：人均CO2排放量、碳排放强度、NDC目标雄心度、碳中和承诺年份
3. 清洁能源投资（权重15%）：可再生能源投资总额、投资占GDP比例、绿色债券发行规模
4. 技术创新能力（权重15%）：清洁能源专利数量、储能技术成熟度、智能电网覆盖率
5. 政策与制度环境（权重15%）：碳定价机制、可再生能源补贴政策、化石燃料补贴规模
6. 社会公平与转型公正（权重15%）：能源贫困率、能源就业人数、公正转型政策覆盖度

输出要求：执行摘要、完整数据表、5国各800-1000字国家分析、1500字横向对比、1000字未来展望、500字方法论说明。总字数8000-10000字。"""

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

outputs_to_score = [
    {
        "name": "NexusFlow",
        "task": "simple",
        "file": "nexusflow_real_v3_output.md",
        "task_desc": SIMPLE_TASK,
    },
    {
        "name": "AutoGen",
        "task": "simple",
        "file": "autogen_output.md",
        "task_desc": SIMPLE_TASK,
    },
    {
        "name": "NexusFlow",
        "task": "complex",
        "file": "nexusflow_complex_output.md",
        "task_desc": COMPLEX_TASK,
    },
]

results = {"simple": {}, "complex": {}}

for item in outputs_to_score:
    filepath = os.path.join(BASE_DIR, item["file"])
    if not os.path.exists(filepath):
        print(f"❌ 文件不存在: {filepath}")
        continue
    
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    print(f"\n{'='*60}")
    print(f"评分: {item['name']} ({item['task']}任务)")
    print(f"文件: {item['file']} ({len(content)} 字符)")
    print(f"{'='*60}")
    
    result = score_output(item["task_desc"], content)
    
    scores = result["scores"]
    composite = result["composite"]
    composite_100 = round(composite * 100, 1)
    
    print(f"  Completeness:  {scores['completeness']}/10")
    print(f"  Depth:         {scores['depth']}/10")
    print(f"  Consistency:   {scores['consistency']}/10")
    print(f"  Novelty:       {scores['novelty']}/10")
    print(f"  Actionability: {scores['actionability']}/10")
    print(f"  加权总分:      {composite_100}/100")
    print(f"  理由: {result['reason']}")
    
    results[item["task"]][item["name"]] = {
        "scores": scores,
        "composite_01": composite,
        "composite_100": composite_100,
        "reason": result["reason"],
        "file": item["file"],
        "output_length": len(content),
    }
    
    time.sleep(2)  # 避免API限流

# 保存结果
output_path = os.path.join(BASE_DIR, "llm_evaluation_results.json")
with open(output_path, 'w', encoding='utf-8') as f:
    json.dump(results, f, ensure_ascii=False, indent=2)

print(f"\n\n{'='*60}")
print(f"✅ 评分结果已保存到: {output_path}")
print(f"{'='*60}")

# 打印汇总
print("\n## 简单任务评分汇总（WHO BRICS 医疗卫生）")
for name in ["NexusFlow", "AutoGen"]:
    if name in results["simple"]:
        r = results["simple"][name]
        print(f"  {name}: {r['composite_100']}分 (C={r['scores']['completeness']} D={r['scores']['depth']} Cons={r['scores']['consistency']} N={r['scores']['novelty']} A={r['scores']['actionability']})")

print("\n## 复杂任务评分汇总（全球能源转型）")
for name in ["NexusFlow"]:
    if name in results["complex"]:
        r = results["complex"][name]
        print(f"  {name}: {r['composite_100']}分 (C={r['scores']['completeness']} D={r['scores']['depth']} Cons={r['scores']['consistency']} N={r['scores']['novelty']} A={r['scores']['actionability']})")
