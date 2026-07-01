#!/bin/bash
# 铉枢·炉守 — Hub控制面板云端部署脚本
# 部署到Cloudflare Pages（免费自定义域名+SSL）

set -e
PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
DEMO_DIR="$PROJECT_DIR/demo"

echo "========================================"
echo "  xuanshu-agents Hub 云端部署"
echo "========================================"
echo ""

# 检查wrangler
if ! command -v npx &>/dev/null; then
    echo "需要Node.js和npm，请先安装"
    exit 1
fi

echo "[1/4] 安装wrangler..."
npx wrangler --version 2>/dev/null || npm install -g wrangler

echo "[2/4] 登录Cloudflare..."
npx wrangler login

echo "[3/4] 部署到Cloudflare Pages..."
npx wrangler pages project create xuanshu-agents-hub --production-branch main 2>/dev/null || true
npx wrangler pages deploy "$DEMO_DIR" --project-name xuanshu-agents-hub --branch main

echo "[4/4] 自定义域名设置..."
echo ""
echo "部署完成！接下来："
echo "1. 去 Cloudflare Dashboard → Pages → xuanshu-agents-hub → Custom domains"
echo "2. 添加你的自定义域名（如 hub.xuan-hub.com）"
echo "3. Cloudflare会自动配置DNS和SSL证书"
echo ""
echo "或者用命令行："
echo "  npx wrangler pages project custom-domain xuanshu-agents-hub hub.你的域名.com"
