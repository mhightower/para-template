# PARA MCP Server — Agent Instructions

This directory contains the MCP server that enforces PARA rules programmatically. Read this file when working on the MCP server code.

## Purpose

The MCP server is the enforcement layer for the PARA system. While `../AGENTS.md` tells an LLM what the rules are, this server implements them in code — ensuring naming conventions, status vocabulary, and archive rules are applied consistently regardless of which LLM is used.

## Architecture

- **Language:** Python
- **Framework:** `mcp` SDK
- **Repo root resolution:** The server resolves the repo root from its own file location (`Path(__file__).parent.parent`). No config needed.
- **Data format:** Markdown files on disk — no database.

## Tools

Each tool enforces one or more rules from `../AGENTS.md`:

| Tool | File path | Enforces |
| --- | --- | --- |
| `create_project` | `server.py` | Naming convention (`YYYY-MM-Name`), required fields, initial status=Active |
| `list_projects` | `server.py` | Reads all project `index.md` files, computes days-since-modified |
| `weekly_review` | `server.py` | Stale check (14-day threshold), returns candidates — never auto-archives |
| `archive_project` | `server.py` | Moves folder to `Archives/`, logs action — requires explicit call |
| `update_status` | `server.py` | Validates against allowed vocabulary: Active, On Hold, Waiting, Complete |
| `capture` | `server.py` | Creates file/folder in correct bucket following naming conventions |

## Rules to enforce in code (never relax these)

1. Project names must match `YYYY-MM-Short-Name` — reject or auto-correct on create
2. Status values must be exactly one of: `Active`, `On Hold`, `Waiting`, `Complete`
3. `archive_project` must never be called without a prior explicit user confirmation in the tool call chain
4. `weekly_review` must flag stale projects but never move them — return a list only
5. All file operations are relative to the repo root — never use absolute paths from config

## Adding a new tool

1. Define the tool function in `server.py`
2. Register it with the `@mcp.tool()` decorator
3. Add it to the Tools table above
4. Add a test case to `tests/` (when tests exist)

## Testing

Run the server locally:

```bash
cd mcp
pip install -r requirements.txt
python server.py
```

Point a Claude Code or OpenClaw session at it via `.claude/settings.json`:

```json
{
  "mcpServers": {
    "para": {
      "command": "python",
      "args": ["mcp/server.py"]
    }
  }
}
```
