# Context Fabric — Product Requirements Document
## MVP (Phase 1)
### 19 March 2026

---

## 1. OVERVIEW

**Context Fabric** is a persistent AI context layer packaged as an Agent Zero skill. It stores project state, architectural decisions, task plans, and session artifacts in Supabase (pgvector), enabling any AI instance to query for relevant prior context before beginning a new task.

**MVP Goal:** A working Agent Zero skill that can ingest markdown documents, decompose a PRD task into sub-steps using an LLM, query the vector DB for relevant context per sub-step, and return aggregated results to inform coding.

**MVP Workflow:**
```
PRD Task → plan-task (LLM decomposes) → query (each sub-step) → aggregated context returned
         ↑                                                              |
         └── ingest-document (session artifacts fed back) ←─────────────┘
```

---

## 2. MVP SCOPE

### In Scope
- Supabase table provisioning with pgvector
- Document ingestion pipeline (markdown → chunk → embed → store)
- Semantic query with metadata filtering
- LLM-driven task decomposition (cheap model)
- Agent Zero skill packaging (SKILL.md standard)
- Section-type auto-superseding (Layer 1 only)
- Testing against real project data

### Out of Scope (Phase 2)
- Repository seeding (`ingest-repo`)
- MCP server exposure
- Semantic collision detection (superseded Layer 2)
- Explicit SUPERSEDES markers (superseded Layer 3)
- `related_chunks` linking
- Temporal chaining (Zep-style)
- Multi-user / RLS policies
- UI or dashboard

---

## 3. TECHNICAL DECISIONS (LOCKED)

These were decided in Session 1 and are not open for re-evaluation:

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Vector store | Supabase + pgvector | Already in stack, co-locates vectors + metadata |
| Embedding model | `text-embedding-3-small` | $0.02/1M tokens, sufficient for technical prose |
| Decomposition model | Cheap LLM (e.g., `gpt-4o-mini` or equivalent) | Task decomposition needs understanding, not heavy reasoning |
| Chunking | Section-level, 800-token overflow split | Preserves semantic coherence |
| Document format | Markdown | Human/AI readable, embeds well, version-controllable |
| Packaging | Agent Zero skill (SKILL.md) | Portable, self-contained |

---

## 4. TASKS

### TASK 1: Supabase Provisioning

**Objective:** Create the Supabase table, enable pgvector, and set up indexes for the context store.

**Requirements:**
- Enable the `vector` extension in Supabase (`CREATE EXTENSION IF NOT EXISTS vector`)
- Create table `context_chunks` with the following schema:

```sql
create table context_chunks (
  id            uuid primary key default gen_random_uuid(),
  content       text not null,                    -- raw chunk text
  embedding     vector(1536) not null,            -- text-embedding-3-small output
  project_name  text not null,
  date_created  timestamptz default now(),
  confidence    text check (confidence in ('high', 'medium', 'low')) default 'high',
  tags          text[] default '{}',
  document_type text check (document_type in (
    'continuation_doc', 'adr', 'task_plan', 'code_pattern', 'session_note'
  )) not null,
  session_number integer,
  section_type  text check (section_type in (
    'identity', 'architecture', 'decisions', 'recent_work',
    'risks', 'constraints', 'competitive', 'patterns', 'other'
  )),
  chunk_type    text check (chunk_type in (
    'decision', 'pattern', 'status', 'constraint', 'pitfall',
    'requirement', 'architecture', 'context', 'other'
  )),
  source_file   text,
  superseded    boolean default false,
  project_phase text check (project_phase in (
    'planning', 'design', 'implementation', 'testing', 'maintenance'
  )),
  source_tier   text check (source_tier in (
    'tier1_docs', 'tier2_code', 'tier3_git', 'tier4_comments'
  )) default 'tier1_docs'
);
```

- Create indexes:
  - `ivfflat` index on `embedding` column for approximate nearest neighbor search
  - B-tree index on `project_name`
  - B-tree index on `superseded`
  - B-tree index on `document_type`
  - Composite index on `(project_name, superseded)` for filtered vector search

- Create a SQL function for similarity search:
```sql
create or replace function match_context_chunks(
  query_embedding vector(1536),
  match_threshold float default 0.7,
  match_count int default 5,
  filter_project text default null,
  filter_superseded boolean default false
)
returns table (
  id uuid,
  content text,
  project_name text,
  document_type text,
  section_type text,
  chunk_type text,
  confidence text,
  tags text[],
  date_created timestamptz,
  session_number integer,
  source_file text,
  project_phase text,
  similarity float
)
language plpgsql as $$
begin
  return query
  select
    cc.id,
    cc.content,
    cc.project_name,
    cc.document_type,
    cc.section_type,
    cc.chunk_type,
    cc.confidence,
    cc.tags,
    cc.date_created,
    cc.session_number,
    cc.source_file,
    cc.project_phase,
    1 - (cc.embedding <=> query_embedding) as similarity
  from context_chunks cc
  where cc.superseded = filter_superseded
    and (filter_project is null or cc.project_name = filter_project)
    and 1 - (cc.embedding <=> query_embedding) > match_threshold
  order by cc.embedding <=> query_embedding
  limit match_count;
end;
$$;
```

**Acceptance Criteria:**
- [ ] pgvector extension enabled
- [ ] `context_chunks` table created with all columns and constraints
- [ ] All indexes created
- [ ] `match_context_chunks` function created and callable
- [ ] Verified by inserting a test row and running a similarity query

---

### TASK 2: Embedding Pipeline

**Objective:** Build a Python module that takes text, calls OpenAI's embedding API, and returns the vector.

**Requirements:**
- Create `lib/embeddings.py`
- Function `embed_text(text: str) -> list[float]`
  - Calls OpenAI `text-embedding-3-small` model
  - Returns 1536-dimensional vector
  - Handles rate limiting with exponential backoff
  - Handles empty/whitespace input gracefully
- Function `embed_batch(texts: list[str]) -> list[list[float]]`
  - Batch embedding for efficiency during ingestion
  - Respects OpenAI batch limits (max 2048 inputs per call)
- Use the `openai` Python package
- API key sourced from environment variable or Supabase secrets

**Acceptance Criteria:**
- [ ] `embed_text` returns a 1536-dim vector for valid input
- [ ] `embed_batch` handles lists of 1-100 texts correctly
- [ ] Empty input returns error, not a crash
- [ ] Rate limiting is handled gracefully

---

### TASK 3: Chunking Engine

**Objective:** Build a Python module that takes a markdown document and produces semantically coherent chunks with metadata.

**Requirements:**
- Create `lib/chunker.py`
- Function `chunk_document(filepath: str, metadata_overrides: dict = None) -> list[Chunk]`
  - Reads a markdown file
  - Splits on `###` headers (section-level chunking)
  - If any section exceeds 800 tokens, split at next natural boundary:
    - Bullet points (`- ` or `* `)
    - Numbered items (`1. `, `2. `)
    - Sub-headers (`####`)
    - Double newlines (paragraph breaks)
  - Each chunk gets a preamble line: `[Project: X | Type: Y | Section: Z | Date: YYYY-MM-DD]`
  - Sub-chunks inherit parent section header

- `Chunk` dataclass:
```python
@dataclass
class Chunk:
    content: str              # the chunk text with preamble
    project_name: str
    document_type: str        # inferred or provided
    section_type: str | None  # inferred from header
    chunk_type: str | None    # inferred from content patterns
    source_file: str          # absolute path
    session_number: int | None
    confidence: str           # default 'high' for direct ingestion
    tags: list[str]           # extracted or provided
    project_phase: str | None
    source_tier: str          # default 'tier1_docs'
```

- Section-type inference rules:
  - Header contains "identity" or "project" → `identity`
  - Header contains "architecture" or "technical" → `architecture`
  - Header contains "decision" or "recent work" or "just happened" → `decisions`
  - Header contains "risk" or "wrong" or "bug" → `risks`
  - Header contains "constraint" or "do not" → `constraints`
  - Header contains "pattern" or "how to think" → `patterns`
  - Otherwise → `other`

- Chunk-type inference rules:
  - Content contains "decided", "chose", "selected", "because" → `decision`
  - Content contains "pattern", "approach", "strategy" → `pattern`
  - Content contains "bug", "broken", "error", "issue" → `pitfall`
  - Content contains "must", "shall", "required" → `requirement`
  - Content contains "constraint", "limitation", "do not" → `constraint`
  - Otherwise → `context`

- Token counting: Use `tiktoken` with `cl100k_base` encoding (matches OpenAI models)

**Acceptance Criteria:**
- [ ] Correctly splits a continuation document into section-level chunks
- [ ] Sections over 800 tokens are split at natural boundaries
- [ ] Each chunk has a preamble line
- [ ] Section-type and chunk-type are inferred correctly for standard continuation documents
- [ ] Metadata overrides work (e.g., force project_name, session_number)
- [ ] Token counting is accurate (within 5% of actual API tokenization)

---

### TASK 4: Ingestion Pipeline (ingest-document)

**Objective:** Build the end-to-end pipeline that takes a markdown file, chunks it, embeds it, and stores it in Supabase.

**Requirements:**
- Create `lib/ingest.py`
- Function `ingest_document(filepath: str, project_name: str, session_number: int = None, metadata_overrides: dict = None) -> IngestResult`
  1. Call `chunk_document()` to produce chunks
  2. Call `embed_batch()` to embed all chunk contents
  3. Insert all chunks + embeddings into `context_chunks` table via Supabase client
  4. **Auto-supersede (Layer 1):** Before inserting, query for existing chunks with same `project_name` + same `section_type` + earlier `session_number`. Mark those as `superseded = true`.
  5. Return `IngestResult` with counts and any errors

- `IngestResult` dataclass:
```python
@dataclass
class IngestResult:
    chunks_created: int
    chunks_superseded: int
    errors: list[str]
    document_type: str
    project_name: str
```

- Supabase client: Use `supabase-py` package
- Connection details from environment variables: `SUPABASE_URL`, `SUPABASE_KEY`

**Acceptance Criteria:**
- [ ] Ingests a continuation document end-to-end (file → chunks → embeddings → stored)
- [ ] Auto-supersedes older chunks of same project + section_type
- [ ] Returns accurate IngestResult
- [ ] Handles Supabase connection errors gracefully
- [ ] Idempotent: re-ingesting the same document doesn't create duplicates (check by source_file + session_number)

---

### TASK 5: Query Engine

**Objective:** Build the semantic search interface that retrieves relevant context from the vector store.

**Requirements:**
- Create `lib/query.py`
- Function `query_context(query_text: str, project_name: str = None, top_k: int = 5, threshold: float = 0.7, include_superseded: bool = False) -> list[QueryResult]`
  1. Embed the query text using `embed_text()`
  2. Call `match_context_chunks` Supabase function with the embedding and filters
  3. Return ranked results

- `QueryResult` dataclass:
```python
@dataclass
class QueryResult:
    id: str
    content: str
    similarity: float
    project_name: str
    document_type: str
    section_type: str | None
    chunk_type: str | None
    confidence: str
    date_created: str
    session_number: int | None
    source_file: str | None
```

- Function `query_multi(queries: list[str], project_name: str = None, top_k_per_query: int = 3, threshold: float = 0.7) -> list[QueryResult]`
  - Runs multiple queries (one per task sub-step)
  - Deduplicates results (same chunk_id from different queries)
  - Re-ranks by max similarity across queries
  - Returns aggregated, deduplicated results

- Function `format_context_brief(results: list[QueryResult]) -> str`
  - Formats retrieved chunks into a readable context brief
  - Groups by project, then by document_type
  - Includes similarity scores and confidence flags
  - Output is markdown, ready to inject into an AI prompt

**Acceptance Criteria:**
- [ ] Single query returns relevant chunks ranked by similarity
- [ ] Multi-query deduplicates and re-ranks correctly
- [ ] Project filter works (only returns chunks from specified project)
- [ ] Cross-project query works (project_name=None returns from all projects)
- [ ] Superseded chunks excluded by default, includable with flag
- [ ] `format_context_brief` produces clean, readable markdown

---

### TASK 6: Task Decomposition Engine (plan-task)

**Objective:** Build the LLM-driven task decomposition that converts a PRD task into queryable sub-steps.

**Requirements:**
- Create `lib/planner.py`
- Function `decompose_task(task_description: str, project_context: str = None) -> TaskPlan`
  1. Send the task description to a cheap LLM (e.g., `gpt-4o-mini`)
  2. System prompt instructs the model to:
     - Break the task into 3-7 concrete implementation sub-steps
     - Each sub-step should be a specific technical action (not vague)
     - Include technologies, patterns, and potential concerns
     - Output as a numbered list
  3. Parse the response into structured sub-steps
  4. Optionally include `project_context` (existing project identity/architecture) to ground the decomposition

- `TaskPlan` dataclass:
```python
@dataclass
class TaskPlan:
    original_task: str
    sub_steps: list[str]       # each is a queryable description
    model_used: str
    project_context_provided: bool
```

- Function `plan_and_query(task_description: str, project_name: str = None, top_k_per_step: int = 3) -> ContextBrief`
  - Orchestrates the full pipeline:
    1. Decompose task into sub-steps
    2. Query vector DB for each sub-step
    3. Aggregate and format results
  - Returns a ready-to-use context brief

- `ContextBrief` dataclass:
```python
@dataclass
class ContextBrief:
    task: str
    plan: TaskPlan
    retrieved_context: list[QueryResult]
    formatted_brief: str       # ready to inject into prompt
    total_chunks_retrieved: int
    projects_referenced: list[str]
```

- LLM call: Use `openai` package, model configurable via environment variable `CF_PLANNER_MODEL` (default: `gpt-4o-mini`)

**Acceptance Criteria:**
- [ ] Decomposes a vague task ("implement authentication") into 3-7 specific sub-steps
- [ ] Sub-steps are technical and specific enough to produce good semantic queries
- [ ] Project context (when provided) grounds the decomposition in the actual tech stack
- [ ] `plan_and_query` returns a complete ContextBrief with formatted output
- [ ] Model is configurable via environment variable
- [ ] Handles LLM API errors gracefully

---

### TASK 7: Agent Zero Skill Packaging

**Objective:** Package Context Fabric as an Agent Zero skill following the SKILL.md standard.

**Requirements:**
- Create `SKILL.md` at project root with:
  - Skill metadata (name, version, description, tags, author)
  - Prerequisites (Supabase account, OpenAI API key, Python packages)
  - Procedures for each operation:
    - **Ingest Document**: How to call the ingestion script with parameters
    - **Query Context**: How to query for relevant context
    - **Plan and Query Task**: How to run the full pipeline (decompose → query → brief)
    - **Status Check**: How to see what's in the DB
  - Configuration instructions (environment variables, Supabase setup)
  - Examples for each procedure

- Create entry-point scripts in `scripts/`:
  - `scripts/ingest.py` — CLI wrapper for `ingest_document()`
  - `scripts/query.py` — CLI wrapper for `query_context()` and `query_multi()`
  - `scripts/plan.py` — CLI wrapper for `plan_and_query()`
  - `scripts/status.py` — Shows DB stats (total chunks, by project, by type, superseded count)
  - `scripts/setup.py` — Runs Supabase provisioning SQL

- Each script accepts command-line arguments and prints results to stdout
- All scripts importable as modules too (for programmatic use)

- Create `requirements.txt`:
  - `openai`
  - `supabase`
  - `tiktoken`
  - `python-dotenv`

- Create `.env.example` with required variables:
  - `SUPABASE_URL`
  - `SUPABASE_KEY`
  - `OPENAI_API_KEY`
  - `CF_PLANNER_MODEL` (default: gpt-4o-mini)

**Acceptance Criteria:**
- [ ] SKILL.md follows the Agent Zero skill standard
- [ ] All four operations documented with examples
- [ ] CLI scripts work from terminal
- [ ] `requirements.txt` is complete and installable
- [ ] `.env.example` documents all required configuration
- [ ] An agent reading SKILL.md can use the skill without additional guidance

---

### TASK 8: Integration Testing

**Objective:** Validate the full pipeline works end-to-end with real project data.

**Test Plan:**

**Test 1 — Ingest the Context Fabric Continuation Document**
- Ingest `AI_Continuation_Document-19Mar2026-1738.md`
- Verify: correct number of chunks created, metadata populated, embeddings stored
- Verify: chunks are retrievable via direct Supabase query

**Test 2 — Single Query Retrieval**
- Query: "What vector database is being used and why?"
- Expected: Returns the architecture section discussing Supabase/pgvector
- Verify: similarity score > 0.75, correct project_name, not superseded

**Test 3 — Cross-Project Query (after ingesting a second project's docs)**
- Ingest a document from a different project (e.g., bulwark-ai if available, or a synthetic test doc)
- Query without project filter
- Verify: results from both projects returned, ranked by relevance

**Test 4 — Task Decomposition + Query Pipeline**
- Task: "Implement a caching layer for the query engine to avoid redundant embedding calls"
- Verify: decomposition produces 3-7 specific sub-steps
- Verify: each sub-step query returns relevant context (or empty if no match — that's valid for a new project)
- Verify: formatted brief is clean, readable markdown

**Test 5 — Auto-Supersede**
- Ingest the continuation document as session 1
- Create a modified version with updated architecture section, ingest as session 2
- Verify: session 1 architecture chunks are marked `superseded = true`
- Verify: default query returns only session 2 architecture chunks

**Test 6 — Idempotency**
- Ingest the same document twice with same session_number
- Verify: no duplicate chunks created

**Acceptance Criteria:**
- [ ] All 6 tests pass
- [ ] No unhandled exceptions
- [ ] Results documented in a test report

---

## 5. FILE STRUCTURE (TARGET)

```
/a0/usr/projects/context_fabric/
├── SKILL.md                              # Agent Zero skill definition
├── requirements.txt                      # Python dependencies
├── .env.example                          # Configuration template
├── AI_Continuation_Document-19Mar2026-1738.md  # Session 1 artifact
├── PRD.md                                # This document
├── lib/
│   ├── __init__.py
│   ├── embeddings.py                     # Embedding pipeline
│   ├── chunker.py                        # Chunking engine
│   ├── ingest.py                         # Ingestion pipeline
│   ├── query.py                          # Query engine
│   ├── planner.py                        # Task decomposition
│   └── config.py                         # Shared configuration (env vars, Supabase client)
├── scripts/
│   ├── ingest.py                         # CLI: ingest a document
│   ├── query.py                          # CLI: query context
│   ├── plan.py                           # CLI: decompose + query
│   ├── status.py                         # CLI: DB stats
│   └── setup.py                          # CLI: Supabase provisioning
├── sql/
│   └── setup.sql                         # Supabase provisioning SQL
└── tests/
    └── test_integration.py               # Integration test suite
```

---

## 6. TASK DEPENDENCY ORDER

```
TASK 1 (Supabase Provisioning)
  └─→ TASK 2 (Embedding Pipeline)
       └─→ TASK 3 (Chunking Engine)
            └─→ TASK 4 (Ingestion Pipeline)  ← depends on 1, 2, 3
                 └─→ TASK 5 (Query Engine)    ← depends on 1, 2
                      └─→ TASK 6 (Task Decomposition) ← depends on 5
                           └─→ TASK 7 (Skill Packaging) ← depends on all
                                └─→ TASK 8 (Integration Testing) ← depends on all
```

Tasks 2 and 3 can be built in parallel.
Task 5 can begin once Tasks 1 and 2 are complete.
Task 6 depends on Task 5.
Task 7 wraps everything.
Task 8 validates everything.

---

## 7. PHASE 2 ROADMAP (NOT IN MVP)

For reference only — do not build these yet:

- **Repo Seeding (`ingest-repo`)**: Scan existing repos, extract from 4 tiers, bulk ingest
- **MCP Server**: Expose Context Fabric as an MCP server for Cursor/Claude Code/VS Code
- **Semantic Collision Detection**: Auto-detect similar chunks during ingestion (superseded Layer 2)
- **Explicit SUPERSEDES Markers**: Parse override markers in documents (superseded Layer 3)
- **Related Chunks Linking**: Build explicit connections between related chunks
- **Temporal Chaining**: Zep-inspired decision history chains
- **Hierarchical Memory Tiers**: Mem0-inspired user/project/session scoping
- **Confidence Decay**: Time-based confidence reduction for aging chunks
- **Status Dashboard**: Visual overview of DB contents and freshness

---

*PRD generated: 19 March 2026*
*Status: Ready for implementation*
*First task: TASK 1 — Supabase Provisioning*
