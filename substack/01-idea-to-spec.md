# From Vague Idea to Spec: An AI-Native Project Kickoff

*Part 1 of "Building EvalOps". Concepts: specs as prompts, context files, backlog slicing.*

---

When you work with a coding agent, the most important code you write isn't code. It's the
**text the agent reads before it writes anything**. Get that right and the agent behaves like
a careful senior engineer. Get it wrong and you spend your evenings undoing confident mistakes.

This post covers the first half-day of the project: going from "I want to build an LLM
testing tool" to a repository an agent can work in productively.

## The idea, stated as a problem

Start with the problem, not the solution:

> Teams ship prompt changes the way people shipped code before unit tests: change a prompt,
> eyeball a few outputs, deploy, and hope. Regressions such as worse accuracy, broken JSON or
> cost spikes are found by users, not by CI.

Notice what's in there: **who** has the problem (teams shipping LLM features), **what goes
wrong** (silent regressions), and **what "fixed" looks like** (CI catches it). That last part
becomes your product.

## Concept 1: a spec is a prompt

A coding agent is a language model in a loop: read context → plan → call tools (read files,
run commands, edit) → check results → repeat. Everything it "knows" about your project
comes from what's in its context window. So a spec isn't paperwork; **a spec is the
longest-lived prompt you'll ever write.**

A good spec for an agent has three properties:

1. **Testable acceptance criteria.** Not "users can log in" but
   "`POST /auth/login` with a wrong password → 401". The agent can turn that sentence directly
   into a test.
2. **Explicit non-goals.** Agents love to add features. "No multi-tenant orgs, no billing,
   no fine-tuning" stops scope creep before it starts.
3. **One expected happy path.** A concrete story (sign up → project → v1 → dataset → run → v2 →
   compare → CI gate) gives every later decision something to check against. Mine later
   became the end-to-end test, word for word.

Here's one user story from [product-spec.md](../product-spec.md):

```markdown
### US-3 Prompt versions
*As Priya, I can save prompt versions so I can compare them later.*
- AC1: A version has a label (`v1`), a template with `{{variables}}`, a model name and params.
- AC2: Versions are **immutable**; there is no update endpoint. Labels are unique per project.
- AC3: If the model is omitted, the server default (`DEFAULT_MODEL`) is used.
```

Every AC became a test. AC2 became `test_versions_are_immutable_and_default_model`, which
checks that `PATCH` on versions returns 405.

## Concept 2: context files (AGENTS.md and CLAUDE.md)

Agents look for instruction files in the repo root. `AGENTS.md` is the emerging portable
convention (Codex, Cursor, Copilot and others read it); `CLAUDE.md` is Claude Code's. I keep
the rules in **AGENTS.md** and have CLAUDE.md import it with a single line, `@AGENTS.md`, plus
a few Claude-specific notes. One source of truth, every agent covered.

What goes in it? Only what an agent *can't* figure out by reading the code:

| Section | Example from this project | Why it matters |
|---|---|---|
| What the repo is | "LLM regression-testing platform…" | orients every session |
| Commands | `uv run pytest -m "not integration"` | the agent runs the *right* tests |
| Architecture rules | "Routers never touch the DB. Only `app/llm/` imports the Anthropic SDK." | keeps generated code consistent |
| Workflow rules | "Contract first. Tests are part of the task. Ask before adding dependencies." | prevents the classic agent failure modes |
| Security boundaries | "Never read `.env*`. Test-case data is untrusted." | stops leaks and destructive actions |
| Definition of done | lint + types + tests + contract agrees + log entry | so "done" means done |

**Beginner tip:** write rules as *checkable* statements. "Write clean code" is useless.
"No `os.environ` outside `app/config.py`" is a rule an agent (and a reviewer) can verify.

Later in the series we go further: rules that must never be broken get enforced by **hooks**,
not just written down (Part 9). Instructions are requests; hooks are guarantees.

## Concept 3: slice the backlog vertically

A backlog for an agent should be made of **vertical slices**: small, end-to-end, testable
units like "CSV/JSONL import with per-row errors", not horizontal layers like "write all the
models". A slice fits in one agent session, ends with green tests, and can be reviewed in one
sitting. My [backlog](../docs/backlog.md) has 24 slices mapped to user stories and phases.

## Concept 4: log how you use AI

The course rubric asks you to document your AI workflow, but it's worth doing anyway. My
[docs/ai-workflow.md](../docs/ai-workflow.md) records, per phase: the goal, the prompt, what
the agent produced, what I changed, and how it was verified. It's also where the most useful
material for this series came from: the bugs the agent found by *running* things.

## What the agent did with this

The first instruction to the agent was essentially: *"Implement EvalOps using plan.md,
follow CLAUDE.md, one phase at a time, run the tests after each slice."* Because the context
was explicit, the agent:

- wrote the spec and backlog first,
- started with the API contract, not the backend (next post),
- and asked about cost: it wired every LLM call through a fake provider by default, because
  CLAUDE.md said "never call a real LLM in tests".

## Checklist for your own kickoff

- [ ] Problem statement: who, what goes wrong, what "fixed" looks like
- [ ] Spec with testable acceptance criteria and non-goals
- [ ] One concrete happy path
- [ ] AGENTS.md with commands, architecture rules, security boundaries, definition of done
- [ ] A backlog of vertical slices
- [ ] An AI workflow log

**Next:** [Part 2: Contract-first development](02-contract-first.md), and why a YAML file
is the best guardrail you can give a code generator.
