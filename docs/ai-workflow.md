# AI-assisted development workflow

How AI tools were used to build EvalOps: what was delegated, which context the agents had,
what the human reviewed, and how every step was verified. Graded as rubric criterion 2.

## Tools and context

| Tool | Used for |
|---|---|
| **Claude Code** (CLI + VS Code extension, Claude Opus 5.5) | primary coding agent: planning, implementation, tests, docs, scans |
| Built-in skills | `claude-api` (current Anthropic SDK usage, model ids, pricing) before writing `app/llm/` |
| Project agent extensions (this repo) | skills, subagents, hooks and MCP server, used from Phase 8 on |

**Context files the agent worked from:** `plan.md` (roadmap, phase checklist), `CLAUDE.md` →
`AGENTS.md` (rules: contract first, layering, never call a real LLM in tests, ask before
deps/schema/CI), `product-spec.md` (acceptance criteria), `openapi.yaml` (contract),
`docs/rubric.md` and `docs/module5-requirements.md` (grading).

## Working pattern

1. **Spec → plan → slice.** The human wrote `plan.md` and `CLAUDE.md`. The agent turned them
   into `product-spec.md` (user stories with testable acceptance criteria) and
   `docs/backlog.md` (24 vertical slices).
2. **Contract first.** `openapi.yaml` was written before any backend code; the TS client
   was generated from it; a drift test compares it with FastAPI's schema on every run.
3. **Small loops, tests inside the loop.** Each slice: implement → run ruff/mypy/tests → fix →
   next. The agent never declared a slice done without a green run.
4. **Verification beyond unit tests.** Postgres integration tests (testcontainers), the full
   Docker stack, a Playwright E2E of the happy path, the gate client against the live stack,
   the MCP server over real stdio, real security scanners, and an outage drill.
5. **Human review.** The author reviews every diff before commit; decisions on security
   findings are recorded in `security/pr-audit.md`.

## Log

Each entry: goal · prompt or delegation · what the AI produced · what was reviewed or changed · verification.

### 2026-10-14 · Phases 0–1: spec, agent context, contract, frontend
- **Prompt:** "Implement the EvalOps project using plan.md and follow CLAUDE.md … develop an
  agent extension pack … generate a step-by-step guide for Substack."
- **Produced:** `product-spec.md`, `AGENTS.md` (CLAUDE.md now imports it), backlog,
  `openapi.yaml` (22 paths, 35 operations, 41 schemas), React app with generated client and query hooks.
- **Reviewed / changed:** after reading the Claude API reference the agent changed the contract:
  `temperature` became nullable (default null) because current Claude models reject sampling
  parameters. Spectral `operation-description` was disabled with a justification (every
  operation has a summary).
- **Verified:** Spectral 0 errors; `tsc` strict, ESLint, 26 Vitest tests; production build.

### 2026-10-14 · Phase 2: backend core
- **Produced:** FastAPI factory, settings, async SQLAlchemy models, Alembic migration 0001,
  JWT auth, hashed project API keys, CRUD, CSV/JSONL import with per-row errors, contract test.
- **Issues found by running things:** method named `list` shadowed the builtin inside class
  annotations (renamed); a test helper treated `[]` as "use defaults" (fixed); Windows needed
  a selector event loop for async psycopg (`run_async` helper + pytest loop factory);
  bcrypt at 12 rounds made the unit suite 38 s, over the 30 s budget, so rounds became a setting
  (4 in tests; prod refuses < 12).
- **Verified:** contract test green; migration upgrade/downgrade on SQLite and Postgres.

### 2026-10-14 · Phase 3: eval engine and worker
- **Delegation:** the agent loaded the `claude-api` skill before writing the provider to get
  current model ids, pricing, structured outputs and error classes rather than recalling them.
- **Produced:** `LLMProvider`, `AnthropicProvider` (SDK retries/timeouts, structured JSON for
  the judge, refusal → error), deterministic `FakeProvider`, 5 evaluators in a registry,
  worker with `SKIP LOCKED`, bounded concurrency, spend cap, summaries; calibration set and script.
- **Decision (human-approved design):** no server-side model fallback for eval runs, because an
  eval must measure the configured model.
- **Honesty note:** the calibration labels were AI-drafted; agreement with FakeProvider (100%)
  is a pipeline check only. Recorded in `calibration/README.md`.
- **Verified:** 77 unit tests; 3 Postgres integration tests including concurrent claimers.

### 2026-10-14 · Phases 4–6: compare, gate, containers, CI/CD
- **Produced:** compare service and UI, gate policy and `/gate`, `scripts/evalops_gate.py`,
  Dockerfiles, dev/prod compose, Caddy, seed script, `ci.yml`, `deploy.yml`, `eval-gate.yml`.
- **Bugs found in integration:** nginx cached the API container's IP and returned 502 after
  the API was recreated (fixed with Docker DNS re-resolution); the gate client crashed on
  Windows printing emoji (UTF-8 stdout).
- **Verified:** `docker compose up` → seed → login → runs → compare through nginx; gate
  client: good prompt exit 0, terse prompt exit 1 with 30 regressions; Playwright E2E green.

### 2026-10-14 · Phase 7: observability
- **Produced:** metrics, OTel traces (`run.execute`, `case.evaluate`, `llm.complete` with
  model/token/cost attributes), collector + Tempo + Prometheus + Grafana, dashboard, alerts.
- **Finding during the drill design:** queue-age metric disappeared with the worker, so the
  queue alert could never fire when the worker was dead. Fixed (API exports it too) and proven
  by the drill (`security/ops-drill/`).
- **Follow-up (done):** the API stores the W3C `traceparent` on the queued run (`eval_runs.trace_context`,
  migration 0002) and the worker continues it, so one Tempo trace spans API → worker → LLM.
  Verified live: trace `4bf92f…` holds the API request, `run.execute`, 30 `case.evaluate`, 60 `llm.complete`.

### 2026-10-14 · Phase 8: agent extension pack
- **Produced:** 3 skills, 3 subagents, MCP server (7 tools, resource, prompt), 3 hooks + audit
  log + contract-approval flow, plugin + marketplace, custom triage agent, permissions doc.
- **API drift caught by running code:** `mcp` 2.x renamed `FastMCP` to `MCPServer`; the
  agent read the installed SDK instead of guessing.
- **Verified:** 7 MCP tests + stdio smoke test against the live stack; 9 hook tests; `claude
  plugin validate` passes for the plugin and marketplace; triage agent run on the live stack.
- **Not verified here:** the Claude path of the triage agent (no API key in this environment).

### 2026-10-14 · Phase 9: security
- **Produced:** real scan outputs, AI audit with decisions, threat model, data policy.
- **Fixed from findings:** rate-limit bypass via rotating fake API keys; upload parsed before
  size check; frontend image CVEs (41 → 0); react-router CVEs (v7); Vitest critical (v5);
  Semgrep blind spot (Python 3.12 generics); Prism removed from dev deps.
- **Accepted (author to confirm):** JWT in localStorage, no per-account lockout, Actions
  pinned by tag. (Tailwind 3 dev-only DoS advisories were accepted first, then fixed in the
  follow-ups below.)

### 2026-10-14 · Follow-ups after launch
- **Daily budget (T7):** `MAX_DAILY_COST_USD` per project per UTC day, checked when a run is
  queued (422), when the worker claims it (fails without calling the model) and after each
  case. Closes the "no daily budget" residual risk. Test:
  `test_daily_budget_blocks_new_runs_and_stops_queued_ones`.
- **Tailwind 4:** replaced the PostCSS setup with `@tailwindcss/vite`, renamed the utilities
  v4 changed (`rounded` → `rounded-sm`, `shadow-sm` → `shadow-xs`, `outline-none` →
  `outline-hidden`) and kept v3's border, placeholder and button-cursor defaults in
  `src/index.css`. `npm audit` (all deps) 7 → 0. The official upgrade tool was not used: it
  needs a clean tree or `--force`, so the 10 renames were done by hand and checked with E2E
  and fresh screenshots.
- **Alertmanager:** severity routing (`page`/`ticket`), grouping, repeat intervals and an
  inhibit rule (`WorkerDown` suppresses `EvalQueueStuck`); a stdlib webhook sink stands in for
  Slack locally. Drill re-run: one page, the symptom alert suppressed, one "resolved".

### 2026-10-20 · Phase 8: parallel worktree demo, backend half (`limit` on list runs)
- **Delegation:** the orchestrator session split the feature into two tasks and handed this
  one to a subagent working only in the git worktree `../evalops-backend` (branch
  `feat/runs-pagination`), while a second subagent did the frontend half in
  `../evalops-frontend` in parallel.
- **Produced (contract first):** optional `limit` query param (1–200) on `listRuns` in
  `openapi.yaml` → `npm run gen:api` (only `schema.d.ts` changed) → route
  (`Query(ge=1, le=200)`) → `RunService.list_all` → `Repo.runs`.
- **Reviewed / changed:** the subagent followed the brief ("omit to return all") and removed
  the repository's existing 100-run cap, making the list unbounded. The orchestrator rejected
  that in review (it undid a hardening guard) and set `default: 100` in the contract, route,
  service and repository, so omitting `limit` behaves exactly as before.
- **Verified:** new `test_list_runs_limit` (newest N, omitted = all 3, 0 and 201 → 422);
  contract drift test, full unit suite, ruff, ruff format, mypy, Spectral and frontend
  typecheck green.

### 2026-10-20 · Phase 8: parallel worktrees, frontend half (Compare CSV export)
- **Delegation:** the orchestrator session split one feature across two git worktrees and
  handed this half to a subagent in `../evalops-frontend` (branch `feat/compare-export`);
  the backend half ran in parallel in `../evalops-backend`. Brief: frontend only, no
  `openapi.yaml`/`src/api/` edits, no new dependencies, commit but don't push or merge.
- **Produced:** `compareCasesToCsv` + `csvCell` in `src/lib/compare.ts` (RFC 4180 quoting,
  CRLF, nulls as empty cells, `'` prefix on text cells starting with `= + - @ \t \r` because
  inputs and model outputs are untrusted); an "Export CSV" button in `CompareTable` that
  downloads the currently filtered and sorted rows as `compare-run-{base}-vs-{head}.csv`
  (Blob + object URL, revoked after the click), disabled when nothing matches.
- **Decision:** numeric cells (e.g. a negative delta) are not prefixed, so they stay numbers
  in a spreadsheet; only string cells can carry a formula.
- **Verified:** 7 new Vitest tests (CSV quoting, injection prefix, header, nulls; export uses
  only the filtered rows, file name, revoke, disabled state); `npm run test`, `lint`,
  `typecheck` and `prettier --check .` all green.

### 2026-10-20 · Plan audit: closing the last two code gaps
- **Goal:** the human asked whether anything in `plan.md` was missing. The audit found two gaps
  the checkboxes didn't show: the parallel worktree demo was documented but never run, and
  Loki was in the tech stack but not in `ops/`. The human asked to implement both.
- **Delegation:** the orchestrator ran the worktree demo (two subagents, entries above) and
  added Loki itself on `main` while they worked; the files don't overlap.
- **Produced (Loki):** `ops/loki.yaml` (single process, filesystem, 7-day retention),
  `ops/alloy.alloy` (Grafana Alloy tails the api/worker/frontend containers through the Docker
  socket, read-only; only `service` and `level` become labels, so `trace_id` and `run_id`
  stay in the line; drops entries older than 1 h so a container's replayed history doesn't
  trigger Loki 400s), `loki` and `alloy` services in the observability compose file, a Loki
  datasource with log → trace links to Tempo and trace → log links back, two dashboard panels,
  LogQL in the runbook, and log retention in the data policy.
- **Verified:** `loki -verify-config` and `alloy fmt` pass. The whole stack was brought up with the
  add-on, and a 30-case run was started. Its "run finished" worker line in Loki carried a
  `trace_id` that Tempo resolved to a 96-span trace. Every LogQL query in the runbook was
  run against Loki. The first attempt surfaced the replayed-history 400s, which led to the drop stage.
- **Found on the way:** the runbook's `grep "generation failed"` step never matches, because
  that text is stored on the result row and never logged. It is left as is for a separate fix.

## Prompts that worked well

- "Read plan.md and CLAUDE.md; implement one phase at a time, run the tests after each slice,
  and log decisions in docs/ai-workflow.md."
- "Before writing the Anthropic provider, load the claude-api skill and use only documented SDK calls."
- "Run the real scanners in Docker, save raw outputs under security/scans, fix what is
  fixable and document what is accepted, with a reason."

## What the human must still do

Review the diffs and the *Author to confirm* rows in `security/pr-audit.md`; review the
calibration labels; run the real-model calibration once; create the AWS resources and enable
`DEPLOY_ENABLED`; record the demo video.
