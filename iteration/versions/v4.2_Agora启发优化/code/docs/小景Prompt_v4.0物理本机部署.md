# 铉枢·炉守 v4.0 物理本机部署 Prompt

> 给小景执行，部署xuanshu-agents v4.0到物理电脑

## 你的任务

在铉瀚的物理电脑上完成xuanshu-agents v4.0框架的完整部署，包括：清理旧服务、克隆仓库、配置环境、启动AgentOS和Hub控制面板、设置远程隧道。完成后所有服务可正常运行。

## 环境

| 项目 | 值 |
|------|-----|
| 系统 | Windows 11 64位 |
| GPU | RTX 3080 Ti Laptop 16GB VRAM |
| CPU | i9-12900H |
| RAM | 32GB |
| 用户名 | 铉瀚 |
| AI根目录 | D:\AI\ |
| 项目目录 | D:\xuan-hub\ |
| Ollama模型目录 | D:\AI\Models\Ollama |
| ComfyUI目录 | D:\AI\ComfyUI\ |

## 铁律

1. 所有URL用 `127.0.0.1`，绝对不用 `localhost`
2. .bat编码GBK+CRLF，.ps1编码UTF-8 BOM+CRLF
3. API Key不硬编码，走环境变量或config.py
4. Ollama和ComfyUI互斥，不能同时跑
5. 16GB VRAM硬约束，模型加载前检查显存
6. 不删白名单软件，不动非AI目录
7. 删除操作必须先备份到 `D:\AI\backup\`

---

## 第1步：诊断当前环境

先看看现在电脑上都有什么：

```powershell
# Python
python --version
# Git
git --version
# Docker
docker info 2>&1 | Select-String "Server Version"
# Ollama
ollama --version 2>$null; ollama list 2>$null
# GPU
nvidia-smi --query-gpu=name,memory.total,memory.free --format=csv,noheader
# 已有容器
docker ps -a --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}" 2>$null
# D盘空间
Get-PSDrive D | Select-Object Used, Free
# D:\xuan-hub 是否已存在
Test-Path "D:\xuan-hub"
```

把诊断结果完整输出，再继续。

---

## 第2步：清理旧Docker服务

### 2.1 RAGFlow全套（占8-10GB RAM，v4.0不需要）

```powershell
# 查看RAGFlow相关容器
$ragflow = @("ragflow","elasticsearch","mysql","minio","redis")
foreach ($n in $ragflow) {
    $c = docker ps -a --filter "name=$n" -q 2>$null
    if ($c) {
        Write-Host "发现容器: $n — 停止并删除"
        docker stop $c 2>$null; docker rm $c 2>$null
    }
}
# 清理悬空卷
docker volume prune -f 2>$null
```

### 2.2 Docker版Ollama（v4.0改用本地安装）

```powershell
$oc = docker ps -a --filter "name=ollama" -q 2>$null
if ($oc) {
    Write-Host "删除Docker版Ollama"
    docker stop $oc 2>$null; docker rm $oc 2>$null
}
```

### 2.3 停止的容器

```powershell
docker container prune -f 2>$null
docker image prune -f 2>$null
```

---

## 第3步：确认Ollama本地安装

```powershell
# 检查Ollama是否安装
$ollCmd = Get-Command ollama -ErrorAction SilentlyContinue
if (-not $ollCmd) {
    Write-Host "Ollama未安装，去 https://ollama.com/download 下载安装"
    # 不要自动下载，让用户手动装
    return
}

# 确认环境变量
$vars = @{
    "OLLAMA_MODELS" = "D:\AI\Models\Ollama"
    "OLLAMA_GPU_OVERHEAD" = "2048"
    "OLLAMA_NUM_PARALLEL" = "2"
    "OLLAMA_MAX_LOADED_MODELS" = "2"
    "OLLAMA_KEEP_ALIVE" = "5m"
}
foreach ($kv in $vars.GetEnumerator()) {
    $cur = [System.Environment]::GetEnvironmentVariable($kv.Key, "User")
    if ($cur -ne $kv.Value) {
        [System.Environment]::SetEnvironmentVariable($kv.Key, $kv.Value, "User")
        Write-Host "设置 $($kv.Key) = $($kv.Value)"
    }
}

# 确认Ollama在运行
$ollRunning = $false
try { $t = New-Object Net.Sockets.TcpClient; $t.Connect("127.0.0.1",11434); $t.Close(); $ollRunning = $true } catch {}
if (-not $ollRunning) {
    Write-Host "启动Ollama..."
    Start-Process "$env:LOCALAPPDATA\Programs\Ollama\ollama app.exe" -WindowStyle Hidden
    Start-Sleep -Seconds 8
}

# 检查模型
$needed = @("qwen3.5:4b","qwen3.5:9b","nomic-embed-text")
$optional = @("qwen3-coder:30b","gemma4:12b")
try {
    $tags = (Invoke-WebRequest -Uri "http://127.0.0.1:11434/api/tags" -UseBasicParsing -TimeoutSec 5).Content | ConvertFrom-Json
    $installed = $tags.models | ForEach-Object { $_.name -replace ':latest$','' }
} catch { $installed = @() }

foreach ($m in $needed) {
    if ($installed -notcontains $m) {
        Write-Host "拉取必要模型: $m"
        & ollama pull $m
    }
}
foreach ($m in $optional) {
    if ($installed -notcontains $m) {
        Write-Host "可选模型未装: $m（输入y拉取）"
        $ans = Read-Host "拉取？(y/N)"
        if ($ans -eq "y") { & ollama pull $m }
    }
}
```

---

## 第4步：精简Docker服务

只保留Open WebUI + Whisper（删掉RAGFlow后）：

```powershell
$composeDir = "D:\AI\docker"
if (-not (Test-Path $composeDir)) { New-Item -ItemType Directory -Path $composeDir -Force | Out-Null }

$compose = @'
version: '3.8'
services:
  open-webui:
    image: ghcr.io/open-webui/open-webui:main
    container_name: open-webui
    restart: unless-stopped
    ports:
      - "8080:8080"
    volumes:
      - openwebui_data:/app/backend/data
    environment:
      - OLLAMA_BASE_URL=http://host.docker.internal:11434
    extra_hosts:
      - "host.docker.internal:host-gateway"

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
    ports:
      - "9000:8000"
    volumes:
      - whisper_models:/root/.cache/huggingface
    environment:
      - MODEL_NAME=large-v3
      - COMPUTE_TYPE=float16

volumes:
  openwebui_data:
  whisper_models:
'@

[System.IO.File]::WriteAllText("$composeDir\docker-compose.yml", $compose, [System.Text.Encoding]::UTF8)
Write-Host "精简docker-compose.yml已写入"
```

如果Docker在运行，问用户要不要启动这些服务：

```powershell
$ans = Read-Host "启动Docker服务(OpenWebUI+Whisper)？(y/N)"
if ($ans -eq "y") {
    Push-Location $composeDir
    docker compose up -d 2>&1
    Pop-Location
}
```

---

## 第5步：克隆xuan-hub仓库

xuan-hub是private仓库，需要GitHub PAT。

```powershell
if (Test-Path "D:\xuan-hub") {
    Write-Host "D:\xuan-hub 已存在"
    $ans = Read-Host "备份旧版并重新克隆？(y/N)"
    if ($ans -eq "y") {
        $bak = "D:\AI\backup\xuan-hub_$(Get-Date -Format 'yyyyMMdd_HHmmss')"
        Move-Item "D:\xuan-hub" $bak
        Write-Host "旧版已备份到: $bak"
    } else {
        # 直接pull
        Push-Location "D:\xuan-hub"
        git pull origin main 2>&1
        Pop-Location
        Write-Host "已更新到最新"
        # 跳到第6步
    }
}

if (-not (Test-Path "D:\xuan-hub")) {
    Write-Host "需要GitHub PAT来克隆private仓库"
    $pat = Read-Host "请输入GitHub PAT（ghp_开头）"
    git clone "https://${pat}@github.com/tsingxuanhan/xuan-hub.git" D:\xuan-hub
    if ($LASTEXITCODE -eq 0) {
        Write-Host "克隆成功"
        Push-Location "D:\xuan-hub"
        git remote set-url origin https://github.com/tsingxuanhan/xuan-hub.git
        Pop-Location
        Write-Host "已清除URL中的PAT"
    } else {
        Write-Host "克隆失败，检查PAT是否有效"
        return
    }
}
```

---

## 第6步：Python虚拟环境 + 依赖

```powershell
$projectRoot = "D:\xuan-hub"
$venvPath = "$projectRoot\.venv"

# 创建venv
if (-not (Test-Path $venvPath)) {
    python -m venv $venvPath
    Write-Host ".venv已创建"
}

$venvPy = "$venvPath\Scripts\python.exe"
$venvPip = "$venvPath\Scripts\pip.exe"

# 升级pip
& $venvPy -m pip install --upgrade pip --quiet

# 安装依赖
$reqFile = "$projectRoot\requirements.txt"
if (Test-Path $reqFile) {
    & $venvPip install -r $reqFile --quiet
    Write-Host "依赖已安装"
} else {
    # 最小依赖
    @("fastapi","uvicorn","pydantic","requests","aiohttp","numpy","python-dotenv","python-multipart","aiofiles") | ForEach-Object {
        & $venvPip install $_ --quiet 2>$null
    }
    Write-Host "最小依赖已安装"
}

# 验证
& $venvPy -c "import fastapi, uvicorn, pydantic, numpy; print('依赖验证通过')"
```

---

## 第7步：配置config.py

```powershell
$cfgExample = "$projectRoot\config.example.py"
$cfgFile = "$projectRoot\config.py"

if (-not (Test-Path $cfgFile)) {
    if (Test-Path $cfgExample) {
        Copy-Item $cfgExample $cfgFile
        Write-Host "已从config.example.py创建config.py"
    }
}
```

**编辑config.py**，用户需要手动填入API Key。打开文件让用户编辑：

```powershell
# 提示用户填入API Key
Write-Host ""
Write-Host "======================================" -ForegroundColor Yellow
Write-Host "  需要编辑 config.py 填入API Key" -ForegroundColor Yellow
Write-Host "======================================" -ForegroundColor Yellow
Write-Host ""
Write-Host "关键配置项（在config.py中修改）:" -ForegroundColor Cyan
Write-Host "  DEEPSEEK_API_KEY = `"sk-你的Key`"    ← 必填，DeepSeek云端推理"
Write-Host "  DEEPSEEK_ENDPOINT = `"https://api.deepseek.com/v1/chat/completions`"  ← 改为直连"
Write-Host "  AGENTOS_CONFIG.port = 8000            ← AgentOS端口"
Write-Host ""

$ans = Read-Host "现在打开config.py编辑？(Y/n)"
if ($ans -ne "n") {
    notepad $cfgFile
    Write-Host "编辑完成后按任意键继续..."
    $null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")
}
```

**重要说明**：
- `DEEPSEEK_ENDPOINT` 需要改为 `https://api.deepseek.com/v1/chat/completions`（直连DeepSeek，不再走本地代理）
- `DEEPSEEK_API_KEY` 需要用户填入真实Key（不要用旧的泄露Key）
- `AGENTOS_CONFIG.port` 改为 8000（默认9090会和其他服务冲突）
- `AGENTOS_CONFIG.host` 改为 `127.0.0.1`

---

## 第8步：启动AgentOS

```powershell
# 检查8000端口是否已被占用
function Test-Port($port) {
    try { $t = New-Object Net.Sockets.TcpClient; $t.Connect("127.0.0.1",$port); $t.Close(); $true }
    catch { $false }
}

if (Test-Port 8000) {
    Write-Host "端口8000已被占用"
    $ans = Read-Host "终止占用进程？(y/N)"
    if ($ans -eq "y") {
        $proc = Get-NetTCPConnection -LocalPort 8000 -ErrorAction SilentlyContinue | Select-Object -ExpandProperty OwningProcess -Unique
        foreach ($p in $proc) { Stop-Process -Id $p -Force 2>$null }
        Start-Sleep -Seconds 2
    }
}

# 启动AgentOS
Push-Location $projectRoot
Start-Process $venvPy -ArgumentList "agentos.py" -WindowStyle Minimized
Pop-Location
Write-Host "AgentOS启动中..."
Start-Sleep -Seconds 5

if (Test-Port 8000) {
    # 验证
    try {
        $r = Invoke-WebRequest -Uri "http://127.0.0.1:8000/health" -UseBasicParsing -TimeoutSec 5
        Write-Host "AgentOS :8000 运行正常 — $($r.Content)"
    } catch {
        Write-Host "AgentOS :8000 端口在监听但/health无响应，检查config.py"
    }
} else {
    Write-Host "AgentOS启动失败 — 检查config.py和Python输出"
}
```

---

## 第9步：启动Hub控制面板

```powershell
$hubPort = 3000

# serve-hub.py应该已在仓库中，如果没有就创建
$serveHub = "$projectRoot\scripts\serve-hub.py"
if (-not (Test-Path $serveHub)) {
    $serveContent = @"
import http.server, socketserver, os, sys
os.chdir(os.path.join(os.path.dirname(__file__), '..', 'demo'))
PORT = 3000
class CORSHandler(http.server.SimpleHTTPRequestHandler):
    def end_headers(self):
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', '*')
        self.send_header('Access-Control-Allow-Headers', '*')
        super().end_headers()
    def log_message(self, format, *args): pass
with socketserver.TCPServer(('', PORT), CORSHandler) as httpd:
    print(f'Hub running at http://127.0.0.1:{PORT}')
    sys.stdout.flush()
    httpd.serve_forever()
"@
    [System.IO.File]::WriteAllText($serveHub, $serveContent, [System.Text.Encoding]::UTF8)
}

if (-not (Test-Port $hubPort)) {
    Start-Process $venvPy -ArgumentList $serveHub -WindowStyle Minimized
    Start-Sleep -Seconds 2
}

if (Test-Port $hubPort) {
    Write-Host "Hub控制面板: http://127.0.0.1:$hubPort"
    $ans = Read-Host "打开浏览器？(Y/n)"
    if ($ans -ne "n") {
        Start-Process "http://127.0.0.1:$hubPort"
    }
} else {
    Write-Host "Hub启动失败"
}
```

---

## 第10步：Cloudflare隧道（远程直连）

安装cloudflared后，可以让炉守（云端Agent）通过公网URL直连物理本机API：

```powershell
if (Get-Command cloudflared -ErrorAction SilentlyContinue) {
    Write-Host "cloudflared已安装"
    $ans = Read-Host "启动隧道？(y/N)"
    if ($ans -eq "y") {
        Write-Host "启动隧道（Ctrl+C停止）..."
        Write-Host "启动后会出现类似 https://xxx.trycloudflare.com 的URL"
        Write-Host "把这个URL发给炉守，就能直连本机AgentOS"
        & cloudflared tunnel --url http://127.0.0.1:8000
    }
} else {
    Write-Host "cloudflared未安装"
    Write-Host "下载: https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-windows-amd64.msi"
    $ans = Read-Host "打开下载页？(y/N)"
    if ($ans -eq "y") { Start-Process "https://github.com/cloudflare/cloudflared/releases" }
}
```

---

## 第11步：验证报告

全部完成后，输出验证结果：

```powershell
Write-Host ""
Write-Host "========== 部署验证报告 ==========" -ForegroundColor Cyan
Write-Host ""

# 服务状态
$services = @{
    "Ollama" = 11434
    "AgentOS" = 8000
    "Hub" = 3000
    "Open WebUI" = 8080
}
foreach ($svc in $services.GetEnumerator()) {
    $up = Test-Port $svc.Value
    $icon = if ($up) { "✅" } else { "❌" }
    Write-Host "$icon $($svc.Key) :$($svc.Value)"
}

# AgentOS API测试
Write-Host ""
Write-Host "--- AgentOS API ---"
try {
    $h = Invoke-WebRequest -Uri "http://127.0.0.1:8000/health" -UseBasicParsing -TimeoutSec 5
    Write-Host "✅ /health — $($h.StatusCode)"
} catch { Write-Host "❌ /health 不可达" }

try {
    $m = Invoke-WebRequest -Uri "http://127.0.0.1:8000/memory/stats" -UseBasicParsing -TimeoutSec 5
    Write-Host "✅ /memory/stats — $($m.StatusCode)"
} catch { Write-Host "❌ /memory/stats" }

try {
    $t = Invoke-WebRequest -Uri "http://127.0.0.1:8000/tools" -UseBasicParsing -TimeoutSec 5
    Write-Host "✅ /tools — $($t.StatusCode)"
} catch { Write-Host "❌ /tools" }

# Hub页面
Write-Host ""
Write-Host "--- Demo页面 ---"
@("hub.html","arch-explorer.html","v4-dashboard.html","a2a-network.html") | ForEach-Object {
    $path = "$projectRoot\demo\$_"
    if (Test-Path $path) {
        $size = [math]::Round((Get-Item $path).Length / 1KB, 1)
        Write-Host "✅ $_ ($size KB)"
    } else {
        Write-Host "❌ $_ 不存在"
    }
}

# GPU状态
Write-Host ""
$nvidia = & nvidia-smi --query-gpu=memory.used,memory.total --format=csv,noheader 2>$null
Write-Host "GPU VRAM: $nvidia"

Write-Host ""
Write-Host "=================================" -ForegroundColor Cyan
```

---

## 服务清单

| 服务 | 端口 | 用途 | 验证URL |
|------|------|------|---------|
| Ollama | :11434 | 本地LLM | http://127.0.0.1:11434/api/tags |
| AgentOS | :8000 | xuanshu-agents网关 | http://127.0.0.1:8000/health |
| Hub | :3000 | 控制面板 | http://127.0.0.1:3000/hub.html |
| Open WebUI | :8080 | 对话前端 | http://127.0.0.1:8080 |

## 可能遇到的问题

1. **AgentOS启动失败** → 检查config.py中DEEPSEEK_API_KEY是否填了，DEEPSEEK_ENDPOINT是否正确
2. **Hub面板API全报错** → 确认AgentOS在:8000运行；Hub会自动降级到mock数据并显示橙色横幅
3. **Ollama模型拉不下来** → 需要开VPN（Hiddify）
4. **GitHub克隆失败** → 需要VPN + 有效PAT
5. **端口被占用** → 用 `netstat -ano | findstr :8000` 查看占用进程
6. **config.py中的AGENTOS_CONFIG.port** → 默认是9090，改为8000
7. **config.py中的AGENTOS_CONFIG.host** → 默认是127.0.0.1，保持不变
