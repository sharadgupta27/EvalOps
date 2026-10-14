"""Runs, results, comparison and the CI gate."""

from typing import Any

from app.errors import Conflict, Invalid, NotFound
from app.models import EvalRun as EvalRunRow
from app.models import RunStatus, TriggeredBy
from app.observability import current_trace_context
from app.schemas import (
    CompareBucket,
    CompareCase,
    CompareCounts,
    CompareResponse,
    EvalResult,
    EvalRun,
    EvaluatorScore,
    GateRequest,
    GateResult,
    GateVerdict,
    PromptParams,
    PromptVersionCreate,
    RunCreate,
    RunProgress,
    RunSummary,
)
from app.services import analysis
from app.services.core import ProjectService, PromptService, Service
from app.services.security import Principal


def run_out(row: EvalRunRow, label: str) -> EvalRun:
    return EvalRun(
        id=row.id,
        project_id=row.project_id,
        prompt_version_id=row.prompt_version_id,
        prompt_label=label,
        dataset_id=row.dataset_id,
        status=row.status,
        triggered_by=row.triggered_by,
        git_sha=row.git_sha,
        progress=RunProgress(done=row.progress_done, total=row.progress_total),
        summary=RunSummary.model_validate(row.summary) if row.summary else None,
        total_tokens=row.total_tokens,
        cost_usd=round(row.cost_usd, 6),
        error=row.error,
        baseline_run_id=row.baseline_run_id,
        created_at=row.created_at,
        started_at=row.started_at,
        finished_at=row.finished_at,
    )


class RunService(Service):
    async def _out(self, row: EvalRunRow) -> EvalRun:
        labels = await self.repo.labels_for({row.prompt_version_id})
        return run_out(row, labels.get(row.prompt_version_id, "?"))

    async def run_for(self, p: Principal, run_id: int) -> EvalRunRow:
        row = await self.repo.run(run_id)
        if row is None:
            raise NotFound("run not found")
        await self.project_for(p, row.project_id)
        return row

    async def list_all(self, p: Principal, project_id: int) -> list[EvalRun]:
        await self.project_for(p, project_id)
        rows = await self.repo.runs(project_id)
        labels = await self.repo.labels_for({r.prompt_version_id for r in rows})
        return [run_out(r, labels.get(r.prompt_version_id, "?")) for r in rows]

    async def get(self, p: Principal, run_id: int) -> EvalRun:
        return await self._out(await self.run_for(p, run_id))

    async def create(self, p: Principal, project_id: int, body: RunCreate) -> EvalRun:
        await self.project_for(p, project_id)
        trigger = TriggeredBy.agent if p.is_api_key else TriggeredBy.ui
        row = await self.queue_run(
            project_id, body.prompt_version_id, body.dataset_id, trigger, body.git_sha
        )
        await self.repo.commit()
        return await self._out(row)

    async def queue_run(
        self,
        project_id: int,
        prompt_version_id: int,
        dataset_id: int,
        trigger: TriggeredBy,
        git_sha: str | None,
        baseline_run_id: int | None = None,
    ) -> EvalRunRow:
        version = await self.repo.prompt_version(prompt_version_id)
        if version is None or version.project_id != project_id:
            raise NotFound("prompt version not found")
        dataset = await self.repo.dataset(dataset_id)
        if dataset is None or dataset.project_id != project_id:
            raise NotFound("dataset not found")
        n_cases = await self.repo.case_count(dataset_id)
        if n_cases == 0:
            raise Invalid("dataset has no test cases")
        if n_cases > self.settings.max_cases_per_run:
            raise Invalid(
                f"dataset has {n_cases} cases; "
                f"MAX_CASES_PER_RUN is {self.settings.max_cases_per_run}"
            )
        if not await self.repo.evaluators(project_id):
            raise Invalid("project has no evaluators; add at least one before running")
        return await self.repo.add(
            EvalRunRow(
                project_id=project_id,
                prompt_version_id=prompt_version_id,
                dataset_id=dataset_id,
                status=RunStatus.queued,
                triggered_by=trigger,
                git_sha=git_sha,
                baseline_run_id=baseline_run_id,
                progress_total=n_cases,
                trace_context=current_trace_context(),
            )
        )

    async def results(self, p: Principal, run_id: int) -> list[EvalResult]:
        await self.run_for(p, run_id)
        return [
            EvalResult(
                id=r.id,
                run_id=r.run_id,
                test_case_id=r.test_case_id,
                inputs=c.inputs,
                expected_output=c.expected_output,
                output=r.output,
                scores=[EvaluatorScore.model_validate(s) for s in r.scores],
                score=round(r.score, 4),
                passed=r.passed,
                latency_ms=round(r.latency_ms, 1),
                tokens_in=r.tokens_in,
                tokens_out=r.tokens_out,
                cost_usd=r.cost_usd,
                error=r.error,
            )
            for r, c in await self.repo.results_with_cases(run_id)
        ]

    async def compare(self, p: Principal, base_id: int, head_id: int) -> CompareResponse:
        base = await self.run_for(p, base_id)
        head = await self.run_for(p, head_id)
        if base.dataset_id != head.dataset_id:
            raise Invalid("runs must use the same dataset to be compared")
        if base.project_id != head.project_id:
            raise Invalid("runs belong to different projects")
        return await self._compare(base, head)

    async def _compare(self, base: EvalRunRow, head: EvalRunRow) -> CompareResponse:
        base_rows = {r.test_case_id: (r, c) for r, c in await self.repo.results_with_cases(base.id)}
        head_rows = {r.test_case_id: (r, c) for r, c in await self.repo.results_with_cases(head.id)}
        cases: list[CompareCase] = []
        counts = dict.fromkeys(CompareBucket, 0)
        for case_id in sorted(base_rows.keys() | head_rows.keys()):
            b = base_rows.get(case_id)
            h = head_rows.get(case_id)
            tc = (h or b)[1]  # type: ignore[index]
            bside = analysis.CaseSide(b[0].passed, b[0].score) if b else None
            hside = analysis.CaseSide(h[0].passed, h[0].score) if h else None
            bucket = analysis.classify(bside, hside)
            counts[bucket] += 1
            cases.append(
                CompareCase(
                    test_case_id=case_id,
                    inputs=tc.inputs,
                    expected_output=tc.expected_output,
                    base_output=b[0].output if b else None,
                    head_output=h[0].output if h else None,
                    base_passed=bside.passed if bside else None,
                    head_passed=hside.passed if hside else None,
                    base_score=round(bside.score, 4) if bside else None,
                    head_score=round(hside.score, 4) if hside else None,
                    delta=round(hside.score - bside.score, 4) if bside and hside else None,
                    bucket=bucket,
                )
            )
        labels = await self.repo.labels_for({base.prompt_version_id, head.prompt_version_id})
        base_out = run_out(base, labels.get(base.prompt_version_id, "?"))
        head_out = run_out(head, labels.get(head.prompt_version_id, "?"))
        base_rate = base_out.summary.pass_rate if base_out.summary else 0.0
        head_rate = head_out.summary.pass_rate if head_out.summary else 0.0
        return CompareResponse(
            base=base_out,
            head=head_out,
            counts=CompareCounts(**{k.value: v for k, v in counts.items()}),
            pass_rate_delta=round(head_rate - base_rate, 4),
            cost_delta_pct=analysis.pct_change(base.cost_usd, head.cost_usd),
            cases=cases,
        )

    # --- gate ----------------------------------------------------------------
    async def start_gate(self, p: Principal, body: GateRequest) -> GateResult:
        assert p.project_id is not None, "gate requires an API key principal"
        project_id = p.project_id
        await self.project_for(p, project_id)
        dataset = await self.repo.dataset(body.dataset_id)
        if dataset is None or dataset.project_id != project_id:
            raise NotFound("dataset not found")

        head_version = await self.repo.prompt_version_by_label(project_id, body.head_label)
        if body.template is not None:
            wanted_params = (body.params or PromptParams()).model_dump()
            wanted_model = body.model or self.settings.default_model
            if head_version is None:
                head_version = await PromptService(self.repo, self.settings).create_row(
                    project_id,
                    PromptVersionCreate(
                        label=body.head_label,
                        template=body.template,
                        model=wanted_model,
                        params=PromptParams.model_validate(wanted_params),
                    ),
                )
            elif (head_version.template, head_version.model, head_version.params) != (
                body.template,
                wanted_model,
                wanted_params,
            ):
                raise Conflict(
                    f"version {body.head_label!r} exists with different content; "
                    "versions are immutable, use a new label (e.g. include the git SHA)"
                )
        if head_version is None:
            raise NotFound(f"prompt version {body.head_label!r} not found")

        baseline = await self._resolve_baseline(project_id, body, head_version.id)
        head = await self.queue_run(
            project_id,
            head_version.id,
            body.dataset_id,
            TriggeredBy.ci,
            body.git_sha,
            baseline_run_id=baseline.id if baseline else None,
        )
        await self.repo.commit()
        return await self.gate_result(p, head.id)

    async def _resolve_baseline(
        self, project_id: int, body: GateRequest, head_version_id: int
    ) -> EvalRunRow | None:
        if body.baseline_run_id is not None:
            run = await self.repo.run(body.baseline_run_id)
            if run is None or run.project_id != project_id or run.dataset_id != body.dataset_id:
                raise NotFound("baseline run not found on this dataset")
            return run
        if body.baseline_label:
            version = await self.repo.prompt_version_by_label(project_id, body.baseline_label)
            if version is None:
                raise NotFound(f"baseline version {body.baseline_label!r} not found")
            run = await self.repo.latest_succeeded_run(project_id, body.dataset_id, version.id)
            if run is None:
                # First gate for this baseline: evaluate it too, so CI never needs a manual step.
                run = await self.queue_run(
                    project_id, version.id, body.dataset_id, TriggeredBy.ci, None
                )
            return run
        return await self.repo.latest_succeeded_run(
            project_id, body.dataset_id, exclude_version_id=head_version_id
        )

    async def gate_result(self, p: Principal, run_id: int) -> GateResult:
        head = await self.run_for(p, run_id)
        policy = await ProjectService(self.repo, self.settings).get_policy(p, head.project_id)
        base = await self.repo.run(head.baseline_run_id) if head.baseline_run_id else None

        def pending(reason: str) -> GateResult:
            return GateResult(
                run_id=head.id,
                baseline_run_id=head.baseline_run_id,
                verdict=GateVerdict.pending,
                reasons=[reason],
                pass_rate=None,
                regressions=None,
                cost_increase_pct=None,
                policy=policy,
            )

        if head.status in (RunStatus.queued, RunStatus.running):
            return pending(f"head run is {head.status.value}")
        if base is not None and base.status in (RunStatus.queued, RunStatus.running):
            return pending(f"baseline run is {base.status.value}")

        summary: dict[str, Any] = head.summary or {}
        regressions = cost_pct = None
        has_baseline = base is not None and base.status == RunStatus.succeeded
        if base is not None and has_baseline and head.status == RunStatus.succeeded:
            cmp = await self._compare(base, head)
            regressions = cmp.counts.regressed
            cost_pct = cmp.cost_delta_pct
        ok, reasons = analysis.gate_verdict(
            policy,
            analysis.GateInputs(
                head_status=head.status.value,
                head_error=head.error,
                head_pass_rate=summary.get("pass_rate"),
                regressions=regressions,
                cost_increase_pct=cost_pct,
                has_baseline=has_baseline,
            ),
        )
        if base is not None and base.status == RunStatus.failed:
            reasons.append(f"baseline run {base.id} failed; compared without baseline")
        return GateResult(
            run_id=head.id,
            baseline_run_id=head.baseline_run_id,
            verdict=GateVerdict.passed if ok else GateVerdict.failed,
            reasons=reasons,
            pass_rate=summary.get("pass_rate"),
            regressions=regressions,
            cost_increase_pct=cost_pct,
            policy=policy,
        )
