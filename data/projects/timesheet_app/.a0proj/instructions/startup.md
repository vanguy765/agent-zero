# Timesheet App — Agent Startup Instructions

## ⚡ SESSION START PROTOCOL — Run this every session

At the start of EVERY session, immediately run the health check and notify the user of any missing critical services:

```bash
bash /a0/usr/projects/timesheet_app/voicelog-scaffold/scripts/dev-health.sh
```

Then use the `notify_user` tool for each failing critical service:
- **Supabase (Kong) down** → `notify_user` type=warning: "Supabase is not running on Windows. Please run `supabase start` in voicelog-scaffold on your Windows machine, then paste `supabase status` output here."
- **Doc Parser down** → `notify_user` type=warning: "Doc Parser is not running (port 5000). Start it with: `cd voicelog-scaffold/doc-parser && docker-compose up` on **Windows**. NEVER run server.py or install packages inside the doc-parser folder from this container."

Do NOT wait for the user to discover data issues — proactively notify at session start.

### 📋 Session Context Request
After running the health check, ask the user for session context using this prompt:

> **"To give you the best help today, please share:**
> 1. **Goal** — What are you building or fixing this session?
> 2. **Supabase status** — Paste output of `supabase status` from Windows (confirms services + current auth keys)
> 3. **pnpm install** — Did you run `pnpm install` on Windows since the last session? (yes/no)
> 4. **Errors** — Any error messages already showing? (paste or 'none')"

---

## 📖 Project Context — Read AGENTS.md

**AGENTS.md is the single source of truth for all AI assistants on this project.**

At session start, read the full project context from:
```
/a0/usr/projects/timesheet_app/voicelog-scaffold/AGENTS.md
```

This file (on the bind mount, always current) contains:
- Full architecture overview and monorepo structure
- Port assignments for all services
- Supabase credentials and environment flags
- Doc-parser endpoints and pipeline
- Stack start commands and troubleshooting

Do NOT rely on startup.md for project architecture — always read AGENTS.md.

> **How the sync works:**
> User edits `AGENTS.md` on Windows → runs `scripts/sync-agent-context.ps1`
> → auto-generates `CLAUDE.md`, `.cursorrules`, `.windsurfrules`
> → Agent Zero reads `AGENTS.md` directly (no sync needed — bind mount is live)

---

## 🖥️ Environment — Two Machines

| Where | What runs |
|---|---|
| **Windows host** | `supabase start` → full Supabase stack (Kong + PostgREST + GoTrue + Studio) |
| **Docker container (me)** | Node.js API, SolidJS frontends, Doc Parser, dev servers |

The container reaches the Windows Supabase stack via `host.docker.internal`.

### Bind Mount (critical)
The project directory is a **9p bind mount**:
```
/a0/usr/projects/timesheet_app/voicelog-scaffold/
  └── maps directly to →
C:\Users\3900X\Documents\GitHub\agentZero\voicelog-scaffold\
```
**Any file written in the container is instantly live on Windows. No git push needed.**

Git operations must be done on Windows (container has no git credentials).

### SUPABASE_URL
| Situation | SUPABASE_URL |
|---|---|
| Windows `supabase start` is running | `http://host.docker.internal:54321` ✅ Preferred |
| Windows Supabase is NOT running | `http://127.0.0.1:54330` ⚠️ Fallback proxy |

Current value in `packages/config/src/index.ts`: `http://host.docker.internal:54321`

---

## 🧹 Codebase Cleanup Protocol

### How to trigger
Just say any of these:
- **"clean up the codebase"**
- **"run cleanup"**
- **"clean up junk files"**

### What gets removed
| Pattern | Examples |
|---------|----------|
| `*.log` anywhere | `error.log`, `docker_logs.txt`, `db_reset_debug.log` |
| `*_debug.*` | `db_reset_debug.log`, `debug_write_test.txt` |
| `temp_*.*` | `temp_trace.txt`, `temp_docker_logs.txt` |
| `test_result*.json` | `test_result_docker.json`, `test_result_patched.json` |
| `old_*.*` | `old_server.py`, `old_server.ts` |
| `backups_*/` dirs | `backups_cv2_integration/`, `backups_page_render/` |
| `backup_*/` dirs | any backup directory |
| `__pycache__/` dirs | Python bytecode cache |
| `.turbo/daemon/*.log.*` | Turbo daemon log files |
| Loose `*.txt` in project root | `build_errors.txt`, `utf8_logs.txt` |
| Loose `*.json` result files in root | `full_result.json`, `jobs.json` |
| `dist/` in app dirs | `apps/*/dist/` (rebuilt by `pnpm build`) |

### What NEVER gets removed
- All source code (`*.py`, `*.ts`, `*.tsx`, `*.js`, `*.jsx`, `*.css`)
- Config files (`.env`, `*.toml`, `.npmrc`, `.gitignore`, `*.yaml`)
- Documentation (`docs/**`, `README.md`, `*.md` in source dirs)
- Database migrations (`supabase/migrations/**`)
- Scripts (`scripts/*.ps1`, `scripts/*.sh`)
- SQL files (`*.sql`)
- Lock files (`pnpm-lock.yaml`)
- `package.json`, `turbo.json`, `tsconfig*.json`, `vite.config.ts`
- `.a0proj/` (project instructions and memory)

---

## ⚠️ Known Issues & Fixes

### `work-orders#dev` fails with ELIFECYCLE exit code 1
**Cause:** Zombie Node.js process still holding port 3004 from a previous session.
**Fix:** Run `scripts/kill-dev-servers.ps1` on Windows before starting dev servers.

### `reset-and-start.ps1` — PowerShell parse error with `{{.Status}}`
**Cause:** PowerShell misinterprets `{{.Status}}` double-braces as a nested script block.
**Fix (already applied):** Assign the format string to a variable first:
```powershell
$fmt = '{{.Status}}'
$status = docker inspect --format $fmt doc-parser 2>$null
```

### `reset-and-start.ps1` references `kill-dev-servers.ps1`
The reset script calls `& "$PSScriptRoot\kill-dev-servers.ps1"` — there is only ONE copy of each script (in `scripts/`). Do not duplicate them.

### `reset-and-start.ps1` — doc-parser health check false negative
**Cause:** The doc-parser FastAPI app has no root `/` endpoint — it returns `404 Not Found`. PowerShell's `Invoke-WebRequest` throws an exception on any non-2xx response, so the health check treated a running service as down.
**Fix (already applied):** `Test-DocParserReady` helper function treats both 200 and 404 as "service is up".

### `vite-plugin-solid` (and other packages) not found on Windows — MODULE_NOT_FOUND
**Root cause:** pnpm installed inside the container creates Linux binaries with no `.cmd` wrapper files. Windows needs `.cmd` files to run `vite`, `turbo`, `tsx`.
**Fix:** Always run `pnpm install` on **Windows** after any container-side install:
```powershell
cd C:\Users\3900X\Documents\GitHub\agentZero\voicelog-scaffold
pnpm install
```
**`.npmrc` must not be deleted** — it sets `node-linker=hoisted` for cross-platform compatibility.

### `material-admin#dev` fails with ELIFECYCLE exit code 1
**Cause:** `apps/material-admin/vite.config.ts` had `port: 3002` — same as `site-companion`.
**Fix applied:** Changed to `port: 3003` to match `docs/ports.md`.
