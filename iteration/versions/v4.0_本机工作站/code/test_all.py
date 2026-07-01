# -*- coding: utf-8 -*-
"""
铉枢·炉守 Agent框架测试
XuanHub Agents Framework Test
"""

import sys
import os
from datetime import datetime

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from agents import MinerAgent, AssayerAgent, CasterAgent, ArtisanAgent


def print_separator(title: str):
    """打印分隔符"""
    print("\n" + "=" * 60)
    print(f"  {title}")
    print("=" * 60)


def test_miner():
    """测试矿工Agent"""
    print_separator("测试 矿工 (Miner) - 文献挖掘")
    
    try:
        agent = MinerAgent()
        print(f"✅ Agent初始化成功: {agent}")
        
        print("\n📋 测试任务: 搜索'nano SiO2 supersulfated cement'的最新研究")
        result = agent.search_papers("nano SiO2 supersulfated cement", max_results=3)
        
        print("\n📤 响应:")
        print(result[:2000] if len(result) > 2000 else result)
        
        stats = agent.get_stats()
        print(f"\n📊 统计: 请求{stats['total_requests']}次, 消耗{stats['total_tokens']}tokens")
        
        return True
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        return False


def test_assayer():
    """测试试金Agent"""
    print_separator("测试 试金 (Assayer) - 知识验证")
    
    try:
        agent = AssayerAgent()
        print(f"✅ Agent初始化成功: {agent}")
        
        test_entry = "SSC的主要成分是矿渣85%+石膏10%+水泥5%"
        print(f"\n📋 测试任务: 验证条目 - {test_entry}")
        
        result = agent.verify_entry(test_entry, "SSC-001")
        
        print("\n📤 响应:")
        print(result[:2000] if len(result) > 2000 else result)
        
        stats = agent.get_stats()
        print(f"\n📊 统计: 请求{stats['total_requests']}次, 消耗{stats['total_tokens']}tokens")
        
        return True
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        return False


def test_caster():
    """测试铸师Agent"""
    print_separator("测试 铸师 (Caster) - 代码生成")
    
    try:
        agent = CasterAgent()
        print(f"✅ Agent初始化成功: {agent}")
        
        print("\n📋 测试任务: 生成检测Ollama服务状态的Python脚本")
        
        requirement = """生成一个Python脚本，功能是检测Ollama服务是否正在运行。

要求：
1. 检查 http://127.0.0.1:11434/api/tags 端点
2. 如果服务正常，返回已加载的模型列表
3. 如果服务未运行，提示用户启动Ollama
4. 设置10秒超时
5. 包含中文提示信息"""
        
        result = agent.generate_code(requirement, language="python")
        
        print("\n📤 响应:")
        print(result[:2500] if len(result) > 2500 else result)
        
        stats = agent.get_stats()
        print(f"\n📊 统计: 请求{stats['total_requests']}次, 消耗{stats['total_tokens']}tokens")
        
        return True
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        return False


def test_artisan():
    """测试匠人Agent"""
    print_separator("测试 匠人 (Artisan) - 建材问答")
    
    try:
        agent = ArtisanAgent()
        print(f"✅ Agent初始化成功: {agent}")
        
        print("\n📋 测试任务: 解释LC3水泥中碳酸钙的作用")
        
        result = agent.explain_concept("LC3水泥中碳酸钙的作用", level="intermediate")
        
        print("\n📤 响应:")
        print(result[:2000] if len(result) > 2000 else result)
        
        stats = agent.get_stats()
        print(f"\n📊 统计: 请求{stats['total_requests']}次, 消耗{stats['total_tokens']}tokens")
        
        return True
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        return False


def main():
    """主测试流程"""
    print("\n" + "=" * 60)
    print("  铉枢·炉守 Agent框架测试")
    print(f"  测试时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)
    
    results = {}
    
    # 依次测试4个Agent
    print("\n🔄 准备测试4个Agent...")
    print("⚠️  注意: 每次测试都会调用DeepSeek API")
    
    # 1. 测试矿工
    results["Miner"] = test_miner()
    
    # 2. 测试试金
    results["Assayer"] = test_assayer()
    
    # 3. 测试铸师
    results["Caster"] = test_caster()
    
    # 4. 测试匠人
    results["Artisan"] = test_artisan()
    
    # 汇总结果
    print_separator("测试结果汇总")
    
    for name, success in results.items():
        status = "✅ 通过" if success else "❌ 失败"
        print(f"  {name}: {status}")
    
    passed = sum(results.values())
    total = len(results)
    
    print(f"\n总计: {passed}/{total} 通过")
    
    if passed == total:
        print("\n🎉 所有Agent测试通过！")
    else:
        print("\n⚠️  部分Agent测试失败，请检查错误信息")
    
    return passed == total


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
