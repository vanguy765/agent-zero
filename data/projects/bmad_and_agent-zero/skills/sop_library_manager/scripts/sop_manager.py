#!/usr/bin/env python3
"""SOP Library Manager — Supabase Storage + Database Sync

Manages the SOP library lifecycle:
  - Upload .md files to Supabase Storage (apps/voicelog/sops/)
  - Parse SOP markdown into structured data
  - Sync parsed data to database tables (sops, sop_executive_checklists, sop_detailed_steps, sop_recommended_videos)
  - Detect changes via MD5 hashing
  - Search/query the library
  - Request agent creation of missing SOPs

Usage:
  python sop_manager.py upload   <file.md>              Upload SOP to storage + parse + sync DB
  python sop_manager.py sync     [--all | <sop_number>]  Re-parse and sync DB from storage
  python sop_manager.py search   <query>                 Search SOPs by keyword/trade/tag
  python sop_manager.py list                              List all SOPs in the library
  python sop_manager.py show     <sop_number>            Show SOP details with cached data
  python sop_manager.py request  <trade> <task>           Request agent to create a new SOP
  python sop_manager.py check    <trade> <task>           Check if suitable SOP exists, request if not
"""

import sys
import os
import re
import json
import hashlib
import argparse
from datetime import datetime, timezone

try:
    from supabase import create_client, Client
except ImportError:
    print("Installing supabase-py...")
    os.system("pip install supabase")
    from supabase import create_client, Client

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
SUPABASE_URL = os.environ.get("SUPABASE_URL", "http://host.docker.internal:54321")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY",
    "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZS1kZW1vIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImV4cCI6MTk4MzgxMjk5Nn0.EGIM96RAZx35lJzdJsyH-qQwv8Hdp7fsn3W0YpN81IU")
STORAGE_BUCKET = "apps"
STORAGE_PREFIX = "voicelog/sops"


def get_client() -> Client:
    return create_client(SUPABASE_URL, SUPABASE_KEY)


def md5_hash(content: str) -> str:
    return hashlib.md5(content.encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# SOP Markdown Parser
# ---------------------------------------------------------------------------
class SOPParser:
    """Parses a structured SOP .md file into components."""

    def __init__(self, content: str):
        self.content = content
        self.lines = content.split("\n")

    def parse_header_table(self) -> dict:
        """Extract the header metadata table (Field | Detail format)."""
        meta = {}
        in_table = False
        for line in self.lines:
            # Detect table start: header row with Field/Detail or SOP Number
            if "|" in line and ("Field" in line and "Detail" in line) and "---" not in line:
                in_table = True
                continue
            # Skip separator row
            if in_table and "|" in line and re.match(r"^[\|\s\-:]+$", line):
                continue
            if in_table and "|" in line:
                cells = [c.strip() for c in line.split("|") if c.strip()]
                if len(cells) >= 2:
                    # Strip bold markdown markers
                    key = re.sub(r"\*\*", "", cells[0]).strip()
                    val = re.sub(r"\*\*", "", cells[1]).strip()
                    if key:
                        meta[key] = val
            elif in_table and "|" not in line and line.strip() and line.strip() != "---":
                break
        return meta

    def parse_sections(self) -> list:
        """Split document into sections by ## headings."""
        sections = []
        current = None
        for line in self.lines:
            m = re.match(r"^## (\d+)\.\s+(.+)$", line)
            if m:
                if current:
                    sections.append(current)
                current = {
                    "number": int(m.group(1)),
                    "title": m.group(2).strip(),
                    "content": ""
                }
            elif current:
                current["content"] += line + "\n"
        if current:
            sections.append(current)
        return sections

    def parse_executive_checklist(self, section_content: str, section_number: int, phase_name: str) -> list:
        """Parse executive checklist table from a procedure section."""
        items = []
        in_table = False
        for line in section_content.split("\n"):
            if "|" in line and "Step" in line and "Step Name" in line:
                in_table = True
                continue
            if in_table and "|" in line and "---" not in line:
                cells = [c.strip() for c in line.split("|") if c.strip()]
                # Strip bold markdown (**text**) and checkbox markers from cells
                cells = [c.replace("**", "").strip() for c in cells]
                if len(cells) >= 3:
                    try:
                        step_num = int(cells[0])
                    except (ValueError, IndexError):
                        continue
                    items.append({
                        "section_number": section_number,
                        "phase_name": phase_name,
                        "step_number": step_num,
                        "step_name": cells[1].strip(),
                        "tasks": cells[2].strip() if len(cells) > 2 else "",
                        "sort_order": step_num
                    })
            elif in_table and "|" not in line and line.strip():
                break
        return items

    def parse_detailed_steps(self, section_content: str, section_number: int, phase_name: str) -> list:
        """Parse detailed step subsections (#### Step N: Name)."""
        steps = []
        current_step = None
        for line in section_content.split("\n"):
            m = re.match(r"^####\s+Step\s+(\d+):\s+(.+)$", line)
            if m:
                if current_step:
                    steps.append(current_step)
                current_step = {
                    "section_number": section_number,
                    "phase_name": phase_name,
                    "step_number": int(m.group(1)),
                    "step_name": m.group(2).strip(),
                    "content": "",
                    "sort_order": int(m.group(1))
                }
            elif current_step:
                current_step["content"] += line + "\n"
        if current_step:
            steps.append(current_step)
        # Trim trailing whitespace from content
        for s in steps:
            s["content"] = s["content"].rstrip()
        return steps

    def parse_recommended_videos(self, section_content: str, section_number: int) -> list:
        """Parse recommended videos tables."""
        videos = []
        current_phase = ""
        in_table = False
        sort_idx = 0
        for line in section_content.split("\n"):
            # Phase heading: ### Phase Name (Section N)
            pm = re.match(r"^###\s+(.+?)(?:\s+\(Section\s+\d+\))?$", line)
            if pm:
                current_phase = pm.group(1).strip()
                in_table = False
                continue
            if "|" in line and "Step" in line and "Video" in line:
                in_table = True
                continue
            if in_table and "|" in line and "---" not in line:
                cells = [c.strip() for c in line.split("|") if c.strip()]
                if len(cells) >= 4:
                    # Extract video title and URL from markdown link
                    video_cell = cells[1]
                    link_match = re.match(r"\[(.+?)\]\((.+?)\)", video_cell)
                    if link_match:
                        title = link_match.group(1)
                        url = link_match.group(2)
                    else:
                        title = video_cell
                        url = ""
                    sort_idx += 1
                    videos.append({
                        "section_number": section_number,
                        "phase_name": current_phase,
                        "step_reference": cells[0],
                        "video_title": title,
                        "video_url": url,
                        "duration": cells[2] if len(cells) > 2 else "",
                        "source": cells[3] if len(cells) > 3 else "",
                        "sort_order": sort_idx
                    })
            elif in_table and "|" not in line and line.strip() and not line.startswith(">"):
                in_table = False
        return videos

    def parse(self) -> dict:
        """Full parse of SOP document."""
        meta = self.parse_header_table()
        sections = self.parse_sections()

        checklists = []
        detailed_steps = []
        videos = []

        for sec in sections:
            title_lower = sec["title"].lower()
            # Procedure sections contain executive checklists and detailed steps
            if "procedure" in title_lower or title_lower.startswith("procedure"):
                phase_name = sec["title"].replace("Procedure \u2014 ", "").replace("Procedure — ", "")
                cl = self.parse_executive_checklist(sec["content"], sec["number"], phase_name)
                checklists.extend(cl)
                ds = self.parse_detailed_steps(sec["content"], sec["number"], phase_name)
                detailed_steps.extend(ds)
            # Recommended Videos section
            elif "recommended video" in title_lower:
                vids = self.parse_recommended_videos(sec["content"], sec["number"])
                videos.extend(vids)

        return {
            "meta": meta,
            "sections": sections,
            "checklists": checklists,
            "detailed_steps": detailed_steps,
            "videos": videos
        }


# ---------------------------------------------------------------------------
# Library Manager
# ---------------------------------------------------------------------------
class SOPLibraryManager:
    """Manages the SOP library in Supabase Storage + Database."""

    def __init__(self):
        self.client = get_client()

    def _ensure_bucket(self):
        """Ensure the storage bucket exists."""
        try:
            self.client.storage.get_bucket(STORAGE_BUCKET)
        except Exception:
            try:
                self.client.storage.create_bucket(STORAGE_BUCKET, options={"public": False})
            except Exception:
                pass  # bucket may already exist

    def upload_sop(self, filepath: str) -> dict:
        """Upload an SOP .md file to storage and sync to DB."""
        self._ensure_bucket()

        with open(filepath, "r") as f:
            content = f.read()

        filename = os.path.basename(filepath)
        storage_path = f"{STORAGE_PREFIX}/{filename}"
        file_hash = md5_hash(content)

        # Upload to storage
        try:
            self.client.storage.from_(STORAGE_BUCKET).remove([storage_path])
        except Exception:
            pass

        with open(filepath, "rb") as f:
            self.client.storage.from_(STORAGE_BUCKET).upload(
                storage_path,
                f,
                file_options={"content-type": "text/markdown", "upsert": "true"}
            )

        # Parse and sync
        result = self._sync_from_content(content, storage_path, file_hash)
        self._log_action(result.get("sop_id"), result.get("sop_number"), "uploaded",
                         {"file": filename, "hash": file_hash})
        return result

    def _sync_from_content(self, content: str, storage_path: str, file_hash: str) -> dict:
        """Parse content and upsert into database."""
        parser = SOPParser(content)
        parsed = parser.parse()
        meta = parsed["meta"]

        sop_number = meta.get("SOP Number", "UNKNOWN")
        trade_parts = meta.get("Trade", "General").split(" — ") if " — " in meta.get("Trade", "") else [meta.get("Trade", "General")]
        trade_name = trade_parts[0].strip() if trade_parts else "General"

        # Derive trade code from SOP number
        trade_code = sop_number.split("-")[0] if "-" in sop_number else "GEN"

        task_name = meta.get("Task", meta.get("Procedure", "Unknown Task"))
        revision = meta.get("Revision", "1.0")
        duration = meta.get("Estimated Duration", meta.get("Duration", ""))

        # Build tags from trade and task
        tags = [trade_code.lower(), trade_name.lower()]
        for word in task_name.lower().split():
            if len(word) > 3:
                tags.append(word)

        # Upsert master SOP record
        sop_data = {
            "sop_number": sop_number,
            "trade_code": trade_code,
            "trade_name": trade_name,
            "task_name": task_name,
            "revision": revision,
            "status": "active",
            "estimated_duration": duration,
            "storage_path": storage_path,
            "file_hash": file_hash,
            "description": f"{trade_name} — {task_name} (Rev {revision})",
            "tags": tags
        }

        # Check if exists
        existing = self.client.table("sops").select("id, file_hash").eq("sop_number", sop_number).execute()

        if existing.data:
            sop_id = existing.data[0]["id"]
            old_hash = existing.data[0].get("file_hash")
            if old_hash == file_hash:
                return {"sop_id": sop_id, "sop_number": sop_number, "status": "unchanged",
                        "message": f"{sop_number} unchanged (hash match)"}
            # Update
            self.client.table("sops").update(sop_data).eq("id", sop_id).execute()
        else:
            result = self.client.table("sops").insert(sop_data).execute()
            sop_id = result.data[0]["id"]

        # Clear old cached data
        self.client.table("sop_executive_checklists").delete().eq("sop_id", sop_id).execute()
        self.client.table("sop_detailed_steps").delete().eq("sop_id", sop_id).execute()
        self.client.table("sop_recommended_videos").delete().eq("sop_id", sop_id).execute()

        # Insert checklists
        for cl in parsed["checklists"]:
            cl["sop_id"] = sop_id
            self.client.table("sop_executive_checklists").insert(cl).execute()

        # Insert detailed steps
        for ds in parsed["detailed_steps"]:
            ds["sop_id"] = sop_id
            self.client.table("sop_detailed_steps").insert(ds).execute()

        # Insert videos
        for vid in parsed["videos"]:
            vid["sop_id"] = sop_id
            self.client.table("sop_recommended_videos").insert(vid).execute()

        return {
            "sop_id": sop_id,
            "sop_number": sop_number,
            "status": "synced",
            "checklists": len(parsed["checklists"]),
            "detailed_steps": len(parsed["detailed_steps"]),
            "videos": len(parsed["videos"]),
            "message": f"{sop_number} synced: {len(parsed['checklists'])} checklists, {len(parsed['detailed_steps'])} steps, {len(parsed['videos'])} videos"
        }

    def sync_all(self) -> list:
        """Re-sync all SOPs from storage."""
        results = []
        sops = self.client.table("sops").select("sop_number, storage_path").execute()
        for sop in sops.data:
            try:
                data = self.client.storage.from_(STORAGE_BUCKET).download(sop["storage_path"])
                content = data.decode("utf-8")
                file_hash = md5_hash(content)
                result = self._sync_from_content(content, sop["storage_path"], file_hash)
                results.append(result)
            except Exception as e:
                results.append({"sop_number": sop["sop_number"], "status": "error", "message": str(e)})
        return results

    def sync_one(self, sop_number: str) -> dict:
        """Re-sync a single SOP from storage."""
        sop = self.client.table("sops").select("storage_path").eq("sop_number", sop_number).execute()
        if not sop.data:
            return {"status": "error", "message": f"SOP {sop_number} not found in database"}
        try:
            data = self.client.storage.from_(STORAGE_BUCKET).download(sop.data[0]["storage_path"])
            content = data.decode("utf-8")
            file_hash = md5_hash(content)
            return self._sync_from_content(content, sop.data[0]["storage_path"], file_hash)
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def search(self, query: str) -> list:
        """Search SOPs by keyword in sop_number, trade, task, description, tags."""
        q = query.lower()
        results = self.client.table("sops").select("*").or_(
            f"sop_number.ilike.%{q}%,trade_name.ilike.%{q}%,task_name.ilike.%{q}%,description.ilike.%{q}%"
        ).execute()
        return results.data

    def list_all(self) -> list:
        """List all SOPs."""
        results = self.client.table("sops").select(
            "sop_number, trade_code, trade_name, task_name, revision, status, storage_path"
        ).order("sop_number").execute()
        return results.data

    def show(self, sop_number: str) -> dict:
        """Show full SOP details with cached data."""
        sop = self.client.table("sops").select("*").eq("sop_number", sop_number).execute()
        if not sop.data:
            return {"error": f"SOP {sop_number} not found"}
        sop_id = sop.data[0]["id"]
        checklists = self.client.table("sop_executive_checklists").select("*").eq("sop_id", sop_id).order("section_number,step_number").execute()
        steps = self.client.table("sop_detailed_steps").select("*").eq("sop_id", sop_id).order("section_number,step_number").execute()
        videos = self.client.table("sop_recommended_videos").select("*").eq("sop_id", sop_id).order("sort_order").execute()
        return {
            "sop": sop.data[0],
            "executive_checklists": checklists.data,
            "detailed_steps": steps.data,
            "recommended_videos": videos.data
        }

    def check_and_request(self, trade: str, task: str) -> dict:
        """Check if a suitable SOP exists. If not, return a request payload for agent creation."""
        results = self.search(f"{trade} {task}")
        if results:
            return {
                "found": True,
                "matches": results,
                "message": f"Found {len(results)} matching SOP(s)"
            }
        # No match — generate agent request
        trade_code = trade[:3].upper()
        # Find next number
        existing = self.client.table("sops").select("sop_number").ilike("sop_number", f"{trade_code}%").execute()
        max_num = 0
        for s in existing.data:
            m = re.search(r"(\d+)$", s["sop_number"])
            if m:
                max_num = max(max_num, int(m.group(1)))
        next_number = f"{trade_code}-SOP-{max_num + 1:03d}"

        request_payload = {
            "found": False,
            "message": f"No SOP found for '{trade} — {task}'. Agent creation requested.",
            "agent_request": {
                "action": "create_sop",
                "sop_number": next_number,
                "trade_code": trade_code,
                "trade_name": trade,
                "task_name": task,
                "prompt": (
                    f"Create a complete Standard Operating Procedure for {trade} — {task}. "
                    f"Assign SOP number {next_number}. Follow the SOP Authoring Guide (SOP-META-001) exactly. "
                    f"Include all mandatory sections: Purpose, Scope, References & Codes, Personnel, Safety, "
                    f"Tools & Equipment, Pre-Work Assessment, Procedure phases with Executive Checklists and "
                    f"Detailed Steps, Recommended Videos, Testing & Commissioning, Cleanup, Troubleshooting, "
                    f"Quality Standards, and Revision History. "
                    f"Save the file as {next_number.replace('-', '_')}_{task.replace(' ', '_')}.md"
                )
            }
        }

        # Log the request
        self._log_action(None, next_number, "agent_requested",
                         {"trade": trade, "task": task})
        return request_payload

    def _log_action(self, sop_id, sop_number, action, details=None):
        """Log a sync action."""
        try:
            self.client.table("sop_sync_log").insert({
                "sop_id": sop_id,
                "sop_number": sop_number,
                "action": action,
                "details": details or {}
            }).execute()
        except Exception:
            pass  # non-critical


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(description="SOP Library Manager")
    sub = parser.add_subparsers(dest="command")

    # upload
    p_upload = sub.add_parser("upload", help="Upload SOP .md file to storage and sync DB")
    p_upload.add_argument("file", help="Path to .md file")

    # sync
    p_sync = sub.add_parser("sync", help="Re-sync DB from storage")
    p_sync.add_argument("--all", action="store_true", help="Sync all SOPs")
    p_sync.add_argument("sop_number", nargs="?", help="Specific SOP number to sync")

    # search
    p_search = sub.add_parser("search", help="Search SOPs")
    p_search.add_argument("query", help="Search query")

    # list
    sub.add_parser("list", help="List all SOPs")

    # show
    p_show = sub.add_parser("show", help="Show SOP details")
    p_show.add_argument("sop_number", help="SOP number")

    # request
    p_req = sub.add_parser("request", help="Request agent to create SOP")
    p_req.add_argument("trade", help="Trade name")
    p_req.add_argument("task", help="Task name")

    # check
    p_check = sub.add_parser("check", help="Check if SOP exists, request if not")
    p_check.add_argument("trade", help="Trade name")
    p_check.add_argument("task", help="Task name")

    args = parser.parse_args()
    mgr = SOPLibraryManager()

    if args.command == "upload":
        result = mgr.upload_sop(args.file)
        print(json.dumps(result, indent=2, default=str))

    elif args.command == "sync":
        if args.all:
            results = mgr.sync_all()
            for r in results:
                print(json.dumps(r, indent=2, default=str))
        elif args.sop_number:
            result = mgr.sync_one(args.sop_number)
            print(json.dumps(result, indent=2, default=str))
        else:
            print("Specify --all or a specific SOP number")

    elif args.command == "search":
        results = mgr.search(args.query)
        for r in results:
            print(f"  {r['sop_number']:15s} {r['trade_name']:15s} {r['task_name']:30s} [{r['status']}]")
        if not results:
            print("  No SOPs found.")

    elif args.command == "list":
        results = mgr.list_all()
        print(f"{'SOP Number':15s} {'Trade':10s} {'Task':30s} {'Rev':5s} {'Status':10s}")
        print("-" * 75)
        for r in results:
            print(f"{r['sop_number']:15s} {r['trade_code']:10s} {r['task_name']:30s} {r['revision']:5s} {r['status']:10s}")
        if not results:
            print("  Library is empty.")

    elif args.command == "show":
        result = mgr.show(args.sop_number)
        print(json.dumps(result, indent=2, default=str))

    elif args.command == "request":
        result = mgr.check_and_request(args.trade, args.task)
        print(json.dumps(result, indent=2, default=str))

    elif args.command == "check":
        result = mgr.check_and_request(args.trade, args.task)
        print(json.dumps(result, indent=2, default=str))

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
