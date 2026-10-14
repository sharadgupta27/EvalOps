"""ORM models. Keep relationships out: repositories query explicitly, which avoids
lazy loads that break under asyncio."""

from __future__ import annotations

import enum
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


def utcnow() -> datetime:
    return datetime.now(UTC)


class EvaluatorType(enum.StrEnum):
    exact_match = "exact_match"
    contains = "contains"
    regex = "regex"
    json_schema = "json_schema"
    llm_judge = "llm_judge"


class RunStatus(enum.StrEnum):
    queued = "queued"
    running = "running"
    succeeded = "succeeded"
    failed = "failed"


class TriggeredBy(enum.StrEnum):
    ui = "ui"
    ci = "ci"
    agent = "agent"


def _enum(e: type[enum.Enum], name: str) -> Enum:
    # native_enum=False stores plain strings: portable across SQLite and Postgres and
    # adding a value later needs no ALTER TYPE.
    return Enum(
        e, name=name, native_enum=False, length=32, values_callable=lambda x: [m.value for m in x]
    )


TS = DateTime(timezone=True)


class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String(254), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(100))
    created_at: Mapped[datetime] = mapped_column(TS, default=utcnow)


class Project(Base):
    __tablename__ = "projects"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(120))
    description: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(TS, default=utcnow)


class ApiKey(Base):
    __tablename__ = "api_keys"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_id: Mapped[int] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(80))
    prefix: Mapped[str] = mapped_column(String(16))
    key_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    created_at: Mapped[datetime] = mapped_column(TS, default=utcnow)
    last_used_at: Mapped[datetime | None] = mapped_column(TS, nullable=True)
    revoked_at: Mapped[datetime | None] = mapped_column(TS, nullable=True)


class PromptVersion(Base):
    __tablename__ = "prompt_versions"
    __table_args__ = (UniqueConstraint("project_id", "label", name="uq_prompt_version_label"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_id: Mapped[int] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), index=True
    )
    label: Mapped[str] = mapped_column(String(40))
    template: Mapped[str] = mapped_column(Text)
    model: Mapped[str] = mapped_column(String(100))
    params: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(TS, default=utcnow)


class Dataset(Base):
    __tablename__ = "datasets"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_id: Mapped[int] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(120))
    created_at: Mapped[datetime] = mapped_column(TS, default=utcnow)


class TestCase(Base):
    __tablename__ = "test_cases"
    __test__ = False  # stop pytest from collecting this class
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    dataset_id: Mapped[int] = mapped_column(
        ForeignKey("datasets.id", ondelete="CASCADE"), index=True
    )
    inputs: Mapped[dict[str, Any]] = mapped_column(JSON)
    expected_output: Mapped[str | None] = mapped_column(Text, nullable=True)
    tags: Mapped[list[str]] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(TS, default=utcnow)


class Evaluator(Base):
    __tablename__ = "evaluators"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_id: Mapped[int] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), index=True
    )
    type: Mapped[EvaluatorType] = mapped_column(_enum(EvaluatorType, "evaluator_type"))
    name: Mapped[str] = mapped_column(String(80))
    config: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    weight: Mapped[float] = mapped_column(Float, default=1.0)


class EvalRun(Base):
    """Also the job queue: the worker claims rows with status=queued."""

    __tablename__ = "eval_runs"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_id: Mapped[int] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), index=True
    )
    prompt_version_id: Mapped[int] = mapped_column(
        ForeignKey("prompt_versions.id", ondelete="CASCADE"), index=True
    )
    dataset_id: Mapped[int] = mapped_column(
        ForeignKey("datasets.id", ondelete="CASCADE"), index=True
    )
    status: Mapped[RunStatus] = mapped_column(_enum(RunStatus, "run_status"), index=True)
    triggered_by: Mapped[TriggeredBy] = mapped_column(_enum(TriggeredBy, "triggered_by"))
    git_sha: Mapped[str | None] = mapped_column(String(64), nullable=True)
    baseline_run_id: Mapped[int | None] = mapped_column(
        ForeignKey("eval_runs.id", ondelete="SET NULL"), nullable=True
    )
    progress_done: Mapped[int] = mapped_column(Integer, default=0)
    progress_total: Mapped[int] = mapped_column(Integer, default=0)
    summary: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    total_tokens: Mapped[int] = mapped_column(Integer, default=0)
    cost_usd: Mapped[float] = mapped_column(Float, default=0.0)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(TS, default=utcnow, index=True)
    started_at: Mapped[datetime | None] = mapped_column(TS, nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(TS, nullable=True)


class EvalResult(Base):
    __tablename__ = "eval_results"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("eval_runs.id", ondelete="CASCADE"), index=True)
    test_case_id: Mapped[int] = mapped_column(
        ForeignKey("test_cases.id", ondelete="CASCADE"), index=True
    )
    output: Mapped[str | None] = mapped_column(Text, nullable=True)
    scores: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    score: Mapped[float] = mapped_column(Float, default=0.0)
    passed: Mapped[bool] = mapped_column(Boolean, default=False)
    latency_ms: Mapped[float] = mapped_column(Float, default=0.0)
    tokens_in: Mapped[int] = mapped_column(Integer, default=0)
    tokens_out: Mapped[int] = mapped_column(Integer, default=0)
    cost_usd: Mapped[float] = mapped_column(Float, default=0.0)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)


class GatePolicy(Base):
    __tablename__ = "gate_policies"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_id: Mapped[int] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), unique=True
    )
    min_pass_rate: Mapped[float] = mapped_column(Float, default=0.8)
    max_regressions: Mapped[int] = mapped_column(Integer, default=0)
    max_cost_increase_pct: Mapped[float] = mapped_column(Float, default=20.0)
