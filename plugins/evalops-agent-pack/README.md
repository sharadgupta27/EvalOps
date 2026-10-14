# evalops-agent-pack (Claude Code plugin)

Packages the EvalOps agent extensions so another repository can reuse them with one install
instead of copying files.

| Component | What it adds |
|---|---|
| `skills/add-eval-case` | Turn a bug report into regression test cases and prove they fail |
| `skills/review-api-change` | Contract-first checklist; unlocks `openapi.yaml` edits |
| `skills/debug-ci-failure` | Map a red CI job to a local repro and a real fix |
| `agents/api-contract-reviewer` | Read-only API diff reviewer |
| `agents/eval-reviewer` | Critiques judge prompts, rubrics and datasets |
| `agents/qa-tester` | Writes and runs tests; may only touch test files |
| `hooks/` | Secret/migration/contract/destructive-command guard, format-on-save, tests-before-stop |
| `.mcp.json` | The `evalops` MCP server (scoped to one project API key) |

## Install

```bash
# from a checkout of the EvalOps repo (the repo root contains .claude-plugin/marketplace.json)
claude plugin marketplace add ./
claude plugin install evalops-agent-pack@evalops
```

or inside Claude Code: `/plugin marketplace add <path-or-git-url>` then `/plugin install evalops-agent-pack@evalops`.

Requirements: `uv` on PATH (hooks and the MCP server run through it), and these env vars for
the MCP server: `EVALOPS_URL` and `EVALOPS_API_KEY` (a project key from *Gate & API keys*).

## Do not edit files here

Everything in this folder except `.claude-plugin/`, `hooks/hooks.json`, `.mcp.json` and this
README is generated from `agent-capabilities/`, `agent-hooks/` and `mcp-server/` by
`python agent-hooks/install.py`. CI fails if the copies are stale (`--check`).

Permissions and threat notes: [docs/permissions.md](../../docs/permissions.md).
