---
stepsCompleted: [step-01-init, step-02-discovery, step-02b-vision, step-02c-executive-summary, step-03-success, step-04-journeys, step-05-domain, step-06-innovation, step-07-project-type, step-08-scoping, step-09-functional, step-10-nonfunctional, step-11-polish]
inputDocuments: [product-brief-taskflow-2026-02-26.md]
workflowType: 'prd'
briefCount: 1
researchCount: 0
brainstormingCount: 0
projectDocsCount: 0
classification:
  projectType: web_app
  domain: general
  complexity: low
  projectContext: greenfield
---

# Product Requirements Document - TaskFlow

**Author:** Root
**Date:** 2026-02-26

## Executive Summary

TaskFlow is a mobile-first web application that replaces verbal coordination on construction remodeling sites with a shared, real-time digital task board. It targets small remodeling crews — typically 15 workers across 5 trades managing ~25 residential units — where a single site superintendent currently serves as the sole coordination bottleneck, manually directing each worker to their next task every morning.

Workers self-assign tasks by viewing a live board organized by unit and trade, claiming work through a single checkbox tap or voice command. The primary users are trades workers (electricians, plumbers, painters, laborers) who need instant task visibility with zero friction, and site superintendents who need to shift from human dispatchers to exception-focused managers.

TaskFlow solves a coordination problem, not a project management problem. It does not compete with Procore, Fieldwire, or other construction PM platforms. It competes with shouting across the job site.

### What Makes This Special

The core insight is that construction coordination fails at a human bottleneck, not a software gap. When one person's brain is the system of record for who goes where, every morning starts with a queue of workers waiting for instructions. TaskFlow eliminates that queue entirely.

The differentiator is radical simplicity for a hostile-to-technology environment: dirty hands, bright sunlight, zero patience for onboarding. The entire interaction model is a checkbox tap or a voice command like "Claim Unit 12." No logins in MVP, no complex navigation, no training required. Workers see their trades' tasks, tap to claim, and walk to the unit.

Users choose TaskFlow over alternatives because there are no alternatives at this level. Enterprise construction tools are overbuilt for a 15-person crew. Group texts and whiteboards don't provide real-time visibility. TaskFlow occupies the gap: structured enough to coordinate, simple enough to actually get used.

## Project Classification

| Dimension | Value |
|---|---|
| **Project Type** | Web App (Mobile-first PWA) |
| **Domain** | General — Construction Operations |
| **Complexity** | Low |
| **Project Context** | Greenfield |

## Success Criteria

### User Success

- **Elimination of coordination dependency**: 90% reduction in "where should I go?" questions directed at the superintendent by end of week 1.
- **Faster productive start**: Workers begin productive work within 15 minutes of site arrival (vs. current 30+ minutes waiting for direction).
- **Self-directing workforce**: 80%+ of daily tasks are self-assigned by workers through the board, not directed by the superintendent.
- **Blocked work prevention**: At least 1 blocked-work incident per week is caught via the board before a worker physically arrives at an occupied or unready unit.
- **Zero-friction interaction**: Workers complete the claim-a-task flow in under 10 seconds via tap or voice — no training, no onboarding friction.

### Business Success

- **Rapid crew adoption**: 80% of crew actively using TaskFlow daily by day 3 of rollout.
- **Organic stickiness**: Superintendent stops reminding workers to check the app by end of week 1 — usage becomes self-sustaining.
- **Measurable time recovery**: 30 minutes saved per worker per day (7.5 hours total crew savings for a 15-person crew), measured at 2-week mark.
- **Superintendent liberation**: Superintendent spends <20% of the day on task direction (down from ~50%), freeing capacity for quality management and problem-solving.
- **Go/No-Go gate**: All four metrics above met at the 2-week mark triggers green light for V2 investment.

### Technical Success

- **Real-time sync latency**: Board state updates propagate to all connected clients within 2 seconds of any change.
- **Mobile performance**: First meaningful paint under 3 seconds on a mid-range Android phone over 4G. Interaction response under 200ms.
- **Voice command reliability**: Voice-to-action success rate ≥85% in outdoor construction site noise conditions.
- **Offline resilience**: App remains usable for viewing last-known board state when connectivity drops; syncs automatically on reconnection.
- **Concurrent capacity**: Supports 25+ simultaneous users on a single project board without degradation.

### Measurable Outcomes

| Metric | Target | Measurement Method | Timeframe |
|--------|--------|-------------------|----------|
| Daily Active Users | 80%+ of crew | TaskFlow usage logs | Day 3 |
| Task Claim Rate | 80%+ self-assigned | Claimed vs. super-assigned ratio | Week 1 |
| Blocked Task Detection | ≥1/week caught early | Tasks flagged blocked before worker arrival | Week 2 |
| Site Throughput | Measurable increase in units/week | Pre vs. post TaskFlow comparison | Week 2 |
| Super Satisfaction | Weekly qualitative rating | "How much time did TaskFlow save you?" | Ongoing |

## Product Scope & Phased Development

### MVP Strategy & Philosophy

**MVP Approach:** Problem-Solving / Validation MVP

The MVP exists to answer one question: *Does replacing verbal coordination with a shared digital board change crew behavior?* Every feature included must directly serve this validation. Every feature excluded is deferred until the answer is "yes."

**MVP Success Gate:** All four business success metrics met at the 2-week mark (80% daily adoption, 80% self-assigned tasks, measurable time savings, superintendent time recovery) triggers V2 investment.

**Resource Estimate:** 1 full-stack developer, 4–6 weeks. Target architecture: mobile-first offline-capable web client with low-latency real-time sync and lightweight persistence.

### MVP — Minimum Viable Product

**Core User Journeys Supported:**
- ✅ Carlos Claims His First Task (Worker Happy Path)
- ✅ Carlos Hits a Blocked Unit (Worker Edge Case)
- ✅ Mike Sets Up the Board (Admin/Setup Path)
- ✅ Mike Manages the Day (Superintendent Monitoring)
- ❌ Sarah Checks Progress Remotely (deferred to V2)

| # | Feature | Description | Why Essential |
|---|---------|-------------|---------------|
| 1 | **Unit Board** | Grid/list of all units with status: Available, In-Progress, Done, Blocked | The product's core — single source of truth replacing the superintendent's mental model |
| 2 | **Multi-Trade Tagging** | Workers select one or more trades on first use (e.g., Laborer + Painter) | Reflects real-world reality where workers carry multiple trades |
| 3 | **Board Filtering** | Filter by trade; defaults to worker's own trades; preferences remembered | Prevents information overload — Carlos sees electrical, not plumbing |
| 4 | **Task Claiming** | Tap checkbox to claim a unit task; name and trade appear on the board | The core interaction replacing "Hey Mike, where should I go?" |
| 5 | **Live Board** | Real-time updates — everyone sees claims, completions, and blocks as they happen | Eliminates the information vacuum that causes wasted trips |
| 6 | **Voice Commands** | "Claim Unit 12" / "Mark Unit 7 electrical done" — hands-free operation | Non-negotiable for dirty-hands, job-site reality |

### Explicitly Excluded from MVP

| Feature | Reason for Exclusion | Workaround |
|---------|---------------------|------------|
| User authentication | Adds friction; single-crew doesn't need it | Shared link + localStorage identity |
| Remote PM dashboard | Not needed to validate core hypothesis | Mike screenshots the board |
| Automatic dependency blocking | Requires usage data to design correctly | Manual "blocked" status flag |
| Photo documentation | Enhancement, not coordination | Workers use phone camera separately |
| Historical analytics | Premature — need data first | Manual observation at 2-week gate |
| Multi-site support | V1 is one crew, one project | Separate board per project |

### Growth Features (Post-MVP)

| Phase | Feature | Rationale |
|-------|---------|----------|
| **V2** | Remote PM Dashboard | Sarah's view — real-time progress visibility without calling Mike |
| **V2** | Automatic Dependency Blocking | Replace manual "blocked" flags with trade-dependency logic learned from V1 usage patterns |
| **V2** | Photo Documentation | Natural extension of task completion — visual proof of work |
| **V2** | Historical Reports & Analytics | Progress tracking for PMs and property owners |
| **V2** | User Accounts & Auth | Required foundation for multi-site and data security |

### Vision (Future)

| Phase | Milestone | Key Additions |
|-------|-----------|---------------|
| **V3** | Multi-site, multi-crew | Site switching, GC oversight view, cross-project visibility |
| **V4** | City-wide platform | Crew marketplace, trade scheduling across projects, reputation system |

The MVP is the wedge — prove it works for one crew, then expand outward.

### Risk Mitigation Strategy

**Technical Risks:**

| Risk | Severity | Mitigation |
|------|----------|------------|
| Voice recognition fails in construction noise | Medium | Voice is enhancement, not dependency. Tap-first design ensures MVP works without voice. Degrade gracefully. |
| Real-time sync unreliable on job sites | High | Offline-first architecture. Last-known board state cached locally. Auto-reconnect with visual indicator. |
| PWA limitations on iOS Safari | Medium | Core features (board, claiming) work in any browser. PWA install is nice-to-have. |
| localStorage identity loss | Low | Cookie + localStorage redundancy. Worst case: re-enter name and trade (10 seconds). |

**Market Risks:**

| Risk | Severity | Mitigation |
|------|----------|------------|
| Workers won't adopt voluntarily | High | Superintendent introduces it. Zero-friction design. If board is faster than waiting for Mike, adoption follows. |
| Superintendent feels replaced/threatened | Medium | Frame as "liberation" not replacement. Mike gains quality-check time. |
| One crew success doesn't generalize | Medium | V1 validates the concept. V2 tests with different crew sizes and trade mixes. |

**Resource Risks:**

| Risk | Severity | Mitigation |
|------|----------|------------|
| Solo developer bottleneck | Medium | MVP scope is deliberately small. Use managed backend services to reduce infrastructure work. |
| Scope creep during development | High | MVP feature list is frozen. Any addition requires removing something else. |
| Timeline exceeds 6 weeks | Low | Phased delivery: board-only in week 2, claiming in week 3, voice in week 5. Usable at each stage. |

## User Journeys

### Journey 1: Carlos Claims His First Task (Worker Happy Path)

**Persona:** Carlos, electrician, 10 years in the trade. Smartphone in his back pocket. Zero patience for apps.

**Opening Scene:** It's 6:55am on a Tuesday. Carlos pulls into the gravel lot at the Riverside Apartments remodel — 25 units, five trades, controlled chaos. Normally he'd find Mike standing by the trailer with a clipboard and a coffee, rattling off assignments to a semicircle of workers. Today Mike just says: "Check the board. Link's on the group text."

**Rising Action:** Carlos taps the link on his phone. A simple page loads — no login, no signup. It asks one thing: his name and trade. He types "Carlos" and taps "Electrical." The board appears — a list of units, each showing what trades are needed. He filters to electrical. Units 4, 7, 12, and 18 need rough-in. Unit 12 is closest to where he parked.

**Climax:** Carlos taps the checkbox next to "Unit 12 — Electrical Rough-In." His name appears on the board. Done. He pockets his phone and walks to Unit 12. It took nine seconds. He didn't talk to Mike. He didn't wait in line. He didn't walk to the wrong unit.

**Resolution:** By 7:05am Carlos is pulling wire in Unit 12. He checks the board at lunch — Units 4 and 7 are claimed by Ricky, Unit 18 is still open. He claims it for the afternoon. At 3pm he taps "Done" on both units. Tomorrow morning he won't even think about it — he'll just check the board like checking the weather.

**Capabilities Revealed:** Trade selection on first use, board filtering by trade, one-tap task claiming, real-time status updates, remembered preferences.

### Journey 2: Carlos Hits a Blocked Unit (Worker Edge Case)

**Persona:** Same Carlos, one week into using TaskFlow. He's a convert.

**Opening Scene:** Wednesday morning. Carlos checks the board over coffee in his truck. Three electrical tasks are available. He taps Unit 9 — it's a big unit, good for a full morning.

**Rising Action:** Carlos walks into Unit 9 and immediately sees the problem: plumbing rough-in isn't finished. Pipes are half-run, tools are sitting out, but no plumber in sight. He can't start electrical until plumbing is done — wires go behind the pipes.

**Climax:** Carlos pulls out his phone, finds Unit 9 on the board, and taps the status from "In-Progress" to "Blocked." He adds a quick note via voice: "Plumbing not done, can't start electrical." The board updates instantly. Mike sees the block notification. Meanwhile, Carlos unclaims Unit 9 and claims Unit 15 instead — no time wasted, no hunting for Mike to ask what to do.

**Resolution:** Mike sees the block, finds out the plumber called in sick, and reassigns plumbing coverage. By afternoon, Unit 9 is unblocked and another electrician claims it. The blocked-work incident that would have cost an hour of idle time cost Carlos three minutes.

**Capabilities Revealed:** Status change (to Blocked), voice-input notes, unclaim/reclaim flow, block visibility for superintendent, real-time notification of status changes.

### Journey 3: Mike Sets Up the Board (Admin/Setup Path)

**Persona:** Mike, site superintendent. First on site, last to leave. Keeps the entire project in his head — until today.

**Opening Scene:** It's Sunday evening before the Monday kickoff of a new 25-unit remodel. Mike is at his kitchen table with the unit list from the project manager. He's been dreading the usual Monday morning chaos — 15 workers showing up, all asking where to go at once.

**Rising Action:** Mike opens TaskFlow on his laptop. He creates a new project: "Riverside Apartments." He adds 25 units — typing each unit number. For each unit, he tags which trades are needed: demolition first, then plumbing and electrical rough-in, then drywall, then paint. It takes him about 10 minutes. He marks Units 1–5 as "Available" for demolition since those are ready to start. The rest stay in a "Not Ready" state.

**Climax:** Mike looks at the board and for the first time sees his entire mental model laid out visually. Twenty-five units, five trades, clear statuses. He copies the board link and drops it in the crew group text: "New app for tomorrow. Open this link when you get to site. Pick your trade, pick a unit, get to work. No more waiting for me."

**Resolution:** Monday morning, Mike stands by the trailer and watches. Workers trickle in, pull out phones, and start claiming units. By 7:10am, all five demolition units are claimed and workers are walking to their spots. Nobody asked Mike where to go. He sips his coffee and walks the site checking quality instead of directing traffic.

**Capabilities Revealed:** Project creation, unit management (add/edit), trade-to-unit assignment, bulk status setting, shareable board link (no auth), board overview/dashboard view.

### Journey 4: Mike Manages the Day (Superintendent Monitoring)

**Persona:** Same Mike, two weeks into using TaskFlow. The board is his command center.

**Opening Scene:** It's 9:30am. Mike is walking the site doing quality checks — something he never had time for before TaskFlow. His phone buzzes: Unit 9 just went to "Blocked" status.

**Rising Action:** Mike opens the board and sees Carlos's voice note: "Plumbing not done, can't start electrical." He checks the plumbing row — Hector was supposed to finish Unit 9 yesterday but it still shows "In-Progress." Mike calls Hector, who says he got pulled to Unit 14 for an emergency fix. Mike scans the board for available plumbers — Danny just finished Unit 6 and hasn't claimed anything new.

**Climax:** Mike walks over to Danny: "Unit 9 needs plumbing finished before electrical can start. Can you knock it out this morning?" Danny claims Unit 9 on the board. Within minutes, the block is being resolved. Mike didn't discover this problem by stumbling into Unit 9 at 2pm — he caught it at 9:30am because the board told him.

**Resolution:** By end of day, Mike reviews the board: 18 of 25 units have active work, 3 are blocked (all with notes explaining why), and 4 are complete. He screenshots the board and texts it to Sarah, the PM. "Day 9 status — no call needed." He saved two hours today that he would have spent answering "where should I go?" questions.

**Capabilities Revealed:** Real-time block notifications, voice note visibility, board-wide status overview, worker activity tracking, screenshot-friendly board layout.

### Journey 5: Sarah Checks Progress Remotely (V2 Scope — No MVP FRs Assigned)

**Persona:** Sarah, remote project manager. Oversees three remodeling projects from the office.

**Opening Scene:** It's 2pm. The property owner just called Sarah asking for a progress update on Riverside Apartments. Normally she'd have to call Mike, interrupt his work, and get a verbal summary she'd scribble into a spreadsheet.

**Resolution (V2 Vision):** Sarah opens TaskFlow on her laptop, selects the Riverside project, and sees the real-time board. 20 of 25 units show progress. She generates a status snapshot — a simple summary showing units complete, in-progress, and blocked — and emails it to the property owner. Total time: 90 seconds. Mike's phone never rang.

**Capabilities Revealed (V2):** Remote dashboard access, multi-project view, status snapshot/report generation, stakeholder-friendly output.

### Journey Requirements Summary

| Journey | Key Capabilities Revealed |
|---------|-------------------------|
| **Carlos Happy Path** | Trade selection, board filtering, one-tap claiming, real-time updates, preference memory |
| **Carlos Edge Case** | Status changes (Blocked), voice notes, unclaim/reclaim, block notifications |
| **Mike Setup** | Project creation, unit management, trade-to-unit assignment, shareable link, no-auth access |
| **Mike Monitoring** | Real-time alerts, board overview, worker activity visibility, screenshot-friendly layout |
| **Sarah Remote (V2)** | Remote dashboard, multi-project view, report generation |

**MVP capability set derived from journeys:** Project setup, unit board with statuses, multi-trade tagging, board filtering, one-tap claiming, voice commands, real-time sync, block status with notes, shareable no-auth link, superintendent overview.

## Web App Specific Requirements

### Project-Type Overview

TaskFlow is a mobile-first Progressive Web App (PWA) built as a Single Page Application. The architecture prioritizes real-time data synchronization, offline resilience, and extreme interaction simplicity over traditional web app concerns like SEO, complex routing, or rich content rendering.

### Browser & Device Matrix

| Target | Priority | Minimum Version | Notes |
|--------|----------|----------------|-------|
| Chrome Android | **Primary** | Last 2 major versions | 70%+ of crew devices |
| Safari iOS | Secondary | iOS 15+ | iPhone users on crew |
| Chrome Desktop | Setup only | Last 2 major versions | Mike's project setup flow |
| Safari Desktop | Setup only | Last 2 major versions | Fallback for Mac users |

**Not supported:** Internet Explorer, Firefox Mobile, Opera Mini, or any browser without WebSocket support.

### Responsive Design Strategy

- **Mobile (320px–480px)**: Primary design target. Single-column board layout. All interactions reachable with one thumb. Minimum tap target: 48x48px.
- **Tablet (481px–1024px)**: Enhanced board density — two-column unit grid. Superintendent monitoring view.
- **Desktop (1025px+)**: Project setup and administration. Multi-column board with expanded unit detail. Not optimized for daily worker use.

### Performance Targets

See Non-Functional Requirements for specific performance targets.

### SEO Strategy

**Not applicable.** TaskFlow is a private coordination tool accessed via direct shared links. No public-facing pages, no search engine indexing needed. `robots.txt` disallows all crawling. Board URLs use opaque project IDs, not human-readable slugs.

### Accessibility Approach

TaskFlow's accessibility strategy is driven by its hostile-environment context rather than traditional WCAG compliance:

- **Voice-first interaction**: Primary accessibility feature — hands-free operation via voice commands ("Claim Unit 12", "Mark done")
- **High contrast mode**: Default UI uses high-contrast colors readable in direct sunlight
- **Large touch targets**: Minimum 48x48px tap areas; claim checkboxes oversized for gloved/dirty hands
- **Minimal text dependency**: Status communicated through color + icon + position, not text-heavy UI
- **Screen reader compatible**: Semantic HTML with ARIA labels for standard assistive technology support
- **No fine motor requirements**: No drag-and-drop, no small buttons, no hover states required

### Real-Time Architecture Considerations

- **Protocol**: Low-latency bidirectional messaging with fallback channel for environments blocking primary protocol upgrades
- **Reconnection**: Automatic reconnect with exponential backoff; visual indicator when disconnected
- **Conflict resolution**: Last-write-wins for status changes; optimistic UI with server reconciliation
- **State management**: Client maintains local board state; server pushes deltas, not full board refreshes

### Implementation Considerations

- **PWA manifest**: Configured for standalone display mode, portrait orientation lock on mobile
- **Offline strategy**: Cache-first for static assets, network-first for board data with local fallback to last-known state
- **No authentication in MVP**: Board access via shareable URL with opaque project ID (security through obscurity, acceptable for MVP)
- **Voice integration**: Browser-native speech recognition APIs where available; graceful fallback to manual input if unsupported or permission denied

## Functional Requirements

### Board Management

- FR1: Superintendent can create a new project board by defining a project name
- FR2: Superintendent can define units (rooms/apartments) on a project board with unit identifiers
- FR3: Superintendent can assign one or more trade types to each unit
- FR4: Superintendent can set unit status (available, in-progress, blocked, complete)
- FR5: Superintendent can generate a shareable link for the project board
- FR6: Superintendent can edit project board configuration after creation (add/remove units, modify trades)

### Task Visibility

- FR7: Any crew member can view the full project board showing all units and their current statuses
- FR8: Crew member can filter the board to show only units matching their trade(s)
- FR9: Crew member can see which units are available, in-progress, blocked, or complete at a glance via visual status indicators
- FR10: Crew member can see who has claimed a unit currently in-progress
- FR11: Crew member can view notes attached to a blocked unit explaining the blocking reason

### Task Coordination

- FR12: Crew member can claim an available unit with a single interaction
- FR13: Crew member can mark their claimed unit as complete
- FR14: Crew member can release a claimed unit back to available status
- FR15: Crew member can add a status note when updating a unit (e.g., "paint drying, back tomorrow")
- FR16: System prevents multiple crew members from claiming the same unit simultaneously
- FR16a: Crew member can flag a unit as blocked and provide a reason (e.g., "drywall not finished", "no power to unit")
- FR16b: Crew member can remove a block on a unit when the blocking condition is resolved
- FR16c: System records who set and who cleared each block for accountability

### Real-Time Communication

- FR17: All board changes propagate to all connected clients within the performance target window
- FR18: System displays a visual indicator when a client loses server connection
- FR19: System automatically reconnects when connection is restored and syncs board state
- FR20: System maintains a viewable cached board state when offline
- FR21: System resolves conflicting simultaneous updates using last-write-wins with optimistic UI

### Voice Interaction

- FR22: Crew member can issue voice commands to claim a unit (e.g., "Claim Unit 12")
- FR23: Crew member can issue voice commands to update unit status (e.g., "Mark done")
- FR24: Crew member can add voice-dictated notes to a unit
- FR25: System provides visual confirmation of recognized voice commands before executing
- FR26: System gracefully degrades to manual input when voice recognition is unavailable or denied

### Crew Identity

- FR27: First-time visitor can establish a lightweight identity by entering their name and selecting their trade(s)
- FR28: System persists crew member identity locally across browser sessions
- FR29: System associates crew member actions (claims, completions) with their identity
- FR30: Crew member can update their name or trade associations

### Superintendent Operations

- FR31: Superintendent can view an overview of all units with aggregated progress statistics
- FR32: Superintendent can mark any unit as blocked and attach a reason note
- FR33: Superintendent can unblock a unit, returning it to available status
- FR34: Superintendent can reassign or unclaim a unit currently claimed by a crew member
- FR35: Superintendent can see a summary of crew activity (who claimed what, when)
- FR35a: Superintendent can view a log of block/unblock actions by crew members

## Non-Functional Requirements

### Performance

- NFR1: Board state changes propagate to all connected clients within 2 seconds under normal network conditions
- NFR2: Initial board load completes within 3 seconds on a 3G mobile connection
- NFR3: Voice command recognition completes within 1 second of utterance end
- NFR4: UI interactions (tap to claim, status change) provide visual feedback within 100ms
- NFR5: System supports 20 concurrent users on a single project board without performance degradation

### Reliability & Availability

- NFR6: When network connection is lost, 100% of board read operations (viewing units, statuses, notes) remain available from local cache; write operations (claims, status changes) queue locally and sync within 5 seconds of reconnection
- NFR7: System automatically detects connection loss and displays status indicator within 5 seconds
- NFR8: System automatically reconnects and syncs board state when connectivity is restored, without user intervention
- NFR9: No board data is lost during network interruptions — all local actions queue and sync on reconnection
- NFR10: System resolves sync conflicts using server-timestamp last-write-wins; concurrent claim attempts on the same unit resolve to a single owner within 2 seconds; acceptance test: 10 simultaneous claim requests produce exactly 1 winner with 0 data corruption
- NFR11: After browser refresh, user identity (name + trade) and current board view (filters, scroll position) restore within 2 seconds; no locally queued actions are lost; acceptance test: refresh during active session preserves identity and pending actions 100% of the time

### Accessibility (Construction Environment)

- NFR12: All interactive elements have minimum touch target size of 48x48px (gloved finger operation)
- NFR13: Board status indicators are distinguishable by both color AND shape/icon (sunlight washout, color blindness)
- NFR14: All critical information maintains readable contrast ratio in direct sunlight (minimum 7:1 contrast)
- NFR15: Voice interaction provides an alternative input path for all primary actions (claim, complete, block, note)
- NFR16: Application is fully usable in portrait orientation on devices 5" and larger
- NFR17: No interaction requires two-handed operation

### Security & Data Integrity

- NFR18: Board data transmitted over HTTPS (TLS 1.2+)
- NFR19: Shareable project links use unguessable tokens (minimum 128-bit entropy)
- NFR20: System prevents race conditions on unit claiming (server-authoritative state)

### Scalability (Growth Path)

- NFR21: Architecture supports horizontal scaling to 100 concurrent project boards and 500 simultaneous connected users without fundamental redesign; V2 scaling validated by load test demonstrating <3s board sync at target concurrency
- NFR22: Data model supports addition of user authentication layer with zero-downtime migration; existing board data, crew identities, and historical actions remain accessible post-migration; acceptance test: auth layer added without DROP/recreate of core tables

## Appendix A: Implementation Notes

> **Note:** These are recommended implementation choices, not requirements. The PRD sections above define *what* the system must do; this appendix captures *how* the team may choose to build it. Alternative technologies that meet the stated NFRs are equally valid.

### Recommended Technology Stack

| Layer | Recommendation | Rationale |
|-------|---------------|----------|
| **Frontend** | React or Vue (PWA) | Component model suits board UI; strong PWA tooling |
| **Runtime** | Node.js | JavaScript full-stack simplifies solo-dev workflow |
| **Real-Time** | WebSocket (primary) + SSE (fallback) | Low-latency bidirectional sync; SSE for restricted networks |
| **Database** | PostgreSQL or Firebase | PostgreSQL for relational integrity; Firebase for rapid prototyping |
| **Offline** | Service Worker (cache-first static, network-first data) | Standard PWA offline pattern |
| **Voice** | Web Speech API | Browser-native; no external service dependency |

### PWA Configuration

- Standalone display mode, portrait orientation lock on mobile
- Service worker registered at root scope
- App manifest with construction-appropriate icons and theme colors

### Architecture Decision Records

ADRs for significant technology choices should be maintained in `docs/architecture/` as the project progresses.
