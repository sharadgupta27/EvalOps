"""All database access lives here. Services call repositories; routers never do."""

from collections.abc import Sequence
from datetime import UTC, datetime
from typing import Any, TypeVar

from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    ApiKey,
    Dataset,
    EvalResult,
    EvalRun,
    Evaluator,
    GatePolicy,
    Project,
    PromptVersion,
    RunStatus,
    TestCase,
    User,
)

# TypeVar instead of PEP 695 syntax: keeps the file parseable by Semgrep (SAST coverage).
T = TypeVar("T")


class Repo:
    def __init__(self, session: AsyncSession) -> None:
        self.s = session

    async def commit(self) -> None:
        await self.s.commit()

    async def add(self, obj: T) -> T:
        self.s.add(obj)
        await self.s.flush()
        return obj

    async def delete_obj(self, obj: object) -> None:
        await self.s.delete(obj)
        await self.s.flush()

    # --- users ---------------------------------------------------------------
    async def user_by_email(self, email: str) -> User | None:
        return await self.s.scalar(select(User).where(func.lower(User.email) == email.lower()))

    async def user_by_id(self, user_id: int) -> User | None:
        return await self.s.get(User, user_id)

    # --- projects ------------------------------------------------------------
    async def projects_for_owner(self, owner_id: int) -> Sequence[Project]:
        q = select(Project).where(Project.owner_id == owner_id).order_by(Project.id.desc())
        return (await self.s.scalars(q)).all()

    async def project(self, project_id: int) -> Project | None:
        return await self.s.get(Project, project_id)

    # --- api keys ------------------------------------------------------------
    async def api_keys(self, project_id: int) -> Sequence[ApiKey]:
        q = select(ApiKey).where(ApiKey.project_id == project_id).order_by(ApiKey.id.desc())
        return (await self.s.scalars(q)).all()

    async def api_key(self, project_id: int, key_id: int) -> ApiKey | None:
        return await self.s.scalar(
            select(ApiKey).where(ApiKey.project_id == project_id, ApiKey.id == key_id)
        )

    async def active_api_key_by_hash(self, key_hash: str) -> ApiKey | None:
        return await self.s.scalar(
            select(ApiKey).where(ApiKey.key_hash == key_hash, ApiKey.revoked_at.is_(None))
        )

    # --- prompt versions -----------------------------------------------------
    async def prompt_versions(self, project_id: int) -> Sequence[PromptVersion]:
        q = (
            select(PromptVersion)
            .where(PromptVersion.project_id == project_id)
            .order_by(PromptVersion.id.desc())
        )
        return (await self.s.scalars(q)).all()

    async def prompt_version(self, version_id: int) -> PromptVersion | None:
        return await self.s.get(PromptVersion, version_id)

    async def prompt_version_by_label(self, project_id: int, label: str) -> PromptVersion | None:
        return await self.s.scalar(
            select(PromptVersion).where(
                PromptVersion.project_id == project_id, PromptVersion.label == label
            )
        )

    async def labels_for(self, version_ids: set[int]) -> dict[int, str]:
        if not version_ids:
            return {}
        q = select(PromptVersion.id, PromptVersion.label).where(PromptVersion.id.in_(version_ids))
        return {row.id: row.label for row in await self.s.execute(q)}

    # --- datasets & cases ----------------------------------------------------
    async def datasets_with_counts(self, project_id: int) -> list[tuple[Dataset, int]]:
        counts = (
            select(TestCase.dataset_id, func.count(TestCase.id).label("n"))
            .group_by(TestCase.dataset_id)
            .subquery()
        )
        q = (
            select(Dataset, func.coalesce(counts.c.n, 0))
            .outerjoin(counts, counts.c.dataset_id == Dataset.id)
            .where(Dataset.project_id == project_id)
            .order_by(Dataset.id.desc())
        )
        return [(d, int(n)) for d, n in (await self.s.execute(q)).all()]

    async def dataset(self, dataset_id: int) -> Dataset | None:
        return await self.s.get(Dataset, dataset_id)

    async def case_count(self, dataset_id: int) -> int:
        q = select(func.count(TestCase.id)).where(TestCase.dataset_id == dataset_id)
        return int(await self.s.scalar(q) or 0)

    async def cases(self, dataset_id: int) -> Sequence[TestCase]:
        q = select(TestCase).where(TestCase.dataset_id == dataset_id).order_by(TestCase.id)
        return (await self.s.scalars(q)).all()

    async def case(self, dataset_id: int, case_id: int) -> TestCase | None:
        return await self.s.scalar(
            select(TestCase).where(TestCase.dataset_id == dataset_id, TestCase.id == case_id)
        )

    async def add_cases(self, cases: list[TestCase]) -> None:
        self.s.add_all(cases)
        await self.s.flush()

    # --- evaluators ----------------------------------------------------------
    async def evaluators(self, project_id: int) -> Sequence[Evaluator]:
        q = select(Evaluator).where(Evaluator.project_id == project_id).order_by(Evaluator.id)
        return (await self.s.scalars(q)).all()

    async def evaluator(self, project_id: int, evaluator_id: int) -> Evaluator | None:
        return await self.s.scalar(
            select(Evaluator).where(
                Evaluator.project_id == project_id, Evaluator.id == evaluator_id
            )
        )

    # --- gate policy ---------------------------------------------------------
    async def gate_policy(self, project_id: int) -> GatePolicy | None:
        return await self.s.scalar(select(GatePolicy).where(GatePolicy.project_id == project_id))

    # --- runs ----------------------------------------------------------------
    async def runs(self, project_id: int, limit: int | None = None) -> Sequence[EvalRun]:
        q = select(EvalRun).where(EvalRun.project_id == project_id).order_by(EvalRun.id.desc())
        if limit is not None:
            q = q.limit(limit)
        return (await self.s.scalars(q)).all()

    async def run(self, run_id: int) -> EvalRun | None:
        return await self.s.get(EvalRun, run_id)

    async def latest_succeeded_run(
        self,
        project_id: int,
        dataset_id: int,
        prompt_version_id: int | None = None,
        exclude_version_id: int | None = None,
    ) -> EvalRun | None:
        q = select(EvalRun).where(
            EvalRun.project_id == project_id,
            EvalRun.dataset_id == dataset_id,
            EvalRun.status == RunStatus.succeeded,
        )
        if prompt_version_id is not None:
            q = q.where(EvalRun.prompt_version_id == prompt_version_id)
        if exclude_version_id is not None:
            q = q.where(EvalRun.prompt_version_id != exclude_version_id)
        return await self.s.scalar(q.order_by(EvalRun.id.desc()).limit(1))

    async def claim_next_run(self) -> EvalRun | None:
        """Atomically move the oldest queued run to `running`.

        FOR UPDATE SKIP LOCKED lets several workers poll the same table without
        double-processing; SQLite ignores the clause and serialises writers instead.
        """
        q = (
            select(EvalRun)
            .where(EvalRun.status == RunStatus.queued)
            .order_by(EvalRun.id)
            .limit(1)
            .with_for_update(skip_locked=True)
        )
        run = await self.s.scalar(q)
        if run is None:
            await self.s.rollback()
            return None
        run.status = RunStatus.running
        run.started_at = datetime.now(UTC)
        await self.s.commit()
        return run

    async def oldest_queued_age_seconds(self) -> float:
        oldest = await self.s.scalar(
            select(func.min(EvalRun.created_at)).where(EvalRun.status == RunStatus.queued)
        )
        if oldest is None:
            return 0.0
        if oldest.tzinfo is None:  # SQLite drops tzinfo
            oldest = oldest.replace(tzinfo=UTC)
        return (datetime.now(UTC) - oldest).total_seconds()

    async def project_spend_today(self, project_id: int) -> float:
        """USD spent by runs created since midnight UTC (the MAX_DAILY_COST_USD window)."""
        midnight = datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0)
        q = select(func.coalesce(func.sum(EvalRun.cost_usd), 0.0)).where(
            EvalRun.project_id == project_id, EvalRun.created_at >= midnight
        )
        return float(await self.s.scalar(q) or 0.0)

    async def count_runs_by_status(self) -> dict[str, int]:
        q = select(EvalRun.status, func.count(EvalRun.id)).group_by(EvalRun.status)
        return {str(status): int(n) for status, n in (await self.s.execute(q)).all()}

    async def update_run(self, run_id: int, **values: Any) -> None:
        await self.s.execute(update(EvalRun).where(EvalRun.id == run_id).values(**values))

    # --- results -------------------------------------------------------------
    async def results(self, run_id: int) -> Sequence[EvalResult]:
        q = select(EvalResult).where(EvalResult.run_id == run_id).order_by(EvalResult.test_case_id)
        return (await self.s.scalars(q)).all()

    async def results_with_cases(self, run_id: int) -> list[tuple[EvalResult, TestCase]]:
        q = (
            select(EvalResult, TestCase)
            .join(TestCase, TestCase.id == EvalResult.test_case_id)
            .where(EvalResult.run_id == run_id)
            .order_by(EvalResult.test_case_id)
        )
        return [(r, c) for r, c in (await self.s.execute(q)).all()]

    async def delete_results(self, run_id: int) -> None:
        await self.s.execute(delete(EvalResult).where(EvalResult.run_id == run_id))
