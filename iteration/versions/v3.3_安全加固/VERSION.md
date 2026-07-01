# v3.3 — 安全加固

**日期:** 2025年6月  
**核心变更:** API密钥管理安全化，MCP客户端集成

## 关键文件
| 文件 | 说明 |
|------|------|
| `config.py` | 配置管理，密钥走环境变量 |
| `mcp_client.py` | MCP协议客户端 |
| `base_agent.py` | Agent基类，Guardrails安全护栏 |

## 技术要点
- 所有API Key改为环境变量读取，禁止硬编码
- MCP客户端：Model Context Protocol 工具调用
- 安全护栏：输入/输出校验，防止注入

## 代码规模
13 个 Python 文件 · 4,084 行

> **注:** 相比v3.2新增mcp_client.py，config.py重构为环境变量模式。
