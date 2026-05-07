# AgenticAIArchitecture Implementation (Local-First)

This folder now contains a concrete implementation of the architecture in `AgenticAIArchitecture.docx`:

- Input guardrails (PII redaction, injection checks, length limits)
- Session context support (user, tenant, role)
- Planner + executor orchestration loop with budgets
- Multi-tool layer:
  - Hybrid retriever (BM25 + dense embeddings)
  - Graph retriever (`networkx`)
  - SQL read tool (`sqlite3`)
  - Optional reranker (`CrossEncoder`)
- Memory:
  - Short-term scratchpad during run
  - Long-term memory via `chromadb` (fallback in-memory if unavailable)
- Output guardrails (grounding score + citation requirements)
- Trace/audit output for observability

## Install

```bash
pip install -r AgenticAI/requirements.txt
```

## Run Demo

```bash
python AgenticAI/agentic_ai_architecture.py
```

The demo creates a local SQLite DB, runs a full agentic cycle, and prints:

- grounded answer
- citations
- grounding score
- audit ID
- full trace events

## Notes

- The planner is local and deterministic by default for reliability.
- If `sentence-transformers` is installed, dense retrieval and reranking are automatically enabled.
- If `chromadb` is installed, long-term memory is persisted locally in `AgenticAI/.agent_memory`.