# SOP Library Manager

> **Skill for Agent Zero** — Manages a Supabase-backed library of Standard Operating Procedures (SOPs) for trade work.

---

## Table of Contents

1. [What It Does](#what-it-does)
2. [Architecture](#architecture)
3. [Quick Start](#quick-start)
4. [CLI Reference](#cli-reference)
5. [Python API Reference](#python-api-reference)
6. [Database Schema](#database-schema)
7. [File Structure](#file-structure)
8. [Environment Variables](#environment-variables)
9. [Troubleshooting](#troubleshooting)

---

## What It Does

The SOP Library Manager provides a **complete lifecycle** for Standard Operating Procedures:

| Capability | Description |
|---|---|
| **Upload** | Push `.md` SOP files to Supabase Storage |
| **Parse** | Extract executive checklists, detailed steps, and video links from structured markdown |
| **Sync** | Keep the database in sync with storage (change detection via MD5 hash) |
| **Search** | Full-text keyword search across SOP number, trade, task, and description |
| **Show** | Retrieve complete SOP data including all cached sub-tables |
| **Check & Request** | Look up whether an SOP exists; if not, generate an agent-ready creation prompt |

### Who Is This For?

- **Agent Zero agents** that need to find, retrieve, or create SOPs during task execution
- **Developers** building trade-management applications on top of the SOP library
- **Administrators** maintaining the SOP library and ensuring quality standards

---

## Architecture

```
┌──────────────────────────────────────────────────────────────┐
│                    SOP Library Manager                        │
│                                                              │
│  ┌──────────┐    ┌──────────────┐    ┌───────────────────┐   │
│  │ .md File  │───►│ Upload to    │───►│ Parse Markdown    │   │
│  │ (on disk) │    │ Supabase     │    │ (regex engine)    │   │
│  └──────────┘    │ Storage      │    └────────┬──────────┘   │
│                  └──────────────┘             │              │
│                                              ▼              │
│                  ┌────────────────────────────────────────┐  │
│                  │         Supabase Database              │  │
│                  │                                        │  │
│                  │  ┌──────────┐  ┌────────────────────┐  │  │
│                  │  │   sops   │  │ sop_executive_     │  │  │
│                  │  │ (master) │──│ checklists         │  │  │
│                  │  └──────────┘  └────────────────────┘  │  │
│                  │       │        ┌────────────────────┐  │  │
│                  │       ├───────►│ sop_detailed_steps │  │  │
│                  │       │        └────────────────────┘  │  │
│                  │       │        ┌────────────────────┐  │  │
│                  │       └───────►│ sop_recommended_   │  │  │
│                  │                │ videos             │  │  │
│                  │                └────────────────────┘  │  │
│                  │        ┌────────────────────┐          │  │
│                  │        │  sop_sync_log      │          │  │
│                  │        │  (audit trail)     │          │  │
│                  │        └────────────────────┘          │  │
│                  └────────────────────────────────────────┘  │
│                                                              │
│  ┌──────────────────────────────────────────────────────┐    │
│  │                    CLI / Python API                   │    │
│  │  upload │ sync │ search │ list │ show │ check │ req  │    │
│  └──────────────────────────────────────────────────────┘    │
└──────────────────────────────────────────────────────────────┘
```

### Data Flow

1. **Author** writes an SOP in markdown following the [SOP Authoring Guide](../../docs/sop/SOP_AUTHORING_GUIDE.md)
2. **Upload** pushes the file to Supabase Storage bucket `apps/voicelog/sops/`
3. **Parser** extracts structured data using regex patterns:
   - Metadata (SOP number, trade, revision, etc.)
   - Executive checklists (phase → step → task mapping)
   - Detailed steps (section → step → content)
   - Recommended videos (title, URL, phase mapping)
4. **Database** stores parsed data in normalized tables for fast retrieval
5. **Agents/Apps** query via CLI or Python API

---

## Quick Start

### Prerequisites

- Supabase running locally (or remotely with URL configured)
- Migration `20260228000001_sop_library.sql` applied
- Python 3.10+ with `supabase` package installed

### 1. Install Dependencies

```bash
pip install supabase
```

### 2. Upload Your First SOP

```bash
cd /a0/usr/projects/bmad_and_agent-zero
python skills/sop_library_manager/scripts/sop_manager.py upload docs/sop/SOP_Plumbing_Sink_Replacement.md
```

### 3. Verify It Worked

```bash
python skills/sop_library_manager/scripts/sop_manager.py list
python skills/sop_library_manager/scripts/sop_manager.py show PLB-SOP-001
```

### 4. Search the Library

```bash
python skills/sop_library_manager/scripts/sop_manager.py search "plumbing"
```

---

## CLI Reference

All commands are run from the `voicelog-scaffold/` directory:

```bash
python skills/sop_library_manager/scripts/sop_manager.py <command> [args]
```

### `upload <file>`

Upload an SOP markdown file to Supabase Storage and sync to database.

```bash
python skills/sop_library_manager/scripts/sop_manager.py upload docs/sop/SOP_Plumbing_Sink_Replacement.md
```

**Output:** JSON with `sop_id`, `sop_number`, and sync counts.

---

### `sync [--all | <sop_number>]`

Re-parse and sync database from storage. Detects changes via MD5 hash.

```bash
# Sync all SOPs
python skills/sop_library_manager/scripts/sop_manager.py sync --all

# Sync specific SOP
python skills/sop_library_manager/scripts/sop_manager.py sync PLB-SOP-001
```

---

### `search <query>`

Keyword search across SOP number, trade name, task name, and description.

```bash
python skills/sop_library_manager/scripts/sop_manager.py search "electrical"
python skills/sop_library_manager/scripts/sop_manager.py search "sink"
```

**Output:** JSON array of matching SOP records.

---

### `list`

List all SOPs in the library with key metadata.

```bash
python skills/sop_library_manager/scripts/sop_manager.py list
```

**Output:** JSON array with `sop_number`, `trade_code`, `trade_name`, `task_name`, `revision`, `status`, `storage_path`.

---

### `show <sop_number>`

Retrieve full SOP details including all cached checklists, steps, and videos.

```bash
python skills/sop_library_manager/scripts/sop_manager.py show PLB-SOP-001
```

**Output:** JSON object with keys: `sop`, `executive_checklists`, `detailed_steps`, `recommended_videos`.

---

### `check <trade> <task>`

Check if a matching SOP exists. If not, generate an agent creation request.

```bash
python skills/sop_library_manager/scripts/sop_manager.py check "Plumbing" "Water Heater Replacement"
python skills/sop_library_manager/scripts/sop_manager.py check "HVAC" "Thermostat Installation"
```

**If found:** `{ "found": true, "matches": [...] }`
**If not found:** `{ "found": false, "agent_request": { "action": "create_sop", "prompt": "..." } }`

---

### `request <trade> <task>`

Force-generate an agent creation request (even if SOP exists).

```bash
python skills/sop_library_manager/scripts/sop_manager.py request "Carpentry" "Door Frame Installation"
```

---

## Python API Reference

```python
import sys
sys.path.insert(0, 'skills/sop_library_manager/scripts')
from sop_manager import SOPLibraryManager

mgr = SOPLibraryManager()
```

### `mgr.upload(file_path: str) -> dict`

Upload a local `.md` file to storage and sync to database.

```python
result = mgr.upload('docs/sop/SOP_Plumbing_Sink_Replacement.md')
# Returns: { "status": "synced", "sop_id": "...", "sop_number": "PLB-SOP-001", ... }
```

### `mgr.search(query: str) -> list`

Search SOPs by keyword.

```python
results = mgr.search('plumbing')
for sop in results:
    print(sop['sop_number'], sop['task_name'])
```

### `mgr.list_all() -> list`

List all SOPs with summary metadata.

```python
for sop in mgr.list_all():
    print(sop['sop_number'], sop['trade_name'], sop['status'])
```

### `mgr.show(sop_number: str) -> dict`

Get full SOP details with all cached data.

```python
details = mgr.show('PLB-SOP-001')
print(details['sop']['task_name'])
print(f"Checklists: {len(details['executive_checklists'])}")
print(f"Steps: {len(details['detailed_steps'])}")
print(f"Videos: {len(details['recommended_videos'])}")
```

### `mgr.check_and_request(trade: str, task: str) -> dict`

Check if SOP exists; generate creation request if not.

```python
result = mgr.check_and_request('HVAC', 'Thermostat Installation')
if result['found']:
    print(f"Found {len(result['matches'])} match(es)")
else:
    print(f"Request: {result['agent_request']['prompt']}")
```

### `mgr.sync_file(storage_path: str) -> dict`

Sync a specific file from storage to database.

```python
result = mgr.sync_file('voicelog/sops/SOP_Plumbing_Sink_Replacement.md')
```

### `mgr.sync_all() -> list`

Sync all SOP files from storage to database.

```python
results = mgr.sync_all()
for r in results:
    print(r['sop_number'], r['status'])
```

---

## Database Schema

### `sops` (Master Table)

| Column | Type | Description |
|---|---|---|
| `id` | uuid | Primary key |
| `sop_number` | text | Unique identifier (e.g., PLB-SOP-001) |
| `trade_code` | text | 3-letter trade code (PLB, ELC, HVA) |
| `trade_name` | text | Full trade name |
| `task_name` | text | Task description |
| `revision` | text | Version string |
| `effective_date` | text | Date SOP became effective |
| `description` | text | Brief description |
| `scope` | text | Scope of the procedure |
| `status` | text | active, draft, archived |
| `storage_path` | text | Path in Supabase Storage |
| `file_hash` | text | MD5 hash for change detection |
| `tags` | text[] | Searchable tags |

### `sop_executive_checklists`

| Column | Type | Description |
|---|---|---|
| `sop_id` | uuid | FK → sops.id |
| `section_type` | text | "removal" or "installation" |
| `section_number` | int | Section number in document |
| `step_number` | int | Step within section |
| `step_name` | text | Phase/group name |
| `tasks` | text | Comma-separated task descriptions |
| `is_checked` | bool | Completion status |

### `sop_detailed_steps`

| Column | Type | Description |
|---|---|---|
| `sop_id` | uuid | FK → sops.id |
| `section_type` | text | "removal" or "installation" |
| `section_number` | int | Section number |
| `step_number` | int | Step number |
| `step_title` | text | Step heading |
| `content` | text | Full step content (markdown) |

### `sop_recommended_videos`

| Column | Type | Description |
|---|---|---|
| `sop_id` | uuid | FK → sops.id |
| `title` | text | Video title |
| `url` | text | YouTube/video URL |
| `procedure_phase` | text | Which phase the video covers |
| `sort_order` | int | Display order |

### `sop_sync_log`

| Column | Type | Description |
|---|---|---|
| `sop_id` | uuid | FK → sops.id (nullable) |
| `sop_number` | text | SOP number |
| `action` | text | uploaded, synced, agent_requested, etc. |
| `details` | jsonb | Action-specific metadata |
| `created_at` | timestamptz | When the action occurred |

---

## File Structure

```
skills/sop_library_manager/
├── README.md                 # This file — human-readable overview
├── AGENT_GUIDE.md            # Step-by-step guide for Agent Zero agents
├── SKILL.md                  # Skill manifest (agentskills.io standard)
└── scripts/
    └── sop_manager.py        # Main CLI + Python API (single file)
```

### Related Project Files

| File | Path | Purpose |
|---|---|---|
| DB Migration | `supabase/migrations/20260228000001_sop_library.sql` | Creates all tables |
| Authoring Guide | `docs/sop/SOP_AUTHORING_GUIDE.md` | How to write SOPs |
| SOP Template | `docs/sop/SOP_TEMPLATE.md` | Blank SOP starter |
| Library Index | `docs/sop/SOP_INDEX.md` | Master registry |
| Plumbing SOP | `docs/sop/SOP_Plumbing_Sink_Replacement.md` | Example |
| Electrical SOP | `docs/sop/SOP_Electrical_Outlet_Replacement.md` | Example |

---

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `SUPABASE_URL` | `http://host.docker.internal:54321` | Supabase API endpoint |
| `SUPABASE_SERVICE_ROLE_KEY` | Local dev key | Service role key for admin access |

> **Note**: When running inside Docker, use `host.docker.internal` to reach the host's Supabase. When running directly on the host, use `127.0.0.1`.

---

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| `Connection refused` | Supabase not running | Run `supabase start` on host |
| `relation "sops" does not exist` | Migration not applied | Run `supabase db reset` or apply migration SQL |
| `Bucket not found` | First run | Script auto-creates bucket; check storage permissions |
| `Parse returns 0 items` | SOP format mismatch | Verify SOP follows Authoring Guide exactly |
| `Hash unchanged, skipping` | File identical to last sync | Content hasn't changed; force with `sync` command |
| `Connection refused` (Docker) | Wrong URL | Set `SUPABASE_URL=http://host.docker.internal:54321` |
