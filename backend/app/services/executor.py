"""Executes one eval run: generate an output per case, score it, store it, summarise.

LLM calls run concurrently (bounded by WORKER_CONCURRENCY); database writes stay on a
single session because AsyncSession is not safe to share between tasks.
"""

import asyncio
import logging
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from opentelemetry.trace import SpanKind
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.config import Settings
from app.evaluators import CaseData, EvalDeps, Evaluator, build_evaluator
from app.llm.base import LLMError, LLMProvider
from app.models import EvalResult, PromptVersion, RunStatus, TestCase
from app.observability import CASES_EVALUATED, RUNS_FINISHED, context_from, tracer
from app.repositories import Repo
from app.schemas import PromptParams
from app.services import analysis, templating

log = logging.getLogger(__name__)


@dataclass
class CaseRun:
    case_id: int
    output: str | None = None
    scores: list[dict[str, Any]] = field(default_factory=list)
    score: float = 0.0
    passed: bool = False
    latency_ms: float = 0.0
    tokens_in: int = 0
    tokens_out: int = 0
    cost_usd: float = 0.0
    error: str | None = None


async def evaluate_case(
    case: TestCase,
    version: PromptVersion,
    evaluators: list[tuple[Evaluator, float]],
    provider: LLMProvider,
) -> CaseRun:
    result = CaseRun(case_id=case.id)
    params = PromptParams.model_validate(version.params or {})
    with tracer.start_as_current_span("case.evaluate") as span:
        span.set_attribute("evalops.case_id", case.id)
        try:
            prompt = templating.render(version.template, case.inputs)
        except templating.TemplateError as e:
            result.error = str(e)
            return result
        started = time.perf_counter()
        try:
            completion = await provider.complete(
                prompt,
                model=version.model,
                max_tokens=params.max_tokens,
                system=params.system or None,
                temperature=params.temperature,
            )
        except LLMError as e:
            result.error = f"generation failed: {e}"
            result.latency_ms = (time.perf_counter() - started) * 1000
            return result
        result.output = completion.text
        result.latency_ms = completion.latency_ms
        result.tokens_in, result.tokens_out = completion.tokens_in, completion.tokens_out
        result.cost_usd = completion.cost_usd

        data = CaseData(inputs=case.inputs, expected_output=case.expected_output)
        weighted: list[tuple[float, float]] = []
        all_passed = True
        for evaluator, weight in evaluators:
            try:
                s = await evaluator.evaluate(data, completion.text)
            except LLMError as e:
                result.error = f"evaluator {evaluator.name!r} failed: {e}"
                all_passed = False
                continue
            result.scores.append(s.public())
            result.tokens_in += s.tokens_in
            result.tokens_out += s.tokens_out
            result.cost_usd += s.cost_usd
            weighted.append((s.score, weight))
            all_passed &= s.passed
        result.score = analysis.weighted_score(weighted)
        result.passed = all_passed and result.error is None
        span.set_attribute("evalops.passed", result.passed)
        return result


async def execute_run(
    maker: async_sessionmaker[AsyncSession],
    run_id: int,
    provider: LLMProvider,
    settings: Settings,
    trace_context: dict[str, str] | None = None,
) -> None:
    # Continue the trace of the request that queued the run (POST /runs or /gate).
    with tracer.start_as_current_span(
        "run.execute", context=context_from(trace_context), kind=SpanKind.CONSUMER
    ) as span:
        span.set_attribute("evalops.run_id", run_id)
        try:
            await _execute(maker, run_id, provider, settings)
        except Exception as e:
            log.exception("run crashed", extra={"run_id": run_id})
            async with maker() as s:
                await Repo(s).update_run(
                    run_id,
                    status=RunStatus.failed,
                    error=f"internal error: {type(e).__name__}",
                    finished_at=datetime.now(UTC),
                )
                await s.commit()
            RUNS_FINISHED.labels("failed").inc()


async def _execute(
    maker: async_sessionmaker[AsyncSession],
    run_id: int,
    provider: LLMProvider,
    settings: Settings,
) -> None:
    async with maker() as s:
        repo = Repo(s)
        run = await repo.run(run_id)
        if run is None:
            return
        version = await repo.prompt_version(run.prompt_version_id)
        assert version is not None
        cases = list(await repo.cases(run.dataset_id))
        evaluator_rows = list(await repo.evaluators(run.project_id))
        await repo.delete_results(run_id)  # makes a re-claimed run idempotent
        await repo.update_run(run_id, progress_total=len(cases), progress_done=0)
        await s.commit()

    deps = EvalDeps(
        provider=provider, judge_model=settings.judge_model, judge_effort=settings.judge_effort
    )
    evaluators = [
        (build_evaluator(e.type, e.name, e.config, deps), e.weight) for e in evaluator_rows
    ]
    sem = asyncio.Semaphore(settings.worker_concurrency)

    async def one(case: TestCase) -> CaseRun:
        async with sem:
            return await evaluate_case(case, version, evaluators, provider)

    tasks = [asyncio.create_task(one(c)) for c in cases]
    outcomes: list[CaseRun] = []
    spent = 0.0
    tokens = 0
    aborted: str | None = None
    async with maker() as s:
        repo = Repo(s)
        for fut in asyncio.as_completed(tasks):
            r = await fut
            outcomes.append(r)
            spent += r.cost_usd
            tokens += r.tokens_in + r.tokens_out
            CASES_EVALUATED.labels("error" if r.error else ("pass" if r.passed else "fail")).inc()
            s.add(
                EvalResult(
                    run_id=run_id,
                    test_case_id=r.case_id,
                    output=r.output,
                    scores=r.scores,
                    score=r.score,
                    passed=r.passed,
                    latency_ms=r.latency_ms,
                    tokens_in=r.tokens_in,
                    tokens_out=r.tokens_out,
                    cost_usd=r.cost_usd,
                    error=r.error,
                )
            )
            await repo.update_run(
                run_id, progress_done=len(outcomes), cost_usd=spent, total_tokens=tokens
            )
            await s.commit()
            if spent > settings.max_cost_per_run_usd:
                aborted = (
                    f"cost limit exceeded: ${spent:.4f} > MAX_COST_PER_RUN_USD "
                    f"${settings.max_cost_per_run_usd:.2f}"
                )
                break
        if aborted:
            for t in tasks:
                t.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)

        summary = analysis.summarise(
            [
                analysis.CaseOutcome(
                    passed=o.passed,
                    score=o.score,
                    latency_ms=o.latency_ms,
                    tokens=o.tokens_in + o.tokens_out,
                    cost_usd=o.cost_usd,
                    errored=o.error is not None,
                    scores=o.scores,
                )
                for o in outcomes
            ]
        )
        status = RunStatus.failed if aborted else RunStatus.succeeded
        await repo.update_run(
            run_id,
            status=status,
            summary=summary.model_dump(),
            error=aborted,
            finished_at=datetime.now(UTC),
        )
        await s.commit()
    RUNS_FINISHED.labels(status.value).inc()
    log.info("run finished", extra={"run_id": run_id, "status": status.value})
