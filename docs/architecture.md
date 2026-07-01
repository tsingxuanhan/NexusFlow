# Architecture Overview

## System Design

NexusFlow follows a layered architecture:

```
┌─────────────────────────────────────────────────────────┐
│                    Application Layer                    │
│     (Miner | Assayer | Caster | Artisan)                │
├─────────────────────────────────────────────────────────┤
│                    Orchestration Layer                  │
│         (TaskOrchestrator, HandoffManager)              │
├─────────────────────────────────────────────────────────┤
│                     Core Layer                          │
│      (BaseAgent, Memory, Checkpoint, Observability)      │
├─────────────────────────────────────────────────────────┤
│                   Protocol Layer                        │
│          (DeepSeek API, MCP Client)                    │
└─────────────────────────────────────────────────────────┘
```

## Core Components

### BaseAgent

Base class for all agents with:
- DeepSeek API integration
- Conversation management
- Error handling with automatic retry
- Checkpoint integration
- Handoff support

### TaskOrchestrator

DAG-based workflow executor:
- Sequential and parallel execution modes
- Dependency resolution
- Checkpoint saving

### Checkpoint Manager

State persistence:
- SQLite backend for durability
- In-memory for speed
- Automatic save/restore

### MCP Client

Model Context Protocol integration:
- Stdio transport for local tools
- HTTP transport for remote tools
- Tool schema validation

## Design Patterns

1. **Strategy Pattern**: Model selection (pro/flash)
2. **Observer Pattern**: Tracing and metrics
3. **Chain of Responsibility**: Handoff system
4. **Template Method**: Agent base class
