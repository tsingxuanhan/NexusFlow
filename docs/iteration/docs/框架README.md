# xuanshu-agents

> Agent 框架 v4.0 — 从"能用"到"好用"到"有品味"到"自主进化"

基于 DeepSeek API 的多 Agent 协作框架，面向科研场景，强调安全、质量和可观测性。

## 架构

```
                     ┌──────────────────────────────────────┐
                     │           AgentOS (FastAPI)          │
                     │    ┌─────────────────────────┐       │
                     │    │     自主目标处理器        │       │
                     │    │  6阶段: 感知→分析→规划    │       │
                     │    │  →执行→验证→反思          │       │
                     │    └─────────────────────────┘       │
                     └──────────────┬───────────────────────┘
                                    │
          ┌─────────────────────────┼─────────────────────────┐
          │                         │                         │
   ┌──────▼──────┐          ┌──────▼──────┐          ┌──────▼──────┐
   │  矿工(Miner) │          │  铸师(Caster)│          │  匠人(Artisan)│
   │  DeepSeek Pro│          │  DeepSeek Pro│          │ DeepSeek Flash│
   │  文献挖掘     │          │  方案生成     │          │  成果整合      │
   └──────┬──────┘          └──────┬──────┘          └──────┬──────┘
          │                         │                         │
   ┌──────▼──────┐          ┌──────▼──────┐          ┌──────▼──────┐
   │  试金(Assayer)│         │  规划师(Planner)│        │  审查员(Reviewer)│
   │  DeepSeek Flash│        │  DeepSeek Pro │         │ DeepSeek Flash  │
   │  数据验证      │         │  任务拆解      │         │  质量审核        │
   └─────────────┘          └─────────────┘          └─────────────┘
```

## v4.0 核心升级

| Phase | 主题 | 关键交付 |
|-------|------|---------|
| 1 | 泛化基建 | CodeAct优先 + BaseAgent重构 |
| 2 | 规划引擎 | TeLLAgent双Agent分离 + TaskTree |
| 3 | 工具生态 | MCP Client/Server v2 + A2A Protocol |
| 4 | 知识记忆 | 3层记忆 + 10领域知识库 + Sleeptime |
| 5 | AGI能力 | 自主目标处理器 + 元认知 + 跨领域迁移 |

## Open Design 集成 (Phase 1)

v4.0 新增 Open Design MCP 桥接，支持品牌级 UI 原型和演示文稿生成：

- `tools/od_design_tool.py` — 10个MCP设计工具桥接
- `config/open_design_mcp.json` — MCP Client配置
- `scripts/test_od_mcp.py` — 连通性测试
- `docs/open_design_setup.md` — Daemon部署指南

## 快速开始

```python
from tools import register_od_tools
from tools.tool_registry import ToolRegistry

registry = ToolRegistry()
register_od_tools(registry)  # 注册OD设计工具
```

## 核心模块

| 模块 | 说明 |
|------|------|
| `base_agent.py` | Agent基类：chat/react/review + Guardrails + Quality |
| `autonomous.py` | 自主目标6阶段处理器 |
| `meta_cognition.py` | 元认知(HIGH/MED/LOW) + 自适应策略 |
| `cross_domain.py` | 跨领域迁移(8种子类比) |
| `continuous_learning.py` | 持续学习双路径(微调+知识蒸馏) |
| `agentos.py` | AgentOS运行时(FastAPI + stdio) |
| `mcp_client_v2.py` | MCP 2026-07协议 + Tasks原语 |
| `a2a_protocol.py` | Agent-to-Agent发现与协作 |
| `vector_memory.py` | NGramTFIDF + Hybrid RRF检索 |

## 8大Agent角色

矿工(文献挖掘) · 试金(数据验证) · 铸师(方案生成) · 匠人(成果整合) ·
规划师(任务拆解) · 审查员(质量审核) · 研究员(信息检索) · 艺术家(设计生成)

## 依赖

```
pip install -r requirements.txt
```

## 许可

私有仓库，未授权禁止使用。
