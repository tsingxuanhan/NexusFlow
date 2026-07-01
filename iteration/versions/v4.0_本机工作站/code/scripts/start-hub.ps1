#Requires -RunAsAdministrator
# 铉枢·炉守 一键启动脚本 v4.0
# 用法: 右键→使用PowerShell运行，或 .\start-hub.ps1

$ErrorActionPreference = "SilentlyContinue"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

Write-Host ""
Write-Host "  ╔══════════════════════════════════════╗" -ForegroundColor DarkCyan
Write-Host "  ║   铉枢·炉守  Xuanshu Agents Hub     ║" -ForegroundColor Cyan
Write-Host "  ║   One-Click Launcher v4.0            ║" -ForegroundColor DarkGray
Write-Host "  ╚══════════════════════════════════════╝" -ForegroundColor DarkCyan
Write-Host ""

# ===== 配置 =====
$OllamaPath = "D:\AI\Ollama"
$ProjectPath = "D:\xuan-hub"
$DockerPath = "D:\AI"
$HubPort = 3000

# ===== 1. 检查Ollama =====
Write-Host "[1/5] 检查 Ollama..." -ForegroundColor Yellow -NoNewline
$ollama = Get-Process -Name "ollama" -ErrorAction SilentlyContinue
if (-not $ollama) {
    Write-Host " 启动中" -ForegroundColor Gray
    Start-Process -FilePath "$OllamaPath\ollama.exe" -ArgumentList "serve" -WindowStyle Hidden
    Start-Sleep -Seconds 3
    $ollama = Get-Process -Name "ollama" -ErrorAction SilentlyContinue
}
if ($ollama) { Write-Host " ✓ 运行中" -ForegroundColor Green }
else { Write-Host " ✗ 未运行(手动启动ollama serve)" -ForegroundColor Red }

# ===== 2. 检查Docker服务 =====
Write-Host "[2/5] 检查 Docker 服务..." -ForegroundColor Yellow -NoNewline
$docker = Get-Process -Name "com.docker.backend" -ErrorAction SilentlyContinue
if (-not $docker) {
    Write-Host " 启动Docker Desktop" -ForegroundColor Gray
    Start-Process "C:\Program Files\Docker\Docker\Docker Desktop.exe"
    Start-Sleep -Seconds 15
}
Write-Host " ✓" -ForegroundColor Green

# ===== 3. Docker Compose =====
Write-Host "[3/5] 启动 Docker Compose..." -ForegroundColor Yellow -NoNewline
Push-Location "$DockerPath"
$composeResult = docker compose up -d 2>&1
if ($LASTEXITCODE -eq 0) { Write-Host " ✓" -ForegroundColor Green }
else { Write-Host " 部分服务可能未启动" -ForegroundColor DarkYellow }
Pop-Location

# ===== 4. AgentOS =====
Write-Host "[4/5] 启动 AgentOS..." -ForegroundColor Yellow -NoNewline
$agentos = Get-Process -Name "python" -ErrorAction SilentlyContinue | Where-Object { $_.CommandLine -match "agentos" }
if (-not $agentos) {
    Push-Location "$ProjectPath"
    Start-Process -FilePath "python" -ArgumentList "agentos.py" -WindowStyle Minimized
    Pop-Location
    Start-Sleep -Seconds 2
}
Write-Host " ✓ :8000" -ForegroundColor Green

# ===== 5. 打开Hub =====
Write-Host "[5/5] 打开控制面板..." -ForegroundColor Yellow
Start-Sleep -Milliseconds 500
Start-Process "http://127.0.0.1:$HubPort"

Write-Host ""
Write-Host "  ┌─────────────────────────────────────┐" -ForegroundColor DarkCyan
Write-Host "  │  服务状态                            │" -ForegroundColor Cyan
Write-Host "  │  Ollama    : http://127.0.0.1:11434  │" -ForegroundColor Gray
Write-Host "  │  AgentOS   : http://127.0.0.1:8000   │" -ForegroundColor Gray
Write-Host "  │  Open WebUI: http://127.0.0.1:8080   │" -ForegroundColor Gray
Write-Host "  │  Hub面板   : http://127.0.0.1:$HubPort  │" -ForegroundColor Green
Write-Host "  └─────────────────────────────────────┘" -ForegroundColor DarkCyan
Write-Host ""
Write-Host "按任意键退出（服务继续运行）..." -ForegroundColor DarkGray
$null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")
