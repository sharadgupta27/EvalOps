# Runbook

Alerts are defined in [ops/prometheus/alerts.yml](../ops/prometheus/alerts.yml); the
dashboard is *EvalOps overview* in Grafana. Commands assume the prod compose file
(`C="docker compose -f docker-compose.prod.yml"`); in dev drop the `-f`.

## queue-stuck
**`EvalQueueStuck`**: oldest queued run > 5 minutes.
1. Is the worker up? `$C ps worker`. If not, see [worker-down](#worker-down).
2. Is it busy with one huge run? Grafana "Cases by outcome / min" > 0 means it is working.
   Look at `$C logs worker --tail 100` for the `claimed run` id.
3. Stuck on a slow provider? "LLM latency p95" near the timeout (120 s) → check provider
   status; consider lowering `WORKER_CONCURRENCY` if rate-limited (429s in logs).
4. Scale out: `$C up -d --scale worker=2` (safe: claims use `SKIP LOCKED`).

## worker-down
**`WorkerDown`**: Prometheus cannot scrape the worker.
1. `$C ps worker` and `$C logs worker --tail 100`.
2. Crash on start: usually DB connectivity or a bad env var. Compare `.env` with `.env.example`.
3. `$C up -d worker`. Queued runs resume automatically. A run left in `running` by a crash
   needs a reset: `UPDATE eval_runs SET status='queued' WHERE status='running' AND started_at < now() - interval '30 min';`
   (re-claiming is idempotent: old results for that run are deleted first).
Drill: [security/ops-drill/](../security/ops-drill/).

## llm-errors
**`LLMErrorRateHigh`**: more than 20% of model calls fail.
1. `$C logs worker | grep "generation failed"` for the reason (auth, 429, 5xx, refusal).
2. Authentication → rotate `ANTHROPIC_API_KEY` in `.env`, `$C up -d api worker`.
3. 429 → lower `WORKER_CONCURRENCY`; 5xx → provider incident, wait (the SDK already retries).

## spend-spike
**`LLMSpendSpike`**: more than $20 per hour.
1. Grafana "Spend per hour by model": which model?
2. `GET /api/v1/projects/{id}/runs`: who triggered (`triggered_by`, `git_sha`)? A CI loop?
3. Revoke the offending API key in the UI; lower `MAX_COST_PER_RUN_USD` or `MAX_DAILY_COST_USD`; check the gate workflow.
   The daily budget already stops a project at `MAX_DAILY_COST_USD` per UTC day: runs then fail with
   "daily budget reached", which is the signal to investigate rather than raise the cap.

## Useful commands

```bash
$C exec db psql -U evalops -c "select status, count(*) from eval_runs group by 1"
curl -s localhost:8000/metrics | grep evalops_queue    # from inside the host network
```
