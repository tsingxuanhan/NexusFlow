# -*- coding: utf-8 -*-
"""
E3: Skill 检索对比实验

用模拟的 skill 列表（15个技能），对比:
  - 纯规则匹配 (SkillRetriever 原生)
  - 规则 + Nemotron 语义 RRF 融合 (SkillRetriever.enable_semantic_search)

指标：Top-3 命中率

用法:
  python e3_skill_retrieval.py --api_key <NIM_API_KEY> [--model_name nvidia/nemotron-3-embed-1b]
"""

import argparse
import json
import os
import sys
import time
from typing import List, Dict

from bench_utils import (
    load_skill_tasks, ensure_results_dir, save_json, RESULTS_DIR, SEED
)


def create_mock_skills() -> List[Dict]:
    """创建 15 个模拟技能卡"""
    skills_data = [
        {
            "skill_id": "skill_1",
            "applicable_scenario": "文献综述/学术检索",
            "task_description": "检索和梳理混凝土材料科学领域的学术文献，包括纳米材料、矿物掺合料等研究方向",
            "execution_steps": ["使用关键词在学术数据库检索", "按引用数和发表年份筛选", "提取研究主题和方法"],
            "completion_criteria": ["覆盖近5年核心文献", "包含中英文文献"],
            "metadata": {"tags": ["文献", "论文", "学术", "检索", "混凝土", "材料"]},
            "timestamp": time.time(),
        },
        {
            "skill_id": "skill_2",
            "applicable_scenario": "数据分析/实验处理",
            "task_description": "处理混凝土强度测试数据，进行统计分析和可视化报告生成",
            "execution_steps": ["数据清洗和异常值检测", "描述性统计", "回归分析和假设检验", "生成图表和报告"],
            "completion_criteria": ["统计结果有显著性标注", "图表清晰可读"],
            "metadata": {"tags": ["数据", "分析", "统计", "报告", "强度", "测试"]},
            "timestamp": time.time(),
        },
        {
            "skill_id": "skill_3",
            "applicable_scenario": "实验设计/方案规划",
            "task_description": "设计混凝土配合比实验方案，包括材料选择、配比计算和性能测试计划",
            "execution_steps": ["确定目标性能指标", "选择原材料和掺合料", "计算配合比", "设计测试时间节点"],
            "completion_criteria": ["配合比计算完整", "测试计划覆盖关键龄期"],
            "metadata": {"tags": ["设计", "方案", "配方", "材料", "实验", "配合比"]},
            "timestamp": time.time(),
        },
        {
            "skill_id": "skill_4",
            "applicable_scenario": "代码开发/工程实现",
            "task_description": "编写混凝土工程相关的Python代码，包括数据处理、模型训练和数值模拟",
            "execution_steps": ["需求分析和接口设计", "编写核心算法", "单元测试", "性能优化"],
            "completion_criteria": ["代码通过测试", "文档完整"],
            "metadata": {"tags": ["代码", "编程", "python", "开发", "实现", "模拟"]},
            "timestamp": time.time(),
        },
        {
            "skill_id": "skill_5",
            "applicable_scenario": "实验设计/方案规划",
            "task_description": "规划混凝土耐久性野外暴露实验方案，包括环境监测和数据采集计划",
            "execution_steps": ["选择暴露场地", "设计试件组和对照组", "安装监测传感器", "制定采集周期"],
            "completion_criteria": ["场地选择合理", "监测频率满足规范"],
            "metadata": {"tags": ["实验", "方案", "耐久性", "野外", "暴露", "监测"]},
            "timestamp": time.time(),
        },
        {
            "skill_id": "skill_6",
            "applicable_scenario": "代码开发/工程实现",
            "task_description": "实现混凝土结构检测的深度学习模型，包括CNN裂缝检测和缺陷识别",
            "execution_steps": ["准备标注数据集", "选择和训练模型", "模型评估和调优", "部署推理服务"],
            "completion_criteria": ["模型准确率>90%", "推理延迟<1秒"],
            "metadata": {"tags": ["深度学习", "cnn", "裂缝检测", "代码", "模型", "训练"]},
            "timestamp": time.time(),
        },
        {
            "skill_id": "skill_7",
            "applicable_scenario": "信息检索/知识查询",
            "task_description": "查找混凝土工程相关技术标准和规范条文，包括国标、行标和地方标准",
            "execution_steps": ["确定标准类别", "检索标准数据库", "提取相关条文", "对比不同标准要求"],
            "completion_criteria": ["覆盖主要标准", "条文引用准确"],
            "metadata": {"tags": ["查询", "标准", "规范", "知识", "信息", "文档"]},
            "timestamp": time.time(),
        },
        {
            "skill_id": "skill_8",
            "applicable_scenario": "信息检索/知识查询",
            "task_description": "检索混凝土外加剂的最新产品信息和供应商资料",
            "execution_steps": ["收集供应商目录", "对比产品参数", "整理技术数据表"],
            "completion_criteria": ["覆盖主流供应商", "参数对比完整"],
            "metadata": {"tags": ["查询", "信息", "外加剂", "产品", "供应商"]},
            "timestamp": time.time(),
        },
        {
            "skill_id": "skill_9",
            "applicable_scenario": "数据分析/实验处理",
            "task_description": "处理混凝土耐久性加速试验数据，计算氯离子扩散系数和寿命预测",
            "execution_steps": ["导入试验数据", "拟合扩散模型", "计算扩散系数", "预测服役寿命"],
            "completion_criteria": ["拟合R²>0.95", "预测结果有置信区间"],
            "metadata": {"tags": ["数据", "分析", "氯离子", "扩散", "寿命", "预测"]},
            "timestamp": time.time(),
        },
        {
            "skill_id": "skill_10",
            "applicable_scenario": "数据分析/实验处理",
            "task_description": "进行混凝土工程项目的成本效益分析，包括材料成本、施工成本和维护成本",
            "execution_steps": ["收集成本数据", "建立成本模型", "计算全生命周期成本", "敏感性分析"],
            "completion_criteria": ["成本模型合理", "敏感性分析覆盖关键变量"],
            "metadata": {"tags": ["数据", "分析", "成本", "效益", "经济", "报告"]},
            "timestamp": time.time(),
        },
        {
            "skill_id": "skill_11",
            "applicable_scenario": "文献综述/学术检索",
            "task_description": "检索混凝土无损检测技术的最新研究进展，包括声发射、超声波和雷达检测",
            "execution_steps": ["搜索关键词组合", "筛选高质量文献", "分类整理检测方法"],
            "completion_criteria": ["覆盖主流检测技术", "包含近3年文献"],
            "metadata": {"tags": ["文献", "无损检测", "声发射", "超声波", "雷达", "检索"]},
            "timestamp": time.time(),
        },
        {
            "skill_id": "skill_12",
            "applicable_scenario": "代码开发/工程实现",
            "task_description": "开发混凝土配合比优化的优化算法程序，使用遗传算法或粒子群优化",
            "execution_steps": ["定义目标函数", "设置约束条件", "选择优化算法", "参数调优"],
            "completion_criteria": ["算法收敛", "优化结果优于经验配比"],
            "metadata": {"tags": ["代码", "优化", "算法", "遗传算法", "配合比", "开发"]},
            "timestamp": time.time(),
        },
        {
            "skill_id": "skill_13",
            "applicable_scenario": "实验设计/方案规划",
            "task_description": "设计纤维增强混凝土的力学性能测试方案，包括弯曲韧性测试和冲击试验",
            "execution_steps": ["选择测试标准", "设计试件尺寸", "确定加载方案", "规划数据采集"],
            "completion_criteria": ["测试方案符合标准", "数据采集完整"],
            "metadata": {"tags": ["设计", "方案", "纤维", "韧性", "冲击", "测试"]},
            "timestamp": time.time(),
        },
        {
            "skill_id": "skill_14",
            "applicable_scenario": "信息检索/知识查询",
            "task_description": "查找混凝土3D打印技术的专利信息和工程案例",
            "execution_steps": ["检索专利数据库", "收集工程案例", "整理技术参数对比"],
            "completion_criteria": ["专利覆盖核心方向", "案例有详细参数"],
            "metadata": {"tags": ["查询", "专利", "3d打印", "案例", "信息"]},
            "timestamp": time.time(),
        },
        {
            "skill_id": "skill_15",
            "applicable_scenario": "数据分析/实验处理",
            "task_description": "分析混凝土微观结构图像（SEM/XRD），提取孔隙率和水化产物特征",
            "execution_steps": ["图像预处理", "特征提取", "定量分析", "结果可视化"],
            "completion_criteria": ["孔隙率统计准确", "水化产物识别正确"],
            "metadata": {"tags": ["数据", "分析", "sem", "xrd", "微观结构", "图像"]},
            "timestamp": time.time(),
        },
    ]
    return skills_data


def run_e3(api_key: str, model_name: str = "nvidia/nemotron-3-embed-1b") -> Dict:
    print("=" * 70)
    print("E3: Skill 检索对比实验")
    print("=" * 70)

    from nexusflow.core.skill_retriever import SkillRetriever, SkillGraph, TaskSkillCard

    # ---------- 1. 创建技能图 ----------
    print("[1/4] 创建模拟技能库 (15个技能)...")
    skills_data = create_mock_skills()
    graph = SkillGraph()
    for sd in skills_data:
        skill = TaskSkillCard.from_dict(sd)
        graph.add_skill(skill)
    print(f"  技能数: {graph.stats()['total_skills']}")

    # ---------- 2. 加载测试任务 ----------
    tasks = load_skill_tasks()
    print(f"  测试任务数: {len(tasks)}")

    # ---------- 3. 纯规则匹配 ----------
    print("\n[2/4] 纯规则匹配 (SkillRetriever 原生)...")
    retriever_rule = SkillRetriever(skill_graph=graph)

    rule_hits = 0
    rule_per_task = []
    for task in tasks:
        retrieved = retriever_rule.retrieve(task["task"], top_k=3)
        retrieved_ids = [s.skill_id for s in retrieved]
        expected = set(task["expected_skill_ids"])
        hit = bool(expected & set(retrieved_ids))
        rule_per_task.append({
            "task": task["task"],
            "expected": task["expected_skill_ids"],
            "retrieved": retrieved_ids,
            "hit": hit,
        })
        if hit:
            rule_hits += 1

    rule_hit_rate = rule_hits / len(tasks)
    print(f"  Top-3 命中率: {rule_hits}/{len(tasks)} = {rule_hit_rate:.4f}")

    # ---------- 4. 规则 + Nemotron 语义 RRF 融合 ----------
    print("\n[3/4] 规则 + Nemotron 语义 RRF 融合...")
    from bench_utils import create_nemotron_provider, RateLimiter
    provider = create_nemotron_provider(api_key=api_key, model_name=model_name)

    # 重新创建 graph 和 retriever（因为前一个 retriever 可能已经修改了 graph）
    graph2 = SkillGraph()
    for sd in skills_data:
        skill = TaskSkillCard.from_dict(sd)
        graph2.add_skill(skill)

    retriever_semantic = SkillRetriever(skill_graph=graph2)
    rate_limiter = RateLimiter(rpm=40)

    # 启用语义搜索（会预编码所有 skill 的 embedding）
    print("  预编码技能向量...")
    retriever_semantic.enable_semantic_search(provider)
    print(f"  已编码技能数: {len(retriever_semantic._skill_embeddings)}")

    semantic_hits = 0
    semantic_per_task = []
    for i, task in enumerate(tasks):
        rate_limiter.wait()
        retrieved = retriever_semantic.retrieve(task["task"], top_k=3)
        retrieved_ids = [s.skill_id for s in retrieved]
        expected = set(task["expected_skill_ids"])
        hit = bool(expected & set(retrieved_ids))
        semantic_per_task.append({
            "task": task["task"],
            "expected": task["expected_skill_ids"],
            "retrieved": retrieved_ids,
            "hit": hit,
        })
        if hit:
            semantic_hits += 1
        if (i + 1) % 5 == 0:
            print(f"  进度: {i+1}/{len(tasks)}")

    semantic_hit_rate = semantic_hits / len(tasks)
    print(f"  Top-3 命中率: {semantic_hits}/{len(tasks)} = {semantic_hit_rate:.4f}")

    # ---------- 5. 对比分析 ----------
    print("\n[4/4] 对比分析...")

    # 分析差异
    diff_tasks = []
    for i, task in enumerate(tasks):
        rule_hit = rule_per_task[i]["hit"]
        sem_hit = semantic_per_task[i]["hit"]
        if rule_hit != sem_hit:
            diff_tasks.append({
                "task": task["task"],
                "rule_hit": rule_hit,
                "semantic_hit": sem_hit,
                "rule_retrieved": rule_per_task[i]["retrieved"],
                "semantic_retrieved": semantic_per_task[i]["retrieved"],
                "expected": task["expected_skill_ids"],
            })

    results = {
        "rule_only": {
            "top3_hit_rate": round(rule_hit_rate, 4),
            "hits": rule_hits,
            "total": len(tasks),
        },
        "rule_plus_semantic": {
            "top3_hit_rate": round(semantic_hit_rate, 4),
            "hits": semantic_hits,
            "total": len(tasks),
        },
        "improvement": {
            "absolute": round(semantic_hit_rate - rule_hit_rate, 4),
            "relative": round((semantic_hit_rate - rule_hit_rate) / rule_hit_rate * 100, 2) if rule_hit_rate > 0 else 0,
        },
        "per_task_rule": rule_per_task,
        "per_task_semantic": semantic_per_task,
        "differential_tasks": diff_tasks,
    }

    # 保存结果
    ensure_results_dir()
    output_path = os.path.join(RESULTS_DIR, "e3_skill_retrieval.json")
    save_json(output_path, results)
    print(f"\n结果已保存: {output_path}")

    # 汇总
    print("\n" + "=" * 70)
    print("E3 汇总")
    print("=" * 70)
    print(f"  纯规则匹配 Top-3 命中率:      {rule_hit_rate:.4f} ({rule_hits}/{len(tasks)})")
    print(f"  规则+Nemotron语义 Top-3 命中率: {semantic_hit_rate:.4f} ({semantic_hits}/{len(tasks)})")
    print(f"  绝对提升: {results['improvement']['absolute']:+.4f}")
    print(f"  相对提升: {results['improvement']['relative']:+.2f}%")
    print(f"  差异任务数: {len(diff_tasks)}")

    if diff_tasks:
        print("\n  差异任务详情:")
        for dt in diff_tasks:
            flag = "↑" if dt["semantic_hit"] and not dt["rule_hit"] else "↓"
            print(f"    {flag} {dt['task'][:50]}...")
            print(f"      规则: {dt['rule_retrieved']}  语义: {dt['semantic_retrieved']}  期望: {dt['expected']}")

    return results


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="E3: Skill 检索对比实验")
    parser.add_argument("--api_key", required=True, help="NIM API Key")
    parser.add_argument("--model_name", default="nvidia/nemotron-3-embed-1b", help="Nemotron 模型ID")
    args = parser.parse_args()

    run_e3(api_key=args.api_key, model_name=args.model_name)
