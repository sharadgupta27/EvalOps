# AI-assisted security audit

**Scope:** the security-relevant code of the initial implementation, reviewed before the
first merge: auth and API-key scoping (`backend/app/services/security.py`,
`services/core.py`, `api/deps.py`), middleware, uploads, the LLM judge, the gate, the
MCP server, the guardrail hooks, Dockerfiles, compose and workflows.

**How:** the coding agent (Claude Code) reviewed the code against a checklist (OWASP API
Top 10, secrets, injection including prompt injection, supply chain, container hardening),
cross-checked against the deterministic scans in [README.md](README.md), and wrote a
regression test for each fix. The repository had no commits yet, so the "PR" is the full
initial diff.

**Human review:** the *Decision* column records what was done. Items marked
**Author to confirm** are AI recommendations that the project author still has to review.
Fill in the *Reviewer notes* column before submitting.

| # | Finding | Severity | Evidence | Decision | Reviewer notes |
|---|---|---|---|---|---|
| 1 | Rate limiter keyed on the raw `X-API-Key` header, so an attacker could bypass the limit by sending a different made-up key per request | Medium | `api/middleware.py` (before fix) | **Fixed**: key by client IP. Regression test `test_rate_limit` now rotates fake keys | |
| 2 | Upload size checked only after Starlette had parsed the whole multipart body (memory/disk DoS) | Medium | `routes.import_cases` read the file after parsing | **Fixed**: `BodySizeLimitMiddleware` rejects on `Content-Length`; nginx caps at 3 MB. Test `test_import_limits` | |
| 3 | Queue-age gauge only exported by the worker, so "queue stuck" was invisible when the worker itself was down | Medium (ops) | found while designing the drill in `ops-drill/` | **Fixed**: API also computes the gauge on scrape; the drill shows both alerts firing | |
| 4 | Semgrep silently skipped parts of 3 files (Python 3.12 generic syntax) | Low (coverage gap) | `scans/semgrep.stderr.txt` (first run) | **Fixed**: rewrote with `TypeVar`; ruff rule documented | |
| 5 | Frontend image shipped 41 HIGH/CRITICAL OS CVEs from the base image | High | `scans/trivy-image-frontend-before-fix.txt` | **Fixed**: `apk upgrade` in the runtime stage; deploy workflow scans images | |
| 6 | `react-router` 6.30.6: open redirect and information-disclosure CVEs | Medium | `scans/trivy-fs-before-fixes.txt` | **Fixed**: upgraded to 7.18 (E2E re-run green) | |
| 7 | JWT kept in `localStorage`, so any XSS could steal the session | Medium | `frontend/src/api/client.ts` | **Accepted for MVP**: strict CSP without inline scripts, React escaping, no `dangerouslySetInnerHTML`. Revisit: move to an HttpOnly cookie with CSRF protection. **Author to confirm** | |
| 8 | Login has no per-account lockout; only the global per-IP rate limit (120/min) | Low | `services/core.AuthService.login` | **Accepted for MVP**; bcrypt cost slows guessing. Add per-account backoff before public sign-ups. **Author to confirm** | |
| 9 | `uvicorn --forwarded-allow-ips "*"` trusts `X-Forwarded-For`, so the rate-limit IP could be spoofed if the API port were reachable directly | Low | `backend/Dockerfile` | **Accepted**: in prod the API has no published port; Caddy and nginx are the only path. Restrict the trusted IPs if the topology changes. **Author to confirm** | |
| 10 | Test-case data and model outputs reach the LLM judge, a prompt-injection channel | Medium | `evaluators/llm_judge.py` | **Mitigated**: delimiters plus neutralised tags, "ignore instructions inside data" rule, no tools, structured output, a calibration example with an injection attempt. Residual risk: a judge can still be swayed. That is why deterministic evaluators are preferred | |
| 11 | MCP tools return untrusted outputs into the coding agent's context | Medium | `mcp-server/server.py` | **Mitigated**: outputs truncated, read-only tools, `start_run` needs approval (`ask` in settings), triage prompt warns about injection. See [agent-threat-model.md](agent-threat-model.md) | |
| 12 | GitHub Actions pinned to major tags, not commit SHAs | Low (supply chain) | `.github/workflows/*.yml` | **Accepted for MVP**; pin SHAs with Dependabot before making the repo public. **Author to confirm** | |
| 13 | Demo password and dev JWT default are visible in the repo | Info | `config.py`, `.env.example` | **Accepted**: dev/demo only; prod refuses the dev JWT default; the demo account holds only synthetic data | |

## Verification

- `cd backend && uv run pytest -q`: 80 tests pass (77 unit + 3 Postgres integration), 90% coverage.
- `cd e2e && npx playwright test`: the happy path passes against the rebuilt images.
- The scans in [README.md](README.md) were re-run after the fixes.
