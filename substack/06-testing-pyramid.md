# A Testing Pyramid for AI Apps: What to Mock and What Never to Mock

*Part 6 of "Building EvalOps". Concepts: the testing pyramid, fakes vs mocks, testcontainers, end-to-end tests, coverage you can trust.*

---

AI apps tempt you into two bad extremes: test nothing ("it's non-deterministic anyway") or
call the real model in every test (slow, flaky, expensive). The answer is the classic testing
pyramid with one AI-specific rule:

> **Fake the model. Never fake the things you own.**

## The pyramid in this project

```text
                 ▲  1 E2E journey (Playwright, real UI + API + worker + Postgres, fake LLM)
                ▲▲▲  3 integration tests (real Postgres 16 via testcontainers + Alembic)
            ▲▲▲▲▲▲▲▲▲  77 backend unit tests (SQLite, every endpoint, worker, evaluators) + 26 frontend
       ▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲  pure functions: summaries, compare buckets, gate verdicts, formatting
```

Plus the contract test, 7 MCP server tests and 9 hook tests. In total: **80 backend tests at 90%
coverage**, with the unit suite under 30 seconds.

## Concept 1: fakes beat mocks for the model

A **mock** records calls and returns canned values ("when `complete` is called, return X").
A **fake** is a small working implementation. `FakeProvider` is a fake: it follows simple
instructions, recognises the judge prompt and scores it with a transparent heuristic, and can
be scripted per test:

```python
async def test_case_errors_are_recorded_not_fatal(api: Api) -> None:
    ids = await setup_project(api)
    api.fake.script("Where is my order?", error="simulated 529 overloaded")
    run = await api.run(ids["project_id"], v1, ids["dataset_id"])
    assert run["status"] == "succeeded"
    assert run["summary"]["errored"] == 1 and run["summary"]["passed"] == 4
```

That one test proves a real product behaviour (one provider failure doesn't kill a 30-case
run) in milliseconds, for free, deterministically.

The real Anthropic provider is tested without the network too: the test swaps its client for
a stub and checks that it sends the right request (no `temperature`, the right
`output_config`) and turns usage into dollars correctly.

## Concept 2: test through the front door

Most backend tests go through **HTTP**, using an in-process async client. A small helper
makes them read like the user story:

```python
async def test_compare_finds_regressions(api: Api) -> None:
    ids = await setup_project(api)
    base = await api.run(pid, await api.version(pid, "v1", SUPPORT_TEMPLATE_V1), ds)
    head = await api.run(pid, await api.version(pid, "v2", SUPPORT_TEMPLATE_V2), ds)
    cmp = await api.ok("GET", "/runs/compare", params={"base": base["id"], "head": head["id"]})
    assert cmp["counts"]["regressed"] == 5
```

`api.run()` queues a run and then calls the **real worker code** inline (`drain()`), so these
tests exercise routing, auth, services, repositories, the worker and the evaluators together.
Refactors don't break them; real bugs do.

## Concept 3: integration tests against the real database

SQLite is great for speed but it isn't Postgres. `SKIP LOCKED` is ignored by SQLite;
cascades and types behave differently. So the integration tests start a **real Postgres 16
in Docker** with testcontainers, apply the **real Alembic migrations**, and run:

1. import 30 cases from JSONL → run → compare → gate (fails with 30 regressions),
2. cascade delete of a project with runs,
3. four concurrent workers claiming six queued runs: each claimed exactly once.

They're marked `@pytest.mark.integration` and run with a separate command, so the fast loop
stays fast.

## Concept 4: one end-to-end test that matters

[e2e/tests/happy-path.spec.ts](../e2e/tests/happy-path.spec.ts) drives a real browser through
the full story from Part 1 against the Docker stack: sign up, create a project, save v1,
import the CSV, add three evaluators, run (expects "30/30 passed"), save the terse v2, run
(expects "0/30 passed"), open the comparison, expect "30 cases regressed" and expand a row.

One journey, about 8 seconds. E2E tests are expensive to maintain, so write few, and make them
the ones you'd demo to a customer.

Two locator lessons from writing it:

- `getByRole("heading", { name: "Projects" })` also matched "Your projects" (Playwright matches
  substrings by default). Use `exact: true`.
- Assert on accessible names (`Delete mentions-topic` button) rather than raw text inside
  complex markup.

## Concept 5: what never to mock

- **Your database** in integration tests (that's where the subtle bugs live).
- **Your own HTTP layer** (call it through a real client).
- **Your migrations** (the integration suite applies them).
- **Your contract** (the drift test compares real specs).

What to fake: the LLM, third-party HTTP, time if needed. That's it.

## Rules that kept the agent honest

From AGENTS.md: *never call a real LLM in tests; every bug fix gets a regression test; never
weaken or delete a failing test to make CI pass.* When the security review in Part 11 found
a rate-limit bypass, the fix came with a test that fails on the old code. That is the habit to
build.

**Next:** [Part 7: Shipping it](07-shipping.md).
