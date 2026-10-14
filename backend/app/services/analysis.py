"""Pure functions: run summaries, run comparison and gate verdicts. No I/O, easy to test."""

import math
from collections import defaultdict
from dataclasses import dataclass
from typing import Any

from app.schemas import CompareBucket, GatePolicy, RunSummary

# A score change smaller than this between two runs is noise, not a regression.
SCORE_TOLERANCE = 0.25


@dataclass(frozen=True)
class CaseOutcome:
    """The minimum a summary needs to know about one evaluated case."""

    passed: bool
    score: float
    latency_ms: float
    tokens: int
    cost_usd: float
    errored: bool
    scores: list[dict[str, Any]]


def percentile(values: list[float], pct: float) -> float:
    """Nearest-rank percentile; 0.0 for an empty list."""
    if not values:
        return 0.0
    ordered = sorted(values)
    rank = max(1, math.ceil(pct / 100 * len(ordered)))
    return ordered[rank - 1]


def summarise(outcomes: list[CaseOutcome]) -> RunSummary:
    total = len(outcomes)
    passed = sum(o.passed for o in outcomes)
    per_evaluator: dict[str, list[float]] = defaultdict(list)
    for o in outcomes:
        for s in o.scores:
            per_evaluator[s["evaluator"]].append(float(s["score"]))
    latencies = [o.latency_ms for o in outcomes if not o.errored]
    return RunSummary(
        total=total,
        passed=passed,
        errored=sum(o.errored for o in outcomes),
        pass_rate=round(passed / total, 4) if total else 0.0,
        mean_score=round(sum(o.score for o in outcomes) / total, 4) if total else 0.0,
        mean_scores={k: round(sum(v) / len(v), 4) for k, v in sorted(per_evaluator.items())},
        latency_p50_ms=round(percentile(latencies, 50), 1),
        latency_p95_ms=round(percentile(latencies, 95), 1),
        total_tokens=sum(o.tokens for o in outcomes),
        cost_usd=round(sum(o.cost_usd for o in outcomes), 6),
    )


def weighted_score(scores: list[tuple[float, float]]) -> float:
    """Weighted mean of (score, weight) pairs."""
    total_weight = sum(w for _, w in scores)
    if total_weight <= 0:
        return 0.0
    return sum(s * w for s, w in scores) / total_weight


@dataclass(frozen=True)
class CaseSide:
    passed: bool
    score: float


def classify(base: CaseSide | None, head: CaseSide | None) -> CompareBucket:
    if base is None:
        return CompareBucket.added
    if head is None:
        return CompareBucket.removed
    if base.passed and not head.passed:
        return CompareBucket.regressed
    if head.passed and not base.passed:
        return CompareBucket.improved
    delta = head.score - base.score
    if delta <= -SCORE_TOLERANCE:
        return CompareBucket.regressed
    if delta >= SCORE_TOLERANCE:
        return CompareBucket.improved
    return CompareBucket.unchanged


def pct_change(base: float, head: float) -> float | None:
    if base <= 0:
        return None
    return round((head - base) / base * 100, 2)


@dataclass(frozen=True)
class GateInputs:
    head_status: str
    head_error: str | None
    head_pass_rate: float | None
    regressions: int | None
    cost_increase_pct: float | None
    has_baseline: bool


def gate_verdict(policy: GatePolicy, g: GateInputs) -> tuple[bool, list[str]]:
    """Return (passed, reasons). Reasons explain every check, pass or fail."""
    if g.head_status == "failed":
        return False, [f"head run failed: {g.head_error or 'unknown error'}"]
    reasons: list[str] = []
    ok = True
    if g.head_pass_rate is not None:
        good = g.head_pass_rate >= policy.min_pass_rate
        ok &= good
        reasons.append(
            f"pass rate {g.head_pass_rate:.0%} {'>=' if good else '<'} "
            f"minimum {policy.min_pass_rate:.0%}"
        )
    if not g.has_baseline:
        reasons.append("no baseline run: regression and cost checks skipped")
        return ok, reasons
    if g.regressions is not None:
        good = g.regressions <= policy.max_regressions
        ok &= good
        reasons.append(
            f"{g.regressions} regressed case(s) {'<=' if good else '>'} "
            f"allowed {policy.max_regressions}"
        )
    if g.cost_increase_pct is not None:
        good = g.cost_increase_pct <= policy.max_cost_increase_pct
        ok &= good
        reasons.append(
            f"cost change {g.cost_increase_pct:+.1f}% {'within' if good else 'exceeds'} "
            f"limit +{policy.max_cost_increase_pct:.0f}%"
        )
    return ok, reasons
