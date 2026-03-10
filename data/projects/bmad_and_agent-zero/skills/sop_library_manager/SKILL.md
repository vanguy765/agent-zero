# SOP Library Manager

## Metadata
- **Name**: sop_library_manager
- **Version**: 1.1.0
- **Description**: Manages the SOP (Standard Operating Procedure) library in Supabase Storage and Database. Handles uploading, parsing, syncing, searching, and agent-driven creation of SOPs.
- **Tags**: sop, library, supabase, storage, database, procedures, trade, plumbing, electrical, hvac
- **Author**: Agent Zero
- **Created**: 2026-02-28
- **Updated**: 2026-02-28

## Overview

This skill provides a complete lifecycle manager for Standard Operating Procedures stored as `.md` files in Supabase Storage (`apps/voicelog/sops/`). It parses structured SOP markdown into database tables for fast retrieval of executive checklists, detailed steps, and recommended videos.

### Architecture

```
┌─────────────────────────────────────────────────────────┐
│                   SOP Library Flow                       │
│                                                         │
│  .md File ──► Upload to Storage ──► Parse Markdown      │
│                                         │               │
│                                         ▼               │
│                              ┌──────────────────┐       │
│                              │   sops (master)   │       │
│                              └────────┬─────────┘       │
│                    ┌──────────────────┼──────────────┐   │
│                    ▼                  ▼              ▼   │
│          sop_executive_    sop_detailed_   sop_recommended│
│          checklists        steps           _videos        │
│                                                         │
│  Search/Query ◄── Database Tables (fast retrieval)      │
│  Missing SOP? ──► Agent Request ──► Create + Upload     │
└─────────────────────────────────────────────────────────┘
```

### Database Tables

| Table | Purpose |
|---|---|
| `sops` | Master index — SOP number, trade, task, revision, status, storage path, file hash |
| `sop_executive_checklists` | Cached executive checklist items per procedure phase |
| `sop_detailed_steps` | Cached detailed step content per procedure phase |
| `sop_recommended_videos` | Cached video links organized by procedure phase |
| `sop_sync_log` | Audit trail for all library operations |
| `v_sop_library` | Convenience view with content counts |

### Storage

- **Bucket**: `apps`
- **Path**: `voicelog/sops/{filename}.md`
- **Format**: Structured markdown following SOP Authoring Guide (SOP-META-001)

## Prerequisites

- Supabase instance running (local or remote)
- Migration `20260228000001_sop_library.sql` applied
- Python packages: `supabase` (auto-installed if missing)

## Procedures

### 1. Upload an SOP to the Library

Uploads a `.md` file to Supabase Storage, parses it, and syncs all structured data to the database.

```bash
cd /a0/usr/projects/bmad_and_agent-zero
python skills/sop_library_manager/scripts/sop_manager.py upload <path-to-sop.md>
```

**Example:**
```bash
python skills/sop_library_manager/scripts/sop_manager.py upload docs/sop/SOP_Plumbing_Sink_Replacement.md
```

**Output:** JSON with sop_id, sop_number, sync counts for checklists/steps/videos.

### 2. Sync Database from Storage

Re-parses SOP files from storage and updates the database. Detects changes via MD5 hash.

```bash
# Sync all SOPs
python skills/sop_library_manager/scripts/sop_manager.py sync --all

# Sync a specific SOP
python skills/sop_library_manager/scripts/sop_manager.py sync PLB-SOP-001
```

### 3. Search the Library

Search by keyword across SOP number, trade, task name, and description.

```bash
python skills/sop_library_manager/scripts/sop_manager.py search "plumbing"
python skills/sop_library_manager/scripts/sop_manager.py search "outlet"
python skills/sop_library_manager/scripts/sop_manager.py search "sink"
```

### 4. List All SOPs

```bash
python skills/sop_library_manager/scripts/sop_manager.py list
```

### 5. Show SOP Details with Cached Data

Retrieves the full SOP record plus all cached checklists, steps, and videos from the database.

```bash
python skills/sop_library_manager/scripts/sop_manager.py show PLB-SOP-001
```

### 6. Check if SOP Exists — Request Creation if Not

This is the key workflow for agent integration. Checks the library for a matching SOP. If none found, generates an agent request payload with the prompt to create one.

```bash
python skills/sop_library_manager/scripts/sop_manager.py check "Plumbing" "Water Heater Replacement"
```

**If found:** Returns matching SOP records.
**If not found:** Returns an `agent_request` payload:
```json
{
  "found": false,
  "message": "No SOP found for 'Plumbing — Water Heater Replacement'. Agent creation requested.",
  "agent_request": {
    "action": "create_sop",
    "sop_number": "PLB-SOP-002",
    "trade_code": "PLB",
    "trade_name": "Plumbing",
    "task_name": "Water Heater Replacement",
    "prompt": "Create a complete Standard Operating Procedure for Plumbing — Water Heater Replacement..."
  }
}
```

### 7. Agent-Driven SOP Creation Workflow

When `check` returns `found: false`, the agent should:

1. **Read the agent_request payload** from the check result
2. **Call a subordinate agent** (developer profile) with the prompt from the payload
3. **The subordinate creates the SOP** following the Authoring Guide
4. **Upload the new SOP** using the `upload` command
5. **Verify** using the `show` command

See **AGENT_GUIDE.md** for detailed step-by-step instructions with exact tool calls.

## Documentation

| Document | Purpose |
|---|---|
| `SKILL.md` | This file — skill manifest (agentskills.io standard) |
| `README.md` | Human-readable overview with architecture, API reference, and schema docs |
| `AGENT_GUIDE.md` | Step-by-step guide for Agent Zero agents with exact tool call examples |

## File Tree

```
skills/sop_library_manager/
├── SKILL.md                          # Skill manifest
├── README.md                         # Human-readable documentation
├── AGENT_GUIDE.md                    # Agent Zero usage guide
└── scripts/
    └── sop_manager.py                # Main CLI + Python API
```

## Related Files

| File | Location | Purpose |
|---|---|---|
| Migration SQL | `supabase/migrations/20260228000001_sop_library.sql` | Database schema |
| Authoring Guide | `docs/sop/SOP_AUTHORING_GUIDE.md` | SOP writing standards |
| Template | `docs/sop/SOP_TEMPLATE.md` | Blank SOP template |
| Library Index | `docs/sop/SOP_INDEX.md` | Master SOP registry |
| Plumbing SOP | `docs/sop/SOP_Plumbing_Sink_Replacement.md` | Example SOP |
| Electrical SOP | `docs/sop/SOP_Electrical_Outlet_Replacement.md` | Example SOP |

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `SUPABASE_URL` | `http://host.docker.internal:54321` | Supabase API URL |
| `SUPABASE_SERVICE_ROLE_KEY` | Local dev key | Service role key for admin access |

> **Note**: When running inside Docker, use `host.docker.internal` to reach the host's Supabase. When running directly on the host, use `127.0.0.1`.

## Troubleshooting

| Issue | Solution |
|---|---|
| `Connection refused` | Ensure Supabase is running: `supabase status` |
| `relation "sops" does not exist` | Apply migration: `supabase db reset` or run the SQL manually |
| `Bucket not found` | Script auto-creates the bucket; check storage permissions |
| `Parse returns 0 items` | Verify SOP follows the Authoring Guide format exactly |
| `Hash unchanged` | File content identical to last sync; force with `sync` command |
| `Connection refused` (Docker) | Set `SUPABASE_URL=http://host.docker.internal:54321` |
