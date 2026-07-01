# v4.0 — 本机 AI 工作站

**日期:** 2025年6月-2026年5月  
**核心变更:** 从Agent框架扩展为完整AI工作站，工具生态+控制面板+AgentOS

## 核心新增（相比v3.3的13文件→68文件）

### 框架核心
| 文件 | 说明 |
|------|------|
| `base_agent.py` | 重写：2533行，chat/react/review/set_mode/set_dials/chat_with_review |
| `autonomous.py` | 自主目标分解+元认知 |
| `meta_cognition.py` | 元认知引擎 |
| `continuous_learning.py` | 持续学习系统 |
| `cross_domain.py` | 跨领域迁移 |
| `agentos.py` | AgentOS 操作系统层 |

### 记忆系统（Letta 3层）
| 文件 | 说明 |
|------|------|
| `core_memory.py` | 核心记忆 |
| `recall_memory.py` | 回忆记忆 |
| `archival_memory.py` | 归档记忆 |
| `sleeptime.py` | 睡眠时记忆整理 |
| `multi_hop_rag.py` | 多跳RAG |
| `vector_memory.py` | 向量记忆（1683行） |

### 工具生态（20+工具）
| 目录 | 说明 |
|------|------|
| `tools/` | code_exec, file_ops, web_search, browser, git_ops, data_query 等 |
| `control-panel/` | 液态玻璃UI控制面板（index/models/monitor/commands） |
| `demo/` | 架构浏览器demo，电路图风格可视化 |

### 质量与安全
| 文件 | 说明 |
|------|------|
| `guardrails.py` | 安全护栏系统 |
| `quality.py` | 质量控制引擎 |
| `circuit_breaker.py` | 熔断器 |
| `dead_letter_queue.py` | 死信队列 |

## 代码规模
68 个 Python 文件 · 25,773 行 · 146 个文件总计

## 技术要点
- 从纯Agent框架扩展为完整AI工作站
- Letta 3层记忆架构
- 工具生态系统（CodeAct优先）
- 液态玻璃UI控制面板
- AgentOS：本地服务编排
