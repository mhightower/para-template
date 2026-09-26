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
    return re.sub(r"[\s_]+", "-", name).strip("-")


def _ensure_dated_name(name: str) -> str:
    name = _sanitize_name(name)
    if not PROJECT_NAME_RE.match(name):
        name = f"{date.today().strftime('%Y-%m')}-{name}"
    return name


def _parse_index(index_path: Path) -> dict:
    text = index_path.read_text()
    result = {}
    for field in ("Status", "Deadline", "Goal", "Next Action"):
        m = re.search(rf"\*\*{field}:\*\*\s*(.+)", text)
        result[field.lower().replace(" ", "_")] = m.group(1).strip() if m else ""
    return result


def _write_index(index_path: Path, name: str, status: str, deadline: str,
                 goal: str = "TBD", next_action: str = "TBD") -> None:
    index_path.write_text(
        f"# {name}\n\n"
        f"**Status:** {status}\n"
        f"**Deadline:** {deadline}\n"
        f"**Goal:** {goal}\n"
        f"**Next Action:** {next_action}\n"
    )


# ---------------------------------------------------------------------------
# Business logic (root=None → uses REPO_ROOT; pass root for tests)
# ---------------------------------------------------------------------------

def create_project(domain: str, name: str, deadline: str,
                   goal: str = "TBD", next_action: str = "TBD",
                   root: Optional[Path] = None) -> dict:
    r = root if root is not None else REPO_ROOT
    name = _ensure_dated_name(name)
    project_dir = r / domain / "Projects" / name
    if project_dir.exists():
        return {"ok": False, "error": f"Project '{name}' already exists in {domain}/Projects"}
    project_dir.mkdir(parents=True)
    _write_index(project_dir / "index.md", name, "Active", deadline, goal, next_action)
    return {"ok": True, "path": str(project_dir.relative_to(r))}


def list_projects(domain: Optional[str] = None, root: Optional[Path] = None) -> list:
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
                "days_since_modified": days_since,
            })
    return results


def weekly_review(root: Optional[Path] = None) -> list:
    return [p for p in list_projects(root=root) if p["days_since_modified"] >= STALE_DAYS]


def archive_project(path: str, root: Optional[Path] = None) -> dict:
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
            root: Optional[Path] = None) -> dict:
    if bucket not in VALID_BUCKETS:
        return {
            "ok": False,
            "error": f"Invalid bucket '{bucket}'. Must be one of: {', '.join(sorted(VALID_BUCKETS))}",
        }
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
    return {"ok": True, "path": str(file_path.relative_to(r))}


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
def tool_capture(domain: str, bucket: str, title: str, content: str) -> dict:
    """Capture a new item into the correct PARA bucket."""
    return capture(domain, bucket, title, content, root=REPO_ROOT)


@mcp.tool(name="add_file_to_project")
def tool_add_file_to_project(project_path: str, title: str, content: str) -> dict:
    """Add a file to an existing project and update the index.md file list."""
    return add_file_to_project(project_path, title, content, root=REPO_ROOT)


if __name__ == "__main__":  # pragma: no cover
    mcp.run()
