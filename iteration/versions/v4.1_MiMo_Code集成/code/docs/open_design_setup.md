# Open Design Daemon 本机部署指南

> xuanshu-agents v4.0 × Open Design Phase 1 配套文档

## 前置条件

| 依赖 | 最低版本 | 检查命令 |
|------|---------|---------|
| Node.js | 22+ | `node --version` |
| pnpm | 9+ | `pnpm --version` |
| Git | 2.x | `git --version` |
| Ollama | 运行中 | `ollama list` |

## 方案A：Electron桌面安装（推荐）

最简单，无需编译，直接下载：

1. 访问 [Open Design Releases](https://github.com/nexu-io/open-design/releases)
2. 下载 Windows x64 安装包（unsigned）
3. 安装后启动，Daemon 自动在 `localhost:7456` 运行
4. Web UI 自动打开

## 方案B：源码安装

```powershell
# 1. clone仓库（推荐浅克隆节省空间）
git clone --depth 1 https://github.com/nexu-io/open-design.git D:\AI\open-design

# 2. 安装pnpm（如果没有）
npm install -g pnpm

# 3. 安装依赖
cd D:\AI\open-design
pnpm install

# 4. 启动Daemon + Web UI
pnpm tools-dev run web
```

Daemon 默认端口：7456  
Web UI 默认端口：3000

## 方案C：Docker（如果你装了Docker Desktop）

```powershell
docker run -d \
  --name open-design \
  -p 7456:7456 \
  -p 3000:3000 \
  -e BYOK_BASE_URL=http://host.docker.internal:11434/v1 \
  -e BYOK_API_KEY=local \
  -e BYOK_MODEL=qwen3.5:9b \
  -e BYOK_PROVIDER=ollama \
  nexuio/open-design:latest
```

## BYOK配置（Ollama本地模型）

Daemon启动后，在Web UI的 **Settings → BYOK** 页面配置：

| 字段 | 值 |
|------|---|
| Protocol | Ollama |
| Base URL | `http://localhost:11434/v1` |
| Model | `qwen3.5:9b`（快速原型）或 `qwen3-coder:30b`（精修） |

## 验证Daemon运行

```powershell
# 检查Daemon健康
curl http://localhost:7456/api/health

# 检查MCP Server
npx -y open-design-mcp@0.16.1
```

## 运行xuanshu-agents连通性测试

```powershell
cd D:\xuan-hub\xuanshu-agents
python scripts/test_od_mcp.py
```

预期结果：6/6 PASS

## MCP配置文件位置

`xuanshu-agents/config/open_design_mcp.json`

默认配置使用DeepSeek API作为BYOK后端。如需切换到本地Ollama：

```json
{
  "mcpServers": {
    "open-design": {
      "command": "npx",
      "args": ["-y", "open-design-mcp@0.16.1"],
      "env": {
        "OD_DAEMON_URL": "http://localhost:7456",
        "BYOK_BASE_URL": "http://localhost:11434/v1",
        "BYOK_API_KEY": "local",
        "BYOK_MODEL": "qwen3.5:9b",
        "BYOK_PROVIDER": "ollama"
      }
    }
  }
}
```

## 质量建议

| 场景 | 模型 | 质量 |
|------|------|------|
| 快速原型迭代 | qwen3.5:9b | ★★☆ |
| 常规设计 | qwen3-coder:30b | ★★★☆ |
| 精修/品牌级 | DeepSeek V4 (API) | ★★★★ |
| 演示文稿 | qwen3-coder:30b | ★★★ |

**关键**：Ollama 32B以下模型做精细设计一般，快速迭代用本地、精修切DeepSeek API。

## VRAM/RAM开销

| 组件 | RAM | VRAM |
|------|-----|------|
| OD Daemon | ~100-200MB | 0 |
| OD Web UI | ~150-300MB | 0 |
| Ollama模型 | ~200MB | 4-18GB（已有） |
| **新增总计** | **~250-500MB** | **0** |

在32GB RAM + 16GB VRAM环境下完全可行。OD不额外占VRAM。

## 常见问题

**Q: better-sqlite3编译失败**  
A: 用方案A的Electron安装包，不用源码编译。如果必须源码装，确保Node 22+和python3在PATH中。

**Q: Daemon启动后7456端口没响应**  
A: 检查防火墙是否放行。Windows可能需要手动允许。

**Q: Ollama请求超时**  
A: 确保Ollama在运行且模型已下载。`ollama pull qwen3.5:9b`

**Q: 设计质量太差**  
A: 切换BYOK到DeepSeek API或更大的Ollama模型。
