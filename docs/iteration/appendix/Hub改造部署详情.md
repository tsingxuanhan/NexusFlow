# xuanshu-agents Hub 改造与部署详情

## 改造内容（2026-06-10）
### 1. 页面标题和Meta标签
- 标题改为 "xuanshu-agents Hub — AI Agent 控制面板"
- 添加了 description、og:title、og:description、og:type meta标签
- 添加了内联 SVG favicon（紫色六边形）

### 2. CSS样式（新增约120行）
- `.mode-banner` - 双模式横幅样式（蓝色信息风格）
- `.mode-banner.local-mode` - 本地模式绿色风格
- `.localize-btn` - 一键本地化按钮样式
- `.mode-indicator` - Settings页面模式指示器
- `.api-endpoint-disabled` - 禁用输入框样式

### 3. HTML结构修改
- 替换 `offlineBanner` 为 `modeBanner`（双模式横幅）
- 在 `sidebar-footer` 添加一键本地化按钮

### 4. Settings页面修改
- 添加模式指示器（显示云端/本地状态）
- API端点输入框在云端模式下禁用
- 添加"测试云端演示状态"按钮

### 5. JavaScript核心逻辑
**新增函数：**
- `getConnectionMode()` - 获取当前连接模式
- `setConnectionMode(mode)` - 设置并保存模式
- `updateUIForMode(mode)` - 更新UI显示
- `toggleConnectionMode()` - 切换连接模式
- `checkLocalAgentOS()` - 检测本地AgentOS（2秒超时）
- `refreshAllPanels()` - 刷新所有面板
- `testCloudDemo()` - 测试云端演示
- `initializeConnectionMode()` - 初始化连接模式

**修改函数：**
- `apiRequest()` - 云端模式直接返回mock，本地模式失败降级mock
- `getMockData()` - 增强演示数据（更多任务、工具、模型等）
- `saveSettings()` - 保存模式设置
- `loadSettings()` - 恢复模式设置

### 6. 增强的Mock数据
- **health**: 包含version、uptime递增、mode、timestamp
- **stats**: 包含趋势数据（requests_trend、avg_response_time等）
- **models**: 5个真实模型名（qwen3.5:9b、qwen3-coder:30b等）
- **tasks**: 6个不同状态的任务（含失败任务示例）
- **core**: 完整的Core Memory示例
- **tools**: 8个工具（web_search、file_ops、calculator等）
- **gaps**: 4个知识盲区（含优先级）

## 部署过程
1. 代码推送到GitHub仓库 tsingxuanhan/nexusflow
2. 尝试Cloudflare Pages部署遇浏览器加载问题，切换到GitHub Pages
3. 将demo目录内容移到docs目录，通过API开启GitHub Pages
4. 部署完成，访问地址：https://tsingxuanhan.github.io/nexusflow/

## 访问说明
- 云端模式：使用模拟数据展示所有面板功能
- 本地模式：点击「一键本地化」按钮，输入本机AgentOS地址切换到真实API模式