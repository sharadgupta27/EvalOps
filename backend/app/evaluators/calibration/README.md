# Judge calibration set

`judge_calibration.jsonl`: 20 examples for the rubric "Is the reply polite and correct?",
each with a pass/fail label (`human_pass`). 10 good replies; 10 bad ones covering terse
answers, rudeness, wrong facts, polite-but-off-topic answers and one prompt-injection attempt.

**Provenance.** The labels were drafted by the AI coding assistant during development and
must be reviewed by a human before the agreement number is treated as evidence of judge
quality. Mark reviewed rows by adding `"reviewed_by": "<name>"`.

Run: `cd backend && uv run python -m app.evaluators.calibrate` (add `LLM_PROVIDER=anthropic`
and `ANTHROPIC_API_KEY` to measure the real judge).

| Provider | Agreement | Meaning |
|---|---|---|
| FakeProvider | 100% (20/20) | **Pipeline check only.** The fake judge heuristic and the labels were written together, so this number says nothing about real judge quality |
| Claude (`JUDGE_MODEL`) | not yet measured | run with a key and record the result here |
