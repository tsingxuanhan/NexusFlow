@echo off
chcp 65001 >nul
echo.
echo ==========================================================
echo   NexusFlow Dashboard v3 - One-Click Deploy
echo ==========================================================
echo.

:: === LLM Configuration ===
:: DeepSeek Cloud API - 6 agents: Coordinator/Strategist/Archivist/Critic/Synthesizer/Researcher
:: Load from .env file if exists
if exist "%~dp0.env" (
    for /f "usebackq tokens=1,2 delims==" %%a in ("%~dp0.env") do (
        if "%%a"=="DEEPSEEK_API_KEY" set DEEPSEEK_API_KEY=%%b
    )
)
if not defined DEEPSEEK_API_KEY (
    echo [ERROR] DEEPSEEK_API_KEY not set!
    echo Please create config\.env file with your API key.
    echo See config\.env.example for reference.
    pause
    exit /b 1
)
set DEEPSEEK_ENDPOINT=https://api.deepseek.com/v1/chat/completions

:: Ollama Local - 5 agents: Coder/Researcher/Analyst/Observer/Monitor
set OLLAMA_URL=http://localhost:11434
set OLLAMA_PRO_MODEL=deepseek-r1:14b
set OLLAMA_FLASH_MODEL=qwen3.5:9b

:: Ollama Parallel Settings (Critical for CDoL multi-agent concurrency!)
set OLLAMA_NUM_PARALLEL=4
set OLLAMA_MAX_LOADED_MODELS=2
set OLLAMA_FLASH_ATTENTION=1

:: Server
set NEXUSFLOW_PORT=8900

:: Write .env file for Python dotenv loading
(
echo DEEPSEEK_API_KEY=%DEEPSEEK_API_KEY%
echo DEEPSEEK_ENDPOINT=https://api.deepseek.com/v1/chat/completions
echo OLLAMA_URL=http://localhost:11434
echo OLLAMA_PRO_MODEL=deepseek-r1:14b
echo OLLAMA_FLASH_MODEL=qwen3.5:9b
echo OLLAMA_NUM_PARALLEL=4
echo OLLAMA_MAX_LOADED_MODELS=2
echo NEXUSFLOW_PORT=8900
) > "%~dp0.env"

:: Check Python
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python not found. Install Python 3.10+
    echo https://www.python.org/downloads/
    pause
    exit /b 1
)

echo [1/4] Installing dependencies...
pip install fastapi uvicorn aiohttp websockets python-dotenv --quiet 2>nul
if %errorlevel% neq 0 (
    pip install fastapi uvicorn aiohttp websockets python-dotenv --user --quiet
)

echo [2/4] Checking Ollama...
tasklist /FI "IMAGENAME eq ollama.exe" 2>nul | find "ollama" >nul
if %errorlevel% neq 0 (
    echo [WARN] Ollama is not running!
    echo        Start Ollama first, then re-run this script.
    pause
    exit /b 1
)

echo [3/4] Checking Ollama API...
curl -s http://localhost:11434/api/tags >nul 2>&1
if %errorlevel% neq 0 (
    echo [WARN] Ollama API unreachable. Run: ollama serve
) else (
    echo [OK] Ollama API reachable
    echo      Pro model:   deepseek-r1:14b  (Coder, Researcher)
    echo      Flash model: qwen3.5:9b       (Analyst, Observer, Monitor)
    echo      Parallel:    4 requests/model, 2 models loaded
)

echo [4/4] Starting NexusFlow Server...
echo.
echo ==========================================================
echo   Dashboard:    http://localhost:8900
echo   API Docs:     http://localhost:8900/docs
echo ----------------------------------------------------------
echo   Cloud (DeepSeek API):
echo     Coordinator / Strategist / Archivist / Critic / Synthesizer
echo   Local Ollama (deepseek-r1:14b, ~9GB VRAM):
echo     Coder / Researcher
echo   Local Ollama (qwen3.5:9b, ~6.6GB VRAM):
echo     Analyst / Observer / Monitor
echo   Total VRAM: ~15.6GB / 16GB
echo ==========================================================
echo.

python "%~dp0..\server\nexusflow_server.py"
