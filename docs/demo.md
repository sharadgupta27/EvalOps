# Demo script (Module 5)

A 10-minute walkthrough of the agent extension pack on a **real regression**: someone
"shortens" the support prompt, and the agent, its tools and the guardrails catch it.
Record the screen for the 2-minute video; the commands below are copy-pasteable.

## 0. Prepare (before recording)

```bash
docker compose up -d --build --wait
docker compose run --rm api python -m app.seed       # demo project with runs v1 (100%) and v2 (0%)
# UI: http://localhost:5173 (demo@evalops.dev / DEMO_PASSWORD) → project → Gate & API keys → Create key
export EVALOPS_URL=http://localhost:5173 EVALOPS_API_KEY=eo_...
python agent-hooks/install.py
claude
```

## 1. The agent reads the project instructions

> **You:** "What is this repo, and what are the rules for changing the API?"

Expected: it answers from `AGENTS.md`/`CLAUDE.md`: contract first, layering, never call a
real LLM in tests, ask before schema/CI changes.

## 2. A reusable workflow is invoked

> **You:** "A customer complained: when Ben asked 'Where is my order?' the bot replied just
> 'order?'. Use the add-eval-case skill."

Expected: the `add-eval-case` skill runs. It reads the prompt variables via MCP, proposes
1–3 sanitized cases tagged `bug`, and asks before starting a run, which then shows the cases
failing on `v2`.

## 3. A specialised subagent reviews an API change

> **You:** "Add an optional `limit` query parameter to GET /projects/{project_id}/runs."

Expected: the agent follows `review-api-change`, plans the change and delegates to the
`api-contract-reviewer` subagent (read-only), which returns a verdict ("additive, backwards
compatible; document the max").

## 4. The agent calls an MCP tool

> **You:** "Did v2 regress compared to v1? Use the triage-regression prompt for runs 1 and 2."

Expected: calls to `compare_runs` and `get_regressions`. Answer: 30 regressed cases, root
causes "JSON format dropped" and "tone no longer polite", proposed fix as a new label `v3`.

## 5. A hook prevents, formats, checks or logs an action

Show at least one of these:

- The agent tries to edit `openapi.yaml` before approval → **blocked** with the reason and
  the command to run after review. After `approve_contract_change.py`, the edit succeeds.
- > **You:** "Show me what's in .env" → **blocked** (secrets).
- Any Python edit → reformatted automatically (PostToolUse).
- When the agent says it is done → `stop_tests.py` runs the fast tests first.
- `cat agent-hooks/logs/audit.jsonl | tail` shows the logged decisions.

## 6. Review the final diff

```bash
git diff --stat
git diff openapi.yaml backend/ frontend/src/api/
cd backend && uv run pytest -q && cd ../frontend && npm run test
```

Check: contract, generated client and backend agree; new tests exist; no secrets; no
weakened tests. Commit only after this review.

## Bonus: the CI gate catches the bad prompt

```bash
printf 'Be terse: answer in one word.\nCustomer {{customer}} asks:\n{{question}}\n' > prompts/support-reply.txt
python scripts/evalops_gate.py --dataset-id 1 --head-label pr-demo --template-file prompts/support-reply.txt --baseline-label v1
# → ❌ FAIL: pass rate 0% < minimum 80%; 30 regressed case(s) > allowed 0   (exit code 1)
git checkout prompts/support-reply.txt
```

## Bonus: parallel subagents in worktrees

> **You:** "In parallel: (a) in a worktree, add a CSV export button to the Compare page;
> (b) in another worktree, add the runs `limit` parameter. Use one subagent per task, then
> review both diffs."

Expected: two `git worktree` checkouts, two subagent runs, then the orchestrator merges and
runs the full suites.
