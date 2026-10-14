# EvalOps: Product Spec

> Status: v1.0 (MVP). Owner: project author. Source of truth for *what* we build; [plan.md](plan.md) is *how and when*.

## 1. Problem

LLM features (prompts, RAG pipelines, agents) change constantly, but most teams have no automated way to know whether a change made things better or worse. They edit a prompt, look at three outputs, and ship. Regressions (wrong answers, broken JSON, rude tone, cost spikes) are discovered by users.

Classic software solved this with unit tests and CI. **EvalOps brings the same discipline to prompts**: version them, test them against a golden dataset, compare versions, and block a pull request when quality drops.

## 2. Personas

| Persona | Goal | Pain today |
|---|---|---|
| **Priya, AI engineer** (primary) | Ship prompt changes quickly without breaking production | Manual spot checks; no history of which prompt version scored what |
| **Marco, tech lead** | Make sure nobody merges a prompt that degrades quality | No objective gate in CI; reviews are opinion-based |
| **CI bot** (machine user) | Run the eval suite on every PR and return pass/fail | Needs a stable API and a scoped credential, not a human password |

## 3. User Stories and Acceptance Criteria

### US-1 Account
*As Priya, I can register and log in so that my projects are private.*
- AC1: `POST /auth/register` with email + password (≥ 8 chars) creates a user; duplicate email → 409.
- AC2: `POST /auth/login` returns a JWT; wrong password → 401.
- AC3: All project endpoints require a valid JWT; other users' projects return 404.

### US-2 Projects
*As Priya, I can create a project per LLM feature.*
- AC1: Create, list, rename, delete projects.
- AC2: Deleting a project deletes its versions, datasets, evaluators and runs.

### US-3 Prompt versions
*As Priya, I can save prompt versions so I can compare them later.*
- AC1: A version has a label (`v1`), a template with `{{variables}}`, a model name and params (temperature, max_tokens).
- AC2: Versions are **immutable**; there is no update endpoint. Labels are unique per project.
- AC3: If the model is omitted, the server default (`DEFAULT_MODEL`) is used.

### US-4 Datasets and test cases
*As Priya, I can maintain a golden dataset.*
- AC1: Create a dataset, add/edit/delete cases manually. A case has `inputs` (object), optional `expected_output`, and `tags`.
- AC2: Import a CSV or JSONL file. Valid rows are imported; invalid rows are reported with row number and reason. Max upload 2 MB.

### US-5 Evaluators
*As Priya, I can define how outputs are scored.*
- AC1: Types: `exact_match`, `contains`, `regex`, `json_schema`, `llm_judge`.
- AC2: Each evaluator has a `weight` and a `config` validated per type (e.g. `regex` requires `pattern`, `llm_judge` requires `rubric`).
- AC3: A case **passes** when every evaluator passes. `llm_judge` passes when score ≥ `threshold` (default 4 on a 1–5 scale).

### US-6 Runs
*As Priya, I can run a prompt version against a dataset and watch progress.*
- AC1: `POST /projects/{id}/runs` returns immediately with status `queued`. A background worker executes it.
- AC2: `GET /runs/{id}` shows status, progress (done/total) and, when finished, a summary: pass rate, mean score per evaluator, p50/p95 latency, tokens, cost.
- AC3: Runs larger than `MAX_CASES_PER_RUN` are rejected (422). A run stops and is marked failed if it exceeds `MAX_COST_PER_RUN_USD`.
- AC4: Errors on individual cases are recorded per case and do not crash the run.

### US-7 Compare
*As Priya, I can compare two runs to see exactly which cases regressed.*
- AC1: `GET /runs/compare?base=&head=` returns per-case base/head pass + score, and a bucket: `regressed`, `improved`, `unchanged`.
- AC2: Only runs on the same dataset can be compared (else 422).
- AC3: The UI shows bucket counts, filters, and base vs head output side by side.

### US-8 CI gate
*As Marco, I can block a PR when quality drops.*
- AC1: A project has a gate policy: `min_pass_rate`, `max_regressions`, `max_cost_increase_pct`.
- AC2: `POST /gate` authenticated by a **project API key** (header `X-API-Key`) takes a prompt version (label or full template), dataset and baseline, runs synchronously-with-polling and returns `pass`/`fail` with reasons.
- AC3: API keys are shown once at creation, stored hashed, and can be revoked.

### US-9 Agent access
*As Priya, I can ask my coding agent "did my last change regress anything?"*
- AC1: An MCP server exposes read tools + `start_run`, scoped to a single project API key.

## 4. Expected Behavior (happy path)

See [plan.md §1](plan.md#expected-behavior-happy-path). The Playwright E2E test automates this path.

## 5. Non-functional Requirements

| Area | Requirement |
|---|---|
| Cost | Tests and the public demo use `FakeProvider` (no paid API). Per-run case and spend caps. |
| Security | Hashed passwords (bcrypt) and API keys (SHA-256), JWT expiry, CORS allowlist, upload limit, untrusted data delimited in judge prompts. |
| Performance | Unit test suite < 30 s. A 30-case FakeProvider run finishes in < 5 s. |
| Portability | `docker compose up` gives a working system on Windows, macOS and Linux. |
| Observability | `/healthz`, Prometheus `/metrics`, OpenTelemetry traces (optional exporter). |

## 6. Out of Scope (MVP)

Production traffic tracing, embeddings-based similarity, multi-tenant orgs and billing, fine-tuning.
