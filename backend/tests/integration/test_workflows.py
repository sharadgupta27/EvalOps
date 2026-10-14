"""Key workflows end to end on Postgres: import -> run -> compare -> gate, plus the job queue."""

import asyncio
from pathlib import Path

import pytest
from fastapi import FastAPI

from app.models import EvalRun, RunStatus, TriggeredBy
from app.repositories import Repo
from tests.conftest import SUPPORT_TEMPLATE_V1, SUPPORT_TEMPLATE_V2, Api, add_support_evaluators

pytestmark = pytest.mark.integration

SEED_CASES = Path(__file__).resolve().parents[2] / "app" / "seed_data" / "support_cases.jsonl"


async def test_import_run_compare_gate(api: Api) -> None:
    project = await api.ok("POST", "/projects", 201, json={"name": "Support reply generator"})
    pid = project["id"]
    ds = await api.ok("POST", f"/projects/{pid}/datasets", 201, json={"name": "golden"})
    files = {"file": ("support.jsonl", SEED_CASES.read_bytes(), "application/x-ndjson")}
    report = await api.ok("POST", f"/datasets/{ds['id']}/import", files=files)
    assert report == {"imported": 30, "errors": []}
    await add_support_evaluators(api, pid)

    v1 = await api.version(pid, "v1", SUPPORT_TEMPLATE_V1)
    base = await api.run(pid, v1, ds["id"])
    assert base["status"] == "succeeded" and base["summary"]["pass_rate"] == 1.0
    assert base["progress"] == {"done": 30, "total": 30}

    v2 = await api.version(pid, "v2", SUPPORT_TEMPLATE_V2)
    head = await api.run(pid, v2, ds["id"])
    cmp = await api.ok("GET", "/runs/compare", params={"base": base["id"], "head": head["id"]})
    assert cmp["counts"]["regressed"] == 30

    key = (await api.ok("POST", f"/projects/{pid}/api-keys", 201, json={"name": "ci"}))["key"]
    gate = await api.ok(
        "POST",
        "/gate",
        202,
        headers={"X-API-Key": key},
        json={"dataset_id": ds["id"], "head_label": "v2", "baseline_run_id": base["id"]},
    )
    await api.drain()
    verdict = await api.ok("GET", f"/gate/{gate['run_id']}", headers={"X-API-Key": key})
    assert verdict["verdict"] == "fail" and verdict["regressions"] == 30


async def test_cascade_delete_on_postgres(api: Api) -> None:
    ids = await api.project_with_dataset()
    await add_support_evaluators(api, ids["project_id"])
    v1 = await api.version(ids["project_id"], "v1", SUPPORT_TEMPLATE_V1)
    await api.run(ids["project_id"], v1, ids["dataset_id"])
    await api.ok("DELETE", f"/projects/{ids['project_id']}", 204)
    await api.ok("GET", f"/datasets/{ids['dataset_id']}", 404)


async def test_skip_locked_claims_each_run_once(api: Api, app: FastAPI) -> None:
    ids = await api.project_with_dataset()
    await add_support_evaluators(api, ids["project_id"])
    v1 = await api.version(ids["project_id"], "v1", SUPPORT_TEMPLATE_V1)
    maker = app.state.sessionmaker
    async with maker() as s:
        for _ in range(6):
            s.add(
                EvalRun(
                    project_id=ids["project_id"],
                    prompt_version_id=v1,
                    dataset_id=ids["dataset_id"],
                    status=RunStatus.queued,
                    triggered_by=TriggeredBy.ui,
                )
            )
        await s.commit()

    async def claimer() -> list[int]:
        claimed: list[int] = []
        while True:
            async with maker() as s:
                run = await Repo(s).claim_next_run()
            if run is None:
                return claimed
            claimed.append(run.id)

    results = await asyncio.gather(*(claimer() for _ in range(4)))
    all_ids = [i for r in results for i in r]
    assert len(all_ids) == 6 and len(set(all_ids)) == 6  # no run claimed twice
