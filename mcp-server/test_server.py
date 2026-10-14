"""MCP server tests against a fake EvalOps API (httpx.MockTransport). No network, no LLM."""

import json
from typing import Any

import httpx
import pytest

import server
from mcp.server.mcpserver.exceptions import ToolError

RUN = {
    "id": 2,
    "project_id": 1,
    "prompt_label": "v2",
    "dataset_id": 1,
    "status": "succeeded",
    "progress": {"done": 2, "total": 2},
    "summary": {"pass_rate": 0.5, "mean_score": 0.5},
    "cost_usd": 0.01,
    "git_sha": None,
    "triggered_by": "agent",
    "created_at": "2026-10-14T00:00:00Z",
    "error": None,
}
CASES = [
    {
        "test_case_id": 1,
        "bucket": "regressed",
        "delta": -1.0,
        "inputs": {"q": "refund?"},
        "expected_output": "refund",
        "base_output": "Thanks! Refund approved.",
        "head_output": "x" * 2000,
        "base_score": 1.0,
        "head_score": 0.0,
    },
    {
        "test_case_id": 2,
        "bucket": "unchanged",
        "delta": 0,
        "inputs": {"q": "order?"},
        "expected_output": "order",
        "base_output": "a",
        "head_output": "a",
        "base_score": 1.0,
        "head_score": 1.0,
    },
]
seen: list[httpx.Request] = []


def handler(request: httpx.Request) -> httpx.Response:
    seen.append(request)
    assert request.headers["X-API-Key"] == "eo_test"
    path, method = request.url.path.removeprefix("/api/v1"), request.method
    if path == "/projects":
        return httpx.Response(200, json=[{"id": 1, "name": "Support", "description": ""}])
    if path == "/projects/1/prompt-versions":
        return httpx.Response(200, json=[{"id": 5, "label": "v2", "model": "m", "variables": ["q"]}])
    if path == "/projects/1/runs" and method == "POST":
        body = json.loads(request.content)
        assert body == {"prompt_version_id": 5, "dataset_id": 1, "git_sha": "abc"}
        return httpx.Response(202, json=RUN | {"status": "queued"})
    if path == "/projects/1/runs":
        return httpx.Response(200, json=[RUN])
    if path == "/runs/2":
        return httpx.Response(200, json=RUN)
    if path == "/runs/2/results":
        return httpx.Response(
            200,
            json=[{"test_case_id": 1, "passed": False, "score": 0, "error": None, "output": "o", "scores": []}],
        )
    if path == "/runs/compare":
        return httpx.Response(
            200,
            json={
                "base": RUN | {"id": 1, "prompt_label": "v1"},
                "head": RUN,
                "counts": {"regressed": 1, "improved": 0, "unchanged": 1, "added": 0, "removed": 0},
                "pass_rate_delta": -0.5,
                "cost_delta_pct": 3.0,
                "cases": CASES,
            },
        )
    if path == "/runs/404":
        return httpx.Response(404, json={"detail": "run not found"})
    return httpx.Response(500, json={"detail": f"unexpected {method} {path}"})


@pytest.fixture(autouse=True)
def fake_api() -> None:
    seen.clear()
    server.configure(
        httpx.AsyncClient(
            transport=httpx.MockTransport(handler),
            base_url="http://evalops/api/v1",
            headers={"X-API-Key": "eo_test"},
        )
    )


def structured(result: Any) -> Any:
    assert not result.is_error, result.content
    return result.structured_content["result"] if "result" in result.structured_content else result.structured_content


async def test_exposes_expected_tools_with_read_only_hints() -> None:
    tools = {t.name: t for t in await server.mcp.list_tools()}
    assert set(tools) == {
        "list_projects",
        "list_prompt_versions",
        "list_runs",
        "start_run",
        "get_run_summary",
        "compare_runs",
        "get_regressions",
    }
    writers = {n for n, t in tools.items() if not t.annotations.read_only_hint}
    assert writers == {"start_run"}  # the only tool that changes state


async def test_list_projects_and_runs() -> None:
    assert structured(await server.mcp.call_tool("list_projects", {}))[0]["name"] == "Support"
    runs = structured(await server.mcp.call_tool("list_runs", {"project_id": 1}))
    assert runs[0]["pass_rate"] == 0.5 and runs[0]["progress"] == "2/2"


async def test_start_run_resolves_label() -> None:
    run = structured(
        await server.mcp.call_tool(
            "start_run", {"project_id": 1, "dataset_id": 1, "prompt_label": "v2", "git_sha": "abc"}
        )
    )
    assert run["status"] == "queued"


async def test_start_run_unknown_label_is_a_tool_error() -> None:
    with pytest.raises(ToolError, match="available: v2"):
        await server.mcp.call_tool(
            "start_run", {"project_id": 1, "dataset_id": 1, "prompt_label": "nope"}
        )


async def test_regressions_are_filtered_sorted_and_truncated() -> None:
    out = structured(
        await server.mcp.call_tool("get_regressions", {"base_run_id": 1, "head_run_id": 2})
    )
    assert out["total_regressed"] == 1
    case = out["cases"][0]
    assert case["test_case_id"] == 1 and case["inputs"] == {"q": "refund?"}
    assert len(case["head_output"]) < 700 and "more chars" in case["head_output"]


async def test_api_errors_surface_as_tool_errors() -> None:
    with pytest.raises(ToolError, match="run not found"):
        await server.mcp.call_tool("get_run_summary", {"run_id": 404})


async def test_run_resource_and_triage_prompt() -> None:
    contents = list(await server.mcp.read_resource("evalops://runs/2"))
    payload = json.loads(contents[0].content)
    assert payload["run"]["run_id"] == 2 and payload["results"][0]["test_case_id"] == 1
    prompt = await server.mcp.get_prompt("triage-regression", {"base_run_id": "1", "head_run_id": "2"})
    text = prompt.messages[0].content.text
    assert "compare_runs(base_run_id=1, head_run_id=2)" in text and "untrusted" in text
