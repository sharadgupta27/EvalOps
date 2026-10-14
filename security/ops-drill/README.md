# Operational diagnosis drill: "the worker died"

**Date:** 2026-10-14 · **Environment:** local Docker Compose + `ops/` observability stack ·
**Script:** [run-drill.sh](run-drill.sh) · **Raw output:** [drill-output.txt](drill-output.txt)

## Scenario

The background worker stops (crash, OOM, bad deploy). Users can still queue runs, but nothing
processes them. The UI shows "queued" forever. How fast does monitoring tell us, and does
it point to the cause?

## What we did

1. `docker compose stop worker` at 01:03:05Z.
2. Queued run #12 through the API.
3. Polled Prometheus (`up`, alerts) and the API every minute for 8 minutes.
4. `docker compose start worker` and checked the run.

## Timeline (from drill-output.txt)

| t | `up{job="evalops-worker"}` | Run #12 | Alerts |
|---|---|---|---|
| +1m | 0 | queued | `WorkerDown` pending |
| +3m | 0 | queued | **`WorkerDown` firing** |
| +6m | 0 | queued | `EvalQueueStuck` pending (oldest queued run > 5 min), `WorkerDown` firing |
| +8m | 0 | queued | **`EvalQueueStuck` firing**, `WorkerDown` firing |
| recovery +20s | 1 | **succeeded** | both still listed until the next evaluation cycle, then resolve |

## Diagnosis walk-through (what an on-call engineer does)

1. **Alert:** `WorkerDown`. Its runbook link is `docs/runbook.md#worker-down`.
2. `docker compose ps worker` shows the container exited. `docker compose logs worker --tail 50`
   shows the last log line `worker stopped` (a clean stop, not a crash).
3. Grafana *EvalOps overview*: "Oldest queued run" climbs linearly and "Runs finished / min"
   drops to 0. That confirms impact: users are waiting, data is not lost (runs stay queued).
4. **Fix:** restart the worker. Queued runs are picked up automatically because the queue
   lives in Postgres (`SELECT … FOR UPDATE SKIP LOCKED`), so no manual replay is needed.

## Finding: a monitoring blind spot (fixed before this run)

Designing the drill exposed a real gap. The queue-age gauge was only exported **by the
worker**, so when the worker died the metric disappeared and `EvalQueueStuck` could never
fire. That alert would have been silent in exactly the outage it exists for.
Fix: the API now computes `evalops_queue_oldest_age_seconds` on every scrape
(`backend/app/main.py`, test in `test_health_metrics_and_headers`). The timeline above shows
both alerts firing with the fix in place.

## Follow-ups

- Add Alertmanager routing (currently alerts are visible in Prometheus/Grafana only).
- `restart: unless-stopped` is set in production compose, so a crashed worker restarts
  automatically; a clean `stop` (as in this drill) does not.
