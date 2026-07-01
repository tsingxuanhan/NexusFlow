# Examples

## Literature Mining

```python
from agents import MinerAgent

miner = MinerAgent()
papers = miner.search_papers("nano SiO2 supersulfated cement")
print(f"Found {len(papers)} papers")
```

## Code Generation

```python
from agents import CasterAgent

caster = CasterAgent()
code = caster.generate_code(
    "Plot compressive strength vs age",
    language="python"
)
```

## Research Pipeline

```python
from orchestrator import TaskOrchestrator

orch = TaskOrchestrator("research")

def search_task(**kwargs):
    return miner.search_papers("LC3 cement")

def validate_task(**kwargs):
    return assayer.verify(kwargs["search_result"])

orch.add_task("search", search_task)
orch.add_task("validate", validate_task, depends_on=["search"])
results = orch.execute()
```
