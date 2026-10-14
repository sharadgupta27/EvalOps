# Security, audit and DevOps hardening

Everything here was produced by running real tools against this repository on 2026-10-14.
Raw outputs are in [`scans/`](scans/). CI re-runs the same scanners on every PR
(`security` job in [`.github/workflows/ci.yml`](../.github/workflows/ci.yml)).

| Artifact | What it is |
|---|---|
| [scans/](scans/) | Raw output of gitleaks, Semgrep, Trivy (fs + both images), pip-audit, npm audit |
| [pr-audit.md](pr-audit.md) | AI-assisted security review of the codebase, with accept/reject decisions |
| [agent-threat-model.md](agent-threat-model.md) | Threats from our own coding agents, MCP server, hooks and the LLM judge |
| [ai-data-policy.md](ai-data-policy.md) | What data may go to which LLM, retention, secrets handling |
| [ops-drill/](ops-drill/) | Operational diagnosis: a simulated worker outage, as seen by monitoring |

## Deterministic scan results

| Scanner | Scope | First run | After fixes | Fixes |
|---|---|---|---|---|
| **gitleaks** 8.21 | all files | 0 leaks | 0 leaks | allowlisted 3 documented non-secrets in [.gitleaks.toml](../.gitleaks.toml) |
| **Semgrep** 1.99 (python, typescript, dockerfile, secrets) | 176 files | 0 findings, **3 files only partially parsed** | 0 findings, 0 parse errors | Semgrep's parser rejected Python 3.12 `def f[T]` generics. Rewrote 3 functions with `TypeVar` so SAST covers every line |
| **Trivy fs** (vuln, misconfig, secret) | lockfiles, Dockerfiles | 2 MEDIUM (react-router CVE-2026-53666, CVE-2026-53669), 1 HIGH misconfig (frontend Dockerfile without `USER`) | 0 | upgraded react-router 6.30 → 7.18; explicit `USER 101` |
| **Trivy image** backend | `evalops-backend:local` | 0 HIGH/CRITICAL | 0 | none needed |
| **Trivy image** frontend | `evalops-frontend:local` | **41** (39 HIGH, 2 CRITICAL) in Alpine 3.21 packages (openssl, libxml2, zlib, musl, …) | 0 | `apk upgrade` in the runtime stage |
| **pip-audit** | 66 production Python packages | 0 | 0 | none needed |
| **npm audit** (production deps) | frontend runtime | 0 | 0 | none needed |
| **npm audit** (incl. dev deps) | frontend toolchain | 24 (2 critical, 12 high) | **0** | removed Prism from devDependencies (now `npx` on demand); `npm audit fix`; Vitest 3 → 5 (fixes the critical tinypool RCE gadget); Tailwind 3 → 4 (follow-up, cleared the last 7) |

### Previously accepted risk, now fixed

The first pass left 7 dev-dependency findings (5 high, 2 moderate), all in Tailwind CSS 3's
build-time chain (`braces`, `micromatch`, `chokidar`, `postcss-selector-parser`):
denial-of-service via crafted glob patterns or CSS selectors. They only ran on developer
machines and in CI, on inputs we write ourselves, so we accepted them with a review date.
The follow-up migrated to Tailwind 4 with its Vite plugin (`@tailwindcss/vite`), which also
removed `postcss`, `autoprefixer` and both config files. `npm audit` including dev
dependencies now reports **0** ([scans/npm-audit-frontend-all.json](scans/npm-audit-frontend-all.json)).
CI still gates on `npm audit --omit=dev --audit-level=high`.

## Application hardening in place

- Passwords: bcrypt (12 rounds; the app refuses to start in prod with fewer). JWT HS256 with
  expiry; the app refuses to start in prod with the default or a short `JWT_SECRET`.
- API keys: 256-bit random, stored as SHA-256 hashes, shown once, revocable, scoped to one
  project, cannot manage the project (403 on writes other than runs and the gate).
- Other users' resources return 404, not 403, so their existence is not revealed.
- Rate limit per client IP (`RATE_LIMIT_PER_MINUTE`, keyed by IP so rotating fake API keys
  cannot bypass it). Request bodies over the upload limit are rejected from `Content-Length`
  before parsing; nginx caps bodies at 3 MB.
- Strict CORS allowlist (`CORS_ORIGINS`); security headers in the API and nginx; CSP without
  inline scripts on the frontend.
- Cost guardrails: `MAX_CASES_PER_RUN`; `MAX_COST_PER_RUN_USD` (a run that crosses the cap is
  stopped and marked failed); `MAX_DAILY_COST_USD` per project per UTC day (new runs are
  rejected and queued ones fail without calling the model once it is reached).
- Containers run as non-root; images are rebuilt with OS patches; CI scans images before deploy.
- LLM judge: untrusted text is delimited and its tags neutralised; the judge has no tools;
  tested by `test_untrusted_output_cannot_escape_delimiters`.

## Reproduce the scans

```bash
# from the repo root (on Git Bash for Windows, prefix docker commands with MSYS_NO_PATHCONV=1)
docker run --rm -v "$PWD:/repo" zricethezav/gitleaks:v8.21.2 dir /repo --config /repo/.gitleaks.toml --redact
docker run --rm -v "$PWD:/src" -w /src semgrep/semgrep:1.99.0 semgrep scan --config p/python --config p/typescript --config p/dockerfile --config p/secrets --metrics=off .
docker run --rm -v "$PWD:/src" aquasec/trivy:0.57.1 fs --scanners vuln,misconfig,secret --severity MEDIUM,HIGH,CRITICAL --skip-dirs "**/node_modules" --skip-dirs "**/.venv" --skip-dirs plugins /src
docker run --rm -v /var/run/docker.sock:/var/run/docker.sock aquasec/trivy:0.57.1 image --severity HIGH,CRITICAL --ignore-unfixed evalops-frontend:local
cd backend && uv export --frozen --no-dev --format requirements-txt > /tmp/req.txt && uvx pip-audit -r /tmp/req.txt
cd frontend && npm audit --omit=dev
```
