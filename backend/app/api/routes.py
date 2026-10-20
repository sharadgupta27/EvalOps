"""HTTP routes. Each handler parses the request, calls one service method, returns."""

from typing import Annotated

from fastapi import APIRouter, File, Query, Response, UploadFile

from app.api.deps import ApiKeyPrincipalDep, PrincipalDep, RepoDep, SettingsDep
from app.errors import TooLarge
from app.schemas import (
    ApiKey,
    ApiKeyCreate,
    ApiKeyCreated,
    CompareResponse,
    Dataset,
    DatasetCreate,
    Error,
    EvalResult,
    EvalRun,
    Evaluator,
    EvaluatorCreate,
    EvaluatorUpdate,
    GatePolicy,
    GateRequest,
    GateResult,
    ImportResult,
    IngestRequest,
    LoginRequest,
    Project,
    ProjectCreate,
    ProjectUpdate,
    PromptVersion,
    PromptVersionCreate,
    RegisterRequest,
    RunCreate,
    TestCase,
    TestCaseCreate,
    TestCaseUpdate,
    TokenResponse,
    User,
)
from app.services.core import (
    AuthService,
    DatasetService,
    EvaluatorService,
    ProjectService,
    PromptService,
)
from app.services.runs import RunService

ERRORS: dict[int | str, dict[str, object]] = {
    401: {"model": Error},
    404: {"model": Error},
    422: {"model": Error},
}
router = APIRouter(responses=ERRORS)


# --- auth ---------------------------------------------------------------------
@router.post("/auth/register", status_code=201, tags=["auth"], operation_id="register")
async def register(body: RegisterRequest, repo: RepoDep, settings: SettingsDep) -> User:
    return await AuthService(repo, settings).register(body.email, body.password)


@router.post("/auth/login", tags=["auth"], operation_id="login")
async def login(body: LoginRequest, repo: RepoDep, settings: SettingsDep) -> TokenResponse:
    return await AuthService(repo, settings).login(body.email, body.password)


@router.get("/auth/me", tags=["auth"], operation_id="getMe")
async def me(p: PrincipalDep, repo: RepoDep, settings: SettingsDep) -> User:
    return await AuthService(repo, settings).me(p)


# --- projects -----------------------------------------------------------------
@router.get("/projects", tags=["projects"], operation_id="listProjects")
async def list_projects(p: PrincipalDep, repo: RepoDep, settings: SettingsDep) -> list[Project]:
    return await ProjectService(repo, settings).list_all(p)


@router.post("/projects", status_code=201, tags=["projects"], operation_id="createProject")
async def create_project(
    body: ProjectCreate, p: PrincipalDep, repo: RepoDep, settings: SettingsDep
) -> Project:
    return await ProjectService(repo, settings).create(p, body)


@router.get("/projects/{project_id}", tags=["projects"], operation_id="getProject")
async def get_project(
    project_id: int, p: PrincipalDep, repo: RepoDep, settings: SettingsDep
) -> Project:
    return await ProjectService(repo, settings).get(p, project_id)


@router.patch("/projects/{project_id}", tags=["projects"], operation_id="updateProject")
async def update_project(
    project_id: int, body: ProjectUpdate, p: PrincipalDep, repo: RepoDep, settings: SettingsDep
) -> Project:
    return await ProjectService(repo, settings).update(p, project_id, body)


@router.delete(
    "/projects/{project_id}",
    tags=["projects"],
    operation_id="deleteProject",
    status_code=204,
    response_class=Response,
)
async def delete_project(
    project_id: int, p: PrincipalDep, repo: RepoDep, settings: SettingsDep
) -> None:
    await ProjectService(repo, settings).delete(p, project_id)


# --- prompt versions ----------------------------------------------------------
@router.get(
    "/projects/{project_id}/prompt-versions",
    tags=["prompt-versions"],
    operation_id="listPromptVersions",
)
async def list_prompt_versions(
    project_id: int, p: PrincipalDep, repo: RepoDep, settings: SettingsDep
) -> list[PromptVersion]:
    return await PromptService(repo, settings).list_all(p, project_id)


@router.post(
    "/projects/{project_id}/prompt-versions",
    status_code=201,
    tags=["prompt-versions"],
    operation_id="createPromptVersion",
    responses={409: {"model": Error}},
)
async def create_prompt_version(
    project_id: int,
    body: PromptVersionCreate,
    p: PrincipalDep,
    repo: RepoDep,
    settings: SettingsDep,
) -> PromptVersion:
    return await PromptService(repo, settings).create(p, project_id, body)


# --- datasets & cases ---------------------------------------------------------
@router.get("/projects/{project_id}/datasets", tags=["datasets"], operation_id="listDatasets")
async def list_datasets(
    project_id: int, p: PrincipalDep, repo: RepoDep, settings: SettingsDep
) -> list[Dataset]:
    return await DatasetService(repo, settings).list_all(p, project_id)


@router.post(
    "/projects/{project_id}/datasets",
    status_code=201,
    tags=["datasets"],
    operation_id="createDataset",
)
async def create_dataset(
    project_id: int, body: DatasetCreate, p: PrincipalDep, repo: RepoDep, settings: SettingsDep
) -> Dataset:
    return await DatasetService(repo, settings).create(p, project_id, body)


@router.get("/datasets/{dataset_id}", tags=["datasets"], operation_id="getDataset")
async def get_dataset(
    dataset_id: int, p: PrincipalDep, repo: RepoDep, settings: SettingsDep
) -> Dataset:
    return await DatasetService(repo, settings).get(p, dataset_id)


@router.delete(
    "/datasets/{dataset_id}",
    tags=["datasets"],
    operation_id="deleteDataset",
    status_code=204,
    response_class=Response,
)
async def delete_dataset(
    dataset_id: int, p: PrincipalDep, repo: RepoDep, settings: SettingsDep
) -> None:
    await DatasetService(repo, settings).delete(p, dataset_id)


@router.post(
    "/datasets/{dataset_id}/import",
    tags=["datasets"],
    operation_id="importCases",
    responses={413: {"model": Error}},
)
async def import_cases(
    dataset_id: int,
    file: Annotated[UploadFile, File()],
    p: PrincipalDep,
    repo: RepoDep,
    settings: SettingsDep,
) -> ImportResult:
    # Read one byte past the limit so oversize uploads are rejected without buffering them.
    content = await file.read(settings.max_upload_bytes + 1)
    if len(content) > settings.max_upload_bytes:
        raise TooLarge(f"file exceeds {settings.max_upload_bytes} bytes")
    return await DatasetService(repo, settings).import_file(
        p, dataset_id, file.filename or "", content
    )


@router.get("/datasets/{dataset_id}/cases", tags=["datasets"], operation_id="listCases")
async def list_cases(
    dataset_id: int, p: PrincipalDep, repo: RepoDep, settings: SettingsDep
) -> list[TestCase]:
    return await DatasetService(repo, settings).list_cases(p, dataset_id)


@router.post(
    "/datasets/{dataset_id}/cases", status_code=201, tags=["datasets"], operation_id="createCase"
)
async def create_case(
    dataset_id: int, body: TestCaseCreate, p: PrincipalDep, repo: RepoDep, settings: SettingsDep
) -> TestCase:
    return await DatasetService(repo, settings).create_case(p, dataset_id, body)


@router.patch(
    "/datasets/{dataset_id}/cases/{case_id}", tags=["datasets"], operation_id="updateCase"
)
async def update_case(
    dataset_id: int,
    case_id: int,
    body: TestCaseUpdate,
    p: PrincipalDep,
    repo: RepoDep,
    settings: SettingsDep,
) -> TestCase:
    return await DatasetService(repo, settings).update_case(p, dataset_id, case_id, body)


@router.delete(
    "/datasets/{dataset_id}/cases/{case_id}",
    tags=["datasets"],
    operation_id="deleteCase",
    status_code=204,
    response_class=Response,
)
async def delete_case(
    dataset_id: int, case_id: int, p: PrincipalDep, repo: RepoDep, settings: SettingsDep
) -> None:
    await DatasetService(repo, settings).delete_case(p, dataset_id, case_id)


# --- evaluators ---------------------------------------------------------------
@router.get("/projects/{project_id}/evaluators", tags=["evaluators"], operation_id="listEvaluators")
async def list_evaluators(
    project_id: int, p: PrincipalDep, repo: RepoDep, settings: SettingsDep
) -> list[Evaluator]:
    return await EvaluatorService(repo, settings).list_all(p, project_id)


@router.post(
    "/projects/{project_id}/evaluators",
    status_code=201,
    tags=["evaluators"],
    operation_id="createEvaluator",
)
async def create_evaluator(
    project_id: int, body: EvaluatorCreate, p: PrincipalDep, repo: RepoDep, settings: SettingsDep
) -> Evaluator:
    return await EvaluatorService(repo, settings).create(p, project_id, body)


@router.patch(
    "/projects/{project_id}/evaluators/{evaluator_id}",
    tags=["evaluators"],
    operation_id="updateEvaluator",
)
async def update_evaluator(
    project_id: int,
    evaluator_id: int,
    body: EvaluatorUpdate,
    p: PrincipalDep,
    repo: RepoDep,
    settings: SettingsDep,
) -> Evaluator:
    return await EvaluatorService(repo, settings).update(p, project_id, evaluator_id, body)


@router.delete(
    "/projects/{project_id}/evaluators/{evaluator_id}",
    tags=["evaluators"],
    operation_id="deleteEvaluator",
    status_code=204,
    response_class=Response,
)
async def delete_evaluator(
    project_id: int, evaluator_id: int, p: PrincipalDep, repo: RepoDep, settings: SettingsDep
) -> None:
    await EvaluatorService(repo, settings).delete(p, project_id, evaluator_id)


# --- runs ---------------------------------------------------------------------
@router.get("/projects/{project_id}/runs", tags=["runs"], operation_id="listRuns")
async def list_runs(
    project_id: int,
    p: PrincipalDep,
    repo: RepoDep,
    settings: SettingsDep,
    limit: Annotated[int, Query(ge=1, le=200)] = 100,
) -> list[EvalRun]:
    return await RunService(repo, settings).list_all(p, project_id, limit)


@router.post(
    "/projects/{project_id}/runs", status_code=202, tags=["runs"], operation_id="createRun"
)
async def create_run(
    project_id: int, body: RunCreate, p: PrincipalDep, repo: RepoDep, settings: SettingsDep
) -> EvalRun:
    return await RunService(repo, settings).create(p, project_id, body)


# Declared before /runs/{run_id} so "compare" is not parsed as a run id.
@router.get("/runs/compare", tags=["runs"], operation_id="compareRuns")
async def compare_runs(
    base: Annotated[int, Query()],
    head: Annotated[int, Query()],
    p: PrincipalDep,
    repo: RepoDep,
    settings: SettingsDep,
) -> CompareResponse:
    return await RunService(repo, settings).compare(p, base, head)


@router.get("/runs/{run_id}", tags=["runs"], operation_id="getRun")
async def get_run(run_id: int, p: PrincipalDep, repo: RepoDep, settings: SettingsDep) -> EvalRun:
    return await RunService(repo, settings).get(p, run_id)


@router.get("/runs/{run_id}/results", tags=["runs"], operation_id="getRunResults")
async def get_run_results(
    run_id: int, p: PrincipalDep, repo: RepoDep, settings: SettingsDep
) -> list[EvalResult]:
    return await RunService(repo, settings).results(p, run_id)


# --- gate ---------------------------------------------------------------------
@router.get("/projects/{project_id}/gate-policy", tags=["gate"], operation_id="getGatePolicy")
async def get_gate_policy(
    project_id: int, p: PrincipalDep, repo: RepoDep, settings: SettingsDep
) -> GatePolicy:
    return await ProjectService(repo, settings).get_policy(p, project_id)


@router.put("/projects/{project_id}/gate-policy", tags=["gate"], operation_id="putGatePolicy")
async def put_gate_policy(
    project_id: int, body: GatePolicy, p: PrincipalDep, repo: RepoDep, settings: SettingsDep
) -> GatePolicy:
    return await ProjectService(repo, settings).put_policy(p, project_id, body)


@router.post(
    "/gate",
    status_code=202,
    tags=["gate"],
    operation_id="startGate",
    responses={409: {"model": Error}},
)
async def start_gate(
    body: GateRequest, p: ApiKeyPrincipalDep, repo: RepoDep, settings: SettingsDep
) -> GateResult:
    return await RunService(repo, settings).start_gate(p, body)


@router.post(
    "/gate/ingest",
    status_code=201,
    tags=["gate"],
    operation_id="ingestGateRun",
    responses={409: {"model": Error}, 413: {"model": Error}},
)
async def ingest_gate_run(
    body: IngestRequest, p: ApiKeyPrincipalDep, repo: RepoDep, settings: SettingsDep
) -> GateResult:
    return await RunService(repo, settings).ingest_gate(p, body)


@router.get("/gate/{run_id}", tags=["gate"], operation_id="getGateResult")
async def get_gate_result(
    run_id: int, p: ApiKeyPrincipalDep, repo: RepoDep, settings: SettingsDep
) -> GateResult:
    return await RunService(repo, settings).gate_result(p, run_id)


# --- API keys -----------------------------------------------------------------
@router.get("/projects/{project_id}/api-keys", tags=["api-keys"], operation_id="listApiKeys")
async def list_api_keys(
    project_id: int, p: PrincipalDep, repo: RepoDep, settings: SettingsDep
) -> list[ApiKey]:
    return await ProjectService(repo, settings).list_keys(p, project_id)


@router.post(
    "/projects/{project_id}/api-keys",
    status_code=201,
    tags=["api-keys"],
    operation_id="createApiKey",
)
async def create_api_key(
    project_id: int, body: ApiKeyCreate, p: PrincipalDep, repo: RepoDep, settings: SettingsDep
) -> ApiKeyCreated:
    return await ProjectService(repo, settings).create_key(p, project_id, body)


@router.delete(
    "/projects/{project_id}/api-keys/{key_id}",
    tags=["api-keys"],
    operation_id="revokeApiKey",
    status_code=204,
    response_class=Response,
)
async def revoke_api_key(
    project_id: int, key_id: int, p: PrincipalDep, repo: RepoDep, settings: SettingsDep
) -> None:
    await ProjectService(repo, settings).revoke_key(p, project_id, key_id)
