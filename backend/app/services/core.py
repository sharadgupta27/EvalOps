"""Auth, projects, API keys, prompt versions, datasets, cases and evaluators."""

import csv
import io
import json
from datetime import UTC, datetime
from typing import Any

from app.config import Settings
from app.errors import Conflict, Forbidden, Invalid, NotFound, TooLarge, Unauthorized
from app.evaluators import validate_config
from app.models import ApiKey as ApiKeyRow
from app.models import Dataset as DatasetRow
from app.models import Evaluator as EvaluatorRow
from app.models import GatePolicy as GatePolicyRow
from app.models import Project as ProjectRow
from app.models import PromptVersion as PromptVersionRow
from app.models import TestCase as TestCaseRow
from app.models import User as UserRow
from app.repositories import Repo
from app.schemas import (
    ApiKey,
    ApiKeyCreate,
    ApiKeyCreated,
    Dataset,
    DatasetCreate,
    Evaluator,
    EvaluatorCreate,
    EvaluatorUpdate,
    GatePolicy,
    ImportResult,
    ImportRowError,
    Project,
    ProjectCreate,
    ProjectUpdate,
    PromptParams,
    PromptVersion,
    PromptVersionCreate,
    TestCase,
    TestCaseCreate,
    TestCaseUpdate,
    TokenResponse,
    User,
)
from app.services import templating
from app.services.security import (
    Principal,
    create_jwt,
    decode_jwt,
    generate_api_key,
    hash_api_key,
    hash_password,
    verify_password,
)

MAX_IMPORT_ROWS = 5000
DEFAULT_POLICY = GatePolicy(min_pass_rate=0.8, max_regressions=0, max_cost_increase_pct=20.0)


class Service:
    def __init__(self, repo: Repo, settings: Settings) -> None:
        self.repo = repo
        self.settings = settings

    # --- access control ------------------------------------------------------
    async def project_for(self, principal: Principal, project_id: int) -> ProjectRow:
        """Return the project if the caller may see it. 404 (not 403) hides existence."""
        project = await self.repo.project(project_id)
        if project is None:
            raise NotFound("project not found")
        if principal.is_api_key:
            if principal.project_id != project_id:
                raise NotFound("project not found")
        elif project.owner_id != principal.user_id:
            raise NotFound("project not found")
        return project

    async def dataset_for(self, principal: Principal, dataset_id: int) -> DatasetRow:
        dataset = await self.repo.dataset(dataset_id)
        if dataset is None:
            raise NotFound("dataset not found")
        await self.project_for(principal, dataset.project_id)
        return dataset

    @staticmethod
    def require_user(principal: Principal) -> None:
        if principal.is_api_key:
            raise Forbidden("this operation needs a user login, not an API key")


class AuthService(Service):
    async def register(self, email: str, password: str) -> User:
        if await self.repo.user_by_email(email):
            raise Conflict("email already registered")
        user = await self.repo.add(
            UserRow(
                email=email.lower(),
                password_hash=hash_password(password, self.settings.bcrypt_rounds),
            )
        )
        await self.repo.commit()
        return User.model_validate(user)

    async def login(self, email: str, password: str) -> TokenResponse:
        user = await self.repo.user_by_email(email)
        if user is None or not verify_password(password, user.password_hash):
            raise Unauthorized("invalid email or password")
        token = create_jwt(
            user.id, self.settings.jwt_secret.get_secret_value(), self.settings.jwt_expire_minutes
        )
        return TokenResponse(access_token=token, token_type="bearer")  # noqa: S106

    async def principal_from_jwt(self, token: str) -> Principal:
        user_id = decode_jwt(token, self.settings.jwt_secret.get_secret_value())
        if await self.repo.user_by_id(user_id) is None:
            raise Unauthorized("user no longer exists")
        return Principal(kind="user", user_id=user_id)

    async def principal_from_api_key(self, key: str) -> Principal:
        row = await self.repo.active_api_key_by_hash(hash_api_key(key))
        if row is None:
            raise Unauthorized("invalid or revoked API key")
        project = await self.repo.project(row.project_id)
        if project is None:
            raise Unauthorized("invalid or revoked API key")
        row.last_used_at = datetime.now(UTC)
        await self.repo.commit()
        return Principal(
            kind="api_key", user_id=project.owner_id, project_id=project.id, api_key_id=row.id
        )

    async def me(self, principal: Principal) -> User:
        self.require_user(principal)
        user = await self.repo.user_by_id(principal.user_id)
        if user is None:
            raise Unauthorized("user no longer exists")
        return User.model_validate(user)


class ProjectService(Service):
    async def list_all(self, p: Principal) -> list[Project]:
        if p.is_api_key:
            assert p.project_id is not None
            return [Project.model_validate(await self.project_for(p, p.project_id))]
        return [Project.model_validate(x) for x in await self.repo.projects_for_owner(p.user_id)]

    async def create(self, p: Principal, body: ProjectCreate) -> Project:
        self.require_user(p)
        row = await self.repo.add(
            ProjectRow(owner_id=p.user_id, name=body.name, description=body.description)
        )
        await self.repo.commit()
        return Project.model_validate(row)

    async def get(self, p: Principal, project_id: int) -> Project:
        return Project.model_validate(await self.project_for(p, project_id))

    async def update(self, p: Principal, project_id: int, body: ProjectUpdate) -> Project:
        self.require_user(p)
        row = await self.project_for(p, project_id)
        for field, value in body.model_dump(exclude_unset=True, exclude_none=True).items():
            setattr(row, field, value)
        await self.repo.commit()
        return Project.model_validate(row)

    async def delete(self, p: Principal, project_id: int) -> None:
        self.require_user(p)
        await self.repo.delete_obj(await self.project_for(p, project_id))
        await self.repo.commit()

    # --- API keys ------------------------------------------------------------
    async def list_keys(self, p: Principal, project_id: int) -> list[ApiKey]:
        self.require_user(p)
        await self.project_for(p, project_id)
        return [ApiKey.model_validate(k) for k in await self.repo.api_keys(project_id)]

    async def create_key(self, p: Principal, project_id: int, body: ApiKeyCreate) -> ApiKeyCreated:
        self.require_user(p)
        await self.project_for(p, project_id)
        secret = generate_api_key()
        row = await self.repo.add(
            ApiKeyRow(
                project_id=project_id,
                name=body.name,
                prefix=secret[:10],
                key_hash=hash_api_key(secret),
            )
        )
        await self.repo.commit()
        return ApiKeyCreated.model_validate(
            {**ApiKey.model_validate(row).model_dump(), "key": secret}
        )

    async def revoke_key(self, p: Principal, project_id: int, key_id: int) -> None:
        self.require_user(p)
        await self.project_for(p, project_id)
        row = await self.repo.api_key(project_id, key_id)
        if row is None:
            raise NotFound("API key not found")
        row.revoked_at = row.revoked_at or datetime.now(UTC)
        await self.repo.commit()

    # --- gate policy ---------------------------------------------------------
    async def get_policy(self, p: Principal, project_id: int) -> GatePolicy:
        await self.project_for(p, project_id)
        row = await self.repo.gate_policy(project_id)
        return GatePolicy.model_validate(row) if row else DEFAULT_POLICY

    async def put_policy(self, p: Principal, project_id: int, body: GatePolicy) -> GatePolicy:
        self.require_user(p)
        await self.project_for(p, project_id)
        row = await self.repo.gate_policy(project_id)
        if row is None:
            row = await self.repo.add(GatePolicyRow(project_id=project_id))
        row.min_pass_rate = body.min_pass_rate
        row.max_regressions = body.max_regressions
        row.max_cost_increase_pct = body.max_cost_increase_pct
        await self.repo.commit()
        return GatePolicy.model_validate(row)


def prompt_version_out(row: PromptVersionRow) -> PromptVersion:
    return PromptVersion(
        id=row.id,
        project_id=row.project_id,
        label=row.label,
        template=row.template,
        model=row.model,
        params=PromptParams.model_validate(row.params or {}),
        variables=templating.variables(row.template),
        created_at=row.created_at,
    )


class PromptService(Service):
    async def list_all(self, p: Principal, project_id: int) -> list[PromptVersion]:
        await self.project_for(p, project_id)
        return [prompt_version_out(v) for v in await self.repo.prompt_versions(project_id)]

    async def create(
        self, p: Principal, project_id: int, body: PromptVersionCreate
    ) -> PromptVersion:
        self.require_user(p)
        await self.project_for(p, project_id)
        row = await self.create_row(project_id, body)
        await self.repo.commit()
        return prompt_version_out(row)

    async def create_row(self, project_id: int, body: PromptVersionCreate) -> PromptVersionRow:
        if await self.repo.prompt_version_by_label(project_id, body.label):
            raise Conflict(f"prompt version {body.label!r} already exists; versions are immutable")
        params = (body.params or PromptParams()).model_dump()
        return await self.repo.add(
            PromptVersionRow(
                project_id=project_id,
                label=body.label,
                template=body.template,
                model=body.model or self.settings.default_model,
                params=params,
            )
        )


def dataset_out(row: DatasetRow, count: int) -> Dataset:
    return Dataset(
        id=row.id,
        project_id=row.project_id,
        name=row.name,
        case_count=count,
        created_at=row.created_at,
    )


class DatasetService(Service):
    async def list_all(self, p: Principal, project_id: int) -> list[Dataset]:
        await self.project_for(p, project_id)
        return [dataset_out(d, n) for d, n in await self.repo.datasets_with_counts(project_id)]

    async def create(self, p: Principal, project_id: int, body: DatasetCreate) -> Dataset:
        self.require_user(p)
        await self.project_for(p, project_id)
        row = await self.repo.add(DatasetRow(project_id=project_id, name=body.name))
        await self.repo.commit()
        return dataset_out(row, 0)

    async def get(self, p: Principal, dataset_id: int) -> Dataset:
        row = await self.dataset_for(p, dataset_id)
        return dataset_out(row, await self.repo.case_count(dataset_id))

    async def delete(self, p: Principal, dataset_id: int) -> None:
        self.require_user(p)
        await self.repo.delete_obj(await self.dataset_for(p, dataset_id))
        await self.repo.commit()

    # --- cases ---------------------------------------------------------------
    async def list_cases(self, p: Principal, dataset_id: int) -> list[TestCase]:
        await self.dataset_for(p, dataset_id)
        return [TestCase.model_validate(c) for c in await self.repo.cases(dataset_id)]

    async def create_case(self, p: Principal, dataset_id: int, body: TestCaseCreate) -> TestCase:
        self.require_user(p)
        await self.dataset_for(p, dataset_id)
        row = await self.repo.add(
            TestCaseRow(
                dataset_id=dataset_id,
                inputs=body.inputs,
                expected_output=body.expected_output,
                tags=body.tags,
            )
        )
        await self.repo.commit()
        return TestCase.model_validate(row)

    async def update_case(
        self, p: Principal, dataset_id: int, case_id: int, body: TestCaseUpdate
    ) -> TestCase:
        self.require_user(p)
        await self.dataset_for(p, dataset_id)
        row = await self.repo.case(dataset_id, case_id)
        if row is None:
            raise NotFound("test case not found")
        for field, value in body.model_dump(exclude_unset=True).items():
            if field in ("inputs", "tags") and value is None:
                continue
            setattr(row, field, value)
        await self.repo.commit()
        return TestCase.model_validate(row)

    async def delete_case(self, p: Principal, dataset_id: int, case_id: int) -> None:
        self.require_user(p)
        await self.dataset_for(p, dataset_id)
        row = await self.repo.case(dataset_id, case_id)
        if row is None:
            raise NotFound("test case not found")
        await self.repo.delete_obj(row)
        await self.repo.commit()

    async def import_file(
        self, p: Principal, dataset_id: int, filename: str, content: bytes
    ) -> ImportResult:
        self.require_user(p)
        await self.dataset_for(p, dataset_id)
        if len(content) > self.settings.max_upload_bytes:
            raise TooLarge(f"file exceeds {self.settings.max_upload_bytes} bytes")
        try:
            text = content.decode("utf-8-sig")
        except UnicodeDecodeError as e:
            raise Invalid("file must be UTF-8 encoded") from e
        name = filename.lower()
        if name.endswith(".csv"):
            parsed, errors = parse_csv(text)
        elif name.endswith((".jsonl", ".ndjson")):
            parsed, errors = parse_jsonl(text)
        else:
            raise Invalid("unsupported file type: use .csv or .jsonl")
        if len(parsed) > MAX_IMPORT_ROWS:
            raise Invalid(f"too many rows: max {MAX_IMPORT_ROWS}")
        await self.repo.add_cases(
            [
                TestCaseRow(
                    dataset_id=dataset_id,
                    inputs=c.inputs,
                    expected_output=c.expected_output,
                    tags=c.tags,
                )
                for c in parsed
            ]
        )
        await self.repo.commit()
        return ImportResult(imported=len(parsed), errors=errors)


def _tags(value: Any) -> list[str]:
    if value is None or value == "":
        return []
    if isinstance(value, str):
        return [t.strip() for t in value.split(";") if t.strip()]
    if isinstance(value, list) and all(isinstance(t, str) for t in value):
        return value
    raise ValueError("tags must be a list of strings or a ';'-separated string")


def parse_csv(text: str) -> tuple[list[TestCaseCreate], list[ImportRowError]]:
    reader = csv.DictReader(io.StringIO(text))
    if not reader.fieldnames:
        raise Invalid("CSV has no header row")
    reserved = {"expected_output", "tags"}
    input_cols = [c for c in reader.fieldnames if c and c not in reserved]
    if not input_cols:
        raise Invalid("CSV needs at least one input column besides expected_output/tags")
    cases: list[TestCaseCreate] = []
    errors: list[ImportRowError] = []
    for i, row in enumerate(reader, start=1):
        try:
            if None in row:
                raise ValueError("row has more values than the header")
            inputs = {c: row[c] for c in input_cols if row.get(c) not in (None, "")}
            if not inputs:
                raise ValueError("all input columns are empty")
            cases.append(
                TestCaseCreate(
                    inputs=inputs,
                    expected_output=row.get("expected_output") or None,
                    tags=_tags(row.get("tags")),
                )
            )
        except ValueError as e:
            errors.append(ImportRowError(row=i, message=str(e)))
    return cases, errors


def parse_jsonl(text: str) -> tuple[list[TestCaseCreate], list[ImportRowError]]:
    cases: list[TestCaseCreate] = []
    errors: list[ImportRowError] = []
    for i, line in enumerate(text.splitlines(), start=1):
        if not line.strip():
            continue
        try:
            obj = json.loads(line)
            if not isinstance(obj, dict):
                raise ValueError("line must be a JSON object")
            inputs = obj.get("inputs")
            if not isinstance(inputs, dict) or not inputs:
                raise ValueError("'inputs' must be a non-empty object")
            expected = obj.get("expected_output")
            if expected is not None and not isinstance(expected, str):
                raise ValueError("'expected_output' must be a string")
            cases.append(
                TestCaseCreate(inputs=inputs, expected_output=expected, tags=_tags(obj.get("tags")))
            )
        except json.JSONDecodeError as e:
            errors.append(ImportRowError(row=i, message=f"invalid JSON: {e.msg}"))
        except ValueError as e:
            errors.append(ImportRowError(row=i, message=str(e)))
    return cases, errors


class EvaluatorService(Service):
    async def list_all(self, p: Principal, project_id: int) -> list[Evaluator]:
        await self.project_for(p, project_id)
        return [Evaluator.model_validate(e) for e in await self.repo.evaluators(project_id)]

    async def create(self, p: Principal, project_id: int, body: EvaluatorCreate) -> Evaluator:
        self.require_user(p)
        await self.project_for(p, project_id)
        config = validate_config(body.type, body.config)
        row = await self.repo.add(
            EvaluatorRow(
                project_id=project_id,
                type=body.type,
                name=body.name,
                config=config,
                weight=body.weight,
            )
        )
        await self.repo.commit()
        return Evaluator.model_validate(row)

    async def update(
        self, p: Principal, project_id: int, evaluator_id: int, body: EvaluatorUpdate
    ) -> Evaluator:
        self.require_user(p)
        await self.project_for(p, project_id)
        row = await self.repo.evaluator(project_id, evaluator_id)
        if row is None:
            raise NotFound("evaluator not found")
        if body.name is not None:
            row.name = body.name
        if body.weight is not None:
            row.weight = body.weight
        if body.config is not None:
            row.config = validate_config(row.type, body.config)
        await self.repo.commit()
        return Evaluator.model_validate(row)

    async def delete(self, p: Principal, project_id: int, evaluator_id: int) -> None:
        self.require_user(p)
        await self.project_for(p, project_id)
        row = await self.repo.evaluator(project_id, evaluator_id)
        if row is None:
            raise NotFound("evaluator not found")
        await self.repo.delete_obj(row)
        await self.repo.commit()
