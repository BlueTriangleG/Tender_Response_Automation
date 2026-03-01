# RAG Architecture

This document explains how retrieval-augmented generation works in the current system — how historical evidence enters it, how it's stored, how it's retrieved, and how it becomes answerable context.

## What RAG Means In This System

Historical tender knowledge is stored in LanceDB. Each incoming question is embedded and used to retrieve the most relevant historical evidence. The model is then asked to answer using only that evidence. A separate assessment step decides whether the evidence actually supports a full answer, a partial answer, or nothing at all.

This keeps the system tied to prior tender positioning rather than generating answers from model memory.

---

## Design Goal

The retrieval layer solves three problems at once:

1. find historically similar approved answers
2. surface broader supporting evidence from non-tabular documents
3. keep answer generation grounded and auditable

That's why the system uses two evidence lanes instead of one: a high-precision QA lane and a broader document-evidence lane.

---

## End-To-End Flow

```text
historical files
  -> ingest and normalize
  -> embed and store in LanceDB

new tender question
  -> embed query
  -> retrieve QA matches
  -> retrieve document chunk matches
  -> merge and filter evidence
  -> reference assessment
  -> answer generation using only retrieved evidence
  -> structured response with references
```

Retrieval happens before generation, not after it.

---

## Data Sources

### QA Records

Tabular historical files — CSV and XLSX — are parsed into question-answer records, normalized to a canonical structure, embedded, and stored in `qa_records`. These are the primary source for direct answer alignment: high-precision historical anchors that give the workflow something to compare new questions against.

### Document Records

Non-tabular historical files — Markdown, TXT, JSON — are chunked and stored in `document_records`. This lane exists because useful evidence doesn't always come in Q/A form. Platform capability writeups, operations playbooks, and policy excerpts often contain the context needed to support or qualify an answer even when there's no exact prior match.

---

## Ingestion

The ingest flow handles the two source types differently.

CSV and XLSX uploads are parsed into rows, mapped to question/answer/domain fields, normalized into canonical QA records, embedded, and upserted into `qa_records`. The goal is stable, reusable historical answer anchors.

Markdown, TXT, and JSON uploads are parsed as raw text, chunked deterministically, embedded, and upserted into `document_records`. The goal is to preserve broader narrative evidence without forcing it into artificial Q/A form.

Both paths are idempotent — re-ingesting the same file won't create duplicates.

---

## Storage

The retrieval backend is local embedded LanceDB under `data/lancedb`. Two physical tables are used: `qa_records` and `document_records`.

The split is intentional. QA rows are answer anchors. Document chunks are supporting evidence. Keeping them separate makes scoring, filtering, and explanation cleaner, and lets each lane be weighted differently at query time.

---

## Query-Time Retrieval

When a tender question arrives, the same question text is embedded and searched against both tables independently.

The QA lane is biased toward direct historical answer alignment — it's the primary source for answer wording and historical positioning. The document lane returns supporting chunks for nuance, policy context, and detail when exact Q/A matches are weak or incomplete.

### Hybrid Merge

The two lanes are merged into one unified evidence view before being passed to the assessor.

References are combined, sorted by alignment score, with QA items winning tie-breaks over document chunks. Only the top-ranked references are kept. This gives answer generation one coherent evidence set while still exposing source type in the final response.

---

## Filtering And Heuristic Rules

The retrieval layer isn't a pure vector search pass-through. It contains light deterministic logic to improve safety and recall on important edge cases.

For example, the merge layer will include near-threshold exception evidence for absolute-claim questions, and will preserve supporting references that help the assessor detect partial coverage. Raw semantic similarity alone can return the main rule without the relevant caveat — which matters especially for security exceptions, deployment constraints, and audit or immutability claims.

---

## How RAG Connects To The Workflow

Retrieval feeds directly into the per-question graph:

```text
retrieve historical evidence
  -> assess reference sufficiency
  -> generate answer with retrieved evidence only
  -> validate answer
```

The key point is that retrieval doesn't answer the question by itself. RAG is split into three stages — retrieve, assess, generate — and that separation makes the workflow safer and easier to reason about.

### Why Assessment Sits Between Retrieval And Generation

Many systems retrieve evidence and immediately generate. This system adds an explicit assessment step in between that decides whether the evidence is sufficient for a full answer, whether only a partial answer is justified, or whether the system should decline to answer.

This matters because high retrieval similarity doesn't automatically mean the evidence supports the specific claim being asked. A question about a security protocol might surface a highly similar prior answer that only partially applies — and passing that straight to generation without assessment would produce an overclaim.

---

## Evidence In The Output

The final response exposes the retrieval evidence back to the client. For each question, the references can include the matched historical question and answer, the source document, the alignment score, whether the reference was used for generation, and a document excerpt when the source is a chunk.

This makes the response auditable: human reviewers can inspect why any given answer was generated.

---

## How RAG Shapes The Answer Contract

The retrieval layer directly influences several fields in the structured output:

- `historical_alignment_indicator`
- `grounding_status`
- `confidence_level`
- `confidence_reason`
- `references[]`

RAG isn't an isolated utility. It's part of the answer contract.

---

## Current Boundaries

What the current design does well:

- supports mixed-format historical sources (CSV, XLSX, MD, TXT, JSON)
- stores durable local evidence in LanceDB
- retrieves from both QA and document lanes and merges them
- keeps retrieval and generation as separate, inspectable stages

What it doesn't try to be:

- a general enterprise search platform
- a multi-stage re-ranker stack
- a formal knowledge graph
- a globally optimized hybrid BM25 + vector search engine

It's intentionally designed for demo-scale, local, inspectable tender-response grounding.

---

## Related Documents

- Agent workflow design: [AGENT_ARCHITECTURE.md](./AGENT_ARCHITECTURE.md)
- State and memory design: [MEMORY_AND_STATE.md](./MEMORY_AND_STATE.md)
- Main project entry: [README.md](../../README.md)
