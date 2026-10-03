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
# Tags (issue #24)
# ---------------------------------------------------------------------------

class TestTags:
    def _make_note(self, tmp_path, domain, bucket, name, content="# Note\n") -> Path:
        p = tmp_path / domain / bucket
        p.mkdir(parents=True, exist_ok=True)
        note = p / f"{name}.md"
        note.write_text(content)
        return note

    def test_tag_item_adds_tag_to_file(self, tmp_path):
        note = self._make_note(tmp_path, "Work", "Resources", "my-note")
        result = server.tag_item("Work/Resources/my-note.md", "#urgent", root=tmp_path)
        assert result["ok"] is True
        assert "#urgent" in note.read_text()

    def test_tag_item_creates_tags_field_if_absent(self, tmp_path):
        note = self._make_note(tmp_path, "Work", "Resources", "bare")
        server.tag_item("Work/Resources/bare.md", "#new", root=tmp_path)
        text = note.read_text()
        assert "**Tags:**" in text

    def test_tag_item_appends_to_existing_tags(self, tmp_path):
        note = self._make_note(tmp_path, "Work", "Resources", "existing",
                               content="# Note\n\n**Tags:** #first\n")
        server.tag_item("Work/Resources/existing.md", "#second", root=tmp_path)
        text = note.read_text()
        assert "#first" in text
        assert "#second" in text

    def test_tag_item_does_not_duplicate_tag(self, tmp_path):
        note = self._make_note(tmp_path, "Work", "Resources", "dup",
                               content="# Note\n\n**Tags:** #urgent\n")
        result = server.tag_item("Work/Resources/dup.md", "#urgent", root=tmp_path)
        assert result["ok"] is False
        assert "already" in result["error"].lower()

    def test_tag_item_file_not_found(self, tmp_path):
        result = server.tag_item("Work/Resources/missing.md", "#x", root=tmp_path)
        assert result["ok"] is False

    def test_untag_item_removes_tag(self, tmp_path):
        note = self._make_note(tmp_path, "Work", "Resources", "tagged",
                               content="# Note\n\n**Tags:** #urgent #waiting\n")
        result = server.untag_item("Work/Resources/tagged.md", "#urgent", root=tmp_path)
        assert result["ok"] is True
        text = note.read_text()
        assert "#urgent" not in text
        assert "#waiting" in text

    def test_untag_item_tag_not_present_returns_error(self, tmp_path):
        note = self._make_note(tmp_path, "Work", "Resources", "notag",
                               content="# Note\n\n**Tags:** #waiting\n")
        result = server.untag_item("Work/Resources/notag.md", "#missing", root=tmp_path)
        assert result["ok"] is False

    def test_get_tagged_returns_items_with_tag(self, tmp_path):
        self._make_note(tmp_path, "Work", "Resources", "n1",
                        content="# N1\n\n**Tags:** #urgent\n")
        self._make_note(tmp_path, "Personal", "Areas", "n2",
                        content="# N2\n\n**Tags:** #urgent #other\n")
        self._make_note(tmp_path, "Work", "Resources", "n3",
                        content="# N3\n\n**Tags:** #other\n")
        results = server.get_tagged("#urgent", root=tmp_path)
        paths = [r["path"] for r in results]
        assert any("n1" in p for p in paths)
        assert any("n2" in p for p in paths)
        assert not any("n3" in p for p in paths)

    def test_list_tags_returns_all_tags_with_counts(self, tmp_path):
        self._make_note(tmp_path, "Work", "Resources", "a",
                        content="# A\n\n**Tags:** #urgent\n")
        self._make_note(tmp_path, "Work", "Areas", "b",
                        content="# B\n\n**Tags:** #urgent #focus\n")
        tags = server.list_tags(root=tmp_path)
        tag_map = {t["tag"]: t["count"] for t in tags}
        assert tag_map.get("#urgent") == 2
        assert tag_map.get("#focus") == 1

    def test_list_tags_empty_when_no_tags(self, tmp_path):
        self._make_note(tmp_path, "Work", "Resources", "plain", content="# No tags\n")
        tags = server.list_tags(root=tmp_path)
        assert tags == []

    def test_get_tagged_inline_tags_detected(self, tmp_path):
        self._make_note(tmp_path, "Work", "Areas", "inline",
                        content="# Note\n\nThis is #transcribed content.\n")
        results = server.get_tagged("#transcribed", root=tmp_path)
        assert len(results) > 0

    def test_tag_item_rejects_invalid_tag_format(self, tmp_path):
        note = self._make_note(tmp_path, "Work", "Resources", "bad")
        result = server.tag_item("Work/Resources/bad.md", "urgent", root=tmp_path)
        assert result["ok"] is False
        assert "invalid tag" in result["error"].lower()

    def test_untag_item_file_not_found(self, tmp_path):
        result = server.untag_item("Work/Resources/ghost.md", "#x", root=tmp_path)
        assert result["ok"] is False
