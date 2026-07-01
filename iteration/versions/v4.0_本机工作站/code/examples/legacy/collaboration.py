# -*- coding: utf-8 -*-
"""
铉枢·炉守 协作工作流示例
XuanHub Collaboration Workflow Examples

展示如何通过A2A网络让4个Agent协作完成任务。

示例包括:
- 端到端文献挖掘流水线
- A2A咨询示例
- Handoff桥接示例
"""

from typing import Dict, List, Any, Optional
import logging

logger = logging.getLogger("Collaboration")

# 延迟导入，避免循环依赖
_agents_imported = False
_orchestrator_imported = False

try:
    from agents import create_team, a2a_network, MinerAgent, AssayerAgent, CasterAgent, ArtisanAgent
    _agents_imported = True
except ImportError as e:
    logger.warning(f"无法导入agents: {e}")

try:
    from orchestrator import TaskOrchestrator, ExecutionMode
    _orchestrator_imported = True
except ImportError as e:
    logger.warning(f"无法导入orchestrator: {e}")


def literature_mining_pipeline(keywords: str, max_results: int = 5):
    """
    文献挖掘+验证流水线
    
    流程: Miner搜索论文 -> Assayer验证 -> 输出结果
    
    Args:
        keywords: 搜索关键词
        max_results: 最大论文数量
        
    Returns:
        (orchestrator, team) 元组
    """
    if not _agents_imported:
        raise ImportError("agents模块不可用")
    
    # 创建团队
    team = create_team()
    
    if not _orchestrator_imported:
        # 简化模式：直接调用
        return None, team
    
    # 创建编排器
    orchestrator = TaskOrchestrator("lit_mining")
    
    # 添加任务
    orchestrator.add_task(
        name="search",
        func=team["miner"].search_papers,
        params={"keywords": keywords, "max_results": max_results}
    )
    
    # 验证任务依赖于搜索
    orchestrator.add_task(
        name="verify",
        func=team["assayer"].verify_entry,
        params={"entry": "placeholder"},  # 后续会被替换
        depends_on=["search"]
    )
    
    return orchestrator, team


def code_generation_pipeline(requirement: str, language: str = "python"):
    """
    代码生成+审查流水线
    
    流程: Artisan确认需求 -> Caster生成代码 -> Caster审查代码
    
    Args:
        requirement: 功能需求
        language: 编程语言
        
    Returns:
        (orchestrator, team) 元组
    """
    if not _agents_imported:
        raise ImportError("agents模块不可用")
    
    team = create_team()
    
    if not _orchestrator_imported:
        return None, team
    
    orchestrator = TaskOrchestrator("code_gen")
    
    orchestrator.add_task(
        name="generate",
        func=team["caster"].generate_code,
        params={"requirement": requirement, "language": language}
    )
    
    orchestrator.add_task(
        name="review",
        func=team["caster"].review_code,
        params={"code": "placeholder", "language": language},
        depends_on=["generate"]
    )
    
    return orchestrator, team


def full_research_pipeline(keywords: str):
    """
    完整研究流水线
    
    流程:
    1. Miner挖掘文献
    2. Assayer验证关键发现
    3. Artisan解释专业概念
    4. Caster生成分析代码
    
    Args:
        keywords: 研究关键词
        
    Returns:
        流水线结果字典
    """
    if not _agents_imported:
        raise ImportError("agents模块不可用")
    
    team = create_team()
    results = {}
    
    # 步骤1: 文献挖掘
    logger.info("[Pipeline] 步骤1: 文献挖掘")
    papers = team["miner"].search_papers(keywords, max_results=3)
    results["papers"] = papers
    
    # 步骤2: 验证关键发现 (如果找到论文)
    if papers and "未找到" not in papers:
        logger.info("[Pipeline] 步骤2: 验证发现")
        # 提取前200字符作为验证内容
        verify_content = papers[:500]
        results["verification"] = team["assayer"].verify_entry(verify_content)
    else:
        results["verification"] = "无内容可验证"
    
    # 步骤3: 解释专业概念
    logger.info("[Pipeline] 步骤3: 专业问答")
    results["concept"] = team["artisan"].explain_concept(keywords)
    
    # 步骤4: 生成分析代码
    logger.info("[Pipeline] 步骤4: 生成分析代码")
    results["code"] = team["caster"].generate_code(
        f"分析{keywords}相关数据的Python脚本"
    )
    
    return results


def a2a_consult_example():
    """
    A2A咨询示例
    
    展示如何通过A2A网络查询Agent能力
    
    Returns:
        网络状态字典
    """
    if not _agents_imported:
        return {"error": "agents模块不可用"}
    
    team = create_team()
    status = a2a_network.get_network_status()
    
    return status


def a2a_task_request_example():
    """
    A2A任务请求示例
    
    展示如何直接通过A2A协议向其他Agent发送任务请求
    
    Returns:
        任务结果
    """
    if not _agents_imported:
        return {"error": "agents模块不可用"}
    
    team = create_team()
    
    # 通过Miner向Assayer发送验证请求
    msg = team["miner"].a2a.create_task_request(
        receiver_id="assayer",
        action="verify_entry",
        parameters={
            "entry": "超硫铁矿渣水泥(SSC)的主要成分是高炉矿渣",
            "entry_id": "test_001"
        }
    )
    
    response = a2a_network.send_message(msg)
    
    if response:
        return {
            "success": True,
            "task_id": msg.task_id,
            "response": response.content,
            "status": response.status.value if response.status else None
        }
    else:
        return {
            "success": False,
            "error": "未获得响应"
        }


def handoff_bridge_example():
    """
    Handoff桥接到A2A示例
    
    展示当Handoff找不到时，如何通过A2A网络查找能力
    
    Returns:
        桥接结果
    """
    if not _agents_imported:
        return {"error": "agents模块不可用"}
    
    team = create_team()
    
    # 尝试通过handoff_to使用A2A桥接
    # 注意：这需要A2A网络中已有对应能力注册
    result = team["miner"].handoff_to(
        target="verify_entry",  # Assayer的能力
        request="验证SSC的主要成分"
    )
    
    return {
        "success": result.success,
        "target_agent_name": result.target_agent_name,
        "result": result.result,
        "error": result.error,
        "metadata": result.metadata
    }


def get_network_topology():
    """
    获取网络拓扑
    
    返回所有注册的Agent及其能力
    
    Returns:
        网络拓扑信息
    """
    if not _agents_imported:
        return {"error": "agents模块不可用"}
    
    team = create_team()
    status = a2a_network.get_network_status()
    
    topology = {
        "total_agents": status["registered_agents"],
        "agents": []
    }
    
    for agent_info in status["agents"]:
        agent_id = agent_info["id"]
        agent_protocol = a2a_network.get_agent(agent_id)
        
        capabilities = []
        if agent_protocol:
            for cap in agent_protocol.get_capabilities():
                capabilities.append({
                    "name": cap.name,
                    "description": cap.description,
                    "keywords": cap.keywords
                })
        
        topology["agents"].append({
            "id": agent_id,
            "name": agent_info["name"],
            "role": agent_info["role"],
            "capabilities": capabilities
        })
    
    return topology


# 示例用法
if __name__ == "__main__":
    import json
    
    print("=" * 60)
    print("铉枢·炉守 协作工作流示例")
    print("=" * 60)
    
    # 示例1: A2A咨询
    print("\n[示例1] A2A网络状态:")
    status = a2a_consult_example()
    if "error" not in status:
        print(f"  注册Agent数量: {status['registered_agents']}")
        for agent in status["agents"]:
            print(f"  - {agent['name']}: {agent['capabilities']}")
    else:
        print(f"  {status['error']}")
    
    # 示例2: 网络拓扑
    print("\n[示例2] 网络拓扑:")
    topo = get_network_topology()
    if "error" not in topo:
        print(f"  Agent总数: {topo['total_agents']}")
        for agent in topo["agents"]:
            print(f"  [{agent['role'].upper()}] {agent['name']}")
            for cap in agent["capabilities"]:
                print(f"    - {cap['name']}: {cap['description']}")
    else:
        print(f"  {topo['error']}")
    
    print("\n" + "=" * 60)
