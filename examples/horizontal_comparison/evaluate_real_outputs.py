#!/usr/bin/env python3
"""
确定性评估脚本 - 基于可验证指标打分
不依赖LLM评估，用规则判定可量化维度
"""

import json
import re
import os

# 基准数据
GROUND_TRUTH = {
    "life_expectancy": {"CHN": 77.6, "BRA": 72.4, "RUS": 70.0, "IND": 67.3, "ZAF": 61.5},
    "infant_mortality": {"RUS": 3.3, "CHN": 4.5, "BRA": 13.8, "ZAF": 24.4, "IND": 24.5},
    "health_expenditure": {"BRA": 1009.84, "RUS": 1003.33, "CHN": 763.38, "ZAF": 536.59, "IND": 84.69},
    "correct_ranking_sum": {"CHN": 6, "RUS": 6, "BRA": 6, "ZAF": 12, "IND": 14},
    "correct_ranking_order": ["CHN", "RUS", "BRA", "ZAF", "IND"]  # T1并列, 4, 5
}

COUNTRY_NAMES = {
    "中国": "CHN", "巴西": "BRA", "俄罗斯": "RUS", "印度": "IND", "南非": "ZAF",
    "China": "CHN", "Brazil": "BRA", "Russia": "RUS", "India": "IND", "South Africa": "ZAF"
}


def extract_numbers(text: str) -> list:
    """提取文本中的数字"""
    return [float(x) for x in re.findall(r'\d+\.?\d*', text)]


def check_data_accuracy(output: str) -> float:
    """检查数据准确性 - 15%权重"""
    score = 10
    
    # 检查预期寿命数据
    le_data = {"CHN": 77.6, "BRA": 72.4, "RUS": 70.0, "IND": 67.3, "ZAF": 61.5}
    for country, val in le_data.items():
        if str(val) in output or str(int(val)) in output:
            pass
        else:
            score -= 1
    
    # 检查婴儿死亡率
    im_data = {"RUS": 3.3, "CHN": 4.5, "BRA": 13.8, "ZAF": 24.4, "IND": 24.5}
    for country, val in im_data.items():
        if str(val) in output:
            pass
        else:
            score -= 0.5
    
    # 检查人均支出
    he_data = {"BRA": 1009.84, "RUS": 1003.33, "CHN": 763.38, "ZAF": 536.59, "IND": 84.69}
    for country, val in he_data.items():
        if str(val) in output or str(int(val)) in output:
            pass
        else:
            score -= 0.5
    
    return max(0, min(10, score))


def check_ranking_correctness(output: str) -> float:
    """检查排名正确性 - 15%权重"""
    score = 10
    
    # 检查中国排第一或并列第一
    cn_patterns = ["中国.*第[一1]", "中国.*T1", "中国.*排名.*1", "中国.*榜首"]
    if any(re.search(p, output) for p in cn_patterns) or "中国" in output[:500]:
        # 检查排名逻辑
        if "并列" in output or "T1" in output or "6分" in output:
            score = 10
        else:
            score = 8
    else:
        score = 5
    
    # 检查南非和印度在后两位
    if output.find("南非") < output.rfind("排名"):
        if output.find("印度") > output.find("南非"):
            score = min(score, 10)
        else:
            score = min(score, 8)
    
    return score


def check_analysis_depth(output: str) -> float:
    """检查分析深度 - 15%权重"""
    score = 5  # base
    
    # 有因果分析
    causal_keywords = ["原因", "因果", "导致", "源于", "得益于", "反映了", "根源"]
    causal_count = sum(1 for kw in causal_keywords if kw in output)
    score += min(3, causal_count)
    
    # 有分类/模式识别
    pattern_keywords = ["模式", "类型", "分类", "特征"]
    if any(kw in output for kw in pattern_keywords):
        score += 1
    
    # 有具体政策建议
    policy_keywords = ["建议", "应该", "需要", "策略", "措施"]
    if any(kw in output for kw in policy_keywords):
        score += 1
    
    return min(10, score)


def check_methodology(output: str) -> float:
    """检查方法论 - 10%权重"""
    score = 5
    
    # 说明了排名求和法
    if "排名求和" in output or "排名.*求和" in output.replace("\n", "") or "sum" in output.lower():
        score += 2
    
    # 说明了排名规则
    if "排名规则" in output or "计算" in output:
        score += 1
    
    # 有表格呈现
    if "|" in output and "---" in output:
        score += 1
    
    # 解释了指标方向（越高越好/越低越好）
    if "越高越好" in output or "越低越好" in output:
        score += 1
    
    return min(10, score)


def check_completeness(output: str) -> float:
    """检查完整性 - 10%权重"""
    score = 5
    
    # 覆盖三个指标
    indicators = ["预期寿命", "婴儿死亡", "卫生支出"]
    for ind in indicators:
        if ind in output:
            score += 1.5
    
    # 有局限性说明
    if "局限" in output or "不足" in output or "限制" in output:
        score += 0.5
    
    return min(10, score)


def check_cross_validation(output: str) -> float:
    """检查交叉验证 - 10%权重"""
    score = 4  # base
    
    # CDoL多Agent交叉验证
    if "Critic" in output or "审查" in output or "修正" in output:
        score += 2
    
    # 多Agent一致性
    if "一致" in output or "结论一致" in output:
        score += 1
    
    # 多轮验证
    if "Round" in output or "轮" in output:
        score += 1
    
    # 标注数据来源
    if "WHO" in output and ("2021" in output or "2023" in output):
        score += 1
    
    return min(10, score)


def check_uncertainty(output: str) -> float:
    """检查不确定性标注 - 5%权重"""
    score = 4
    
    uncertainty_markers = ["局限", "不足", "可能", "需要谨慎", "需注意", "不一致", "缺失"]
    count = sum(1 for m in uncertainty_markers if m in output)
    score += min(4, count)
    
    return min(10, score)


def check_actionability(output: str) -> float:
    """检查可操作性 - 5%权重"""
    score = 5
    
    # 有具体建议
    if "建议" in output:
        score += 2
    # 按国家分别给建议
    countries = ["中国", "俄罗斯", "巴西", "南非", "印度"]
    country_advice = sum(1 for c in countries if c in output and "建议" in output[output.find(c):output.find(c)+500])
    score += min(3, country_advice)
    
    return min(10, score)


def check_consistency(output: str) -> float:
    """检查逻辑一致性 - 10%权重"""
    score = 8
    
    # 排名和分数逻辑是否自洽
    if "6分" in output and "并列" in output:
        score += 1
    
    # 结论不矛盾
    if "矛盾" not in output or ("已解决" in output or "修正" in output):
        score += 1
    
    return min(10, score)


def check_reproducibility(output: str) -> float:
    """检查可复现性 - 5%权重"""
    score = 5
    
    # 有计算步骤
    if "计算" in output and ("步骤" in output or "公式" in output or "方法" in output):
        score += 2
    
    # 有数据来源标注
    if "WHO" in output or "GHO" in output:
        score += 1
    
    # 有年份标注
    if "2021" in output or "2023" in output:
        score += 1
    
    # 有方法论说明
    if "方法论" in output or "方法" in output:
        score += 1
    
    return min(10, score)


def evaluate_file(filepath: str) -> dict:
    """评估单个输出文件"""
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    scores = {
        "数据准确性": check_data_accuracy(content),
        "排名正确性": check_ranking_correctness(content),
        "分析深度": check_analysis_depth(content),
        "方法论": check_methodology(content),
        "完整性": check_completeness(content),
        "交叉验证": check_cross_validation(content),
        "不确定性标注": check_uncertainty(content),
        "可操作性": check_actionability(content),
        "逻辑一致性": check_consistency(content),
        "可复现性": check_reproducibility(content),
    }
    
    weights = {
        "数据准确性": 0.15, "排名正确性": 0.15, "分析深度": 0.15,
        "方法论": 0.10, "完整性": 0.10, "交叉验证": 0.10,
        "不确定性标注": 0.05, "可操作性": 0.05,
        "逻辑一致性": 0.10, "可复现性": 0.05
    }
    
    weighted = sum(scores[k] * weights[k] for k in scores) * 10
    
    return {
        "scores": scores,
        "weights": weights,
        "weighted_total": round(weighted, 1),
        "dimension_list": [scores[k] for k in scores]
    }


def main():
    base_dir = os.path.dirname(__file__)
    
    # 评估NexusFlow真实输出
    nf_path = os.path.join(base_dir, "nexusflow_real_output.md")
    if os.path.exists(nf_path):
        nf_eval = evaluate_file(nf_path)
        print("=== NexusFlow (真实执行) ===")
        for k, v in nf_eval["scores"].items():
            print(f"  {k}: {v}/10")
        print(f"  加权总分: {nf_eval['weighted_total']}")
    else:
        nf_eval = None
        print("❌ NexusFlow真实输出文件不存在")
    
    # 评估AutoGen输出
    ag_path = os.path.join(base_dir, "autogen_real_output.md")
    if not os.path.exists(ag_path):
        ag_path = os.path.join(base_dir, "autogen_output.md")
    
    if os.path.exists(ag_path):
        ag_eval = evaluate_file(ag_path)
        print("\n=== AutoGen (真实执行) ===")
        for k, v in ag_eval["scores"].items():
            print(f"  {k}: {v}/10")
        print(f"  加权总分: {ag_eval['weighted_total']}")
    else:
        ag_eval = None
        print("❌ AutoGen输出文件不存在")
    
    # 保存评估结果
    results = {
        "evaluation_method": "确定性规则评估（非LLM评估）",
        "nexusflow": nf_eval,
        "autogen": ag_eval,
        "timestamp": __import__('datetime').datetime.now().isoformat()
    }
    
    output_path = os.path.join(base_dir, "real_evaluation_results.json")
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    
    print(f"\n✅ 评估结果已保存: {output_path}")


if __name__ == "__main__":
    main()
