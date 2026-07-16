---
name: a2a-protocol
description: >
  Agent-to-Agent协作协议。支持A2A标准消息、P2P直连通道(三种模式+TTL)、
  能力发现和任务委派。当需要多Agent协作、跨Agent通信、P2P消息传递时使用。
license: MIT
compatibility: Python 3.9+
metadata:
  version: "3.3.0"
  module: a2a_protocol.py
  lines: ~909
---

# A2A Protocol

Agent 间协作协议，两种通信模式：

## 广播模式 (A2ANetwork)

```
Agent A → Network → Agent B/C/D
```

- `send_message()` / `broadcast()`
- `find_agent_by_capability()` 能力发现
- `register_agent()` / `unregister_agent()`

## P2P 直连模式 (P2PChannel)

```
Agent A ←──channel──→ Agent B
```

三种通道模式：
| 模式 | 说明 |
|------|------|
| `direct` | 即时投递，无缓冲 |
| `buffered` | 缓冲队列，按序消费 |
| `priority` | 优先级队列，紧急消息优先 |

每个通道支持 TTL（消息过期时间）。

## 快速使用

```python
from a2a_protocol import A2ANetwork, P2PChannel

network = A2ANetwork()

# 注册Agent
network.register_agent(agent_a.a2a)
network.register_agent(agent_b.a2a)

# 建立P2P通道
channel = network.establish_p2p("agent_a", "agent_b", mode="buffered", ttl=300)

# 发送消息
network.send_p2p("agent_a", "agent_b", content={"task": "analyze"})

# 列出活跃通道
network.list_p2p_channels()
```

## 注意事项

- P2P 通道默认 TTL=300s，超时自动关闭
- `buffered` 模式适合异步任务，`priority` 模式适合紧急中断
- A2A 动作通过 `BaseAgent.register_a2a_action()` 注册
