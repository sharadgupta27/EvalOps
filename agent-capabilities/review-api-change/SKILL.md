---
name: review-api-change
description: Contract-first checklist for any EvalOps API change. Use before editing openapi.yaml, adding or changing an endpoint, a request/response field, a status code, or an auth requirement. Required by the guardrail hook that protects openapi.yaml.
---

# Review an API change (contract first)

`openapi.yaml` is the source of truth. The frontend client is generated from it and
`backend/tests/unit/test_contract.py` fails when the backend drifts from it. A hook blocks
edits to `openapi.yaml` until this review has been done.

## 1. Plan the change (no edits yet)

Write down, in 2–5 bullets:
- Which user story in `product-spec.md` needs it.
- Path, method, operationId, request schema, response schema and status codes.
- Who may call it: user JWT only, or also project API keys (CI/MCP)? See `docs/permissions.md`.
- Is it **backwards compatible**? Adding optional fields or new endpoints is. Renaming or
  removing fields, making optional fields required, or changing types is NOT; those need a
  new field or a deprecation note instead.

## 2. Get an independent review

Delegate to the `api-contract-reviewer` subagent with the plan and the intended YAML diff.
It is read-only and checks naming, compatibility, error responses and auth.
Fix every blocking finding before continuing.

## 3. Unlock and edit the contract

Record the approval so the guardrail hook allows the edit:

```bash
python agent-hooks/approve_contract_change.py "<one-line reason>"
```

Then edit `openapi.yaml` and lint it:

```bash
npx @stoplight/spectral-cli@6 lint openapi.yaml
```

## 4. Propagate in this order

1. `cd frontend && npm run gen:api` (regenerates `src/api/schema.d.ts`; never hand-edit it).
2. Backend: Pydantic schema in `app/schemas/` (names must match the YAML), service logic in
   `app/services/`, route in `app/api/routes.py`. Routers stay thin.
3. If the database changes: `uv run alembic revision --autogenerate -m "..."` and review the
   generated file. Never edit an already-applied migration.
4. Frontend hook in `src/api/hooks.ts`, then the UI.

## 5. Verify

```bash
cd backend && uv run pytest tests/unit/test_contract.py -q && uv run pytest -m "not integration" -q
cd frontend && npm run typecheck && npm run test
```

The approval expires after 2 hours or after the next commit. Log the change in `docs/ai-workflow.md`.
