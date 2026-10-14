# Skills vs Subagents vs MCP vs Hooks: A Mental Model for Extending Coding Agents

*Part 9 of "Building EvalOps". Concepts: the agent loop, instructions, skills, subagents, MCP, hooks, plugins, custom agents, permissions.*

---

Every coding agent (Claude Code, Codex, Cursor, Copilot, Aider…) can be extended. The names
differ (skill, command, rule, recipe, extension), but there are only a handful of underlying
**capabilities**. Learn those and you can configure any tool.

## The agent loop, one more time

```text
read context ─▶ plan ─▶ call a tool (read / edit / run / MCP) ─▶ observe result ─▶ repeat ─▶ diff
```

Each extension plugs into a different part of that loop:

| Capability | Plugs into | Use it for | EvalOps example |
|---|---|---|---|
| **Instructions** (AGENTS.md) | context, every session | facts and rules about the repo | "contract first", commands, security boundaries |
| **Skill** (reusable workflow) | context, loaded *when relevant* | procedures you keep repeating | `add-eval-case`, `review-api-change`, `debug-ci-failure` |
| **Subagent** | a separate loop with its own context and tools | focused side tasks, independent review | `api-contract-reviewer` (read-only) |
| **MCP server** | tools | live data and actions from *your* systems | `compare_runs`, `get_regressions`, `start_run` |
| **Hook** | before/after tool calls, on stop | things that must happen, or must never happen, regardless of what the model decides | block `.env` reads, format on save, run tests before "done" |
| **Plugin** | packaging | sharing all of the above across repos | `evalops-agent-pack` |
| **Custom agent** | your own code, no human in the loop | scheduled or pipeline jobs | nightly regression triage |

### The one-line test for each

- *Is it knowledge?* → instructions.
- *Is it a procedure with steps?* → skill.
- *Does it need a fresh, focused context or limited tools?* → subagent.
- *Does it need live data or actions from a system?* → MCP.
- *Must it happen even if the model forgets?* → hook.
- *Does another repo need it?* → plugin.
- *Does it run unattended?* → custom agent.

## Skills: procedures, written down once

A skill is a markdown file with a name, a description that says *when* to use it, and steps.
The agent loads it only when the task matches, so it costs no context the rest of the time.

```markdown
---
name: add-eval-case
description: Turn a bug report or a bad LLM output into regression test cases in an EvalOps
  dataset. Use when someone reports a wrong, rude, malformed or hallucinated answer…
---
1. Reproduce the variables. The case inputs must contain exactly the template's {{variables}}.
2. Write the case(s): one for the report, up to two near variants. Strip personal data.
3. Check evaluator coverage. If no evaluator would catch this failure, propose one and ask.
…
5. Prove the cases catch the bug: start a run; the new cases must FAIL.
```

Step 5 is the important habit: **a test that never failed proves nothing.**

## Subagents: a second pair of eyes with fewer permissions

A subagent runs in its own context window with its own tool list. Two reasons to use one:

1. **Independence.** A reviewer that didn't write the code reviews it better, and its long
   reading doesn't clutter your main session.
2. **Least privilege.** `api-contract-reviewer` gets `Read, Grep, Glob, git diff`, and nothing
   that edits. `qa-tester` may only touch test files.

```markdown
---
name: api-contract-reviewer
description: Read-only reviewer for EvalOps API contract changes…
tools: Read, Grep, Glob, Bash(git diff:*), Bash(git log:*), Bash(git show:*)
---
You are read-only… Flag as BLOCKING: removed or renamed fields, optional→required…
Output: VERDICT: approve | changes-requested …
```

**Parallel work:** give each subagent its own **git worktree** (a separate checkout of a branch)
and two tasks can proceed at once without stepping on each other. The main session acts as
the orchestrator: write the specs, dispatch, review both diffs, run the full suites, merge.

## Hooks: guarantees instead of requests

Instructions say "please don't edit the API contract without a review." A **hook** makes
it impossible. Hooks are scripts the agent runtime calls around tool use; the event arrives as
JSON on stdin, and exit code 2 blocks the action with a message the agent can act on.

EvalOps's `guard.py` (PreToolUse) blocks:

- reading or writing `.env*` (secrets),
- editing a **committed** migration (create a new one instead),
- hand-editing the generated API client,
- editing `openapi.yaml` without a **fresh contract approval**: the `review-api-change` skill
  ends with `approve_contract_change.py`, which unlocks the file for 2 hours, *for the
  current commit only*,
- destructive commands: `rm -rf`, force pushes, `reset --hard`, `docker volume rm`,
  `compose down -v`, `DROP TABLE`.

`format_on_save.py` (PostToolUse) runs ruff or prettier on the edited file and feeds remaining
lint errors back to the agent. `stop_tests.py` (Stop) runs the fast tests for whatever changed
before the agent may say "done", once, so it can't loop forever. Every decision is appended to
an audit log.

Hooks are tested like any other code: 9 tests run each script as a subprocess against a
throwaway git repo. (Writing those tests exposed my global git signing config: the fixture's
`git commit` hung waiting for a signing prompt. Test fixtures must not depend on your machine.)

**Hooks are guardrails, not a sandbox.** A determined agent can find another path
(`python -c "open('.env')"`). That's why there's defence in depth: hooks plus `permissions.deny`
rules plus `.gitignore` plus gitleaks in CI, and a human reviewing the diff.

## Plugins: packaging for reuse

A plugin bundles skills, subagents, hooks and MCP config so another team installs everything
with one command. In this repo, `agent-capabilities/`, `agent-hooks/` and `mcp-server/` are the
sources, `install.py` copies them into `.claude/` and the plugin folder, and CI fails if the
copies drift. `claude plugin validate` checks the manifests.

## Custom agents: when there's no human in the loop

The nightly triage job doesn't need an interactive agent. It needs a **pipeline with one
smart step**: start a run → wait → compare → if regressions, ask Claude to group root causes →
open a GitHub issue. Plain code for control flow keeps it predictable, cheap and testable; the
LLM does only the judgement. Without an API key it falls back to a deterministic summary
("json-answer failing on 30/30 regressed cases"), which is often enough.

## Permissions: write them down

[docs/permissions.md](../docs/permissions.md) has one table per actor: users, API keys, the
main agent, each subagent, the MCP server, CI, the deploy job and the triage agent. Each row
says what it may do and **where that's enforced**. If you can't name the enforcement, it's
a wish, not a permission.

**Next:** [Part 10: Building an MCP server for your own app](10-mcp-server.md).
