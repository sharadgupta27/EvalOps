---
name: debug-ci-failure
description: Systematic procedure for a failing EvalOps GitHub Actions run (CI, E2E, security scans, eval gate, deploy). Use when a check is red, a PR is blocked, or someone pastes CI logs.
---

# Debug a CI failure

Goal: find the first real error, reproduce it locally, fix the cause (never the symptom),
and leave a regression test.

## 1. Identify the failing job and the first error

```bash
gh run list --limit 5
gh run view <run-id> --log-failed | head -200
```

Read from the top. The first error is usually the cause; later errors are fallout.

## 2. Map the job to a local command

| CI job | Reproduce locally |
|---|---|
| API contract | `npx @stoplight/spectral-cli@6 lint openapi.yaml`; `cd frontend && npm run gen:api && git diff src/api/schema.d.ts` |
| Backend lint/types | `cd backend && uv run ruff check . && uv run ruff format --check . && uv run mypy app tests` |
| Backend unit | `cd backend && uv run pytest -m "not integration" -x -q` |
| Backend integration | `cd backend && uv run pytest -m integration -x -q` (needs Docker) |
| Frontend | `cd frontend && npm run lint && npm run typecheck && npm run test && npm run build` |
| E2E | `docker compose up -d --build --wait && docker compose run --rm api python -m app.seed && cd e2e && npx playwright test` |
| Security | see `security/README.md` for the exact scanner commands |
| Eval gate | `python scripts/evalops_gate.py ...` against a local stack; read the printed reasons |

## 3. Classify

- **Contract drift** (`test_contract.py`): follow the `review-api-change` skill; fix the side
  that diverged from `openapi.yaml`.
- **Flaky test**: rerun once. If it passes, it is still a bug: find the race (timing,
  ordering, shared state) and fix it. Do not add retries or sleeps to hide it.
- **Eval gate fail**: the gate is doing its job. Open the compare link from the step summary;
  use the `triage-regression` MCP prompt. The fix is a better prompt, not a looser policy.
- **Security finding**: fix or document an explicit, justified exception in `security/`.
- **Environment** (missing secret, Docker, rate limit): fix the workflow, never weaken checks.

## 4. Fix and prove it

1. Write or adjust a test that fails for the reported reason.
2. Fix the code.
3. Run the local command from step 2 until green, then the full fast suite.

## Never

- Never delete, skip or weaken a failing test or check to turn CI green.
  If a test is wrong, explain why and ask first.
- Never lower gate thresholds or cost limits to pass.
- Never print secrets from CI logs.
