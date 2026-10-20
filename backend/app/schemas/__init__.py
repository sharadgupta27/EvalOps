"""Pydantic request/response models. Class and field names mirror openapi.yaml exactly:
tests/unit/test_contract.py fails when they drift."""

import enum
from datetime import datetime
from typing import Annotated, Any

from pydantic import BaseModel, ConfigDict, EmailStr, Field, StringConstraints

from app.models import EvaluatorType, RunStatus, TriggeredBy

Label = Annotated[str, StringConstraints(min_length=1, max_length=40, pattern=r"^[A-Za-z0-9._-]+$")]


class _Out(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class Error(BaseModel):
    detail: str | list[dict[str, Any]]


# --- auth -------------------------------------------------------------------
class RegisterRequest(BaseModel):
    email: EmailStr = Field(max_length=254)
    password: str = Field(min_length=8, max_length=128)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str


class User(_Out):
    id: int
    email: str
    created_at: datetime


# --- projects ---------------------------------------------------------------
class Project(_Out):
    id: int
    name: str
    description: str
    created_at: datetime


class ProjectCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    description: str = Field(default="", max_length=2000)


class ProjectUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=2000)


# --- prompt versions ---------------------------------------------------------
class PromptParams(BaseModel):
    temperature: float | None = Field(default=None, ge=0, le=1)
    max_tokens: int = Field(default=2048, ge=1, le=32000)
    system: str = Field(default="", max_length=20000)


class PromptVersion(_Out):
    id: int
    project_id: int
    label: str
    template: str
    model: str
    params: PromptParams
    variables: list[str]
    created_at: datetime


class PromptVersionCreate(BaseModel):
    label: Label
    template: str = Field(min_length=1, max_length=50000)
    model: str | None = Field(default=None, max_length=100)
    params: PromptParams | None = None


# --- datasets ----------------------------------------------------------------
class Dataset(_Out):
    id: int
    project_id: int
    name: str
    case_count: int
    created_at: datetime


class DatasetCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)


class TestCase(_Out):
    __test__ = False
    id: int
    dataset_id: int
    inputs: dict[str, Any]
    expected_output: str | None
    tags: list[str]
    created_at: datetime


class TestCaseCreate(BaseModel):
    __test__ = False
    inputs: dict[str, Any]
    expected_output: str | None = Field(default=None, max_length=20000)
    tags: list[str] = Field(default_factory=list)


class TestCaseUpdate(BaseModel):
    __test__ = False
    inputs: dict[str, Any] | None = None
    expected_output: str | None = Field(default=None, max_length=20000)
    tags: list[str] | None = None


class ImportRowError(BaseModel):
    row: int
    message: str


class ImportResult(BaseModel):
    imported: int
    errors: list[ImportRowError]


# --- evaluators --------------------------------------------------------------
class Evaluator(_Out):
    id: int
    project_id: int
    type: EvaluatorType
    name: str
    config: dict[str, Any]
    weight: float


class EvaluatorCreate(BaseModel):
    type: EvaluatorType
    name: str = Field(min_length=1, max_length=80)
    config: dict[str, Any] = Field(default_factory=dict)
    weight: float = Field(default=1.0, gt=0, le=100)


class EvaluatorUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=80)
    config: dict[str, Any] | None = None
    weight: float | None = Field(default=None, gt=0, le=100)


# --- runs --------------------------------------------------------------------
class RunCreate(BaseModel):
    prompt_version_id: int
    dataset_id: int
    git_sha: str | None = Field(default=None, max_length=64)


class RunProgress(BaseModel):
    done: int
    total: int


class RunSummary(BaseModel):
    total: int
    passed: int
    errored: int
    pass_rate: float
    mean_score: float
    mean_scores: dict[str, float]
    latency_p50_ms: float
    latency_p95_ms: float
    total_tokens: int
    cost_usd: float


class EvalRun(BaseModel):
    id: int
    project_id: int
    prompt_version_id: int
    prompt_label: str
    dataset_id: int
    status: RunStatus
    triggered_by: TriggeredBy
    git_sha: str | None
    progress: RunProgress
    summary: RunSummary | None
    total_tokens: int
    cost_usd: float
    error: str | None
    baseline_run_id: int | None
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None


class EvaluatorScore(BaseModel):
    evaluator: str
    type: EvaluatorType
    score: float
    passed: bool
    reason: str


class EvalResult(BaseModel):
    id: int
    run_id: int
    test_case_id: int
    inputs: dict[str, Any]
    expected_output: str | None
    output: str | None
    scores: list[EvaluatorScore]
    score: float
    passed: bool
    latency_ms: float
    tokens_in: int
    tokens_out: int
    cost_usd: float
    error: str | None


# --- compare -----------------------------------------------------------------
class CompareBucket(enum.StrEnum):
    regressed = "regressed"
    improved = "improved"
    unchanged = "unchanged"
    added = "added"
    removed = "removed"


class CompareCase(BaseModel):
    test_case_id: int
    inputs: dict[str, Any]
    expected_output: str | None
    base_output: str | None
    head_output: str | None
    base_passed: bool | None
    head_passed: bool | None
    base_score: float | None
    head_score: float | None
    delta: float | None
    bucket: CompareBucket


class CompareCounts(BaseModel):
    regressed: int
    improved: int
    unchanged: int
    added: int
    removed: int


class CompareResponse(BaseModel):
    base: EvalRun
    head: EvalRun
    counts: CompareCounts
    pass_rate_delta: float
    cost_delta_pct: float | None
    cases: list[CompareCase]


# --- gate --------------------------------------------------------------------
class GatePolicy(_Out):
    min_pass_rate: float = Field(ge=0, le=1)
    max_regressions: int = Field(ge=0)
    max_cost_increase_pct: float = Field(ge=0)


class GateRequest(BaseModel):
    dataset_id: int
    head_label: Label
    template: str | None = Field(default=None, max_length=50000)
    model: str | None = Field(default=None, max_length=100)
    params: PromptParams | None = None
    baseline_label: str | None = None
    baseline_run_id: int | None = None
    git_sha: str | None = Field(default=None, max_length=64)


class IngestCaseResult(BaseModel):
    case_ref: str = Field(min_length=1, max_length=200)
    output: str | None = Field(default=None, max_length=5000)
    passed: bool
    score: float = Field(ge=0, le=1)
    latency_ms: float = Field(default=0, ge=0)
    error: str | None = Field(default=None, max_length=2000)


class IngestRequest(BaseModel):
    dataset_id: int
    head_label: Label
    baseline_label: Label | None = None
    baseline_run_id: int | None = None
    git_sha: str | None = Field(default=None, max_length=64)
    # 200 is the default MAX_CASES_PER_RUN; the service enforces the configured value.
    results: list[IngestCaseResult] = Field(min_length=1, max_length=200)


class GateVerdict(enum.StrEnum):
    pending = "pending"
    passed = "pass"
    failed = "fail"


class GateResult(BaseModel):
    run_id: int
    baseline_run_id: int | None
    verdict: GateVerdict
    reasons: list[str]
    pass_rate: float | None
    regressions: int | None
    cost_increase_pct: float | None
    policy: GatePolicy


# --- api keys ----------------------------------------------------------------
class ApiKey(_Out):
    id: int
    project_id: int
    name: str
    prefix: str
    created_at: datetime
    last_used_at: datetime | None
    revoked_at: datetime | None


class ApiKeyCreate(BaseModel):
    name: str = Field(min_length=1, max_length=80)


class ApiKeyCreated(ApiKey):
    key: str
