---
name: quality-control
description: >
  Agent输出质量调控系统。灵感来自Taste-Skill(参数化旋钮)和Impeccable(自检命令+反模式)。
  提供QualityDials旋钮、AgentMode预设、ReviewPipeline自检管道。
  当需要控制Agent输出风格、自检质量、消除AI味时使用。
license: MIT
compatibility: Python 3.9+
metadata:
  version: "3.3.0"
  module: quality.py
  lines: ~528
  references:
    - "Taste-Skill (28.5K⭐) — 参数化品味旋钮"
    - "Impeccable (31.6K⭐) — 23条自检命令 + 反模式"
---

# Quality Control

灵感来源：
- **Taste-Skill** → QualityDials（可调旋钮控制输出风格）
- **Impeccable** → ReviewPipeline（自检/审查/精炼命令管道）

## Quality Dials (品味旋钮)

| 旋钮 | 范围 | 效果 |
|------|------|------|
| `creativity` | 0.0-1.0 | 0=严格模板, 1=大胆探索 |
| `precision` | 0.0-1.0 | 0=模糊概括, 1=数据支撑 |
| `verbosity` | 0.0-1.0 | 0=一句话, 1=详尽展开 |
| `caution` | 0.0-1.0 | 0=果断断言, 1=不确定性标注 |

旋钮自动映射到 LLM 参数 (temperature/top_p/max_tokens)。

## Agent Mode (行为模式预设)

| 模式 | creativity | precision | verbosity | caution |
|------|-----------|-----------|-----------|---------|
| `precise` | 0.2 | 0.9 | 0.6 | 0.6 |
| `creative` | 0.9 | 0.3 | 0.6 | 0.2 |
| `concise` | 0.3 | 0.5 | 0.1 | 0.3 |
| `thorough` | 0.4 | 0.9 | 0.9 | 0.6 |
| `balanced` | 0.5 | 0.5 | 0.5 | 0.5 |
| `cautious` | 0.2 | 0.8 | 0.5 | 0.9 |

## Review Pipeline (自检管道)

| 命令 | 说明 | 灵感 |
|------|------|------|
| `PatternAuditCommand` | 反模式审计 | Impeccable /audit |
| `StructureAuditCommand` | 结构完整性检查 | Impeccable /audit |
| `PolishCommand` | 格式精修 | Impeccable /polish |
| `DistillCommand` | 去冗余提炼 | Impeccable /distill |
| `BolderCommand` | 强化观点 | Impeccable /bolder |

三种预设管道：
- `create_default_pipeline()` — 反模式 + 结构 + 精修
- `create_strict_pipeline()` — 全部命令
- `create_quick_pipeline()` — 仅反模式 + 精修

## 使用

```python
from base_agent import BaseAgent
agent = BaseAgent(name="demo")

# 切模式
agent.set_mode("precise")

# 微调旋钮
agent.set_dials(creativity=0.8, verbosity=0.3)

# 自检
result = agent.review(output=text, pipeline="strict")
# → {"score": 0.85, "issues": [...], "suggestions": [...], "revised": ...}
```
