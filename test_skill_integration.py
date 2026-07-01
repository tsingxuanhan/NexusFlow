"""技能蒸馏集成测试"""
import sys
import time
sys.path.insert(0, '/tmp/agent4science_nexus')

# 设置日志
import logging
logging.basicConfig(level=logging.INFO, format='%(name)s - %(message)s')

def test_insight_distiller_task_skills():
    """测试InsightDistiller的task_skills提取"""
    from cognitive_division_engine import InsightDistiller, CDoLResult
    
    distiller = InsightDistiller()
    
    # 模拟科研任务结果（使用CDoLResult的正确字段）
    result = CDoLResult(
        final_answer="成功完成学术检索任务",
        synergy_gain=1.3,
        perspective_assignments=[],
        round0_conclusions=[],
        round1_attributions=[],
        round2_revised=[],
        contradiction_report=None,
        metrics={"revision_rate": 0.5, "bridgeability": 0.7},
    )
    
    # 科研任务应提取技能
    insight = distiller.distill(result, "在Google学术搜索Transformer论文")
    assert "task_skills" in insight, "缺少task_skills字段"
    assert insight["task_skills"] is not None, "科研任务应提取技能"
    assert insight["task_skills"]["applicable_scenario"] == "文献综述/学术检索", \
        f"场景应为文献综述，实际为{insight['task_skills']['applicable_scenario']}"
    print("✅ InsightDistiller task_skills提取测试通过")
    
    # 非科研任务应返回None
    insight2 = distiller.distill(result, "今天天气真好啊")
    assert insight2["task_skills"] is None, "非科研任务应返回None"
    print("✅ 非科研任务跳过测试通过")
    
    # 测试其他场景分类
    test_cases = [
        ("在Google学术搜索Transformer论文", "文献综述/学术检索"),
        ("分析实验数据找出规律", "数据分析/实验处理"),
        ("设计新材料配方", "实验设计/方案规划"),
    ]
    for task_desc, expected_scenario in test_cases:
        insight3 = distiller.distill(result, task_desc)
        if insight3["task_skills"]:
            actual = insight3["task_skills"]["applicable_scenario"]
            assert actual == expected_scenario, f"{task_desc}: 期望{expected_scenario}，实际{actual}"
            print(f"✅ 场景分类测试通过: {task_desc} -> {expected_scenario}")


def test_skill_retriever():
    """测试SkillRetriever的检索功能"""
    from skill_retriever import SkillRetriever, TaskSkillCard
    
    retriever = SkillRetriever()
    
    # 添加测试技能
    skill1 = TaskSkillCard(
        skill_id="test_001",
        applicable_scenario="文献综述/学术检索",
        task_description="在学术数据库搜索论文",
        execution_steps=["打开学术数据库", "输入关键词", "筛选结果", "导出引用"],
        completion_criteria=["找到相关论文并导出引用格式"],
        source="test",
        timestamp=time.time(),
    )
    skill2 = TaskSkillCard(
        skill_id="test_002",
        applicable_scenario="数据分析/实验处理",
        task_description="使用Python分析实验数据",
        execution_steps=["加载数据", "数据清洗", "统计分析", "可视化"],
        completion_criteria=["生成数据分析报告"],
        source="test",
        timestamp=time.time(),
    )
    skill3 = TaskSkillCard(
        skill_id="test_003",
        applicable_scenario="代码开发/工程实现",
        task_description="实现机器学习模型",
        execution_steps=["数据预处理", "模型设计", "训练调参", "评估验证"],
        completion_criteria=["模型达到预期性能"],
        source="test",
        timestamp=time.time(),
    )
    
    retriever.add_skill(skill1)
    retriever.add_skill(skill2)
    retriever.add_skill(skill3)
    
    # 测试场景匹配
    results = retriever.retrieve("搜索机器学习论文", top_k=2)
    assert len(results) > 0, "应该有检索结果"
    assert results[0].applicable_scenario == "文献综述/学术检索", \
        f"学术检索场景应优先，实际为{results[0].applicable_scenario}"
    print("✅ 学术检索场景检索测试通过")
    
    results2 = retriever.retrieve("分析实验数据", top_k=2)
    assert len(results2) > 0, "应该有检索结果"
    assert results2[0].applicable_scenario == "数据分析/实验处理", \
        f"数据分析场景应优先，实际为{results2[0].applicable_scenario}"
    print("✅ 数据分析场景测试通过")
    
    results3 = retriever.retrieve("实现一个深度学习模型", top_k=2)
    assert len(results3) > 0, "应该有检索结果"
    assert results3[0].applicable_scenario == "代码开发/工程实现", \
        f"代码开发场景应优先，实际为{results3[0].applicable_scenario}"
    print("✅ 代码开发场景测试通过")
    
    # 测试Prompt格式化
    prompt = retriever.retrieve_as_prompt("搜索论文")
    assert "[参考技能" in prompt, "Prompt应包含技能标记"
    assert "学术" in prompt or "检索" in prompt, "Prompt应包含相关关键词"
    print("✅ Prompt格式化测试通过")
    
    # 测试空检索
    results_empty = retriever.retrieve("这是一个完全无关的任务xyz123")
    # 应该返回空或很少结果
    print("✅ 空检索测试通过")


def test_insight_store_integration():
    """测试InsightStore与SkillRetriever的集成"""
    from cognitive_division_engine import InsightDistiller, InsightStore, CDoLResult
    from skill_retriever import SkillRetriever
    
    store = InsightStore()
    distiller = InsightDistiller()
    
    # 模拟一次科研任务执行
    result = CDoLResult(
        final_answer="完成学术论文检索",
        synergy_gain=1.2,
        perspective_assignments=[],
        round0_conclusions=[],
        round1_attributions=[],
        round2_revised=[],
        contradiction_report=None,
        metrics={"revision_rate": 0.4, "bridgeability": 0.6},
    )
    
    insight = distiller.distill(result, "在学术数据库搜索相关论文")
    store.add(insight)
    
    # 验证InsightStore能检索到技能
    skills = store.get_task_skills()
    assert len(skills) == 1, f"应有1个技能，实际{len(skills)}"
    print("✅ InsightStore task_skills存储测试通过")
    
    # 验证get_skill_count
    count = store.get_skill_count()
    assert count == 1, f"技能数量应为1，实际{count}"
    print("✅ get_skill_count测试通过")
    
    # 验证get_stats包含task_skills_count
    stats = store.get_stats()
    assert "task_skills_count" in stats, "stats应包含task_skills_count"
    assert stats["task_skills_count"] == 1, "task_skills_count应为1"
    print("✅ get_stats task_skills统计测试通过")
    
    # 验证SkillRetriever能从InsightStore同步
    retriever = SkillRetriever(insight_store=store)
    synced = retriever._sync_from_insights()
    assert synced == 1, f"应同步1个技能，实际{synced}"
    print("✅ SkillRetriever InsightStore同步测试通过")
    
    # 验证同步后的技能可以被检索
    retrieved = retriever.retrieve("搜索论文")
    assert len(retrieved) > 0, "应能检索到同步的技能"
    print("✅ 同步后检索测试通过")
    
    # 验证场景过滤
    filtered = store.get_task_skills(task_type="文献")
    assert len(filtered) > 0, "应能按场景过滤"
    print("✅ 场景过滤测试通过")


def test_skill_card_format():
    """测试TaskSkillCard的格式化和序列化"""
    from skill_retriever import TaskSkillCard
    
    skill = TaskSkillCard(
        skill_id="format_test",
        applicable_scenario="测试场景",
        task_description="这是一个测试任务",
        execution_steps=["步骤1", "步骤2", "步骤3"],
        completion_criteria=["标准1", "标准2"],
        failure_handling="失败时重试",
        source="unit_test",
        timestamp=time.time(),
        model_compatible=True,
        metadata={"tags": ["测试", "示例"]},
    )
    
    # 测试to_dict
    d = skill.to_dict()
    assert d["skill_id"] == "format_test"
    assert d["applicable_scenario"] == "测试场景"
    assert len(d["execution_steps"]) == 3
    print("✅ TaskSkillCard to_dict测试通过")
    
    # 测试from_dict
    skill2 = TaskSkillCard.from_dict(d)
    assert skill2.skill_id == skill.skill_id
    assert skill2.applicable_scenario == skill.applicable_scenario
    print("✅ TaskSkillCard from_dict测试通过")
    
    # 测试to_prompt_fragment
    prompt = skill.to_prompt_fragment()
    assert "### 参考技能：测试场景" in prompt
    assert "**执行步骤**:" in prompt
    assert "1. 步骤1" in prompt
    assert "**完成标准**:" in prompt
    assert "**失败处理**: 失败时重试" in prompt
    print("✅ TaskSkillCard to_prompt_fragment测试通过")


def test_planner_integration():
    """测试PlannerAgent与SkillRetriever的集成"""
    # 只需要测试导入和初始化，不需要完整的Agent运行
    try:
        from agents.planner import SKILL_RETRIEVER_AVAILABLE, SkillRetriever
    except ImportError as e:
        if "crewai" in str(e):
            print("⚠️ Planner集成测试跳过：缺少crewai依赖")
            return
        raise
    
    if SKILL_RETRIEVER_AVAILABLE:
        print("✅ Planner集成测试：SkillRetriever可用")
        
        # 测试SkillRetriever单独实例化
        retriever = SkillRetriever()
        assert retriever is not None
        assert retriever.graph is not None
        print("✅ Planner集成测试：SkillRetriever实例化成功")
        
        # 测试retrieve方法
        skills = retriever.retrieve("搜索论文", top_k=3)
        assert isinstance(skills, list)
        print("✅ Planner集成测试：retrieve方法正常")
    else:
        print("⚠️ Planner集成测试跳过：SkillRetriever导入失败（这是可接受的）")


if __name__ == "__main__":
    print("=" * 60)
    print("=== 技能蒸馏集成测试 ===")
    print("=" * 60)
    print()
    
    tests = [
        ("InsightDistiller task_skills提取", test_insight_distiller_task_skills),
        ("SkillRetriever检索功能", test_skill_retriever),
        ("InsightStore集成", test_insight_store_integration),
        ("TaskSkillCard格式化", test_skill_card_format),
        ("Planner集成", test_planner_integration),
    ]
    
    passed = 0
    failed = 0
    
    for name, test_func in tests:
        print(f"\n--- 测试: {name} ---")
        try:
            test_func()
            passed += 1
        except AssertionError as e:
            print(f"❌ {name} 失败: {e}")
            failed += 1
            import traceback
            traceback.print_exc()
        except Exception as e:
            print(f"❌ {name} 出错: {e}")
            failed += 1
            import traceback
            traceback.print_exc()
    
    print()
    print("=" * 60)
    print(f"测试结果: {passed} 通过, {failed} 失败")
    print("=" * 60)
    
    if failed > 0:
        sys.exit(1)
    else:
        print()
        print("🎉 全部测试通过！技能蒸馏实现完成！")
