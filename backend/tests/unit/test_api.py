"""API behaviour through HTTP, against SQLite. Mirrors the user stories in product-spec.md."""

import json

import httpx

from tests.conftest import (
    SUPPORT_TEMPLATE_V1,
    Api,
    add_support_evaluators,
    register_and_login,
)


# --- US-1 auth -------------------------------------------------------------------
async def test_register_login_me(client: httpx.AsyncClient) -> None:
    headers = await register_and_login(client)
    r = await client.get("/auth/me", headers=headers)
    assert r.status_code == 200 and r.json()["email"] == "priya@example.com"


async def test_duplicate_email_conflicts(client: httpx.AsyncClient) -> None:
    await register_and_login(client)
    r = await client.post(
        "/auth/register", json={"email": "PRIYA@example.com", "password": "x" * 10}
    )
    assert r.status_code == 409


async def test_bad_password_and_missing_token(client: httpx.AsyncClient) -> None:
    await register_and_login(client)
    r = await client.post(
        "/auth/login", json={"email": "priya@example.com", "password": "nope-nope"}
    )
    assert r.status_code == 401
    assert (await client.get("/projects")).status_code == 401
    r = await client.get("/projects", headers={"Authorization": "Bearer garbage"})
    assert r.status_code == 401


async def test_short_password_rejected(client: httpx.AsyncClient) -> None:
    r = await client.post("/auth/register", json={"email": "a@b.co", "password": "short"})
    assert r.status_code == 422


async def test_users_cannot_see_each_others_projects(api: Api) -> None:
    ids = await api.project_with_dataset()
    other = await register_and_login(api.client, "marco@example.com")
    r = await api.client.get(f"/projects/{ids['project_id']}", headers=other)
    assert r.status_code == 404
    r = await api.client.get(f"/datasets/{ids['dataset_id']}/cases", headers=other)
    assert r.status_code == 404
    assert (await api.client.get("/projects", headers=other)).json() == []


# --- US-2 projects -----------------------------------------------------------------
async def test_project_crud_and_cascade(api: Api) -> None:
    ids = await api.project_with_dataset()
    pid = ids["project_id"]
    p = await api.ok("PATCH", f"/projects/{pid}", json={"name": "Renamed"})
    assert p["name"] == "Renamed" and p["description"] == ""
    assert len(await api.ok("GET", "/projects")) == 1
    await api.ok("DELETE", f"/projects/{pid}", 204)
    await api.ok("GET", f"/projects/{pid}", 404)
    await api.ok("GET", f"/datasets/{ids['dataset_id']}", 404)


# --- US-3 prompt versions ------------------------------------------------------------
async def test_versions_are_immutable_and_default_model(api: Api) -> None:
    pid = (await api.ok("POST", "/projects", 201, json={"name": "p"}))["id"]
    v = await api.ok(
        "POST",
        f"/projects/{pid}/prompt-versions",
        201,
        json={"label": "v1", "template": "Hi {{name}}"},
    )
    assert v["model"] == api.app.state.settings.default_model
    assert v["variables"] == ["name"]
    assert v["params"] == {"temperature": None, "max_tokens": 2048, "system": ""}
    await api.ok(
        "POST", f"/projects/{pid}/prompt-versions", 409, json={"label": "v1", "template": "other"}
    )
    r = await api.client.request(
        "PATCH", f"/projects/{pid}/prompt-versions", headers=api.headers, json={}
    )
    assert r.status_code == 405
    await api.ok(
        "POST",
        f"/projects/{pid}/prompt-versions",
        422,
        json={"label": "bad label!", "template": "x"},
    )


# --- US-4 datasets ------------------------------------------------------------------
async def test_case_crud(api: Api) -> None:
    ids = await api.project_with_dataset([])
    ds = ids["dataset_id"]
    c = await api.ok("POST", f"/datasets/{ds}/cases", 201, json={"inputs": {"q": "hi"}})
    assert c["tags"] == [] and c["expected_output"] is None
    c = await api.ok(
        "PATCH", f"/datasets/{ds}/cases/{c['id']}", json={"expected_output": "hello", "tags": ["a"]}
    )
    assert c["expected_output"] == "hello" and c["inputs"] == {"q": "hi"}
    assert (await api.ok("GET", f"/datasets/{ds}"))["case_count"] == 1
    await api.ok("DELETE", f"/datasets/{ds}/cases/{c['id']}", 204)
    await api.ok("DELETE", f"/datasets/{ds}/cases/{c['id']}", 404)


async def test_csv_import_reports_bad_rows(api: Api) -> None:
    ds = (await api.project_with_dataset([]))["dataset_id"]
    csv_text = (
        "question,customer,expected_output,tags\n"
        "How do refunds work?,Ann,refund,billing;faq\n"
        ",,orphan,\n"
        "Where is my order?,Bob,order,\n"
    )
    files = {"file": ("cases.csv", csv_text.encode(), "text/csv")}
    report = await api.ok("POST", f"/datasets/{ds}/import", files=files)
    assert report["imported"] == 2
    assert report["errors"] == [{"row": 2, "message": "all input columns are empty"}]
    cases = await api.ok("GET", f"/datasets/{ds}/cases")
    assert cases[0]["inputs"] == {"question": "How do refunds work?", "customer": "Ann"}
    assert cases[0]["tags"] == ["billing", "faq"]


async def test_jsonl_import(api: Api) -> None:
    ds = (await api.project_with_dataset([]))["dataset_id"]
    lines = [
        json.dumps({"inputs": {"q": "a"}, "expected_output": "A", "tags": ["x"]}),
        "{not json",
        json.dumps({"inputs": {}}),
        json.dumps({"inputs": {"q": "b"}}),
    ]
    files = {"file": ("cases.jsonl", "\n".join(lines).encode(), "application/x-ndjson")}
    report = await api.ok("POST", f"/datasets/{ds}/import", files=files)
    assert report["imported"] == 2
    assert [e["row"] for e in report["errors"]] == [2, 3]


async def test_import_limits(api: Api) -> None:
    ds = (await api.project_with_dataset([]))["dataset_id"]
    files = {"file": ("cases.txt", b"x", "text/plain")}
    await api.ok("POST", f"/datasets/{ds}/import", 422, files=files)
    big = b"q\n" + b"a" * (api.app.state.settings.max_upload_bytes + 10)
    await api.ok(
        "POST", f"/datasets/{ds}/import", 413, files={"file": ("big.csv", big, "text/csv")}
    )
    huge = b"q\n" + b"a" * (api.app.state.settings.max_upload_bytes + 200_000)
    r = await api.ok(
        "POST", f"/datasets/{ds}/import", 413, files={"file": ("huge.csv", huge, "text/csv")}
    )
    assert r["detail"] == "request body too large"  # rejected before multipart parsing


# --- US-5 evaluators -------------------------------------------------------------------
async def test_evaluator_config_validated_per_type(api: Api) -> None:
    pid = (await api.project_with_dataset())["project_id"]
    await api.ok("POST", f"/projects/{pid}/evaluators", 422, json={"type": "regex", "name": "r"})
    e = await api.ok(
        "POST",
        f"/projects/{pid}/evaluators",
        201,
        json={"type": "regex", "name": "r", "config": {"pattern": "\\d"}, "weight": 2},
    )
    assert e["config"] == {"pattern": "\\d", "must_match": True}
    e = await api.ok(
        "PATCH", f"/projects/{pid}/evaluators/{e['id']}", json={"config": {"pattern": "x"}}
    )
    assert e["config"]["pattern"] == "x" and e["weight"] == 2
    await api.ok(
        "PATCH", f"/projects/{pid}/evaluators/{e['id']}", 422, json={"config": {"pattern": "("}}
    )
    await api.ok("DELETE", f"/projects/{pid}/evaluators/{e['id']}", 204)
    assert await api.ok("GET", f"/projects/{pid}/evaluators") == []


# --- API keys and scope ----------------------------------------------------------------
async def test_api_key_shown_once_scoped_and_revocable(api: Api) -> None:
    ids = await api.project_with_dataset()
    pid = ids["project_id"]
    other = await api.ok("POST", "/projects", 201, json={"name": "other"})
    created = await api.ok("POST", f"/projects/{pid}/api-keys", 201, json={"name": "ci"})
    secret = created["key"]
    listed = await api.ok("GET", f"/projects/{pid}/api-keys")
    assert "key" not in listed[0] and listed[0]["prefix"] == secret[:10]

    key = {"X-API-Key": secret}
    assert [p["id"] for p in await api.ok("GET", "/projects", headers=key)] == [pid]
    await api.ok("GET", f"/projects/{other['id']}", 404, headers=key)
    # Keys may read and run, but not manage the project.
    await api.ok("DELETE", f"/projects/{pid}", 403, headers=key)
    await api.ok("POST", f"/projects/{pid}/api-keys", 403, headers=key, json={"name": "x"})
    await api.ok(
        "POST", f"/datasets/{ids['dataset_id']}/cases", 403, headers=key, json={"inputs": {"a": 1}}
    )

    await api.ok("DELETE", f"/projects/{pid}/api-keys/{created['id']}", 204)
    await api.ok("GET", "/projects", 401, headers=key)


async def test_gate_requires_api_key(api: Api) -> None:
    await api.ok("POST", "/gate", 401, json={"dataset_id": 1, "head_label": "v1"})


async def test_health_metrics_and_headers(app: object, client: httpx.AsyncClient) -> None:
    root = httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test")  # type: ignore[arg-type]
    async with root:
        r = await root.get("/healthz")
        assert r.json()["status"] == "ok"
        assert r.headers["x-content-type-options"] == "nosniff"
        await root.get("/api/v1/projects")
        metrics = (await root.get("/metrics")).text
        assert 'evalops_http_requests_total{method="GET",route="/projects",status="401"}' in metrics
        # Queue gauges come from the API too, so a dead worker cannot hide a stuck queue.
        assert "evalops_queue_depth 0.0" in metrics


async def test_rate_limit(tmp_path: object) -> None:
    from app.db import Base
    from app.main import create_app
    from tests.conftest import make_settings

    app = create_app(
        make_settings(f"sqlite+aiosqlite:///{tmp_path}/rl.db", rate_limit_per_minute=3)
    )
    async with app.state.engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://t") as c:
        # Rotating fake API keys must not reset the limit (regression test for the PR audit).
        codes = [
            (await c.get("/api/v1/projects", headers={"X-API-Key": f"fake-{i}"})).status_code
            for i in range(4)
        ]
    await app.state.engine.dispose()
    assert codes == [401, 401, 401, 429]


async def test_evaluators_attached_helper(api: Api) -> None:
    pid = (await api.project_with_dataset())["project_id"]
    await add_support_evaluators(api, pid)
    assert len(await api.ok("GET", f"/projects/{pid}/evaluators")) == 3
    await api.version(pid, "v1", SUPPORT_TEMPLATE_V1)
