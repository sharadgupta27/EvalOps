# EvalOps MCP server

Gives coding agents a **scoped** view of EvalOps: they can inspect runs, find regressions and
start an evaluation, but nothing else. Built with the official Python MCP SDK (`mcp` 2.x,
`MCPServer`), stdio transport.

| Kind | Name | Notes |
|---|---|---|
| tool | `list_projects` | read-only; always the one project the key belongs to |
| tool | `list_prompt_versions(project_id)` | read-only |
| tool | `list_runs(project_id, limit=10)` | read-only |
| tool | `get_run_summary(run_id)` | read-only |
| tool | `compare_runs(base_run_id, head_run_id)` | read-only |
| tool | `get_regressions(base_run_id, head_run_id, limit=10)` | read-only; outputs truncated to 600 chars |
| tool | `start_run(project_id, dataset_id, prompt_label, git_sha?)` | **only write**; costs money with a real model; capped by the server |
| resource | `evalops://runs/{run_id}` | run summary + per-case results as JSON |
| prompt | `triage-regression(base_run_id, head_run_id)` | step-by-step triage with an injection warning |

Security model: [docs/permissions.md](../docs/permissions.md).

## Configure

Environment: `EVALOPS_URL` (default `http://localhost:5173`) and `EVALOPS_API_KEY` (a
project key from *Gate & API keys*).

**Claude Code**: already registered in the repo's [.mcp.json](../.mcp.json):

```json
{ "mcpServers": { "evalops": { "command": "uv", "args": ["run", "--project", "mcp-server", "--quiet", "python", "mcp-server/server.py"],
  "env": { "EVALOPS_URL": "${EVALOPS_URL:-http://localhost:5173}", "EVALOPS_API_KEY": "${EVALOPS_API_KEY}" } } } }
```

**Codex** (`~/.codex/config.toml`):

```toml
[mcp_servers.evalops]
command = "uv"
args = ["--directory", "/path/to/EvalOps/mcp-server", "run", "python", "server.py"]
env = { EVALOPS_URL = "http://localhost:5173", EVALOPS_API_KEY = "eo_..." }
```

**Cursor / Antigravity** (`mcp.json`): same `command`/`args`/`env` under `"mcpServers"`.

## Test

```bash
cd mcp-server
uv run pytest -q                       # 7 tests against a mocked EvalOps API
EVALOPS_API_KEY=eo_... uv run python scripts/smoke.py   # real stdio session against a running stack
```
