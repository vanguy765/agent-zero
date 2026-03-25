# PROJECT CONTINUATION DOCUMENT
## Session 1 — 19 March 2026

### 1. PROJECT IDENTITY

- **Project Name:** Context Fabric
- **What This Project Is:** A persistent AI context layer that stores project state, architectural decisions, task plans, and session artifacts in a vector database (Supabase/pgvector) — enabling any fresh AI instance to resume work on any project with full contextual awareness. Packaged as an Agent Zero skill for portability.
- **Primary Objective:** Eliminate context loss between AI sessions by creating a queryable knowledge base that surfaces relevant prior decisions, patterns, and project state before any new task begins.
- **Strategic Intent:** Create a universal "AI project memory" that compounds in value over time. Every session, every decision, every architectural choice becomes retrievable context for future work — across projects, not just within one. This turns ephemeral AI conversations into durable institutional knowledge.
- **Hard Constraints:**
  - Must work across multiple unrelated projects (not siloed per-project)
  - Must support the workflow: PRD → task decomposition → context query → informed coding
  - Supabase with pgvector is the vector store (already in user's stack)
  - Must produce artifacts a fresh AI instance can consume with zero prior context
  - Must not require manual tagging or curation (automation-first)
  - Packaged as an Agent Zero skill (portable to other platforms)
  - Markdown is the source-of-truth document format

### 2. WHAT EXISTS RIGHT NOW

- **What is built and working:**
  - Project folder exists at `/a0/usr/projects/context_fabric/`
  - Agent Zero project scaffolding (`.a0proj/` with memory, knowledge, instructions structure)
  - The Continuation Document format itself (this document) is a proven artifact
  - Predecessor artifacts exist in the workspace: `SESSION_HANDOFF_PROTOCOL.md`, `bulwark-ai/` project with rich documentation (DECISIONS.md, CONTINUATION_PROMPT.md, PROJECT_STATUS.md, SPEC.md, GUIDE.md)

- **What is partially built:**
  - Nothing partially built — this is a greenfield project in design phase

- **What is broken or blocked:**
  - Nothing broken — no code exists yet

- **What has NOT been started yet:**
  - PRD (next step)
  - Vector DB schema / table design in Supabase
  - Embedding pipeline
  - Chunking implementation
  - Ingestion pipeline (document → chunks → embeddings → stored)
  - Query interface (task description → relevant context retrieval)
  - Task decomposition engine
  - Repo seeding capability
  - Agent Zero skill packaging (SKILL.md, scripts, procedures)
  - Any code whatsoever

### 3. ARCHITECTURE & TECHNICAL MAP

- **Tech stack (decided):**
  - Vector DB: Supabase with pgvector extension
  - Embedding model: OpenAI `text-embedding-3-small` ($0.02/1M tokens)
  - Runtime: Python (aligns with Agent Zero ecosystem)
  - Document format: Markdown
  - Packaging: Agent Zero skill (SKILL.md standard)
  - Future consideration: Also expose as MCP server for Cursor/Claude Code/VS Code portability

- **Key data entities (conceptual, not yet implemented):**
  - `ProjectRecord` — identity, stack, constraints, status
  - `DecisionRecord` — architectural decisions with rationale and tradeoffs
  - `SessionRecord` — what happened, what changed, what's next
  - `TaskPlan` — pre-execution logic plan for a PRD task
  - `CodePattern` — reusable patterns, solutions, and anti-patterns discovered

- **How the system works end-to-end (conceptual):**
  1. Developer has a PRD with defined tasks
  2. Before starting a task, the system decomposes it into logical sub-steps
  3. Each sub-step becomes a targeted semantic query against the vector DB
  4. The DB returns: related decisions from this project, similar patterns from other projects, known pitfalls, relevant code patterns
  5. Retrieved context is aggregated and injected into the AI's prompt as pre-task briefing
  6. The AI executes the task with full contextual awareness
  7. After the session, artifacts (decisions, changes, outcomes) are ingested back into the DB
  8. The cycle compounds — every session makes future sessions smarter

- **Skill operations (planned):**
  - `ingest-document` — feed a single artifact, chunk, embed, store
  - `ingest-repo` — point at a repo root, scan/extract/classify/bulk-load (cold-start seeder)
  - `query` — feed a task plan, retrieve relevant context
  - `plan-task` — feed a raw PRD task, decompose into logic plan (feeds into query)
  - `status` — show DB contents, freshness, project coverage

- **Chunking strategy (decided):**
  - Primary: Section-level chunks aligned to document headers (### sections)
  - Overflow: Split sections exceeding ~800 tokens at natural boundaries (bullets, sub-headers)
  - Sub-chunks inherit parent section header as preamble for standalone context
  - Special handling by document type: continuation docs (section-level), ADRs (one per decision), task plans (one per step), code patterns (one per pattern)
  - Every chunk gets a context preamble: `[Project: X | Type: Y | Section: Z | Date: YYYY-MM-DD]`

- **Metadata schema (decided, 14 fields):**

  | Field | Type | Purpose |
  |-------|------|--------|
  | `project_name` | string | Filter/search by project |
  | `date_created` | timestamp | Recency ranking |
  | `confidence` | enum: high/medium/low | Reliability flag |
  | `tags` | string[] | Free-form categorization |
  | `document_type` | enum | continuation_doc, adr, task_plan, code_pattern, session_note |
  | `session_number` | integer | Which session produced this |
  | `section_type` | enum | identity, architecture, decisions, recent_work, risks, constraints |
  | `chunk_type` | enum | decision, pattern, status, constraint, pitfall, requirement |
  | `source_file` | string | Original file path for traceability |
  | `superseded` | boolean | Flag when overridden by later decision |
  | `supersede_candidate` | uuid (nullable) | Points to similar older chunk detected during ingestion |
  | `project_phase` | enum | planning, design, implementation, testing, maintenance |
  | `related_chunks` | uuid[] | Explicit links between related chunks |
  | `source_tier` | enum | tier1_docs, tier2_code, tier3_git, tier4_comments |

- **Superseded detection (decided, 3 layers):**
  1. **Section-Type Replacement** (auto, high confidence): New continuation doc section auto-supersedes same project + same section_type + earlier session
  2. **Semantic Collision Detection** (auto, medium confidence): New chunk with cosine similarity > 0.85 to existing chunk flags `supersede_candidate` — query engine prefers newer
  3. **Explicit Markers** (manual, highest precision): `> SUPERSEDES: "description"` convention in documents, parsed by ingestion pipeline

- **External dependencies:**
  - Supabase account with pgvector extension enabled
  - OpenAI API key (for text-embedding-3-small)
  - Agent Zero framework (host environment)

### 4. RECENT WORK — WHAT JUST HAPPENED (HIGH PRIORITY)

- **What was worked on in this session:**
  - Full conceptual design of Context Fabric from initial idea to detailed architecture
  - Competitive landscape analysis (live research)
  - All major technical decisions made and documented with rationale
  - This is Session 1 — pure design, no code

- **What decisions were made and WHY:**
  1. **Supabase/pgvector over dedicated vector DB:** Already in user's stack, co-locates vectors + metadata, RLS for free, handles the scale (thousands to tens of thousands of chunks)
  2. **text-embedding-3-small over larger models:** Retrieval not reasoning — $0.02/1M tokens is negligible, quality sufficient for technical prose matching
  3. **Section-level chunking with 800-token overflow:** Preserves semantic coherence of decisions/rationale while handling variable-length sections
  4. **Task decomposition as query enrichment:** Core differentiator — decomposing "implement auth" into specific sub-steps produces dramatically better semantic matches than raw task titles
  5. **Cross-project scope:** Patterns, anti-patterns, and decisions transfer across projects. Siloing destroys compounding value
  6. **Agent Zero skill packaging:** Portable, self-contained, follows existing ecosystem. Future MCP server exposure for broader tool compatibility
  7. **Markdown as source of truth:** Human-readable, AI-readable, version-controllable, embeds well. Validated by OpenClaw making the same choice
  8. **Automation-first ingestion:** No manual tagging. System extracts structure from natural artifacts
  9. **Three-layer superseded detection:** Auto section replacement + semantic collision + explicit markers. Prevents stale context without manual curation
  10. **Repo seeding capability:** Cold-start solution. Extract from existing repos: structured docs (tier 1), code structure (tier 2), git history (tier 3), code comments (tier 4)

- **What changed in the system:** Nothing in code — founding design session

- **What was discussed but NOT yet implemented:**
  - Everything listed above — all decisions are design-level, no code exists
  - PRD needs to be written next
  - MCP server exposure (future consideration, not MVP)
  - Temporal chaining inspired by Zep (store decision chains, not just boolean superseded)
  - Hierarchical memory tiers inspired by Mem0 (user-level, project-level, session-level)

- **Open threads or unresolved questions:**
  1. Exact Supabase table schema (columns, indexes, RLS policies)
  2. Embedding dimension and distance metric for pgvector (cosine vs. inner product)
  3. Retrieval budget — how many chunks per sub-task query, total cap per task
  4. Task decomposition implementation — LLM-driven or template-based?
  5. MCP server exposure — when and how (post-MVP)
  6. How to handle the Agent Zero skill's Supabase credentials (secrets management)

### 5. COMPETITIVE LANDSCAPE (researched this session)

| Tool | What It Does | How Context Fabric Differs |
|------|-------------|---------------------------|
| **Mem0** | Dedicated memory layer, vector + knowledge graph, hierarchical memory, cloud-first | CF is self-hosted (Supabase), PRD-workflow-driven, cross-project. Mem0 is conversational memory, not project intelligence |
| **Zep (Graphiti)** | Temporal knowledge graph, time as first-class dimension, sub-100ms retrieval | CF should steal temporal chaining concept. Zep is conversation-focused, not PRD-task-driven |
| **Letta (MemGPT)** | LLM-driven memory management | Adds latency/cost per memory op. CF uses deterministic chunking + embedding, cheaper and faster |
| **ContextStream** | MCP server for coding assistant memory, indexes codebase, cross-session | Closest competitor. CF adds task decomposition, cross-project retrieval, repo seeding. Consider MCP compatibility |
| **OpenClaw Memory** | Markdown-based, plugin ecosystem, DAG summarization | Validates markdown-as-truth approach. Tied to OpenClaw ecosystem, not portable |
| **mcp-memory-keeper** | MCP server for Claude Code context persistence | Lightweight, focused. CF is broader (multi-project, PRD workflow, repo seeding) |
| **OpenViking (ByteDance)** | Open-source context database, OpenClaw-native | 15k+ stars, worth monitoring. Different scope (context DB vs. workflow-integrated intelligence) |

**Key differentiators no competitor has:**
- Task decomposition as query enrichment
- Cross-project knowledge transfer
- PRD → decompose → query → code workflow
- Repo seeding from existing codebases

### 6. WHAT COULD GO WRONG

- **Known bugs or issues:** N/A — no code exists
- **Edge cases to watch for:**
  - Cross-project context pollution (irrelevant results from unrelated projects with similar terminology)
  - Stale context presented as current (mitigated by superseded detection, but not foolproof)
  - Over-retrieval overwhelming AI context window
  - Under-retrieval from over-aggressive chunking
  - Embedding model changes breaking similarity scores for existing vectors

- **Technical debt or shortcuts taken:** None — clean slate

- **Assumptions that could be wrong:**
  - Semantic search over embedded markdown chunks produces sufficiently relevant results (needs validation)
  - Task decomposition produces better queries than simpler approaches (needs A/B testing)
  - Cross-project retrieval adds more value than noise (needs tuning)
  - text-embedding-3-small is sufficient quality (may need upgrade)
  - Agent Zero's existing memory system can't already do this with configuration (should verify)

### 7. HOW TO THINK ABOUT THIS PROJECT

1. **Core pattern:** An augmented retrieval system (RAG-adjacent) purpose-built for developer workflow. Not a chatbot, not a search engine — a **context compiler** that assembles relevant knowledge before each task. The pipeline is: generate structured artifacts → embed and store → retrieve semantically at decision time → inject as context.

2. **Most common mistake a new person would make:** Trying to build a general-purpose knowledge base or note-taking system. This is laser-focused on one workflow: PRD task → decompose → query → code. Every design decision serves that pipeline.

3. **What looks like it should be redesigned but intentionally should NOT be:** The Continuation Document format. It looks verbose and could be "optimized" into a compact schema. Don't. The verbosity enables good embeddings and serves as a standalone fallback. Structured schemas embed poorly.

### 8. DO NOT TOUCH LIST

- Do NOT build a general-purpose knowledge management system — stay focused on the PRD → task → context → code pipeline
- Do NOT skip the Task Logic Planning step — task decomposition IS the query enrichment
- Do NOT use a relational database as the primary store — vector search is the core capability
- Do NOT create a proprietary document format — Markdown is the standard
- Do NOT require manual tagging or curation — automate extraction
- Do NOT refactor the Continuation Document format into a compact schema — verbosity enables good embeddings
- Preserve cross-project retrieval design — do not silo per-project
- Ask before selecting new frameworks, libraries, or dependencies
- Do NOT rebuild conversational memory (Mem0/Zep territory) — focus on project intelligence

### 9. CONFIDENCE & FRESHNESS

| Section | Confidence | Notes |
|---------|-----------|-------|
| 1. Project Identity | ✅ HIGH | Defined this session |
| 2. What Exists | ✅ HIGH | Verified against project file tree |
| 3. Architecture | ✅ HIGH | All decisions made with rationale this session |
| 4. Recent Work | ✅ HIGH | This IS the session |
| 5. Competitive Landscape | ✅ HIGH | Live research conducted this session |
| 6. What Could Go Wrong | ⚠️ MEDIUM | Speculative — based on experience with similar systems |
| 7. How to Think | ✅ HIGH | Core philosophy established with clear reasoning |
| 8. Do Not Touch | ✅ HIGH | Directly derived from session decisions |

---

*Document generated: 19 March 2026, 17:38 PST*
*Next step: Write the PRD for Context Fabric*


---

## RESUME PROMPT

Copy-paste the following into a new AI conversation along with the continuation document:

```
You are resuming work on an ongoing AI-assisted software project.

Before doing ANYTHING else:

1. Read the attached file `AI_Continuation_Document-19Mar2026-1738.md` in its entirety.
2. Check the USER DIRECTIVE section at the bottom of this prompt.
3. Summarize your understanding of the current project state in 3-5 sentences.
4. State the specific next action you will take.
5. Ask clarification questions ONLY if something blocks execution.
6. Then begin working.

Rules:
- Do NOT guess or hallucinate project state. Everything you need is in the document.
- Do NOT refactor, rename, or redesign anything unless explicitly asked.
- Preserve all existing decisions and their documented rationale.
- If the document says "do not touch" something, do not touch it.
- Treat the Continuation Document as ground truth for project state.

---
USER DIRECTIVE (fill in or leave blank):

[Write your specific instruction here if you want the AI to do something specific next.
If left blank, the AI should analyze the project state, propose the most strategic
next action with brief reasoning, and wait for confirmation before proceeding.]
---
```
