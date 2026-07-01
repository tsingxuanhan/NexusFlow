# API Reference

## BaseAgent

```python
from base_agent import BaseAgent

agent = BaseAgent(
    name="agent_name",
    model="pro",  # or "flash"
    system_prompt="You are a...",
    enable_checkpoint=True
)

result = agent.chat("user message")
agent.reset()
```

## TaskOrchestrator

```python
from orchestrator import TaskOrchestrator, ExecutionMode

orch = TaskOrchestrator("workflow_name")
orch.add_task("task1", func1, depends_on=[])
orch.add_task("task2", func2, depends_on=["task1"])
results = orch.execute(mode=ExecutionMode.SEQUENTIAL)
```

## Checkpoint

```python
from checkpoint import get_default_manager, SqliteCheckpointer

manager = get_default_manager(backend="sqlite", db_path="checkpoints.db")
```

## MCP Client

```python
from mcp_client import MCPClient, StdioTransport

client = MCPClient(transport=StdioTransport(command=["python", "tool.py"]))
tools = await client.list_tools()
result = await client.call_tool("tool_name", {"arg": "value"})
```
