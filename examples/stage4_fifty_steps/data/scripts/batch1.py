#!/usr/bin/env python3
"""Batch 1: Steps 1-3 (Coordinator + Strategist)"""
import requests, json, os, time

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
BASE = os.path.join(REPO_ROOT, "examples", "stage4_fifty_steps")
ART = os.path.join(BASE, "stage4_artifacts")

def call_ds(sys_p, usr_p, max_t=3000):
    r = requests.post("https://api.deepseek.com/v1/chat/completions",
        headers={"Authorization":"Bearer sk-your-key-here","Content-Type":"application/json"},
        json={"model":"deepseek-chat","messages":[{"role":"system","content":sys_p},{"role":"user","content":usr_p}],"max_tokens":max_t,"temperature":0.7},
        timeout=120)
    d = r.json()
    tokens = d.get("usage",{}).get("total_tokens",0)
    return d["choices"][0]["message"]["content"], tokens

def save(fn, content):
    with open(os.path.join(ART, fn), "w") as f:
        f.write(content)
    print(f"  Saved {fn} ({len(content)} chars)")

total_tokens = 0

# STEP 1
print("STEP 1: Coordinator Task Decomposition")
r1, t1 = call_ds(
    "你是NexusFlow Coordinator Agent。接收科研任务并分解为结构化DAG。",
    """任务：基于NOAA气候数据+WHO健康数据，分析气候变化与公共健康关联。
分解为8阶段50步DAG，JSON格式输出每步的：编号、Agent角色、模块、输入、输出、依赖步骤。
10角色：Coordinator,Strategist,Researcher,Analyst,Coder,Critic,FusionJudge,Archivist,Reviewer,Observer""", 2500)
total_tokens += t1
save("step01_task_dag.json", r1)

# STEP 2
print("STEP 2: Coordinator DAG Routing")
r2, t2 = call_ds(
    "你是NexusFlow Coordinator Agent，负责拓扑切换与路由。",
    f"基于任务DAG:\n{r1[:1500]}\n\n输出：1)拓扑序列(Chain/Parallel/Tree/Debate) 2)切换点 3)Agent分配 4)上下文窗口配置(token预算)", 2000)
total_tokens += t2
save("step02_dag_routing.json", r2)

# STEP 3
print("STEP 3: Strategist Framework")
r3, t3 = call_ds(
    "你是NexusFlow Strategist Agent，设计研究策略和分析框架。",
    """主题：NOAA+WHO气候-健康关联分析。设计：
1. 3个假设(H1温度-呼吸疾病 H2降水-心血管滞后 H3区域异质性)
2. 变量体系(自变量/因变量/协变量)
3. 统计方法(相关/回归/DLNM/分层)
4. 分析路径图""", 2500)
total_tokens += t3
save("step03_framework.md", r3)

print(f"\nBatch 1 complete. Tokens: {total_tokens}")
