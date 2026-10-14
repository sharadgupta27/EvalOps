# Backlog

Vertical slices derived from [product-spec.md](../product-spec.md). Each item is small enough for one agent session and maps to a user story (US-n). Status is mirrored in [plan.md](../plan.md).

| ID | Slice | Story | Phase | Status |
|---|---|---|---|---|
| B-01 | Repo hygiene, spec, AGENTS.md, CLAUDE.md, ai-workflow log | n/a | 0 | done |
| B-02 | `openapi.yaml` covering US-1…US-8 + Spectral lint | all | 1 | done |
| B-03 | Vite/React/TS scaffold, generated client, query hooks | all | 1 | done |
| B-04 | Pages: Login, Projects, Project detail tabs, Dataset, Run, Compare | US-1…7 | 1 | done |
| B-05 | Vitest: formatting + compare-table logic + login form | US-6/7 | 1 | done |
| B-06 | FastAPI factory, settings, layering, error handler | n/a | 2 | done |
| B-07 | ORM models + first Alembic migration | all | 2 | done |
| B-08 | Auth (JWT) + project API keys (hashed, shown once) | US-1, US-8 | 2 | done |
| B-09 | CRUD: projects, versions, datasets, cases, evaluators | US-2…5 | 2 | done |
| B-10 | CSV/JSONL import with per-row errors | US-4 | 2 | done |
| B-11 | Contract drift test | n/a | 2 | done |
| B-12 | LLMProvider: Anthropic + Fake | US-6 | 3 | done |
| B-13 | Evaluator registry + 5 evaluators | US-5 | 3 | done |
| B-14 | Worker (SKIP LOCKED), concurrency, summary, cost guardrails | US-6 | 3 | done |
| B-15 | Judge calibration set + agreement script | US-5 | 3 | done |
| B-16 | Compare service + UI | US-7 | 4 | done |
| B-17 | Gate policy + `/gate` + eval-gate workflow | US-8 | 4 | done |
| B-18 | Integration tests (testcontainers) + Playwright E2E | n/a | 5 | done |
| B-19 | Dockerfiles, compose (dev/prod), seed | n/a | 6 | done |
| B-20 | CI + deploy workflows | n/a | 6 | done (first live deploy pending AWS setup) |
| B-21 | Metrics, tracing, dashboard, alert | n/a | 7 | done |
| B-22 | Agent extension pack (skills, subagents, MCP, hooks, plugin, custom agent) | US-9 | 8 | done |
| B-23 | Security scans, AI PR audit, data policy, hardening | n/a | 9 | done |
| B-24 | README, demo, Substack series | n/a | 10 | done |
