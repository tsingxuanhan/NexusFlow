#!/usr/bin/env python3
"""Batch 5: Steps 46-50 (Report Generation)"""
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
fusion = load("step45_final_fusion.md")
hypo = load("step43_hypothesis.md")
synth = load("step41_synthesis.md")
lit = load("step04_08_literature.md")
framework = load("step03_framework.md")
exp_design = load("step20_26_experiment.md")
corr = load("step27_correlation.md")
reg = load("step28_regression.md")
regional = load("step30_regional.md")

# STEP 46: Report Outline
print("STEP 46: Report Outline")
r46, t = call_ds("你是Archivist Agent，整理全部产物构建报告大纲。",
f"""产物：最终结论:{fusion[:400]} 假设验证:{hypo[:400]} 综合:{synth[:400]} 文献:{lit[:400]}
构建报告大纲(标题/摘要要点/各章节要点和字数)。""", 2000)
tokens += t
save("step46_outline.md", r46)

# STEP 47: Methods Section
print("STEP 47: Methods Section")
r47, t = call_ds("你是Archivist Agent，撰写学术风格研究方法章节。",
f"""框架:{framework[:600]}
实验设计:{exp_design[:600]}
撰写3.研究方法(3.1研究设计 3.2数据来源NOAA GSOY+WHO GHO 3.3变量定义 3.4统计方法 3.5质量控制 3.6局限性)
~1500字。""", 3000)
tokens += t
save("step47_methods.md", r47)

# STEP 48: Results & Discussion
print("STEP 48: Results & Discussion")
r48, t = call_ds("你是Archivist Agent，撰写结果与讨论章节。",
f"""相关:{corr[:400]} 回归:{reg[:400]} 区域:{regional[:400]} CDoL:{fusion[:400]} 假设:{hypo[:400]}
撰写4.结果(4.1描述统计 4.2温度-健康 4.3降水-健康 4.4区域异质性 4.5假设检验) 5.讨论(5.1文献对比 5.2机制 5.3政策 5.4局限 5.5展望) ~2000字""", 4000)
tokens += t
save("step48_results.md", r48)

# STEP 49: Abstract & Conclusion
print("STEP 49: Abstract & Conclusion")
r49, t = call_ds("你是Archivist Agent，撰写摘要和结论。",
f"""全部结论:{fusion[:500]} 假设:{hypo[:400]} 结果:{r48[:500]}
输出：1)中文摘要(300字) 2)英文Abstract(250词) 3)关键词 4)结论章节(800字)""", 3000)
tokens += t
save("step49_abstract.md", r49)

# STEP 50: Quality Check
print("STEP 50: Final Quality Check")
r50, t = call_ds("你是Archivist Agent，最终质量检查。",
f"""大纲:{r46[:200]} 方法:{r47[:300]} 结果:{r48[:300]} 摘要:{r49[:300]} CDoL:{fusion[:300]}
检查：1)逻辑一致性 2)数据引用 3)可复现性 4)统计报告 5)学术规范 6)共识度 7)可读性
输出：质量评估+修改建议+质量评分(满分10)""", 2000)
tokens += t
save("step50_quality.md", r50)

print(f"\nBatch 5 complete. Tokens: {tokens}")
