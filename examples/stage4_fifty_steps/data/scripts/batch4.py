#!/usr/bin/env python3
"""Batch 4: Steps 36-45 (CDoL Round 2-3, Synthesis)"""
import requests, json, os

ART = "/app/data/所有对话/主对话/nexusflow-ppt/stage4_fifty_steps/stage4_artifacts"

def call_ds(sys_p, usr_p, max_t=3000):
    r = requests.post("https://api.deepseek.com/v1/chat/completions",
        headers={"Authorization":"Bearer sk-your-key-here","Content-Type":"application/json"},
        json={"model":"deepseek-chat","messages":[{"role":"system","content":sys_p},{"role":"user","content":usr_p}],"max_tokens":max_t,"temperature":0.7},
        timeout=120)
    d = r.json()
    return d["choices"][0]["message"]["content"], d.get("usage",{}).get("total_tokens",0)

def load(fn):
    try:
        with open(os.path.join(ART, fn)) as f: return f.read()
    except: return "(not found)"

def save(fn, content):
    with open(os.path.join(ART, fn), "w") as f: f.write(content)
    print(f"  Saved {fn} ({len(content)} chars)")

tokens = 0
critic_r1 = load("step33_critic_r1.md")
analyst_r1 = load("step34_analyst_r1.md")
corr = load("step27_correlation.md")
reg = load("step28_regression.md")
regional = load("step30_regional.md")
lag = load("step31_lag_effect.md")

# STEP 36: CDoL Protocol Code
print("STEP 36: CDoL Protocol Implementation")
r36, t = call_ds("你是Coder Agent，实现CDoL多轮辩论协议。",
"""实现CDoL协议Python框架：
- 6角色: Coordinator,Strategist,Researcher,Analyst,Critic,FusionJudge
- 3轮辩论: R1方法论→R2结果可靠性→R3整体结论
- 每轮: Critic质疑→各Agent回应→FusionJudge融合
- 终止条件: 共识度>0.7或max_rounds
输出: CDoLProtocol类 + Agent接口 + 融合算法 + 共识度量(Kappa)""", 2500)
tokens += t
save("step36_cdol_protocol.py", r36)

# STEP 39: CDoL Round 2 - Critic
print("STEP 39: CDoL Round 2 Critic")
r39, t = call_ds("你是Critic Agent，第二轮质疑聚焦结果可靠性。",
f"""CDoL第二轮 - 结果可靠性挑战
第一轮已讨论方法论: {critic_r1[:400]}
分析师修正: {analyst_r1[:400]}

新质疑(至少4个)：1)效应量实际意义 2)样本代表性 3)时间跨度 4)模型选择偏差 5)多重比较 6)外部效度""", 2000)
tokens += t
save("step39_critic_r2.md", r39)

# STEP 40: CDoL Round 2 - FusionJudge
print("STEP 40: CDoL Round 2 Fusion")
r40, t = call_ds("你是FusionJudge Agent，执行第二轮融合判定。",
f"""CDoL第二轮融合：
R2质疑: {r39}
R1修正结论: {analyst_r1[:400]}

输出：1)各Agent立场 2)共识/分歧点 3)权重判定 4)共识度(0-1) 5)融合结论(含置信度) 6)是否达共识阈值(>0.7)""", 2000)
tokens += t
save("step40_fusion_r2.md", r40)

# STEP 41: Synthesis
print("STEP 41: Results Synthesis")
r41, t = call_ds("你是Analyst Agent，综合分析结果整合。",
f"""综合所有结果：
相关: {corr[:300]}
回归: {reg[:300]}
区域: {regional[:300]}
滞后: {lag[:300]}
CDoL R2: {r40[:300]}

输出：1)温度-健康关联结论 2)降水-健康结论 3)区域异质性发现 4)H1/H2/H3裁定 5)创新点与局限 6)建议""", 2000)
tokens += t
save("step41_synthesis.md", r41)

# STEP 43: Hypothesis Verification
print("STEP 43: Hypothesis Verification")
r43, t = call_ds("你是Strategist Agent，假设验证总结。",
f"""综合：{r41[:600]}
CDoL R2: {r40[:400]}

最终裁定：
H1(温度-呼吸疾病): 支持/部分支持/拒绝 + 证据强度
H2(降水-心血管滞后): 支持/部分支持/拒绝 + 证据强度
H3(区域异质性): 支持/部分支持/拒绝 + 证据强度
整体置信度评分。""", 1500)
tokens += t
save("step43_hypothesis.md", r43)

# STEP 44: CDoL Round 3 - Critic
print("STEP 44: CDoL Round 3 Critic")
r44, t = call_ds("你是Critic Agent，最终轮质疑整体结论。",
f"""CDoL第三轮 - 最终挑战
假设验证: {r43[:500]}
综合结论: {r41[:400]}

最终质疑：1)外部效度 2)政策可行性 3)未解决矛盾 4)实际贡献度 5)是否需要额外验证
明确同意/反对的方面。""", 1500)
tokens += t
save("step44_critic_r3.md", r44)

# STEP 45: CDoL Round 3 - Final Fusion
print("STEP 45: CDoL Round 3 Final Fusion")
r45, t = call_ds("你是FusionJudge Agent，最终融合判定。",
f"""CDoL最终轮融合：
R3质疑: {r44}
R2共识: {r40[:400]}

输出：1)三轮共识演化轨迹 2)最终共识度(0-1) 3)共识结论(≤5条) 4)保留分歧 5)最终置信度 6)是否达可发表标准 7)报告呈现建议""", 2000)
tokens += t
save("step45_final_fusion.md", r45)

print(f"\nBatch 4 complete. Tokens: {tokens}")
