# Agent extension pack

How coding agents are extended, constrained and shared in this repository (Module 5 deliverable).
The concepts are tool-agnostic; the concrete files target Claude Code, with notes for others.

## Mental model

| Capability | Question it answers | Here |
|---|---|---|
| Project instructions | "What is this repo and what are the rules?" | [AGENTS.md](../AGENTS.md) (portable), [CLAUDE.md](../CLAUDE.md) (imports it) |
| Reusable workflow (skill) | "How do we always do X?" | [agent-capabilities/](../agent-capabilities/): `add-eval-case`, `review-api-change`, `debug-ci-failure` |
| Specialised subagent | "Who should do this side task, with what tools?" | `api-contract-reviewer` (read-only), `eval-reviewer`, `qa-tester` |
| MCP server | "Which live system data and actions may the agent use?" | [mcp-server/](../mcp-server/): 7 tools, 1 resource, 1 prompt, one project key |
| Hooks / guardrails | "What must happen (or never happen) automatically?" | [agent-hooks/](../agent-hooks/): guard, format-on-save, tests-before-stop, audit log |
| Plugin | "How do other repos get all of this?" | [plugins/evalops-agent-pack/](../plugins/evalops-agent-pack/) + [.claude-plugin/marketplace.json](../.claude-plugin/marketplace.json) |
| Custom agent | "What runs unattended on a schedule?" | [custom-agent/agent.py](../custom-agent/agent.py) via [nightly-triage.yml](../.github/workflows/nightly-triage.yml) |
| Permissions | "Who may do what?" | [permissions.md](permissions.md), [security/agent-threat-model.md](../security/agent-threat-model.md) |

**Rule of thumb.** Put *knowledge* in instructions, *procedures* in skills, *focused
judgement with limited tools* in subagents, *live data and actions* behind MCP, *things that
must not depend on the model remembering* in hooks, and *unattended jobs* in a custom agent.

## Layout and sources of truth

```text
AGENTS.md, CLAUDE.md                 instructions
agent-capabilities/<skill>/SKILL.md  skills (source)
agent-capabilities/subagents/*.md    subagents (source)
agent-hooks/*.py                     hook scripts (source) + tests/ + install.py
mcp-server/server.py                 MCP server (source) + test_server.py + scripts/smoke.py
.claude/settings.json                hooks wiring, permissions, MCP allowlist (this repo)
.claude/skills, .claude/agents       GENERATED copies, loaded by Claude Code in this repo
plugins/evalops-agent-pack/          GENERATED plugin bundle for other repos
.mcp.json                            registers the MCP server for this repo
custom-agent/agent.py                scheduled triage agent
```

`python agent-hooks/install.py` regenerates the copies; CI runs `--check` and fails on drift.

## Setup (Claude Code)

```bash
docker compose up -d --build --wait && docker compose run --rm api python -m app.seed
# create a key in the UI (project → Gate & API keys), then:
export EVALOPS_URL=http://localhost:5173 EVALOPS_API_KEY=eo_...   # PowerShell: $env:EVALOPS_API_KEY="eo_..."
python agent-hooks/install.py
claude                     # open in the repo root; approve the "evalops" MCP server once
```

Inside Claude Code: `/agents` lists the subagents, `/mcp` shows the server, skills load
automatically when relevant (or ask: "use the add-eval-case skill").

**Other agents.** Codex and Cursor read `AGENTS.md`. The MCP server works in any MCP client
(see `mcp-server/README.md` for Codex `config.toml` and Cursor/Antigravity `mcp.json`).
The hook scripts read JSON on stdin and exit 2 to block, so any agent with pre-/post-command
hooks can call them.

## The components in detail

### Skills
- **add-eval-case**: bug report → 1–3 sanitized cases → prove they fail on the current prompt.
- **review-api-change**: contract-first checklist; delegates review to `api-contract-reviewer`;
  records approval with `approve_contract_change.py`, which unlocks `openapi.yaml` for 2 hours
  and only for the current commit.
- **debug-ci-failure**: maps every CI job to a local command; forbids weakening tests or gates.

### Subagents
Each has a narrow `tools:` list. Reviewers cannot edit; the QA agent may only touch tests.
Running them in their own context keeps long diffs and logs out of the main session.

### MCP server
Tools: `list_projects`, `list_prompt_versions`, `list_runs`, `start_run`, `get_run_summary`,
`compare_runs`, `get_regressions` · resource `evalops://runs/{run_id}` · prompt
`triage-regression`. Tested in-process (`mcp-server/test_server.py`, 7 tests) and over real
stdio against the running stack (`mcp-server/scripts/smoke.py`).

### Hooks
| Event | Script | Effect |
|---|---|---|
| PreToolUse (Read/Edit/Write/Bash) | `guard.py` | blocks secrets, committed migrations, generated client, unreviewed `openapi.yaml`, destructive commands; logs every decision |
| PostToolUse (Edit/Write) | `format_on_save.py` | ruff format + fix (Python), prettier (TS); reports remaining lint errors to the agent |
| Stop | `stop_tests.py` | runs fast backend and/or frontend tests for changed areas; blocks "done" if red (once, no loops) |

Tested with 9 subprocess tests against a throwaway git repo (`agent-hooks/tests/`).

### Custom agent
Plain-code pipeline (start run → wait → compare → triage → issue) with one LLM call for
the judgement step. Why not an interactive agent: it is unattended, repetitive and must be
cheap and auditable. Works without an Anthropic key (deterministic report).

## Parallel work with worktrees

Two independent tasks can run side by side in isolated checkouts, each with its own subagent:

```bash
git worktree add ../evalops-frontend -b feat/compare-export
git worktree add ../evalops-backend  -b feat/runs-pagination
```

In Claude Code, the main session acts as orchestrator: it writes a short spec per task,
starts one subagent per worktree (Agent tool with `isolation: "worktree"`, or a separate
`claude` session in each directory), waits, then reviews both diffs and runs the full suite
before merging. Rules: tasks must not touch the same files; contract changes go first
(`review-api-change`) and the other worktree rebases on them. The sequence is in [demo.md](demo.md).
