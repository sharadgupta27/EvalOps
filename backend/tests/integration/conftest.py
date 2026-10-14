"""Integration fixtures: a real Postgres 16 in Docker (testcontainers) migrated with Alembic."""

from collections.abc import AsyncIterator, Iterator
from pathlib import Path

import httpx
import pytest
from alembic import command
from alembic.config import Config
from fastapi import FastAPI
from sqlalchemy import text
from testcontainers.postgres import PostgresContainer  # community module not shipped yet

from app.main import create_app
from tests.conftest import make_settings

BACKEND = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="session")
def pg_url() -> Iterator[str]:
    with PostgresContainer("postgres:16-alpine", driver="psycopg") as pg:
        url = pg.get_connection_url()  # postgresql+psycopg://...
        cfg = Config(str(BACKEND / "alembic.ini"))
        cfg.set_main_option("script_location", str(BACKEND / "migrations"))
        cfg.attributes["database_url"] = url
        command.upgrade(cfg, "head")
        yield url


@pytest.fixture
async def app(pg_url: str) -> AsyncIterator[FastAPI]:
    application = create_app(make_settings(pg_url))
    yield application
    # Each test starts from empty tables; the schema itself comes from the migration.
    async with application.state.engine.begin() as conn:
        await conn.execute(
            text(
                "TRUNCATE users, projects, api_keys, prompt_versions, datasets, test_cases, "
                "evaluators, eval_runs, eval_results, gate_policies RESTART IDENTITY CASCADE"
            )
        )
    await application.state.engine.dispose()


@pytest.fixture
async def client(app: FastAPI) -> AsyncIterator[httpx.AsyncClient]:
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test/api/v1"
    ) as c:
        yield c
