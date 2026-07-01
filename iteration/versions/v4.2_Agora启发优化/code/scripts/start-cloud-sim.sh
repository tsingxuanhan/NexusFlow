#!/bin/bash
# ============================================================
# 铉枢 · 云电脑模拟本机 — 一键启动
# 用途：在云电脑上完整模拟本机AI工作站环境
# 启动后所有服务端口与本机一致
# ============================================================

set -e
echo "🔍 铉枢 · 启动模拟环境..."

# 1. Start Docker services
echo "📦 启动Docker服务..."
cd /root/ai-workstation/docker/cloud-sim
docker compose up -d ollama open-webui portainer drawio
echo "  ✓ Docker服务已启动"

# 2. Start API Proxy Layer
echo "🔗 启动API代理层..."
if ! curl -s http://127.0.0.1:8083/health > /dev/null 2>&1; then
    cd /root/ai-workstation/api-proxy
    nohup python3 proxy.py > /tmp/proxy.log 2>&1 &
    sleep 2
fi
echo "  ✓ :8083 DeepSeek Gateway"
echo "  ✓ :8084 MiMo 700M Gateway"
echo "  ✓ :8085 MiMo 200M Gateway"

# 3. Start Control Panel
echo "🖥️ 启动控制面板..."
if ! curl -s http://127.0.0.1:8766 > /dev/null 2>&1; then
    cd /root/ai-workstation/control-panel
    nohup python3 -m http.server 8766 --bind 0.0.0.0 > /tmp/panel.log 2>&1 &
    sleep 1
fi
echo "  ✓ 控制面板 :8766"

# 4. Verify all services
echo ""
echo "============================================="
echo "  服务状态"
echo "============================================="

check() {
    local name=$1 port=$2
    status=$(curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:$port 2>/dev/null || echo "000")
    if [ "$status" = "200" ] || [ "$status" = "302" ]; then
        echo "  ✅ $name (:$port) - HTTP $status"
    else
        echo "  ⚠️  $name (:$port) - HTTP $status"
    fi
}

check "Ollama API" 11434
check "Open WebUI" 3000
check "DeepSeek代理" 8083
check "MiMo 700M代理" 8084
check "MiMo 200M代理" 8085
check "控制面板" 8766
check "Draw.io" 8080
check "Portainer" 19443

echo ""
echo "🚀 模拟环境就绪！"
echo "   WebUI: http://127.0.0.1:3000"
echo "   面板:  http://127.0.0.1:8766"
