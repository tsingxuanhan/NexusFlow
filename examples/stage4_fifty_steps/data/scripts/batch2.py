#!/usr/bin/env python3
"""Batch 2: Steps 4-13 (Literature + Hypothesis) + Steps 14-17 (NOAA/WHO Data)"""
import requests, json, os, subprocess, time

BASE = "/app/data/所有对话/主对话/nexusflow-ppt/stage4_fifty_steps"
ART = os.path.join(BASE, "stage4_artifacts")
NOAA = "/app/data/所有对话/主对话/.skills/skill_noaa-data-skill/bin/_cli_wrapper.py"
WHO = "/app/data/所有对话/主对话/.skills/skill_who-data-skill/scripts/_cli_wrapper.py"

def call_ds(sys_p, usr_p, max_t=3000):
    r = requests.post("https://api.deepseek.com/v1/chat/completions",
        headers={"Authorization":"Bearer sk-your-key-here","Content-Type":"application/json"},
        json={"model":"deepseek-chat","messages":[{"role":"system","content":sys_p},{"role":"user","content":usr_p}],"max_tokens":max_t,"temperature":0.7},
        timeout=120)
    d = r.json()
    return d["choices"][0]["message"]["content"], d.get("usage",{}).get("total_tokens",0)

def noaa(cmd, params=None):
    c = ["python3", NOAA, "call", cmd]
    if params:
        for k,v in params.items(): c.extend(["--param", f"{k}={v}"])
    r = subprocess.run(c, capture_output=True, text=True, timeout=60, cwd=os.path.dirname(NOAA))
    return r.stdout.strip() if r.returncode == 0 else f"ERR:{r.stderr[:200]}"

def who(cmd, params=None):
    c = ["python3", WHO, "call", cmd]
    if params:
        for k,v in params.items(): c.extend(["--param", f"{k}={v}"])
    r = subprocess.run(c, capture_output=True, text=True, timeout=60, cwd=os.path.dirname(WHO))
    return r.stdout.strip() if r.returncode == 0 else f"ERR:{r.stderr[:200]}"

def save(fn, content):
    with open(os.path.join(ART, fn), "w") as f: f.write(content)
    print(f"  Saved {fn} ({len(content)} chars)")

tokens = 0

# STEP 4-8: Literature Review
print("STEPS 4-8: Literature Review")
r, t = call_ds("你是Researcher Agent，模拟气候-健康领域系统文献综述。",
"""完成步骤4-8:
Step4: 列出10篇关键文献(标题/作者/年份/核心发现)
Step5: 提取核心发现按主题分类
Step6: 识别3个研究空白
Step7: 汇总综述+3个核心研究问题
Step8: 文献图谱表(文献|方法|数据源|结论|局限)""", 3500)
tokens += t
save("step04_08_literature.md", r)
lit = r

# STEP 9-13: Hypothesis Generation
print("STEPS 9-13: Hypothesis Generation")
r2, t2 = call_ds("你是Strategist Agent，基于文献生成假设。",
f"文献综述:\n{lit[:1500]}\n\n生成H1/H2/H3假设+验证框架+Critic审查意见(步骤9-13)", 2500)
tokens += t2
save("step09_13_hypothesis.md", r2)

# STEP 14: NOAA Temperature Data (REAL)
print("STEP 14: NOAA Temperature Data")
noaa_temp = noaa("get-data", {"datasetid":"GSOY","startdate":"2010-01-01","enddate":"2020-12-31",
    "locationid":"CITY:US390029","datatypeid":"TMAX,TMIN","units":"metric","limit":"100"})
save("step14_noaa_temp.json", noaa_temp)

# STEP 15: NOAA Precipitation + extra city
print("STEP 15: NOAA Precipitation Data")
noaa_prcp = noaa("get-data", {"datasetid":"GSOY","startdate":"2010-01-01","enddate":"2020-12-31",
    "locationid":"CITY:US390029","datatypeid":"PRCP","units":"metric","limit":"100"})
save("step15_noaa_prcp.json", noaa_prcp)

noaa_ny = noaa("get-data", {"datasetid":"GSOY","startdate":"2010-01-01","enddate":"2020-12-31",
    "locationid":"CITY:US360010","datatypeid":"TMAX,TMIN,PRCP","units":"metric","limit":"100"})
save("step15b_noaa_newyork.json", noaa_ny)

# STEP 16: WHO Health Data (REAL)
print("STEP 16: WHO Health Data")
who_resp = who("search-indicators", {"query":"respiratory","top":"15"})
save("step16a_who_resp_search.json", who_resp)

who_mort = who("search-indicators", {"query":"mortality","top":"15"})
save("step16b_who_mortality_search.json", who_mort)

who_le = who("get-indicator-data", {"indicator_code":"WHOSIS_000002","time_from":"2010","time_to":"2020","top":"100"})
save("step16c_who_life_expectancy.json", who_le)

# STEP 17: WHO Cardiovascular Data (REAL)
print("STEP 17: WHO Cardiovascular Data")
who_cv = who("search-indicators", {"query":"cardiovascular","top":"15"})
save("step17a_who_cv_search.json", who_cv)

who_ncd = who("get-indicator-data", {"indicator_code":"NCDMORT_000008","time_from":"2010","time_to":"2019","top":"100"})
save("step17b_who_ncd.json", who_ncd)

who_air = who("search-indicators", {"query":"air pollution","top":"10"})
save("step17c_who_airpollution.json", who_air)

print(f"\nBatch 2 complete. Tokens: {tokens}")
# Save data summaries for next batch
with open(os.path.join(ART, "_data_summary.txt"), "w") as f:
    f.write(f"NOAA_TEMP:\n{noaa_temp[:600]}\n\nNOAA_PRCP:\n{noaa_prcp[:600]}\n\nWHO_LE:\n{who_le[:600]}\n\nWHO_NCD:\n{who_ncd[:600]}\n\nLIT:\n{lit[:800]}\n\nHYPO:\n{r2[:800]}\n")
print("Data summary saved for next batch")
