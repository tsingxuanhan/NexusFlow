# Vector Memory Guide

> Semantic Memory System in NexusFlow v3.1.1

## Overview

NexusFlow integrates a three-tier memory architecture with NGram TF-IDF semantic embeddings:

| Tier | Type | Latency | Use Case |
|------|------|---------|----------|
| **L1 Hot** | Current context | <1ms | Active task state |
| **L2 Semantic** | Vector search | ~20ms | Cross-task memory |
| **L3 Episodic** | Long-term log | Archive | Historical patterns |

## Key Features

### NGram TF-IDF Embeddings

Unlike traditional word embeddings, NGram TF-IDF captures:

- **Word-level n-grams**: "super sulfated cement" → ["super sulfated", "sulfated cement"]
- **Character-level n-grams**: Handles typos and morphological variations
- **Subword similarity**: "nano SiO2" ↔ "silica nanoparticle"

Example:
```python
from vector_memory import NGramTFIDFProvider

provider = NGramTFIDFProvider()

# Word-level + char-level n-grams
query_emb = provider.embed("nano silica SSC")
doc_emb = provider.embed("SiO2 nanoparticle supersulfated")

# High similarity despite different wording!
similarity = cosine_similarity([query_emb], [doc_emb])
```

## Usage

### Basic Memory Operations

```python
from vector_memory import (
    SimpleEmbeddingProvider,
    NGramTFIDFProvider,
    PersistentVectorStore,
    MemoryTier
)

# Choose embedding provider
provider = NGramTFIDFProvider()

# Create persistent store
memory = PersistentVectorStore(
    provider=provider,
    persist_path="./data/vector_memory.json"
)

# Add entries with metadata
memory.add(
    content="LC3 contains 50% limestone and 50% calcined clay",
    tier=MemoryTier.L2_SEMANTIC,
    metadata={"source": "paper_2024", "domain": "cement"}
)

# Search with semantic understanding
results = memory.search("limestone blended binders", top_k=5)

for result in results:
    print(f"[{result.score:.3f}] {result.entry.content}")
```

### Multi-Tier Memory

```python
from vector_memory import MemoryEntry, MemoryTier

# L1: Hot context (current task)
memory.add(
    content="User researching SSC mix design",
    tier=MemoryTier.L1_HOT,
    metadata={"task_id": "current"}
)

# L2: Semantic memory (cross-task)
memory.add(
    content="SSC requires min 70% GGBS, max 5% clinker",
    tier=MemoryTier.L2_SEMANTIC,
    metadata={"category": "composition"}
)

# L3: Episodic log (historical)
memory.add(
    content="2024-05: SSC project completed with 42MPa strength",
    tier=MemoryTier.L3_EPISODIC,
    metadata={"date": "2024-05-15", "project": "ssc_demo"}
)
```

### LLM Integration

```python
from vector_memory import LLMEnhancedMemory

# Wrap with LLM for query enhancement
memory = LLMEnhancedMemory(
    base_store=PersistentVectorStore(provider=NGramTFIDFProvider()),
    llm_client=llm
)

# Natural language queries
results = memory.query(
    "What SSC compositions achieved >40 MPa in our experiments?"
)
```

## Persistence

### JSON Persistence

```python
# Save to JSON
memory.persist("./data/vector_memory.json")

# Load from JSON
memory = PersistentVectorStore.load(
    "./data/vector_memory.json",
    provider=NGramTFIDFProvider()
)
```

### ChromaDB Backend (Optional)

```python
from vector_memory import ChromaDBVectorStore

# Use ChromaDB for production
memory = ChromaDBVectorStore(
    persist_directory="./chroma_db",
    provider=NGramTFIDFProvider()
)

# Automatic fallback to PersistentVectorStore if ChromaDB unavailable
```

## Configuration

```python
# NGramTFIDFProvider config
provider = NGramTFIDFProvider(
    word_ngram_range=(1, 3),    # Unigrams, bigrams, trigrams
    char_ngram_range=(3, 5),    # 3-5 char n-grams
    dimension=384,              # Embedding dimension
    idf_mode="smooth"          # Smooth IDF weighting
)

# Memory config
memory = PersistentVectorStore(
    provider=provider,
    persist_path="./data/vector_memory.json",
    top_k_default=5,
    similarity_threshold=0.3
)
```

## Performance

| Operation | Latency | Notes |
|-----------|---------|-------|
| Embed (short text) | <5ms | Cached embeddings |
| Embed (batch 100) | ~100ms | Parallel processing |
| Search (top_k=5) | ~20ms | Including embedding |
| Persist (1000 entries) | ~50ms | JSON serialization |

## Best Practices

1. **Batch operations** for bulk additions
2. **Cache embeddings** for frequently queried content
3. **Set similarity threshold** to filter low-quality matches
4. **Use metadata** for filtering and attribution
5. **Persist regularly** to avoid memory loss
