# Threat model: agents, extensions and the LLM judge

EvalOps has two kinds of AI inside its trust boundary:

1. **The product's own LLM calls**: the model under test and the LLM judge.
2. **The coding agents that build and operate it**: Claude Code with our skills, subagents,
   hooks and MCP server, plus the scheduled triage agent.

Both read text we do not control. The model below lists what can go wrong and what stops it.

## Assets

Project API keys and JWTs · `ANTHROPIC_API_KEY` (money) · the production database · the
integrity of eval results (a fake "pass" lets a bad prompt ship) · the source code and CI.

## Threats and mitigations

| # | Threat | Path | Mitigation | Residual risk |
|---|---|---|---|---|
| T1 | **Prompt injection into the judge** makes a bad output score 5/5 | test-case inputs or the model output say "ignore the rubric" | Untrusted blocks delimited, closing tags neutralised (`neutralise()`), explicit rule in `judge.md`, JSON-schema output, no tools; calibration set contains an injection example | A sufficiently clever injection can still bias a score. Pair judges with deterministic evaluators; watch calibration agreement |
| T2 | **Injection via MCP results into the coding agent** steers it to edit code or leak secrets | `get_regressions` returns model outputs | Read-only tools; outputs truncated (600 chars); `start_run` requires approval; secrets unreadable (guard hook + `deny` rules); triage prompt says to report, not follow, embedded instructions | The agent still reads hostile text; a human reviews the diff (demo step 6) |
| T3 | **Over-privileged MCP key** used to read or modify other projects | stolen or misused `EVALOPS_API_KEY` | Keys are scoped to one project server-side (404 elsewhere), cannot create keys, delete, or edit datasets/evaluators (403), are hashed at rest, revocable, and `last_used_at` is tracked | A key can start runs (costs money, bounded by the per-run caps) and create prompt versions through `/gate` |
| T4 | **Hook bypass**: the agent reaches a blocked file or command another way | e.g. `python -c "open('.env')"`, or editing with a tool the matcher misses | Defence in depth: guard hook + `permissions.deny` in `.claude/settings.json` + `.gitignore` + gitleaks in CI. Hooks are documented as guardrails, not a sandbox | Regex command filters are bypassable. Run agents in containers or worktrees without production credentials |
| T5 | **Hooks disabled or edited** by the agent itself | the agent edits `.claude/settings.json` or `agent-hooks/` | Changes show up in the diff and in review; `install.py --check` in CI catches drift between the plugin and its sources | A local user can always disable hooks: they protect against mistakes, not a malicious operator |
| T6 | **Malicious plugin update** (supply chain) | someone installs a modified `evalops-agent-pack` | Plugin installed from this repo's marketplace file; hooks are short, readable stdlib Python; plugin copies are generated and checked in CI | Pin the marketplace to a commit for other teams |
| T7 | **Cost abuse**: agent or CI loops `start_run` against a paid model | runaway agent or compromised key | `MAX_CASES_PER_RUN`, `MAX_COST_PER_RUN_USD`, `MAX_DAILY_COST_USD` per project (checked when a run is queued, when it starts and after each case), rate limiting, `start_run` in the `ask` list, `LLMSpendSpike` alert | A key can spend up to one day's budget before a human notices; keep the budget small on public deployments |
| T8 | **Triage agent posts sensitive data to GitHub issues** | nightly agent copies outputs into an issue | Agent includes only ids, counts and a summary; LLM triage sees truncated outputs; issue repo is the private project repo | If datasets ever hold PII, issues could leak it: see [ai-data-policy.md](ai-data-policy.md) |
| T9 | **Secrets in traces or logs** | spans or logs include prompts or keys | Spans carry model/token/cost attributes only; the collector deletes `evalops.prompt`/`evalops.output` attributes; JSON logs never include bodies; audit log records targets, not contents | none known |
| T11 | **Forged results through `POST /gate/ingest`**: a leaked project key records a "passing" run, or plants attacker-chosen text in `output` | stolen CI key; a PR from a fork that can read the secret | The key can only add runs to datasets that already exist and match them case for case (no dataset, case, evaluator or policy writes); `output` ≤ 5000 chars, 200 results, body-size limit; a result with an `error` never counts as passed; ingested runs are labelled `model=external` and `triggered_by=ci`, so they are distinguishable from runs EvalOps executed; keys are revocable | The ingest endpoint trusts the caller's `passed`: a leaked key can make the gate pass. Do not expose the key to workflows from forks, rotate it on suspicion, and keep rendering `output` escaped (the UI does; MCP truncates it) |
| T10 | **Destructive agent actions** (force push, dropping the DB) | an agent mistake | Guard hook blocks `rm -rf`, force push, `reset --hard`, `docker volume rm`, `compose down -v`, `DROP/TRUNCATE`; CLAUDE.md forbids touching AWS without approval | Commands outside the patterns, so keep human approval for deploys |

## Testing the mitigations

- `backend/tests/unit/test_evaluators.py::test_untrusted_output_cannot_escape_delimiters` (T1)
- `backend/tests/unit/test_api.py::test_api_key_shown_once_scoped_and_revocable` (T3)
- `agent-hooks/tests/test_hooks.py` (T4, T10): secrets, migrations, contract, destructive commands
- `mcp-server/test_server.py::test_exposes_expected_tools_with_read_only_hints` (T2, T3)
