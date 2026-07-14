#!/usr/bin/env python3
"""
NexusFlow 横向对比 - 真实执行版
================================
用NexusFlow CDoL三轮协议 + DeepSeek API真实调用，
执行与AutoGen/CrewAI完全相同的WHO BRICS任务。

对比指标: score / elapsed / api_calls / tokens
"""

import json
import time
import os
import sys
import urllib.request
import urllib.error
from datetime import datetime
from typing import Dict, List, Tuple

# ============================================================
# 配置
# ============================================================
API_KEY = os.environ.get("DEEPSEEK_API_KEY", "sk-your-key-here")
ENDPOINT = "https://api.deepseek.com/v1/chat/completions"
MODEL = "deepseek-chat"

WHO_TASK = """查询WHO GHO数据库，获取BRICS五国（巴西、俄罗斯、印度、中国、南非）的以下三项指标的最新数据：
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

# ============================================================
# CDoL 三轮协议实现
# ============================================================

AGENT_PROMPTS = {
    "researcher": """你是NexusFlow的Researcher（数据研究员）。
你的职责是准确获取和整理数据。
请基于任务要求，确认WHO GHO数据，整理成结构化格式。
要求：数据准确、标注来源年份和置信区间。""",

    "analyst": """你是NexusFlow的Analyst（数据分析师）。
你的职责是进行定量分析和计算。
请基于WHO数据：
1. 计算各国在三个指标上的排名（1-5分）
2. 用排名求和法计算综合健康指数
3. 给出综合排名
要求：计算过程透明、可复现。""",

    "strategist": """你是NexusFlow的Strategist（策略制定者）。
你的职责是从宏观视角制定分析框架。
请基于数据和分析结果，对BRICS五国医疗卫生体系进行深度分析。
要求：包含因果分析、政策建议、横向对比。""",

    "critic": """你是NexusFlow的Critic（独立审查者）。
你的职责是质疑和审查其他Agent的结论。
请审查以下结论的准确性、完整性和逻辑一致性：
{prev_conclusions}
提出你的质疑（如有），或确认结论正确。
要求：独立判断，不受其他Agent影响。""",

    "synthesizer": """你是NexusFlow的Synthesizer（综合者）。
你的职责是综合所有Agent的分析结果，生成最终报告。
请基于所有Agent的贡献，生成一份完整的WHO BRICS健康分析报告。
要求：
1. 数据准确性（与WHO官方数据一致）
2. 排名正确性
3. 分析深度（因果分析，非仅罗列）
4. 方法论合理
5. 完整覆盖
6. 标注局限性
7. 结论自洽"""
}


def call_deepseek(system_prompt: str, user_content: str) -> Tuple[str, int]:
    """调用DeepSeek API，返回(回复内容, token消耗)"""
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json"
    }
    payload = json.dumps({
        "model": MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content}
        ],
        "temperature": 0.7,
        "max_tokens": 4096
    }).encode()

    req = urllib.request.Request(ENDPOINT, data=payload, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            data = json.loads(resp.read())
            content = data["choices"][0]["message"]["content"]
            tokens = data.get("usage", {}).get("total_tokens", 0)
            return content, tokens
    except Exception as e:
        return f"ERROR: {e}", 0


def run_nexusflow_cdol(task: str) -> Dict:
    """
    NexusFlow CDoL三轮协议执行
    
    Round 0: 各Agent独立分析（信息不对称）
    Round 1: 归因分析（识别矛盾来源）
    Round 2: 修正结论（基于反馈调整）
    Fusion: 融合判断
    Synthesis: 最终报告
    """
    api_calls = 0
    total_tokens = 0
    round_results = {}
    
    # === Round 0: 各Agent独立分析 ===
    print("  [Round 0] 各Agent独立分析...")
    r0_conclusions = {}
    for role, prompt in AGENT_PROMPTS.items():
        if role in ("critic", "synthesizer"):
            continue  # Critic和Synthesizer在后续轮次
        sys_p = prompt
        content, tokens = call_deepseek(sys_p, task)
        api_calls += 1
        total_tokens += tokens
        r0_conclusions[role] = content
        print(f"    {role}: {len(content)}字, {tokens}tokens")
    
    # === Round 1: Critic审查 ===
    print("  [Round 1] Critic审查...")
    prev_conclusions = "\n\n".join([
        f"[{role}] {c[:500]}..." for role, c in r0_conclusions.items()
    ])
    critic_prompt = AGENT_PROMPTS["critic"].format(prev_conclusions=prev_conclusions)
    critic_content, critic_tokens = call_deepseek(critic_prompt, "请审查上述结论")
    api_calls += 1
    total_tokens += critic_tokens
    round_results["critic_round1"] = critic_content
    print(f"    critic: {len(critic_content)}字, {critic_tokens}tokens")
    
    # === Round 2: 各Agent基于Critic反馈修正 ===
    print("  [Round 2] 各Agent修正结论...")
    r2_conclusions = {}
    for role in ["researcher", "analyst", "strategist"]:
        revise_prompt = f"""你是NexusFlow的{role.capitalize()}。
你之前的分析结论：
{r0_conclusions[role][:1000]}

Critic的审查意见：
{critic_content[:1000]}

请基于Critic的反馈修正你的结论。如果Critic的意见合理，采纳并修正；如果不合理，坚持原结论并说明理由。"""
        content, tokens = call_deepseek(revise_prompt, "请修正你的结论")
        api_calls += 1
        total_tokens += tokens
        r2_conclusions[role] = content
        print(f"    {role} revised: {len(content)}字, {tokens}tokens")
    
    # === Fusion + Synthesis ===
    print("  [Fusion] 综合最终报告...")
    all_context = "\n\n".join([
        f"[{role} Round 0] {c[:500]}" for role, c in r0_conclusions.items()
    ] + [
        f"[Critic] {critic_content[:500]}"
    ] + [
        f"[{role} Round 2] {c[:500]}" for role, c in r2_conclusions.items()
    ])
    
    synth_content, synth_tokens = call_deepseek(
        AGENT_PROMPTS["synthesizer"],
        f"以下是所有Agent的分析结果和Critic审查意见：\n{all_context}\n\n请生成最终完整报告。"
    )
    api_calls += 1
    total_tokens += synth_tokens
    print(f"    synthesizer: {len(synth_content)}字, {synth_tokens}tokens")
    
    return {
        "output": synth_content,
        "api_calls": api_calls,
        "tokens": total_tokens,
        "round0": r0_conclusions,
        "critic": critic_content,
        "round2": r2_conclusions
    }


def evaluate_output(output: str) -> Dict:
    """10维度评估输出质量"""
    # 使用LLM做评估
    eval_prompt = """你是一个严格的评估专家。请对以下WHO BRICS健康分析报告进行10维度评分。
每个维度0-10分。评分标准：
1. 数据准确性(15%): 数值是否与WHO官方一致
2. 排名正确性(15%): 国家排名是否正确
3. 分析深度(15%): 是否有因果分析
4. 方法论(10%): 综合指数计算是否合理
5. 完整性(10%): 是否覆盖全部3项指标
6. 交叉验证(10%): 是否多源比对
7. 不确定性标注(5%): 是否标注数据局限
8. 可操作性(5%): 建议是否可落地
9. 逻辑一致性(10%): 结论是否自洽
10. 可复现性(5%): 过程是否可复现

基准数据：
- 预期寿命(2021): 中国77.6 > 巴西72.4 > 俄罗斯70.0 > 印度67.3 > 南非61.5
- 婴儿死亡率(2023): 俄罗斯3.3 < 中国4.5 < 巴西13.8 < 南非24.4 < 印度24.5
- 人均卫生支出(2023): 巴西1009.84 > 俄罗斯1003.33 > 中国763.38 > 南非536.59 > 印度84.69
- 正确综合排名: 中国12分=俄罗斯12分=巴西12分 > 南非5分 > 印度4分

请严格按以下JSON格式输出（不要输出其他内容）：
{"scores": [d1, d2, ..., d10], "total": 加权总分}"""

    eval_content, eval_tokens = call_deepseek(eval_prompt, f"请评估以下报告：\n{output[:4000]}")
    
    try:
        # 尝试提取JSON
        start = eval_content.find("{")
        end = eval_content.rfind("}") + 1
        if start >= 0 and end > start:
            result = json.loads(eval_content[start:end])
            return {
                "dimension_scores": result.get("scores", [0]*10),
                "total_score": result.get("total", 0),
                "eval_tokens": eval_tokens,
                "raw_eval": eval_content
            }
    except:
        pass
    
    return {
        "dimension_scores": [0]*10,
        "total_score": 0,
        "eval_tokens": eval_tokens,
        "raw_eval": eval_content
    }


def main():
    print("🔵 NexusFlow 横向对比 - 真实执行")
    print(f"   时间: {datetime.now().isoformat()}")
    print(f"   模型: {MODEL}")
    print(f"   API Key: {'✅ 已设置' if API_KEY != 'sk-your-key-here' else '❌ 未设置'}")
    print()
    
    if API_KEY == "sk-your-key-here":
        print("❌ 请设置环境变量 DEEPSEEK_API_KEY")
        sys.exit(1)
    
    # 执行CDoL三轮协议
    start_time = time.time()
    result = run_nexusflow_cdol(WHO_TASK)
    elapsed = time.time() - start_time
    
    print(f"\n  执行完成: {elapsed:.1f}秒, {result['api_calls']}次API调用, {result['tokens']}tokens")
    
    # 评估
    print("\n📊 评估输出质量...")
    evaluation = evaluate_output(result["output"])
    eval_time = time.time() - start_time
    
    # 计算加权总分
    weights = [0.15, 0.15, 0.15, 0.10, 0.10, 0.10, 0.05, 0.05, 0.10, 0.05]
    weighted_score = sum(s * w for s, w in zip(evaluation["dimension_scores"], weights)) * 10
    
    # 汇总结果
    final_result = {
        "experiment": {
            "date": datetime.now().isoformat(),
            "task_description": "WHO BRICS 五国医疗卫生体系分析",
            "llm": f"{MODEL} (DeepSeek API)",
            "api_endpoint": ENDPOINT,
            "framework_version": "NexusFlow v3.4 CDoL",
            "execution_mode": "real"
        },
        "result": {
            "framework": "NexusFlow",
            "mode": "real",
            "score": round(weighted_score, 1),
            "elapsed": round(elapsed, 1),
            "api_calls": result["api_calls"],
            "tokens": result["tokens"],
            "evaluation": {
                "total_score": round(weighted_score, 1),
                "dimension_scores": evaluation["dimension_scores"],
                "eval_tokens": evaluation["eval_tokens"]
            },
            "cdol_details": {
                "round0_agents": len(result["round0"]),
                "critic_review": True,
                "round2_revisions": len(result["round2"]),
                "total_rounds": 3
            },
            "timestamp": datetime.now().isoformat()
        },
        "output_preview": result["output"][:2000],
        "full_output_length": len(result["output"])
    }
    
    # 保存结果
    output_path = os.path.join(os.path.dirname(__file__), "nexusflow_real_result.json")
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(final_result, f, ensure_ascii=False, indent=2)
    
    # 保存完整输出
    output_md_path = os.path.join(os.path.dirname(__file__), "nexusflow_real_output.md")
    with open(output_md_path, "w", encoding="utf-8") as f:
        f.write("# NexusFlow 横向对比 - 真实执行输出\n\n")
        f.write(f"> 执行时间: {datetime.now().isoformat()}\n")
        f.write(f"> 模型: {MODEL}\n")
        f.write(f"> 耗时: {elapsed:.1f}秒\n")
        f.write(f"> API调用: {result['api_calls']}次\n")
        f.write(f"> Token消耗: {result['tokens']}\n")
        f.write(f"> 评估得分: {weighted_score:.1f}/100\n\n")
        f.write("---\n\n")
        f.write(result["output"])
    
    print(f"\n✅ 结果已保存:")
    print(f"   JSON: {output_path}")
    print(f"   输出: {output_md_path}")
    print(f"\n📊 最终得分: {weighted_score:.1f}/100")
    print(f"   维度评分: {evaluation['dimension_scores']}")
    print(f"   耗时: {elapsed:.1f}秒")
    print(f"   API调用: {result['api_calls']}次")
    print(f"   Tokens: {result['tokens']}")
    
    return final_result


if __name__ == "__main__":
    main()
