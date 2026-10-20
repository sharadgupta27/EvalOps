# Permissions

Who and what may do what, and why. Principle: **least privilege per actor**, enforced in
code where possible and by configuration otherwise. Changing this table requires updating the
enforcement listed next to it.

## Product API

| Capability | User (JWT) | Project API key (CI, MCP, agents) | Enforced in |
|---|---|---|---|
| See own projects | all owned projects | **only its own project** (404 for others) | `Service.project_for` |
| Create / rename / delete projects | ✅ | ❌ 403 | `Service.require_user` |
| Create prompt versions | ✅ | only via `POST /gate` (new label, immutable) or `POST /gate/ingest` (a `model=external` placeholder with a constant template; a label that belongs to a real version is a 409) | `RunService.start_gate`, `RunService.ingest_gate` |
| Datasets, cases, evaluators: read | ✅ | ✅ | |
| Datasets, cases, evaluators: write | ✅ | ❌ 403 | `require_user` |
| Start runs | ✅ (`triggered_by=ui`) | ✅ (`agent`, or `ci` via gate); bounded by case, per-run cost and daily budget caps | `queue_run` |
| Record a run of results computed elsewhere | ✅ (no endpoint) | ✅ via `POST /gate/ingest` into an existing dataset; no queue, no LLM call, no cost, so the case, per-run cost and daily budget caps do not apply. The guards are the case-count cap, `output` ≤ 5000 chars, the request body limit and rate limiting | `RunService.ingest_gate`, `BodySizeLimitMiddleware` |
| Compare, results, summaries | ✅ | ✅ | |
| Gate policy: read / write | ✅ / ✅ | ✅ / ❌ | `put_policy` |
| `POST /gate`, `POST /gate/ingest`, `GET /gate/{id}` | ❌ (API key only) | ✅ | `get_api_key_principal` |
| Create / list / revoke API keys | ✅ | ❌ (a key cannot mint keys) | `require_user` |

Keys are 256-bit random, stored hashed (SHA-256), shown once, revocable, and record
`last_used_at`.

## Coding agents (Claude Code in this repo)

| Actor | May | May not | Enforced by |
|---|---|---|---|
| Main agent | edit code, run tests and linters, read MCP data | read `.env*`; edit committed migrations, the generated client, or `openapi.yaml` without review; destructive git/docker/SQL; deploy or touch AWS | `agent-hooks/guard.py` (PreToolUse), `.claude/settings.json` `permissions.deny`, CLAUDE.md |
| Main agent | `git commit`, `git push`, `docker compose`, `start_run` | run any of these without asking first | `permissions.ask` |
| `api-contract-reviewer` | Read, Grep, Glob, `git diff/log/show` | edit anything | `tools:` frontmatter |
| `eval-reviewer` | read files, run calibration, read-only EvalOps MCP tools | edit, start runs | `tools:` frontmatter |
| `qa-tester` | read, edit **test files**, run test commands | change application code (instructed; reviewed in diff) | `tools:` + instructions + review |
| Hooks | run formatters, linters, fast tests; append to `agent-hooks/logs/audit.jsonl` | network access, reading secrets | code review of `agent-hooks/` |

## MCP server (`mcp-server/server.py`)

- One project API key via `EVALOPS_API_KEY`; the API enforces the scope, so the MCP server
  cannot widen it even if the code is changed.
- Tools: `list_projects`, `list_prompt_versions`, `list_runs`, `get_run_summary`,
  `compare_runs`, `get_regressions` are **read-only** (`readOnlyHint`), and
  `start_run` is the **only state-changing tool**: it queues a run, costs money with a real
  model, and needs user approval (`ask`).
- No delete, edit, key or policy tools. Adding one requires updating this file and
  `security/agent-threat-model.md` in the same change (rule in CLAUDE.md).
- Outputs are truncated to 600 characters per field to limit context flooding and injection.

## Automation

| Actor | Credentials | Scope |
|---|---|---|
| CI (`ci.yml`, `eval-gate.yml`) | none for prod; ephemeral stack and key created by the seed script | read repo; GitHub token `contents: read` |
| Deploy (`deploy.yml`) | `GITHUB_TOKEN` (`packages: write`), `EC2_SSH_KEY` in the `production` environment | push images, SSH to one host; runs only after CI is green on `main`, opt-in via `DEPLOY_ENABLED` |
| Nightly triage agent | `EVALOPS_API_KEY` (one project), `ANTHROPIC_API_KEY` (optional), `GITHUB_TOKEN` with `issues: write` | read EvalOps, start one run, open one issue |
