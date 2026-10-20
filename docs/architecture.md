# Architecture

```text
 Browser ──HTTPS──▶ Caddy (TLS, prod) ──▶ nginx "frontend" ──/api──▶ FastAPI "api" ──▶ Postgres
                                          (React SPA, CSP)          │  ▲                ▲   │
 GitHub Actions / MCP / triage agent ──X-API-Key──────────────────┘  │ enqueue: INSERT │   │ claim:
                                                                      │ eval_runs       │   │ SELECT … FOR UPDATE
                                                                      │ (status=queued) │   │ SKIP LOCKED
                                                                      ▼                 │   ▼
                                                             Worker (same image, `python -m app.worker`)
                                                                      │ bounded concurrency (asyncio.Semaphore)
                                                                      ▼
                                                     LLMProvider ── AnthropicProvider (prod)
                                                                 └─ FakeProvider (tests, CI, demo)
 Observability: api & worker ─OTLP─▶ OTel Collector ─▶ Tempo (traces);  Prometheus scrapes /metrics;
                container stdout (JSON lines) ─▶ Alloy ─▶ Loki (logs);  Grafana links logs ⇄ traces by trace_id
                The API stores the W3C traceparent on the queued row, so API + worker spans form one trace
```

## Components

| Component | Tech | Responsibility |
|---|---|---|
| Frontend | React 18, TypeScript, Vite, TanStack Query, React Router 7, Tailwind 4 | UI. All HTTP goes through the client generated from `openapi.yaml` (`src/api/schema.d.ts` + `client.ts`) and is wrapped in query hooks (`src/api/hooks.ts`). Pure logic (`src/lib/`) is unit tested |
| API | FastAPI, Pydantic v2, async SQLAlchemy 2 | HTTP only in `api/routes.py`; business logic in `services/`; all SQL in `repositories/`. Domain exceptions map to HTTP in one handler |
| Worker | same image, asyncio | Claims queued runs, renders each case's prompt, calls the model, runs evaluators, writes results, summarises, enforces the per-run spend cap and the project's daily budget |
| Evaluators | registry + plugins | `exact_match`, `contains`, `regex`, `json_schema`, `llm_judge`. Config validated per type with Pydantic on create |
| LLM layer | Anthropic SDK behind `LLMProvider` | Only `app/llm/` imports the SDK. `InstrumentedProvider` adds spans and metrics (model, tokens, cost) |
| Database | PostgreSQL 16 (prod/dev), SQLite (unit tests) | Selected by `DATABASE_URL`; schema via Alembic migrations |
| Contract | OpenAPI 3.1 | Source of truth: Spectral lint, generated TS client, backend drift test |
| Containers | Docker, Compose | `db`, `migrate` (one-shot Alembic), `api`, `worker`, `frontend`; prod adds `caddy` |
| CI/CD | GitHub Actions | `ci.yml` (contract, backend, frontend, agent pack, E2E, security) → `deploy.yml` (GHCR images, Trivy, SSH roll-out, health check); `eval-gate.yml`; `nightly-triage.yml` |
| Observability | OpenTelemetry, Prometheus, Tempo, Loki + Alloy, Grafana, Alertmanager | `ops/`: traces, JSON logs in Loki (only `service` and `level` are labels; `trace_id`/`run_id` stay in the line), dashboard, 4 alert rules; Alertmanager routes `page` and `ticket` severities to separate receivers and suppresses `EvalQueueStuck` while `WorkerDown` fires; runbook |

## Key decisions

| Decision | Choice | Why / trade-off |
|---|---|---|
| Job queue | the `eval_runs` table itself + `SELECT … FOR UPDATE SKIP LOCKED` | No Redis/Celery to operate; transactional with the data; several workers can poll safely (integration test `test_skip_locked_claims_each_run_once`). Trade-off: polling latency (1 s) and DB load at very high volume |
| Async everywhere | async endpoints, `AsyncSession`, async worker | LLM calls are I/O-bound; one worker process evaluates many cases concurrently. Trade-off: no lazy-loaded relationships (repositories query explicitly) |
| One image, two roles | `uvicorn` vs `python -m app.worker` | identical code and dependencies; scale api and worker independently |
| Fake vs real LLM | `LLM_PROVIDER=fake` or `anthropic` | tests and the public demo are free and deterministic; the fake simulates instruction-following so demos are meaningful |
| Scores | every evaluator scores 0..1; case score = weighted mean; case passes only if every evaluator passes | comparable across evaluator types; compare uses pass/fail flips plus a 0.25 score-tolerance |
| Judge | structured JSON output (`output_config.format`), effort `low`, delimited untrusted data, no tools | reliability and injection resistance; calibrated against labels |
| No model fallback in eval runs | refusals become case errors | an eval must measure the configured model (the triage agent, which only summarises, does use fallback) |
| Immutable prompt versions | no update endpoint; the gate reuses a label only if content is identical | comparisons stay meaningful and auditable |
| Auth | JWT for humans; hashed, project-scoped API keys for machines | different credentials and permissions for people and automation |

## Request flow: "run v2 and compare"

1. UI `POST /projects/1/runs` → `RunService.queue_run` checks the version, dataset, case cap
   and that evaluators exist → inserts `eval_runs(status=queued)` → returns 202.
2. Worker `claim_next_run()` → `running` → `execute_run`: per case render → `provider.complete`
   → evaluators → write `eval_results`, update progress and spend (stop at the cap).
3. Summary (pass rate, mean per evaluator, p50/p95 latency, tokens, cost) stored on the run.
4. UI polls `GET /runs/{id}` every second while queued/running; then `GET /runs/compare`.

## Environments

| | dev (compose) | test | prod |
|---|---|---|---|
| DB | Postgres container | SQLite per test; Postgres via testcontainers for integration | Postgres container with volume (RDS is the stretch goal) |
| LLM | fake (switchable) | fake | anthropic or fake (public demo) |
| Secrets | defaults OK | test values | must be set: the app refuses the dev JWT secret |
| TLS | none | n/a | Caddy + Let's Encrypt |
