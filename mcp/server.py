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
INBOX_DIR = "Inbox"

mcp = MCPServer("PARA")


def _now() -> datetime:
    """Return current datetime; exists as a seam for testing."""
    return datetime.now()


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
        m = re.search(rf"\*\*{field}:\*\*[ \t]*([^\n]*)", text)
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


def _audit(action: str, source: str, destination: str, root: Path) -> None:
    """Append a line to the PARA audit log."""
    log = root / ".para-audit.log"
    ts = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
    with log.open("a") as f:
        f.write(f"{ts}  {action}  {source}  ->  {destination}\n")


def _find_items_by_name(name: str, exclude_bucket: str,
                        root: Path) -> list:
    """Return a list of dicts with path, domain, bucket, and kind matching name."""
    matches = []
    for domain_dir in sorted(root.iterdir()):
        if not domain_dir.is_dir() or domain_dir.name.startswith((".", "_")):
            continue
        for bucket in ("Projects", "Areas", "Resources", "Archives"):
            if bucket == exclude_bucket:
                continue
            bucket_dir = domain_dir / bucket
            if not bucket_dir.exists():
                continue
            # folder match
            candidate_dir = bucket_dir / name
            if candidate_dir.is_dir():
                matches.append({
                    "path": str(candidate_dir.relative_to(root)),
                    "domain": domain_dir.name,
                    "bucket": bucket,
                    "kind": "folder",
                })
            # file match
            candidate_file = bucket_dir / f"{name}.md"
            if candidate_file.is_file():
                matches.append({
                    "path": str(candidate_file.relative_to(root)),
                    "domain": domain_dir.name,
                    "bucket": bucket,
                    "kind": "file",
                })
    return matches


def archive_item(name: str, root: Optional[Path] = None) -> dict:
    """Archive any PARA item by name (or full path) in one step."""
    r = root if root is not None else REPO_ROOT

    # full path passed directly
    if "/" in name:
        parts = Path(name).parts
        if len(parts) != 3 or ".." in parts or any(p == "" for p in parts):
            return {"ok": False, "error": "Path must be exactly <domain>/<bucket>/<item>"}
        domain, bucket, item_name = parts[0], parts[1], parts[2]
        if bucket not in ("Projects", "Areas", "Resources", "Archives"):
            return {"ok": False, "error": f"Invalid bucket '{bucket}'; must be Projects, Areas, Resources, or Archives"}
        src = r / domain / bucket / item_name
        if not src.exists():
            return {"ok": False, "error": f"'{name}' not found"}
        matches = [{"path": str(src.relative_to(r)), "domain": domain, "bucket": bucket,
                    "kind": "folder" if src.is_dir() else "file"}]
    else:
        matches = _find_items_by_name(name, exclude_bucket="Archives", root=r)

    if not matches:
        return {"ok": False, "error": f"'{name}' not found in any PARA bucket"}
    if len(matches) > 1:
        return {"ok": False, "ambiguous": True, "matches": matches}

    match = matches[0]
    src = r / match["path"]
    domain, bucket, item_name = match["domain"], match["bucket"], src.name
    dest_dir = r / domain / "Archives"
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / item_name

    # record original bucket
    if match["kind"] == "folder":
        index = src / "index.md"
        if index.exists():
            text = index.read_text().rstrip("\n")
            if "**Original Bucket:**" not in text:
                index.write_text(text + f"\n**Original Bucket:** {bucket}\n")
    else:
        text = src.read_text().rstrip("\n")
        if "**Original Bucket:**" not in text:
            src.write_text(text + f"\n**Original Bucket:** {bucket}\n")

    shutil.move(str(src), str(dest))
    source_path = match["path"]
    dest_path = f"{domain}/Archives/{item_name}"
    _audit("archive", source_path, dest_path, r)
    return {"ok": True, "source": source_path, "destination": dest_path}


def _find_in_archives(name: str, root: Path) -> list:
    """Return matches for name inside Archives buckets."""
    matches = []
    for domain_dir in sorted(root.iterdir()):
        if not domain_dir.is_dir() or domain_dir.name.startswith((".", "_")):
            continue
        arch_dir = domain_dir / "Archives"
        if not arch_dir.exists():
            continue
        candidate_dir = arch_dir / name
        if candidate_dir.is_dir():
            matches.append({
                "path": str(candidate_dir.relative_to(root)),
                "domain": domain_dir.name,
                "kind": "folder",
            })
        candidate_file = arch_dir / f"{name}.md"
        if candidate_file.is_file():
            matches.append({
                "path": str(candidate_file.relative_to(root)),
                "domain": domain_dir.name,
                "kind": "file",
            })
    return matches


def revive_item(name: str, root: Optional[Path] = None) -> dict:
    """Restore an archived PARA item to its original bucket in one step."""
    r = root if root is not None else REPO_ROOT

    if "/" in name:
        parts = Path(name).parts
        if len(parts) != 3 or parts[1] != "Archives" or ".." in parts or any(p == "" for p in parts):
            return {"ok": False, "error": "Path must be exactly <domain>/Archives/<item>"}
        domain, item_name = parts[0], parts[2]
        src = r / domain / "Archives" / item_name
        if not src.exists():
            return {"ok": False, "error": f"'{name}' not found in Archives"}
        matches = [{"path": str(src.relative_to(r)), "domain": domain,
                    "kind": "folder" if src.is_dir() else "file"}]
    else:
        matches = _find_in_archives(name, r)

    if not matches:
        return {"ok": False, "error": f"'{name}' not found in Archives"}
    if len(matches) > 1:
        return {"ok": False, "ambiguous": True, "matches": matches}

    match = matches[0]
    src = r / match["path"]
    domain = match["domain"]
    item_name = src.name

    # determine original bucket
    valid_buckets = {"Projects", "Areas", "Resources"}
    if match["kind"] == "folder":
        index = src / "index.md"
        if index.exists():
            m = re.search(r"\*\*Original Bucket:\*\*\s*(.+)", index.read_text())
            original_bucket = m.group(1).strip() if m else "Projects"
        else:
            original_bucket = "Projects"
    else:
        m = re.search(r"\*\*Original Bucket:\*\*\s*(.+)", src.read_text())
        original_bucket = m.group(1).strip() if m else "Areas"
    if original_bucket not in valid_buckets:
        original_bucket = "Projects"

    dest_dir = r / domain / original_bucket
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / item_name
    shutil.move(str(src), str(dest))
    source_path = match["path"]
    dest_path = f"{domain}/{original_bucket}/{item_name}"
    _audit("revive", source_path, dest_path, r)
    return {"ok": True, "source": source_path, "destination": dest_path}


VALID_DIGEST_PERIODS = {"daily", "weekly"}


def generate_digest(period: str = "daily", root: Optional[Path] = None) -> dict:
    """Generate a structured daily or weekly PARA digest.

    Sections: deadlines, next_actions, waiting, area_flags, recent_items.
    Weekly adds stale_alerts. Empty periods return a nothing_new dict.
    """
    if period not in VALID_DIGEST_PERIODS:
        return {"ok": False, "error": f"Invalid period '{period}'. Must be one of: {', '.join(sorted(VALID_DIGEST_PERIODS))}"}

    r = root if root is not None else REPO_ROOT
    today = date.today()
    projects = list_projects(root=r)

    deadlines = []
    next_actions = []
    waiting = []

    for p in projects:
        # read next_action from index.md
        index_path = r / p["path"] / "index.md"
        parsed = _parse_index(index_path) if index_path.exists() else {}
        next_action = parsed.get("next_action", "TBD")

        deadline_str = p.get("deadline", "")
        if deadline_str:
            try:
                deadline = date.fromisoformat(deadline_str)
                delta = (deadline - today).days
                if 0 <= delta <= 3:
                    deadlines.append({
                        "name": p["name"],
                        "deadline": deadline_str,
                        "deadline_relative": p.get("deadline_relative", ""),
                        "path": p["path"],
                    })
            except ValueError:
                pass

        if p.get("status") == "Active":
            next_actions.append({
                "name": p["name"],
                "next_action": next_action,
                "path": p["path"],
            })
        elif p.get("status") == "Waiting":
            waiting.append({"name": p["name"], "next_action": next_action, "path": p["path"]})

    # area flags
    area_flags = []
    for domain_dir in sorted(r.iterdir()):
        if not domain_dir.is_dir() or domain_dir.name.startswith((".", "_")):
            continue
        areas_dir = domain_dir / "Areas"
        if not areas_dir.exists():
            continue
        for md_file in areas_dir.rglob("*.md"):
            text = md_file.read_text(errors="replace")
            if re.search(r"\b(TODO|Follow up|Check back)\b", text, re.IGNORECASE):
                area_flags.append({
                    "name": md_file.stem,
                    "path": str(md_file.relative_to(r)),
                })

    # recent items: modified within threshold window
    threshold = 1 if period == "daily" else 7
    recent_items = []
    for domain_dir in sorted(r.iterdir()):
        if not domain_dir.is_dir() or domain_dir.name.startswith((".", "_")):
            continue
        for bucket in ("Projects", "Areas", "Resources"):
            bucket_dir = domain_dir / bucket
            if not bucket_dir.exists():
                continue
            for md_file in bucket_dir.rglob("*.md"):
                mtime = datetime.fromtimestamp(md_file.stat().st_mtime)
                days_since = (datetime.now() - mtime).days
                if days_since < threshold:
                    recent_items.append({
                        "name": md_file.stem,
                        "path": str(md_file.relative_to(r)),
                        "bucket": bucket,
                    })

    if not deadlines and not next_actions and not waiting and not area_flags and not recent_items:
        return {"ok": True, "nothing_new": True, "message": "Nothing new to report."}

    # TODO: "items moved" (inbox→project) and "projects updated" tracking are not yet implemented
    result = {
        "ok": True,
        "period": period,
        "deadlines": deadlines,
        "next_actions": next_actions,
        "waiting": waiting,
        "area_flags": area_flags,
        "recent_items": recent_items,
    }

    if period == "weekly":
        result["stale_alerts"] = weekly_review(root=r)

    return result


WIKI_LINK_RE = re.compile(r"\[\[([^\[\]]+)\]\]")


def _extract_wiki_links(text: str) -> list:
    """Return all [[name]] targets from text."""
    return WIKI_LINK_RE.findall(text)


def _resolve_link_path(name: str, root: Path) -> Optional[str]:
    """Return the relative path for a wiki-link name, or None if not found."""
    for domain_dir in root.iterdir():
        if not domain_dir.is_dir() or domain_dir.name.startswith((".", "_")):
            continue
        for bucket in ("Projects", "Areas", "Resources", "Archives"):
            bucket_dir = domain_dir / bucket
            if not bucket_dir.exists():
                continue
            folder = bucket_dir / name
            if folder.is_dir():
                return str(folder.relative_to(root))
            md_file = bucket_dir / f"{name}.md"
            if md_file.is_file():
                return str(md_file.relative_to(root))
    return None


def _find_item_path(name: str, root: Path) -> Optional[Path]:
    """Return the Path object for an item (folder index.md or .md file) by name."""
    for domain_dir in root.iterdir():
        if not domain_dir.is_dir() or domain_dir.name.startswith((".", "_")):
            continue
        for bucket in ("Projects", "Areas", "Resources", "Archives"):
            bucket_dir = domain_dir / bucket
            if not bucket_dir.exists():
                continue
            folder = bucket_dir / name
            if folder.is_dir():
                idx = folder / "index.md"
                if idx.exists():
                    return idx
            md_file = bucket_dir / f"{name}.md"
            if md_file.is_file():
                return md_file
    return None


def list_links(item_name: str, root: Optional[Path] = None) -> dict:
    """List all forward and back references for a PARA item.

    Forward links are [[...]] targets found in the item's content.
    Backlinks are files across all buckets that contain [[item_name]].
    """
    r = root if root is not None else REPO_ROOT
    item_path = _find_item_path(item_name, r)
    if item_path is None:
        return {"ok": False, "error": f"Item '{item_name}' not found"}

    text = item_path.read_text(errors="replace")
    link_names = _extract_wiki_links(text)
    forward_links = [
        {"name": n, "path": _resolve_link_path(n, r)}
        for n in link_names
    ]

    backlinks = []
    for domain_dir in sorted(r.iterdir()):
        if not domain_dir.is_dir() or domain_dir.name.startswith((".", "_")):
            continue
        for bucket in ("Projects", "Areas", "Resources", "Archives"):
            bucket_dir = domain_dir / bucket
            if not bucket_dir.exists():
                continue
            for md_file in bucket_dir.rglob("*.md"):
                if md_file == item_path:
                    continue
                content = md_file.read_text(errors="replace")
                if f"[[{item_name}]]" in content:
                    # for folder-based items (index.md), use the parent dir name
                    link_name = (md_file.parent.name
                                 if md_file.name == "index.md" else md_file.stem)
                    backlinks.append({
                        "name": link_name,
                        "path": str(md_file.relative_to(r)),
                    })

    return {
        "ok": True,
        "item": item_name,
        "path": str(item_path.relative_to(r)),
        "forward_links": forward_links,
        "backlinks": backlinks,
    }


def lint_links(root: Optional[Path] = None) -> list:
    """Return all broken [[wiki-links]] across the PARA vault."""
    r = root if root is not None else REPO_ROOT
    resolve_cache: dict = {}

    def _cached_resolve(name: str) -> Optional[Path]:
        if name not in resolve_cache:
            resolve_cache[name] = _resolve_link_path(name, r)
        return resolve_cache[name]

    broken = []
    for domain_dir in sorted(r.iterdir()):
        if not domain_dir.is_dir() or domain_dir.name.startswith((".", "_")):
            continue
        for bucket in ("Projects", "Areas", "Resources", "Archives"):
            bucket_dir = domain_dir / bucket
            if not bucket_dir.exists():
                continue
            for md_file in bucket_dir.rglob("*.md"):
                text = md_file.read_text(errors="replace")
                for name in _extract_wiki_links(text):
                    if _cached_resolve(name) is None:
                        broken.append({
                            "source_path": str(md_file.relative_to(r)),
                            "link_name": name,
                        })
    return broken


def staleness_nudge(threshold_days: int = 30, root: Optional[Path] = None) -> list:
    """Return projects whose last modification exceeds threshold_days.

    Staleness is based on the most recent mtime across all files in the project
    directory (not just index.md). Respects a per-project **Staleness Threshold:**
    N field in index.md.
    """
    r = root if root is not None else REPO_ROOT
    results = []
    for proj in list_projects(root=r):
        proj_dir = r / proj["path"]
        index_path = proj_dir / "index.md"
        text = index_path.read_text() if index_path.exists() else ""
        m = re.search(r"\*\*Staleness Threshold:\*\*\s*(\d+)", text)
        effective_threshold = int(m.group(1)) if m else threshold_days
        # use most recent mtime across all files in the project dir
        all_files = list(proj_dir.rglob("*"))
        if all_files:
            newest_mtime = max(f.stat().st_mtime for f in all_files if f.is_file())
            days_since = (datetime.now() - datetime.fromtimestamp(newest_mtime)).days
        else:
            days_since = proj["days_since_modified"]
        if days_since >= effective_threshold:
            entry = dict(proj)
            entry["days_since_modified"] = days_since
            results.append(entry)
    return results


VALID_NUDGE_ACTIONS = {"archive", "continue", "convert-to-area"}


def respond_to_staleness_nudge(path: str, action: str,
                                root: Optional[Path] = None) -> dict:
    """Handle a user response to a staleness nudge: archive, continue, or convert-to-area."""
    if action not in VALID_NUDGE_ACTIONS:
        return {
            "ok": False,
            "error": f"Invalid action '{action}'. Must be one of: {', '.join(sorted(VALID_NUDGE_ACTIONS))}",
        }
    # Validate path is exactly <domain>/Projects/<name> (relative, no traversal)
    parts = Path(path).parts
    if (len(parts) != 3 or parts[1] != "Projects"
            or ".." in parts or any(p == "" for p in parts)):
        return {"ok": False, "error": "Path must be exactly <domain>/Projects/<name>"}
    r = root if root is not None else REPO_ROOT
    src = r / parts[0] / "Projects" / parts[2]
    if not src.exists():
        return {"ok": False, "error": f"Path '{path}' not found"}

    if action == "archive":
        return archive_project(path, root=r)

    if action == "continue":
        index = src / "index.md"
        index.touch()
        return {"ok": True, "path": path, "action": "continue"}

    # convert-to-area
    domain, name = parts[0], parts[2]
    dest_dir = r / domain / "Areas"
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / name
    if dest.exists():
        return {"ok": False, "error": f"'{name}' already exists in {domain}/Areas"}
    shutil.move(str(src), str(dest))
    return {"ok": True, "path": f"{domain}/Areas/{name}", "action": "convert-to-area"}


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


def find_items(query: str, root: Optional[Path] = None) -> dict:
    """Search all PARA buckets for items matching the natural-language query.

    Returns a dict with ok=True and results list, or ok=False with a message
    and suggestions when nothing matches or query is empty.
    """
    r = root if root is not None else REPO_ROOT
    terms = [t.lower() for t in query.split() if t]

    if not terms:
        return {
            "ok": False,
            "message": "Query is empty.",
            "suggestions": [
                "Enter one or more keywords to search.",
                "Try a project name, area, or topic.",
            ],
        }

    def _score(filename: str, text: str) -> int:
        name_lower = filename.lower()
        text_lower = text.lower()
        score = 0
        for term in terms:
            score += name_lower.count(term) * 3  # filename match weighted higher
            score += text_lower.count(term)
        return score

    def _excerpt(text: str, terms: list) -> str:
        lower = text.lower()
        best_pos = None
        for term in terms:
            idx = lower.find(term)
            if idx != -1 and (best_pos is None or idx < best_pos):
                best_pos = idx
        if best_pos is None:
            best_pos = 0
        start = max(0, best_pos - 40)
        snippet = text[start:start + 160].strip()
        return snippet[:200]

    results = []
    for domain_dir in sorted(r.iterdir()):
        if not domain_dir.is_dir() or domain_dir.name.startswith((".", "_")):
            continue
        for bucket in ("Projects", "Areas", "Resources", "Archives"):
            bucket_dir = domain_dir / bucket
            if not bucket_dir.exists():
                continue
            for md_file in bucket_dir.rglob("*.md"):
                text = md_file.read_text(errors="replace")
                score = _score(md_file.stem, text)
                if score == 0:
                    continue
                # derive title from first heading or filename
                m = re.search(r"^#\s+(.+)", text, re.MULTILINE)
                title = m.group(1).strip() if m else md_file.stem
                results.append({
                    "title": title,
                    "path": str(md_file.relative_to(r)),
                    "bucket": bucket,
                    "excerpt": _excerpt(text, terms),
                    "_score": score,
                })

    if not results:
        return {
            "ok": False,
            "message": f"No results found for '{query}'.",
            "suggestions": [
                "Try broader or different keywords.",
                "Check spelling of project or file names.",
                "Use a single keyword to widen the search.",
            ],
        }

    results.sort(key=lambda x: x["_score"], reverse=True)
    for item in results:
        del item["_score"]
    return {"ok": True, "results": results}


# ---------------------------------------------------------------------------
# Inbox capture and triage
# ---------------------------------------------------------------------------

def capture_to_inbox(content: str, tags: Optional[list] = None,
                     root: Optional[Path] = None) -> dict:
    """File raw content into Inbox/ with a timestamped filename and optional tag frontmatter."""
    r = root if root is not None else REPO_ROOT
    inbox = r / INBOX_DIR
    inbox.mkdir(parents=True, exist_ok=True)
    ts = _now().strftime("%Y-%m-%d-%H%M%S")
    file_path = inbox / f"{ts}.md"
    tags = tags or []
    if tags:
        tag_lines = "\n".join(f"  - {t}" for t in tags)
        text = f"---\ntags:\n{tag_lines}\n---\n\n{content}\n"
    else:
        text = content + "\n"
    file_path.write_text(text)
    return {"ok": True, "path": str(file_path.relative_to(r))}


def _collect_para_names(root: Path) -> list:
    """Walk the PARA structure and return (bucket_type, display_name, relative_path) tuples."""
    items = []
    for domain_dir in root.iterdir():
        if not domain_dir.is_dir() or domain_dir.name.startswith((".", "_")):
            continue
        if domain_dir.name == INBOX_DIR:
            continue
        for bucket in ("Projects", "Areas", "Resources"):
            bucket_dir = domain_dir / bucket
            if not bucket_dir.exists():
                continue
            for entry in bucket_dir.iterdir():
                if entry.is_dir() and (entry / "index.md").exists():
                    items.append((bucket, entry.name, str(entry.relative_to(root))))
                elif entry.is_file() and entry.suffix == ".md":
                    items.append((bucket, entry.stem, str(entry.relative_to(root))))
    return items


def _extract_tags_from_inbox(text: str) -> list:
    """Parse YAML frontmatter tags list from inbox file text."""
    if not text.startswith("---\n"):
        return []
    end = text.find("\n---\n", 4)
    if end == -1:
        return []
    frontmatter = text[4:end]
    tags = []
    in_tags = False
    for line in frontmatter.splitlines():
        if line.strip() == "tags:":
            in_tags = True
            continue
        if in_tags:
            m = re.match(r"^\s+-\s+(.+)$", line)
            if m:
                tags.append(m.group(1).strip().lower())
            else:
                in_tags = False
    return tags


def suggest_triage(inbox_file: str, root: Optional[Path] = None) -> dict:
    """Read an inbox file and suggest PARA destinations based on keyword/tag matching."""
    r = root if root is not None else REPO_ROOT
    file_path = r / inbox_file
    if not file_path.exists():
        return {"ok": False, "error": f"Inbox file not found: '{inbox_file}'"}

    text = file_path.read_text()
    tags = _extract_tags_from_inbox(text)
    content_lower = text.lower()

    para_items = _collect_para_names(root=r)
    suggestions = []

    for bucket, name, path in para_items:
        name_words = re.split(r"[\s\-_]+", name.lower())
        name_words = [w for w in name_words if len(w) > 2 and not re.match(r"^\d+$", w)]

        tag_hit = any(w in tags for w in name_words)
        keyword_hits = sum(1 for w in name_words if w in content_lower)

        if tag_hit:
            suggestions.append({
                "destination": path,
                "reason": f"Tag match on '{name}'",
                "confidence": "high",
            })
        elif keyword_hits >= 2:
            suggestions.append({
                "destination": path,
                "reason": f"Keyword match on '{name}' ({keyword_hits} words)",
                "confidence": "high",
            })
        elif keyword_hits == 1:
            suggestions.append({
                "destination": path,
                "reason": f"Keyword match on '{name}'",
                "confidence": "medium" if len(name_words) == 1 else "low",
            })

    suggestions.sort(key=lambda s: {"high": 0, "medium": 1, "low": 2}[s["confidence"]])
    return {"ok": True, "suggestions": suggestions}
# Due-dates (issue #26)
# ---------------------------------------------------------------------------

def set_due(project_path: str, due_date: str, root: Optional[Path] = None) -> dict:
    """Set or update the Deadline field in a project's index.md."""
    try:
        date.fromisoformat(due_date)
    except ValueError:
        return {"ok": False, "error": f"Invalid date '{due_date}'. Use ISO format YYYY-MM-DD."}
    r = root if root is not None else REPO_ROOT
    index = r / project_path / "index.md"
    if not index.exists():
        return {"ok": False, "error": f"Project not found at '{project_path}'"}
    text = index.read_text()
    if "**Deadline:**" not in text:
        return {"ok": False, "error": f"No Deadline field found in '{project_path}/index.md'"}
    text = re.sub(r"(?m)^\*\*Deadline:\*\*[ \t]*.*$", f"**Deadline:** {due_date}", text)
    index.write_text(text)
    return {"ok": True, "path": project_path, "deadline": due_date}


def unset_due(project_path: str, root: Optional[Path] = None) -> dict:
    """Clear the Deadline field in a project's index.md."""
    r = root if root is not None else REPO_ROOT
    index = r / project_path / "index.md"
    if not index.exists():
        return {"ok": False, "error": f"Project not found at '{project_path}'"}
    text = index.read_text()
    if "**Deadline:**" not in text:
        return {"ok": False, "error": f"No Deadline field found in '{project_path}/index.md'"}
    text = re.sub(r"(?m)^\*\*Deadline:\*\*[ \t]*.*$", "**Deadline:**", text)
    index.write_text(text)
    return {"ok": True, "path": project_path, "deadline": ""}


def list_due(domain: Optional[str] = None, root: Optional[Path] = None) -> list:
    """Return all projects with a deadline, sorted ascending by date."""
    projects = list_projects(domain=domain, root=root)
    with_deadline = [p for p in projects if p.get("deadline")]
    with_deadline.sort(key=lambda x: x["deadline"])
    return with_deadline


def get_upcoming_deadlines(days: int = 7, domain: Optional[str] = None,
                           root: Optional[Path] = None) -> list:
    """Return projects with deadlines within the next `days` days."""
    today = date.today()
    results = []
    for p in list_due(domain=domain, root=root):
        try:
            dl = date.fromisoformat(p["deadline"])
        except ValueError:
            continue
        delta = (dl - today).days
        if 0 <= delta <= days:
            results.append(p)
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


@mcp.tool(name="capture_to_inbox")
def tool_capture_to_inbox(content: str, tags: Optional[list] = None) -> dict:
    """Drop raw content into Inbox/ without choosing a project or area upfront."""
    return capture_to_inbox(content, tags=tags or [], root=REPO_ROOT)


@mcp.tool(name="suggest_triage")
def tool_suggest_triage(inbox_file: str) -> dict:
    """Suggest which Project/Area/Resource an inbox item belongs to."""
    return suggest_triage(inbox_file, root=REPO_ROOT)


@mcp.tool(name="set_due")
def tool_set_due(project_path: str, due_date: str) -> dict:
    """Set or update the deadline on a project. due_date: YYYY-MM-DD."""
    return set_due(project_path, due_date, root=REPO_ROOT)


@mcp.tool(name="unset_due")
def tool_unset_due(project_path: str) -> dict:
    """Clear the deadline from a project."""
    return unset_due(project_path, root=REPO_ROOT)


@mcp.tool(name="list_due")
def tool_list_due(domain: str = "") -> list:
    """List all projects with deadlines, sorted ascending by date."""
    return list_due(domain=domain or None, root=REPO_ROOT)


@mcp.tool(name="get_upcoming_deadlines")
def tool_get_upcoming_deadlines(days: int = 7, domain: str = "") -> list:
    """Return projects with deadlines within the next N days (default 7)."""
    return get_upcoming_deadlines(days=days, domain=domain or None, root=REPO_ROOT)


@mcp.tool(name="archive_item")
def tool_archive_item(name: str) -> dict:
    """Archive any PARA item by name or path in one step."""
    return archive_item(name, root=REPO_ROOT)


@mcp.tool(name="revive_item")
def tool_revive_item(name: str) -> dict:
    """Restore an archived PARA item to its original bucket in one step."""
    return revive_item(name, root=REPO_ROOT)


@mcp.tool(name="find_items")
def tool_find_items(query: str) -> dict:
    """Search all PARA buckets with a natural-language query. Returns ranked results."""
    return find_items(query, root=REPO_ROOT)


@mcp.tool(name="generate_digest")
def tool_generate_digest(period: str = "daily") -> dict:
    """Generate a daily or weekly PARA digest. Trigger on demand with /digest."""
    return generate_digest(period=period, root=REPO_ROOT)


@mcp.tool(name="list_links")
def tool_list_links(item_name: str) -> dict:
    """List all forward and back [[wiki-link]] references for a PARA item."""
    return list_links(item_name, root=REPO_ROOT)


@mcp.tool(name="lint_links")
def tool_lint_links() -> list:
    """Return all broken [[wiki-links]] across the vault."""
    return lint_links(root=REPO_ROOT)


@mcp.tool(name="staleness_nudge")
def tool_staleness_nudge(threshold_days: int = 30) -> list:
    """List projects with no activity beyond threshold_days (default 30). Respects per-project overrides."""
    return staleness_nudge(threshold_days=threshold_days, root=REPO_ROOT)


@mcp.tool(name="respond_to_staleness_nudge")
def tool_respond_to_staleness_nudge(path: str, action: str) -> dict:
    """Respond to a staleness nudge: archive, continue, or convert-to-area."""
    return respond_to_staleness_nudge(path, action, root=REPO_ROOT)


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
