# RAG Architecture

This document explains how retrieval-augmented generation works in the current system.

It focuses on design rather than code internals. The goal is to make one thing clear: how historical evidence enters the system, how it is stored, how it is retrieved, and how it is turned into answerable context.

## What RAG Means In This System

In this project, RAG means:

- historical tender knowledge is stored in LanceDB
- each incoming tender question is embedded and used to retrieve relevant historical evidence
- the model is asked to answer only with that evidence
- the workflow decides whether the evidence supports a grounded answer, a partial answer, or no answer

This keeps the workflow tied to prior tender positioning instead of relying on model memory alone.

## Design Goal

The retrieval layer is designed to solve three problems at once:

1. find historically similar approved answers
2. surface broader supporting evidence from non-tabular documents
3. keep the answer generation step grounded and auditable

That is why the system uses two evidence lanes instead of one:

- a high-precision QA lane
- a broader document-evidence lane

## End-To-End RAG Flow

High-level flow:

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

## Data Sources

The system supports two historical evidence source types.

### 1. QA Records

These come from tabular historical repositories such as CSV or XLSX files with question-answer-domain structure.

Examples:

- approved prior tender answers
- structured repository exports
- flat historical Q/A spreadsheets

These are stored in LanceDB table:

- `qa_records`

Why this lane exists:

- it is the best source for direct answer alignment
- it gives the workflow high-precision historical anchors

### 2. Document Records

These come from non-tabular historical files such as:

- Markdown
- TXT
- JSON

Examples:

- platform capability writeups
- operations playbooks
- policy excerpts
- supporting narrative material

These are chunked and stored in LanceDB table:

- `document_records`

Why this lane exists:

- some useful evidence does not exist in strict Q/A form
- document evidence helps when exact Q/A matches are weak or incomplete

## Ingestion Design

Historical content enters the retrieval system through the history ingest flow.

### Tabular Ingest Path

CSV and XLSX uploads are:

- parsed into rows
- mapped to question, answer, and domain fields
- normalized into canonical QA records
- embedded
- upserted into `qa_records`

Design intent:

- preserve stable, reusable historical answer anchors

### Document Ingest Path

Markdown, TXT, and JSON uploads are:

- parsed as raw evidence text
- chunked deterministically
- embedded
- upserted into `document_records`

Design intent:

- preserve broader narrative evidence without forcing it into artificial Q/A form

## Storage Layer

The retrieval backend is local embedded LanceDB under:

- [data/lancedb](/Users/autumn/Learning/interview%20questions/pans_software/data/lancedb)

The design uses two physical tables:

- `qa_records`
- `document_records`

This split is intentional.

Why two tables instead of one mixed table:

- QA rows and document chunks have different semantics
- QA rows are answer anchors
- document chunks are supporting evidence
- keeping them separate makes scoring, filtering, and explanation cleaner

## Query-Time Retrieval

When a new tender question arrives, the system retrieves evidence from both lanes.

### QA Retrieval

The tender question text is embedded and searched against `qa_records`.

Retrieval behavior:

- top semantic matches are returned
- distance is converted into a normalized alignment score
- the QA lane is biased toward direct historical answer alignment

Design role:

- primary source for answer wording and historical positioning

### Document Retrieval

The same tender question text is embedded and searched against `document_records`.

Retrieval behavior:

- top document chunks are returned
- each chunk is scored the same way as QA results
- excerpts are returned as supporting evidence

Design role:

- secondary source for nuance, policy context, and supporting detail

## Hybrid Retrieval Merge

The system does not treat the two retrieval lanes as separate final outputs.

Instead, it merges them into one unified historical evidence view.

Merge behavior:

- QA references and document references are combined
- references are sorted by alignment score
- QA items win tie-breaks over document chunks
- only a capped number of top references are kept

Why this design matters:

- answer generation receives one coherent evidence set
- the workflow can still expose source type in the final response
- QA stays primary without discarding useful document evidence

## Filtering And Heuristic Retrieval Rules

The retrieval layer is not a pure vector search pass-through.

It contains light deterministic logic to improve safety and recall on important edge cases.

Examples of what the merge layer does:

- include near-threshold exception evidence for absolute-claim questions
- preserve supporting references that help the assessor detect partial coverage
- keep security-sensitive edge cases from looking fully grounded when important caveats exist

Design reason:

- raw semantic similarity alone is not enough for careful tender answering
- some questions need retrieval to surface both the main rule and the exception

This is especially important for:

- security exceptions
- deployment constraints
- audit and immutability claims

## How RAG Connects To LangGraph

The retrieval layer feeds directly into the question workflow.

High-level sequence:

```text
retrieve historical evidence
  -> assess reference sufficiency
  -> generate answer with retrieved evidence only
  -> validate answer
```

The key architectural point is that retrieval does not answer the question by itself.

RAG is split into three stages:

1. retrieve evidence
2. assess whether the evidence is sufficient
3. generate and validate an answer from that evidence

That separation makes the workflow safer and easier to reason about.

## Why Reference Assessment Sits After Retrieval

Many systems retrieve evidence and immediately generate.

This system adds an explicit assessment step in between.

That step decides:

- is the evidence sufficient for a full answer
- is only a partial answer justified
- should the system refuse to answer

This matters because good retrieval similarity does not automatically mean the evidence supports the exact tender claim being asked.

## How Retrieved Evidence Appears In The Output

The final tender response exposes retrieval evidence back to the client.

Each question can include references such as:

- matched historical question
- matched historical answer
- source document
- alignment score
- whether the reference was used for answer generation
- document excerpt when the source is a chunk

Design effect:

- the response is auditable
- human reviewers can inspect why an answer was generated
- grounding and conflict analysis can be explained

## Confidence And Grounding Depend On RAG

The retrieval layer does not just fetch context. It directly influences:

- `historical_alignment_indicator`
- `grounding_status`
- `confidence_level`
- `confidence_reason`
- `references[]`

This means RAG is not an isolated utility. It is part of the answer contract.

## Why This RAG Design Fits The Tender Use Case

Tender answering is not only about finding similar text.

It also needs:

- historical consistency
- conservative handling of unsupported claims
- traceable evidence
- mixed evidence types

The current design fits that need because:

- QA retrieval anchors answers to prior approved positioning
- document retrieval supplies broader supporting context
- reference assessment prevents retrieval from being treated as proof automatically
- structured outputs expose the evidence trail

## Current Boundaries

What the current RAG design does well:

- supports mixed-format historical sources
- stores durable local evidence in LanceDB
- retrieves from both QA and document lanes
- merges evidence into a single historical context
- keeps retrieval and generation separate

What it does not try to be:

- a general enterprise search platform
- a multi-stage re-ranker stack
- a formal knowledge graph
- a globally optimized hybrid BM25 plus vector search engine

It is intentionally designed for demo-scale, local, inspectable tender-response grounding.

## Related Documents

- Main project entry: [README.md](/Users/autumn/Learning/interview%20questions/pans_software/README.md)
- Agent workflow design: [AGENT_ARCHITECTURE.md](/Users/autumn/Learning/interview%20questions/pans_software/docs/delivery/AGENT_ARCHITECTURE.md)
- Dataset guide: [test_data/README.md](/Users/autumn/Learning/interview%20questions/pans_software/test_data/README.md)
- Earlier LanceDB bootstrap plan: [2026-02-28-local-lancedb-rag.md](/Users/autumn/Learning/interview%20questions/pans_software/docs/plans/2026-02-28-local-lancedb-rag.md)
