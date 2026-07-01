# 铉枢本地工作站 v4.0 全面升级 Prompt

## 背景

AI工作站上次部署约一个月前，模型和服务版本均已过时。xuanshu-agents框架已完成v4.0升级并推送到GitHub。现在需要：
1. 全面升级本地部署到2026年6月最新版本
2. 删除所有过时的模型和配置
3. 部署xuanshu-agents v4.0本地环境
4. 更新自愈脚本适配新架构
5. 全程遵守铁律

## 环境

- **系统**: Windows 11
- **GPU**: RTX 3080 Ti Laptop 16GB VRAM
- **CPU**: i9-12900H
- **RAM**: 32GB
- **用户名**: 铉瀚
- **AI工具箱**: 桌面\AI工具箱\
- **AI根目录**: D:\AI\
- **Ollama模型存储**: D:\AI\Models\Ollama
- **ComfyUI路径**: D:\AI\ComfyUI\
- **GitHub仓库**: https://github.com/tsingxuanhan/xuan-hub (private，需用户手动输入PAT)
- **自愈脚本**: D:\AI\shortcut_heal_v2.ps1
- **初始状态快照**: D:\AI\initial_state.json
- **白名单**: D:\AI\shortcut_whitelist.json

---

## 第一步：升级 Ollama 到 v0.30+

### 1.1 检查当前版本
```powershell
ollama --version
```
如果版本低于0.30.5，必须升级。

### 1.2 升级方式
去 https://ollama.com/download 下载最新Windows安装包，直接安装覆盖。

v0.30关键更新（据[Ollama Blog](https://ollama.com/blog/improved-performance-and-model-support-with-gguf)）：
- NVIDIA GPU性能提升约20%
- 支持GGUF直载
- Gemma 4 QAT权重支持（v0.30.6+）
- Vulkan加速支持

### 1.3 确认环境变量
```powershell
# 验证这些用户级环境变量仍然正确
foreach ($var in @("OLLAMA_MODELS","OLLAMA_GPU_OVERHEAD","OLLAMA_NUM_PARALLEL","OLLAMA_MAX_LOADED_MODELS","OLLAMA_KEEP_ALIVE")) {
    $val = [System.Environment]::GetEnvironmentVariable($var, "User")
    Write-Host "$var = $val"
}
```

预期值：
| 变量 | 值 |
|------|-----|
| OLLAMA_MODELS | D:\AI\Models\Ollama |
| OLLAMA_GPU_OVERHEAD | 2048 |
| OLLAMA_NUM_PARALLEL | 2 |
| OLLAMA_MAX_LOADED_MODELS | 2 |
| OLLAMA_KEEP_ALIVE | 5m |

缺失的补上（管理员PowerShell）：
```powershell
[System.Environment]::SetEnvironmentVariable("OLLAMA_MODELS", "D:\AI\Models\Ollama", "User")
[System.Environment]::SetEnvironmentVariable("OLLAMA_GPU_OVERHEAD", "2048", "User")
[System.Environment]::SetEnvironmentVariable("OLLAMA_NUM_PARALLEL", "2", "User")
[System.Environment]::SetEnvironmentVariable("OLLAMA_MAX_LOADED_MODELS", "2", "User")
[System.Environment]::SetEnvironmentVariable("OLLAMA_KEEP_ALIVE", "5m", "User")
```

### 1.4 重启Ollama
```powershell
taskkill /F /IM ollama.exe 2>$null
taskkill /F /IM ollama_app.exe 2>$null
Start-Sleep -Seconds 3
# 从开始菜单重新打开Ollama，或：
Start-Process "C:\Users\铉瀚\AppData\Local\Programs\Ollama\ollama app.exe"
```

---

## 第二步：清理过时模型

### 2.1 查看当前已安装模型
```powershell
ollama list
```

### 2.2 删除过时模型

以下模型已过时，逐一删除：

| 模型 | 删除原因 | 替代品 |
|------|---------|--------|
| qwen3:4b | 被Qwen3.5:4b取代 | qwen3.5:4b |
| qwen3:8b | 被Qwen3.5:9b取代 | qwen3.5:9b |
| deepseek-r1:8b | 本地推理不如Qwen3.5，云端用DeepSeek API | qwen3.5:9b |
| deepseek-r1:14b | 16GB卡跑14B太慢(5-8 tok/s)，体验差 | qwen3.5:9b |
| qwen3.6:27b | 16GB VRAM无法流畅运行27B模型 | qwen3.5:9b + 云端API |
| gemma3:12b | 被Gemma 4:12b取代 | gemma4:12b |

```powershell
# 逐一删除（模型存在才删，不存在跳过）
$oldModels = @("qwen3:4b", "qwen3:8b", "deepseek-r1:8b", "deepseek-r1:14b", "qwen3.6:27b", "gemma3:12b")
$currentModels = ollama list 2>&1
foreach ($m in $oldModels) {
    if ($currentModels -match [regex]::Escape($m)) {
        Write-Host "删除过时模型: $m"
        ollama rm $m
    } else {
        Write-Host "跳过(未安装): $m"
    }
}
```

### 2.3 保留的模型
| 模型 | 保留原因 |
|------|---------|
| nomic-embed-text:latest | 仍是最优轻量嵌入模型(0.3GB)，RAG用 |
| qwen3.5:9b | 主力推理，保留（如已安装则不重复拉取） |

---

## 第三步：拉取新模型

### 3.1 新模型配置表

| 模型 | Ollama Tag | 用途 | VRAM(Q4) | 状态 |
|------|-----------|------|----------|------|
| Qwen3.5 9B | qwen3.5:9b | 日常推理主力 | ~7GB | 保留或更新 |
| Qwen3.5 4B | qwen3.5:4b | 快速执行/轻量任务 | ~3.5GB | 新增 |
| Qwen3-Coder 30B-A3B | qwen3-coder:30b | 代码专用(MoE 3.3B活跃) | ~15.6GB | 新增 |
| Gemma 4 12B | gemma4:12b | 多模态(图+音+文) | ~10GB | 新增 |
| nomic-embed-text | nomic-embed-text | RAG嵌入 | ~0.3GB | 保留 |

### 3.2 拉取命令
```powershell
# 主力模型（如已有则跳过，ollama会自动检测）
ollama pull qwen3.5:9b
ollama pull qwen3.5:4b

# 代码模型 — MoE架构，30B总参但仅3.3B活跃，16GB卡可跑
ollama pull qwen3-coder:30b

# 多模态模型 — 2026年6月3日发布，原生视觉+音频
ollama pull gemma4:12b

# 嵌入模型（如已有则跳过）
ollama pull nomic-embed-text
```

### 3.3 VRAM三种运行模式（16GB硬约束）

| 模式 | 加载模型 | VRAM占用 | 适用场景 |
|------|---------|----------|---------|
| **日常模式** | qwen3.5:9b + qwen3.5:4b + nomic-embed-text | ~11GB | 对话+轻任务+RAG |
| **代码模式** | qwen3-coder:30b（独占） | ~15.6GB | 编程/Agent任务 |
| **多模态模式** | gemma4:12b（独占） | ~10GB | 看图/音频分析 |

**互斥规则（铁律）：**
- 日常模式和多模态模式可以切换（先stop再run）
- 代码模式独占，与任何其他大模型互斥
- ComfyUI与任何Ollama大模型互斥
- nomic-embed-text可与任何模式共存（仅0.3GB）

### 3.4 验证模型
```powershell
ollama list
# 确认输出包含：qwen3.5:9b, qwen3.5:4b, qwen3-coder:30b, gemma4:12b, nomic-embed-text

# 快速测试每个模型
ollama run qwen3.5:4b "你好，一句话介绍自己" --nowordwrap
ollama run qwen3.5:9b "你好，一句话介绍自己" --nowordwrap
ollama run qwen3-coder:30b "def hello(): pass" --nowordwrap
ollama run gemma4:12b "你好，一句话介绍自己" --nowordwrap
```

---

## 第四步：升级 Docker 服务

### 4.1 确认 Docker Desktop 运行
```powershell
docker info
```
如果报错，启动 Docker Desktop。

### 4.2 升级 Open WebUI
```powershell
# 停止旧容器
docker stop open-webui 2>$null
docker rm open-webui 2>$null

# 拉取最新镜像
docker pull ghcr.io/open-webui/open-webui:main

# 重新启动（使用host网络模式，端口8080）
docker run -d `
  --name open-webui `
  --restart unless-stopped `
  --network host `
  --add-host=host.docker.internal:host-gateway `
  -v openwebui_data:/app/backend/data `
  -e OLLAMA_BASE_URL=http://127.0.0.1:11434 `
  -e WEBUI_SECRET_KEY=ai-workstation-secret-key `
  ghcr.io/open-webui/open-webui:main
```

**注意：OLLAMA_BASE_URL使用 `http://127.0.0.1:11434`，不用 `http://localhost:11434`（铁律）。**

### 4.3 验证Open WebUI
```powershell
Start-Sleep -Seconds 15
try {
    $r = Invoke-WebRequest -Uri "http://127.0.0.1:8080" -TimeoutSec 10 -UseBasicParsing
    Write-Host "✅ Open WebUI可达 (状态码: $($r.StatusCode))"
} catch {
    Write-Host "❌ Open WebUI不可达"
}
```

### 4.4 Open WebUI模型配置

登录Open WebUI（http://127.0.0.1:8080），为每个模型设置描述和参数：

**qwen3.5:9b（日常推理主力）**
- 描述：日常对话/代码生成/Agent工作流主力
- 标签：agent, coding, tool-calling, daily
- 参数：temperature=0.7, top_p=0.9, num_ctx=32768, num_predict=8192

**qwen3.5:4b（快速执行）**
- 描述：轻量快速任务/40-50 tok/s高速推理
- 标签：fast, light, daily
- 参数：temperature=0.7, top_p=0.9, num_ctx=16384, num_predict=4096

**qwen3-coder:30b（代码专用）**
- 描述：Agent级代码生成/MoE 30B架构3.3B活跃/编程+调试+重构
- 标签：coding, agent, moe
- 参数：temperature=0.3, top_p=0.95, num_ctx=32768, num_predict=8192

**gemma4:12b（多模态）**
- 描述：原生视觉+音频+文本多模态/看图分析/文档理解
- 标签：multimodal, vision, audio
- 参数：temperature=0.7, top_p=0.9, num_ctx=16384, num_predict=4096

### 4.5 RAGFlow 处理

**评估是否保留RAGFlow：** RAGFlow完整栈（ES+MySQL+MinIO+Redis+RAGFlow）占用约8-10GB RAM，对32GB内存机器负担较大。如果用户不常用RAG功能，建议：
- 停止并移除RAGFlow相关容器
- xuanshu-agents v4.0自带RAG系统（multi_hop_rag.py + vector_memory.py），可替代
- 如用户确认保留，则更新docker-compose后重启

```powershell
# 如决定移除RAGFlow栈：
docker stop ragflow elasticsearch mysql minio redis 2>$null
docker rm ragflow elasticsearch mysql minio redis 2>$null
# 数据卷保留不删，万一以后要用
```

如果保留，更新docker-compose.yml中所有`localhost`为`127.0.0.1`后重新启动。

---

## 第五步：升级 ComfyUI

### 5.1 更新ComfyUI本体
```powershell
cd D:\AI\ComfyUI
.\venv\Scripts\activate
git pull 2>$null
pip install -r requirements.txt --upgrade
```

### 5.2 更新自定义节点
```powershell
cd D:\AI\ComfyUI\custom_nodes
Get-ChildItem -Directory | ForEach-Object {
    Push-Location $_.FullName
    if (Test-Path ".git") {
        Write-Host "更新: $($_.Name)"
        git pull 2>$null
    }
    Pop-Location
}
```

### 5.3 ComfyUI模型更新建议

| 模型类型 | 旧版(过时) | 新版推荐 | 存放路径 |
|----------|-----------|---------|---------|
| 图像生成 | SDXL 1.0 | FLUX.1-schnell (Q8量化) | models/checkpoints/ |
| 视频生成 | 无 | LTX-Video 2.3 | models/checkpoints/ |
| 3D生成 | 无 | TripoSplat (可选) | models/checkpoints/ |
| VAE | SDXL VAE | FLUX自带(无需额外VAE) | — |
| LoRA | 旧版SDXL LoRA | FLUX LoRA | models/loras/ |

**FLUX.1-schnell**下载（从 https://huggingface.co/black-forest-labs/FLUX.1-schnell 或 Civitai 下载GGUF/Q8量化版）：
- Q8量化版约 12GB，16GB VRAM可跑（需关闭Ollama）
- Q4量化版约 6GB，VRAM余量更大

### 5.4 验证ComfyUI
```powershell
cd D:\AI\ComfyUI
.\venv\Scripts\activate
# 先确认Ollama已停止
taskkill /F /IM ollama.exe 2>$null
# 启动ComfyUI
python main.py --force-fp16 --listen 127.0.0.1
```
访问 http://127.0.0.1:8188 确认正常，然后Ctrl+C关闭（回到Ollama模式）。

---

## 第六步：部署 xuanshu-agents v4.0

### 6.1 Clone仓库

**注意：xuan-hub是private仓库，需要GitHub PAT。请用户在终端输入PAT后执行clone。**

```powershell
# 如果 D:\xuan-hub 已存在，先备份再删除
if (Test-Path "D:\xuan-hub") {
    $backupDir = "D:\AI\backup\xuan-hub_$(Get-Date -Format 'yyyyMMdd_HHmmss')"
    Move-Item "D:\xuan-hub" $backupDir
    Write-Host "旧版已备份到: $backupDir"
}

# Clone（需要用户输入PAT）
$pat = Read-Host "请输入GitHub PAT"
git clone "https://${pat}@github.com/tsingxuanhan/xuan-hub.git" D:\xuan-hub

# 清除remote URL中的PAT
cd D:\xuan-hub
git remote set-url origin https://github.com/tsingxuanhan/xuan-hub.git
```

### 6.2 配置 config.py
```powershell
cd D:\xuan-hub\xuanshu-agents

# 从模板创建配置
Copy-Item config.example.py config.py
```

编辑 `config.py`，填入实际值：
```python
# 本地部署配置 — DeepSeek API + Ollama双后端

# DeepSeek API（云端推理后端）
DEEPSEEK_API_KEY = "sk-你的DeepSeek API Key"  # 用户手动填入
DEEPSEEK_BASE_URL = "https://api.deepseek.com/v1"
DEEPSEEK_PRO_MODEL = "deepseek-v4-pro"
DEEPSEEK_FLASH_MODEL = "deepseek-v4-flash"

# Ollama本地推理后端
OLLAMA_BASE_URL = "http://127.0.0.1:11434"
OLLAMA_DEFAULT_MODEL = "qwen3.5:9b"
OLLAMA_CODE_MODEL = "qwen3-coder:30b"
OLLAMA_FAST_MODEL = "qwen3.5:4b"
OLLAMA_MULTIMODAL_MODEL = "gemma4:12b"
OLLAMA_EMBED_MODEL = "nomic-embed-text"

# 模型选择策略
# heavy: DeepSeek PRO (云端)
# medium: DeepSeek Flash (云端) / Ollama qwen3.5:9b (本地)
# light: Ollama qwen3.5:4b (本地)
# code: Ollama qwen3-coder:30b (本地) / DeepSeek (云端)
# multimodal: Ollama gemma4:12b (本地)
```

### 6.3 安装Python依赖
```powershell
cd D:\xuan-hub\xuanshu-agents
pip install -r requirements.txt
```

v4.0主要依赖：
- fastapi, uvicorn (AgentOS服务)
- httpx (API调用)
- pydantic (数据验证)
- numpy (向量计算，替代chromadb/sentence-transformers)
- python-multipart, aiofiles (文件处理)

**注意：不要安装 chromadb 或 sentence-transformers，这些在本机环境(HuggingFace不通/内存有限)无法运行。v4.0使用NGramTFIDFProvider作为向量记忆后端，无需这些依赖。**

### 6.4 验证框架
```powershell
cd D:\xuan-hub\xuanshu-agents
python -c "
from agents import *
print('agents模块导入成功')
print(f'__all__包含 {len(__all__)} 个导出项')

# 测试BaseAgent创建
from agents import BaseAgent
agent = BaseAgent(name='test', role='tester')
print(f'BaseAgent创建成功: {agent.name}')

# 测试向量记忆
from agents import NGramTFIDFProvider
provider = NGramTFIDFProvider()
print('NGramTFIDFProvider创建成功')

print('✅ xuanshu-agents v4.0 本地部署验证通过')
"
```

---

## 第七步：更新自愈脚本

### 7.1 更新 initial_state.json 中的模型列表

读取 `D:\AI\initial_state.json`，将 `ollama_models` 字段更新为：

```json
"ollama_models": [
    "qwen3.5:9b",
    "qwen3.5:4b",
    "qwen3-coder:30b",
    "gemma4:12b",
    "nomic-embed-text:latest"
]
```

同时更新 `description` 为 `"AI工作站v4.0初始状态快照 - 自愈脚本恢复基准"`，版本号改为 `"4.0"`。

### 7.2 在自愈脚本中增加Ollama健康检查

在 `shortcut_heal_v2.ps1` 的主修复循环之后，路径检查之前，增加Ollama健康检查段落：

```powershell
# ===== Ollama 健康检查 =====
Write-Log "INFO" "开始Ollama健康检查"

# 1. 检查Ollama进程是否运行
$ollamaProcess = Get-Process -Name "ollama" -ErrorAction SilentlyContinue
if (-not $ollamaProcess) {
    Write-Log "WARN" "Ollama未运行，尝试启动"
    $ollamaApp = Get-ChildItem "$env:LOCALAPPDATA\Programs\Ollama" -Filter "ollama app.exe" -Recurse -Depth 1 -ErrorAction SilentlyContinue
    if ($ollamaApp) {
        Start-Process $ollamaApp[0].FullName
        Start-Sleep -Seconds 10
        Write-Log "INFO" "Ollama已启动"
    } else {
        Write-Log "ERROR" "Ollama未安装或路径变更，需手动处理"
    }
}

# 2. 检查Ollama版本
$ollamaVersion = ollama --version 2>&1
if ($ollamaVersion -match "0\.3[0-9]") {
    Write-Log "INFO" "Ollama版本正常: $ollamaVersion"
} else {
    Write-Log "WARN" "Ollama版本过低: $ollamaVersion，建议升级到0.30+"
}

# 3. 检查关键模型是否存在
$models = ollama list 2>&1
$requiredModels = @("qwen3.5:9b", "qwen3.5:4b", "qwen3-coder:30b", "gemma4:12b", "nomic-embed-text")
foreach ($m in $requiredModels) {
    if ($models -match [regex]::Escape($m)) {
        Write-Log "INFO" "模型存在: $m"
    } else {
        Write-Log "WARN" "模型缺失: $m，需手动 ollama pull $m"
    }
}

# 4. 检查环境变量
$expectedVars = @{
    "OLLAMA_MODELS" = "D:\AI\Models\Ollama"
    "OLLAMA_GPU_OVERHEAD" = "2048"
    "OLLAMA_NUM_PARALLEL" = "2"
    "OLLAMA_MAX_LOADED_MODELS" = "2"
    "OLLAMA_KEEP_ALIVE" = "5m"
}
foreach ($var in $expectedVars.Keys) {
    $actual = [System.Environment]::GetEnvironmentVariable($var, "User")
    if ($actual -eq $expectedVars[$var]) {
        Write-Log "INFO" "环境变量正确: $var = $actual"
    } else {
        Write-Log "WARN" "环境变量异常: $var 实际='$actual' 预期='$($expectedVars[$var])'"
    }
}
```

### 7.3 增加Docker服务健康检查

在Ollama检查之后增加：

```powershell
# ===== Docker服务健康检查 =====
Write-Log "INFO" "开始Docker服务健康检查"

$dockerInfo = docker info 2>&1
if ($dockerInfo -match "error") {
    Write-Log "WARN" "Docker Desktop未运行"
} else {
    Write-Log "INFO" "Docker Desktop运行正常"
    
    # 检查Open WebUI容器
    $webuiContainer = docker ps --filter "name=open-webui" --format "{{.Status}}" 2>$null
    if ($webuiContainer) {
        Write-Log "INFO" "Open WebUI运行中: $webuiContainer"
    } else {
        Write-Log "WARN" "Open WebUI未运行"
    }
}
```

### 7.4 增加xuanshu-agents路径检查

在路径检查段落中增加：

```powershell
# xuanshu-agents v4.0 路径检查
$xuanshuPaths = @{
    "D:\xuan-hub\" = "xuanshu-agents仓库"
    "D:\xuan-hub\xuanshu-agents\" = "框架核心"
    "D:\xuan-hub\xuanshu-agents\config.py" = "配置文件"
    "D:\xuan-hub\xuanshu-agents\agents\" = "Agent模块"
}
foreach ($path in $xuanshuPaths.Keys) {
    if (Test-Path $path) {
        Write-Log "INFO" "路径存在: $($xuanshuPaths[$path]) ($path)"
    } else {
        Write-Log "WARN" "路径缺失: $($xuanshuPaths[$path]) ($path)"
    }
}
```

### 7.5 更新快捷方式注册

更新 `D:\AI\shortcut_registry.json` 中的模型相关配置：

- "AI对话" 快捷方式的目标模型从 `qwen3.5:9b` 改为同时支持 `qwen3.5:9b` 和 `qwen3.5:4b` 双模型
- "模型切换" 快捷方式的脚本更新，支持4种模式切换（日常/代码/多模态/关闭）

新增一个快捷方式（第11个）：

| 序号 | 名称 | 互斥组 | 功能 |
|------|------|--------|------|
| 11 | Agent网关 | 无 | 启动xuanshu-agents AgentOS服务(:8000) |

对应的启动脚本（.bat）内容：

```bat
@echo off
chcp 936 >nul 2>&1
cd /d D:\xuan-hub\xuanshu-agents
python -m agents.agentos --host 127.0.0.1 --port 8000
pause
```

**注意：.bat文件必须GBK编码+CRLF换行。**

### 7.6 更新计划任务

```powershell
# 更新自愈脚本的计划任务（触发条件不变）
Unregister-ScheduledTask -TaskName "AI_Shortcut_Heal" -Confirm:$false -ErrorAction SilentlyContinue

$action = New-ScheduledTaskAction -Execute "powershell.exe" -Argument "-ExecutionPolicy Bypass -File `"D:\AI\shortcut_heal_v2.ps1`""
$trigger1 = New-ScheduledTaskTrigger -AtLogOn
$trigger2 = New-ScheduledTaskTrigger -Daily -At 8:00AM
$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable -ExecutionTimeLimit (New-TimeSpan -Minutes 5)
Register-ScheduledTask -TaskName "AI_Shortcut_Heal" -Action $action -Trigger $trigger1,$trigger2 -Settings $settings -Force -Description "AI工作站v4.0自愈（Ollama+Docker+xuanshu-agents健康检查+VPN免疫+白名单保护）"
```

### 7.7 重新锁定初始状态

所有更新完成后，重新执行初始状态锁定：

```powershell
# 采集当前完整快照并覆盖 D:\AI\initial_state.json
# 备份旧快照
Copy-Item "D:\AI\initial_state.json" "D:\AI\backup\initial_state_v3_$(Get-Date -Format 'yyyyMMdd_HHmmss').json" -ErrorAction SilentlyContinue

# 新快照的版本和描述更新
# version: "4.0"
# description: "AI工作站v4.0初始状态快照 - 自愈脚本恢复基准"
# ollama_models: 更新为新模型列表
# 新增 xuanshu_agents 路径检查项
```

---

## 第八步：更新 docker-compose.yml

如果保留Docker编排方式，更新 `D:\AI工作站部署\docker-compose.yml`：

### 8.1 关键修改项

1. **所有 `localhost` 替换为 `127.0.0.1`**（铁律）
2. **Ollama 改为原生安装**，从docker-compose中移除ollama服务
3. **Open WebUI 连接地址** 改为 `http://127.0.0.1:11434`
4. **RAGFlow** 如不保留则整段删除（含ES/MySQL/MinIO/Redis）
5. **faster-whisper** 端口检查是否与系统冲突（9000/9443）
6. **volume路径** 确认指向 D:\AI\ 下的正确位置

### 8.2 精简后的docker-compose（推荐）

```yaml
version: '3.8'

services:
  open-webui:
    image: ghcr.io/open-webui/open-webui:main
    container_name: open-webui
    restart: unless-stopped
    network_mode: host
    volumes:
      - openwebui_data:/app/backend/data
    environment:
      - OLLAMA_BASE_URL=http://127.0.0.1:11434
      - WEBUI_SECRET_KEY=ai-workstation-secret-key
    extra_hosts:
      - "host.docker.internal:host-gateway"

  # faster-whisper（可选，语音识别）
  faster-whisper:
    image: onerahmet/faster-whisper-server:latest
    container_name: faster-whisper
    restart: unless-stopped
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: all
              capabilities: [gpu]
    network_mode: host
    volumes:
      - whisper_models:/root/.cache/huggingface
    environment:
      - MODEL_NAME=large-v3
      - COMPUTE_TYPE=float16

volumes:
  openwebui_data:
    driver: local
    driver_opts:
      type: none
      o: bind
      device: D:/AI/docker-data/open-webui

  whisper_models:
    driver: local
    driver_opts:
      type: none
      o: bind
      device: D:/AI/docker-data/whisper_models
```

---

## 第九步：全面验证

### 9.1 服务验证清单

| 服务 | 验证方式 | 预期结果 |
|------|---------|---------|
| Ollama v0.30+ | `ollama --version` | >= 0.30.5 |
| Ollama模型 | `ollama list` | 5个模型全部列出 |
| Ollama推理 | `ollama run qwen3.5:4b "1+1=?"` | 正常回答 |
| Open WebUI | 访问 http://127.0.0.1:8080 | 页面正常加载 |
| ComfyUI | 启动后访问 http://127.0.0.1:8188 | 页面正常(需Ollama关闭) |
| xuanshu-agents | `python -c "from agents import *"` | 导入成功40项 |
| AgentOS | `python -m agents.agentos --help` | 帮助信息正常 |
| 自愈脚本 | 运行 `shortcut_heal_v2.ps1` | 无错误，日志正常 |

### 9.2 VRAM压力测试

```powershell
# 测试日常模式
ollama run qwen3.5:9b "测试"
ollama run qwen3.5:4b "测试"  # 第二个模型
nvidia-smi  # 确认VRAM占用在11GB左右

# 测试代码模式
ollama stop qwen3.5:9b
ollama stop qwen3.5:4b
ollama run qwen3-coder:30b "def fibonacci(n):"  # 应流畅运行
nvidia-smi  # 确认VRAM占用在15.6GB左右

# 测试多模态模式
ollama stop qwen3-coder:30b
ollama run gemma4:12b "描述这张图片"  # 需要上传图片测试
nvidia-smi  # 确认VRAM占用在10GB左右
```

### 9.3 自愈脚本验证

1. 运行自愈脚本，确认所有检查项通过
2. 故意修改一个快捷方式目标路径，运行自愈脚本，确认被恢复
3. 开启VPN（Hiddify），运行自愈脚本，确认不受影响
4. 确认桌面非AI工具箱快捷方式完全未被触碰
5. 确认白名单应用完全未被修改

---

## 第十步：生成验证报告

保存到 `D:\AI\self_check_report_v4.md`，包含：

1. Ollama版本和模型列表
2. Docker服务状态
3. ComfyUI状态
4. xuanshu-agents v4.0导入测试结果
5. VRAM三种模式测试结果
6. 自愈脚本V3验证结果
7. 过时模型删除记录
8. 未通过项及建议

---

## 完整服务清单与端口

| 服务 | 端口 | 用途 | 验证URL |
|------|------|------|---------|
| Ollama | :11434 | 本地LLM运行时 | http://127.0.0.1:11434/api/tags |
| Open WebUI | :8080 | LLM对话前端 | http://127.0.0.1:8080 |
| ComfyUI | :8188 | AI绘图 | http://127.0.0.1:8188 |
| AgentOS | :8000 | xuanshu-agents网关 | http://127.0.0.1:8000/health |
| faster-whisper | :9000 | 语音识别(可选) | http://127.0.0.1:9000/health |

---

## 铁律（任何情况下不可违反）

1. ❌ 绝对不删除、移动、卸载白名单中的任何软件和游戏
2. ❌ 绝对不清理/清空任何AppData、浏览器数据、凭据数据
3. ❌ 绝对不修改白名单中软件的快捷方式（越界保护铁律）
4. ❌ 绝对不运行任何清理工具或优化工具
5. ❌ 自愈脚本只操作 D:\AI\ 和 桌面\AI工具箱\ 下的文件，其他位置一律跳过
6. ❌ 不修改快捷方式的名称和图标（user_controlled属性以当前实际值为准）
7. ✅ 本体装C盘，数据放D盘，这是硬规则
8. ✅ 用户改了快捷方式名称/图标，以用户当前状态为真值
9. ✅ 所有URL使用 `127.0.0.1`，绝对不用 `localhost`（VPN免疫铁律）
10. ✅ 任何下载/安装操作，默认路径都指向D盘
11. ✅ 白名单应用操作必须双重确认（两遍确认才执行）
12. ✅ Edge不入白名单，可自由操作无需确认
13. ✅ 桌面非快捷方式文件不受白名单限制，可自由使用
14. ✅ 自愈脚本必须幂等：执行多次结果一致
15. ✅ initial_state.json 是自愈的唯一真值来源，如果它损坏则报错退出不做任何修改
16. ✅ .bat编码GBK+CRLF，.ps1编码UTF-8 BOM+CRLF，.json编码UTF-8
17. ✅ 修复前必须备份原文件到 D:\AI\backup\（带时间戳）
18. ✅ VPN开/关/切换三种状态下，脚本行为必须完全一致
19. ✅ Ollama和ComfyUI互斥，不能同时运行大模型和生图
20. ✅ 16GB VRAM是硬约束，模型加载前检查显存余量
21. ✅ qwen3-coder:30b 独占模式运行，不与其他大模型共存
22. ✅ API Key绝不硬编码，全部走环境变量或config.py（config.py在.gitignore中）
23. ✅ 数据不出本机，隐私不外泄
24. ✅ 不编造参考文献

---

## 注意事项

1. 拉取模型时需要VPN（Ollama模型下载走外网），确认Hiddify在运行
2. GitHub clone需要VPN+PAT，请用户提前准备好
3. DeepSeek API Key需要用户手动填入config.py，脚本中不包含
4. ComfyUI新模型(FLUX.1)下载也需要VPN，文件较大(6-12GB)，注意磁盘空间
5. RAGFlow是否保留需问用户，建议移除以释放RAM
6. 所有操作前确认备份了旧的initial_state.json
7. 操作顺序很重要：先升级Ollama→删旧模型→拉新模型→升级Docker→部署框架→更新自愈脚本
