---
name: guardrails
description: >
  输入/输出安全校验系统。支持注入检测、长度限制、敏感内容过滤、工具权限控制、
  AI反模式检测(AntiPatternOutputGuard)。当需要Agent安全防护、输入过滤、
  输出质量拦截时使用。
license: MIT
compatibility: Python 3.9+
metadata:
  version: "3.3.0"
  module: guardrails.py
  lines: ~505
---

# Guardrails

Agent 安全校验层，链式执行 + 短路阻断。

## 架构

```
Input → [InjectionGuard] → [LengthGuard] → Agent → [OutputGuard] → [AntiPatternGuard] → Output
                                                        ↘ [SensitiveContentGuard]
Tool调用 → [ToolPermissionGuard]
```

## Guardrail 类型

| Guard | 类型 | 说明 |
|-------|------|------|
| `PromptInjectionGuard` | Input | 检测提示注入 |
| `InputLengthGuard` | Input | 输入长度限制 |
| `OutputLengthGuard` | Output | 输出长度限制 |
| `SensitiveContentGuard` | Output | 敏感内容过滤/遮蔽 |
| `AntiPatternOutputGuard` | Output | AI反模式检测 (Impeccable/Taste-Skill) |
| `ToolPermissionGuard` | Tool | 工具调用权限控制 |

## 动作类型

| Action | 行为 |
|--------|------|
| `PASS` | 通过 |
| `WARN` | 警告但放行 |
| `BLOCK` | 阻断 |
| `MODIFY` | 修改后放行 |

## 反模式检测

`AntiPatternOutputGuard` 检测 8 类 AI 输出反模式：
- `ai_disclaimer` — "作为AI语言模型..."
- `generic_summary` — "综上所述，我..."
- `hedge_overuse` — "需要注意的是..."
- `enumeration_fatigue` — 机械枚举
- `intensity_inflation` — "至关重要"
- `contextual_padding` — 填充性背景句
- `trivial_assertion` — "毋庸置疑"
- `qualifier_chain` — 限定词链

三种模式: `warn`(默认) / `modify` / `block`

## 注意事项

- 反模式检测与 `quality.py` 的 `PatternAuditCommand` 检测相同模式但接口不同
- Guardrail 层自动拦截（chat 流程内），Review 层按需深度审查
- 自定义 Guard 只需继承 `InputGuardrail`/`OutputGuardrail`/`ToolGuardrail`
