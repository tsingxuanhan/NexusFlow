# v3.2 — Agent 架构优化

**日期:** 2025年5-6月  
**核心变更:** 四角色矿工/试金/铸师/匠人架构成型，A2A协议+Handoff

## 关键文件
| 文件 | 说明 |
|------|------|
| `agents/miner.py` | 矿工Agent — 文献/数据收集 |
| `agents/assayer.py` | 试金Agent — 数据验证 |
| `agents/caster.py` | 铸师Agent — 方案生成 |
| `agents/artisan.py` | 匠人Agent — 成果整合 |
| `handoff.py` | Agent间任务交接 |
| `orchestrator.py` | 编排调度器 |

## 技术要点
- 四角色分工：矿工(pro)→试金(flash)→铸师(pro)→匠人(flash)
- Handoff 机制：能力发现 + 任务委派 + 结果回收
- A2A 网关：跨Agent通信

## 代码规模
13 个 Python 文件 · 3,511 行

> **注:** 此版本架构设计是后续所有版本的基础。
