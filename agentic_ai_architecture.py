"""
Local-first implementation of the AgenticAIArchitecture design.

This module implements:
1) Input guardrails + session context
2) Planner + executor orchestration with step/time/token budgets
3) Tool layer with hybrid retrieval, graph retrieval, and SQL access
4) Memory (short-term + optional long-term with ChromaDB)
5) Output guardrails with citations and audit IDs
6) Observability traces for every major step

The implementation is intentionally provider-agnostic and works fully local.
"""

from __future__ import annotations

import hashlib
import json
import re
import sqlite3
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import networkx as nx
import numpy as np
from pydantic import BaseModel, Field
from rank_bm25 import BM25Okapi

try:
    import chromadb

    HAS_CHROMA = True
except ImportError:
    chromadb = None
    HAS_CHROMA = False

try:
    from sentence_transformers import CrossEncoder, SentenceTransformer

    HAS_SENTENCE_TRANSFORMERS = True
except ImportError:
    CrossEncoder = None
    SentenceTransformer = None
    HAS_SENTENCE_TRANSFORMERS = False


class SessionContext(BaseModel):
    user_id: str
    tenant_id: str
    role: str = "user"


class UserQuery(BaseModel):
    text: str = Field(min_length=1, max_length=5000)
    context: SessionContext


class PlanStep(BaseModel):
    objective: str
    tools: list[str] = Field(default_factory=list)


class ExecutionPlan(BaseModel):
    query_rewrite: str
    steps: list[PlanStep]
    use_planner: bool


class ToolObservation(BaseModel):
    tool: str
    output: str
    citations: list[str] = Field(default_factory=list)


class AgentResponse(BaseModel):
    answer: str
    citations: list[str]
    grounding_score: float
    audit_id: str
    blocked: bool = False
    block_reason: str | None = None
    trace: list[dict[str, Any]] = Field(default_factory=list)


class InputGuardrails:
    _email = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
    _phone = re.compile(r"\+?\d[\d\s().-]{7,}\d")
    _injection = re.compile(
        r"ignore\s+previous\s+instructions|system\s+prompt|developer\s+message|jailbreak",
        re.IGNORECASE,
    )

    @classmethod
    def sanitize(cls, text: str, max_len: int = 4000) -> tuple[str, bool, str | None]:
        trimmed = text.strip()
        if len(trimmed) > max_len:
            return "", True, f"Input exceeds max length of {max_len} characters"

        if cls._injection.search(trimmed):
            return "", True, "Potential prompt injection detected"

        scrubbed = cls._email.sub("[REDACTED_EMAIL]", trimmed)
        scrubbed = cls._phone.sub("[REDACTED_PHONE]", scrubbed)
        return scrubbed, False, None


class OutputGuardrails:
    @staticmethod
    def evaluate(answer: str, citations: list[str]) -> tuple[float, bool, str | None]:
        # Basic grounding proxy: require citations for knowledge-heavy responses.
        citation_weight = min(len(citations) / 3.0, 1.0)
        answer_weight = 0.0 if len(answer.strip()) < 40 else 0.5
        grounding = min(1.0, citation_weight * 0.7 + answer_weight)

        if grounding < 0.45:
            return grounding, True, "Low grounding score; response blocked by output guardrail"
        return grounding, False, None


@dataclass
class TraceEvent:
    ts: float
    phase: str
    detail: str
    data: dict[str, Any] = field(default_factory=dict)


class TraceCollector:
    def __init__(self) -> None:
        self._events: list[TraceEvent] = []

    def add(self, phase: str, detail: str, **data: Any) -> None:
        self._events.append(TraceEvent(ts=time.time(), phase=phase, detail=detail, data=data))

    def as_dict(self) -> list[dict[str, Any]]:
        return [
            {
                "ts": e.ts,
                "phase": e.phase,
                "detail": e.detail,
                "data": e.data,
            }
            for e in self._events
        ]


class LongTermMemory:
    def __init__(self, memory_dir: Path) -> None:
        self.memory_dir = memory_dir
        self.memory_dir.mkdir(parents=True, exist_ok=True)
        self.in_memory: list[tuple[str, str, str]] = []

        self.collection = None
        if HAS_CHROMA:
            client = chromadb.PersistentClient(path=str(self.memory_dir))
            self.collection = client.get_or_create_collection("agent_episodes")

    def write(self, tenant_id: str, user_id: str, summary: str) -> None:
        doc_id = str(uuid.uuid4())
        if self.collection is not None:
            self.collection.add(
                ids=[doc_id],
                documents=[summary],
                metadatas=[{"tenant_id": tenant_id, "user_id": user_id}],
            )
        else:
            self.in_memory.append((tenant_id, user_id, summary))

    def recall(self, tenant_id: str, user_id: str, query: str, top_k: int = 3) -> list[str]:
        if self.collection is not None:
            result = self.collection.query(
                query_texts=[query],
                n_results=top_k,
                where={"$and": [{"tenant_id": tenant_id}, {"user_id": user_id}]},
            )
            return result.get("documents", [[]])[0]

        filtered = [item[2] for item in self.in_memory if item[0] == tenant_id and item[1] == user_id]
        return filtered[:top_k]


class HybridRetriever:
    def __init__(self, docs: list[dict[str, str]], embedding_model: str = "all-MiniLM-L6-v2") -> None:
        self.docs = docs
        self.texts = [d["text"] for d in docs]
        self.ids = [d["id"] for d in docs]
        self.tokens = [t.lower().split() for t in self.texts]
        self.bm25 = BM25Okapi(self.tokens)

        self.embedder = None
        self.embeddings = None
        if HAS_SENTENCE_TRANSFORMERS:
            self.embedder = SentenceTransformer(embedding_model)
            self.embeddings = self.embedder.encode(self.texts, normalize_embeddings=True)

    def retrieve(self, query: str, top_k: int = 5) -> list[dict[str, Any]]:
        bm25_scores = self.bm25.get_scores(query.lower().split())
        bm25_rank = np.argsort(-bm25_scores)[: max(top_k * 3, 10)]

        if self.embedder is None or self.embeddings is None:
            ranked = bm25_rank[:top_k]
            return [
                {
                    "id": self.ids[i],
                    "text": self.texts[i],
                    "score": float(bm25_scores[i]),
                    "source": "hybrid:builtin_bm25",
                }
                for i in ranked
            ]

        q = self.embedder.encode([query], normalize_embeddings=True)[0]
        dense_scores = np.dot(self.embeddings, q)

        fused = []
        for i in bm25_rank:
            score = float(0.45 * bm25_scores[i] + 0.55 * dense_scores[i])
            fused.append((i, score))
        fused.sort(key=lambda x: x[1], reverse=True)

        return [
            {
                "id": self.ids[i],
                "text": self.texts[i],
                "score": score,
                "source": "hybrid:bm25+dense",
            }
            for i, score in fused[:top_k]
        ]


class GraphRetriever:
    def __init__(self, edges: list[tuple[str, str, str]]) -> None:
        self.graph = nx.MultiDiGraph()
        for src, rel, dst in edges:
            self.graph.add_edge(src, dst, relation=rel)

    def retrieve(self, entity: str, max_depth: int = 2, limit: int = 12) -> list[str]:
        if entity not in self.graph:
            return []

        results: list[str] = []
        frontier = [(entity, 0)]
        seen = {entity}

        while frontier and len(results) < limit:
            node, depth = frontier.pop(0)
            if depth >= max_depth:
                continue
            for _, neighbor, data in self.graph.out_edges(node, data=True):
                rel = data.get("relation", "related_to")
                results.append(f"{node} -[{rel}]-> {neighbor}")
                if neighbor not in seen:
                    seen.add(neighbor)
                    frontier.append((neighbor, depth + 1))
                if len(results) >= limit:
                    break
        return results


class SQLReadTool:
    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path

    def query(self, sql: str, max_rows: int = 20) -> list[dict[str, Any]]:
        normalized = sql.strip().lower()
        if not normalized.startswith("select"):
            raise ValueError("Only SELECT queries are permitted")

        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(sql).fetchmany(max_rows)
            return [dict(row) for row in rows]


class Reranker:
    def __init__(self, model_name: str = "cross-encoder/ms-marco-MiniLM-L-6-v2") -> None:
        self.model = None
        if HAS_SENTENCE_TRANSFORMERS:
            self.model = CrossEncoder(model_name)

    def rerank(self, query: str, candidates: list[dict[str, Any]], top_k: int = 5) -> list[dict[str, Any]]:
        if not candidates:
            return []

        if self.model is None:
            candidates.sort(key=lambda x: x.get("score", 0.0), reverse=True)
            return candidates[:top_k]

        pairs = [(query, c["text"]) for c in candidates]
        scores = self.model.predict(pairs)
        packed = []
        for candidate, score in zip(candidates, scores):
            updated = dict(candidate)
            updated["rerank_score"] = float(score)
            packed.append(updated)
        packed.sort(key=lambda x: x["rerank_score"], reverse=True)
        return packed[:top_k]


@dataclass
class AgentConfig:
    max_steps: int = 6
    per_step_timeout_sec: float = 8.0
    total_token_budget: int = 12000
    planner_enabled: bool = True


class LocalAgenticArchitecture:
    def __init__(
        self,
        docs: list[dict[str, str]],
        graph_edges: list[tuple[str, str, str]],
        db_path: Path,
        config: AgentConfig | None = None,
        memory_dir: Path | None = None,
    ) -> None:
        self.config = config or AgentConfig()
        self.retriever = HybridRetriever(docs)
        self.graph = GraphRetriever(graph_edges)
        self.sql_tool = SQLReadTool(db_path)
        self.reranker = Reranker()
        self.memory = LongTermMemory(memory_dir or Path(".agent_memory"))

    def _planner(self, query: str) -> ExecutionPlan:
        # Local deterministic planner; replace with stronger model if needed.
        steps = [
            PlanStep(objective="Gather semantic and lexical context", tools=["hybrid_retriever", "reranker"]),
            PlanStep(objective="Check entity relationships", tools=["graph_retriever"]),
        ]
        if re.search(r"revenue|count|total|sql|database", query, re.IGNORECASE):
            steps.append(PlanStep(objective="Pull live tabular data", tools=["sql_tool"]))

        rewrite = query.replace("customer", "customer account")
        return ExecutionPlan(query_rewrite=rewrite, steps=steps, use_planner=self.config.planner_enabled)

    def _extract_entity(self, query: str) -> str | None:
        m = re.search(r"customer(?:\s+account)?\s+([A-Za-z0-9_-]+)", query, re.IGNORECASE)
        if m:
            return f"customer:{m.group(1)}"
        return None

    def _execute_step(self, step: PlanStep, query: str, trace: TraceCollector) -> ToolObservation:
        step_start = time.time()
        parts: list[str] = []
        citations: list[str] = []

        if "hybrid_retriever" in step.tools:
            found = self.retriever.retrieve(query, top_k=8)
            reranked = self.reranker.rerank(query, found, top_k=4)
            for item in reranked:
                parts.append(f"[{item['id']}] {item['text']}")
                citations.append(item["id"])
            trace.add("tool", "hybrid retrieval completed", hits=len(reranked))

        if "graph_retriever" in step.tools:
            entity = self._extract_entity(query)
            if entity:
                graph_hits = self.graph.retrieve(entity, max_depth=2)
                if graph_hits:
                    parts.append("Graph context: " + " | ".join(graph_hits))
                    citations.append(f"graph:{entity}")
            trace.add("tool", "graph retrieval completed", entity=entity or "none")

        if "sql_tool" in step.tools:
            try:
                rows = self.sql_tool.query("SELECT customer_id, contract_count, mrr FROM customer_metrics LIMIT 5")
                parts.append("SQL snapshot: " + json.dumps(rows))
                citations.append("sql:customer_metrics")
                trace.add("tool", "sql query completed", rows=len(rows))
            except Exception as exc:
                parts.append(f"SQL tool error: {exc}")
                trace.add("tool", "sql query failed", error=str(exc))

        elapsed = time.time() - step_start
        if elapsed > self.config.per_step_timeout_sec:
            parts.append("Step timeout exceeded; partial results returned")
            trace.add("budget", "per-step timeout exceeded", elapsed=elapsed)

        return ToolObservation(tool="+".join(step.tools), output="\n".join(parts), citations=citations)

    def _synthesize(self, query: str, observations: list[ToolObservation], memory_hits: list[str]) -> tuple[str, list[str]]:
        citation_set: list[str] = []
        evidence = []

        for obs in observations:
            evidence.append(obs.output)
            for c in obs.citations:
                if c not in citation_set:
                    citation_set.append(c)

        if memory_hits:
            evidence.append("Prior relevant memory: " + " || ".join(memory_hits))

        answer = (
            "Based on retrieved evidence, here is a grounded response:\n\n"
            f"Question: {query}\n\n"
            "Evidence Summary:\n"
            + "\n".join(f"- {line}" for line in evidence if line.strip())
            + "\n\nRecommended next step: validate cited sources before any write action."
        )

        return answer, citation_set

    def run(self, raw_query: str, session: SessionContext) -> AgentResponse:
        trace = TraceCollector()
        audit_id = hashlib.sha256(f"{time.time()}:{session.tenant_id}:{raw_query}".encode("utf-8")).hexdigest()[:16]

        clean_query, blocked, reason = InputGuardrails.sanitize(raw_query)
        trace.add("guardrail", "input checked", blocked=blocked, reason=reason)
        if blocked:
            return AgentResponse(
                answer="",
                citations=[],
                grounding_score=0.0,
                audit_id=audit_id,
                blocked=True,
                block_reason=reason,
                trace=trace.as_dict(),
            )

        user_query = UserQuery(text=clean_query, context=session)
        memory_hits = self.memory.recall(session.tenant_id, session.user_id, user_query.text)
        trace.add("memory", "recalled episodes", hits=len(memory_hits))

        plan = self._planner(user_query.text) if self.config.planner_enabled else ExecutionPlan(
            query_rewrite=user_query.text,
            steps=[PlanStep(objective="Direct retrieve", tools=["hybrid_retriever", "reranker"])],
            use_planner=False,
        )
        trace.add("planner", "plan built", steps=len(plan.steps), rewrite=plan.query_rewrite)

        observations: list[ToolObservation] = []
        token_budget_used = 0
        for idx, step in enumerate(plan.steps, start=1):
            if idx > self.config.max_steps:
                trace.add("budget", "max step budget reached", max_steps=self.config.max_steps)
                break

            approx_tokens = len((plan.query_rewrite + step.objective).split())
            token_budget_used += approx_tokens
            if token_budget_used > self.config.total_token_budget:
                trace.add("budget", "token budget reached", used=token_budget_used)
                break

            trace.add("executor", "running step", index=idx, objective=step.objective, tools=step.tools)
            observations.append(self._execute_step(step, plan.query_rewrite, trace))

        answer, citations = self._synthesize(plan.query_rewrite, observations, memory_hits)
        grounding, out_blocked, out_reason = OutputGuardrails.evaluate(answer, citations)
        trace.add("guardrail", "output checked", blocked=out_blocked, grounding=grounding)

        if out_blocked:
            return AgentResponse(
                answer="",
                citations=citations,
                grounding_score=grounding,
                audit_id=audit_id,
                blocked=True,
                block_reason=out_reason,
                trace=trace.as_dict(),
            )

        self.memory.write(
            tenant_id=session.tenant_id,
            user_id=session.user_id,
            summary=f"Q: {plan.query_rewrite}\nA: {answer[:500]}\nCitations: {', '.join(citations)}",
        )
        trace.add("memory", "episode written", citations=len(citations))

        return AgentResponse(
            answer=answer,
            citations=citations,
            grounding_score=grounding,
            audit_id=audit_id,
            blocked=False,
            trace=trace.as_dict(),
        )


def build_demo_runtime(root: Path) -> LocalAgenticArchitecture:
    docs = [
        {"id": "doc:contracts", "text": "Customer contracts include amendments and renewal clauses with approval hierarchy."},
        {"id": "doc:policy", "text": "PII must be redacted before responses are sent outside tenant boundaries."},
        {"id": "doc:finance", "text": "MRR is computed from active subscriptions and excludes one-time onboarding fees."},
        {"id": "doc:incident", "text": "Grounding score below threshold requires automatic retry or human escalation."},
    ]

    edges = [
        ("customer:acme", "has_contract", "contract:42"),
        ("contract:42", "amended_by", "amendment:7"),
        ("contract:42", "owned_by", "team:legal"),
    ]

    db_path = root / "agentic_demo.db"
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS customer_metrics (
                customer_id TEXT PRIMARY KEY,
                contract_count INTEGER,
                mrr REAL
            )
            """
        )
        conn.execute("DELETE FROM customer_metrics")
        conn.executemany(
            "INSERT INTO customer_metrics(customer_id, contract_count, mrr) VALUES (?, ?, ?)",
            [
                ("acme", 5, 10250.0),
                ("globex", 2, 4100.0),
                ("initech", 3, 6650.0),
            ],
        )
        conn.commit()

    return LocalAgenticArchitecture(
        docs=docs,
        graph_edges=edges,
        db_path=db_path,
        memory_dir=root / ".agent_memory",
    )


if __name__ == "__main__":
    runtime = build_demo_runtime(Path(__file__).parent)
    session = SessionContext(user_id="rahul", tenant_id="tenant-a", role="analyst")
    result = runtime.run(
        "For customer acme, summarize contract relationships and include mrr signal from database.",
        session,
    )
    print(json.dumps(result.model_dump(), indent=2))