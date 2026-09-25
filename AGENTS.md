# PARA — OpenClaw Agent Instructions

This repo implements the PARA method across one or more life domains.

## Structure

Each domain (e.g. `Work/`, `Personal/`) contains four buckets:

- `Projects/` — active work with a deadline or finish line
- `Areas/` — ongoing responsibilities with no end date
- `Resources/` — reference material for future use
- `Archives/` — inactive items from any bucket

See `CONVENTIONS.md` for naming rules and filing guidelines.

## Agent responsibilities

### Capture
When the user gives you a new item (note, task, link, idea), classify it into the correct domain and bucket and create the appropriate file or folder. Ask the domain and bucket only if genuinely ambiguous.

### File
Follow the naming conventions in `CONVENTIONS.md`. Prefer speed over perfection — file first, refine later.

### Review
On a weekly review request:
1. List all open Projects across all domains with their last-updated date
2. Flag any Project with no activity in 14+ days
3. Identify any Area that may have spawned a Project worth creating
4. Suggest items to Archive

### Notify
Surface upcoming Project deadlines and next actions when asked for a daily or weekly digest.

### Archive
When a Project is complete or paused, move it to `Archives/` in the same domain. Do not delete.

## What the agent should not do

- Modify the `_template-domain/` folder
- Delete any file without explicit user confirmation
- Make assumptions about personal details not present in this repo
