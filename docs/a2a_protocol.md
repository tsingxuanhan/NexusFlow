# A2A Protocol Guide

> Agent-to-Agent Communication in NexusFlow v3.2

## Overview

The A2A (Agent-to-Agent) protocol enables native inter-agent communication in NexusFlow. Unlike traditional request-response patterns, A2A provides:

- **Auto-registration**: Agents automatically expose their capabilities
- **Capability-based routing**: Tasks are routed based on capability matching
- **Async messaging**: Non-blocking communication between agents
- **Handoff bridge**: Seamless fallback when direct handoff is unavailable

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                      A2A Network                            │
│  ┌─────────────────────────────────────────────────────┐    │
│  │              Capability Registry                      │    │
│  │  - Miner: [search_papers, mine_papers]               │    │
│  │  - Assayer: [verify_entry, cross_check]             │    │
│  │  - Caster: [generate_code, review_code]             │    │
│  │  - Artisan: [explain_concept, answer_question]       │    │
│  └─────────────────────────────────────────────────────┘    │
│                          │                                 │
│  ┌───────────────────────┼───────────────────────┐         │
│  │           Message Router                          │         │
│  │   Routes requests based on capability match       │         │
│  └───────────────────────┬───────────────────────┘         │
│                          │                                 │
│  ┌───────────────────────┴───────────────────────┐         │
│  │           Handoff Bridge                         │         │
│  │   Falls back to A2A when Handoff unavailable    │         │
│  └─────────────────────────────────────────────────┘         │
└─────────────────────────────────────────────────────────────┘
```

## Usage

### 1. Create Agent Team

```python
from agents import create_team, a2a_network

# Create team with auto-registered capabilities
team = create_team()

# Query network status
status = a2a_network.get_network_status()
print(f"Agents: {status['registered_agents']}")
for agent in status['agents']:
    print(f"  {agent['name']}: {agent['capabilities']}")
```

### 2. Direct A2A Request

```python
# Miner requests verification from Assayer
miner = team["miner"]

task_request = miner.a2a.create_task_request(
    receiver_id="assayer",
    action="verify_entry",
    parameters={
        "entry": "Super-sulfated cement contains 80-85% GGBS",
        "entry_id": "ssc_001"
    }
)

# Send request
response = a2a_network.send_message(task_request)
print(f"Status: {response.status}")
print(f"Result: {response.content}")
```

### 3. Get Network Topology

```python
from collaboration import get_network_topology

topology = get_network_topology()
print(f"Total Agents: {topology['total_agents']}")

for agent in topology["agents"]:
    print(f"\n[{agent['role'].upper()}] {agent['name']}")
    for cap in agent["capabilities"]:
        print(f"  - {cap['name']}: {cap['description']}")
```

### 4. Handoff Bridge

When a handoff target is unavailable, the system automatically bridges to A2A:

```python
# Miner attempts handoff to "verify_entry"
# If Assayer is registered, uses native handoff
# Otherwise, falls back to A2A request
result = miner.handoff_to(
    target="verify_entry",
    request="Verify SSC composition claims"
)
```

## Capability Definition

Agents define capabilities with metadata:

```python
class MinerAgent(BaseAgent):
    CAPABILITIES = [
        Capability(
            name="search_papers",
            description="Deep literature search",
            keywords=["paper", "search", "literature", "research"]
        ),
        Capability(
            name="mine_papers",
            description="Extract structured data from papers",
            keywords=["extract", "data", "structure"]
        )
    ]
```

## Message Format

```python
@dataclass
class A2AMessage:
    task_id: str              # Unique task identifier
    sender_id: str             # Sender agent ID
    receiver_id: str           # Target agent ID
    action: str                # Capability action name
    parameters: Dict           # Action parameters
    priority: MessagePriority  # HIGH/NORMAL/LOW
    timeout: int               # Seconds before timeout
    metadata: Dict             # Additional metadata
```

## Error Handling

```python
# Timeout handling
try:
    response = a2a_network.send_message(request, timeout=30)
except A2ATimeoutError:
    print("Agent did not respond in time")

# Capability not found
try:
    a2a_network.send_message(request)
except CapabilityNotFoundError:
    print("No agent supports this capability")
```

## Best Practices

1. **Use Orchestrator for complex workflows** - Chains multiple A2A calls
2. **Set appropriate timeouts** - Heavy tasks need longer timeouts
3. **Handle failures gracefully** - Implement retry logic
4. **Log A2A interactions** - For debugging and optimization
