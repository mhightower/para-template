# PARA — OpenClaw Agent Instructions

This repo implements the PARA method across one or more life domains.

## Structure

Each domain (e.g. `Work/`, `Personal/`) contains four buckets:

- `Projects/` — active work with a deadline or finish line
- `Areas/` — ongoing responsibilities with no end date
- `Resources/` — reference material for future use
- `Archives/` — inactive items from any bucket

See `CONVENTIONS.md` for naming rules and filing guidelines.

---

## MCP Tools

When the `para` MCP server is available, use its tools for all file operations.
The server enforces naming conventions, status vocabulary, and archive rules in
code — do not reimplement those rules manually.

| Tool | When to use |
| --- | --- |
| `create_project` | Starting a new project |
| `list_projects` | Getting an overview of active work |
| `weekly_review` | Running the weekly review stale check |
| `archive_project` | Archiving a project (requires explicit user confirmation first) |
| `update_status` | Changing a project's status |
| `capture` | Filing a new Area, Resource, or Archive item |
| `add_file_to_project` | Adding a file to an existing project |

If the MCP server is unavailable, fall back to direct file operations following
`CONVENTIONS.md`.

---

## Capture Protocol

When the user gives you a new item (note, task, link, idea):

1. Determine the correct domain and bucket using the decision flowchart below
2. Ask only if the domain or bucket is genuinely ambiguous — prefer to file fast and correct later
3. Use the appropriate MCP tool (or create the file directly if MCP is unavailable)
4. Confirm what was filed and where

**Minimum fields to populate at capture:**

- Projects: goal, deadline (or "no hard deadline"), status (`Active`)
- Areas: purpose statement
- Resources: topic, source URL if applicable

### Project vs. Area decision flowchart

```text
Does this have a finish line or deadline?
├── YES → Is it something you are actively working on now?
│         ├── YES → Projects/
│         └── NO  → Projects/ (status: On Hold)
└── NO  → Is it an ongoing responsibility you maintain?
          ├── YES → Areas/
          └── NO  → Resources/ (if reference) or discard
```

---

## Project Status

Use `update_status` to change a project's status. The MCP server enforces the
allowed vocabulary — see `mcp/AGENTS.md` for the exact values.

---

## Linking Convention

When an item in one bucket is related to another, add a `See:` line:

```text
See: Work/Resources/Interview-Prep/
See: Personal/Areas/Health.md
```

Use this when:

- A Resource is actively feeding a Project
- An Area spawned a Project
- An archived item is referenced by an active one

---

## Weekly Review Protocol

On a weekly review request, run these steps in order:

1. **Stale check** — call `weekly_review`; present the results to the user
2. **Blocked/Waiting** — surface any Project with status `Waiting` and ask if it is unblocked
3. **Areas → Projects** — scan Areas for anything that has grown into a Project-sized commitment; suggest creating a Project if so
4. **Resources** — note any Resources not linked to an active Project (may be archivable)
5. **Archive suggestions** — list candidates for archiving with reasons; call `archive_project` only after explicit user confirmation

---

## Daily Digest Format

When asked for a daily digest, output in this order:

1. **Today's Project deadlines** — any Project with a deadline of today or within 3 days
2. **Active Projects — next actions** — one next action per Active Project, across all domains
3. **Waiting Projects** — brief status check on anything blocked externally
4. **Reminders from Areas** — any Area with a note flagged for follow-up

Keep it scannable — one line per item unless the user asks for detail.

---

## Archiving

Call `archive_project` only after the user explicitly confirms. Never move,
rename, or delete files during archiving — the MCP tool handles the move.
Archive an Area or Resource only on explicit user request (direct file move).

---

## What the agent should not do

- Modify the `_template-domain/` folder
- Delete any file without explicit user confirmation
- Archive anything without explicit user confirmation
- Invent project statuses — use `update_status` which enforces the vocabulary
- Make assumptions about personal details not present in this repo
