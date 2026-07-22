# Stage 4: 五十步长程任务实验

## 实验概述

50 步渐进式气候-健康关联分析任务，验证 NexusFlow 在超长程任务中的稳定性和质量闭环能力。

## 目录结构

```
stage4_fifty_steps/
├── engine.py                 # 主引擎（可执行）
├── artifacts/                # ⚠️ 步骤产物样本
├── data/
│   ├── artifacts/            # ⚠️ 步骤产物样本
│   └── scripts/              # 批量执行脚本（可执行）
└── README.md
```

## ⚠️ 关于 artifacts/ 目录中的 .py 文件

`artifacts/` 和 `data/artifacts/` 目录下的 `.py` 文件 **不是可执行的 Python 脚本**。它们是 50 步任务执行过程中各步骤的**产物样本**，记录了每一步 Agent 生成的代码片段和分析内容。

这些文件的内容格式为：
- Markdown 代码块（以 ` ```python ` 开头）
- 中文描述文本 + 嵌入代码
- LLM 生成的代码框架描述

如果需要查看可执行的脚本，请参考：
- `engine.py` — 50步任务主引擎
- `data/scripts/batch*.py` — 分批次执行脚本
- `data/scripts/engine.py` — 批处理引擎

## 运行方式

```bash
# 50步主引擎
python examples/stage4_fifty_steps/engine.py

# 批量执行
python examples/stage4_fifty_steps/data/scripts/batch1.py
```
