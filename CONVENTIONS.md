# Conventions

## Project naming

Projects are named `YYYY-MM-Short-Name` so they sort chronologically:

```
Projects/
├── 2026-01-Launch-Website/
├── 2026-03-Learn-Rust/
└── 2026-09-Renovate-Kitchen/
```

Each project folder contains at minimum an `index.md` with:
- Goal / desired outcome
- Deadline or target date
- Current status
- Next action

## Area naming

Areas are single Markdown files named for the responsibility:

```
Areas/
├── Health.md
├── Finance.md
└── Career-Development.md
```

## Resource naming

Resources can be files or folders depending on volume:

```
Resources/
├── Interview-Prep/        ← folder when there are many files
│   ├── behavioral.md
│   └── system-design.md
└── Productivity-Links.md  ← single file for light reference
```

## Archiving

To archive an item, move it into the `Archives/` folder of the same domain. Keep the original structure intact — do not rename or restructure archived items.

```bash
# Archive a project
mv Work/Projects/2026-03-Old-Project Work/Archives/
```

## Git workflow

All changes go through branches and pull requests — never commit directly to `main`.

### Branch naming

```
<feature-type>/<short-description>

feature/mcp-server
fix/stale-date-calculation
docs/conventions-update
refactor/domain-structure
```

### Worktree convention

Worktrees are checked out under `worktree/` and ignored by git:

```bash
# Create a worktree for a new branch
git worktree add worktree/<branch-name> -b <feature-type>/<description>

# Example
git worktree add worktree/feature-mcp-server -b feature/mcp-server
```

Remove when done:
```bash
git worktree remove worktree/<branch-name>
```

---

## Filing speed over perfection

When in doubt about which bucket something belongs in, file it fast and move it later. The system only works if friction is low.
