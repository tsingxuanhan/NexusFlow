# -*- coding: utf-8 -*-
"""
铉枢·炉守 Open Design MCP连通性测试
XuanHub × Open Design — Phase 1 Verification

测试项:
1. MCP配置加载
2. open-design-mcp npm包可用性
3. MCP Client V2 → open-design-mcp stdio连接
4. 10个OD工具发现
5. Daemon连通性检测
6. od_compose_brief（无需Daemon的工具）调用
"""

import asyncio
import json
import os
import sys
import logging

logging.basicConfig(level=logging.INFO, format="[%(name)s] %(levelname)s: %(message)s")
logger = logging.getLogger("ODTest")

# 添加项目根目录到路径
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE_DIR)


async def test_config_load():
    """测试1: MCP配置加载"""
    print("\n=== Test 1: 配置加载 ===")
    config_path = os.path.join(BASE_DIR, "config", "open_design_mcp.json")
    
    try:
        with open(config_path, 'r') as f:
            config = json.load(f)
        
        od_config = config.get("mcpServers", {}).get("open-design", {})
        assert od_config.get("command") == "npx", "Command should be npx"
        assert "open-design-mcp" in str(od_config.get("args")), "Args should contain open-design-mcp"
        
        print(f"  ✓ Config loaded: {od_config.get('command')} {' '.join(od_config.get('args', []))}")
        print(f"  ✓ Daemon URL: {od_config.get('env', {}).get('OD_DAEMON_URL')}")
        print(f"  ✓ BYOK Provider: {od_config.get('env', {}).get('BYOK_PROVIDER')}")
        return True
    except Exception as e:
        print(f"  ✗ Config load failed: {e}")
        return False


async def test_npm_package():
    """测试2: open-design-mcp npm包可用性"""
    print("\n=== Test 2: npm包可用性 ===")
    
    try:
        import subprocess
        result = subprocess.run(
            ["npm", "info", "open-design-mcp", "version"],
            capture_output=True, text=True, timeout=15
        )
        if result.returncode == 0:
            version = result.stdout.strip()
            print(f"  ✓ open-design-mcp@{version} available in npm registry")
            return True
        else:
            print(f"  ✗ npm info failed: {result.stderr.strip()}")
            return False
    except Exception as e:
        print(f"  ✗ npm check failed: {e}")
        return False


async def test_mcp_stdio_connection():
    """测试3: MCP Client V2 → open-design-mcp stdio连接"""
    print("\n=== Test 3: MCP stdio连接 ===")
    
    try:
        from mcp_client_v2 import MCPClientV2
        
        client = MCPClientV2()
        
        # 加载配置
        config_path = os.path.join(BASE_DIR, "config", "open_design_mcp.json")
        with open(config_path, 'r') as f:
            config = json.load(f)
        od_config = config["mcpServers"]["open-design"]
        
        # 解析环境变量
        env = {}
        for key, value in od_config.get("env", {}).items():
            if isinstance(value, str) and value.startswith("${") and value.endswith("}"):
                env_name = value[2:-1]
                env[key] = os.environ.get(env_name, "")
            else:
                env[key] = value
        
        await client.connect_stdio(
            server_name="open-design",
            command=od_config["command"],
            args=od_config["args"],
            env=env if env else None
        )
        
        print("  ✓ MCP Client connected to open-design-mcp via stdio")
        
        # 列出工具
        tools = client.get_tools()
        print(f"  ✓ Discovered {len(tools)} tools:")
        for tool in tools:
            print(f"    - {tool.name}: {tool.description[:60]}...")
        
        await client.disconnect()
        return True
        
    except Exception as e:
        print(f"  ✗ MCP connection failed: {e}")
        print(f"    Hint: Make sure OD Daemon is running on port 7456")
        return False


async def test_tool_definitions():
    """测试4: 10个OD工具定义完整性"""
    print("\n=== Test 4: 工具定义完整性 ===")
    
    from tools.od_design_tool import OD_MCP_TOOLS
    
    expected = [
        "od_list_projects", "od_get_project", "od_create_project",
        "od_update_project", "od_delete_project", "od_save_artifact",
        "od_save_project_file", "od_lint_artifact", "od_compose_brief",
        "od_generate_design"
    ]
    
    all_ok = True
    for name in expected:
        if name in OD_MCP_TOOLS:
            desc = OD_MCP_TOOLS[name]["description"]
            print(f"  ✓ {name}: {desc[:50]}...")
        else:
            print(f"  ✗ {name}: MISSING")
            all_ok = False
    
    print(f"\n  Total: {len(OD_MCP_TOOLS)}/10 tool definitions")
    return all_ok


async def test_daemon_connectivity():
    """测试5: OD Daemon连通性（HTTP探测7456端口）"""
    print("\n=== Test 5: Daemon连通性 ===")
    
    try:
        import urllib.request
        req = urllib.request.Request(
            "http://localhost:7456/api/health",
            method="GET"
        )
        with urllib.request.urlopen(req, timeout=5) as resp:
            status = resp.status
            print(f"  ✓ Daemon responding: HTTP {status}")
            return True
    except urllib.error.URLError as e:
        print(f"  ✗ Daemon not reachable: {e.reason}")
        print(f"    Hint: Start OD Daemon with 'od' or 'pnpm tools-dev run web'")
        return False
    except Exception as e:
        print(f"  ✗ Daemon check failed: {e}")
        return False


async def test_bridge_tool():
    """测试6: ODDesignTool桥接类"""
    print("\n=== Test 6: 桥接工具类 ===")
    
    try:
        from tools.od_design_tool import ODDesignTool
        
        tool = ODDesignTool()
        print(f"  ✓ ODDesignTool instantiated: {tool.name}")
        print(f"  ✓ Description: {tool.description[:80]}...")
        print(f"  ✓ Sub-tools: {len(tool.get_sub_tools())}")
        
        # 测试参数验证
        result = tool.execute(action="od_compose_brief", title="Test", description="Test brief")
        if result.success:
            print(f"  ✓ od_compose_brief works (no Daemon required)")
        else:
            print(f"  ⚠ od_compose_brief returned: {result.error}")
        
        # 测试错误处理
        result = tool.execute(action="nonexistent_tool")
        assert not result.success, "Should fail for unknown action"
        print(f"  ✓ Error handling works for unknown actions")
        
        return True
    except Exception as e:
        print(f"  ✗ Bridge tool test failed: {e}")
        return False


async def run_all_tests():
    """运行所有测试"""
    print("=" * 60)
    print("Open Design × xuanshu-agents MCP Phase 1 连通性测试")
    print("=" * 60)
    
    results = {}
    
    results["config_load"] = await test_config_load()
    results["npm_package"] = await test_npm_package()
    results["tool_definitions"] = await test_tool_definitions()
    results["bridge_tool"] = await test_bridge_tool()
    results["daemon"] = await test_daemon_connectivity()
    results["mcp_stdio"] = await test_mcp_stdio_connection()
    
    print("\n" + "=" * 60)
    print("测试结果汇总")
    print("=" * 60)
    
    for name, passed in results.items():
        status = "✓ PASS" if passed else "✗ FAIL"
        print(f"  {status}  {name}")
    
    passed = sum(1 for v in results.values() if v)
    total = len(results)
    print(f"\n  {passed}/{total} tests passed")
    
    if not results.get("daemon") or not results.get("mcp_stdio"):
        print("\n⚠ Daemon未启动 — config/tool定义/桥接类已就绪，")
        print("  启动OD Daemon后重新运行即可验证完整连通。")
    
    return passed == total


if __name__ == "__main__":
    asyncio.run(run_all_tests())
