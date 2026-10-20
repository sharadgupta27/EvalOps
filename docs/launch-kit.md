# Launch kit: resume bullets and LinkedIn post

Drafts for Phase 10. Every number is taken from the repo as of 2026-10-20. Replace the
`[…]` placeholders before posting, and don't claim a judge-agreement figure until it has
been measured against a real model (see `backend/app/evaluators/calibration/README.md`).

## Resume bullets

**EvalOps: LLM regression-testing platform** (solo project, AI Dev Tools Zoomcamp 2026) ·
Python, FastAPI, PostgreSQL, React/TypeScript, Docker, GitHub Actions, OpenTelemetry

- Built a platform that versions prompts, runs them against golden datasets, scores every output
  with deterministic checks and an LLM judge, and blocks pull requests when quality drops.
- Designed the API contract first in OpenAPI 3.1, generated the TypeScript client from it, and
  added a CI test that fails on any drift between the contract and the FastAPI backend.
- Implemented a Postgres job queue (`SELECT … FOR UPDATE SKIP LOCKED`) with bounded-concurrency
  workers, per-run spend caps and a daily budget per project, with no Redis or broker to run.
- Wrote 134 automated tests: 84 backend tests at 90% coverage, including integration tests on
  real Postgres via testcontainers, 33 frontend tests, a Playwright end-to-end journey, and
  tests for the MCP server and agent hooks. All of them run in CI, alongside gitleaks,
  Semgrep, Trivy, pip-audit and npm audit.
- Instrumented API → worker → LLM calls as a single OpenTelemetry trace per run. Shipped
  Grafana dashboards, logs in Loki linked to traces, and Alertmanager alerts with a runbook.
- Packaged a Claude Code extension pack: 3 skills, 3 subagents, guardrail hooks, an MCP server
  scoped to one project API key, and a nightly agent that triages regressions into GitHub issues.

Short version (one line):

- Built EvalOps, an LLM regression-testing platform (FastAPI, Postgres, React, Docker) that
  gates pull requests on prompt quality. It has 134 automated tests, OpenTelemetry tracing and
  a Claude Code MCP/agent pack.

## LinkedIn post

Paste as plain text (LinkedIn ignores Markdown).

```text
Most teams test their code. Very few test their prompts.

Change one sentence in a system prompt and you can break JSON output, lose the polite tone or
double your token bill, and you usually find out from a user.

For the DataTalksClub AI Dev Tools Zoomcamp I built EvalOps, unit tests for prompts:

✅ Version prompts and keep a golden dataset of test cases
✅ Score every output with deterministic checks (JSON schema, regex, contains) and an LLM judge
✅ Compare two prompt versions case by case and see exactly what regressed
✅ A GitHub Action that fails the PR when quality drops below your thresholds

In the demo, a "make it shorter" prompt edit drops the pass rate from 100% to 0%. The CI
gate catches it before merge.

Under the hood: FastAPI, PostgreSQL as the job queue, React + TypeScript, Docker, OpenTelemetry
traces from API to LLM call, and 134 automated tests. I also built a Claude Code extension
pack (skills, subagents, hooks and an MCP server) so a coding agent can run evals and triage
regressions itself.

I wrote up every step as a beginner-friendly series, from spec to deployment: [Substack link]

Code: https://github.com/sharadgupta27/EvalOps
Live demo: [URL after deploy]

#LLM #AIEngineering #MLOps #Evals #Python #DataTalksClub
```
