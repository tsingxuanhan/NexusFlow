#Requires -RunAsAdministrator
<#
.SYNOPSIS
    铉枢·炉守 本地部署管理器
.DESCRIPTION
    拉取最新代码 / 检查服务 / 清理废弃容器 / 启动AgentOS+Hub
#>

$ErrorActionPreference = "Continue"
$ProjectRoot = "D:\xuan-hub"
$PythonExe = "$ProjectRoot\.venv\Scripts\python.exe"
$OllamaModels = "D:\AI\Models\Ollama"

function Write-Status($icon, $msg) {
    Write-Host "  [$icon] $msg" -ForegroundColor $(if($icon -eq "✓"){"Green"}elseif($icon -eq "X"){"Red"}elseif($icon -eq "!"){"Yellow"}else{"Cyan"})
}

function Test-Port($port) {
    try {
        $tcp = New-Object System.Net.Sockets.TcpClient
        $tcp.Connect("127.0.0.1", $port)
        $tcp.Close()
        return $true
    } catch { return $false }
}

# ========== 1. 诊断当前状态 ==========
Write-Host "`n============================================" -ForegroundColor Cyan
Write-Host "  铉枢·炉守 — 本地状态诊断" -ForegroundColor Cyan
Write-Host "============================================`n" -ForegroundColor Cyan

# Docker容器
Write-Host "--- Docker容器 ---" -ForegroundColor Yellow
$dockerAvailable = $false
try {
    $containers = docker ps -a --format "{{.Names}}\t{{.Status}}\t{{.Ports}}" 2>$null
    $dockerAvailable = $true
    if ($containers) {
        $containers | ForEach-Object {
            $parts = $_ -split "`t"
            $name = $parts[0]
            $status = $parts[1]
            $ports = $parts[2]
            $isRunning = $status -match "Up"
            $icon = if($isRunning){"✓"}else{"X"}
            Write-Status $icon "$name — $status $ports"
        }
    } else {
        Write-Status "-" "无Docker容器运行"
    }
} catch {
    Write-Status "X" "Docker未运行或未安装"
}

# Ollama
Write-Host "`n--- Ollama ---" -ForegroundColor Yellow
if (Test-Port 11434) {
    Write-Status "✓" "Ollama :11434 在线"
    try {
        $models = (Invoke-WebRequest -Uri "http://127.0.0.1:11434/api/tags" -UseBasicParsing -TimeoutSec 5).Content | ConvertFrom-Json
        foreach ($m in $models.models) {
            $size = [math]::Round($m.size / 1GB, 2)
            Write-Status " " "  $($m.name) (${size}GB)"
        }
    } catch {
        Write-Status "!" "无法获取模型列表"
    }
} else {
    Write-Status "X" "Ollama :11434 离线"
}

# AgentOS
Write-Host "`n--- AgentOS ---" -ForegroundColor Yellow
if (Test-Port 8000) {
    Write-Status "✓" "AgentOS :8000 在线"
    try {
        $health = (Invoke-WebRequest -Uri "http://127.0.0.1:8000/health" -UseBasicParsing -TimeoutSec 3).Content | ConvertFrom-Json
        Write-Status " " "  版本: $($health.version) | Agent: $($health.agent)"
    } catch {
        Write-Status "!" "健康检查失败"
    }
} else {
    Write-Status "X" "AgentOS :8000 离线"
}

# Hub面板
Write-Host "`n--- Hub面板 ---" -ForegroundColor Yellow
if (Test-Port 3000) {
    Write-Status "✓" "Hub :3000 在线"
} else {
    Write-Status "X" "Hub :3000 离线"
}

# 其他服务
foreach ($svc in @(@{Name="OpenWebUI";Port=8080}, @{Name="ComfyUI";Port=8188}, @{Name="Whisper";Port=9000})) {
    if (Test-Port $svc.Port) {
        Write-Status "✓" "$($svc.Name) :$($svc.Port) 在线"
    } else {
        Write-Status "-" "$($svc.Name) :$($svc.Port) 离线"
    }
}

# ========== 2. 清理废弃容器 ==========
Write-Host "`n============================================" -ForegroundColor Cyan
Write-Host "  清理废弃Docker资源" -ForegroundColor Cyan
Write-Host "============================================`n" -ForegroundColor Cyan

if ($dockerAvailable) {
    # 已停止的容器
    $stopped = docker ps -a --filter "status=exited" --format "{{.Names}}" 2>$null
    if ($stopped) {
        Write-Host "已停止的容器:" -ForegroundColor Yellow
        $stopped | ForEach-Object { Write-Host "  - $_" }
        $answer = Read-Host "是否删除这些已停止的容器？(y/N)"
        if ($answer -eq "y" -or $answer -eq "Y") {
            docker container prune -f 2>$null
            Write-Status "✓" "已清理停止的容器"
        }
    } else {
        Write-Status "✓" "无已停止的容器需要清理"
    }

    # 悬空镜像
    $dangling = docker images --filter "dangling=true" -q 2>$null
    if ($dangling) {
        $danglingCount = ($dangling | Measure-Object).Count
        Write-Status "!" "发现 $danglingCount 个悬空镜像"
        $answer = Read-Host "是否清理悬空镜像？(y/N)"
        if ($answer -eq "y" -or $answer -eq "Y") {
            docker image prune -f 2>$null
            Write-Status "✓" "已清理悬空镜像"
        }
    }

    # RAGFlow检查
    $ragflowContainers = docker ps -a --filter "name=ragflow" --format "{{.Names}}\t{{.Status}}" 2>$null
    if ($ragflowContainers) {
        Write-Host "`n[!] 检测到RAGFlow容器:" -ForegroundColor Yellow
        $ragflowContainers | ForEach-Object { Write-Host "  $_" }
        Write-Host "  RAGFlow占用8-10GB RAM，建议移除（不影响框架功能）" -ForegroundColor Yellow
        $answer = Read-Host "是否停止并删除RAGFlow？(y/N)"
        if ($answer -eq "y" -or $answer -eq "Y") {
            docker ps -a --filter "name=ragflow" -q | ForEach-Object { docker stop $_ 2>$null; docker rm $_ 2>$null }
            Write-Status "✓" "RAGFlow已移除"
        }
    }
}

# ========== 3. 拉取最新代码 ==========
Write-Host "`n============================================" -ForegroundColor Cyan
Write-Host "  同步最新代码" -ForegroundColor Cyan
Write-Host "============================================`n" -ForegroundColor Cyan

if (Test-Path $ProjectRoot) {
    Push-Location $ProjectRoot
    Write-Status " " "正在pull..."
    git pull origin main 2>&1 | ForEach-Object { Write-Host "  $_" }
    Write-Status "✓" "代码已同步"
    Pop-Location
} else {
    Write-Status "!" "项目目录 $ProjectRoot 不存在"
    $answer = Read-Host "是否克隆仓库？(y/N)"
    if ($answer -eq "y" -or $answer -eq "Y") {
        git clone https://github.com/tsingxuanhan/xuan-hub.git $ProjectRoot
        Write-Status "✓" "仓库已克隆"
    }
}

# ========== 4. Python环境 ==========
Write-Host "`n============================================" -ForegroundColor Cyan
Write-Host "  Python环境检查" -ForegroundColor Cyan
Write-Host "============================================`n" -ForegroundColor Cyan

if (-not (Test-Path "$ProjectRoot\.venv")) {
    Write-Status "!" "未找到.venv，正在创建..."
    Push-Location $ProjectRoot
    python -m venv .venv
    & $PythonExe -m pip install --upgrade pip
    Pop-Location
    Write-Status "✓" "虚拟环境已创建"
}

# 安装/更新依赖
Push-Location $ProjectRoot
if (Test-Path "requirements.txt") {
    Write-Status " " "检查依赖..."
    & $PythonExe -m pip install -r requirements.txt --quiet 2>&1 | ForEach-Object {
        if ($_ -match "Successfully installed|Requirement already satisfied") { }
    }
    Write-Status "✓" "依赖已就绪"
}
Pop-Location

# ========== 5. 启动服务 ==========
Write-Host "`n============================================" -ForegroundColor Cyan
Write-Host "  启动服务" -ForegroundColor Cyan
Write-Host "============================================`n" -ForegroundColor Cyan

# Ollama
if (-not (Test-Port 11434)) {
    Write-Status "!" "Ollama未启动，正在启动..."
    Start-Process "ollama" -ArgumentList "serve" -WindowStyle Hidden
    Start-Sleep -Seconds 3
    if (Test-Port 11434) {
        Write-Status "✓" "Ollama已启动"
    } else {
        Write-Status "X" "Ollama启动失败，请手动启动"
    }
} else {
    Write-Status "✓" "Ollama已在运行"
}

# AgentOS
if (-not (Test-Port 8000)) {
    Write-Status " " "正在启动AgentOS..."
    Push-Location $ProjectRoot
    Start-Process $PythonExe -ArgumentList "agentos.py" -WindowStyle Minimized
    Pop-Location
    Start-Sleep -Seconds 3
    if (Test-Port 8000) {
        Write-Status "✓" "AgentOS :8000 已启动"
    } else {
        Write-Status "X" "AgentOS启动失败，请检查日志"
    }
} else {
    Write-Status "✓" "AgentOS已在运行"
}

# Hub面板
if (-not (Test-Port 3000)) {
    Write-Status " " "正在启动Hub面板..."
    Push-Location $ProjectRoot
    Start-Process $PythonExe -ArgumentList "scripts\serve-hub.py" -WindowStyle Minimized
    Pop-Location
    Start-Sleep -Seconds 2
    if (Test-Port 3000) {
        Write-Status "✓" "Hub :3000 已启动"
    } else {
        Write-Status "X" "Hub启动失败"
    }
} else {
    Write-Status "✓" "Hub已在运行"
}

# ========== 6. 最终状态 ==========
Write-Host "`n============================================" -ForegroundColor Green
Write-Host "  部署完成！" -ForegroundColor Green
Write-Host "============================================`n" -ForegroundColor Green

Write-Host "  Hub控制面板:  http://127.0.0.1:3000" -ForegroundColor White
Write-Host "  AgentOS API:  http://127.0.0.1:8000" -ForegroundColor White
Write-Host "  Ollama API:   http://127.0.0.1:11434" -ForegroundColor White
Write-Host ""

if (Test-Port 3000) {
    $answer = Read-Host "是否在浏览器中打开Hub面板？(Y/n)"
    if ($answer -ne "n" -and $answer -ne "N") {
        Start-Process "http://127.0.0.1:3000"
    }
}

Write-Host "`n按任意键退出..." -ForegroundColor DarkGray
$null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")
