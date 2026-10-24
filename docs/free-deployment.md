# Free self-hosting (and reaching it from CI)

EvalOps needs a database and two small processes. It runs fine on a laptop or an always-on mini PC, and the only thing CI needs is a URL it can call. This page is the free route; the AWS route stays in [deployment.md](deployment.md).

```bash
cp .env.selfhost.example .env.selfhost       # POSTGRES_PASSWORD, JWT_SECRET (and tunnel keys, below)
docker compose --env-file .env.selfhost -f docker-compose.selfhost.yml up -d --build
docker compose --env-file .env.selfhost -f docker-compose.selfhost.yml run --rm api python -m app.seed   # optional demo data
```

UI at `http://localhost:5173`, API at `http://localhost:8000` (both bound to this machine only). `LLM_PROVIDER=fake` is the default: nothing is sent anywhere and nothing costs money.

## Letting GitHub Actions reach it

Choose one:

| Option | Cost | What you get | Start with |
|---|---|---|---|
| **Self-hosted runner on the same machine** | free | no public URL at all: CI calls `http://localhost:8000` | GitHub, Settings, Actions, Runners (private repositories only) |
| **Tailscale Funnel** | free | a stable `https://<name>.<tailnet>.ts.net`, no domain needed | `--profile funnel`, `TS_AUTHKEY` |
| **Cloudflare Tunnel** | free tunnel; needs a domain on Cloudflare | your own hostname | `--profile tunnel`, `TUNNEL_TOKEN`, route the hostname to `http://frontend:8080` |

```bash
docker compose --env-file .env.selfhost -f docker-compose.selfhost.yml --profile funnel up -d
```

Set `PUBLIC_URL` in `.env.selfhost` to the public address (it feeds CORS), then use that address as `EVALOPS_URL` in the calling repository (for CiteSure: `docs/free-deployment.md` there). The two tunnel containers need your Tailscale or Cloudflare account, so they were configured but not started here; the rest of the stack was built and run, and CiteSure's gate was exercised against it (pass, pass against a baseline, fail on a regression).

## Keep it safe when it is reachable

- Create a **project API key** per caller; it is shown once and stored hashed. The gate endpoints accept only that key.
- Keep `DEMO_PASSWORD` empty and skip the seed on a reachable instance.
- `RATE_LIMIT_PER_MINUTE`, `MAX_COST_PER_RUN_USD` and `MAX_DAILY_COST_USD` are set conservatively in the self-host compose file.
- Restrict the UI (not `/api/v1/gate/*`) with Cloudflare Access or a Tailscale ACL if only you use it.
- The machine must be on when CI runs: an unreachable EvalOps fails the CiteSure job on purpose (exit code 2), it does not skip the gate.

## Private data

EvalOps stores whatever CI sends. CiteSure can send only hashes, pass/fail and scores (`PRIVATE_MODE=true` or `--redact`), which is all the gate needs. With `LLM_PROVIDER=anthropic` here, the cases you run are sent to Anthropic, so keep real company questions out of such projects. See [security/ai-data-policy.md](../security/ai-data-policy.md).
