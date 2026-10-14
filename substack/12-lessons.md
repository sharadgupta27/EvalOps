# What I'd Tell You Before You Start: Lessons from Building EvalOps with a Coding Agent

*Part 12 (final) of "Building EvalOps".*

---

Eleven posts ago EvalOps was a paragraph. Now it's a deployed-ready platform with a contract,
a backend, a frontend, a worker, a CI gate, observability, security artifacts and an agent
extension pack. Here's what I'd tell you before you build your own.

## The numbers

| | |
|---|---|
| API | 22 paths, 35 operations, 41 schemas, Spectral-clean |
| Backend tests | 80 (77 unit in about 24 s + 3 Postgres integration), **90% coverage** |
| Frontend tests | 26 Vitest (pure logic ≈ 91% covered) + 1 Playwright journey |
| Agent pack tests | 7 MCP server + 9 hook tests; plugin validated |
| Security | 6 scanners; fixed 41 image CVEs, 2 library CVEs, 1 rate-limit bypass, 1 upload DoS, 1 SAST blind spot |
| Ops | 4 alerts, 1 dashboard, 1 outage drill that found 1 monitoring bug |
| The demo | v1 → 100% pass; "shorter" v2 → 0% pass, 30 regressions, gate exit code 1 |

## Lessons

**1. Context is the product.** The time spent on `plan.md`, the spec and `AGENTS.md` paid back
every hour after. The agent made the most mistakes where the rules were vague, and the fewest
where they were checkable ("no `fetch` outside `src/api/`").

**2. Running beats reading.** Almost every interesting bug was found by *executing*
something: a builtin shadowed in a class body, `[] or default`, Windows event loops, nginx
caching a dead IP, an emoji crashing a console, a git signing prompt hanging a test fixture.
Tell your agent to run the tests after every slice, and give it an environment where it can.

**3. Contracts make AI code trustworthy.** A generated client plus a drift test turned
"frontend and backend disagree" from a production bug into a red test with the exact field name.

**4. Fake the model, not your system.** A deterministic fake that *behaves* like a model made
tests fast and free and the demo meaningful. Real Postgres, real migrations and a real browser
caught what fakes can't.

**5. Measure your judge, and say what the number means.** LLM-as-judge is powerful and
fallible. Calibrate it against labels. And never present a pipeline sanity check (100% with a
fake judge) as evidence of quality.

**6. Prefer guarantees to requests.** "Please don't edit the contract" is a request. A hook that
blocks it until a reviewer approved is a guarantee. Use instructions for knowledge, hooks for
rules that must hold.

**7. Drill your alerts.** An alert you've never seen fire is a hypothesis. Ten minutes of
breaking things on purpose found a blind spot that would have hidden a real outage.

**8. Read the scanner's errors.** "0 findings" with a parse error is not "0 findings".

**9. Document decisions, not just code.** Accepted risks with reasons, "author to confirm"
markers, honest gaps written down until they're closed. That's what makes a
portfolio project credible to a reviewer.

## What I'd do differently

- Propagate trace context through the job queue from day one. I added it as a follow-up; it
  was one column and ten lines, and before it every run showed up as two unrelated traces.
- Use HttpOnly cookies instead of `localStorage` for the session token.
- Start on Tailwind 4 and avoid the dev-dependency advisories entirely.
- Get the real-model judge calibration number earlier: it's the most interesting metric
  in the project and the one I can't fake.

## If you want to build one

Fork the idea, not the code: pick an LLM feature you care about (a RAG answerer, a
classifier, a SQL generator), write its golden dataset first, and make "is it better?" a
question your CI answers. That's the habit hiring managers for AI engineering roles look for.

Thanks for reading the series. The full repository, with every file referenced in these
posts, is linked below.
