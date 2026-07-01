---
name: base-agent
description: >
  xuanshu-agents 核心Agent基类。提供对话管理、流式回调、检查点/回滚、
  Handoff协作、熔断降级、Guardrails校验、Quality Dials旋钮、ReAct循环。
  当需要使用或扩展BaseAgent、创建自定义Agent、理解Agent生命周期时使用。
license: MIT
compatibility: Python 3.9+, requires config.py and DeepSeek API
metadata:
  version: "3.3.0"
  module: base_agent.py
  lines: ~1168
---

# Base Agent

xuanshu-agents 的核心类，所有 Agent 继承自 `BaseAgent`。

## 快速创建

```python
from base_agent import BaseAgent

agent = BaseAgent(
    name="my-agent",
    model="pro",           # "pro" | "flash" | 自定义模型名
    system_prompt="你是一个助手",
    enable_checkpoint=True  # 自动保存检查点
)
```

## 核心能力

| 方法 | 说明 |
|------|------|
| `chat(input, stream, on_chunk, on_complete)` | 对话（支持流式+回调） |
| `react(task, max_iterations)` | ReAct 推理-行动-观察循环 |
| `review(output, pipeline)` | 输出自检审查（Impeccable 风格） |
| `chat_with_review(input)` | 对话 + 自检一步到位 |
| `set_mode(mode)` | 切换行为模式 precise/creative/concise/thorough/balanced/cautious |
| `set_dials(creativity=, precision=, verbosity=, caution=)` | 微调质量旋钮 |
| `save_checkpoint()` / `load_checkpoint()` | 检查点保存/恢复 |
| `handoff_to(target)` | 协作交接 |
| `register_a2a_action()` | 注册 A2A 协议动作 |

## 质量旋钮 (Taste-Skill 风格)

旋钮自动映射到 LLM 生成参数：

| 旋钮 | 范围 | 映射 |
|------|------|------|
| creativity | 0.0-1.0 | temperature: 0.3~1.2 |
| precision | 0.0-1.0 | top_p: 0.7~1.0 |
| verbosity | 0.0-1.0 | max_tokens: 512~8192 |
| caution | 0.0-1.0 | prompt_suffix 条件约束 |

## 生命周期

```
__init__ → chat/react → Guardrails(入) → LLM调用 → Guardrails(出) → Review → 回调
         ↘ 检查点自动保存 (每N条消息)
         ↘ 熔断器保护 API 调用
         ↘ 自动降级 (pro → flash)
```

## 注意事项

- `chat()` 不指定 temperature 时，自动从 Quality Dials 推导
- 检查点默认每 5 条消息自动保存，可通过 `checkpoint_interval` 调整
- Guardrails 检测到反模式时默认 WARN 不 BLOCK，可在 `create_default_guardrails()` 中调整
