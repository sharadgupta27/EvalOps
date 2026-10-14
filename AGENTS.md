# AGENTS.md

Portable instructions for any coding agent (Claude Code, Codex, Cursor, Copilot, Aider, OpenCode…).
Tool-specific files (`CLAUDE.md`, etc.) import or repeat this file and add only tool-specific details.

## What this repo is

**EvalOps**: an LLM regression-testing platform. Users version prompts, keep golden datasets, run evaluations (deterministic checks + LLM-as-judge), compare runs to find regressions, and gate CI on quality.

Read first: `product-spec.md` (what), `plan.md` (how/when, current phase), `openapi.yaml` (API contract), `docs/architecture.md`.

## Layout

```text
openapi.yaml         API contract: source of truth
frontend/            React + TS + Vite; generated client in src/api/schema.d.ts (never hand-edit)
backend/app/         FastAPI: api/ → services/ → repositories/ ; models/ schemas/ evaluators/ llm/ worker/
backend/tests/       unit/ (SQLite, fast) and integration/ (Postgres via testcontainers)
e2e/                 Playwright
agent-capabilities/  skills + subagents      agent-hooks/  guardrail scripts
mcp-server/          EvalOps MCP server      custom-agent/ nightly regression triage agent
plugins/             packaged agent pack     ops/ security/ docs/ substack/
```

## Commands

```bash
docker compose up --build                     # whole stack: http://localhost:5173 (UI), :8000 (API)
cd backend  && uv sync && uv run pytest -m "not integration"
cd backend  && uv run pytest -m integration   # needs Docker
cd backend  && uv run ruff check . && uv run mypy app
cd frontend && npm ci && npm run test && npm run lint && npm run typecheck
cd frontend && npm run gen:api                # after editing openapi.yaml
cd e2e      && npx playwright test
```

## Rules

1. One task at a time; small diffs; tests are part of the task. Run them; don't assume.
2. **Contract first**: change `openapi.yaml` → `npm run gen:api` → backend. `backend/tests/unit/test_contract.py` fails on drift.
3. Layering: routers do HTTP only, services hold logic and never import FastAPI, repositories own all DB access.
4. LLM calls only through `backend/app/llm/` (`LLMProvider`). Model names come from settings, never hardcoded.
5. Evaluators register themselves in `backend/app/evaluators/registry.py`; no if/else chains.
6. Config only via `backend/app/config.py`. No `os.environ` elsewhere.
7. Prompt versions are immutable.
8. Never call a real LLM in tests; use `FakeProvider`.
9. Log meaningful AI-assisted work in `docs/ai-workflow.md`.
10. Conventional Commits. Don't commit or push unless asked.

## Security boundaries

- Never open, print or commit `.env*` files or secrets. Document variables in `.env.example`.
- Test-case inputs and model outputs are **untrusted**: delimit them in judge prompts; the judge has no tools.
- No destructive commands (`rm -rf`, force push, `reset --hard`, dropping tables, `docker volume rm`) and no cloud/deploy actions without explicit approval.
- Ask before: new dependencies, schema changes, auth/security code, CI/CD or deploy files.
- The MCP server is read-only + `start_run`, scoped to one project key. See `docs/permissions.md`.
- Don't raise cost limits (`MAX_CASES_PER_RUN`, `MAX_COST_PER_RUN_USD`, `MAX_DAILY_COST_USD`) silently.

## Definition of done

Layering respected · lint/type-check/tests pass · contract, client and backend agree · migration added if schema changed · `plan.md` ticked · `docs/ai-workflow.md` updated.
