# SOP Library Manager — Agent Guide

> **For Agent Zero agents** — How to use this skill to find, retrieve, create, and manage SOPs.

---

## Quick Reference

| Action | Command | When to Use |
|---|---|---|
| **Find an SOP** | `search "<keyword>"` | User asks about a procedure |
| **List all SOPs** | `list` | User wants to see available procedures |
| **Get full SOP** | `show <SOP_NUMBER>` | User needs detailed procedure steps |
| **Check + auto-request** | `check "<trade>" "<task>"` | Before starting work — verify SOP exists |
| **Upload new SOP** | `upload <file_path>` | After creating a new SOP document |
| **Re-sync database** | `sync --all` | After manual edits to SOP files |

---

## Setup

### Load the Skill

Before using this skill, load it to get full instructions:

```json
{
    "tool_name": "skills_tool:load",
    "tool_args": {
        "skill_name": "sop_library_manager"
    }
}
```

### Working Directory

All commands run from:
```
/a0/usr/projects/bmad_and_agent-zero
```

### Script Location

```
skills/sop_library_manager/scripts/sop_manager.py
```

---

## Workflow 1: Search for an SOP

**Scenario**: User asks "Do we have a procedure for replacing a kitchen sink?"

### Step 1 — Search the library

```json
{
    "tool_name": "code_execution_tool",
    "tool_args": {
        "runtime": "terminal",
        "code": "cd /a0/usr/projects/bmad_and_agent-zero && python skills/sop_library_manager/scripts/sop_manager.py search \"sink\""
    }
}
```

**Expected output**: JSON array of matching SOPs.

### Step 2 — Show full details (if found)

```json
{
    "tool_name": "code_execution_tool",
    "tool_args": {
        "runtime": "terminal",
        "code": "cd /a0/usr/projects/bmad_and_agent-zero && python skills/sop_library_manager/scripts/sop_manager.py show PLB-SOP-001"
    }
}
```

**Expected output**: Full SOP record with executive checklists, detailed steps, and recommended videos.

---

## Workflow 2: Check Before Work Starts

**Scenario**: A work order requires HVAC thermostat installation. Check if an SOP exists.

### Step 1 — Check and request

```json
{
    "tool_name": "code_execution_tool",
    "tool_args": {
        "runtime": "terminal",
        "code": "cd /a0/usr/projects/bmad_and_agent-zero && python skills/sop_library_manager/scripts/sop_manager.py check \"HVAC\" \"Thermostat Installation\""
    }
}
```

### Step 2 — Interpret the result

**If `found: true`**:
```json
{
    "found": true,
    "matches": [ { "sop_number": "HVA-SOP-001", ... } ],
    "message": "Found 1 matching SOP(s)"
}
```
→ Use `show HVA-SOP-001` to get the full procedure.

**If `found: false`**:
```json
{
    "found": false,
    "message": "No SOP found for 'HVAC — Thermostat Installation'. Agent creation requested.",
    "agent_request": {
        "action": "create_sop",
        "sop_number": "HVA-SOP-001",
        "trade_code": "HVA",
        "trade_name": "HVAC",
        "task_name": "Thermostat Installation",
        "prompt": "Create a complete Standard Operating Procedure for HVAC — Thermostat Installation..."
    }
}
```
→ Proceed to **Workflow 3** to create the missing SOP.

---

## Workflow 3: Create a Missing SOP

**Scenario**: `check` returned `found: false` with an `agent_request` payload.

### Step 1 — Read the authoring guide

The SOP must follow the standardized format. The authoring guide is at:
```
docs/sop/SOP_AUTHORING_GUIDE.md
```

A blank template is at:
```
docs/sop/SOP_TEMPLATE.md
```

### Step 2 — Create the SOP document

Use the prompt from the `agent_request` payload. Either:

**Option A — Delegate to a subordinate agent:**

```json
{
    "tool_name": "call_subordinate",
    "tool_args": {
        "profile": "developer",
        "message": "You are an SOP Author specializing in trade procedures.\n\nCreate a complete Standard Operating Procedure for HVAC — Thermostat Installation.\nAssign SOP number HVA-SOP-001.\n\nFollow the SOP Authoring Guide exactly (read it at docs/sop/SOP_AUTHORING_GUIDE.md).\nUse the template at docs/sop/SOP_TEMPLATE.md as your starting point.\n\nInclude ALL mandatory sections: Purpose, Scope, References & Codes, Personnel, Safety, Tools & Equipment, Pre-Work Assessment, Procedure phases with Executive Checklists and Detailed Steps, Recommended Videos, Testing & Commissioning, Cleanup, Troubleshooting, Quality Standards, and Revision History.\n\nSave the file as: docs/general/HVA_SOP_001_Thermostat_Installation.md\n\nWorking directory: /a0/usr/projects/bmad_and_agent-zero",
        "reset": "true"
    }
}
```

**Option B — Write it directly** using `code_execution_tool` with Python.

### Step 3 — Upload to the library

```json
{
    "tool_name": "code_execution_tool",
    "tool_args": {
        "runtime": "terminal",
        "code": "cd /a0/usr/projects/bmad_and_agent-zero && python skills/sop_library_manager/scripts/sop_manager.py upload docs/general/HVA_SOP_001_Thermostat_Installation.md"
    }
}
```

### Step 4 — Verify

```json
{
    "tool_name": "code_execution_tool",
    "tool_args": {
        "runtime": "terminal",
        "code": "cd /a0/usr/projects/bmad_and_agent-zero && python skills/sop_library_manager/scripts/sop_manager.py show HVA-SOP-001"
    }
}
```

### Step 5 — Update the index

Add the new SOP to `docs/sop/SOP_INDEX.md` in the appropriate trade section.

---

## Workflow 4: List All Available SOPs

**Scenario**: User asks "What procedures do we have?"

```json
{
    "tool_name": "code_execution_tool",
    "tool_args": {
        "runtime": "terminal",
        "code": "cd /a0/usr/projects/bmad_and_agent-zero && python skills/sop_library_manager/scripts/sop_manager.py list"
    }
}
```

---

## Workflow 5: Re-sync After Edits

**Scenario**: An SOP markdown file was edited manually. Sync the database.

```json
{
    "tool_name": "code_execution_tool",
    "tool_args": {
        "runtime": "terminal",
        "code": "cd /a0/usr/projects/bmad_and_agent-zero && python skills/sop_library_manager/scripts/sop_manager.py sync --all"
    }
}
```

Or sync a specific SOP:

```json
{
    "tool_name": "code_execution_tool",
    "tool_args": {
        "runtime": "terminal",
        "code": "cd /a0/usr/projects/bmad_and_agent-zero && python skills/sop_library_manager/scripts/sop_manager.py sync PLB-SOP-001"
    }
}
```

---

## Python API (Alternative to CLI)

For more complex operations, use the Python API directly:

```json
{
    "tool_name": "code_execution_tool",
    "tool_args": {
        "runtime": "python",
        "code": "import sys\nsys.path.insert(0, '/a0/usr/projects/bmad_and_agent-zero/skills/sop_library_manager/scripts')\nfrom sop_manager import SOPLibraryManager\n\nmgr = SOPLibraryManager()\n\n# Search\nresults = mgr.search('plumbing')\nfor r in results:\n    print(r['sop_number'], r['task_name'])\n\n# Show full details\ndetails = mgr.show('PLB-SOP-001')\nprint(f\"Checklists: {len(details['executive_checklists'])}\")"
    }
}
```

### Available Methods

| Method | Args | Returns | Description |
|---|---|---|---|
| `mgr.search(query)` | `str` | `list[dict]` | Keyword search across all SOP fields |
| `mgr.list_all()` | — | `list[dict]` | All SOPs with summary metadata |
| `mgr.show(sop_number)` | `str` | `dict` | Full SOP + checklists + steps + videos |
| `mgr.check_and_request(trade, task)` | `str, str` | `dict` | Check existence; generate creation request if missing |
| `mgr.upload(file_path)` | `str` | `dict` | Upload .md to storage + sync to DB |
| `mgr.sync_file(storage_path)` | `str` | `dict` | Re-sync one file from storage |
| `mgr.sync_all()` | — | `list[dict]` | Re-sync all files from storage |

---

## SOP Document Format

All SOPs must follow the **SOP Authoring Guide** (`SOP-META-001`). Key requirements:

### Mandatory 15-Section Structure

| # | Section | Content |
|---|---|---|
| 1 | Purpose | Why this SOP exists |
| 2 | Scope | What's covered and what's not |
| 3 | References & Codes | Applicable standards (NEC, IPC, UPC, etc.) |
| 4 | Personnel & Qualifications | Who can perform this work |
| 5 | Safety Requirements | PPE, lockout/tagout, hazards |
| 6 | Tools & Equipment | Required tools and materials |
| 7 | Pre-Work Assessment | Site evaluation checklist |
| 8 | Procedure Phase 1 | Removal/Demolition (Executive Checklist + Detailed Steps) |
| 9 | Procedure Phase 2 | Installation/Assembly (Executive Checklist + Detailed Steps) |
| 10 | Recommended Videos | YouTube tutorials mapped to procedure phases |
| 11 | Testing & Commissioning | Verification procedures |
| 12 | Cleanup & Restoration | Site cleanup requirements |
| 13 | Troubleshooting | Common issues and solutions |
| 14 | Quality Standards | Acceptance criteria |
| 15 | Revision History | Document change log |

### Three-Tier Procedure Hierarchy

Each procedure phase (Sections 8 & 9) uses three tiers:

1. **Executive Checklist** — 5 high-level phases with checkboxes for quick tracking
2. **Detailed Steps** — Numbered sub-steps under each phase heading
3. **Step-by-step instructions** — Granular procedural content within each step

### Naming Convention

```
{TRADE_CODE}-SOP-{NNN}
```

| Trade | Code | Example |
|---|---|---|
| Plumbing | PLB | PLB-SOP-001 |
| Electrical | ELC | ELC-SOP-001 |
| HVAC | HVA | HVA-SOP-001 |
| Carpentry | CRP | CRP-SOP-001 |
| Painting | PNT | PNT-SOP-001 |
| Drywall | DRY | DRY-SOP-001 |
| Roofing | ROF | ROF-SOP-001 |
| Flooring | FLR | FLR-SOP-001 |

---

## Current Library Contents

| SOP Number | Trade | Task | Status |
|---|---|---|---|
| PLB-SOP-001 | Plumbing | Remove & Replace Sink (Kitchen / Bathroom / Utility) | ✅ Active |
| ELC-SOP-001 | Electrical | Remove & Replace Electrical Outlet (120V/240V) | ✅ Active |

---

## Related Files

| File | Path | Purpose |
|---|---|---|
| Authoring Guide | `docs/sop/SOP_AUTHORING_GUIDE.md` | How to write SOPs |
| Blank Template | `docs/sop/SOP_TEMPLATE.md` | Starting point for new SOPs |
| Library Index | `docs/sop/SOP_INDEX.md` | Master registry of all SOPs |
| DB Migration | `supabase/migrations/20260228000001_sop_library.sql` | Database schema |
| Plumbing SOP | `docs/sop/SOP_Plumbing_Sink_Replacement.md` | Example SOP |
| Electrical SOP | `docs/sop/SOP_Electrical_Outlet_Replacement.md` | Example SOP |

---

## Troubleshooting

| Problem | Solution |
|---|---|
| `Connection refused` | Supabase not running. User must start it on host: `supabase start` |
| `relation "sops" does not exist` | Migration not applied. Run: `supabase db reset` |
| `Parse returns 0 items` | SOP doesn't follow the Authoring Guide format. Check section headings. |
| `Hash unchanged, skipping` | File hasn't changed since last sync. Edit the file or use `sync` to force. |
| Search returns nothing | Try broader keywords. Search checks: sop_number, trade_name, task_name, description. |

---

## Environment Notes

- **Inside Docker container**: Supabase URL = `http://host.docker.internal:54321`
- **On host machine**: Supabase URL = `http://127.0.0.1:54321`
- The script auto-detects via `SUPABASE_URL` environment variable
- Default service role key is the standard Supabase local dev key
