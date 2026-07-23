# 安全策略

## 支持的版本

| 版本 | 支持状态 |
|------|---------|
| 3.1.x | ✅ 当前维护 |
| 3.0.x | ⚠️ 安全补丁 |
| < 3.0 | ❌ 不再支持 |

## 报告漏洞

如果你发现了安全漏洞，请通过以下方式报告：

- **邮箱**：jing_dev@coze.email
- **GitHub Issue**：使用 [Security Advisory](https://github.com/tsingxuanhan/NexusFlow/security/advisories/new)（推荐，支持私密报告）

请提供以下信息：
1. 漏洞描述
2. 复现步骤
3. 影响范围
4. 如有可能，提供修复建议

## 安全实践

### API Key 管理

- **严禁硬编码**：所有 API Key 必须通过环境变量传递（`DEEPSEEK_API_KEY` 等）
- `.env` 文件已加入 `.gitignore`，不会被提交
- 配置模板参见 `.env.example`

### 依赖安全

- CI 流水线对每次 push 和 PR 运行依赖安全检查
- 使用 `.gitleaks.toml` 扫描 git 历史中的密钥泄露

### 端边云通信

- 端边云三层调度中，本地 Ollama 模型仅接受 `localhost` 连接
- DeepSeek API 通信使用 HTTPS 加密传输

## 已知限制

- Dashboard（端口 8900）默认无认证，仅限本地开发环境使用
- 生产环境部署时请自行添加认证层或限制网络访问
