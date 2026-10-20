"""POST /gate/ingest: results computed elsewhere (CiteSure) are gated like a native run."""

from typing import Any

from tests.conftest import SUPPORT_TEMPLATE_V1, Api

REFS = ["q-a", "q-b", "q-c", "q-d"]


async def ingest_dataset(api: Api, refs: list[str] | None = None) -> dict[str, int]:
    """A dataset shaped like an external system's export: every case has `inputs.case_ref`."""
    cases = [
        {"inputs": {"case_ref": ref, "question": f"question {ref}"}, "expected_output": "answer"}
        for ref in refs or REFS
    ]
    return await api.project_with_dataset(cases)


def results(passed: dict[str, bool] | None = None, **extra: Any) -> list[dict[str, Any]]:
    passed = passed or {}
    return [
        {
            "case_ref": ref,
            "output": f"out {ref}",
            "passed": passed.get(ref, True),
            "score": 1.0 if passed.get(ref, True) else 0.0,
            **extra,
        }
        for ref in REFS
    ]


async def key_for(api: Api, pid: int) -> dict[str, str]:
    created = await api.ok("POST", f"/projects/{pid}/api-keys", 201, json={"name": "ci"})
    return {"X-API-Key": created["key"]}


async def ingest(
    api: Api, key: dict[str, str], ds: int, label: str, status: int = 201, **body: Any
) -> Any:
    payload = {"dataset_id": ds, "head_label": label, "results": results(), **body}
    return await api.ok("POST", "/gate/ingest", status, headers=key, json=payload)


async def test_ingest_records_a_run_and_passes_without_baseline(api: Api) -> None:
    ids = await ingest_dataset(api)
    key = await key_for(api, ids["project_id"])
    gate = await ingest(api, key, ids["dataset_id"], "main", git_sha="abc123")

    assert gate["verdict"] == "pass" and gate["baseline_run_id"] is None
    assert gate["pass_rate"] == 1.0 and gate["regressions"] is None
    assert any("no baseline" in r for r in gate["reasons"])

    run = await api.ok("GET", f"/runs/{gate['run_id']}", headers=key)
    assert run["status"] == "succeeded" and run["triggered_by"] == "ci"
    assert run["prompt_label"] == "main" and run["git_sha"] == "abc123"
    assert run["progress"] == {"done": 4, "total": 4}
    assert run["summary"]["pass_rate"] == 1.0 and run["cost_usd"] == 0
    stored = await api.ok("GET", f"/runs/{run['id']}/results", headers=key)
    assert {r["inputs"]["case_ref"] for r in stored} == set(REFS)
    assert all(r["passed"] and r["scores"] == [] and r["output"] for r in stored)
    # The same verdict is readable afterwards through the normal gate endpoint.
    again = await api.ok("GET", f"/gate/{gate['run_id']}", headers=key)
    assert again["verdict"] == "pass"


async def test_ingest_finds_regressions_against_the_baseline_label(api: Api) -> None:
    ids = await ingest_dataset(api)
    ds = ids["dataset_id"]
    key = await key_for(api, ids["project_id"])
    base = await ingest(api, key, ds, "main")

    bad = await ingest(
        api,
        key,
        ds,
        "pr-7",
        baseline_label="main",
        results=results({"q-a": False, "q-b": False}),
    )
    assert bad["baseline_run_id"] == base["run_id"]
    assert bad["verdict"] == "fail" and bad["regressions"] == 2
    assert any("pass rate 50%" in r for r in bad["reasons"])
    cmp = await api.ok(
        "GET", "/runs/compare", params={"base": base["run_id"], "head": bad["run_id"]}
    )
    assert cmp["counts"]["regressed"] == 2 and cmp["counts"]["unchanged"] == 2
    assert {c["head_output"] for c in cmp["cases"]} == {f"out {ref}" for ref in REFS}


async def test_ingest_main_gates_against_the_previous_main_run(api: Api) -> None:
    ids = await ingest_dataset(api)
    ds = ids["dataset_id"]
    key = await key_for(api, ids["project_id"])
    first = await ingest(api, key, ds, "main")
    # A PR run in between must not become the baseline of the next main run.
    await ingest(api, key, ds, "pr-7", baseline_label="main", results=results({"q-a": False}))
    second = await ingest(api, key, ds, "main", baseline_label="main")
    assert second["baseline_run_id"] == first["run_id"] and second["verdict"] == "pass"


async def test_ingest_without_baseline_label_uses_the_latest_other_run(api: Api) -> None:
    ids = await ingest_dataset(api)
    ds = ids["dataset_id"]
    key = await key_for(api, ids["project_id"])
    first = await ingest(api, key, ds, "main")
    second = await ingest(api, key, ds, "pr-1")
    assert second["baseline_run_id"] == first["run_id"]


async def test_ingest_known_label_without_a_succeeded_run_skips_regression_checks(
    api: Api,
) -> None:
    ids = await ingest_dataset(api)
    pid, ds = ids["project_id"], ids["dataset_id"]
    key = await key_for(api, pid)
    await api.version(pid, "v1", SUPPORT_TEMPLATE_V1)  # exists, never ran
    gate = await ingest(api, key, ds, "pr-1", baseline_label="v1")
    assert gate["baseline_run_id"] is None
    assert any("no baseline" in r for r in gate["reasons"])


async def test_unknown_baseline_label_or_run_is_404(api: Api) -> None:
    ids = await ingest_dataset(api)
    ds = ids["dataset_id"]
    key = await key_for(api, ids["project_id"])
    r = await ingest(api, key, ds, "pr-1", 404, baseline_label="nope")
    assert "baseline version" in r["detail"]
    await ingest(api, key, ds, "pr-1", 404, baseline_run_id=9999)
    # Nothing was recorded by the failed calls.
    assert await api.ok("GET", f"/projects/{ids['project_id']}/runs") == []


async def test_results_must_cover_the_dataset_exactly(api: Api) -> None:
    ids = await ingest_dataset(api)
    ds = ids["dataset_id"]
    key = await key_for(api, ids["project_id"])
    sent = results()
    sent[1]["case_ref"] = "q-zzz"  # q-b is now missing and q-zzz is unknown
    sent.append(dict(sent[0]))  # q-a twice
    r = await ingest(api, key, ds, "pr-1", 422, results=sent)
    detail = r["detail"]
    assert "unknown case_ref: q-zzz" in detail
    assert "duplicate case_ref: q-a" in detail
    assert "missing case_ref: q-b" in detail
    assert "added to the dataset" in detail
    assert await api.ok("GET", f"/projects/{ids['project_id']}/runs") == []


async def test_dataset_cases_must_be_addressable(api: Api) -> None:
    ids = await api.project_with_dataset(
        [
            {"inputs": {"case_ref": "q-a"}},
            {"inputs": {"case_ref": "q-a"}},
            {"inputs": {"question": "no ref"}},
        ]
    )
    key = await key_for(api, ids["project_id"])
    r = await ingest(api, key, ids["dataset_id"], "pr-1", 422)
    assert "without inputs.case_ref" in r["detail"]
    assert "more than one test case" in r["detail"]


async def test_label_of_a_real_prompt_version_is_a_conflict(api: Api) -> None:
    ids = await ingest_dataset(api)
    pid, ds = ids["project_id"], ids["dataset_id"]
    key = await key_for(api, pid)
    await api.version(pid, "v1", SUPPORT_TEMPLATE_V1)
    r = await ingest(api, key, ds, "v1", 409)
    assert "real prompt version" in r["detail"]
    # Naming a real version's model "external" does not make it ingestable either.
    await api.ok(
        "POST",
        f"/projects/{pid}/prompt-versions",
        201,
        json={"label": "sneaky", "template": "t", "model": "external"},
    )
    await ingest(api, key, ds, "sneaky", 409)


async def test_reusing_a_label_adds_a_run_on_the_same_version(api: Api) -> None:
    ids = await ingest_dataset(api)
    key = await key_for(api, ids["project_id"])
    a = await ingest(api, key, ids["dataset_id"], "main")
    b = await ingest(api, key, ids["dataset_id"], "main")
    assert a["run_id"] != b["run_id"]
    runs = await api.ok("GET", f"/projects/{ids['project_id']}/runs")
    assert len(runs) == 2 and len({r["prompt_version_id"] for r in runs}) == 1


async def test_a_result_with_an_error_never_counts_as_passed(api: Api) -> None:
    ids = await ingest_dataset(api)
    key = await key_for(api, ids["project_id"])
    sent = results()
    sent[0].update(error="pipeline crashed", passed=True)
    gate = await ingest(api, key, ids["dataset_id"], "pr-1", results=sent)
    run = await api.ok("GET", f"/runs/{gate['run_id']}", headers=key)
    assert run["summary"]["passed"] == 3 and run["summary"]["errored"] == 1


async def test_policy_threshold_applies(api: Api) -> None:
    ids = await ingest_dataset(api)
    pid = ids["project_id"]
    key = await key_for(api, pid)
    await api.ok(
        "PUT",
        f"/projects/{pid}/gate-policy",
        json={"min_pass_rate": 1.0, "max_regressions": 10, "max_cost_increase_pct": 100},
    )
    gate = await ingest(api, key, ids["dataset_id"], "pr-1", results=results({"q-d": False}))
    assert gate["verdict"] == "fail" and gate["policy"]["min_pass_rate"] == 1.0


async def test_ingest_is_api_key_only_and_project_scoped(api: Api) -> None:
    ids = await ingest_dataset(api)
    ds = ids["dataset_id"]
    body = {"dataset_id": ds, "head_label": "pr-1", "results": results()}
    await api.ok("POST", "/gate/ingest", 401, json=body)  # a user JWT is not an API key
    other = await api.project_with_dataset()
    other_key = await key_for(api, other["project_id"])
    # Another project's key cannot see this dataset.
    await api.ok("POST", "/gate/ingest", 404, headers=other_key, json=body)


async def test_result_count_is_capped_by_the_run_limit(api: Api) -> None:
    ids = await ingest_dataset(api)
    key = await key_for(api, ids["project_id"])
    api.app.state.settings.max_cases_per_run = 3
    r = await ingest(api, key, ids["dataset_id"], "pr-1", 422)
    assert "MAX_CASES_PER_RUN" in r["detail"]


async def test_request_validation(api: Api) -> None:
    ids = await ingest_dataset(api)
    key = await key_for(api, ids["project_id"])
    ds = ids["dataset_id"]
    await ingest(api, key, ds, "bad label!", 422)
    await ingest(api, key, ds, "pr-1", 422, results=[])
    await ingest(
        api, key, ds, "pr-1", 422, results=[{"case_ref": "q-a", "passed": True, "score": 2}]
    )
    await ingest(
        api,
        key,
        ds,
        "pr-1",
        422,
        results=[{"case_ref": "q-a", "passed": True, "score": 1, "output": "x" * 5001}],
    )
