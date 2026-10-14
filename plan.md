# EvalOps: Project Plan

> LLM regression-testing platform. Final project for the DataTalksClub AI Dev Tools Zoomcamp (2026).
> Working name: **EvalOps**. Rubric: [docs/rubric.md](docs/rubric.md). Module 5 deliverable: [docs/module5-requirements.md](docs/module5-requirements.md).

---

## 1. Problem

Teams ship prompts and RAG pipelines the way people shipped code before unit tests: change a prompt, eyeball a few outputs, deploy, and hope. Regressions such as worse accuracy, broken JSON, hallucinations or cost spikes are found by users, not by CI.

**EvalOps** lets a team:

1. Version prompts (template + model + parameters).
2. Maintain golden datasets of test cases.
3. Run evaluations with deterministic checks and LLM-as-judge scoring.
4. Compare two versions side by side and see exactly which cases regressed.
5. Gate CI: a GitHub Action calls EvalOps and fails the PR if quality drops below thresholds.

**Target user:** an AI engineer on a product team who owns one or more LLM features.

### Expected behavior (happy path)

1. The user signs up and creates a project, for example "Support reply generator".
2. The user creates prompt version `v1` and uploads a dataset of 30 test cases (CSV/JSONL).
3. The user attaches evaluators: `json_schema`, `contains`, and `llm_judge` (rubric: "Is the reply polite and correct?").
4. The user starts a run. A worker executes every case, scores it and stores the results. The UI shows progress, then a pass rate, average score, latency, tokens and cost.
5. The user creates `v2`, runs it, and opens **Compare v1 → v2**. The UI shows a diff table of improved and regressed cases.
6. CI calls `POST /api/v1/gate` with a project API key. The response is `pass` or `fail` with reasons, and the GitHub Action exits accordingly.

### Non-goals (MVP)

- Hosting customer LLM apps or tracing production traffic.
- Embedding-based similarity scoring (stretch goal).
- Multi-tenant orgs/teams and billing (one user owns many projects).
- Fine-tuning.

---

## 2. Architecture

```text
┌──────────────┐  generated TS client  ┌────────────────────┐
│ React (Vite) │ ───────────────────▶ │ FastAPI  (api)     │──┐
│  frontend/   │ ◀─────────────────── │  backend/app       │  │ SQLAlchemy
└──────────────┘       JSON / REST     └────────┬───────────┘  ▼
                                                │ enqueue  ┌───────────┐
 GitHub Action ── API key ──▶ /api/v1/gate      └─────────▶│ Postgres  │
                                                           │ (jobs +   │
                          ┌────────────────────┐  poll     │  data)    │
                          │ Worker (same image)│◀─────────▶└───────────┘
                          │ runs evals         │
                          └─────────┬──────────┘
                                    │ LLMProvider interface
                         ┌──────────┴──────────┐
                         │ AnthropicProvider   │  (prod)
                         │ FakeProvider        │  (tests, demo, CI)
                         └─────────────────────┘
```

**Key design decisions**

| Decision | Choice | Why |
|---|---|---|
| Job queue | Postgres table + `SELECT … FOR UPDATE SKIP LOCKED` worker | No Redis to run; it's a real pattern used in industry and it's easy to explain |
| LLM access | `LLMProvider` protocol with real and fake implementations | Tests never hit a paid API, and the public demo can run without a key |
| Contract | `openapi.yaml` is the source of truth; the TS client is generated from it | Satisfies rubric criteria 4 and 5, and stops frontend/backend drift |
| DB per environment | `DATABASE_URL`: SQLite for unit tests, Postgres for compose/prod | Satisfies rubric criterion 7 |
| Auth | Email/password with JWT for the UI; per-project API keys for CI | Machines and humans get different credentials |

---

## 3. Tech Stack

| Layer | Tech |
|---|---|
| Frontend | React 18 + TypeScript + Vite, TanStack Query, React Router, Tailwind, `openapi-typescript` + `openapi-fetch` |
| Frontend tests | Vitest + React Testing Library; Playwright for E2E |
| Backend | Python 3.12, FastAPI, Pydantic v2, SQLAlchemy 2.0, Alembic, `uv` |
| Backend tests | pytest, httpx `TestClient`, testcontainers (Postgres) for integration |
| LLM | Anthropic SDK behind `LLMProvider`; models set by env (`JUDGE_MODEL`, `DEFAULT_MODEL`) |
| Database | PostgreSQL 16 (SQLite for fast unit tests) |
| Containers | Docker, Docker Compose (`api`, `worker`, `frontend`/nginx, `db`) |
| CI/CD | GitHub Actions: lint → test → build → push to GHCR → deploy |
| Hosting | AWS EC2 (t3.small) running Compose behind Caddy (HTTPS). Stretch: ECS Fargate + RDS |
| Observability | OpenTelemetry → Prometheus / Loki / Tempo / Grafana (`ops/`) |
| Security | gitleaks, Semgrep, Trivy, pip-audit, npm audit |

---

## 4. Data Model

```text
users            id, email, password_hash, created_at
projects         id, owner_id→users, name, description, created_at
api_keys         id, project_id, name, key_hash, last_used_at, revoked_at
prompt_versions  id, project_id, label (v1, v2…), template, model, params JSON, created_at
datasets         id, project_id, name, created_at
test_cases       id, dataset_id, inputs JSON, expected_output, tags[], created_at
evaluators       id, project_id, type ENUM, name, config JSON, weight
                 type ∈ {exact_match, contains, regex, json_schema, llm_judge}
eval_runs        id, project_id, prompt_version_id, dataset_id, status ENUM,
                 triggered_by ENUM{ui, ci, agent}, git_sha, summary JSON,
                 total_tokens, cost_usd, trace_context JSON (W3C traceparent),
                 created_at, started_at, finished_at
                 status ∈ {queued, running, succeeded, failed}
eval_results     id, run_id, test_case_id, output, scores JSON, passed BOOL,
                 latency_ms, tokens_in, tokens_out, cost_usd, error
gate_policies    id, project_id, min_pass_rate, max_regressions, max_cost_increase_pct
```

---

## 5. API Surface (`/api/v1`)

| Method & path | Purpose |
|---|---|
| `POST /auth/register`, `POST /auth/login` | User auth (JWT) |
| `GET/POST /projects`, `GET/PATCH/DELETE /projects/{id}` | Projects |
| `GET/POST /projects/{id}/prompt-versions` | Versions are immutable once created |
| `GET/POST /projects/{id}/datasets`, `POST /datasets/{id}/import` | CSV/JSONL upload |
| `GET/POST/PATCH/DELETE /datasets/{id}/cases` | Test cases |
| `GET/POST/PATCH/DELETE /projects/{id}/evaluators` | Evaluator config |
| `POST /projects/{id}/runs`, `GET /runs/{id}`, `GET /runs/{id}/results` | Start a run and poll progress |
| `GET /runs/compare?base={id}&head={id}` | Regression diff |
| `GET/PUT /projects/{id}/gate-policy` | Thresholds |
| `POST /gate` (API key) | CI entry point: run head, compare to baseline, return pass/fail |
| `POST/DELETE /projects/{id}/api-keys` | CI keys (shown once) |
| `GET /healthz`, `GET /metrics` | Ops |

---

## 6. Repository Layout

```text
README.md                 # problem, architecture, run/test/deploy, AI workflow summary
product-spec.md
AGENTS.md                 # portable agent instructions
CLAUDE.md                 # Claude Code–specific (imports AGENTS.md)
plan.md                   # this file
openapi.yaml
docker-compose.yml
docker-compose.prod.yml
frontend/
backend/
  app/{api,services,repositories,models,schemas,evaluators,llm,worker}/
  migrations/
  tests/{unit,integration}/
e2e/                      # Playwright
.github/workflows/{ci.yml,deploy.yml,eval-gate.yml}
ops/                      # otel collector, grafana dashboards, alert rules
security/                 # scan outputs, PR audit, ai-data-policy.md
docs/
  ai-workflow.md          # prompts, delegation, review log  (rubric criterion 2)
  architecture.md
  agent-extension-pack.md
  permissions.md
  demo.md
agent-capabilities/
  add-eval-case/SKILL.md
  review-api-change/SKILL.md
  debug-ci-failure/SKILL.md
  subagents/{eval-reviewer.md, api-contract-reviewer.md, qa-tester.md}
agent-hooks/
mcp-server/{server.py, README.md}
plugins/evalops-agent-pack/
custom-agent/{agent.py, README.md}
substack/                 # article drafts, one per phase
```

---

## 7. Phases

Each phase ends with a commit, a `docs/ai-workflow.md` entry and a Substack chapter draft.
Effort estimates assume part-time work (about 10 h/week).

### Phase 0: Spec & Agent Context (≈ 0.5 week)
- [x] `git init`, `.gitignore`, `.editorconfig`, MIT license
- [x] `product-spec.md`: personas, user stories, acceptance criteria
- [x] Break the spec into a backlog (GitHub Issues or `docs/backlog.md`)
- [x] `AGENTS.md` (portable) and `CLAUDE.md` (imports AGENTS.md)
- [x] Start `docs/ai-workflow.md`

**Done when:** an agent with no other context can explain the project and pick up a task.
**Rubric:** 1, 2 · **Guide chapter:** *"From vague idea to spec: AI-native project kickoff"*. Concepts: specs as prompts, context files, backlog slicing.

### Phase 1: API Contract & Frontend Prototype (≈ 1 week)
- [x] Write `openapi.yaml` from the user stories (contract first)
- [x] Lint the contract with Spectral in CI
- [x] Scaffold Vite + React + TS, and generate the client into `frontend/src/api/`
- [x] Mock server (Prism) so the frontend can be built before the backend
- [x] Pages: Login, Projects, Project detail (Versions / Datasets / Evaluators / Runs), Run detail, Compare
- [x] Vitest tests for core UI logic (score formatting, compare-table diffing)

**Done when:** the full UI flow works against the mock server.
**Rubric:** 4, 5 · **Guide chapter:** *"Contract-first development: why OpenAPI keeps AI-generated code honest"*.

### Phase 2: Backend Core (≈ 1.5 weeks)
- [x] FastAPI app factory, settings via `pydantic-settings`, layered `api → services → repositories`
- [x] SQLAlchemy models plus the first Alembic migration
- [x] Auth (JWT) and project API keys (hashed, shown once)
- [x] CRUD endpoints for projects, versions, datasets, cases and evaluators
- [x] CSV/JSONL import with validation errors reported per row
- [x] Contract test: the FastAPI-generated schema must match `openapi.yaml` (fails CI on drift)
- [x] Unit tests (SQLite)

**Done when:** the frontend runs against the real backend with the mock server removed.
**Rubric:** 6, 7 · **Guide chapter:** *"Building a FastAPI backend from a contract with a coding agent"*.

### Phase 3: Eval Engine & Worker (≈ 1.5 weeks)
- [x] `LLMProvider` protocol, with `AnthropicProvider` (retries, timeouts, token/cost capture) and `FakeProvider` (deterministic)
- [x] Evaluator plugins: `exact_match`, `contains`, `regex`, `json_schema`, `llm_judge` (rubric prompt that returns structured JSON: `{score: 1-5, reasoning}`)
- [x] Worker: claims jobs with `SKIP LOCKED`, runs cases with bounded concurrency, writes results, updates the run summary
- [x] Run-level summary: pass rate, mean score per evaluator, p50/p95 latency, tokens, cost
- [x] Cost guardrails: max cases per run, max spend per run and a daily budget per project (configurable)
- [ ] Judge calibration: a small human-labelled set and agreement % reported in the README _(status: set + script done; labels AI-drafted, need human review; real-model agreement not yet measured)_

**Done when:** a 30-case run finishes end to end and the UI shows live progress.
**Rubric:** 6 · **Guide chapter:** *"How to evaluate LLM output: deterministic checks vs LLM-as-judge (and why judges need judging)"*.

### Phase 4: Compare, Regressions & CI Gate (≈ 1 week)
- [x] Compare service: per-case delta, regressed / improved / unchanged buckets
- [x] Compare UI with filters and a side-by-side output diff
- [x] Gate policy and the `POST /gate` endpoint
- [x] `.github/workflows/eval-gate.yml`: **dogfooding**, where EvalOps evaluates its own `llm_judge` prompt on every PR that touches `backend/app/evaluators/prompts/`

**Done when:** a deliberately worse prompt fails the PR check.
**Rubric:** 11 · **Guide chapter:** *"Unit tests for prompts: gating pull requests on LLM quality"*.

### Phase 5: Testing Depth (≈ 1 week)
- [x] `backend/tests/unit/` vs `backend/tests/integration/` (testcontainers Postgres), with separate pytest markers and commands
- [x] Integration tests for the key workflows: import → run → compare → gate
- [x] Playwright E2E for the happy path from section 1 (using FakeProvider)
- [x] Coverage report in CI; document every test command in the README

**Rubric:** 4, 6, 9 · **Guide chapter:** *"A testing pyramid for AI apps: what to mock and what never to mock"*.

### Phase 6: Containerize, Deploy, CI/CD (≈ 1 week)
- [x] Multi-stage Dockerfiles (backend image runs as `api` or `worker` via command)
- [x] `docker-compose.yml` (dev) and `docker-compose.prod.yml`; `docker compose up` gives a working system
- [x] Seed script with a demo project and dataset
- [x] `ci.yml`: lint, type-check, unit and integration tests, Playwright, image build
- [ ] `deploy.yml`: on `main` with green tests, push to GHCR, SSH deploy to EC2, run migrations, health check _(status: workflow ready; needs AWS resources + `DEPLOY_ENABLED=true` (docs/deployment.md))_
- [ ] Public demo: FakeProvider by default, plus a rate-limited real-model mode _(status: FakeProvider default + rate limit + spend caps done; public URL pending)_

**Done when:** a merged PR is live on the public URL without manual steps.
**Rubric:** 8, 10, 11, 14 · **Guide chapter:** *"Shipping it: Docker Compose, GitHub Actions and AWS for a solo AI engineer"*.

### Phase 7: Observability (≈ 0.5 week)
- [x] OpenTelemetry tracing across api → worker → LLM call (span attributes: model, tokens, cost)
- [x] Grafana dashboard: run throughput, LLM latency, error rate, spend per day
- [x] One actionable alert (for example, worker queue age > 5 min)
- [x] Separate dev and prod environment configs

**Rubric:** 13 (operational diagnosis) · **Guide chapter:** *"Observability for LLM apps: tracing tokens and dollars"*.

### Phase 8: Agent Extension Pack (≈ 1.5 weeks)

| Requirement | Implementation |
|---|---|
| Project instructions | `AGENTS.md` + `CLAUDE.md` |
| Reusable workflow ×3 | `add-eval-case` (adds cases from a bug report), `review-api-change` (contract + migration + client regen checklist), `debug-ci-failure` |
| Specialized subagents | `eval-reviewer` (critiques judge prompts and rubrics), `api-contract-reviewer` (read-only, reviews openapi diffs), `qa-tester` |
| MCP server | `mcp-server/server.py` (Python MCP SDK). Tools: `list_projects`, `start_run`, `get_run_summary`, `compare_runs`, `get_regressions`. Resource: `evalops://runs/{id}`. Prompt: `triage-regression`. Scoped to a single project API key |
| Hooks / guardrails | PreToolUse: block edits to `.env*`, `migrations/` history and `openapi.yaml` without the contract-review skill. PostToolUse: run ruff/prettier on edited files. Stop: run the fast test suite |
| Plugin | `plugins/evalops-agent-pack/` bundles the skills, subagents, hooks and MCP config for reuse in other repos |
| Custom agent | `custom-agent/agent.py`: nightly scheduled job (GitHub Actions cron) that runs evals, finds regressions and opens an issue with a triage summary |
| Permissions note | `docs/permissions.md`: what each agent, tool and key may do, and why |
| Parallel work | Demonstrate 2 subagents in separate git worktrees (for example, a frontend task and a backend task) |

**Demo** (`docs/demo.md`): follow the 6-step Module 5 demo script using a real regression.
**Rubric:** 12 · **Guide chapters:** *"Skills vs subagents vs MCP vs hooks: a mental model"* and *"Building an MCP server for your own app"*.

### Phase 9: Security, Audit & Hardening (≈ 0.5 week)
- [x] Deterministic scans in CI: gitleaks, Semgrep, Trivy (images), pip-audit, npm audit; save outputs in `security/`
- [ ] AI PR audit: an agent reviews a real PR, and you save the output plus your accept/reject notes _(status: audit done in security/pr-audit.md; author still to fill reviewer notes)_
- [x] Agent and extension threat notes: prompt injection via test-case data into the judge, MCP key scoping, hook bypass
- [x] `security/ai-data-policy.md`: what data may be sent to which LLM, retention, secrets handling
- [x] App hardening: rate limits, upload size limits, a strict CORS allowlist, hashed API keys

**Rubric:** 13 · **Guide chapter:** *"Threat-modeling an AI app (including your own coding agents)"*.

### Phase 10: Docs, Demo & Launch (≈ 0.5 week)
- [ ] README: problem, screenshots, architecture diagram, live URL, numbers (judge agreement %, test count, coverage) _(status: live URL pending deploy)_
- [ ] 2-minute demo video _(status: script in docs/demo.md)_
- [ ] Polish and publish the Substack series; link the repo _(status: drafts in substack/)_
- [ ] Resume bullets and a LinkedIn post

**Rubric:** 1, 3, 14

---

## 8. Rubric Coverage

| # | Criterion | Where it is satisfied |
|---|---|---|
| 1 | Problem description | README, product-spec.md |
| 2 | AI-assisted workflow | docs/ai-workflow.md, AGENTS.md |
| 3 | Technologies & architecture | README, docs/architecture.md |
| 4 | Frontend (3 pts) | Phase 1 + Vitest |
| 5 | API contract | openapi.yaml + drift test |
| 6 | Backend (3 pts) | Phases 2–3 + pytest |
| 7 | Database | Postgres/SQLite via env, Alembic |
| 8 | Containerization | docker-compose.yml |
| 9 | Integration tests | backend/tests/integration, e2e/ |
| 10 | Deployment | AWS EC2 public URL |
| 11 | CI/CD | ci.yml + deploy.yml + eval-gate.yml |
| 12 | Agent extension pack | Phase 8 |
| 13 | Security / audit / DevOps | security/, ops/ |
| 14 | Reproducibility | README "Run / Test / Deploy" sections |

---

## 9. Risks & Mitigations

| Risk | Mitigation |
|---|---|
| LLM API cost during dev and demo | FakeProvider by default, per-run spend cap, daily budget per project, small datasets |
| Flaky LLM-judge scores | temperature 0, structured output, calibration set, report agreement % |
| Scope creep | Non-goals list; stretch items only after Phase 10 |
| AWS cost | t3.small + Compose; stop the instance after review period |
| Prompt injection via test-case data | Delimit untrusted input in judge prompts, never give the judge tools |

## 10. Stretch Goals
- Embedding similarity evaluator (pgvector)
- RAG-specific metrics: faithfulness, context recall
- Multiple providers (OpenAI, local Ollama) behind `LLMProvider`
- Human review queue to label disagreements and improve the judge
