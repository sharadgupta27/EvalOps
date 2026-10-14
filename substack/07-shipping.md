# Shipping It: Docker Compose, GitHub Actions and AWS for a Solo AI Engineer

*Part 7 of "Building EvalOps". Concepts: containers, multi-stage builds, Compose, CI vs CD, image registries, zero-click deploys, rollbacks.*

---

"Works on my machine" isn't shipped. This post turns EvalOps into something anyone can run
with one command, and that deploys itself when tests pass.

## Concept 1: containers, briefly

A container image bundles your code with *exactly* the runtime and libraries it needs. Same
image on your laptop, in CI and in production, so whole classes of bugs disappear.

### One backend image, two jobs

The API and the worker share all their code, so they share one image and differ only in the
command they start:

```yaml
api:     { command: uvicorn app.main:app --host 0.0.0.0 --port 8000 }   # default CMD
worker:  { command: ["python", "-m", "app.worker"] }
```

### Multi-stage builds

```dockerfile
FROM python:3.12-slim AS builder          # stage 1: has uv, installs dependencies
COPY --from=ghcr.io/astral-sh/uv:0.12 /uv /bin/uv
RUN uv sync --frozen --no-dev --no-install-project

FROM python:3.12-slim AS runtime          # stage 2: only the venv + code
RUN useradd --uid 10001 evalops
COPY --from=builder /app/.venv /app/.venv
COPY app ./app
USER evalops                              # never run as root
HEALTHCHECK CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/healthz')"
```

The final image has no build tools, runs as a non-root user, and reports its own health.

The frontend is built with Node, then served by an **unprivileged nginx** that also proxies
`/api` to the backend, so the browser talks to one origin and there's no CORS dance.

## Concept 2: Compose, a whole system in one file

```bash
docker compose up -d --build --wait
docker compose run --rm api python -m app.seed
```

That's the entire setup: Postgres, a **one-shot `migrate` service** (runs `alembic upgrade
head` and exits), the API, the worker and the frontend. `depends_on` with conditions encodes
the boot order: the API starts only after migrations *completed successfully*, and the
frontend only after the API is *healthy*. `--wait` blocks until everything is healthy, which
is exactly what CI needs.

**A bug worth knowing about:** after recreating the API container, the site returned **502**.
nginx resolves `api` to an IP *once at startup* and kept the old one. The fix is to use Docker's
DNS resolver and put the upstream in a variable so it's re-resolved:

```nginx
resolver 127.0.0.11 valid=10s ipv6=off;
set $api_upstream http://api:8000;
location /api/ { proxy_pass $api_upstream; }
```

## Concept 3: CI and CD are different promises

- **CI (continuous integration):** every PR is automatically checked.
- **CD (continuous deployment):** every green `main` is automatically released.

[ci.yml](../.github/workflows/ci.yml) runs six jobs in parallel:

| Job | Checks |
|---|---|
| contract | Spectral lint; the committed TS client equals a fresh `gen:api` |
| backend | ruff, mypy, unit tests with coverage, Postgres integration tests, judge calibration |
| frontend | ESLint + Prettier, `tsc`, Vitest with coverage, production build |
| agent-pack | plugin copies in sync, hook tests, MCP server tests |
| e2e | `docker compose up`, seed, Playwright |
| security | gitleaks, Semgrep, Trivy, pip-audit, npm audit (Part 11) |

[deploy.yml](../.github/workflows/deploy.yml) runs **only after CI succeeds on `main`**:

```text
build both images (tag = git SHA) → push to GHCR → Trivy scan (fail on CRITICAL)
→ scp compose file → ssh: docker compose pull && up -d --wait → curl https://domain/healthz
```

Tagging images with the commit SHA means every deploy is traceable, and **rollback is one
command**: `IMAGE_TAG=<previous-sha> docker compose up -d --wait`.

## Concept 4: the simplest production that's still production

For a solo project, a single **EC2 t3.small** running the same Compose file is a great
trade-off: about the price of a lunch per month, and nothing new to learn. **Caddy** in front
provides automatic HTTPS with Let's Encrypt from a 5-line config. Secrets live in a `.env` file
on the server (mode 600), never in git.

Production settings differ from dev in a few deliberate ways: `ENVIRONMENT=prod` (the app
refuses weak secrets), no published database or API ports, restart policies, log rotation,
and a lower spend cap for the public demo, which runs the fake model by default.

The full checklist (DNS, security group, Docker install, GitHub environment secrets, the
opt-in `DEPLOY_ENABLED` variable, rollback) is in [docs/deployment.md](../docs/deployment.md).
Graduating to ECS Fargate and RDS later means changing infrastructure, not code.

## What "reproducible" means

A reviewer should be able to clone the repo and, with only Docker installed:

1. start the system (`docker compose up`),
2. load demo data (`app.seed`),
3. run every test suite (commands in the README),
4. deploy it (`docs/deployment.md`).

If any step needs tribal knowledge, it isn't reproducible yet.

**Next:** [Part 8: Observability for LLM apps](08-observability.md).
