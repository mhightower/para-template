"""Unit tests for PARA MCP server — written before implementation (TDD)."""
import os
import time
from datetime import date
from pathlib import Path

import pytest

import server


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_project(root: Path, domain: str, name: str, deadline: str = "2026-12-31",
                 status: str = "Active") -> Path:
    proj = root / domain / "Projects" / name
    proj.mkdir(parents=True)
    (proj / "index.md").write_text(
        f"# {name}\n\n"
        f"**Status:** {status}\n"
        f"**Deadline:** {deadline}\n"
        f"**Goal:** TBD\n"
        f"**Next Action:** TBD\n"
    )
    return proj


def age_file(path: Path, days: int) -> None:
    t = time.time() - days * 86400
    os.utime(path, (t, t))


# ---------------------------------------------------------------------------
# create_project
# ---------------------------------------------------------------------------

class TestCreateProject:
    def test_creates_folder_and_index(self, tmp_path):
        result = server.create_project("Work", "2026-09-Test-Project", "2026-12-31", root=tmp_path)
        assert result["ok"] is True
        assert (tmp_path / "Work" / "Projects" / "2026-09-Test-Project" / "index.md").exists()

    def test_auto_prefixes_date_when_missing(self, tmp_path):
        result = server.create_project("Work", "NoDate", "2026-12-31", root=tmp_path)
        assert result["ok"] is True
        assert date.today().strftime("%Y-%m") in result["path"]

    def test_initial_status_is_active(self, tmp_path):
        server.create_project("Work", "2026-09-Foo", "2026-12-31", root=tmp_path)
        text = (tmp_path / "Work" / "Projects" / "2026-09-Foo" / "index.md").read_text()
        assert "**Status:** Active" in text

    def test_stores_deadline(self, tmp_path):
        server.create_project("Work", "2026-09-Bar", "2027-03-01", root=tmp_path)
        text = (tmp_path / "Work" / "Projects" / "2026-09-Bar" / "index.md").read_text()
        assert "**Deadline:** 2027-03-01" in text

    def test_stores_custom_goal_and_next_action(self, tmp_path):
        server.create_project(
            "Work", "2026-09-Baz", "2026-12-31",
            goal="Ship it", next_action="Write tests", root=tmp_path
        )
        text = (tmp_path / "Work" / "Projects" / "2026-09-Baz" / "index.md").read_text()
        assert "**Goal:** Ship it" in text
        assert "**Next Action:** Write tests" in text

    def test_rejects_duplicate(self, tmp_path):
        server.create_project("Work", "2026-09-Dup", "2026-12-31", root=tmp_path)
        result = server.create_project("Work", "2026-09-Dup", "2026-12-31", root=tmp_path)
        assert result["ok"] is False
        assert "already exists" in result["error"]

    def test_sanitizes_spaces_to_hyphens(self, tmp_path):
        result = server.create_project("Work", "My Cool Project", "2026-12-31", root=tmp_path)
        assert result["ok"] is True
        assert "My-Cool-Project" in result["path"]

    def test_creates_parent_dirs(self, tmp_path):
        result = server.create_project("NewDomain", "2026-09-X", "2026-12-31", root=tmp_path)
        assert result["ok"] is True
        assert (tmp_path / "NewDomain" / "Projects" / "2026-09-X").is_dir()

    def test_path_in_result_is_relative(self, tmp_path):
        result = server.create_project("Work", "2026-09-Rel", "2026-12-31", root=tmp_path)
        assert result["ok"] is True
        assert not Path(result["path"]).is_absolute()


# ---------------------------------------------------------------------------
# list_projects
# ---------------------------------------------------------------------------

class TestListProjects:
    def test_returns_all_projects_across_domains(self, tmp_path):
        make_project(tmp_path, "Work", "2026-09-A")
        make_project(tmp_path, "Personal", "2026-09-B")
        names = {p["name"] for p in server.list_projects(root=tmp_path)}
        assert {"2026-09-A", "2026-09-B"} == names

    def test_filters_by_domain(self, tmp_path):
        make_project(tmp_path, "Work", "2026-09-A")
        make_project(tmp_path, "Personal", "2026-09-B")
        result = server.list_projects(domain="Work", root=tmp_path)
        assert len(result) == 1
        assert result[0]["domain"] == "Work"

    def test_includes_days_since_modified(self, tmp_path):
        make_project(tmp_path, "Work", "2026-09-A")
        result = server.list_projects(root=tmp_path)
        assert "days_since_modified" in result[0]
        assert isinstance(result[0]["days_since_modified"], int)

    def test_returns_empty_when_no_projects(self, tmp_path):
        assert server.list_projects(root=tmp_path) == []

    def test_skips_project_dirs_without_index(self, tmp_path):
        (tmp_path / "Work" / "Projects" / "2026-09-NoIndex").mkdir(parents=True)
        assert server.list_projects(root=tmp_path) == []

    def test_includes_status_from_index(self, tmp_path):
        make_project(tmp_path, "Work", "2026-09-A", status="On Hold")
        result = server.list_projects(root=tmp_path)
        assert result[0]["status"] == "On Hold"

    def test_skips_hidden_dirs(self, tmp_path):
        make_project(tmp_path, ".git", "2026-09-A")
        assert server.list_projects(root=tmp_path) == []

    def test_includes_deadline_from_index(self, tmp_path):
        make_project(tmp_path, "Work", "2026-09-A", deadline="2027-06-01")
        result = server.list_projects(root=tmp_path)
        assert result[0]["deadline"] == "2027-06-01"

    def test_skips_domain_dirs_with_no_projects_subdir(self, tmp_path):
        (tmp_path / "Work").mkdir()
        assert server.list_projects(root=tmp_path) == []

    def test_skips_loose_files_in_projects_dir(self, tmp_path):
        (tmp_path / "Work" / "Projects").mkdir(parents=True)
        (tmp_path / "Work" / "Projects" / "README.md").write_text("ignore me")
        assert server.list_projects(root=tmp_path) == []


# ---------------------------------------------------------------------------
# weekly_review
# ---------------------------------------------------------------------------

class TestWeeklyReview:
    def test_returns_stale_projects(self, tmp_path):
        proj = make_project(tmp_path, "Work", "2026-09-Old")
        age_file(proj / "index.md", 15)
        result = server.weekly_review(root=tmp_path)
        assert any(p["name"] == "2026-09-Old" for p in result)

    def test_excludes_fresh_projects(self, tmp_path):
        make_project(tmp_path, "Work", "2026-09-Fresh")
        assert server.weekly_review(root=tmp_path) == []

    def test_does_not_move_files(self, tmp_path):
        proj = make_project(tmp_path, "Work", "2026-09-Stale")
        age_file(proj / "index.md", 20)
        server.weekly_review(root=tmp_path)
        assert (tmp_path / "Work" / "Projects" / "2026-09-Stale").exists()

    def test_exactly_14_days_is_stale(self, tmp_path):
        proj = make_project(tmp_path, "Work", "2026-09-Border")
        age_file(proj / "index.md", 14)
        result = server.weekly_review(root=tmp_path)
        assert any(p["name"] == "2026-09-Border" for p in result)

    def test_13_days_is_not_stale(self, tmp_path):
        proj = make_project(tmp_path, "Work", "2026-09-Almost")
        age_file(proj / "index.md", 13)
        result = server.weekly_review(root=tmp_path)
        assert not any(p["name"] == "2026-09-Almost" for p in result)

    def test_returns_empty_when_no_stale(self, tmp_path):
        make_project(tmp_path, "Work", "2026-09-Fresh")
        assert server.weekly_review(root=tmp_path) == []


# ---------------------------------------------------------------------------
# archive_project
# ---------------------------------------------------------------------------

class TestArchiveProject:
    def test_moves_to_archives(self, tmp_path):
        make_project(tmp_path, "Work", "2026-09-Done")
        result = server.archive_project("Work/Projects/2026-09-Done", root=tmp_path)
        assert result["ok"] is True
        assert (tmp_path / "Work" / "Archives" / "2026-09-Done").exists()

    def test_removes_from_projects(self, tmp_path):
        make_project(tmp_path, "Work", "2026-09-Done")
        server.archive_project("Work/Projects/2026-09-Done", root=tmp_path)
        assert not (tmp_path / "Work" / "Projects" / "2026-09-Done").exists()

    def test_fails_if_path_not_found(self, tmp_path):
        result = server.archive_project("Work/Projects/2026-09-Ghost", root=tmp_path)
        assert result["ok"] is False
        assert "not found" in result["error"]

    def test_fails_if_not_under_projects(self, tmp_path):
        (tmp_path / "Work" / "Areas").mkdir(parents=True)
        (tmp_path / "Work" / "Areas" / "Health").mkdir()
        result = server.archive_project("Work/Areas/Health", root=tmp_path)
        assert result["ok"] is False
        assert "Projects" in result["error"]

    def test_fails_if_dest_already_exists(self, tmp_path):
        make_project(tmp_path, "Work", "2026-09-Done")
        server.archive_project("Work/Projects/2026-09-Done", root=tmp_path)
        make_project(tmp_path, "Work", "2026-09-Done")  # re-create
        result = server.archive_project("Work/Projects/2026-09-Done", root=tmp_path)
        assert result["ok"] is False
        assert "already exists" in result["error"]

    def test_creates_archives_dir_if_missing(self, tmp_path):
        make_project(tmp_path, "Work", "2026-09-New")
        assert not (tmp_path / "Work" / "Archives").exists()
        server.archive_project("Work/Projects/2026-09-New", root=tmp_path)
        assert (tmp_path / "Work" / "Archives").is_dir()

    def test_result_contains_archived_to_path(self, tmp_path):
        make_project(tmp_path, "Work", "2026-09-Done")
        result = server.archive_project("Work/Projects/2026-09-Done", root=tmp_path)
        assert "archived_to" in result
        assert "Archives" in result["archived_to"]


# ---------------------------------------------------------------------------
# update_status
# ---------------------------------------------------------------------------

class TestUpdateStatus:
    @pytest.mark.parametrize("status", ["Active", "On Hold", "Waiting", "Complete"])
    def test_valid_statuses_accepted(self, tmp_path, status):
        make_project(tmp_path, "Work", "2026-09-Proj")
        result = server.update_status("Work/Projects/2026-09-Proj", status, root=tmp_path)
        assert result["ok"] is True
        assert result["status"] == status

    def test_rejects_invalid_status(self, tmp_path):
        make_project(tmp_path, "Work", "2026-09-Proj")
        result = server.update_status("Work/Projects/2026-09-Proj", "Done", root=tmp_path)
        assert result["ok"] is False
        assert "Invalid status" in result["error"]

    def test_updates_file_on_disk(self, tmp_path):
        make_project(tmp_path, "Work", "2026-09-Proj", status="Active")
        server.update_status("Work/Projects/2026-09-Proj", "On Hold", root=tmp_path)
        text = (tmp_path / "Work" / "Projects" / "2026-09-Proj" / "index.md").read_text()
        assert "**Status:** On Hold" in text

    def test_fails_if_index_not_found(self, tmp_path):
        result = server.update_status("Work/Projects/2026-09-Ghost", "Active", root=tmp_path)
        assert result["ok"] is False
        assert "not found" in result["error"]

    def test_fails_if_no_status_field_in_index(self, tmp_path):
        proj = tmp_path / "Work" / "Projects" / "2026-09-NoStatus"
        proj.mkdir(parents=True)
        (proj / "index.md").write_text("# No Status\n\nJust content.\n")
        result = server.update_status("Work/Projects/2026-09-NoStatus", "Active", root=tmp_path)
        assert result["ok"] is False
        assert "Status field" in result["error"]

    def test_old_status_is_removed(self, tmp_path):
        make_project(tmp_path, "Work", "2026-09-Proj", status="Active")
        server.update_status("Work/Projects/2026-09-Proj", "Waiting", root=tmp_path)
        text = (tmp_path / "Work" / "Projects" / "2026-09-Proj" / "index.md").read_text()
        assert "**Status:** Active" not in text
        assert "**Status:** Waiting" in text


# ---------------------------------------------------------------------------
# capture
# ---------------------------------------------------------------------------

class TestCapture:
    def test_creates_resource_file(self, tmp_path):
        result = server.capture("Work", "Resources", "Interview-Tips", "Some tips", root=tmp_path)
        assert result["ok"] is True
        assert (tmp_path / "Work" / "Resources" / "Interview-Tips.md").exists()

    def test_creates_area_file(self, tmp_path):
        result = server.capture("Personal", "Areas", "Health", "Track health", root=tmp_path)
        assert result["ok"] is True
        assert (tmp_path / "Personal" / "Areas" / "Health.md").exists()

    def test_creates_project_as_folder_with_index(self, tmp_path):
        result = server.capture("Work", "Projects", "2026-09-New-App", "# Plan", root=tmp_path)
        assert result["ok"] is True
        assert (tmp_path / "Work" / "Projects" / "2026-09-New-App" / "index.md").exists()

    def test_rejects_invalid_bucket(self, tmp_path):
        result = server.capture("Work", "Drafts", "Foo", "content", root=tmp_path)
        assert result["ok"] is False
        assert "Invalid bucket" in result["error"]

    def test_fails_if_file_already_exists(self, tmp_path):
        server.capture("Work", "Resources", "Tips", "v1", root=tmp_path)
        result = server.capture("Work", "Resources", "Tips", "v2", root=tmp_path)
        assert result["ok"] is False
        assert "already exists" in result["error"]

    def test_writes_content_to_file(self, tmp_path):
        server.capture("Work", "Resources", "Notes", "hello world", root=tmp_path)
        assert (tmp_path / "Work" / "Resources" / "Notes.md").read_text() == "hello world"

    def test_sanitizes_spaces_in_title(self, tmp_path):
        result = server.capture("Work", "Resources", "My Notes", "content", root=tmp_path)
        assert result["ok"] is True
        assert (tmp_path / "Work" / "Resources" / "My-Notes.md").exists()

    def test_archives_bucket_works(self, tmp_path):
        result = server.capture("Work", "Archives", "Old-Note", "content", root=tmp_path)
        assert result["ok"] is True

    def test_path_in_result_is_relative(self, tmp_path):
        result = server.capture("Work", "Resources", "X", "c", root=tmp_path)
        assert not Path(result["path"]).is_absolute()

    def test_project_capture_auto_dates_name(self, tmp_path):
        result = server.capture("Work", "Projects", "Undated", "content", root=tmp_path)
        assert result["ok"] is True
        assert date.today().strftime("%Y-%m") in result["path"]


# ---------------------------------------------------------------------------
# MCP tool wrappers (smoke tests — verify delegation, not business logic)
# ---------------------------------------------------------------------------

class TestMCPToolWrappers:
    """Call the @mcp.tool-decorated wrappers directly to confirm they delegate correctly."""

    def test_tool_create_project_delegates(self, tmp_path, monkeypatch):
        monkeypatch.setattr(server, "REPO_ROOT", tmp_path)
        result = server.tool_create_project("Work", "2026-09-MCP", "2026-12-31")
        assert result["ok"] is True

    def test_tool_list_projects_delegates(self, tmp_path, monkeypatch):
        monkeypatch.setattr(server, "REPO_ROOT", tmp_path)
        make_project(tmp_path, "Work", "2026-09-A")
        result = server.tool_list_projects()
        assert isinstance(result, list)

    def test_tool_list_projects_with_domain(self, tmp_path, monkeypatch):
        monkeypatch.setattr(server, "REPO_ROOT", tmp_path)
        make_project(tmp_path, "Work", "2026-09-A")
        result = server.tool_list_projects(domain="Work")
        assert len(result) == 1

    def test_tool_weekly_review_delegates(self, tmp_path, monkeypatch):
        monkeypatch.setattr(server, "REPO_ROOT", tmp_path)
        result = server.tool_weekly_review()
        assert isinstance(result, list)

    def test_tool_archive_project_delegates(self, tmp_path, monkeypatch):
        monkeypatch.setattr(server, "REPO_ROOT", tmp_path)
        make_project(tmp_path, "Work", "2026-09-Done")
        result = server.tool_archive_project("Work/Projects/2026-09-Done")
        assert result["ok"] is True

    def test_tool_update_status_delegates(self, tmp_path, monkeypatch):
        monkeypatch.setattr(server, "REPO_ROOT", tmp_path)
        make_project(tmp_path, "Work", "2026-09-Proj")
        result = server.tool_update_status("Work/Projects/2026-09-Proj", "Complete")
        assert result["ok"] is True

    def test_tool_capture_delegates(self, tmp_path, monkeypatch):
        monkeypatch.setattr(server, "REPO_ROOT", tmp_path)
        result = server.tool_capture("Work", "Resources", "Test", "content")
        assert result["ok"] is True
