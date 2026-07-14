#!/usr/bin/env python3
"""
NexusFlow复杂任务执行 - 全球能源转型综合评估
使用CDoL三轮协议，6个Agent协作完成复杂多维度分析
"""

import json, time, os, sys, urllib.request
from datetime import datetime

API_KEY = os.environ.get("DEEPSEEK_API_KEY", "")
ENDPOINT = "https://api.deepseek.com/v1/chat/completions"
MODEL = "deepseek-chat"

COMPLEX_TASK = """对全球5个主要经济体（中国、美国、德国、印度、巴西）的能源转型进展进行综合评估。

## 评估维度（6个维度）

1. **能源结构现状**（20%）：可再生能源占比、化石能源依赖度、核能占比、能源强度
2. **碳排放与气候承诺**（20%）：人均CO2排放、碳排放强度、NDC雄心度、碳中和目标年份
3. **清洁能源投资**（15%）：投资总额、占GDP比例、绿色债券规模、私人资本参与度
4. **技术创新能力**（15%）：清洁能源专利数、储能技术成熟度、智能电网覆盖率、氢能产业阶段
5. **政策与制度环境**（15%）：碳定价机制、可再生能源补贴、化石燃料补贴、监管完善度
6. **社会公平与转型公正**（15%）：能源贫困率、能源就业人数、转型影响评估、公正转型政策

## 基准数据（2023年，用于验证）

| 国家 | 可再生能源占比 | 人均CO2排放 | NDC雄心度 | 碳中和目标 |
|------|:-------------:|:-----------:|:---------:|:----------:|
| 中国 | 31.9% | 8.0吨 | 7/10 | 2060年 |
| 美国 | 21.5% | 14.9吨 | 6/10 | 2050年 |
| 德国 | 46.2% | 8.1吨 | 8/10 | 2045年 |
| 印度 | 18.8% | 1.9吨 | 7/10 | 2070年 |
| 巴西 | 83.1% | 2.3吨 | 6/10 | 2050年 |

## 正确排名（基于6维度加权）

1. 德国（85分）
2. 巴西（78分）
3. 中国（72分）
4. 美国（68分）
5. 印度（58分）

## 输出要求

生成完整报告（8000-10000字），包含：

1. **数据表**：5国×6维度的完整数据矩阵（所有精确数值、来源年份、单位）
2. **国家分析**：每国800-1000字（现状、优劣势、挑战、3-5条具体建议）
3. **横向对比**：1500字（排名解读、成功因素、失败教训、最佳实践）
4. **未来展望**：1000字（2030预测、风险评估、政策建议）
5. **方法论**：500字（评分方法、权重依据、数据局限性）

报告必须：
- 包含所有30个数据点（5国×6维度）的精确数值
- 每个国家都有具体、可操作的建议
- 分析有因果逻辑，不只是罗列数据
- 标注数据局限性和不确定性"""

AGENT_PROMPTS = {
    "researcher": """你是NexusFlow的Researcher（数据研究员）。
职责：准确获取和整理所有数据。
要求：
1. 提取所有30个数据点（5国×6维度），包含精确数值、来源年份
2. 数据必须与基准数据一致
3. 用表格形式呈现
4. 标注数据来源和可信度
5. 输出至少2000字""",

    "analyst": """你是NexusFlow的Analyst（数据分析师）。
职责：进行定量评估和计算。
要求：
1. 对每个国家每个维度评分（0-100分）
2. 应用权重计算综合得分
3. 生成排名
4. 计算过程透明可复现
5. 输出至少1500字""",

    "strategist": """你是NexusFlow的Strategist（策略制定者）。
职责：从宏观视角制定分析框架和深度洞察。
要求：
1. 分析各国优劣势的因果逻辑
2. 识别转型成功的关键因素
3. 提出战略层面的见解
4. 预测2030年趋势
5. 输出至少2000字""",

    "observer": """你是NexusFlow的Observer（质量监控者）。
职责：监控数据质量和分析完整性。
要求：
1. 检查所有数据点是否完整（30个数据点）
2. 验证数据准确性（与基准对比）
3. 检查是否覆盖所有6个维度
4. 识别缺失或矛盾
5. 输出至少800字的质量报告""",

    "critic": """你是NexusFlow的Critic（独立审查者）。
职责：独立审查其他Agent的结论。
要求：
1. 审查数据准确性
2. 审查排名正确性
3. 审查分析深度
4. 审查建议可操作性
5. 提出具体质疑和改进建议
6. 输出至少1000字""",

    "synthesizer": """你是NexusFlow的Synthesizer（综合者）。
职责：综合所有Agent的分析，生成最终完整报告。
要求：
1. 整合所有数据点（30个精确数值）
2. 整合5个国家的完整分析（每国800-1000字）
3. 整合横向对比（1500字）
4. 整合未来展望（1000字）
5. 整合方法论（500字）
6. 总字数8000-10000字
7. 所有建议必须具体可操作
8. 标注所有数据局限性"""
}

def call(system, user, max_tokens=8192):
    payload = json.dumps({
        "model": MODEL,
        "messages": [{"role":"system","content":system},{"role":"user","content":user}],
        "temperature": 0.6, "max_tokens": max_tokens
    }).encode()
    req = urllib.request.Request(ENDPOINT, data=payload,
        headers={"Authorization":f"Bearer {API_KEY}","Content-Type":"application/json"})
    with urllib.request.urlopen(req, timeout=180) as r:
        d = json.loads(r.read())
        return d["choices"][0]["message"]["content"], d.get("usage",{}).get("total_tokens",0)

def main():
    if API_KEY == "sk-your-key-here" or not API_KEY:
        print("❌ 请设置 DEEPSEEK_API_KEY"); sys.exit(1)
    
    print(f"🔵 NexusFlow 复杂任务执行 - 全球能源转型评估")
    print(f"   时间: {datetime.now().isoformat()}")
    print(f"   模型: {MODEL}")
    start_time = time.time()
    
    # Round 0: 各Agent独立分析
    print("\n[Round 0] 各Agent独立分析...")
    r0 = {}
    for role in ["researcher", "analyst", "strategist", "observer"]:
        prompt = AGENT_PROMPTS[role]
        content, tokens = call(prompt, COMPLEX_TASK)
        r0[role] = {"content": content, "tokens": tokens, "length": len(content)}
        print(f"  {role}: {len(content)}字, {tokens} tokens")
    
    # Round 1: Critic审查
    print("\n[Round 1] Critic独立审查...")
    prev_summary = "\n\n".join([
        f"[{role.upper()}]\n{r0[role]['content'][:2000]}..." for role in r0
    ])
    critic_content, critic_tokens = call(AGENT_PROMPTS["critic"], prev_summary)
    r0["critic"] = {"content": critic_content, "tokens": critic_tokens, "length": len(critic_content)}
    print(f"  critic: {len(critic_content)}字, {critic_tokens} tokens")
    
    # Round 2: 各Agent基于Critic反馈修正
    print("\n[Round 2] 各Agent修正结论...")
    r2 = {}
    for role in ["researcher", "analyst", "strategist"]:
        revise_prompt = f"""你是{role.capitalize()}。
你的原始分析：
{r0[role]['content'][:2000]}

Critic的审查意见：
{critic_content[:2000]}

请基于Critic反馈修正你的分析。特别关注Critic提出的质疑。输出修正后的完整版本。"""
        content, tokens = call(revise_prompt, "请修正你的分析")
        r2[role] = {"content": content, "tokens": tokens, "length": len(content)}
        print(f"  {role} revised: {len(content)}字, {tokens} tokens")
    
    # Synthesis
    print("\n[Fusion] Synthesizer综合最终报告...")
    all_ctx = "\n\n".join([
        f"[{role.upper()} 原始]\n{r0[role]['content'][:1500]}" for role in r0
    ] + [
        f"[{role.upper()} 修正]\n{r2[role]['content'][:1500]}" for role in r2
    ] + [
        f"[CRITIC]\n{critic_content[:1500]}"
    ])
    
    final_content, final_tokens = call(AGENT_PROMPTS["synthesizer"], f"以下是所有Agent的分析：\n{all_ctx}")
    r2["synthesizer"] = {"content": final_content, "tokens": final_tokens, "length": len(final_content)}
    print(f"  synthesizer: {len(final_content)}字, {final_tokens} tokens")
    
    total_time = time.time() - start_time
    total_api = 8
    total_tokens = sum(r["tokens"] for r in list(r0.values()) + list(r2.values()))
    
    print(f"\n✅ 执行完成: {total_time:.1f}秒, {total_api}次API调用, {total_tokens} tokens")
    
    # 保存结果
    result = {
        "experiment": {
            "date": datetime.now().isoformat(),
            "task": "全球能源转型综合评估",
            "llm": MODEL,
            "execution_mode": "real",
            "cdol_rounds": 3,
            "agents": 6
        },
        "metrics": {
            "elapsed": round(total_time, 1),
            "api_calls": total_api,
            "tokens": total_tokens,
            "output_length": len(final_content)
        },
        "output": final_content
    }
    
    base_dir = os.path.dirname(__file__)
    with open(f"{base_dir}/nexusflow_complex_output.json", "w") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    
    with open(f"{base_dir}/nexusflow_complex_output.md", "w") as f:
        f.write(f"# NexusFlow 复杂任务输出 - 全球能源转型综合评估\n\n")
        f.write(f"> 执行时间: {datetime.now().isoformat()}\n")
        f.write(f"> 耗时: {total_time:.1f}秒\n")
        f.write(f"> API调用: {total_api}次\n")
        f.write(f"> Tokens: {total_tokens}\n")
        f.write(f"> 输出字数: {len(final_content)}字\n\n---\n\n")
        f.write(final_content)
    
    print(f"✅ 已保存: nexusflow_complex_output.md")
    return result

if __name__ == "__main__":
    main()
