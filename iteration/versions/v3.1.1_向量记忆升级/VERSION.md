# v3.1.1 — 向量记忆升级

**日期:** 2025年5月  
**核心变更:** 引入 NGramTFIDF 向量记忆，替代纯文本匹配

## 关键文件
| 文件 | 说明 |
|------|------|
| `memory.py` | 记忆管理器，集成 NGram+TF-IDF 向量检索 |
| `base_agent.py` | Agent基类，新增 hybrid_retrieve (RRF融合) |
| `checkpoint.py` | 检查点持久化 |

## 技术要点
- 不依赖 HuggingFace（外网不通），用 n-gram + TF-IDF 实现语义近似
- SlotMemory 槽位机制，冲突检测
- 混合检索：向量相似度 + 关键词匹配，RRF 融合排序

## 代码规模
13 个 Python 文件 · 3,511 行

> **注:** v3.1.1/v3.2/v3.3 共享同一归档基础代码，各版本差异体现在设计文档中描述的增量修改。
