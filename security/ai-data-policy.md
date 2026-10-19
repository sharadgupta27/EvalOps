# AI tool and data policy

Applies to the EvalOps product and to the AI tools used to build it. Owner: project author.
Review: every 6 months or when a new AI provider is added.

## 1. Which data may go to which model

| Data class | Examples | Product LLM calls (Anthropic API) | Coding agents (Claude Code etc.) | Never |
|---|---|---|---|---|
| **Public** | docs, demo dataset, open-source code | ✅ | ✅ | |
| **Internal** | prompts, evaluator configs, synthetic test cases, eval results | ✅ (that is the product) | ✅ | |
| **Customer content** | real support tickets used as test cases | ✅ only after PII is removed, and only with a provider under a data-processing agreement | ⚠️ only redacted samples; prefer synthetic | |
| **Personal data (PII)** | names, emails, order ids of real people | ❌ redact first | ❌ | in datasets, issues, logs, traces |
| **Secrets** | API keys, JWT secret, DB passwords, `.env` | ❌ | ❌ (blocked by hooks and `deny` rules) | in prompts, code, commits, CI logs |

The `add-eval-case` skill instructs agents to replace personal data with fake values before
adding a case.

## 2. Providers and retention

- **Product LLM calls** go only through `backend/app/llm/` to the Anthropic API, using the
  operator's own key. Anthropic's API terms apply (commercial terms: inputs and outputs are
  not used for model training by default; retention per the operator's agreement). EvalOps
  stores prompts, outputs and scores in its own Postgres database until the project is deleted.
- **Default is no external calls**: `LLM_PROVIDER=fake` for tests, CI and the public demo.
  Switching to `anthropic` is an explicit operator decision per environment.
- **Observability** stores metadata only (model, tokens, cost, latency, ids). Prompts and
  outputs are not put in traces or logs (collector scrubs them as a second line of defence).
  Traces are kept 48 hours, Loki logs 7 days, Prometheus data 15 days. The log shipper
  (Alloy) mounts the Docker socket read-only to discover containers; that is acceptable for
  the local/demo add-on only, not for a shared host.
- **The triage agent** sends truncated regressed cases to Claude to write a summary and posts
  the summary to the project's private GitHub issues.

## 3. Secrets handling

- Secrets live in environment variables: `.env` locally (git-ignored), GitHub Actions secrets
  in CI, `/opt/evalops/.env` on the server (mode 600). `.env.example` documents names only.
- API keys are shown once and stored as SHA-256 hashes. Passwords are bcrypt hashes.
- gitleaks runs in CI on the full history. A leaked key is rotated immediately (revoke in
  *Gate & API keys*, or rotate at the provider), not just deleted from git.
- Agents may not read `.env*` files (guard hook + `permissions.deny`).

## 4. Rules for AI-assisted development

1. Every AI-produced change is reviewed by a human before merge; reviews are logged in
   `docs/ai-workflow.md`.
2. AI output is untrusted until tests pass. Tests may not be weakened to make AI code pass.
3. No AI tool gets production credentials. Deploys go through CI with human-approved merges.
4. AI-generated labels or evaluation data (e.g. the judge calibration set) are marked as
   such and reviewed by a human before they are used to make decisions.
5. Use the least capable access that works: MCP keys are per project, subagents get only
   the tools they need (`tools:` frontmatter), reviewers are read-only.
