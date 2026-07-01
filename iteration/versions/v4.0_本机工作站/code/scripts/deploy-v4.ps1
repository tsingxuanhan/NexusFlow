#Requires -RunAsAdministrator
<#
.SYNOPSIS
    铉枢·炉守 v4.0 — 物理本机完整部署
.DESCRIPTION
    清理旧Docker容器 + 部署新架构 + 启动AgentOS + Hub + 隧道
    适用于: RTX 3080 Ti Laptop 16GB / i9-12900H / 32GB RAM / Windows 11
.NOTES
    保存到 D:\xuan-hub\scripts\deploy-v4.ps1，右键"以管理员身份运行"
#>

$ErrorActionPreference = "Continue"

# ==================== 配置 ====================
$Config = @{
    ProjectRoot   = "D:\xuan-hub"
    AIRoot        = "D:\AI"
    OllamaModels  = "D:\AI\Models\Ollama"
    ComfyUIPath   = "D:\AI\ComfyUI"
    PythonExe     = ""          # 自动检测
    VenvPath      = "D:\xuan-hub\.venv"
    HubPort       = 3000
    AgentOSPort   = 8000
    OllamaPort    = 11434
    WebUIPort     = 8080
}

# 颜色输出
function S($icon, $msg) {
    $c = switch($icon) { "✓"{"Green"} "X"{"Red"} "!"{"Yellow"} default{"Cyan"} }
    Write-Host "  [$icon] $msg" -ForegroundColor $c
}

function Section($title) {
    Write-Host "`n============================================" -ForegroundColor Cyan
    Write-Host "  $title" -ForegroundColor Cyan
    Write-Host "============================================`n" -ForegroundColor Cyan
}

function Test-Port($port) {
    try { $t = New-Object Net.Sockets.TcpClient; $t.Connect("127.0.0.1",$port); $t.Close(); $true }
    catch { $false }
}

# ==================== 第1步: 诊断 ====================
Section "第1步 · 当前环境诊断"

# Python
$pyCmd = $null
foreach ($cmd in @("python", "python3", "py")) {
    try { $v = & $cmd --version 2>&1; if ($v -match "3\.(\d+)") { $pyCmd = $cmd; break } } catch {}
}
if ($pyCmd) {
    $pyVer = & $pyCmd --version 2>&1
    S "✓" "Python: $pyVer ($pyCmd)"
    $Config.PythonExe = (Get-Command $pyCmd).Source
} else {
    S "X" "未找到Python 3！请安装 https://www.python.org/downloads/"
    S "!" "安装时勾选 'Add Python to PATH'"
    exit 1
}

# Git
try { $gitVer = & git --version 2>&1; S "✓" "Git: $gitVer" } catch { S "X" "Git未安装" }

# Docker
$dockerOk = $false
try {
    $null = docker info 2>&1
    $dockerOk = $true
    S "✓" "Docker: 运行中"
    $containers = docker ps -a --format "{{.Names}}`t{{.Status}}`t{{.Ports}}" 2>$null
    if ($containers) {
        S " " "当前容器:"
        $containers | ForEach-Object {
            $p = $_ -split "`t"
            $running = $p[1] -match "Up"
            S $(if($running){"✓"}else{"X"}) "$($p[0]) — $($p[1]) $($p[2])"
        }
    }
} catch {
    S "X" "Docker未运行或未安装"
}

# Ollama
if (Test-Port 11434) {
    S "✓" "Ollama :11434 运行中"
    try {
        $tags = (Invoke-WebRequest -Uri "http://127.0.0.1:11434/api/tags" -UseBasicParsing -TimeoutSec 5).Content | ConvertFrom-Json
        foreach ($m in $tags.models) {
            $sz = [math]::Round($m.size / 1GB, 2)
            S " " "  $($m.name) (${sz}GB)"
        }
    } catch {}
} else {
    S "-" "Ollama :11434 未运行"
}

# NVIDIA
try {
    $nvidia = & nvidia-smi --query-gpu=name,memory.total,memory.free --format=csv,noheader 2>&1
    S "✓" "GPU: $nvidia"
} catch { S "X" "nvidia-smi不可用" }

# ==================== 第2步: 清理旧服务 ====================
Section "第2步 · 清理旧Docker服务"

if ($dockerOk) {
    # RAGFlow全家桶 — 占8-10GB RAM，v4.0不需要
    $ragflowNames = @("ragflow", "elasticsearch", "mysql", "minio", "redis")
    $ragflowRunning = docker ps -a --filter "name=ragflow" --filter "name=elasticsearch" --filter "name=mysql" --filter "name=minio" --filter "name=redis" --format "{{.Names}}" 2>$null
    
    if ($ragflowRunning) {
        S "!" "检测到RAGFlow相关容器（占用8-10GB RAM）:"
        $ragflowRunning | ForEach-Object { S " " "  $_" }
        $ans = Read-Host "删除RAGFlow全套？(y/N)"
        if ($ans -eq "y" -or $ans -eq "Y") {
            foreach ($name in $ragflowNames) {
                $c = docker ps -a --filter "name=$name" -q 2>$null
                if ($c) { docker stop $c 2>$null; docker rm $c 2>$null; S "✓" "$name 已删除" }
            }
            # 清理RAGFlow数据卷
            S " " "清理RAGFlow数据..."
            docker volume prune -f 2>$null
        }
    } else {
        S "✓" "无RAGFlow容器"
    }

    # 停止的容器
    $stopped = docker ps -a --filter "status=exited" --format "{{.Names}}" 2>$null
    if ($stopped) {
        S "!" "已停止的容器:"
        $stopped | ForEach-Object { S " " "  $_" }
        $ans = Read-Host "清理？(y/N)"
        if ($ans -eq "y" -or $ans -eq "Y") {
            docker container prune -f 2>$null
            S "✓" "已清理"
        }
    }

    # 悬空镜像
    $dangling = docker images --filter "dangling=true" -q 2>$null
    if ($dangling) {
        $cnt = ($dangling | Measure-Object).Count
        S "!" "$cnt 个悬空镜像"
        $ans = Read-Host "清理？(y/N)"
        if ($ans -eq "y" -or $ans -eq "Y") {
            docker image prune -f 2>$null
            S "✓" "已清理"
        }
    }

    # Ollama容器 — v4.0改用本地安装（更稳定）
    $ollamaContainer = docker ps -a --filter "name=ollama" -q 2>$null
    if ($ollamaContainer) {
        S "!" "检测到Docker版Ollama（v4.0推荐本地安装，更快更稳）"
        $ans = Read-Host "删除Docker版Ollama？(y/N)"
        if ($ans -eq "y" -or $ans -eq "Y") {
            docker stop $ollamaContainer 2>$null
            docker rm $ollamaContainer 2>$null
            S "✓" "Docker版Ollama已删除"
        }
    }
} else {
    S "-" "Docker未运行，跳过容器清理"
}

# ==================== 第3步: 安装Ollama本地版 ====================
Section "第3步 · Ollama本地安装"

if (-not (Get-Command ollama -ErrorAction SilentlyContinue)) {
    S "!" "Ollama未安装，正在下载..."
    $ollamaUrl = "https://ollama.com/download/OllamaSetup.exe"
    $ollamaInstaller = "$env:TEMP\OllamaSetup.exe"
    Invoke-WebRequest -Uri $ollamaUrl -OutFile $ollamaInstaller -UseBasicParsing
    S " " "启动安装器（请按提示完成）..."
    Start-Process $ollamaInstaller -Wait
    S "✓" "Ollama安装完成"
} else {
    $ollVer = & ollama --version 2>&1
    S "✓" "Ollama已安装: $ollVer"
}

# 设置环境变量
$envVars = @{
    "OLLAMA_MODELS"         = $Config.OllamaModels
    "OLLAMA_GPU_OVERHEAD"   = "2048"
    "OLLAMA_NUM_PARALLEL"   = "2"
    "OLLAMA_MAX_LOADED_MODELS" = "2"
    "OLLAMA_KEEP_ALIVE"     = "5m"
}
foreach ($kv in $envVars.GetEnumerator()) {
    $current = [System.Environment]::GetEnvironmentVariable($kv.Key, "User")
    if ($current -ne $kv.Value) {
        [System.Environment]::SetEnvironmentVariable($kv.Key, $kv.Value, "User")
        S " " "设置 $($_.Key) = $($kv.Value)"
    }
}

# 启动Ollama
if (-not (Test-Port 11434)) {
    S " " "启动Ollama..."
    $ollamaPath = Get-Command ollama -ErrorAction SilentlyContinue
    if ($ollamaPath) {
        Start-Process $ollamaPath.Source -ArgumentList "serve" -WindowStyle Hidden
        Start-Sleep -Seconds 5
    }
    # 也尝试从安装路径启动
    $appPath = "$env:LOCALAPPDATA\Programs\Ollama\ollama app.exe"
    if ((Test-Path $appPath) -and -not (Test-Port 11434)) {
        Start-Process $appPath -WindowStyle Hidden
        Start-Sleep -Seconds 5
    }
}
if (Test-Port 11434) { S "✓" "Ollama :11434 在线" } else { S "X" "Ollama启动失败" }

# 检查模型
$neededModels = @("qwen3.5:4b", "nomic-embed-text")
$optionalModels = @("qwen3.5:9b", "qwen3-coder:30b", "gemma4:12b")

try {
    $existing = (Invoke-WebRequest -Uri "http://127.0.0.1:11434/api/tags" -UseBasicParsing -TimeoutSec 5).Content | ConvertFrom-Json
    $existingNames = $existing.models | ForEach-Object { $_.name -replace ':latest$','' }
} catch { $existingNames = @() }

foreach ($m in $neededModels) {
    if ($existingNames -notcontains $m) {
        S "!" "缺少必要模型: $m，正在拉取..."
        & ollama pull $m
    } else {
        S "✓" "模型 $m 已就绪"
    }
}

$missing = $optionalModels | Where-Object { $existingNames -notcontains $_ }
if ($missing) {
    S "!" "可选模型未安装: $($missing -join ', ')"
    $ans = Read-Host "拉取可选模型？(y/N)"
    if ($ans -eq "y" -or $ans -eq "Y") {
        foreach ($m in $missing) { & ollama pull $m }
    }
}

# ==================== 第4步: Docker服务（精简版） ====================
Section "第4步 · Docker服务（精简版，无RAGFlow）"

# 写精简版docker-compose
$composeDir = "$($Config.AIRoot)\docker"
if (-not (Test-Path $composeDir)) { New-Item -ItemType Directory -Path $composeDir -Force | Out-Null }

$composeContent = @'
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

Set-Content -Path "$composeDir\docker-compose.yml" -Value $composeContent -Encoding UTF8
S "✓" "精简docker-compose.yml已生成（仅OpenWebUI + Whisper）"

if ($dockerOk) {
    $ans = Read-Host "启动Docker服务？(y/N)"
    if ($ans -eq "y" -or $ans -eq "Y") {
        Push-Location $composeDir
        docker compose up -d 2>&1 | ForEach-Object { Write-Host "  $_" }
        Pop-Location
        S "✓" "Docker服务已启动"
    }
}

# ==================== 第5步: 克隆/更新仓库 ====================
Section "第5步 · xuanshu-agents v4.0"

if (Test-Path $Config.ProjectRoot) {
    Push-Location $Config.ProjectRoot
    S " " "拉取最新代码..."
    git pull origin main 2>&1 | ForEach-Object { Write-Host "  $_" }
    S "✓" "代码已更新"
    Pop-Location
} else {
    S "!" "$($Config.ProjectRoot) 不存在"
    $ans = Read-Host "克隆xuan-hub？(y/N)"
    if ($ans -eq "y" -or $ans -eq "Y") {
        git clone https://github.com/tsingxuanhan/xuan-hub.git $Config.ProjectRoot
        S "✓" "仓库已克隆"
    } else {
        S "X" "跳过克隆，后续手动处理"
    }
}

# ==================== 第6步: Python虚拟环境 ====================
Section "第6步 · Python环境"

if (-not (Test-Path $Config.VenvPath)) {
    S " " "创建虚拟环境..."
    & $Config.PythonExe -m venv $Config.VenvPath
    S "✓" ".venv已创建"
}

$venvPython = "$($Config.VenvPath)\Scripts\python.exe"
if (-not (Test-Path $venvPython)) {
    S "X" "venv创建失败"
    exit 1
}

# 升级pip
& $venvPython -m pip install --upgrade pip --quiet 2>&1 | Out-Null

# 安装依赖
$reqFile = "$($Config.ProjectRoot)\requirements.txt"
if (Test-Path $reqFile) {
    S " " "安装Python依赖..."
    & $venvPython -m pip install -r $reqFile --quiet 2>&1 | ForEach-Object {
        if ($_ -match "error|Error") { Write-Host "  $_" -ForegroundColor Red }
    }
    S "✓" "依赖已安装"
} else {
    # 最小依赖集
    S " " "安装最小依赖集..."
    @("fastapi", "uvicorn", "pydantic", "requests") | ForEach-Object {
        & $venvPython -m pip install $_ --quiet 2>&1 | Out-Null
    }
    S "✓" "最小依赖已安装"
}

# ==================== 第7步: 启动AgentOS ====================
Section "第7步 · 启动AgentOS"

if (Test-Port $Config.AgentOSPort) {
    S "✓" "AgentOS :$($Config.AgentOSPort) 已在运行"
} else {
    S " " "启动AgentOS..."
    Push-Location $Config.ProjectRoot
    
    # 先检查config.py
    if (-not (Test-Path "$($Config.ProjectRoot)\config.py")) {
        if (Test-Path "$($Config.ProjectRoot)\config.example.py") {
            Copy-Item "$($Config.ProjectRoot)\config.example.py" "$($Config.ProjectRoot)\config.py"
            S "!" "已从config.example.py创建config.py，请编辑后重启"
        }
    }
    
    Start-Process $venvPython -ArgumentList "agentos.py" -WindowStyle Minimized
    Pop-Location
    
    Start-Sleep -Seconds 5
    if (Test-Port $Config.AgentOSPort) {
        S "✓" "AgentOS :$($Config.AgentOSPort) 已启动"
    } else {
        S "X" "AgentOS启动失败 — 检查config.py中的API Key配置"
    }
}

# ==================== 第8步: 启动Hub ====================
Section "第8步 · 启动Hub控制面板"

$serveHub = "$($Config.ProjectRoot)\scripts\serve-hub.py"
$hubHtml = "$($Config.ProjectRoot)\demo\hub.html"

if (-not (Test-Path $serveHub)) {
    # 创建serve-hub.py
    $serveContent = @"
import http.server
import socketserver
import os
import sys

os.chdir(os.path.join(os.path.dirname(__file__), '..', 'demo'))
PORT = 3000

class CORSHandler(http.server.SimpleHTTPRequestHandler):
    def end_headers(self):
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', '*')
        self.send_header('Access-Control-Allow-Headers', '*')
        super().end_headers()
    def log_message(self, format, *args):
        pass

with socketserver.TCPServer(('', PORT), CORSHandler) as httpd:
    print(f'Hub running at http://127.0.0.1:{PORT}')
    sys.stdout.flush()
    httpd.serve_forever()
"@
    Set-Content -Path $serveHub -Value $serveContent -Encoding UTF8
}

if (Test-Port $Config.HubPort) {
    S "✓" "Hub :$($Config.HubPort) 已在运行"
} else {
    S " " "启动Hub..."
    Start-Process $venvPython -ArgumentList $serveHub -WindowStyle Minimized
    Start-Sleep -Seconds 2
    if (Test-Port $Config.HubPort) {
        S "✓" "Hub :$($Config.HubPort) 已启动"
    } else {
        S "X" "Hub启动失败"
    }
}

# ==================== 第9步: Cloudflare隧道（可选） ====================
Section "第9步 · 远程隧道（可选）"

S " " "如果你需要让炉守（云端Agent）访问本机API："
S " " "1. 安装cloudflared: https://github.com/cloudflare/cloudflared/releases"
S " " "2. 运行: cloudflared tunnel --url http://127.0.0.1:8000"
S " " "3. 把生成的URL发给炉守"
Write-Host ""
$ans = Read-Host "现在设置隧道？(y/N)"
if ($ans -eq "y" -or $ans -eq "Y") {
    if (Get-Command cloudflared -ErrorAction SilentlyContinue) {
        S " " "启动隧道（Ctrl+C停止）..."
        & cloudflared tunnel --url http://127.0.0.1:8000
    } else {
        S "!" "请先安装cloudflared"
        S " " "下载: https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-windows-amd64.msi"
        Start-Process "https://github.com/cloudflare/cloudflared/releases"
    }
}

# ==================== 完成 ====================
Section "部署完成！"

Write-Host "  服务地址:" -ForegroundColor White
if (Test-Port $Config.HubPort) { Write-Host "    Hub控制面板:  http://127.0.0.1:$($Config.HubPort)" -ForegroundColor Green }
if (Test-Port $Config.AgentOSPort) { Write-Host "    AgentOS API:  http://127.0.0.1:$($Config.AgentOSPort)" -ForegroundColor Green }
if (Test-Port $Config.OllamaPort) { Write-Host "    Ollama API:   http://127.0.0.1:$($Config.OllamaPort)" -ForegroundColor Green }
if (Test-Port $Config.WebUIPort) { Write-Host "    Open WebUI:   http://127.0.0.1:$($Config.WebUIPort)" -ForegroundColor Green }
Write-Host ""

if (Test-Port $Config.HubPort) {
    $ans = Read-Host "打开Hub控制面板？(Y/n)"
    if ($ans -ne "n" -and $ans -ne "N") {
        Start-Process "http://127.0.0.1:$($Config.HubPort)"
    }
}

Write-Host "`n按任意键退出..." -ForegroundColor DarkGray
$null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")
