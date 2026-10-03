"""PARA MCP Server — enforces PARA rules programmatically.

Repo root is resolved from this file's location: Path(__file__).parent.parent.
All file operations are relative to that root; no absolute paths from config.
"""
import re
import shutil
from datetime import date, datetime
from pathlib import Path
from typing import Optional

from mcp.server.mcpserver import MCPServer

REPO_ROOT = Path(__file__).parent.parent

VALID_STATUSES = {"Active", "On Hold", "Waiting", "Complete"}
VALID_BUCKETS = {"Projects", "Areas", "Resources", "Archives"}
PROJECT_NAME_RE = re.compile(r"^\d{4}-\d{2}-.+$")
STALE_DAYS = 14

mcp = MCPServer("PARA")


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _sanitize_name(name: str) -> str:
    """Replace whitespace/underscores with hyphens and strip leading/trailing hyphens."""
    return re.sub(r"[\s_]+", "-", name).strip("-")


def _ensure_dated_name(name: str) -> str:
    """Prefix name with YYYY-MM- if it doesn't already match the project naming convention."""
    name = _sanitize_name(name)
    if not PROJECT_NAME_RE.match(name):
        name = f"{date.today().strftime('%Y-%m')}-{name}"
    return name


def _parse_index(index_path: Path) -> dict:
    """Extract Status, Deadline, Goal, and Next Action fields from an index.md."""
    text = index_path.read_text()
    result = {}
    for field in ("Status", "Deadline", "Goal", "Next Action"):
        m = re.search(rf"\*\*{field}:\*\*\s*(.+)", text)
        result[field.lower().replace(" ", "_")] = m.group(1).strip() if m else ""
    return result


def _write_index(index_path: Path, name: str, status: str, deadline: str,
                 goal: str = "TBD", next_action: str = "TBD") -> None:
    """Write a standard index.md with the four required PARA fields."""
    index_path.write_text(
        f"# {name}\n\n"
        f"**Status:** {status}\n"
        f"**Deadline:** {deadline}\n"
        f"**Goal:** {goal}\n"
        f"**Next Action:** {next_action}\n"
    )


def _validate_url(url: str) -> bool:
    """Return True only for http:// or https:// URLs."""
    return url.startswith(("http://", "https://"))


def _parse_resource(path: Path) -> dict:
    """Extract links from the ## Links section of a resource .md file."""
    text = path.read_text()
    links = []
    m = re.search(r"## Links\n\n((?:- \[.*?\]\(.*?\)\n)+)", text)
    if m:
        for entry in re.finditer(r"- \[([^\]]*)\]\(([^)]+)\)", m.group(1)):
            label, url = entry.group(1), entry.group(2)
            links.append({"label": label if label else url, "url": url})
    return {"links": links}


def _append_links_section(file_path: Path, url: str, label: str) -> None:
    """Append a link entry to the ## Links section of a file, creating the section if absent."""
    display = label if label else url
    entry = f"- [{display}]({url})"
    text = file_path.read_text().rstrip("\n")
    if "## Links" in text:
        text = text + f"\n{entry}\n"
    else:
        text = text + f"\n\n## Links\n\n{entry}\n"
    file_path.write_text(text)


def _resolve_resource_file(resource_path: str, r: Path) -> Optional[Path]:
    """Return the .md file for a resource path (folder → index.md, bare name → name.md)."""
    p = r / resource_path
    if p.is_dir():
        f = p / "index.md"
        return f if f.exists() else None
    if p.suffix != ".md":
        p = p.with_suffix(".md")
    return p if p.exists() else None


def _format_deadline_relative(deadline_str: str, today: Optional[date] = None) -> str:
    """Return a human-readable relative string for a deadline date (e.g. '2 weeks', 'overdue 3 days')."""
    if not deadline_str:
        return ""
    try:
        deadline = date.fromisoformat(deadline_str)
    except ValueError:
        return ""
    ref = today if today is not None else date.today()
    delta = (deadline - ref).days
    if delta == 0:
        return "today"

    def _relative(n: int) -> str:
        if n == 1:
            return "1 day"
        if n < 7:
            return f"{n} days"
        if n < 56:
            weeks = n // 7
            return f"{weeks} week" if weeks == 1 else f"{weeks} weeks"
        months = n // 30
        return f"{months} month" if months == 1 else f"{months} months"

    if delta > 0:
        return _relative(delta)
    return f"overdue {_relative(-delta)}"


# ---------------------------------------------------------------------------
# Business logic (root=None → uses REPO_ROOT; pass root for tests)
# ---------------------------------------------------------------------------

def create_project(domain: str, name: str, deadline: str,
                   goal: str = "TBD", next_action: str = "TBD",
                   root: Optional[Path] = None) -> dict:
    """Create a new project folder with index.md under <domain>/Projects/."""
    r = root if root is not None else REPO_ROOT
    name = _ensure_dated_name(name)
    project_dir = r / domain / "Projects" / name
    if project_dir.exists():
        return {"ok": False, "error": f"Project '{name}' already exists in {domain}/Projects"}
    project_dir.mkdir(parents=True)
    _write_index(project_dir / "index.md", name, "Active", deadline, goal, next_action)
    return {"ok": True, "path": str(project_dir.relative_to(r))}


def list_projects(domain: Optional[str] = None, root: Optional[Path] = None) -> list:
    """Return all projects across domains (or one domain), including days since last modified."""
    r = root if root is not None else REPO_ROOT
    results = []
    if domain:
        candidates = [r / domain]
    else:
        candidates = [d for d in r.iterdir() if d.is_dir() and not d.name.startswith((".", "_"))]
    for d in candidates:
        projects_dir = d / "Projects"
        if not projects_dir.exists():
            continue
        for proj in projects_dir.iterdir():
            if not proj.is_dir():
                continue
            index = proj / "index.md"
            if not index.exists():
                continue
            data = _parse_index(index)
            mtime = datetime.fromtimestamp(index.stat().st_mtime)
            days_since = (datetime.now() - mtime).days
            results.append({
                "path": str(proj.relative_to(r)),
                "domain": d.name,
                "name": proj.name,
                "status": data["status"],
                "deadline": data["deadline"],
                "deadline_relative": _format_deadline_relative(data["deadline"]),
                "days_since_modified": days_since,
            })
    return results


def weekly_review(root: Optional[Path] = None) -> list:
    """Return projects stale for STALE_DAYS or more. Never moves files."""
    return [p for p in list_projects(root=root) if p["days_since_modified"] >= STALE_DAYS]


def archive_project(path: str, root: Optional[Path] = None) -> dict:
    """Move a project from <domain>/Projects/<name> to <domain>/Archives/<name>."""
    r = root if root is not None else REPO_ROOT
    src = r / path
    if not src.exists():
        return {"ok": False, "error": f"Path '{path}' not found"}
    parts = Path(path).parts
    if len(parts) < 3 or parts[1] != "Projects":
        return {"ok": False, "error": "Path must be under <domain>/Projects/<name>"}
    domain, name = parts[0], parts[2]
    dest_dir = r / domain / "Archives"
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / name
    if dest.exists():
        return {"ok": False, "error": f"'{name}' already exists in {domain}/Archives"}
    shutil.move(str(src), str(dest))
    return {"ok": True, "archived_to": f"{domain}/Archives/{name}"}


def update_status(path: str, status: str, root: Optional[Path] = None) -> dict:
    """Rewrite the Status field in a project's index.md; rejects invalid values."""
    if status not in VALID_STATUSES:
        return {
            "ok": False,
            "error": f"Invalid status '{status}'. Must be one of: {', '.join(sorted(VALID_STATUSES))}",
        }
    r = root if root is not None else REPO_ROOT
    index = r / path / "index.md"
    if not index.exists():
        return {"ok": False, "error": f"index.md not found at '{path}'"}
    text = index.read_text()
    if "**Status:**" not in text:
        return {"ok": False, "error": "No Status field found in index.md"}
    text = re.sub(r"\*\*Status:\*\*\s*.+", f"**Status:** {status}", text)
    index.write_text(text)
    return {"ok": True, "path": path, "status": status}


def _update_index_files(proj_dir: Path) -> None:
    """Rebuild the ## Files section in index.md from current folder contents."""
    index = proj_dir / "index.md"
    files = sorted(
        f for f in proj_dir.iterdir()
        if f.is_file() and f.suffix == ".md" and f.name != "index.md"
    )
    text = re.sub(r"\n## Files\n[\s\S]*$", "", index.read_text()).rstrip("\n")
    if files:
        file_list = "\n".join(f"- [{f.stem}]({f.name})" for f in files)
        text = text + f"\n\n## Files\n\n{file_list}\n"
    else:
        text = text + "\n"
    index.write_text(text)


def add_file_to_project(project_path: str, title: str, content: str,
                        root: Optional[Path] = None) -> dict:
    """Add a new .md file to a project folder and rebuild the index.md ## Files list."""
    r = root if root is not None else REPO_ROOT
    proj_dir = r / project_path
    if not (proj_dir / "index.md").exists():
        return {"ok": False, "error": f"Project not found at '{project_path}'"}
    title = _sanitize_name(title)
    file_path = proj_dir / f"{title}.md"
    if file_path.exists():
        return {"ok": False, "error": f"'{title}.md' already exists in {project_path}"}
    file_path.write_text(content)
    _update_index_files(proj_dir)
    return {"ok": True, "path": str(file_path.relative_to(r))}


def capture(domain: str, bucket: str, title: str, content: str,
            url: Optional[str] = None, url_label: Optional[str] = None,
            root: Optional[Path] = None) -> dict:
    """File a new item into any PARA bucket; Projects get a folder+index.md, others get a .md file."""
    if bucket not in VALID_BUCKETS:
        return {
            "ok": False,
            "error": f"Invalid bucket '{bucket}'. Must be one of: {', '.join(sorted(VALID_BUCKETS))}",
        }
    if url is not None and not _validate_url(url):
        return {"ok": False, "error": f"Invalid URL '{url}'. Must start with http:// or https://"}
    r = root if root is not None else REPO_ROOT
    title = _sanitize_name(title)
    if bucket == "Projects":
        title = _ensure_dated_name(title)
        dest = r / domain / bucket / title
        dest.mkdir(parents=True, exist_ok=True)
        file_path = dest / "index.md"
    else:
        dest_dir = r / domain / bucket
        dest_dir.mkdir(parents=True, exist_ok=True)
        file_path = dest_dir / f"{title}.md"
    if file_path.exists():
        return {"ok": False, "error": f"'{file_path.relative_to(r)}' already exists"}
    file_path.write_text(content)
    if url is not None:
        _append_links_section(file_path, url, url_label or "")
    return {"ok": True, "path": str(file_path.relative_to(r))}


def add_link_to_resource(resource_path: str, url: str, label: str = "",
                         root: Optional[Path] = None) -> dict:
    """Append a URL to the ## Links section of an existing resource file or folder."""
    if not _validate_url(url):
        return {"ok": False, "error": f"Invalid URL '{url}'. Must start with http:// or https://"}
    r = root if root is not None else REPO_ROOT
    file_path = _resolve_resource_file(resource_path, r)
    if file_path is None:
        return {"ok": False, "error": f"Resource not found at '{resource_path}'"}
    existing = _parse_resource(file_path)
    if any(link["url"] == url for link in existing["links"]):
        return {"ok": False, "error": f"URL '{url}' already exists in this resource"}
    _append_links_section(file_path, url, label)
    return {"ok": True, "path": str(file_path.relative_to(r))}


def list_resources(domain: Optional[str] = None, with_links: bool = False,
                   root: Optional[Path] = None) -> list:
    """List all resources across domains (or one domain), optionally including their links."""
    r = root if root is not None else REPO_ROOT
    results = []
    if domain:
        candidates = [r / domain]
    else:
        candidates = [d for d in r.iterdir() if d.is_dir() and not d.name.startswith((".", "_"))]
    for d in candidates:
        resources_dir = d / "Resources"
        if not resources_dir.exists():
            continue
        for item in sorted(resources_dir.iterdir()):
            if item.is_file() and item.suffix == ".md":
                entry = {"path": str(item.relative_to(r)), "domain": d.name, "name": item.stem}
                if with_links:
                    entry["links"] = _parse_resource(item)["links"]
                results.append(entry)
            elif item.is_dir():
                index = item / "index.md"
                if index.exists():
                    entry = {"path": str(item.relative_to(r)), "domain": d.name, "name": item.name}
                    if with_links:
                        entry["links"] = _parse_resource(index)["links"]
                    results.append(entry)
    return results


# ---------------------------------------------------------------------------
# Tags (issue #24)
# ---------------------------------------------------------------------------

TAG_RE = re.compile(r"#[a-zA-Z][a-zA-Z0-9_-]*")


def _parse_tags(text: str) -> set:
    """Extract all #tags from **Tags:** frontmatter line and inline content."""
    return set(TAG_RE.findall(text))


def _get_frontmatter_tags(text: str) -> list:
    """Return tags from the **Tags:** field only (for structured editing)."""
    m = re.search(r"\*\*Tags:\*\*\s*(.*)", text)
    if not m:
        return []
    return TAG_RE.findall(m.group(1))


def _set_frontmatter_tags(text: str, tags: list) -> str:
    """Rewrite or add the **Tags:** line with the given tag list."""
    tags_line = f"**Tags:** {' '.join(tags)}" if tags else "**Tags:**"
    if re.search(r"\*\*Tags:\*\*", text):
        return re.sub(r"\*\*Tags:\*\*.*", tags_line, text)
    return text.rstrip("\n") + f"\n{tags_line}\n"


def tag_item(path: str, tag: str, root: Optional[Path] = None) -> dict:
    """Add a #tag to an item's **Tags:** frontmatter field."""
    r = root if root is not None else REPO_ROOT
    file_path = r / path
    if not file_path.exists():
        return {"ok": False, "error": f"File not found: '{path}'"}
    if not TAG_RE.match(tag):
        return {"ok": False, "error": f"Invalid tag '{tag}'. Must match #word pattern."}
    text = file_path.read_text()
    existing = _get_frontmatter_tags(text)
    if tag in existing:
        return {"ok": False, "error": f"Tag '{tag}' already present in '{path}'"}
    new_tags = existing + [tag]
    file_path.write_text(_set_frontmatter_tags(text, new_tags))
    return {"ok": True, "path": path, "tags": new_tags}


def untag_item(path: str, tag: str, root: Optional[Path] = None) -> dict:
    """Remove a #tag from an item's **Tags:** frontmatter field."""
    r = root if root is not None else REPO_ROOT
    file_path = r / path
    if not file_path.exists():
        return {"ok": False, "error": f"File not found: '{path}'"}
    text = file_path.read_text()
    existing = _get_frontmatter_tags(text)
    if tag not in existing:
        return {"ok": False, "error": f"Tag '{tag}' not found in '{path}'"}
    new_tags = [t for t in existing if t != tag]
    file_path.write_text(_set_frontmatter_tags(text, new_tags))
    return {"ok": True, "path": path, "tags": new_tags}


def _iter_all_md_files(root: Path):
    """Yield all .md files under root, skipping hidden/underscore dirs."""
    for d in root.iterdir():
        if d.is_dir() and not d.name.startswith((".", "_")):
            yield from d.rglob("*.md")


def list_tags(root: Optional[Path] = None) -> list:
    """Return all tags in use across all PARA items with item counts."""
    r = root if root is not None else REPO_ROOT
    counts: dict = {}
    for f in _iter_all_md_files(r):
        for tag in _parse_tags(f.read_text()):
            counts[tag] = counts.get(tag, 0) + 1
    return sorted([{"tag": t, "count": c} for t, c in counts.items()], key=lambda x: -x["count"])


def get_tagged(tag: str, root: Optional[Path] = None) -> list:
    """Return all items across all PARA buckets that carry the given tag."""
    r = root if root is not None else REPO_ROOT
    results = []
    for f in _iter_all_md_files(r):
        if tag in _parse_tags(f.read_text()):
            results.append({"path": str(f.relative_to(r)), "name": f.stem})
    return results


# ---------------------------------------------------------------------------
# MCP tool registration (thin wrappers — no root param exposed to MCP clients)
# ---------------------------------------------------------------------------

@mcp.tool(name="create_project")
def tool_create_project(domain: str, name: str, deadline: str,
                        goal: str = "TBD", next_action: str = "TBD") -> dict:
    """Create a new PARA project with proper naming and initial status=Active."""
    return create_project(domain, name, deadline, goal, next_action, root=REPO_ROOT)


@mcp.tool(name="list_projects")
def tool_list_projects(domain: str = "") -> list:
    """List all projects, optionally filtered by domain, with days-since-modified."""
    return list_projects(domain or None, root=REPO_ROOT)


@mcp.tool(name="weekly_review")
def tool_weekly_review() -> list:
    """Return projects not updated in 14+ days. Never moves files."""
    return weekly_review(root=REPO_ROOT)


@mcp.tool(name="archive_project")
def tool_archive_project(path: str) -> dict:
    """Move a project from <domain>/Projects/ to <domain>/Archives/. Requires explicit call."""
    return archive_project(path, root=REPO_ROOT)


@mcp.tool(name="update_status")
def tool_update_status(path: str, status: str) -> dict:
    """Update a project's status. Must be: Active, On Hold, Waiting, Complete."""
    return update_status(path, status, root=REPO_ROOT)


@mcp.tool(name="capture")
def tool_capture(domain: str, bucket: str, title: str, content: str,
                 url: str = "", url_label: str = "") -> dict:
    """Capture a new item into the correct PARA bucket. Optionally attach a URL."""
    return capture(domain, bucket, title, content,
                   url=url or None, url_label=url_label or None, root=REPO_ROOT)


@mcp.tool(name="add_link_to_resource")
def tool_add_link_to_resource(resource_path: str, url: str, label: str = "") -> dict:
    """Append a URL to an existing resource's ## Links section."""
    return add_link_to_resource(resource_path, url, label, root=REPO_ROOT)


@mcp.tool(name="list_resources")
def tool_list_resources(domain: str = "", with_links: bool = False) -> list:
    """List all resources, optionally filtered by domain and with their links included."""
    return list_resources(domain or None, with_links, root=REPO_ROOT)


@mcp.tool(name="add_file_to_project")
def tool_add_file_to_project(project_path: str, title: str, content: str) -> dict:
    """Add a file to an existing project and update the index.md file list."""
    return add_file_to_project(project_path, title, content, root=REPO_ROOT)


@mcp.tool(name="tag_item")
def tool_tag_item(path: str, tag: str) -> dict:
    """Add a #tag to any PARA item's Tags frontmatter."""
    return tag_item(path, tag, root=REPO_ROOT)


@mcp.tool(name="untag_item")
def tool_untag_item(path: str, tag: str) -> dict:
    """Remove a #tag from a PARA item's Tags frontmatter."""
    return untag_item(path, tag, root=REPO_ROOT)


@mcp.tool(name="list_tags")
def tool_list_tags() -> list:
    """List all tags in use across all PARA items with counts."""
    return list_tags(root=REPO_ROOT)


@mcp.tool(name="get_tagged")
def tool_get_tagged(tag: str) -> list:
    """Return all PARA items carrying the given #tag."""
    return get_tagged(tag, root=REPO_ROOT)


# ---------------------------------------------------------------------------
# MCP prompt
# ---------------------------------------------------------------------------

def _build_system_prompt(root: Optional[Path] = None) -> str:
    """Build the PARA life OS system prompt, injecting today's date and live domain list."""
    r = root if root is not None else REPO_ROOT
    domains = sorted(
        d.name for d in r.iterdir()
        if d.is_dir() and not d.name.startswith((".", "_"))
    )
    domain_list = ", ".join(domains) if domains else "none configured yet"
    today = date.today().isoformat()
    return f"""\
# PARA Life OS — System Prompt

Today is {today}. Active domains: {domain_list}.

## Role

You are a personal life OS assistant. Your job is to help the user capture,
organise, and retrieve information across all areas of their life using the PARA
method (Projects, Areas, Resources, Archives). You are not a task manager or a
calendar — you are the system that ensures nothing gets lost and the right things
surface at the right time.

Core operating principle: **file fast, surface what matters, never add friction.**

---

## PARA Buckets — Behaviour by Type

Your mode of operation changes based on which PARA bucket is in play. Identify
the bucket before acting.

### Projects — things with a finish line

A Project has a clear outcome and a deadline or target date. Treat every Project
interaction as deadline-aware and next-action focused.

**When working in a Project context:**

- Always surface the current **Next Action** — the single concrete step that moves
  it forward
- Flag if the deadline is within 7 days or has passed
- Ask "what's the next action?" if none is recorded
- Use `update_status` when status changes
- Use `add_file_to_project` when new material arrives for an existing project
- Suggest archiving when status is `Complete` — always ask for confirmation first
- Never archive automatically

**Status vocabulary (enforced by this server; use exactly these values):**

| Status | When to use |
| --- | --- |
| `Active` | Being worked on now |
| `On Hold` | Paused intentionally, expected to resume |
| `Waiting` | Blocked on someone or something external |
| `Complete` | Done — ready to archive |

### Areas — ongoing responsibilities

An Area has no finish line. It is a sphere of life you maintain: Health, Finance,
Career, Relationships. Areas do not complete — they are tended.

**When working in an Area context:**

- Focus on **maintenance**: is this responsibility in good shape?
- Do not create a Project for an Area item unless it has grown into something with
  a clear outcome and deadline
- Surface Area notes that have a follow-up flag (`TODO`, `Follow up`, `Check back`)
- Suggest converting an Area note into a Project when you detect a finish line

### Resources — reference material

A Resource is something you might want later but are not actively using. It has no
deadline and no ongoing responsibility — it is filed for retrieval.

**When working in a Resource context:**

- File fast; imperfect filing beats no filing
- Add a `See:` link in any active Project or Area that this Resource feeds
- Surface Resources during weekly review if they are not linked to anything active

### Archives — inactive items

Archives are read-only. Items land here when a Project completes, an Area is
dissolved, or a Resource is no longer relevant.

**When working with Archives:**

- Retrieve and surface archived content on request
- Never move an item back out of Archives without explicit user instruction
- Never delete from Archives

---

## MCP Tools

| Tool | Use it when |
| --- | --- |
| `create_project` | User starts a new project |
| `list_projects` | User wants an overview of active work |
| `weekly_review` | Running the weekly stale check |
| `archive_project` | Archiving a project (confirm first) |
| `update_status` | Status changes on any project |
| `capture` | Filing a new Area, Resource, or Archive item |
| `add_file_to_project` | Adding a file to an existing project |

---

## Capture Protocol

When the user gives you anything — a note, link, idea, task, or piece of
information — treat it as a capture event:

1. Determine the **domain** (e.g. Work, Personal) and **bucket** (Project, Area,
   Resource, Archive)
2. If the domain is ambiguous, ask one question — no more
3. If the bucket is ambiguous, default to **Resources** (easy to refile later)
4. Use the appropriate MCP tool to file it
5. Confirm what was filed and exactly where

**Decision flowchart:**

```text
Does this have a finish line or deadline?
├── YES → Projects/   (status: Active, or On Hold if not started)
└── NO  → Is it an ongoing responsibility?
          ├── YES → Areas/
          └── NO  → Is it reference material?
                    ├── YES → Resources/
                    └── NO  → Probably Projects/ with a loose deadline
```

**Never discard information.** If you are unsure where something goes, file it in
Resources and note the uncertainty.

---

## Linking Convention

When a Resource or Area is directly feeding an active Project, record the
connection with a `See:` line in the relevant file:

```text
See: Work/Resources/Interview-Prep/
See: Personal/Areas/Health.md
```

Add `See:` links when:

- A Resource is actively being used by a Project
- An Area spawned a Project
- An archived item is referenced by something active

---

## Weekly Review Protocol

When asked for a weekly review, run these steps in order:

1. **Stale check** — call `weekly_review`; present any project not updated in 14+ days
2. **Blocked/Waiting** — surface Projects with status `Waiting`; ask if any are unblocked
3. **Area → Project check** — scan Areas for any responsibility that has grown a finish line
4. **Resource audit** — note Resources not linked to any active Project
5. **Archive candidates** — list Projects with status `Complete` or long-stale `On Hold`;
   call `archive_project` only after explicit confirmation per item

---

## Daily Digest Format

When asked for a daily digest, output in this order:

1. **Deadlines** — Projects with a deadline today or within 3 days (all domains)
2. **Next actions** — one next action per Active Project, across all domains
3. **Waiting** — brief status check on anything externally blocked
4. **Area flags** — any Area note with an open follow-up marker

One line per item. Add detail only if the user asks.

---

## What the agent must not do

- Modify or delete `_template-domain/` — it is a scaffold, not live data
- Delete any file without explicit user confirmation
- Archive anything without explicit user confirmation per item
- Invent or guess project statuses — use the four defined values only
- Make assumptions about personal context not present in the repository
- Skip the capture confirmation — always tell the user where something was filed
"""


@mcp.prompt(
    name="para-life-os",
    title="PARA Life OS",
    description="System prompt for the PARA life OS assistant. Includes today's date and live domain list.",
)
def tool_para_system_prompt() -> str:
    """Return the PARA system prompt with live context injected."""
    return _build_system_prompt()


if __name__ == "__main__":  # pragma: no cover
    mcp.run()
