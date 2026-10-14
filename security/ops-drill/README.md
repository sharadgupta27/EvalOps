# Operational diagnosis drill: "the worker died"

**Date:** 2026-10-14 · **Environment:** local Docker Compose + `ops/` observability stack ·
**Script:** [run-drill.sh](run-drill.sh) · **Raw output:** [drill-output.txt](drill-output.txt)

## Scenario

The background worker stops (crash, OOM, bad deploy). Users can still queue runs, but nothing
processes them. The UI shows "queued" forever. How fast does monitoring tell us, and does
it point to the cause?

## What we did

1. `docker compose stop worker` at 10:40:50Z.
2. Queued run #21 through the API.
3. Every minute for 8 minutes: polled Prometheus (`up`, queue age, alert states),
   Alertmanager (active and inhibited alerts) and the `alert-sink` log (notifications actually
   delivered).
4. `docker compose start worker`, checked the run, and waited for the "resolved" notification.

The first run of this drill (01:03Z, run #12) had no Alertmanager: alerts were only visible in
Prometheus and Grafana. This second run adds the routing layer.

## Timeline (from drill-output.txt)

| t | `up{job="evalops-worker"}` | Run #21 | Prometheus | Alertmanager | Notifications delivered |
|---|---|---|---|---|---|
| +1m, +2m | 0 | queued | `WorkerDown` pending | none | none |
| +3m | 0 | queued | **`WorkerDown` firing** | `WorkerDown` active | **1 × page: `WorkerDown` firing** (startsAt 10:43:04Z) |
| +6m | 0 | queued | `EvalQueueStuck` pending (oldest queued run > 5 min) | `WorkerDown` active | still 1 |
| +8m | 0 | queued | **`EvalQueueStuck` firing**, `WorkerDown` firing | `WorkerDown` active, **`EvalQueueStuck` suppressed (inhibited by `WorkerDown`)** | still 1 |
| recovery +20s | 1 | **succeeded** | resolving | | |
| recovery +4m | 1 | succeeded | none | none | **1 × page: `WorkerDown` resolved** |

One outage produced exactly one page and one "resolved" message. Without the inhibit rule,
the on-call engineer would have been paged twice for the same cause.

## Diagnosis walk-through (what an on-call engineer does)

1. **Page:** `WorkerDown` arrives on the `page` receiver (Slack/PagerDuty in production; the
   `alert-sink` log locally). Its runbook link is `docs/runbook.md#worker-down`.
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

- ~~Add Alertmanager routing~~ Done: `ops/alertmanager/alertmanager.yml`, verified by this run.
- Connect the `page` receiver to a real channel when deploying (examples in that file).
- `restart: unless-stopped` is set in production compose, so a crashed worker restarts
  automatically; a clean `stop` (as in this drill) does not.
