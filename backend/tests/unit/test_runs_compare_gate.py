"""US-6 runs, US-7 compare and US-8 gate, executed by the real worker code with FakeProvider."""

from app.services.analysis import SCORE_TOLERANCE
from tests.conftest import (
    SUPPORT_TEMPLATE_V1,
    SUPPORT_TEMPLATE_V2,
    Api,
    add_support_evaluators,
)


async def setup_project(api: Api) -> dict[str, int]:
    ids = await api.project_with_dataset()
    await add_support_evaluators(api, ids["project_id"])
    return ids


async def test_run_lifecycle_and_summary(api: Api) -> None:
    ids = await setup_project(api)
    pid, ds = ids["project_id"], ids["dataset_id"]
    v1 = await api.version(pid, "v1", SUPPORT_TEMPLATE_V1)
    queued = await api.ok(
        "POST", f"/projects/{pid}/runs", 202, json={"prompt_version_id": v1, "dataset_id": ds}
    )
    assert queued["status"] == "queued" and queued["progress"] == {"done": 0, "total": 5}
    assert queued["triggered_by"] == "ui" and queued["summary"] is None

    assert await api.drain() == [queued["id"]]
    run = await api.ok("GET", f"/runs/{queued['id']}")
    assert run["status"] == "succeeded" and run["progress"] == {"done": 5, "total": 5}
    s = run["summary"]
    assert s["pass_rate"] == 1.0 and s["errored"] == 0
    assert set(s["mean_scores"]) == {"mentions-topic", "json-answer", "polite-and-correct"}
    assert run["total_tokens"] > 0 and run["cost_usd"] > 0
    assert run["started_at"] and run["finished_at"]

    results = await api.ok("GET", f"/runs/{run['id']}/results")
    assert len(results) == 5
    assert all(r["passed"] and len(r["scores"]) == 3 for r in results)
    assert results[0]["inputs"]["question"] and results[0]["expected_output"]
    assert [r["prompt_label"] for r in await api.ok("GET", f"/projects/{pid}/runs")] == ["v1"]


async def test_run_guardrails(api: Api) -> None:
    ids = await api.project_with_dataset()
    pid, ds = ids["project_id"], ids["dataset_id"]
    v1 = await api.version(pid, "v1", SUPPORT_TEMPLATE_V1)
    body = {"prompt_version_id": v1, "dataset_id": ds}
    r = await api.ok("POST", f"/projects/{pid}/runs", 422, json=body)
    assert "evaluators" in r["detail"]
    await add_support_evaluators(api, pid)
    api.app.state.settings.max_cases_per_run = 3
    r = await api.ok("POST", f"/projects/{pid}/runs", 422, json=body)
    assert "MAX_CASES_PER_RUN" in r["detail"]
    empty = await api.ok("POST", f"/projects/{pid}/datasets", 201, json={"name": "empty"})
    await api.ok(
        "POST",
        f"/projects/{pid}/runs",
        422,
        json={"prompt_version_id": v1, "dataset_id": empty["id"]},
    )
    await api.ok(
        "POST", f"/projects/{pid}/runs", 404, json={"prompt_version_id": 999, "dataset_id": ds}
    )


async def test_cost_limit_stops_run(api: Api) -> None:
    ids = await setup_project(api)
    pid = ids["project_id"]
    api.app.state.settings.max_cost_per_run_usd = 0.0000001
    api.app.state.settings.worker_concurrency = 1
    v1 = await api.version(pid, "v1", SUPPORT_TEMPLATE_V1)
    run = await api.run(pid, v1, ids["dataset_id"])
    assert run["status"] == "failed" and "cost limit" in run["error"]
    assert run["progress"]["done"] < run["progress"]["total"]


async def test_case_errors_are_recorded_not_fatal(api: Api) -> None:
    ids = await setup_project(api)
    pid = ids["project_id"]
    api.fake.script("Where is my order?", error="simulated 529 overloaded")
    v1 = await api.version(pid, "v1", SUPPORT_TEMPLATE_V1)
    run = await api.run(pid, v1, ids["dataset_id"])
    assert run["status"] == "succeeded"
    assert run["summary"]["errored"] == 1 and run["summary"]["passed"] == 4
    results = await api.ok("GET", f"/runs/{run['id']}/results")
    failed = [r for r in results if r["error"]]
    assert len(failed) == 1 and "overloaded" in failed[0]["error"] and failed[0]["output"] is None


async def test_missing_template_variable_is_a_case_error(api: Api) -> None:
    ids = await setup_project(api)
    v = await api.version(ids["project_id"], "v1", "{{nonexistent}}")
    run = await api.run(ids["project_id"], v, ids["dataset_id"])
    assert run["summary"]["errored"] == 5 and run["summary"]["pass_rate"] == 0


async def test_compare_finds_regressions(api: Api) -> None:
    ids = await setup_project(api)
    pid, ds = ids["project_id"], ids["dataset_id"]
    base = await api.run(pid, await api.version(pid, "v1", SUPPORT_TEMPLATE_V1), ds)
    head = await api.run(pid, await api.version(pid, "v2", SUPPORT_TEMPLATE_V2), ds)
    cmp = await api.ok("GET", "/runs/compare", params={"base": base["id"], "head": head["id"]})
    assert cmp["counts"]["regressed"] == 5 and cmp["counts"]["improved"] == 0
    assert cmp["pass_rate_delta"] == -1.0
    case = cmp["cases"][0]
    assert case["bucket"] == "regressed" and case["base_passed"] and not case["head_passed"]
    assert case["delta"] < -SCORE_TOLERANCE
    assert case["base_output"] != case["head_output"]
    assert cmp["base"]["prompt_label"] == "v1" and cmp["head"]["prompt_label"] == "v2"

    # Same comparison reversed: everything improves.
    rev = await api.ok("GET", "/runs/compare", params={"base": head["id"], "head": base["id"]})
    assert rev["counts"]["improved"] == 5


async def test_compare_requires_same_dataset(api: Api) -> None:
    ids = await setup_project(api)
    pid = ids["project_id"]
    other = await api.ok("POST", f"/projects/{pid}/datasets", 201, json={"name": "d2"})
    await api.ok(
        "POST",
        f"/datasets/{other['id']}/cases",
        201,
        json={"inputs": {"customer": "x", "question": "q"}},
    )
    v1 = await api.version(pid, "v1", SUPPORT_TEMPLATE_V1)
    a = await api.run(pid, v1, ids["dataset_id"])
    b = await api.run(pid, v1, other["id"])
    await api.ok("GET", "/runs/compare", 422, params={"base": a["id"], "head": b["id"]})


async def gate_key(api: Api, pid: int) -> dict[str, str]:
    created = await api.ok("POST", f"/projects/{pid}/api-keys", 201, json={"name": "ci"})
    return {"X-API-Key": created["key"]}


async def test_gate_fails_on_worse_prompt_and_passes_on_good_one(api: Api) -> None:
    ids = await setup_project(api)
    pid, ds = ids["project_id"], ids["dataset_id"]
    key = await gate_key(api, pid)
    await api.version(pid, "v1", SUPPORT_TEMPLATE_V1)

    # First gate: baseline v1 has never run, so the gate queues it too.
    good = await api.ok(
        "POST",
        "/gate",
        202,
        headers=key,
        json={
            "dataset_id": ds,
            "head_label": "v1-copy",
            "template": SUPPORT_TEMPLATE_V1,
            "baseline_label": "v1",
            "git_sha": "abc123",
        },
    )
    assert good["verdict"] == "pending" and good["baseline_run_id"] is not None
    await api.drain()
    verdict = await api.ok("GET", f"/gate/{good['run_id']}", headers=key)
    assert verdict["verdict"] == "pass", verdict["reasons"]
    assert verdict["regressions"] == 0 and verdict["pass_rate"] == 1.0

    bad = await api.ok(
        "POST",
        "/gate",
        202,
        headers=key,
        json={
            "dataset_id": ds,
            "head_label": "v2",
            "template": SUPPORT_TEMPLATE_V2,
            "baseline_label": "v1",
        },
    )
    await api.drain()
    verdict = await api.ok("GET", f"/gate/{bad['run_id']}", headers=key)
    assert verdict["verdict"] == "fail"
    assert verdict["regressions"] == 5
    assert any("pass rate 0%" in r for r in verdict["reasons"])
    run = await api.ok("GET", f"/runs/{bad['run_id']}", headers=key)
    assert run["triggered_by"] == "ci"


async def test_gate_respects_custom_policy_and_immutability(api: Api) -> None:
    ids = await setup_project(api)
    pid, ds = ids["project_id"], ids["dataset_id"]
    key = await gate_key(api, pid)
    await api.ok(
        "PUT",
        f"/projects/{pid}/gate-policy",
        json={"min_pass_rate": 0, "max_regressions": 10, "max_cost_increase_pct": 1000},
    )
    await api.ok(
        "PUT",
        f"/projects/{pid}/gate-policy",
        403,
        headers=key,
        json={"min_pass_rate": 0, "max_regressions": 1, "max_cost_increase_pct": 1},
    )
    first = await api.ok(
        "POST",
        "/gate",
        202,
        headers=key,
        json={"dataset_id": ds, "head_label": "v2", "template": SUPPORT_TEMPLATE_V2},
    )
    await api.drain()
    result = await api.ok("GET", f"/gate/{first['run_id']}", headers=key)
    assert result["verdict"] == "pass"
    assert any("no baseline" in r for r in result["reasons"])
    # Same label, different template: rejected because versions are immutable.
    r = await api.ok(
        "POST",
        "/gate",
        409,
        headers=key,
        json={"dataset_id": ds, "head_label": "v2", "template": "changed"},
    )
    assert "immutable" in r["detail"]


async def test_api_key_runs_are_tagged_agent(api: Api) -> None:
    ids = await setup_project(api)
    pid = ids["project_id"]
    key = await gate_key(api, pid)
    v1 = await api.version(pid, "v1", SUPPORT_TEMPLATE_V1)
    run = await api.ok(
        "POST",
        f"/projects/{pid}/runs",
        202,
        headers=key,
        json={"prompt_version_id": v1, "dataset_id": ids["dataset_id"]},
    )
    assert run["triggered_by"] == "agent"
