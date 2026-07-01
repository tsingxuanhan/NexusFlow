# xuanshu-agents Hub → Cloudflare Pages 部署指南

## 前置条件
- Cloudflare账号（免费版即可）
- GitHub账号（仓库已公开或私有均可）

## 步骤

### 1. 登录Cloudflare Dashboard
访问 https://dash.cloudflare.com → 左侧菜单 → Workers & Pages

### 2. 创建Pages项目
1. 点击 **Create** → **Pages** → **Connect to Git**
2. 选择 **GitHub** → 授权连接
3. 选择仓库: `tsingxuanhan/nexusflow`（公开仓库，推荐）或 `xuan-hub`（私有）
4. 配置构建设置:
   - **Framework preset**: None
   - **Build command**: 留空
   - **Build output directory**: `demo`
   - **Root directory**: `/`
5. 点击 **Save and Deploy**

### 3. 自动部署
Cloudflare会自动部署，之后每次push到main分支都会自动重新部署。

### 4. 免费子域名
部署成功后，Cloudflare会自动分配一个 `*.pages.dev` 子域名。

### 5. 绑定自定义域名（可选）
1. 在Pages项目设置 → **Custom domains**
2. 添加 `hub.xuan-hub.com`
3. Cloudflare会自动配置DNS和SSL证书

## 后续更新
只需 `git push` 到main分支，Cloudflare Pages会自动检测并重新部署。

## 当前部署文件
- `demo/hub.html` — 主控制面板（双模式：云端预览+一键本地化）
- `demo/arch-explorer.html` — 架构浏览器
- `demo/v4-dashboard.html` — v4仪表盘
- `demo/a2a-network.html` — A2A网络可视化
- `demo/index.html` — 入口重定向
- `demo/404.html` — 404重定向
- `demo/_redirects` — SPA路由配置
