# Observability for LLM Apps: Tracing Tokens and Dollars

*Part 8 of "Building EvalOps". Concepts: logs vs metrics vs traces, OpenTelemetry, Prometheus, Grafana, actionable alerts, and a real outage drill.*

---

LLM apps fail in new ways: a provider slows down, a model starts refusing, a loop burns $50 in
an hour. Observability is how you find out from a dashboard instead of an invoice.

## Concept 1: the three signals

| Signal | Answers | EvalOps example |
|---|---|---|
| **Logs** | what happened, in detail | `{"msg": "claimed run", "run_id": 12, "trace_id": "…"}` (JSON, one line each) |
| **Metrics** | how much / how fast, over time | `evalops_llm_cost_usd_total{model="claude-opus-5-5"}` |
| **Traces** | where the time went in one request | `run.execute → case.evaluate → llm.complete (2.1 s, 812 tokens, $0.01)` |

## Concept 2: instrument once, at the boundary

All model calls already go through `LLMProvider`, so instrumentation is one wrapper:

```python
class InstrumentedProvider:
    async def complete(self, prompt, *, model, max_tokens, **kw):
        with tracer.start_as_current_span("llm.complete") as span:
            span.set_attribute("gen_ai.request.model", model)
            c = await self.inner.complete(prompt, model=model, max_tokens=max_tokens, **kw)
            span.set_attribute("gen_ai.usage.input_tokens", c.tokens_in)
            span.set_attribute("gen_ai.usage.output_tokens", c.tokens_out)
            span.set_attribute("evalops.cost_usd", c.cost_usd)
            LLM_LATENCY.labels(self.name, model).observe(c.latency_ms / 1000)
            LLM_COST.labels(model).inc(c.cost_usd)
            return c
```

This is why the provider abstraction from Part 4 pays off twice. The same design applies to
privacy: spans carry **model, tokens, cost and latency, never prompts or outputs**, and the
OpenTelemetry Collector deletes those attributes as a second line of defence.

**Metric labels.** HTTP metrics are labelled by route *template* (`/runs/{run_id}`), never
the raw path. Otherwise every run id creates a new time series and Prometheus falls over.

## The stack

```text
api, worker ──OTLP──▶ OTel Collector ──▶ Tempo (traces)
                              └─ span metrics ─▶ Prometheus ◀── scrapes /metrics on api and worker
                                                     └──▶ Grafana (dashboard, alerts)
```

One command adds it to the dev stack:
`docker compose -f docker-compose.yml -f ops/docker-compose.observability.yml up -d`.
The provisioned dashboard shows runs per minute, queue age and depth, spend today, LLM p50/p95
latency by model, error rate, tokens per minute, spend per hour by model, cases by outcome,
API 5xx rate and p95 latency per route.

## Concept 3: alerts must be actionable

An alert should mean *someone needs to do something now*, and link to what. EvalOps has four:

| Alert | Condition | Action (runbook) |
|---|---|---|
| `EvalQueueStuck` | oldest queued run > 5 min | worker down, stuck or overloaded |
| `WorkerDown` | worker not scrapeable for 2 min | check container and logs, restart |
| `LLMErrorRateHigh` | > 20% of model calls failing | auth, 429 or provider incident |
| `LLMSpendSpike` | > $20 in an hour | find the trigger, revoke the key |

Each has a section in [docs/runbook.md](../docs/runbook.md).

Prometheus decides *whether* an alert fires. **Alertmanager** decides *who hears about it, and
how often*. Three ideas carry most of the value:

- **Routing by severity.** `severity: page` goes to the receiver that wakes someone up
  (notify after 10 s, repeat hourly); `ticket` alerts batch up for working hours.
- **Grouping and repeat intervals.** Ten alerts from one incident become one message, and a
  long outage doesn't send a notification every 15 seconds.
- **Inhibition.** When the worker is down the queue is *always* stuck. An inhibit rule
  suppresses `EvalQueueStuck` while `WorkerDown` fires, so the page names the cause, not the
  symptom.

```yaml
inhibit_rules:
  - source_matchers: ['alertname="WorkerDown"']
    target_matchers: ['alertname="EvalQueueStuck"']
```

Locally both receivers post to a 40-line standard-library webhook (`alert_sink.py`) that
prints each alert, so routing can be tested without a Slack workspace. Swapping it for Slack
or PagerDuty is a config change, with the secret read from a mounted file.

## Concept 4: drill it, and find your blind spots

I didn't want to *believe* the alerts worked; I wanted to watch them. So I wrote a drill
script: stop the worker, queue a run, and record Prometheus every minute for 8 minutes.

**Designing the drill found a real bug before it ran.** The queue-age metric was published
*by the worker*. If the worker is dead, so is the metric, and `EvalQueueStuck` can never fire
in the exact outage it was written for. The fix: the API also computes the queue age every
time Prometheus scrapes it.

After adding Alertmanager I ran the drill again and also recorded what was actually
*delivered*:

| t | worker up? | run #21 | Prometheus | notifications delivered |
|---|---|---|---|---|
| +1 min | no | queued | `WorkerDown` pending | none |
| +3 min | no | queued | **`WorkerDown` firing** | **page: `WorkerDown`** |
| +6 min | no | queued | `EvalQueueStuck` pending | (no change) |
| +8 min | no | queued | **`EvalQueueStuck` firing** | none: inhibited by `WorkerDown` |
| restart +20 s | yes | **succeeded** | resolving | |
| restart +4 min | yes | succeeded | none | **page: `WorkerDown` resolved** |

One outage, one page, one all-clear.

Because the queue lives in Postgres, recovery is just a restart: the queued run was picked up
automatically and no data was lost. The full write-up is in
[security/ops-drill/](../security/ops-drill/README.md).

**Lesson:** an alert you've never seen fire is a hypothesis. A 10-minute drill turns it into
evidence, and often finds a bug.

## Concept 5: one trace across the job queue

A trace follows one request through every service it touches. Over HTTP that is automatic:
the caller sends a `traceparent` header (`00-<trace id>-<parent span id>-01`) and the server
continues the same trace. A job queue breaks the chain. The API answers `202 Accepted` and
returns; minutes later the worker picks the row up in a different process with no headers.
Without help, Tempo shows two unrelated traces: "someone queued a run" and "something ran".

My first version had exactly that gap. The fix is to treat the job row like an HTTP request
and give it headers:

```python
# API, inside POST /runs: serialise the active span as W3C headers onto the row
carrier: dict[str, str] = {}
propagate.inject(carrier)          # {"traceparent": "00-4bf9...-00f0...-01"}
run.trace_context = carrier or None

# Worker, after claiming the row: continue that trace
with tracer.start_as_current_span(
    "run.execute", context=propagate.extract(run.trace_context or {}), kind=SpanKind.CONSUMER
):
    ...
```

It costs one nullable JSON column (migration `0002`). Now a single trace shows the API
request, then `run.execute`, then 30 `case.evaluate` spans and 60 `llm.complete` spans (one
model call and one judge call per case). If the CI gate script sends its own `traceparent`,
the trace starts in GitHub Actions. A unit test (`test_worker_continues_the_trace_that_queued_the_run`)
checks that the worker's span is a child of the API's span.

**Lesson:** anywhere work crosses a queue, cron or webhook, carry the trace context
yourself. No library can guess which row belongs to which request.

**Next:** [Part 9: Skills vs subagents vs MCP vs hooks](09-agent-extension-mental-model.md).
