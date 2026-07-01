# ============================================================
# 铉枢 · 本机AI工作站 — 一键启动
# 适用于: Windows 11 + RTX 3080 Ti 16GB
# ============================================================

$ErrorActionPreference = "Stop"
Write-Host "🔍 铉枢 · 启动本机工作站..." -ForegroundColor Cyan

# 1. 启动 Docker 服务
Write-Host "📦 启动Docker服务..."
Set-Location "D:\AI\ai-workstation\docker"

# 确认 Docker Desktop 运行
$dockerRunning = Get-Process "Docker Desktop" -ErrorAction SilentlyContinue
if (-not $dockerRunning) {
    Write-Host "  启动 Docker Desktop..."
    Start-Process "C:\Program Files\Docker\Docker\Docker Desktop.exe"
    Start-Sleep -Seconds 30
}

docker compose up -d ollama open-webui portainer stirling-pdf drawio
Write-Host "  ✓ Docker服务已启动" -ForegroundColor Green

# 2. 启动 API 代理层
Write-Host "🔗 启动API代理层..."
$proxyPath = "D:\AI\ai-workstation\api-proxy"
if (-not (Test-Path "$proxyPath\proxy.py")) {
    # 从仓库复制
    Copy-Item "\\wsl$\Ubuntu\root\ai-workstation\api-proxy\proxy.py" $proxyPath -Force
}

# 检查代理是否已运行
$proxyRunning = Get-NetTCPConnection -LocalPort 8083 -ErrorAction SilentlyContinue
if (-not $proxyRunning) {
    Start-Process python -ArgumentList "$proxyPath\proxy.py" -WindowStyle Hidden
    Start-Sleep -Seconds 2
}
Write-Host "  ✓ :8083 DeepSeek Gateway" -ForegroundColor Green
Write-Host "  ✓ :8084 MiMo 700M Gateway" -ForegroundColor Green
Write-Host "  ✓ :8085 MiMo 200M Gateway" -ForegroundColor Green

# 3. 启动控制面板
Write-Host "🖥️ 启动控制面板..."
$panelPath = "D:\AI\ai-workstation\control-panel"
$panelRunning = Get-NetTCPConnection -LocalPort 8766 -ErrorAction SilentlyContinue
if (-not $panelRunning) {
    Start-Process python -ArgumentList "-m", "http.server", "8766" -WorkingDirectory $panelPath -WindowStyle Hidden
    Start-Sleep -Seconds 1
}
Write-Host "  ✓ 控制面板 :8766" -ForegroundColor Green

# 4. 验证服务
Write-Host ""
Write-Host "=============================================" -ForegroundColor Yellow
Write-Host "  服务状态" -ForegroundColor Yellow
Write-Host "=============================================" -ForegroundColor Yellow

$services = @{
    "Ollama API" = 11434
    "Open WebUI" = 3000
    "DeepSeek代理" = 8083
    "MiMo 700M代理" = 8084
    "MiMo 200M代理" = 8085
    "控制面板" = 8766
    "ComfyUI" = 8188
    "JupyterLab" = 8888
    "Portainer" = 9443
    "Draw.io" = 8082
    "Stirling PDF" = 8400
    "Zotero" = 23119
}

foreach ($svc in $services.GetEnumerator()) {
    try {
        $tcp = Get-NetTCPConnection -LocalPort $svc.Value -State Listen -ErrorAction SilentlyContinue
        if ($tcp) {
            Write-Host "  ✅ $($svc.Key) (:$($svc.Value))" -ForegroundColor Green
        } else {
            Write-Host "  ⚠️  $($svc.Key) (:$($svc.Value)) - 未启动" -ForegroundColor Yellow
        }
    } catch {
        Write-Host "  ⚠️  $($svc.Key) (:$($svc.Value)) - 未启动" -ForegroundColor Yellow
    }
}

Write-Host ""
Write-Host "🚀 工作站就绪！" -ForegroundColor Cyan
Write-Host "   WebUI:  http://127.0.0.1:3000"
Write-Host "   面板:   http://127.0.0.1:8766"
Write-Host "   监控:   https://127.0.0.1:9443"
