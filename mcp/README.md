# PARA MCP Server

> **Status: Planned** — not yet implemented. See `AGENTS.md` in this directory for the spec.

A local MCP server that enforces PARA rules programmatically, making every tool call consistent regardless of which LLM you use.

## Setup (once implemented)

```bash
cd mcp
pip install -r requirements.txt
python server.py
```

Configure in `.claude/settings.json`:

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

## See also

- `AGENTS.md` in this directory — code-level instructions for the MCP server
- `../AGENTS.md` — top-level PARA operating instructions for the agent
- `../CONVENTIONS.md` — naming and filing conventions the server enforces
