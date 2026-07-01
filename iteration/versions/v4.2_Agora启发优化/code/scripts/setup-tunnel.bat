@echo off
chcp 936 >nul 2>&1
title 铉枢·直连隧道
echo ============================================
echo   铉枢·炉守 — Cloudflare Tunnel 直连设置
echo ============================================
echo.

:: 检查cloudflared
where cloudflared >nul 2>&1
if %errorlevel% neq 0 (
    echo [!] 未检测到 cloudflared，正在下载...
    echo.
    powershell -Command "& {Invoke-WebRequest -Uri 'https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-windows-amd64.msi' -OutFile '%TEMP%\cloudflared.msi'}"
    echo [i] 正在安装 cloudflared...
    msiexec /i "%TEMP%\cloudflared.msi" /quiet /norestart
    timeout /t 3 >nul
    where cloudflared >nul 2>&1
    if %errorlevel% neq 0 (
        echo [X] 安装失败，请手动下载: https://github.com/cloudflare/cloudflared/releases
        pause
        exit /b 1
    )
    echo [✓] cloudflared 安装成功
)
echo [✓] cloudflared 已就绪
echo.

:: 检查本地服务
echo [i] 检测本地服务...
set AGENTOS_OK=0
set OLLAMA_OK=0
set WEBUI_OK=0

powershell -Command "try { $r = Invoke-WebRequest -Uri 'http://127.0.0.1:8000/health' -TimeoutSec 3 -UseBasicParsing; if($r.StatusCode -eq 200){exit 0} } catch {}" >nul 2>&1
if %errorlevel% equ 0 (
    echo   [✓] AgentOS  :8000 — 在线
    set AGENTOS_OK=1
) else (
    echo   [X] AgentOS  :8000 — 离线
)

powershell -Command "try { $r = Invoke-WebRequest -Uri 'http://127.0.0.1:11434/api/tags' -TimeoutSec 3 -UseBasicParsing; if($r.StatusCode -eq 200){exit 0} } catch {}" >nul 2>&1
if %errorlevel% equ 0 (
    echo   [✓] Ollama   :11434 — 在线
    set OLLAMA_OK=1
) else (
    echo   [X] Ollama   :11434 — 离线
)

powershell -Command "try { $r = Invoke-WebRequest -Uri 'http://127.0.0.1:8080' -TimeoutSec 3 -UseBasicParsing; if($r.StatusCode -eq 200){exit 0} } catch {}" >nul 2>&1
if %errorlevel% equ 0 (
    echo   [✓] OpenWebUI :8080 — 在线
    set WEBUI_OK=1
) else (
    echo   [X] OpenWebUI :8080 — 离线
)

echo.

:: 创建隧道配置
set CONFIG_DIR=%USERPROFILE%\.xuanshu
if not exist "%CONFIG_DIR%" mkdir "%CONFIG_DIR%"

echo [i] 创建多端口隧道配置...
(
echo tunnel: auto
echo credentials-file: %CONFIG_DIR%\tunnel.json
echo.
echo ingress:
echo   - hostname: "*"
echo     service: http://127.0.0.1:8000
echo   - service: http_status:404
) > "%CONFIG_DIR%\tunnel-config.yml"

echo.
echo ============================================
echo   隧道启动中...
echo   启动后请将生成的公网URL发给炉守（云端Agent）
echo   炉守即可通过该URL访问你的本机API
echo ============================================
echo.

:: 启动快速隧道（无需账户）
cloudflared tunnel --url http://127.0.0.1:8000

pause
