import asyncio
import sys
from collections.abc import AsyncIterator, Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx
import pytest
from fastapi import FastAPI

from app.config import Settings
from app.db import Base
from app.llm.fake import FakeProvider
from app.main import create_app
from app.worker import drain

SUPPORT_TEMPLATE_V1 = (
    "You are a polite, friendly support agent. Reply in JSON with an 'answer' field.\n"
    "Customer {{customer}} asks:\n{{question}}"
)
SUPPORT_TEMPLATE_V2 = "Be terse: answer in one word.\nCustomer {{customer}} asks:\n{{question}}"


def make_settings(database_url: str, **overrides: Any) -> Settings:
    values: dict[str, Any] = {
        "environment": "test",
        "database_url": database_url,
        "llm_provider": "fake",
        "rate_limit_per_minute": 0,
        "worker_concurrency": 4,
        "bcrypt_rounds": 4,
    }
    return Settings(**(values | overrides))


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    return make_settings(f"sqlite+aiosqlite:///{tmp_path.as_posix()}/test.db")


@pytest.fixture
async def app(settings: Settings) -> AsyncIterator[FastAPI]:
    application = create_app(settings)
    async with application.state.engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield application
    await application.state.engine.dispose()


@pytest.fixture
async def client(app: FastAPI) -> AsyncIterator[httpx.AsyncClient]:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test/api/v1") as c:
        yield c


@pytest.fixture
def fake() -> FakeProvider:
    return FakeProvider()


@dataclass
class Api:
    """Small helper so tests read like the user journey."""

    client: httpx.AsyncClient
    app: FastAPI
    fake: FakeProvider
    headers: dict[str, str]

    async def ok(self, method: str, url: str, status: int = 200, **kw: Any) -> Any:
        kw.setdefault("headers", self.headers)
        r = await self.client.request(method, url, **kw)
        assert r.status_code == status, f"{method} {url} -> {r.status_code}: {r.text}"
        return r.json() if r.content else None

    async def drain(self) -> list[int]:
        return await drain(self.app.state.sessionmaker, self.fake, self.app.state.settings)

    async def project_with_dataset(
        self, cases: list[dict[str, Any]] | None = None
    ) -> dict[str, int]:
        project = await self.ok("POST", "/projects", 201, json={"name": "Support bot"})
        pid = project["id"]
        ds = await self.ok("POST", f"/projects/{pid}/datasets", 201, json={"name": "golden"})
        for case in default_cases() if cases is None else cases:
            await self.ok("POST", f"/datasets/{ds['id']}/cases", 201, json=case)
        return {"project_id": pid, "dataset_id": ds["id"]}

    async def version(self, project_id: int, label: str, template: str) -> int:
        v = await self.ok(
            "POST",
            f"/projects/{project_id}/prompt-versions",
            201,
            json={"label": label, "template": template},
        )
        return int(v["id"])

    async def run(self, project_id: int, version_id: int, dataset_id: int) -> dict[str, Any]:
        run = await self.ok(
            "POST",
            f"/projects/{project_id}/runs",
            202,
            json={"prompt_version_id": version_id, "dataset_id": dataset_id},
        )
        await self.drain()
        result: dict[str, Any] = await self.ok("GET", f"/runs/{run['id']}")
        return result


def default_cases() -> list[dict[str, Any]]:
    questions = [
        ("How do I get a refund?", "refund"),
        ("Where is my order?", "order"),
        ("Can I change my password?", "password"),
        ("Do you ship to Canada?", "Canada"),
        ("How do I cancel my subscription?", "subscription"),
    ]
    return [
        {"inputs": {"customer": f"C{i}", "question": q}, "expected_output": kw, "tags": ["faq"]}
        for i, (q, kw) in enumerate(questions)
    ]


async def register_and_login(
    client: httpx.AsyncClient, email: str = "priya@example.com"
) -> dict[str, str]:
    r = await client.post("/auth/register", json={"email": email, "password": "correct-horse-1"})
    assert r.status_code == 201, r.text
    r = await client.post("/auth/login", json={"email": email, "password": "correct-horse-1"})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


@pytest.fixture
async def api(client: httpx.AsyncClient, app: FastAPI, fake: FakeProvider) -> Api:
    return Api(client=client, app=app, fake=fake, headers=await register_and_login(client))


async def add_support_evaluators(api: Api, project_id: int) -> None:
    await api.ok(
        "POST",
        f"/projects/{project_id}/evaluators",
        201,
        json={"type": "contains", "name": "mentions-topic"},
    )
    await api.ok(
        "POST",
        f"/projects/{project_id}/evaluators",
        201,
        json={
            "type": "json_schema",
            "name": "json-answer",
            "config": {
                "schema": {
                    "type": "object",
                    "required": ["answer"],
                    "properties": {"answer": {"type": "string"}},
                }
            },
        },
    )
    await api.ok(
        "POST",
        f"/projects/{project_id}/evaluators",
        201,
        json={
            "type": "llm_judge",
            "name": "polite-and-correct",
            "config": {"rubric": "Is the reply polite and correct?", "threshold": 4},
        },
    )


def pytest_asyncio_loop_factories(
    config: pytest.Config, item: pytest.Item
) -> Mapping[str, Callable[[], asyncio.AbstractEventLoop]]:
    # psycopg's async driver cannot run on Windows' default Proactor loop.
    # pytest-asyncio rejects None from this hook, so other platforms must return
    # the default loop explicitly.
    if sys.platform == "win32":
        return {"selector": asyncio.SelectorEventLoop}
    return {"default": asyncio.new_event_loop}
