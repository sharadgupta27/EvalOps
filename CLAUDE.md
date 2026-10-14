# CLAUDE.md

Guidance for Claude Code (and other coding agents) working in this repository.

@AGENTS.md

## Claude Code specifics

- Skills live in `agent-capabilities/` and are exposed to Claude Code through `.claude/skills/` (copied by `agent-hooks/install.ps1` / `install.sh`, or installed via the plugin in `plugins/evalops-agent-pack/`).
- Subagents: `.claude/agents/` (`eval-reviewer`, `api-contract-reviewer`, `qa-tester`).
- Hooks are configured in `.claude/settings.json` and implemented in `agent-hooks/`.
- The EvalOps MCP server is registered in `.mcp.json`.

## Project

**EvalOps** is an LLM regression-testing platform. Users version prompts, maintain golden datasets, run evaluations (deterministic checks and LLM-as-judge), compare versions to find regressions, and gate CI on quality thresholds.

This is the final project for the DataTalksClub AI Dev Tools Zoomcamp. Grading rubric: [docs/rubric.md](docs/rubric.md). Agent extension pack requirements: [docs/module5-requirements.md](docs/module5-requirements.md).

- **Roadmap and current phase:** [plan.md](plan.md). Read it before starting work. Tick checkboxes when a task is done.
- **Product requirements:** `product-spec.md`
- **API contract (source of truth):** `openapi.yaml`

## Workflow Rules

1. **One task at a time.** Pick a single unchecked item from `plan.md`, state the plan in 2–5 bullets, then implement. Keep diffs small and focused.
2. **Contract first.** API changes start in `openapi.yaml`. Then regenerate the frontend client, then update the backend. Never let them drift; the contract test enforces this.
3. **Tests are part of the task.** A task is done only when the relevant tests exist and pass. Run them, don't assume.
4. **Log AI usage.** After each meaningful task, append an entry to `docs/ai-workflow.md`: the goal, the prompt or delegation used, what you produced, what the human reviewed or changed, and how it was verified. This log is graded (rubric criterion 2).
5. **Ask before** adding a new dependency, changing the database schema, changing auth or security code, or touching CI/CD and deploy files.
6. **Don't commit or push** unless asked. When committing, use Conventional Commits (`feat:`, `fix:`, `test:`, `docs:`, `chore:`, `ci:`).
7. **Substack drafts.** When a phase completes, draft its guide chapter in `substack/` and explain concepts for beginners. Write for readers, not for agents.

## Repository Layout

```text
frontend/            React + TS + Vite. API client generated into src/api/ (do not hand-edit)
backend/app/
  api/               FastAPI routers: HTTP only, no business logic
  services/          business logic
  repositories/      all DB access (SQLAlchemy)
  models/            ORM models
  schemas/           Pydantic request/response models
  evaluators/        one module per evaluator type; judge prompts in evaluators/prompts/
  llm/               LLMProvider protocol, AnthropicProvider, FakeProvider
  worker/            job polling and run execution
backend/migrations/  Alembic
backend/tests/{unit,integration}/
e2e/                 Playwright
ops/  security/  docs/
agent-capabilities/  agent-hooks/  mcp-server/  plugins/  custom-agent/
```

## Commands

```bash
# Full stack (migrations run automatically in the one-shot `migrate` service)
docker compose up -d --build --wait      # api :8000, frontend :5173, postgres :5432
docker compose run --rm api python -m app.seed   # demo data (demo@evalops.dev / DEMO_PASSWORD)
docker compose -f docker-compose.yml -f ops/docker-compose.observability.yml up -d   # + Grafana :3000

# Backend (from backend/)
uv sync
uv run uvicorn app.main:app --reload
uv run python -m app.worker
uv run pytest -m "not integration"       # fast unit tests (SQLite, < 30 s)
uv run pytest -m integration             # needs Docker (testcontainers Postgres)
uv run ruff check . && uv run ruff format . && uv run mypy app tests
uv run alembic revision --autogenerate -m "<message>"
uv run python -m app.evaluators.calibrate   # judge vs labelled set

# Frontend (from frontend/)
npm ci
npm run dev
npm run gen:api                          # regenerate client from ../openapi.yaml
npm run mock                             # Prism mock server of the contract on :8000
npm run test                             # Vitest
npm run lint && npm run typecheck

# E2E (from e2e/, against a running, seeded stack)
npx playwright test

# Agent pack and CI gate (from repo root)
python agent-hooks/install.py            # sync skills/subagents/hooks into .claude/ and the plugin
python -m unittest discover -s agent-hooks/tests
cd mcp-server && uv run pytest
python scripts/evalops_gate.py --help
```

The dev machine runs Windows with PowerShell. Prefer commands that work cross-platform. Use `docker compose` (v2), not `docker-compose`.

## Architecture Rules

- **Layering:** `api → services → repositories`. Routers never touch the DB session directly. Services never import FastAPI.
- **Frontend API calls** go only through the generated client in `frontend/src/api/` and wrap it in TanStack Query hooks. No ad-hoc `fetch` calls in components.
- **LLM calls** go only through the `LLMProvider` protocol in `backend/app/llm/`. No other module imports the Anthropic SDK.
- **Model names and parameters** come from settings and env vars (`DEFAULT_MODEL`, `JUDGE_MODEL`). Never hardcode them.
- **Evaluators** implement a common interface `evaluate(case, output) -> EvalScore`. Add new ones by registering them, not with if/else chains.
- **Background work** runs in the worker via the Postgres jobs table, never inside request handlers.
- **Config** comes only from `app/config.py` (pydantic-settings). No `os.environ` lookups elsewhere.
- **Prompt versions are immutable.** Edits create a new version.

## Coding Conventions

**Python:**
- 3.12, full type hints, `ruff` for lint and format, `mypy` clean.
- Pydantic v2 and SQLAlchemy 2.0 style (`Mapped[...]`, `select()`).
- Async endpoints.
- Raise domain exceptions in services; map them to HTTP errors in one exception handler.

**TypeScript:**
- `strict` mode, function components and hooks, ESLint + Prettier.
- Tailwind 4 for styling (CSS-first config in `src/index.css`, no `tailwind.config.js`).
- No `any` unless justified in a comment.

**Naming:** snake_case for Python and DB columns, camelCase for TS, kebab-case for file names in `frontend/src/components`.

**Comments:** explain *why*, not *what*. No commented-out code.

## Testing Rules

- **Never call a real LLM in tests.** Use `FakeProvider`, which is deterministic and configurable per test.
- Unit tests use SQLite and run in under 30 s total. Integration tests are marked `@pytest.mark.integration` and use Postgres via testcontainers.
- Every bug fix includes a regression test.
- Playwright E2E covers the happy path in `plan.md` §1 and uses seeded data.
- Do not weaken or delete a failing test to make CI pass. Fix the code, or explain why the test is wrong and ask.

## Database

- All schema changes go through Alembic migrations. Never edit an already-applied migration.
- `DATABASE_URL` selects the engine (SQLite for tests, Postgres for dev and prod). Don't write Postgres-only SQL outside repositories that are explicitly Postgres-only (for example, the `SKIP LOCKED` job claim).

## Security Boundaries

- **Never read, print, or commit secrets.** Don't open `.env*` files; use `.env.example` for documentation.
- **Never hardcode API keys, tokens, or passwords.** Store API keys hashed, and show them to the user only once.
- **Test-case inputs and model outputs are untrusted data.** In judge prompts, wrap them in clear delimiters. Never give the judge tools.
- **No destructive commands without explicit approval.** This covers `rm -rf`, `git push --force`, `git reset --hard`, `docker volume rm`, dropping tables, and anything against production.
- **No deploying or touching AWS resources** unless explicitly asked.
- **The MCP server is scoped** to a single project API key and exposes read operations plus `start_run` only. Don't add delete or write tools without updating `docs/permissions.md`.
- **Enforce cost limits:** respect max cases per run and max spend per run. Don't raise the defaults silently.

## Definition of Done

- [ ] Code follows the layering and conventions above
- [ ] Lint, type-check and the relevant tests pass locally
- [ ] `openapi.yaml`, the generated client and the backend agree (when the API changed)
- [ ] Migration added (when the schema changed)
- [ ] `plan.md` checkbox ticked and `docs/ai-workflow.md` entry added
- [ ] README or this file updated if setup, commands or behavior changed
