"""`python -m app.seed`: create a demo user, project, 30-case dataset, evaluators, two prompt
versions and two finished runs, so a fresh install has something to look at.

Idempotent: if the demo user already exists nothing is changed.
Options:
  --api-key-out PATH   also create a project API key and write it to PATH (for CI/E2E)
  --no-runs            skip executing the demo runs
"""

import argparse
import asyncio
import json
from pathlib import Path

from app.config import get_settings
from app.db import make_engine, make_sessionmaker, run_async
from app.llm import build_provider
from app.repositories import Repo
from app.schemas import (
    ApiKeyCreate,
    DatasetCreate,
    EvaluatorCreate,
    GatePolicy,
    ProjectCreate,
    PromptVersionCreate,
    RunCreate,
)
from app.services.core import (
    AuthService,
    DatasetService,
    EvaluatorService,
    ProjectService,
    PromptService,
)
from app.services.runs import RunService
from app.services.security import Principal
from app.worker import drain

DATA = Path(__file__).parent / "seed_data" / "support_cases.jsonl"
DEMO_EMAIL = "demo@evalops.dev"

V1 = (
    "You are a polite, friendly support agent for an online store.\n"
    "Reply in JSON with a single field 'answer'. Mention the customer's topic explicitly.\n"
    "Customer {{customer}} asks:\n{{question}}"
)
V2 = (
    "You are a support agent. Be terse: answer in one word.\n"
    "Customer {{customer}} asks:\n{{question}}"
)


async def seed(api_key_out: Path | None, run_demo: bool) -> None:
    settings = get_settings()
    engine = make_engine(settings)
    maker = make_sessionmaker(engine)
    try:
        async with maker() as s:
            repo = Repo(s)
            if await repo.user_by_email(DEMO_EMAIL):
                print(f"demo user {DEMO_EMAIL} already exists; nothing to do")
                return
            user = await AuthService(repo, settings).register(
                DEMO_EMAIL, settings.demo_password.get_secret_value()
            )
            p = Principal(kind="user", user_id=user.id)
            project = await ProjectService(repo, settings).create(
                p,
                ProjectCreate(
                    name="Support reply generator",
                    description="Demo: customer-support replies graded for topic, JSON and tone.",
                ),
            )
            ds = await DatasetService(repo, settings).create(
                p, project.id, DatasetCreate(name="golden-support-v1")
            )
            report = await DatasetService(repo, settings).import_file(
                p, ds.id, DATA.name, DATA.read_bytes()
            )
            evaluators = EvaluatorService(repo, settings)
            await evaluators.create(
                p, project.id, EvaluatorCreate(type="contains", name="mentions-topic")
            )
            await evaluators.create(
                p,
                project.id,
                EvaluatorCreate(
                    type="json_schema",
                    name="json-answer",
                    config={
                        "schema": {
                            "type": "object",
                            "required": ["answer"],
                            "properties": {"answer": {"type": "string", "minLength": 1}},
                        }
                    },
                ),
            )
            await evaluators.create(
                p,
                project.id,
                EvaluatorCreate(
                    type="llm_judge",
                    name="polite-and-correct",
                    config={"rubric": "Is the reply polite and correct?", "threshold": 4},
                    weight=2,
                ),
            )
            await ProjectService(repo, settings).put_policy(
                p,
                project.id,
                GatePolicy(min_pass_rate=0.8, max_regressions=0, max_cost_increase_pct=20),
            )
            prompts = PromptService(repo, settings)
            v1 = await prompts.create(p, project.id, PromptVersionCreate(label="v1", template=V1))
            v2 = await prompts.create(p, project.id, PromptVersionCreate(label="v2", template=V2))
            if api_key_out:
                key = await ProjectService(repo, settings).create_key(
                    p, project.id, ApiKeyCreate(name="seed")
                )
                key_info = {"api_key": key.key, "project_id": project.id, "dataset_id": ds.id}
            if run_demo:
                runs = RunService(repo, settings)
                await runs.create(
                    p, project.id, RunCreate(prompt_version_id=v1.id, dataset_id=ds.id)
                )
                await runs.create(
                    p, project.id, RunCreate(prompt_version_id=v2.id, dataset_id=ds.id)
                )
        if api_key_out:
            await asyncio.to_thread(api_key_out.write_text, json.dumps(key_info))
        if run_demo:
            await drain(maker, build_provider(settings), settings)
        print(
            f"seeded project {project.id} with {report.imported} cases; "
            f"login as {DEMO_EMAIL} (password from DEMO_PASSWORD)"
        )
    finally:
        await engine.dispose()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--api-key-out", type=Path)
    parser.add_argument("--no-runs", action="store_true")
    args = parser.parse_args()
    run_async(seed(args.api_key_out, not args.no_runs))


if __name__ == "__main__":
    main()
