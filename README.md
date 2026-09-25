# PARA Template

A GitHub template for organizing your digital life using the [PARA method](https://www.todoist.com/productivity-methods/para-method) — Projects, Areas, Resources, Archives — with built-in OpenClaw agent support.

## What is PARA?

| Bucket | Definition | When to use |
|---|---|---|
| **Projects** | Active work with a clear deadline or finish line | Anything you are actively doing right now |
| **Areas** | Ongoing responsibilities with no end date | Things you maintain indefinitely |
| **Resources** | Reference material you may want later | Anything worth saving for future use |
| **Archives** | Inactive items from any bucket | Completed, paused, or no-longer-relevant items |

## How to use this template

1. Click **Use this template** on GitHub to create your own repo
2. Rename or delete the starter domains (`Work/`, `Personal/`, `Family/`) to match your life
3. Copy `_template-domain/` whenever you need a new domain
4. Follow the conventions in `CONVENTIONS.md`

## Domains

This template ships with three starter domains. Customize freely.

- `Work/` — professional responsibilities and projects
- `Personal/` — individual goals and resources
- `Family/` — shared household responsibilities

To add a domain (e.g. `SideProjects/`):
```bash
cp -r _template-domain/ SideProjects/
```

## OpenClaw Integration

This template includes `AGENTS.md` and `CLAUDE.md` so your OpenClaw agent understands the PARA structure and can help you capture, file, and review items.

See `AGENTS.md` for how the agent interacts with this repo.
