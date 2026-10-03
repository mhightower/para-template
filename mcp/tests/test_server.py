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


def make_project_without_deadline(root: Path, domain: str, name: str, status: str = "Active") -> Path:
    proj = root / domain / "Projects" / name
    proj.mkdir(parents=True)
    (proj / "index.md").write_text(
        f"# {name}\n\n"
        f"**Status:** {status}\n"
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

    def test_skips_underscore_dirs(self, tmp_path):
        make_project(tmp_path, "_template-domain", "2026-09-A")
        assert server.list_projects(root=tmp_path) == []

    def test_includes_deadline_from_index(self, tmp_path):
        make_project(tmp_path, "Work", "2026-09-A", deadline="2027-06-01")
        result = server.list_projects(root=tmp_path)
        assert result[0]["deadline"] == "2027-06-01"

    def test_includes_deadline_relative(self, tmp_path):
        make_project(tmp_path, "Work", "2026-09-A", deadline="2027-06-01")
        result = server.list_projects(root=tmp_path)
        assert "deadline_relative" in result[0]
        assert isinstance(result[0]["deadline_relative"], str)

    def test_skips_domain_dirs_with_no_projects_subdir(self, tmp_path):
        (tmp_path / "Work").mkdir()
        assert server.list_projects(root=tmp_path) == []

    def test_skips_loose_files_in_projects_dir(self, tmp_path):
        (tmp_path / "Work" / "Projects").mkdir(parents=True)
        (tmp_path / "Work" / "Projects" / "README.md").write_text("ignore me")
        assert server.list_projects(root=tmp_path) == []


# ---------------------------------------------------------------------------
# _format_deadline_relative
# ---------------------------------------------------------------------------

class TestDeadlineRelative:
    def _fmt(self, deadline_str, today_str):
        today = date.fromisoformat(today_str)
        return server._format_deadline_relative(deadline_str, today=today)

    def test_empty_deadline_returns_empty(self):
        assert self._fmt("", "2026-09-28") == ""

    def test_tbd_returns_empty(self):
        assert self._fmt("TBD", "2026-09-28") == ""

    def test_invalid_date_returns_empty(self):
        assert self._fmt("not-a-date", "2026-09-28") == ""

    def test_today(self):
        assert self._fmt("2026-09-28", "2026-09-28") == "today"

    def test_tomorrow(self):
        assert self._fmt("2026-09-29", "2026-09-28") == "1 day"

    def test_days(self):
        assert self._fmt("2026-10-04", "2026-09-28") == "6 days"

    def test_one_week(self):
        assert self._fmt("2026-10-12", "2026-09-28") == "2 weeks"

    def test_weeks(self):
        assert self._fmt("2026-11-09", "2026-09-28") == "6 weeks"

    def test_months(self):
        assert self._fmt("2027-03-28", "2026-09-28") == "6 months"

    def test_overdue_one_day(self):
        assert self._fmt("2026-09-27", "2026-09-28") == "overdue 1 day"

    def test_overdue_days(self):
        assert self._fmt("2026-09-21", "2026-09-28") == "overdue 1 week"

    def test_overdue_weeks(self):
        assert self._fmt("2026-08-28", "2026-09-28") == "overdue 4 weeks"

    def test_overdue_months(self):
        assert self._fmt("2026-03-28", "2026-09-28") == "overdue 6 months"


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
# add_file_to_project
# ---------------------------------------------------------------------------

class TestAddFileToProject:
    def test_creates_file_in_project(self, tmp_path):
        make_project(tmp_path, "Personal", "2026-09-Puppies")
        result = server.add_file_to_project("Personal/Projects/2026-09-Puppies", "Mic", "# Mic", root=tmp_path)
        assert result["ok"] is True
        assert (tmp_path / "Personal" / "Projects" / "2026-09-Puppies" / "Mic.md").exists()

    def test_updates_index_with_files_section(self, tmp_path):
        make_project(tmp_path, "Personal", "2026-09-Puppies")
        server.add_file_to_project("Personal/Projects/2026-09-Puppies", "Mic", "# Mic", root=tmp_path)
        index = (tmp_path / "Personal" / "Projects" / "2026-09-Puppies" / "index.md").read_text()
        assert "## Files" in index
        assert "- [Mic](Mic.md)" in index

    def test_index_does_not_list_itself(self, tmp_path):
        make_project(tmp_path, "Personal", "2026-09-Puppies")
        server.add_file_to_project("Personal/Projects/2026-09-Puppies", "Mic", "# Mic", root=tmp_path)
        index = (tmp_path / "Personal" / "Projects" / "2026-09-Puppies" / "index.md").read_text()
        files_section = index.split("## Files")[1] if "## Files" in index else ""
        assert "index.md" not in files_section

    def test_multiple_files_listed_sorted(self, tmp_path):
        make_project(tmp_path, "Personal", "2026-09-Puppies")
        server.add_file_to_project("Personal/Projects/2026-09-Puppies", "Zoe", "# Zoe", root=tmp_path)
        server.add_file_to_project("Personal/Projects/2026-09-Puppies", "Abel", "# Abel", root=tmp_path)
        index = (tmp_path / "Personal" / "Projects" / "2026-09-Puppies" / "index.md").read_text()
        assert index.index("Abel") < index.index("Zoe")

    def test_second_add_updates_existing_files_section(self, tmp_path):
        make_project(tmp_path, "Personal", "2026-09-Puppies")
        server.add_file_to_project("Personal/Projects/2026-09-Puppies", "Mic", "# Mic", root=tmp_path)
        server.add_file_to_project("Personal/Projects/2026-09-Puppies", "Bell", "# Bell", root=tmp_path)
        index = (tmp_path / "Personal" / "Projects" / "2026-09-Puppies" / "index.md").read_text()
        assert index.count("## Files") == 1
        assert "- [Bell](Bell.md)" in index
        assert "- [Mic](Mic.md)" in index

    def test_fails_if_project_not_found(self, tmp_path):
        result = server.add_file_to_project("Personal/Projects/2026-09-Ghost", "Note", "content", root=tmp_path)
        assert result["ok"] is False
        assert "not found" in result["error"]

    def test_fails_if_file_already_exists(self, tmp_path):
        make_project(tmp_path, "Personal", "2026-09-Puppies")
        server.add_file_to_project("Personal/Projects/2026-09-Puppies", "Mic", "# Mic", root=tmp_path)
        result = server.add_file_to_project("Personal/Projects/2026-09-Puppies", "Mic", "# Mic again", root=tmp_path)
        assert result["ok"] is False
        assert "already exists" in result["error"]

    def test_sanitizes_title_spaces(self, tmp_path):
        make_project(tmp_path, "Personal", "2026-09-Puppies")
        result = server.add_file_to_project("Personal/Projects/2026-09-Puppies", "My Dog", "# My Dog", root=tmp_path)
        assert result["ok"] is True
        assert (tmp_path / "Personal" / "Projects" / "2026-09-Puppies" / "My-Dog.md").exists()

    def test_path_in_result_is_relative(self, tmp_path):
        make_project(tmp_path, "Personal", "2026-09-Puppies")
        result = server.add_file_to_project("Personal/Projects/2026-09-Puppies", "Note", "content", root=tmp_path)
        assert not Path(result["path"]).is_absolute()

    def test_preserves_existing_index_content(self, tmp_path):
        make_project(tmp_path, "Personal", "2026-09-Puppies", deadline="2027-01-01")
        server.add_file_to_project("Personal/Projects/2026-09-Puppies", "Mic", "# Mic", root=tmp_path)
        index = (tmp_path / "Personal" / "Projects" / "2026-09-Puppies" / "index.md").read_text()
        assert "**Deadline:** 2027-01-01" in index
        assert "**Status:** Active" in index

    def test_update_index_files_empty_removes_section(self, tmp_path):
        proj = make_project(tmp_path, "Personal", "2026-09-Empty")
        server._update_index_files(proj)
        index = (proj / "index.md").read_text()
        assert "## Files" not in index


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

    def test_tool_add_file_to_project_delegates(self, tmp_path, monkeypatch):
        monkeypatch.setattr(server, "REPO_ROOT", tmp_path)
        make_project(tmp_path, "Personal", "2026-09-Test")
        result = server.tool_add_file_to_project("Personal/Projects/2026-09-Test", "Note", "content")
        assert result["ok"] is True


class TestSystemPrompt:
    def test_contains_today(self, tmp_path):
        prompt = server._build_system_prompt(root=tmp_path)
        assert date.today().isoformat() in prompt

    def test_lists_domains(self, tmp_path):
        (tmp_path / "Work").mkdir()
        (tmp_path / "Personal").mkdir()
        prompt = server._build_system_prompt(root=tmp_path)
        assert "Work" in prompt
        assert "Personal" in prompt

    def test_no_domains_shows_placeholder(self, tmp_path):
        prompt = server._build_system_prompt(root=tmp_path)
        assert "none configured yet" in prompt

    def test_excludes_hidden_and_underscore_dirs(self, tmp_path):
        (tmp_path / ".git").mkdir()
        (tmp_path / "_template-domain").mkdir()
        (tmp_path / "Work").mkdir()
        prompt = server._build_system_prompt(root=tmp_path)
        # domain list line is "Active domains: ..." — check exclusions there
        domain_line = next(l for l in prompt.splitlines() if "Active domains:" in l)
        assert ".git" not in domain_line
        assert "_template-domain" not in domain_line
        assert "Work" in domain_line

    def test_contains_key_sections(self, tmp_path):
        prompt = server._build_system_prompt(root=tmp_path)
        assert "## MCP Tools" in prompt
        assert "## Capture Protocol" in prompt
        assert "## Weekly Review Protocol" in prompt

    def test_prompt_wrapper_uses_repo_root(self, tmp_path, monkeypatch):
        monkeypatch.setattr(server, "REPO_ROOT", tmp_path)
        result = server.tool_para_system_prompt()
        assert isinstance(result, str)
        assert "PARA Life OS" in result


# ---------------------------------------------------------------------------
# _validate_url
# ---------------------------------------------------------------------------

class TestValidateUrl:
    def test_https_valid(self):
        assert server._validate_url("https://example.com") is True

    def test_http_valid(self):
        assert server._validate_url("http://example.com") is True

    def test_missing_scheme_invalid(self):
        assert server._validate_url("example.com") is False

    def test_empty_invalid(self):
        assert server._validate_url("") is False

    def test_ftp_invalid(self):
        assert server._validate_url("ftp://files.example.com") is False


# ---------------------------------------------------------------------------
# _parse_resource
# ---------------------------------------------------------------------------

class TestParseResource:
    def test_no_links_section(self, tmp_path):
        f = tmp_path / "note.md"
        f.write_text("# Note\n\nsome content\n")
        assert server._parse_resource(f) == {"links": []}

    def test_single_link(self, tmp_path):
        f = tmp_path / "note.md"
        f.write_text("# Note\n\n## Links\n\n- [MDN](https://developer.mozilla.org)\n")
        assert server._parse_resource(f) == {
            "links": [{"label": "MDN", "url": "https://developer.mozilla.org"}]
        }

    def test_multiple_links(self, tmp_path):
        f = tmp_path / "note.md"
        f.write_text(
            "# Note\n\n## Links\n\n"
            "- [MDN](https://developer.mozilla.org)\n"
            "- [TS](https://typescriptlang.org)\n"
        )
        result = server._parse_resource(f)
        assert len(result["links"]) == 2
        assert result["links"][1]["label"] == "TS"

    def test_link_without_label_uses_url(self, tmp_path):
        f = tmp_path / "note.md"
        f.write_text("# Note\n\n## Links\n\n- [](https://example.com)\n")
        result = server._parse_resource(f)
        assert result["links"][0]["label"] == "https://example.com"


# ---------------------------------------------------------------------------
# _append_links_section
# ---------------------------------------------------------------------------

class TestAppendLinksSection:
    def test_creates_links_section(self, tmp_path):
        f = tmp_path / "note.md"
        f.write_text("# Note\n\nsome content\n")
        server._append_links_section(f, "https://example.com", "Example")
        text = f.read_text()
        assert "## Links" in text
        assert "- [Example](https://example.com)" in text

    def test_appends_to_existing_section(self, tmp_path):
        f = tmp_path / "note.md"
        f.write_text("# Note\n\n## Links\n\n- [First](https://first.com)\n")
        server._append_links_section(f, "https://second.com", "Second")
        text = f.read_text()
        assert "- [First](https://first.com)" in text
        assert "- [Second](https://second.com)" in text

    def test_empty_label_uses_url(self, tmp_path):
        f = tmp_path / "note.md"
        f.write_text("# Note\n")
        server._append_links_section(f, "https://example.com", "")
        assert "- [https://example.com](https://example.com)" in f.read_text()


# ---------------------------------------------------------------------------
# capture with URL
# ---------------------------------------------------------------------------

class TestCaptureWithUrl:
    def test_capture_resource_with_url(self, tmp_path):
        result = server.capture("Work", "Resources", "Python-Docs",
                                "Reference material.",
                                url="https://docs.python.org", url_label="Python Docs",
                                root=tmp_path)
        assert result["ok"] is True
        text = (tmp_path / "Work" / "Resources" / "Python-Docs.md").read_text()
        assert "## Links" in text
        assert "- [Python Docs](https://docs.python.org)" in text

    def test_capture_without_url_unchanged(self, tmp_path):
        result = server.capture("Work", "Resources", "Notes", "content", root=tmp_path)
        assert result["ok"] is True
        text = (tmp_path / "Work" / "Resources" / "Notes.md").read_text()
        assert "## Links" not in text

    def test_capture_invalid_url_rejected(self, tmp_path):
        result = server.capture("Work", "Resources", "Bad",
                                "content", url="not-a-url", root=tmp_path)
        assert result["ok"] is False
        assert "URL" in result["error"]

    def test_capture_url_label_defaults_to_url(self, tmp_path):
        server.capture("Work", "Resources", "No-Label", "content",
                       url="https://example.com", root=tmp_path)
        text = (tmp_path / "Work" / "Resources" / "No-Label.md").read_text()
        assert "- [https://example.com](https://example.com)" in text


# ---------------------------------------------------------------------------
# add_link_to_resource
# ---------------------------------------------------------------------------

class TestAddLinkToResource:
    def test_adds_link_to_file_resource(self, tmp_path):
        (tmp_path / "Work" / "Resources").mkdir(parents=True)
        (tmp_path / "Work" / "Resources" / "Notes.md").write_text("# Notes\n")
        result = server.add_link_to_resource(
            "Work/Resources/Notes", "https://example.com", "Example", root=tmp_path
        )
        assert result["ok"] is True
        text = (tmp_path / "Work" / "Resources" / "Notes.md").read_text()
        assert "- [Example](https://example.com)" in text

    def test_adds_link_to_folder_resource(self, tmp_path):
        folder = tmp_path / "Work" / "Resources" / "Interview-Prep"
        folder.mkdir(parents=True)
        (folder / "index.md").write_text("# Interview Prep\n")
        result = server.add_link_to_resource(
            "Work/Resources/Interview-Prep", "https://example.com", "Guide", root=tmp_path
        )
        assert result["ok"] is True
        assert "- [Guide](https://example.com)" in (folder / "index.md").read_text()

    def test_path_with_md_extension(self, tmp_path):
        (tmp_path / "Work" / "Resources").mkdir(parents=True)
        (tmp_path / "Work" / "Resources" / "Notes.md").write_text("# Notes\n")
        result = server.add_link_to_resource(
            "Work/Resources/Notes.md", "https://example.com", "Ex", root=tmp_path
        )
        assert result["ok"] is True

    def test_invalid_url_rejected(self, tmp_path):
        (tmp_path / "Work" / "Resources").mkdir(parents=True)
        (tmp_path / "Work" / "Resources" / "Notes.md").write_text("# Notes\n")
        result = server.add_link_to_resource(
            "Work/Resources/Notes", "bad-url", "Bad", root=tmp_path
        )
        assert result["ok"] is False
        assert "URL" in result["error"]

    def test_resource_not_found(self, tmp_path):
        result = server.add_link_to_resource(
            "Work/Resources/Missing", "https://example.com", "X", root=tmp_path
        )
        assert result["ok"] is False
        assert "not found" in result["error"]

    def test_duplicate_url_rejected(self, tmp_path):
        (tmp_path / "Work" / "Resources").mkdir(parents=True)
        (tmp_path / "Work" / "Resources" / "Notes.md").write_text(
            "# Notes\n\n## Links\n\n- [X](https://example.com)\n"
        )
        result = server.add_link_to_resource(
            "Work/Resources/Notes", "https://example.com", "Dup", root=tmp_path
        )
        assert result["ok"] is False
        assert "already" in result["error"]


# ---------------------------------------------------------------------------
# list_resources
# ---------------------------------------------------------------------------

class TestListResources:
    def _make_resource_file(self, root, domain, name, content="# Resource\n"):
        d = root / domain / "Resources"
        d.mkdir(parents=True, exist_ok=True)
        (d / f"{name}.md").write_text(content)

    def _make_resource_folder(self, root, domain, name, content="# Resource\n"):
        d = root / domain / "Resources" / name
        d.mkdir(parents=True, exist_ok=True)
        (d / "index.md").write_text(content)

    def test_lists_file_resources(self, tmp_path):
        self._make_resource_file(tmp_path, "Work", "Python-Docs")
        result = server.list_resources(root=tmp_path)
        assert len(result) == 1
        assert result[0]["name"] == "Python-Docs"

    def test_lists_folder_resources(self, tmp_path):
        self._make_resource_folder(tmp_path, "Work", "Interview-Prep")
        result = server.list_resources(root=tmp_path)
        assert len(result) == 1
        assert result[0]["name"] == "Interview-Prep"

    def test_filters_by_domain(self, tmp_path):
        self._make_resource_file(tmp_path, "Work", "Work-Note")
        self._make_resource_file(tmp_path, "Personal", "Personal-Note")
        result = server.list_resources(domain="Work", root=tmp_path)
        assert len(result) == 1
        assert result[0]["domain"] == "Work"

    def test_empty_when_no_resources(self, tmp_path):
        assert server.list_resources(root=tmp_path) == []

    def test_with_links_false_omits_links(self, tmp_path):
        self._make_resource_file(tmp_path, "Work", "Note",
                                 "# Note\n\n## Links\n\n- [X](https://x.com)\n")
        result = server.list_resources(root=tmp_path)
        assert "links" not in result[0]

    def test_with_links_true_includes_links(self, tmp_path):
        self._make_resource_file(tmp_path, "Work", "Note",
                                 "# Note\n\n## Links\n\n- [X](https://x.com)\n")
        result = server.list_resources(with_links=True, root=tmp_path)
        assert result[0]["links"] == [{"label": "X", "url": "https://x.com"}]

    def test_skips_hidden_and_underscore_domains(self, tmp_path):
        self._make_resource_file(tmp_path, ".hidden", "Note")
        self._make_resource_file(tmp_path, "_template-domain", "Note")
        assert server.list_resources(root=tmp_path) == []


# ---------------------------------------------------------------------------
# MCP tool wrapper additions
# ---------------------------------------------------------------------------

class TestMCPResourceToolWrappers:
    def test_tool_add_link_to_resource_delegates(self, tmp_path, monkeypatch):
        monkeypatch.setattr(server, "REPO_ROOT", tmp_path)
        (tmp_path / "Work" / "Resources").mkdir(parents=True)
        (tmp_path / "Work" / "Resources" / "Note.md").write_text("# Note\n")
        result = server.tool_add_link_to_resource(
            "Work/Resources/Note", "https://example.com", "Example"
        )
        assert result["ok"] is True

    def test_tool_list_resources_delegates(self, tmp_path, monkeypatch):
        monkeypatch.setattr(server, "REPO_ROOT", tmp_path)
        result = server.tool_list_resources()
        assert isinstance(result, list)

    def test_skips_domain_with_no_resources_dir(self, tmp_path):
        (tmp_path / "Work").mkdir()
        assert server.list_resources(root=tmp_path) == []

    def test_with_links_true_folder_resource(self, tmp_path):
        folder = tmp_path / "Work" / "Resources" / "Interview-Prep"
        folder.mkdir(parents=True)
        (folder / "index.md").write_text(
            "# Prep\n\n## Links\n\n- [Guide](https://guide.com)\n"
        )
        result = server.list_resources(with_links=True, root=tmp_path)
        assert result[0]["links"] == [{"label": "Guide", "url": "https://guide.com"}]


# ---------------------------------------------------------------------------
# capture_to_inbox
# ---------------------------------------------------------------------------

class TestCaptureToInbox:
    def test_creates_inbox_dir(self, tmp_path):
        server.capture_to_inbox("some note", root=tmp_path)
        assert (tmp_path / "Inbox").is_dir()

    def test_returns_file_path(self, tmp_path):
        result = server.capture_to_inbox("some note", root=tmp_path)
        assert result["ok"] is True
        assert "path" in result
        assert result["path"].startswith("Inbox/")

    def test_file_is_timestamped_markdown(self, tmp_path):
        result = server.capture_to_inbox("hello", root=tmp_path)
        p = Path(result["path"])
        assert p.suffix == ".md"
        # filename like YYYY-MM-DD-HHMMSS.md
        import re
        assert re.match(r"^\d{4}-\d{2}-\d{2}-\d{6}\.md$", p.name)

    def test_file_contains_content(self, tmp_path):
        result = server.capture_to_inbox("my note content", root=tmp_path)
        text = (tmp_path / result["path"]).read_text()
        assert "my note content" in text

    def test_no_tags_no_frontmatter(self, tmp_path):
        result = server.capture_to_inbox("just content", root=tmp_path)
        text = (tmp_path / result["path"]).read_text()
        assert "tags:" not in text

    def test_tags_appear_in_frontmatter(self, tmp_path):
        result = server.capture_to_inbox("tagged", tags=["work", "idea"], root=tmp_path)
        text = (tmp_path / result["path"]).read_text()
        assert "tags:" in text
        assert "work" in text
        assert "idea" in text

    def test_frontmatter_is_valid_yaml_block(self, tmp_path):
        result = server.capture_to_inbox("content", tags=["a"], root=tmp_path)
        text = (tmp_path / result["path"]).read_text()
        assert text.startswith("---\n")
        assert "---\n" in text[4:]  # closing delimiter

    def test_multiple_captures_create_distinct_files(self, tmp_path, monkeypatch):
        import server as srv
        from datetime import datetime
        times = [datetime(2026, 10, 1, 12, 0, 0), datetime(2026, 10, 1, 12, 0, 1)]
        calls = iter(times)
        monkeypatch.setattr(srv, "_now", lambda: next(calls))
        r1 = server.capture_to_inbox("note 1", root=tmp_path)
        r2 = server.capture_to_inbox("note 2", root=tmp_path)
        assert r1["path"] != r2["path"]

    def test_path_is_relative(self, tmp_path):
        result = server.capture_to_inbox("x", root=tmp_path)
        assert not Path(result["path"]).is_absolute()

    def test_tool_wrapper_delegates(self, tmp_path, monkeypatch):
        monkeypatch.setattr(server, "REPO_ROOT", tmp_path)
        result = server.tool_capture_to_inbox("hi")
        assert result["ok"] is True


# ---------------------------------------------------------------------------
# suggest_triage
# ---------------------------------------------------------------------------

class TestSuggestTriage:
    def _make_inbox_file(self, root: Path, content: str, tags=None) -> str:
        result = server.capture_to_inbox(content, tags=tags or [], root=root)
        return result["path"]

    def test_returns_dict_with_suggestions(self, tmp_path):
        path = self._make_inbox_file(tmp_path, "something")
        result = server.suggest_triage(path, root=tmp_path)
        assert isinstance(result, dict)
        assert result["ok"] is True
        assert "suggestions" in result

    def test_empty_para_structure_returns_empty_suggestions(self, tmp_path):
        path = self._make_inbox_file(tmp_path, "random note")
        result = server.suggest_triage(path, root=tmp_path)
        assert result["suggestions"] == []

    def test_keyword_match_on_project_name(self, tmp_path):
        make_project(tmp_path, "Work", "2026-10-Interview-Prep")
        path = self._make_inbox_file(tmp_path, "Need to prepare for interview next week")
        result = server.suggest_triage(path, root=tmp_path)
        suggestions = result["suggestions"]
        assert len(suggestions) >= 1
        paths = [s["destination"] for s in suggestions]
        assert any("Interview-Prep" in p for p in paths)

    def test_suggestion_has_required_fields(self, tmp_path):
        make_project(tmp_path, "Work", "2026-10-Interview-Prep")
        path = self._make_inbox_file(tmp_path, "interview question notes")
        result = server.suggest_triage(path, root=tmp_path)
        suggestions = result["suggestions"]
        if suggestions:
            s = suggestions[0]
            assert "destination" in s
            assert "reason" in s
            assert "confidence" in s
            assert s["confidence"] in ("high", "medium", "low")

    def test_tag_match_on_area_name(self, tmp_path):
        (tmp_path / "Personal" / "Areas").mkdir(parents=True)
        (tmp_path / "Personal" / "Areas" / "Health.md").write_text("# Health\n")
        path = self._make_inbox_file(tmp_path, "went for a run", tags=["health"])
        result = server.suggest_triage(path, root=tmp_path)
        assert any("Health" in s["destination"] for s in result["suggestions"])

    def test_no_match_returns_empty_suggestions(self, tmp_path):
        make_project(tmp_path, "Work", "2026-10-Coding-Project")
        path = self._make_inbox_file(tmp_path, "completely unrelated zqxwvutsrp gibberish")
        result = server.suggest_triage(path, root=tmp_path)
        assert result["suggestions"] == []

    def test_missing_inbox_file_returns_error(self, tmp_path):
        result = server.suggest_triage("Inbox/nonexistent.md", root=tmp_path)
        assert isinstance(result, dict)
        assert result["ok"] is False

    def test_confidence_high_for_exact_tag_match(self, tmp_path):
        make_project(tmp_path, "Work", "2026-10-Health")
        path = self._make_inbox_file(tmp_path, "some note", tags=["health"])
        result = server.suggest_triage(path, root=tmp_path)
        tag_matches = [s for s in result["suggestions"] if "tag" in s["reason"].lower()]
        if tag_matches:
            assert tag_matches[0]["confidence"] in ("high", "medium")

    def test_tool_wrapper_delegates(self, tmp_path, monkeypatch):
        monkeypatch.setattr(server, "REPO_ROOT", tmp_path)
        path = self._make_inbox_file(tmp_path, "test")
        result = server.tool_suggest_triage(path)
        assert isinstance(result, dict)
        assert "suggestions" in result
# Due-dates (issue #26)
# ---------------------------------------------------------------------------

class TestDueDates:
    def test_set_due_updates_deadline_in_frontmatter(self, tmp_path):
        make_project(tmp_path, "Work", "2026-09-A", deadline="2026-12-31")
        result = server.set_due("Work/Projects/2026-09-A", "2027-03-01", root=tmp_path)
        assert result["ok"] is True
        text = (tmp_path / "Work" / "Projects" / "2026-09-A" / "index.md").read_text()
        assert "**Deadline:** 2027-03-01" in text

    def test_set_due_rejects_invalid_date(self, tmp_path):
        make_project(tmp_path, "Work", "2026-09-A")
        result = server.set_due("Work/Projects/2026-09-A", "not-a-date", root=tmp_path)
        assert result["ok"] is False

    def test_set_due_project_not_found(self, tmp_path):
        result = server.set_due("Work/Projects/nonexistent", "2027-01-01", root=tmp_path)
        assert result["ok"] is False

    def test_unset_due_clears_deadline_field(self, tmp_path):
        make_project(tmp_path, "Work", "2026-09-A", deadline="2027-01-15")
        result = server.unset_due("Work/Projects/2026-09-A", root=tmp_path)
        assert result["ok"] is True
        text = (tmp_path / "Work" / "Projects" / "2026-09-A" / "index.md").read_text()
        assert "**Deadline:**" in text
        assert "**Goal:** TBD" in text
        assert "**Next Action:** TBD" in text
        assert "**Status:** Active" in text
        parsed = server._parse_index(tmp_path / "Work" / "Projects" / "2026-09-A" / "index.md")
        assert parsed["deadline"] == ""

    def test_set_due_and_unset_due_keep_adjacent_frontmatter_intact(self, tmp_path):
        path = make_project(tmp_path, "Work", "2026-09-A", deadline="2027-01-15") / "index.md"
        original = path.read_text()
        set_result = server.set_due("Work/Projects/2026-09-A", "2027-02-01", root=tmp_path)
        unset_result = server.unset_due("Work/Projects/2026-09-A", root=tmp_path)
        assert set_result["ok"] is True
        assert unset_result["ok"] is True
        text = path.read_text()
        assert "**Status:** Active" in text
        assert "**Goal:** TBD" in text
        assert "**Next Action:** TBD" in text
        assert text.count("**Deadline:**") == 1
        assert text != original

    def test_unset_due_project_not_found(self, tmp_path):
        result = server.unset_due("Work/Projects/ghost", root=tmp_path)
        assert result["ok"] is False

    def test_list_due_returns_projects_sorted_ascending(self, tmp_path):
        make_project(tmp_path, "Work", "2026-09-A", deadline="2027-06-01")
        make_project(tmp_path, "Work", "2026-09-B", deadline="2027-01-15")
        make_project(tmp_path, "Work", "2026-09-C", deadline="2027-03-20")
        results = server.list_due(root=tmp_path)
        dates = [r["deadline"] for r in results]
        assert dates == sorted(dates)

    def test_list_due_excludes_projects_without_deadline(self, tmp_path):
        make_project(tmp_path, "Work", "2026-09-NoDeadline", deadline="")
        make_project(tmp_path, "Work", "2026-09-WithDeadline", deadline="2027-01-01")
        results = server.list_due(root=tmp_path)
        names = [r["name"] for r in results]
        assert "2026-09-WithDeadline" in names
        assert "2026-09-NoDeadline" not in names

    def test_get_upcoming_deadlines_returns_within_window(self, tmp_path):
        from datetime import date, timedelta
        today = date.today()
        soon = (today + timedelta(days=5)).isoformat()
        far = (today + timedelta(days=30)).isoformat()
        make_project(tmp_path, "Work", "2026-09-Soon", deadline=soon)
        make_project(tmp_path, "Work", "2026-09-Far", deadline=far)
        results = server.get_upcoming_deadlines(days=7, root=tmp_path)
        names = [r["name"] for r in results]
        assert "2026-09-Soon" in names
        assert "2026-09-Far" not in names

    def test_get_upcoming_deadlines_skips_invalid_deadline_formats(self, tmp_path):
        # Projects with empty or malformed deadlines should be skipped gracefully
        make_project(tmp_path, "Work", "2026-09-Bad", deadline="not-a-date")
        results = server.get_upcoming_deadlines(days=365, root=tmp_path)
        names = [r["name"] for r in results]
        assert "2026-09-Bad" not in names

    def test_set_due_rejects_project_without_deadline_field(self, tmp_path):
        make_project_without_deadline(tmp_path, "Work", "2026-09-NoDeadline")
        result = server.set_due("Work/Projects/2026-09-NoDeadline", "2027-01-01", root=tmp_path)
        assert result["ok"] is False
        assert "No Deadline field" in result["error"]

    def test_unset_due_rejects_project_without_deadline_field(self, tmp_path):
        make_project_without_deadline(tmp_path, "Work", "2026-09-NoDeadline")
        result = server.unset_due("Work/Projects/2026-09-NoDeadline", root=tmp_path)
        assert result["ok"] is False
        assert "No Deadline field" in result["error"]


# ---------------------------------------------------------------------------
# archive_item / revive_item (issue #18: One-command archive and revive)
# ---------------------------------------------------------------------------

class TestArchiveItem:
    def test_archives_project_by_name(self, tmp_path):
        make_project(tmp_path, "Work", "2026-09-Target")
        result = server.archive_item("2026-09-Target", root=tmp_path)
        assert result["ok"] is True
        assert (tmp_path / "Work" / "Archives" / "2026-09-Target").exists()

    def test_result_includes_source_and_dest(self, tmp_path):
        make_project(tmp_path, "Work", "2026-09-Target")
        result = server.archive_item("2026-09-Target", root=tmp_path)
        assert "source" in result
        assert "destination" in result

    def test_archives_by_full_path(self, tmp_path):
        make_project(tmp_path, "Work", "2026-09-Full")
        result = server.archive_item("Work/Projects/2026-09-Full", root=tmp_path)
        assert result["ok"] is True

    def test_disambiguation_on_multiple_matches(self, tmp_path):
        make_project(tmp_path, "Work", "2026-09-Same")
        make_project(tmp_path, "Personal", "2026-09-Same")
        result = server.archive_item("2026-09-Same", root=tmp_path)
        assert result.get("ambiguous") is True
        assert "matches" in result
        assert len(result["matches"]) == 2

    def test_error_on_no_match(self, tmp_path):
        result = server.archive_item("NoSuchItem", root=tmp_path)
        assert result["ok"] is False
        assert "not found" in result["error"].lower()

    def test_archives_area_file(self, tmp_path):
        (tmp_path / "Work" / "Areas").mkdir(parents=True)
        (tmp_path / "Work" / "Areas" / "Health.md").write_text("# Health\n")
        result = server.archive_item("Health", root=tmp_path)
        assert result["ok"] is True
        assert (tmp_path / "Work" / "Archives" / "Health.md").exists()

    def test_writes_audit_log(self, tmp_path):
        make_project(tmp_path, "Work", "2026-09-Audited")
        server.archive_item("2026-09-Audited", root=tmp_path)
        log = (tmp_path / ".para-audit.log")
        assert log.exists()
        text = log.read_text()
        assert "archive" in text.lower()
        assert "2026-09-Audited" in text

    def test_skips_archives_bucket_in_search(self, tmp_path):
        arch = tmp_path / "Work" / "Archives" / "2026-09-AlreadyArchived"
        arch.mkdir(parents=True)
        (arch / "index.md").write_text("# Old\n")
        result = server.archive_item("2026-09-AlreadyArchived", root=tmp_path)
        assert result["ok"] is False

    def test_tool_wrapper_delegates(self, tmp_path, monkeypatch):
        monkeypatch.setattr(server, "REPO_ROOT", tmp_path)
        make_project(tmp_path, "Work", "2026-09-T")
        result = server.tool_archive_item("2026-09-T")
        assert result["ok"] is True


class TestReviveItem:
    def test_revives_project_from_archives(self, tmp_path):
        make_project(tmp_path, "Work", "2026-09-Revive")
        server.archive_item("2026-09-Revive", root=tmp_path)
        result = server.revive_item("2026-09-Revive", root=tmp_path)
        assert result["ok"] is True
        assert (tmp_path / "Work" / "Projects" / "2026-09-Revive").exists()

    def test_result_includes_source_and_destination(self, tmp_path):
        make_project(tmp_path, "Work", "2026-09-R2")
        server.archive_item("2026-09-R2", root=tmp_path)
        result = server.revive_item("2026-09-R2", root=tmp_path)
        assert "source" in result
        assert "destination" in result

    def test_error_on_no_archived_match(self, tmp_path):
        result = server.revive_item("NoSuchItem", root=tmp_path)
        assert result["ok"] is False
        assert "not found" in result["error"].lower()

    def test_disambiguation_on_multiple_archived_matches(self, tmp_path):
        for domain in ("Work", "Personal"):
            arch = tmp_path / domain / "Archives" / "2026-09-Same"
            arch.mkdir(parents=True)
            (arch / "index.md").write_text(
                f"# Same\n\n**Status:** Active\n**Deadline:** 2026-12-31\n"
                f"**Goal:** TBD\n**Next Action:** TBD\n"
                f"**Original Bucket:** Projects\n"
            )
        result = server.revive_item("2026-09-Same", root=tmp_path)
        assert result.get("ambiguous") is True
        assert len(result["matches"]) == 2

    def test_writes_audit_log_on_revive(self, tmp_path):
        make_project(tmp_path, "Work", "2026-09-AuditRevive")
        server.archive_item("2026-09-AuditRevive", root=tmp_path)
        server.revive_item("2026-09-AuditRevive", root=tmp_path)
        log = (tmp_path / ".para-audit.log")
        text = log.read_text()
        assert "revive" in text.lower()

    def test_revives_area_file(self, tmp_path):
        (tmp_path / "Work" / "Areas").mkdir(parents=True)
        (tmp_path / "Work" / "Areas" / "Health.md").write_text("# Health\n")
        server.archive_item("Health", root=tmp_path)
        result = server.revive_item("Health", root=tmp_path)
        assert result["ok"] is True

    def test_tool_wrapper_delegates(self, tmp_path, monkeypatch):
        monkeypatch.setattr(server, "REPO_ROOT", tmp_path)
        make_project(tmp_path, "Work", "2026-09-TV")
        server.archive_item("2026-09-TV", root=tmp_path)
        result = server.tool_revive_item("2026-09-TV")
        assert result["ok"] is True

    def test_archive_by_path_not_found(self, tmp_path):
        result = server.archive_item("Work/Projects/Missing", root=tmp_path)
        assert result["ok"] is False
        assert "not found" in result["error"].lower()

    def test_archive_rejects_traversal_path(self, tmp_path):
        result = server.archive_item("../../../etc/passwd", root=tmp_path)
        assert result["ok"] is False

    def test_archive_rejects_extra_segments_in_path(self, tmp_path):
        make_project(tmp_path, "Work", "2026-09-Deep")
        result = server.archive_item("Work/Projects/2026-09-Deep/index.md", root=tmp_path)
        assert result["ok"] is False

    def test_revive_rejects_path_not_under_archives(self, tmp_path):
        make_project(tmp_path, "Work", "2026-09-Live")
        result = server.revive_item("Work/Projects/2026-09-Live", root=tmp_path)
        assert result["ok"] is False

    def test_revive_rejects_traversal_path(self, tmp_path):
        result = server.revive_item("../../../etc/passwd", root=tmp_path)
        assert result["ok"] is False

    def test_revive_folder_without_index_defaults_to_projects(self, tmp_path):
        arch = tmp_path / "Work" / "Archives" / "2026-09-NoIndex"
        arch.mkdir(parents=True)
        result = server.revive_item("2026-09-NoIndex", root=tmp_path)
        assert result["ok"] is True
        assert (tmp_path / "Work" / "Projects" / "2026-09-NoIndex").exists()

    def test_archive_by_short_path_error(self, tmp_path):
        (tmp_path / "Work").mkdir(parents=True)
        (tmp_path / "Work" / "item").mkdir()
        result = server.archive_item("Work/item", root=tmp_path)
        assert result["ok"] is False

    def test_archive_skips_non_dir_root_items(self, tmp_path):
        (tmp_path / "README.md").write_text("top level")
        make_project(tmp_path, "Work", "2026-09-OK")
        result = server.archive_item("2026-09-OK", root=tmp_path)
        assert result["ok"] is True

    def test_revive_by_full_path(self, tmp_path):
        make_project(tmp_path, "Work", "2026-09-FP")
        server.archive_item("2026-09-FP", root=tmp_path)
        result = server.revive_item("Work/Archives/2026-09-FP", root=tmp_path)
        assert result["ok"] is True

    def test_revive_by_path_not_found(self, tmp_path):
        result = server.revive_item("Work/Archives/Missing", root=tmp_path)
        assert result["ok"] is False

    def test_revive_skips_domain_with_no_archives(self, tmp_path):
        # domain with no Archives dir at all
        (tmp_path / "Empty").mkdir()
        make_project(tmp_path, "Work", "2026-09-A")
        server.archive_item("2026-09-A", root=tmp_path)
        result = server.revive_item("2026-09-A", root=tmp_path)
        assert result["ok"] is True
