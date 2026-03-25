# [Project Name] — Agent Zero Startup Instructions

## SESSION START PROTOCOL — Run this every session

### 1. Read project context
At session start, read the full project context from:
```
/path/to/your/project/AGENTS.md
```
This is the single source of truth for architecture, ports, credentials, and stack commands.
Do NOT rely on this startup.md for project architecture details.

### 2. Health check
Run any relevant health checks and notify the user of failing critical services.

### 3. Ask for session context
> "To give you the best help today, please share:
> 1. Goal — What are you building or fixing this session?
> 2. Services — Are all required services running? Any errors showing?
> 3. Recent changes — Anything changed outside this environment since last session?"

---

## Environment Notes

[Document your specific environment here.]
[Examples: two machines, bind mounts, Docker setup, OS differences]

---

## Cleanup Protocol

Trigger phrases: "clean up the codebase" / "run cleanup"

Remove: *.log, temp_*, *_debug.*, __pycache__/, dist/ in app dirs
Never remove: source code, config files, migrations, lock files, .a0proj/

---

## Known Issues & Fixes

[Document project-specific recurring issues here as you discover them.]
