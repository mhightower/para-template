# PARA Template

A GitHub template for organizing your digital life using the [PARA method](https://www.todoist.com/productivity-methods/para-method) — Projects, Areas, Resources, Archives — with built-in OpenClaw and Claude Code agent support and an MCP server for rule enforcement.

## What is PARA?

| Bucket | Definition | When to use |
|---|---|---|
| **Projects** | Active work with a clear deadline or finish line | Anything you are actively working on now |
| **Areas** | Ongoing responsibilities with no end date | Things you maintain indefinitely |
| **Resources** | Reference material you may want later | Anything worth saving for future use |
| **Archives** | Inactive items from any bucket | Completed, paused, or no-longer-relevant items |

## How to use this template

1. Click **Use this template** on GitHub to create your own repo
2. Copy `_template-domain/` for each domain you want (e.g. `Work/`, `Personal/`)
3. Follow the conventions in `CONVENTIONS.md`
4. Set up the MCP server (see `mcp/README.md`) for automated rule enforcement

## Repo layout

```
.
├── AGENTS.md              ← Agent operating instructions (OpenClaw, any LLM)
├── CLAUDE.md              ← Claude Code specific instructions
├── GEMINI.md              ← Gemini CLI specific instructions
├── CONVENTIONS.md         ← Naming rules, filing guide, status vocabulary
├── _template-domain/      ← Copy this to add a new domain
│   ├── Projects/
│   ├── Areas/
│   ├── Resources/
│   └── Archives/
├── YourDomain/            ← Created by you (copy _template-domain/)
├── mcp/
│   ├── AGENTS.md          ← MCP server code instructions
│   ├── server.py          ← MCP server (enforces PARA rules programmatically)
│   └── README.md          ← MCP setup guide
├── .claude/
│   └── settings.json      ← Claude Code permissions + MCP server config
└── .github/
    └── copilot-instructions.md
```

## Domains

Create domains that match your life — there are no defaults. To add a domain:

```bash
cp -r _template-domain/ Work/
cp -r _template-domain/ Personal/
cp -r _template-domain/ SideProjects/
```

Name them anything. Each gets its own `Projects/`, `Areas/`, `Resources/`, and `Archives/`.

## AI Agent Integration

This template is designed to be used with an AI agent (OpenClaw, Claude Code, Gemini CLI, or GitHub Copilot). The agent reads `AGENTS.md` to understand:

- How to classify and file new items
- The weekly review protocol
- Stale project rules (14-day warning before archiving)
- The daily digest format
- Archive rules (never without your confirmation)

See `AGENTS.md` for the full operating instructions.

## MCP Server

The `mcp/` directory contains a Python MCP server that enforces PARA rules in code — ensuring naming conventions, status vocabulary, and archive rules are applied consistently across any LLM or tool.

**Tools provided:**

| Tool | What it does |
|---|---|
| `create_project` | Creates a project with correct naming and required fields |
| `list_projects` | Lists all projects with status and days-since-modified |
| `weekly_review` | Runs stale check and surfaces archive candidates |
| `archive_project` | Moves a project to Archives (explicit action only) |
| `update_status` | Updates project status (validates vocabulary) |
| `capture` | Files a new item in the correct bucket |

See `mcp/README.md` for setup instructions.

## Key files

| File | Purpose |
|---|---|
| `AGENTS.md` | How the AI agent should operate in this repo |
| `CONVENTIONS.md` | Naming rules, status vocabulary, filing guide |
| `mcp/AGENTS.md` | Code-level instructions for working on the MCP server |
