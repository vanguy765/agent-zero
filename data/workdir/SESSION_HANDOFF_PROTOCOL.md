# Session Handoff Protocol — Universal Context Preservation Prompt

> **What this is**: Paste this prompt into any AI conversation when you're ready
> to end a development session and need to preserve full context for continuation.
> It instructs the AI to generate three documents that capture everything a new
> agent needs to pick up exactly where you left off.

---

## Prompt (copy everything below this line)

---

I need you to generate a complete session handoff package for this project so a
new AI agent can continue development without losing any context. Create the
following three documents:

---

### Document 1: DECISIONS.md — Architecture Decision Records

**Purpose**: Capture every significant design decision from our conversation(s)
so the next agent doesn't re-debate settled questions.

**Format**: Each decision as a numbered ADR with these sections:
- **ADR-NNN: Title** (with Date and Status: Accepted/Deferred/Superseded)
- **Context**: What situation or question prompted this decision
- **Decision**: What was decided (one clear sentence)
- **Alternatives Considered**: Table of options with why each was rejected
- **Rationale**: The reasoning chain — WHY this choice over the alternatives
- **Consequences**: What follows from this decision (trade-offs, constraints)

**What to extract from our conversation**:
- Every time we chose between options (technology, architecture, naming, approach)
- Every time we explicitly decided NOT to do something (and why)
- Every time we established a principle or constraint
- Every time we deferred something to later (and why it was deferred)
- Design philosophy decisions (patterns, conventions, standards)
- Trade-off analyses we performed

**Include a Table of Contents** linking to each ADR.
**Include a Version History table** at the end.

---

### Document 2: PROJECT_STATUS.md — Full Project Context

**Purpose**: Give a new agent the complete picture — where the project came from,
where it is, and where it's going.

**Required sections**:

#### 2a. Creator Vision
Leave a placeholder block for me to fill in:
```
> *[To be written by the project creator. Capture: why you started this,
> what problem you encountered, who it's for, what success looks like.]*
```

#### 2b. Project Evolution Narrative
Chronological account of how the project developed across our session(s):
- What was built in what order and why that sequence
- What discoveries or pivots happened during development
- What each phase produced and what it revealed
- Maturity rating per phase (★ scale) — what's battle-tested vs. recent

#### 2c. Current State Assessment
Three categories:
- ✅ **What's production-ready** (implemented, tested, documented)
- 📋 **What's drafted but not implemented** (discussed, designed, no code)
- ❌ **What doesn't exist yet** (identified as needed but not started)

#### 2d. Competitive Landscape / Prior Art
- What existing tools/libraries/standards overlap with this project
- How this project differs from each (specific differentiators)
- Positioning statement (one paragraph capturing unique value)

#### 2e. Open Questions
Numbered list (OQ-N) of unresolved design decisions:
- The question itself
- Context from our discussion
- Current leaning (if any)
- Sub-questions that need answering

#### 2f. Known Gaps & Technical Debt
Numbered list (TD-N) of known issues that need fixing:
- What's missing, outdated, or incomplete
- Not open questions — these are known problems with known solutions

#### 2g. Audience & Adoption Profile
- Primary and secondary target audiences
- Adoption barriers (in severity order)
- Adoption accelerators (in impact order)

---

### Document 3: CONTINUATION_PROMPT.md — Ready-to-Paste Handoff

**Purpose**: A self-contained prompt that can be pasted into a new conversation
to bootstrap the next agent with full context.

**Required sections**:

#### 3a. Creator Vision
Same placeholder as PROJECT_STATUS.md for me to fill in.

#### 3b. Context Files — Read These First
Table with reading order, file paths, what each captures, and line counts.
Explain WHY this reading order matters.

#### 3c. Project Identity
Name, tagline, version, file location, one-paragraph mission statement.

#### 3d. Architecture Summary
The core technical architecture in bullet form — enough for the agent to
understand the system without reading the full spec.

#### 3e. Design Philosophy
Non-negotiable principles that constrain all future decisions.

#### 3f. Current File Structure
Complete tree with annotations (line counts, test status, empty directories).

#### 3g. What's Implemented
Function/feature inventory with test coverage status.

#### 3h. Key Design Decisions (Summary)
One-line summaries referencing ADR numbers in DECISIONS.md.

#### 3i. Development Priorities
Prioritized next steps in High/Medium/Lower tiers with brief descriptions.

#### 3j. Known Technical Debt (Summary)
One-line summaries referencing TD numbers in PROJECT_STATUS.md.

#### 3k. Open Questions (Summary)
One-line summaries referencing OQ numbers in PROJECT_STATUS.md.

#### 3l. Environment Notes
File paths, build commands, test commands, runtime requirements.

---

## Quality Criteria

Before delivering, verify each document against these criteria:

### DECISIONS.md
- [ ] Every design choice from our conversation is captured
- [ ] Every rejected alternative is documented with reason
- [ ] Deferred decisions are marked with status "Deferred" and rationale
- [ ] Table of Contents links to all ADRs
- [ ] No decision requires reading our conversation to understand

### PROJECT_STATUS.md
- [ ] Evolution narrative covers every development phase chronologically
- [ ] Current state clearly distinguishes done / drafted / missing
- [ ] Open questions capture the actual uncertainty (not just the topic)
- [ ] Technical debt items are actionable (not vague)
- [ ] Creator Vision placeholder is present

### CONTINUATION_PROMPT.md
- [ ] Self-contained — an agent with ONLY this prompt can orient itself
- [ ] References all context files with correct paths
- [ ] Reading order is specified with rationale
- [ ] File structure matches actual project state
- [ ] Test status is current and verified
- [ ] Next steps are prioritized and actionable
- [ ] Creator Vision placeholder is present

---

## Delivery Instructions

1. Write all three files to the project root directory
2. Verify file sizes and line counts
3. Run any existing tests to confirm current status
4. Present a summary table of what was created
5. Remind me to fill in the Creator Vision sections before using

---

## Notes for the AI Agent

- **Extract, don't invent**: Every ADR must trace to an actual conversation.
  Don't fabricate decisions that weren't discussed.
- **Capture uncertainty**: If something was discussed but not resolved, it's
  an Open Question, not a Decision.
- **Be specific**: "We chose X over Y because Z" is useful.
  "We made some decisions" is not.
- **Include the reasoning chain**: The rationale section is the most valuable
  part of each ADR. Don't abbreviate it.
- **Verify before writing**: Check actual file paths, test results, and
  project state before documenting them.
- **The continuation prompt must work standalone**: An agent reading ONLY
  the continuation prompt should be able to start working immediately,
  with the other documents providing deeper context on demand.

---

*End of Session Handoff Protocol*
