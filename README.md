# NexusFlow

> Dynamic Cognitive Topology Engine for Ultra-Long-Horizon Multi-Agent Collaborative Reasoning

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.9+](https://img.shields.io/badge/Python-3.9+-blue.svg)](https://www.python.org/)
[![Lines](https://img.shields.io/badge/Lines-35000+-orange.svg)]()
[![Phase](https://img.shields.io/badge/Phase-7-blue.svg)]()

## What is NexusFlow?

NexusFlow is a **dynamic heterogeneous multi-agent framework** that solves ultra-long-horizon complex tasks through **cognitive division of labor** and **adaptive context management**. Built on 7 iterative phases of development (27,000+ lines), it goes beyond traditional "decompose-and-execute" patterns by enabling genuine deep collaborative reasoning.

**Key Innovation:** Information asymmetry between agents is not a deficiency — it's a *resource*. By constraining what each agent can see, we force cognitive processes that no single agent (even with complete information) could achieve alone.

## Core Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    NexusFlow Dynamic Cognitive Topology                  │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  ┌──────────────────────────────────────────────────────────────────┐  │
│  │              PlannerAgent (Task Decomposition)                    │  │
│  │  Goal → TaskTree → Auto-detect CDoL nodes → Route              │  │
│  └──────────────────────┬───────────────────────────────────────────┘  │
│                         │                                               │
│  ┌──────────────────────┴───────────────────────────────────────────┐  │
│  │            DynamicTopologyRouter (Phase 6)                        │  │
│  │  ┌─────────────┐  ┌──────────────┐  ┌──────────────────────┐    │  │
│  │  │ Capability   │  │ Load-Aware   │  │ Experience Learning  │    │  │
│  │  │ Matching     │  │ Scheduling   │  │ & Pattern Cache      │    │  │
│  │  └─────────────┘  └──────────────┘  └──────────────────────┘    │  │
│  │                         │                                         │  │
│  │         ┌───────────────┼───────────────┐                        │  │
│  │         │ Sequential    │ CDoL Mode     │                        │  │
│  │         │ (star/chain)  │ (perspective  │                        │  │
│  │         │               │  decomposition│                        │  │
│  │         └───────────────┴───────────────┘                        │  │
│  └──────────────────────────────────────────────────────────────────┘  │
│                                                                          │
│  ┌──────────────────────────────────────────────────────────────────┐  │
│  │        Cognitive Division Engine (Phase 7 — Core Innovation)      │  │
│  │                                                                    │  │
│  │   PerspectiveDecomposer → CommunicationLayer → FusionJudge        │  │
│  │                                                                    │  │
│  │   Round 0: Independent reasoning (isolated context masks)         │  │
│  │   Round 1: Difference attribution (share conclusions, not data)   │  │
│  │   Round 2: Correction & convergence                               │  │
│  │   → False consensus detection (compare reasoning chains, not answers)│
│  └──────────────────────────────────────────────────────────────────┘  │
│                                                                          │
│  ┌──────────────────────────────────────────────────────────────────┐  │
│  │        Adaptive Context Manager (Phase 7)                         │  │
│  │                                                                    │  │
│  │   LocalContextWindow ← AdaptiveWindowController ← LazinessDetector│  │
│  │        │                                                           │  │
│  │   GlobalMemoryPool ← ForcedGlobalSync ← RetrievalHeadAgent        │  │
│  │                                                                    │  │
│  │   "Small window + NoPE" strategy: constrain local view,           │  │
│  │   periodically force global awareness injection                    │  │
│  └──────────────────────────────────────────────────────────────────┘  │
│                                                                          │
│  ┌──────────────────────────────────────────────────────────────────┐  │
│  │           Edge-Cloud Scheduler (Phase 6)                          │  │
│  │   Edge (Device) ←→ Fog (Gateway) ←→ Cloud (Server)              │  │
│  │   Privacy-first scheduling · 5 scheduling policies                │  │
│  └──────────────────────────────────────────────────────────────────┘  │
│                                                                          │
│  ┌──────────────────────────────────────────────────────────────────┐  │
│  │     Foundation: BaseAgent · A2A Protocol · Letta Memory System    │  │
│  │     8 specialized agents · 12 built-in tools · Guardrails        │  │
│  └──────────────────────────────────────────────────────────────────┘  │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

## 7 Phases of Evolution

| Phase | Focus | Key Modules |
|-------|-------|-------------|
| **1** | Generalization Infrastructure | TaskTree decomposition, Tree-of-Thought, Self-reflection |
| **2** | Planning Engine | Planner/Executor separation, Adaptive strategy |
| **3** | Tool Ecosystem | CodeAct execution, 12 tools, MCP v2 |
| **4** | Knowledge & Memory | Letta 3-Layer Memory, Sleeptime consolidation, Multi-Hop RAG |
| **5** | AGI Core | Autonomous processor, Meta-cognition, Cross-domain transfer, AgentOS |
| **6** | Dynamic Swarm Intelligence | DynamicTopologyRouter, EdgeCloudScheduler, NexusFlow Dashboard |
| **7** | Deep Collaborative Reasoning | CognitiveDivisionEngine, AdaptiveContextManager, False Consensus Detection |

## Phase 7: Core Innovations

### 1. Cognitive Division of Labor (CDoL) Engine

Traditional multi-agent systems share all information with all agents. CDoL does the opposite:

**The Theoretical Flip:**
- Classical view: information asymmetry is a problem to be solved
- CDoL view: information asymmetry is a *cognitive resource* to be exploited

**How it works:**
1. **PerspectiveDecomposer** splits a task into isolated viewpoints (6 strategies: evidence-split, role-constraint, layer-separation, modality-split, time-slice, abstraction-level)
2. Each agent receives a `ContextMask` — only sees a subset of the problem
3. **Round 0:** Independent reasoning in isolation
4. **Round 1:** Share intermediate conclusions (not raw data) via lossy communication channel
5. **Round 2:** Attribution & correction
6. **FusionJudge** detects 4 types of contradictions, including **false consensus** (same conclusion, contradictory reasoning paths)

**Why it matters:** The collaborative gain comes from the cognitive process *forced* by information constraints — the upper bound exceeds any single agent, even one given complete information.

### 2. Adaptive Context Manager

Inspired by Tsinghua & OpenBMB's hybrid attention research (2026), addressing the "large window laziness" problem:

- **LazinessDetector** monitors 4 indicators: retrieval frequency, correction rate, confidence trend, information source diversity
- **AdaptiveWindowController** dynamically adjusts context window size (512 → 32768)
- **GlobalMemoryPool** serves as horizontal convergence layer across all agents
- **ForcedGlobalSync** periodically injects global summaries (NoPE strategy: "small window + no positional encoding = forced global awareness")
- **RetrievalHeadAgent** specialized retrieval-only agent for bridging information gaps

### 3. Seamless Architecture Integration

Both modules surgically embed into the existing 6-layer architecture through precisely defined injection points — no module stacking, clean backward compatibility.

## Agent Roles

| Agent | Role | Specialization |
|-------|------|---------------|
| **Miner** | Literature Explorer | Deep research, paper discovery, knowledge mining |
| **Assayer** | Knowledge Validator | Cross-verification, fact-checking, quality audit |
| **Caster** | Code Engineer | Script generation, data processing, automation |
| **Artisan** | Domain Expert | Field-specific Q&A, concept explanation |
| **Planner** | Strategy Architect | Task decomposition, CDoL node detection |
| **Executor** | Action Runner | CodeAct-first execution, tool orchestration |
| **Researcher** | Deep Analyst | Multi-source investigation, evidence synthesis |
| **Reviewer** | Quality Gate | Output validation, consistency check |

## Module Overview

| Module | Lines | Phase | Description |
|--------|-------|-------|-------------|
| **BaseAgent** | ~2600 | 1-7 | Core agent + context window hooks |
| **VectorMemory** | ~1700 | 4 | NGram+TF-IDF hybrid retrieval |
| **A2A Protocol** | ~1030 | 1,7 | Inter-agent + 6 CDOL message types |
| **CognitiveDivisionEngine** | ~1500 | 7 | Perspective decomposition + fusion |
| **AdaptiveContextManager** | ~1520 | 7 | Window control + laziness detection |
| **DynamicTopologyRouter** | ~870 | 6 | NetworkX-based dynamic routing |
| **EdgeCloudScheduler** | ~535 | 6 | Edge-Fog-Cloud scheduling |
| **Autonomous** | ~780 | 5 | 6-stage goal processor |
| **Meta-Cognition** | ~680 | 5 | Self-assessment system |
| **AgentOS** | ~640 | 5 | FastAPI + stdio server |
| **RecallMemory** | ~610 | 4 | Episodic memory with temporal indexing |
| **ArchivalMemory** | ~600 | 4 | Compressed long-term storage |
| **TaskTree** | ~620 | 1,7 | Task decomposition + CDoL markers |
| **Cross-Domain** | ~590 | 5 | Analogical transfer (8 seeds) |
| **MemoryManager** | ~510 | 4,7 | 3-layer + Global Pool |
| **NexusFlow Demo** | ~590 | 6,7 | Full demonstration |
| **Dashboard** | ~370 | 6 | Real-time monitoring UI |

**Total: 35,000+ lines across 40+ modules**

## Quick Start

### Basic Usage

```python
from nexusflow import BaseAgent

agent = BaseAgent(
    name="research_assistant",
    model="pro",
    system_prompt="You are a scientific research assistant"
)

reply = agent.chat("Explain the mechanical properties of LC3 cement")
```

### Cognitive Division Demo

```python
from nexusflow import CognitiveDivisionEngine
from demo.nexusflow_demo import demo_cognitive_division

# Run the full CDoL demonstration
# Simulates a low-carbon cement formulation decision
# with 3 agents in isolated perspectives
result = demo_cognitive_division()
```

### Adaptive Context Demo

```python
from demo.nexusflow_demo import demo_adaptive_context

# Shows window size adaptation + laziness detection
# across 10 simulation steps
demo_adaptive_context()
```

### Autonomous Mode

```python
from nexusflow import AutonomousProcessor

processor = AutonomousProcessor(agent)
result = processor.process(
    "Design an experiment to test SSC with different nano-SiO₂ dosages"
)
# Intent → Decompose → Plan → Execute → Verify → Report
```

## Configuration

All credentials via environment variables — **no hardcoded secrets**:

```bash
export LLM_API_KEY="sk-your-key-here"
export LLM_ENDPOINT="http://127.0.0.1:8083/v1/chat/completions"
```

### Phase 7 Configuration (config.example.py)

```python
# Cognitive Division Engine
CDOL_ENABLED = True
CDOL_MAX_ROUNDS = 2              # Max communication rounds
CDOL_MIN_BRIDGEABILITY = 0.3     # Min bridgeability threshold
CDOL_FALSE_CONSENSUS_THRESHOLD = 0.7

# Adaptive Context Manager
CONTEXT_WINDOW_DEFAULT = 4096
CONTEXT_WINDOW_MIN = 512
CONTEXT_WINDOW_MAX = 32768
LAZINESS_CHECK_INTERVAL = 5
GLOBAL_SYNC_INTERVAL = 10
```

## Theoretical Foundation

### Why Cognitive Division Works

The theoretical core is drawn from cognitive science and recent transformer architecture research:

1. **Bounded rationality as feature**: Herbert Simon's bounded rationality suggests that decision-making under constraints produces *different* (not worse) cognitive processes. CDoL exploits this by design.

2. **Hybrid attention insight**: Tsinghua & OpenBMB (2026) showed that "large window laziness" — models with larger context windows attend less carefully to relevant information. Our AdaptiveContextManager applies the counter-strategy: constrain local windows, force global sync.

3. **False consensus detection**: Traditional ensemble methods compare final answers. CDoL compares *reasoning chains* — detecting when agents reach the same conclusion through contradictory exclusion processes. This catches errors that voting/averaging would miss.

## Project Structure

```
nexusflow/
├── agents/                          # Role-based agents
│   ├── domains/                     # Knowledge domain modules
│   ├── planner.py                   # Task decomposition + CDoL detection
│   └── __init__.py                  # Module registry
├── tools/                           # 12 built-in tools
├── demo/
│   └── nexusflow_demo.py           # Full Phase 6+7 demonstration
├── docs/                            # Design documents
├── iteration/                       # Version history (v3.0 → v5.0)
│
├── # Phase 7 Core (NEW)
├── cognitive_division_engine.py     # CDoL: decomposition + communication + fusion
├── adaptive_context_manager.py      # Adaptive window + global memory + laziness
│
├── # Phase 6 Core
├── dynamic_router.py                # Dynamic topology routing
├── edge_cloud_scheduler.py          # Edge-Fog-Cloud scheduling
├── dashboard.py                     # Real-time monitoring
│
├── # Foundation (Phase 1-5)
├── base_agent.py                    # Core agent class
├── autonomous.py                    # Autonomous goal processor
├── meta_cognition.py                # Self-assessment
├── cross_domain.py                  # Cross-domain transfer
├── continuous_learning.py           # Dual-path learning
├── agentos.py                       # AgentOS server
├── task_tree.py                     # Task decomposition
├── memory_manager.py                # Memory orchestration (4-layer)
├── a2a_protocol.py                  # Agent-to-Agent protocol
├── a2a_gateway.py                   # A2A network hub
├── ...                              # 20+ more modules
│
├── config.example.py                # Configuration template
├── requirements.txt                 # Dependencies
└── README.md                        # This file
```

## Design Principles

1. **Safety First** — Guardrails, circuit breakers, and anti-pattern detection at every layer
2. **Cognitive Division > Simple Decomposition** — Information asymmetry as resource, not defect
3. **Adaptive over Static** — Context windows, routing topology, and scheduling all adapt dynamically
4. **Observable** — OpenTelemetry tracing + NexusFlow Dashboard for real-time monitoring
5. **Backward Compatible** — All Phase 7 modules are optional; missing dependencies degrade gracefully
6. **Privacy-First Scheduling** — Edge-cloud scheduler respects data sensitivity levels


## Research Roadmap

### Near-Term (2026 Q3)

| Direction | Description | Related Work |
|-----------|-------------|--------------|
| **Agent Self-Evolution Benchmark** | Evaluate agent architecture evolution using rule-based crossover benchmarks (GDPevo-style) | PrismShadow AI, GDPevo (2026) |
| **End-to-End Validation** | Full 50-step materials science workflow (low-carbon cement formulation optimization) | — |
| **CDoL Ablation Study** | Quantitative comparison: CDoL on/off, measuring reasoning depth and convergence speed | — |
| **Cross-Framework Benchmark** | Head-to-head comparison with AutoGen, CrewAI, LangGraph on identical tasks | Agora (ICML 2026) |

### Medium-Term (2026 Q4 - 2027)

| Direction | Description |
|-----------|-------------|
| **Harness Engineering Alignment** | Align with L3 Harness Engineering paradigm (Prompt → Context → Harness) for production-grade reliability |
| **Hybrid Attention Optimization** | Apply "large window laziness" countermeasures from Tsinghua & OpenBMB research to further optimize AdaptiveContextManager |
| **World Model Integration** | Connect CDoL perspective decomposition with world model construction for embodied agent scenarios |
| **Causal Reasoning Layer** | Add causal inference capabilities to the FusionJudge for better attribution analysis |

### Theoretical Alignment

NexusFlow's engineering architecture aligns with the emerging **three-layer Agentic engineering paradigm**:

```
L1: Prompt Engineering     → Agent System Prompts & Task Instructions
L2: Context Engineering    → AdaptiveContextManager (precise info injection)
L3: Harness Engineering    → DynamicRouter + CDoL Engine (reliable execution)
```

This alignment validates that NexusFlow is not an isolated design but follows the frontier of production-grade agent engineering.

## License

MIT License — see [LICENSE](LICENSE) for details.

---

*NexusFlow — Where cognitive diversity meets dynamic topology*
