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

## Capture Protocol

When the user gives you a new item (note, task, link, idea):

1. Determine the correct domain and bucket using the decision flowchart below
2. Ask only if the domain or bucket is genuinely ambiguous — prefer to file fast and correct later
3. Create the appropriate file or folder following `CONVENTIONS.md`
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

## Project Status Vocabulary

Always use one of these exact statuses in a project's `index.md`:

| Status | Meaning |
| --- | --- |
| `Active` | Being worked on now |
| `On Hold` | Paused intentionally, expected to resume |
| `Waiting` | Blocked on someone or something external |
| `Complete` | Done — ready to archive |

Never invent new statuses.

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

1. **Projects** — List all Projects across all domains with status and last-modified date
2. **Stale check** — Flag any Project with no file changes in 14+ days as stale; warn the user it will be moved to Archives if no action is taken
3. **Blocked/Waiting** — Surface any Project with status `Waiting` and ask if it is unblocked
4. **Areas → Projects** — Scan Areas for anything that has grown into a Project-sized commitment; suggest creating a Project if so
5. **Resources** — Note any Resources not linked to an active Project (may be archivable)
6. **Archive suggestions** — List candidates for archiving with reasons; never archive without user confirmation

---

## Stale Project Rule

A Project is stale when no file in its folder has been modified in **14 days**.

On detection:

1. Flag it in the weekly review output
2. Warn the user: *"This project has had no activity in 14+ days. It will be suggested for Archives at the next review unless marked Active or On Hold."*
3. At the following review, if still stale, suggest archiving — but do not move it without explicit user confirmation

---

## Daily Digest Format

When asked for a daily digest, output in this order:

1. **Today's Project deadlines** — any Project with a deadline of today or within 3 days
2. **Active Projects — next actions** — one next action per Active Project, across all domains
3. **Waiting Projects** — brief status check on anything blocked externally
4. **Reminders from Areas** — any Area with a note flagged for follow-up

Keep it scannable — one line per item unless the user asks for detail.

---

## Archive Rules

Archive a Project when any of the following are true:

- Status is `Complete`
- Status has been `On Hold` for 30+ days with no file activity
- User explicitly requests it

To archive: move the entire Project folder to `Archives/` in the same domain. Do not rename, restructure, or delete any files.

Archive an Area or Resource only on explicit user request.

---

## Agent responsibilities

### Capture

Follow the Capture Protocol above.

### File

Follow the naming conventions in `CONVENTIONS.md`. Prefer speed over perfection — file first, refine later.

### Review

Follow the Weekly Review Protocol above.

### Notify

Surface upcoming Project deadlines and next actions when asked for a daily or weekly digest. Follow the Daily Digest Format above.

### Archive

Follow the Archive Rules above. Never archive without user confirmation.

---

## What the agent should not do

- Modify the `_template-domain/` folder
- Delete any file without explicit user confirmation
- Archive anything without explicit user confirmation
- Invent project statuses outside the defined vocabulary
- Make assumptions about personal details not present in this repo
