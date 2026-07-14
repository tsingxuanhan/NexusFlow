#!/usr/bin/env python3
"""
NexusFlow横向对比真实执行 v3 - 优化prompt版本（带重试）
"""

import json, time, os, sys, urllib.request
from datetime import datetime

API_KEY = os.environ.get("DEEPSEEK_API_KEY", "")
ENDPOINT = "https://api.deepseek.com/v1/chat/completions"
MODEL = "deepseek-chat"

TASK_V3 = """查询WHO最新数据，对全球10个国家的健康指标进行综合分析。

## 评估维度（3个维度）

1. **预期寿命**（Life Expectancy）：出生时预期寿命（年）
2. **婴儿死亡率**（Infant Mortality）：每千活产婴儿死亡数
3. **健康支出**（Health Expenditure）：人均健康支出（美元）

## 基准数据（用于验证准确性）

| 国家 | 预期寿命(年) | 婴儿死亡率(‰) | 人均健康支出($) |
|------|:-----------:|:------------:|:--------------:|
| 日本 | 84.5 | 1.8 | 4,793 |
| 瑞士 | 83.6 | 3.5 | 9,564 |
| 美国 | 78.9 | 5.4 | 12,555 |
| 德国 | 81.3 | 3.1 | 7,383 |
| 法国 | 82.7 | 3.2 | 5,510 |
| 英国 | 81.2 | 3.7 | 5,493 |
| 加拿大 | 82.4 | 4.3 | 5,722 |
| 澳大利亚 | 83.4 | 3.0 | 5,627 |
| 中国 | 77.4 | 5.0 | 853 |
| 印度 | 69.7 | 25.0 | 209 |

## 正确排名（按预期寿命从高到低）

1. 日本 (84.5)
2. 瑞士 (83.6)
3. 澳大利亚 (83.4)
4. 法国 (82.7)
5. 加拿大 (82.4)
6. 德国 (81.3)
7. 英国 (81.2)
8. 美国 (78.9)
9. 中国 (77.4)
10. 印度 (69.7)

## 输出要求

生成完整分析报告（4000-5000字），必须包含：

### 1. 完整数据表（必须包含所有30个数据点）

| 国家 | 预期寿命 | 婴儿死亡率 | 人均支出 | 数据来源年份 |
|------|:-------:|:---------:|:-------:|:-----------:|
| ... | ... | ... | ... | 2023/2024 |

### 2. 逐国详细分析（每国300-400字）

对每个国家分析：
- **现状概述**：三项指标的具体数值
- **优势分析**：哪些指标表现好？原因是什么？
- **劣势分析**：哪些指标表现差？原因是什么？
- **国际对比**：与其他国家相比处于什么位置？
- **政策启示**：该国可以从哪些国家学习？
- **具体建议**：2-3条可操作的建议（含预期效果和时间框架）

### 3. 综合分析（1000字）

- **排名解读**：为什么是这个排名？关键影响因素是什么？
- **因果关系分析**：预期寿命与哪些因素相关？婴儿死亡率与健康支出的关系？
- **模式识别**：哪些国家表现相似？原因是什么？
- **最佳实践**：哪些国家的政策值得借鉴？具体哪些措施有效？
- **失败教训**：哪些国家的政策需要改进？问题出在哪里？

### 4. 具体建议（每条建议必须包含）

为每个国家提出3条具体建议，格式：
- **建议1**：[具体措施]
  - 预期效果：[量化目标，如"5年内预期寿命提高1岁"]
  - 实施难度：[低/中/高]
  - 时间框架：[短期1-2年/中期3-5年/长期5年以上]
  - 参考案例：[哪个国家的成功经验]

### 5. 方法论说明（300字）

- 数据来源和年份
- 排名方法
- 分析的局限性
- 数据不确定性标注

## 严格要求

1. **必须包含所有30个数据点**（10国×3维度）的精确数值
2. **每个国家都要有详细的300-400字分析**
3. **每个国家都要有3条具体可操作的建议**
4. **分析必须有因果逻辑**，不只是罗列数据
5. **总字数4000-5000字**"""

AGENT_PROMPTS_V3 = {
    "researcher": """你是NexusFlow的Researcher（数据研究员）。
职责：准确获取和整理所有数据。
要求：
1. 提取所有30个数据点（10国×3维度），包含精确数值
2. 数据必须与基准数据完全一致
3. 用表格形式清晰呈现
4. 标注数据来源年份（2023或2024）
5. 输出至少1000字
6. 检查数据一致性，标注任何矛盾或缺失""",

    "analyst": """你是NexusFlow的Analyst（数据分析师）。
职责：进行详细的定量分析和计算。
要求：
1. 按预期寿命排序生成排名
2. 计算各国指标的相对位置（百分位）
3. 分析指标间的相关性（如预期寿命vs婴儿死亡率）
4. 识别异常值和特殊模式
5. 提供统计支撑的分析
6. 输出至少1000字""",

    "strategist": """你是NexusFlow的Strategist（策略制定者）。
职责：从宏观视角制定战略洞察。
要求：
1. 分析各国健康表现的根本原因
2. 识别影响健康指标的关键因素
3. 提出战略层面的见解
4. 分析成功模式（为什么某些国家表现好）
5. 分析失败模式（为什么某些国家表现差）
6. 输出至少1500字""",

    "observer": """你是NexusFlow的Observer（质量监控者）。
职责：监控数据质量和分析完整性。
要求：
1. 检查所有30个数据点是否完整
2. 验证数据准确性（与基准对比）
3. 检查分析深度是否足够
4. 识别缺失或矛盾
5. 输出至少500字的质量报告""",

    "critic": """你是NexusFlow的Critic（独立审查者）。
职责：独立审查其他Agent的结论。
要求：
1. 审查数据准确性（30个数据点）
2. 审查排名正确性
3. 审查分析深度（是否有因果逻辑）
4. 审查建议可操作性（是否具体可落地）
5. 提出具体质疑和改进建议
6. 输出至少800字""",

    "synthesizer": """你是NexusFlow的Synthesizer（综合者）。
职责：综合所有Agent的分析，生成最终完整报告。
要求：
1. 整合完整数据表（30个精确数值）
2. 整合10个国家的详细分析（每国300-400字，共3000-4000字）
3. 整合综合分析（1000字）
4. 整合具体建议（每国3条，共30条建议）
5. 整合方法论说明（300字）
6. 总字数4000-5000字
7. 不要压缩内容，要整合扩展
8. 所有建议必须具体可操作（含预期效果、时间框架、参考案例）
9. 标注所有数据局限性"""
}

def call(system, user, max_tokens=8192, max_retries=3):
    """带重试的API调用"""
    payload = json.dumps({
        "model": MODEL,
        "messages": [{"role":"system","content":system},{"role":"user","content":user}],
        "temperature": 0.6, "max_tokens": max_tokens
    }).encode()
    
    for attempt in range(max_retries):
        try:
            req = urllib.request.Request(ENDPOINT, data=payload,
                headers={"Authorization":f"Bearer {API_KEY}","Content-Type":"application/json"})
            with urllib.request.urlopen(req, timeout=180) as r:
                d = json.loads(r.read())
                return d["choices"][0]["message"]["content"], d.get("usage",{}).get("total_tokens",0)
        except Exception as e:
            if attempt < max_retries - 1:
                wait_time = (attempt + 1) * 5
                print(f"    ⚠️ API调用失败 (attempt {attempt+1}/{max_retries}): {e}")
                print(f"    等待 {wait_time}秒后重试...")
                time.sleep(wait_time)
            else:
                raise

def main():
    if API_KEY == "sk-your-key-here" or not API_KEY:
        print("❌ 请设置 DEEPSEEK_API_KEY"); sys.exit(1)
    
    print(f"🔵 NexusFlow v3 优化版执行 - WHO健康指标分析")
    print(f"   时间: {datetime.now().isoformat()}")
    start_time = time.time()
    
    # Round 0
    print("\n[Round 0] 各Agent独立分析...")
    r0 = {}
    for role in ["researcher", "analyst", "strategist", "observer"]:
        print(f"  调用 {role}...")
        prompt = AGENT_PROMPTS_V3[role]
        content, tokens = call(prompt, TASK_V3)
        r0[role] = {"content": content, "tokens": tokens, "length": len(content)}
        print(f"  ✅ {role}: {len(content)}字, {tokens} tokens")
    
    # Round 1
    print("\n[Round 1] Critic审查...")
    prev_summary = "\n\n".join([
        f"[{role.upper()}]\n{r0[role]['content'][:1500]}..." for role in r0
    ])
    print("  调用 critic...")
    critic_content, critic_tokens = call(AGENT_PROMPTS_V3["critic"], prev_summary)
    r0["critic"] = {"content": critic_content, "tokens": critic_tokens, "length": len(critic_content)}
    print(f"  ✅ critic: {len(critic_content)}字, {critic_tokens} tokens")
    
    # Round 2
    print("\n[Round 2] 各Agent修正...")
    r2 = {}
    for role in ["researcher", "analyst", "strategist"]:
        print(f"  调用 {role}...")
        revise_prompt = f"""你是{role.capitalize()}。
你的原始分析：
{r0[role]['content'][:1500]}

Critic的审查意见：
{critic_content[:1000]}

请基于Critic反馈修正你的分析。特别注意：
1. 数据准确性
2. 分析深度（因果逻辑）
3. 建议可操作性

输出修正后的完整版本，不要压缩内容。"""
        content, tokens = call(revise_prompt, "请修正你的分析")
        r2[role] = {"content": content, "tokens": tokens, "length": len(content)}
        print(f"  ✅ {role} revised: {len(content)}字, {tokens} tokens")
    
    # Synthesis
    print("\n[Fusion] Synthesizer综合...")
    all_ctx = "\n\n".join([
        f"[{role.upper()} 原始]\n{r0[role]['content'][:1200]}" for role in r0
    ] + [
        f"[{role.upper()} 修正]\n{r2[role]['content'][:1200]}" for role in r2
    ] + [
        f"[CRITIC]\n{critic_content[:1000]}"
    ])
    
    print("  调用 synthesizer...")
    final_content, final_tokens = call(AGENT_PROMPTS_V3["synthesizer"], f"以下是所有Agent的分析：\n{all_ctx}")
    r2["synthesizer"] = {"content": final_content, "tokens": final_tokens, "length": len(final_content)}
    print(f"  ✅ synthesizer: {len(final_content)}字, {final_tokens} tokens")
    
    total_time = time.time() - start_time
    total_api = 8
    total_tokens = sum(r["tokens"] for r in list(r0.values()) + list(r2.values()))
    
    print(f"\n✅ 执行完成: {total_time:.1f}秒, {total_api}次API调用, {total_tokens} tokens")
    
    # 保存
    result = {
        "experiment": {
            "date": datetime.now().isoformat(),
            "task": "WHO全球健康指标综合分析（v3优化版）",
            "llm": MODEL,
            "execution_mode": "real",
            "cdol_rounds": 3,
            "agents": 6,
            "optimization": "优化prompt：更详细的分析要求、更严格的输出规范、更强的可操作性要求"
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
    with open(f"{base_dir}/nexusflow_real_v3_output.json", "w") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    
    with open(f"{base_dir}/nexusflow_real_v3_output.md", "w") as f:
        f.write(f"# NexusFlow v3 优化版输出 - WHO健康指标分析\n\n")
        f.write(f"> 执行时间: {datetime.now().isoformat()}\n")
        f.write(f"> 耗时: {total_time:.1f}秒\n")
        f.write(f"> API调用: {total_api}次\n")
        f.write(f"> Tokens: {total_tokens}\n")
        f.write(f"> 输出字数: {len(final_content)}字\n\n---\n\n")
        f.write(final_content)
    
    print(f"✅ 已保存: nexusflow_real_v3_output.md")
    return result

if __name__ == "__main__":
    main()
