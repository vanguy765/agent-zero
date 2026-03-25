# [Project Name] — Agent Context

This file is the **single source of truth** for all AI assistants on this project.
Edit this file, then run `scripts/sync-agent-context.ps1` to update Claude/Cursor/Windsurf.
Agent Zero reads this file directly — no sync needed.

---

## Project Overview

[What the app does in 2-3 sentences.]

**Stack:** [e.g. Hono API · SolidJS · Supabase · Python service]

---

## Architecture

```
project-root/
├── apps/
│   ├── api/          # [description] — port XXXX
│   └── web/          # [description] — port XXXX
├── packages/
│   └── shared/       # [description]
└── [other dirs]
```

**Development workflow:** [e.g. Schema-first. Define in packages/schemas → API → UI]

---

## Port Assignments

| Port | Service |
|------|---------|
| 3000 | API     |
| 3001 | Web App |
| 5000 | [Other] |

---

## Local Credentials & Environment

| Key       | Value / Location         |
|-----------|-------------------------|
| DB URL    | `postgresql://...`       |
| Anon Key  | run `[command]` to get   |
| Studio UI | `http://localhost:XXXXX` |

---

## Environment Flags

| Variable     | Location | Effect         |
|--------------|----------|----------------|
| `FLAG=value` | `.env`   | [what it does] |

---

## Start Commands

```bash
# Start everything
[command]

# Kill zombie processes
[command]

# Reset database
[command]
```

---

## Key Docs

| File                    | Topic              |
|-------------------------|--------------------|
| `docs/architecture.md`  | Architecture dive  |
| `docs/testing.md`       | Test credentials   |

---

## Known Issues & Fixes

[Document recurring gotchas here as you discover them.]
