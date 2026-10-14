# Contract-First Development: Why OpenAPI Keeps AI-Generated Code Honest

*Part 2 of "Building EvalOps". Concepts: API contracts, OpenAPI, generated clients, mock servers, drift tests.*

---

When an AI agent writes both your frontend and your backend, it's very good at making each
side *internally* consistent and quietly bad at keeping them consistent *with each other*.
The frontend expects `passRate`, the backend sends `pass_rate`, and both compile.

The fix is old-fashioned and works even better with agents: **write the API contract first,
and make every other piece derive from it or be checked against it.**

## Concept: what is an API contract?

An API contract is a machine-readable description of every endpoint: path, method, inputs,
outputs, status codes, auth. The standard format is **OpenAPI** (a YAML or JSON file). Here's
the "start a run" endpoint from [openapi.yaml](../openapi.yaml):

```yaml
/projects/{project_id}/runs:
  post:
    operationId: createRun
    summary: Queue an evaluation run
    requestBody:
      required: true
      content:
        application/json:
          schema: { $ref: '#/components/schemas/RunCreate' }
    responses:
      '202':
        description: Queued
        content:
          application/json:
            schema: { $ref: '#/components/schemas/EvalRun' }
      '404': { $ref: '#/components/responses/NotFound' }
      '422': { $ref: '#/components/responses/ValidationFailed' }
```

Notice `202 Accepted`, not `200`: the run is queued, not finished. Writing the contract first
forces decisions like that *before* code exists. EvalOps ended up with 22 paths, 35
operations and 41 schemas.

## The contract-first loop

```text
openapi.yaml ──lint (Spectral)──▶ OK?
     │
     ├──▶ npm run gen:api ──▶ frontend/src/api/schema.d.ts (TypeScript types, never hand-edited)
     │
     ├──▶ Prism mock server ──▶ build the UI before the backend exists
     │
     └──▶ backend (FastAPI + Pydantic) ──▶ test_contract.py compares the two specs on every run
```

### 1. Lint the contract

[Spectral](https://github.com/stoplightio/spectral) checks the YAML for mistakes and
inconsistencies (missing operationIds, undefined tags…). It runs in CI. Good rules catch
bad API design the same way a linter catches bad code.

### 2. Generate the client, don't write it

`openapi-typescript` turns the YAML into TypeScript types, and `openapi-fetch` gives you a
tiny typed `fetch` wrapper. The result: if the contract says `pass_rate`, writing `passRate`
in a component is a **compile error**.

```ts
// frontend/src/api/hooks.ts
export const useRun = (id: number) =>
  useQuery({
    queryKey: keys.run(id),
    queryFn: () => unwrap(api.GET("/runs/{run_id}", { params: { path: { run_id: id } } })),
    // poll every second while the run is in flight
    refetchInterval: (q) => (q.state.data && ACTIVE_RUN.has(q.state.data.status) ? 1000 : false),
  });
```

The path string `"/runs/{run_id}"` is type-checked against the contract; so are the params
and the response. All components use hooks like this one: there is no `fetch` anywhere else,
and an ESLint rule (`no-restricted-globals: fetch`) enforces that.

### 3. Mock the backend

`npm run mock` starts Prism, which reads the contract and serves fake responses that match
it. You can build and click through the whole UI before writing a line of Python.

### 4. Test the backend against the contract

This is the step most tutorials skip, and it's the one that matters most with an agent.
FastAPI generates its own OpenAPI document from the Python code. The test
[test_contract.py](../backend/tests/unit/test_contract.py) loads both specs and compares:

- the same set of `(path, method)` operations,
- operationIds, parameters, success status codes, request/response schema names,
- for every schema: property names, required fields and enum values.

```python
def test_component_schemas_match(contract, generated):
    ...
    if cp != gp:
        problems.append(f"{name}.properties: contract-only={cp - gp} backend-only={gp - cp}")
```

If the agent adds a field to a Pydantic model but not to the contract, CI goes red with a
precise message. That turns "the agent drifted" from a production bug into a failing test.

## A real story: the contract changed for a good reason

Midway through, the agent read the current Claude API documentation before writing the LLM
provider and discovered that current Claude models **reject sampling parameters** like
`temperature`. My contract had `temperature: number, default 0`. The right move was to change
the contract (nullable, default `null`, "leave null for models that reject sampling
parameters"), regenerate the client, then update the backend in that order. Contract first
also means *changes* start in the contract.

Later (Part 9) we make this rule unbreakable: a hook blocks edits to `openapi.yaml` unless a
contract review happened first.

## Frontend structure in one picture

```text
src/api/schema.d.ts   generated from openapi.yaml
src/api/client.ts     createClient + auth middleware + error unwrapping (the only HTTP code)
src/api/hooks.ts      TanStack Query hooks: one per endpoint
src/lib/*.ts          pure logic (formatting, compare filtering): unit tested
src/components, pages UI, which only calls hooks
```

**TanStack Query** handles caching, loading and error states, refetching after mutations,
and polling. That's why the run page shows live progress with zero extra code.

## Testing the frontend

Twenty-six Vitest tests cover what's worth testing:

- pure logic: percentage formatting, how the compare table filters and sorts ("worst
  regressions first"), a tiny word-diff,
- the API client: it attaches the token, turns error bodies into readable messages, and logs
  you out on 401,
- components with React Testing Library: the compare table expands into a side-by-side diff;
  the evaluator form refuses invalid JSON *without* calling the API.

Pages are covered by the end-to-end test in Part 6.

**Next:** [Part 3: Building the backend from the contract](03-backend.md).
