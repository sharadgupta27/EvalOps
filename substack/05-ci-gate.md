# Unit Tests for Prompts: Gating Pull Requests on LLM Quality

*Part 5 of "Building EvalOps". Concepts: background jobs, a Postgres job queue, comparing runs, regression buckets, a CI quality gate.*

---

Here's the moment the project exists for. A teammate opens a pull request that "simplifies"
the support prompt:

```diff
- You are a polite, friendly support agent for an online store.
- Reply in JSON with a single field 'answer'. Mention the customer's topic explicitly.
+ You are a support agent. Be terse: answer in one word.
```

It looks harmless. EvalOps runs the 30-case golden dataset, compares against the current
version and fails the PR:

```text
### ❌ EvalOps gate: **FAIL**
- pass rate 0% < minimum 80%
- 30 regressed case(s) > allowed 0
- cost change -27.2% within limit +20%
```

This post builds that path.

## Concept 1: never do slow work inside a request

A 30-case run takes seconds with a fake model and minutes with a real one. HTTP requests
shouldn't wait that long. So `POST /runs` only **queues** the work and returns `202 Accepted`,
and a separate **worker** process does it. The UI polls `GET /runs/{id}` for progress.

## Concept 2: a job queue in Postgres (no Redis needed)

You don't need a message broker to have a reliable queue. The `eval_runs` table *is* the
queue: a run with `status = 'queued'` is a job. The worker claims one like this:

```python
q = (select(EvalRun)
     .where(EvalRun.status == RunStatus.queued)
     .order_by(EvalRun.id).limit(1)
     .with_for_update(skip_locked=True))
```

`FOR UPDATE` locks the row; `SKIP LOCKED` tells other workers to skip locked rows instead of
waiting. Run four workers and each picks a different job, never the same one twice. That's not
a claim; it's an integration test against real Postgres (four concurrent claimers, six jobs,
six distinct claims).

Bonus properties: jobs survive restarts (they're rows), they're transactional with your data,
and there's one less service to operate. The trade-off is polling (1 s) and database load at
very high volume. That's fine here.

Inside the worker, cases run concurrently with a semaphore (`WORKER_CONCURRENCY`), because
model calls are slow I/O, but results are written through a single database session, because
sessions aren't safe to share between concurrent tasks.

## Concept 3: comparing two runs

Two runs of different prompt versions on the **same dataset** can be compared case by case.
Each case lands in a bucket:

| Bucket | Rule |
|---|---|
| regressed | passed → failed, or score dropped by ≥ 0.25 |
| improved | failed → passed, or score rose by ≥ 0.25 |
| unchanged | everything else |
| added / removed | case only in one run |

The 0.25 tolerance matters: LLM-judged scores jitter a little, and you don't want noise to
count as regressions. The logic lives in a pure function (`classify`) with a table-driven test
for every bucket.

The compare page leads with a verdict ("30 cases regressed"), then the numbers, then a
filterable table sorted worst-first. Clicking a row shows base and head outputs side by side
with new words highlighted, which is usually all you need to see *why*.

## Concept 4: the gate

A **gate policy** per project defines "good enough":

```json
{ "min_pass_rate": 0.8, "max_regressions": 0, "max_cost_increase_pct": 20 }
```

CI calls `POST /api/v1/gate` with a **project API key** (never a person's password):

```json
{ "dataset_id": 1, "head_label": "pr-42-abc1234",
  "template": "<contents of prompts/support-reply.txt>", "baseline_label": "v1",
  "git_sha": "abc1234..." }
```

The server creates the head version (immutable; reusing a label with different content is a
409 conflict), picks the baseline run (or queues it if the baseline was never evaluated, so the
first CI run needs no manual setup), queues the head run and returns `pending`. The client polls
`GET /gate/{run_id}` until the verdict is in. Every check produces a human-readable reason,
whether it passes or fails, because "failed" with no explanation gets ignored.

## The client: 100 lines of standard library

[scripts/evalops_gate.py](../scripts/evalops_gate.py) has no dependencies, so it runs on any
CI runner. It exits **0 on pass, 1 on fail, 2 on errors**, prints the reasons and writes them
to the GitHub step summary. In the workflow:

```yaml
- name: Gate the PR's prompt against v1
  run: |
    python3 scripts/evalops_gate.py --url http://localhost:5173 \
      --dataset-id "$DATASET_ID" --baseline-label v1 \
      --head-label "pr-${{ github.event.pull_request.number }}-${GITHUB_SHA::7}" \
      --template-file prompts/support-reply.txt --git-sha "$GITHUB_SHA"
```

In this repo, the gate workflow starts the whole stack in CI with the fake provider, seeds it,
and gates every PR that touches `prompts/`. Testing it locally: the good prompt → exit 0;
the terse prompt → exit 1 with 30 regressions.

**A bug you'll probably hit too:** the first run of the client crashed on Windows printing
the ✅ emoji, because Windows consoles default to a legacy code page. One line
(`sys.stdout.reconfigure(encoding="utf-8")`) fixed it.

## Why this is the right abstraction

The gate turns prompt quality into the same thing as code quality: **a red or green check
on the PR, with reasons.** Reviewers stop debating "does this feel better?" and look at the
regressed cases instead.

**Next:** [Part 6: A testing pyramid for AI apps](06-testing-pyramid.md).
