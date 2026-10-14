# Nightly regression-triage agent

A small, scheduled, non-interactive agent. Every night (GitHub Actions cron,
[nightly-triage.yml](../.github/workflows/nightly-triage.yml)) it:

1. re-evaluates the newest prompt version on the dataset (catches model or provider drift),
2. compares it with the previous successful run,
3. if cases regressed, writes a triage report (Claude when `ANTHROPIC_API_KEY` is set,
   otherwise a deterministic summary of failing evaluators), and
4. opens a GitHub issue labelled `eval-regression` (with `--open-issue`).

Exit code: 0 = no regressions, 1 = regressions found.

## Why a custom agent here

An interactive coding agent is great when a human steers. This job has no human in the loop,
a fixed procedure and a cost budget, so the control flow is ordinary code and the model is
used for the one step that needs judgement: explaining *why* cases got worse. That keeps it
predictable, cheap, testable and auditable.

## Run locally

```bash
export EVALOPS_URL=http://localhost:5173 EVALOPS_API_KEY=eo_...    # a project key
uv run --project custom-agent python custom-agent/agent.py --dataset-id 1
uv run --project custom-agent python custom-agent/agent.py --no-run   # just compare the 2 latest runs
```

Optional: `ANTHROPIC_API_KEY` (LLM triage), `TRIAGE_MODEL` (default `claude-opus-5-5`),
`GITHUB_TOKEN` + `GITHUB_REPOSITORY` with `--open-issue`.

The LLM call uses the Anthropic SDK with server-side model fallback enabled: a triage summary
is advisory, so being answered by a fallback model is fine. Eval runs deliberately do not
use fallbacks.

## Status

Verified against the local stack with the deterministic report (run #13: 30 regressions,
failing evaluators listed). The Claude path was not exercised in this environment (no API key).
Run it once with a key before relying on it.
