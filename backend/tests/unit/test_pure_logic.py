import pytest

from app.schemas import CompareBucket, GatePolicy
from app.services import analysis, templating
from app.services.analysis import CaseOutcome, CaseSide, GateInputs

POLICY = GatePolicy(min_pass_rate=0.8, max_regressions=0, max_cost_increase_pct=20)


class TestTemplating:
    def test_extracts_unique_variables_in_order(self) -> None:
        assert templating.variables("{{a}} {{ b }} {{a}}") == ["a", "b"]

    def test_renders_values_and_non_strings(self) -> None:
        assert templating.render("Hi {{name}}, n={{n}}", {"name": "Ada", "n": 3}) == "Hi Ada, n=3"

    def test_missing_variable_is_an_error(self) -> None:
        with pytest.raises(templating.TemplateError, match="question"):
            templating.render("{{question}}", {})

    def test_does_not_evaluate_braces_in_values(self) -> None:
        assert templating.render("{{x}}", {"x": "{{y}}"}) == "{{y}}"


class TestSummary:
    def outcome(
        self, passed: bool, score: float, latency: float, errored: bool = False
    ) -> CaseOutcome:
        return CaseOutcome(
            passed=passed,
            score=score,
            latency_ms=latency,
            tokens=10,
            cost_usd=0.01,
            errored=errored,
            scores=[{"evaluator": "e", "score": score}],
        )

    def test_summary_numbers(self) -> None:
        s = analysis.summarise(
            [
                self.outcome(True, 1, 100),
                self.outcome(False, 0.5, 300),
                self.outcome(False, 0, 0, True),
            ]
        )
        assert (s.total, s.passed, s.errored) == (3, 1, 1)
        assert s.pass_rate == pytest.approx(0.3333, abs=1e-4)
        assert s.mean_scores == {"e": 0.5}
        assert s.latency_p50_ms == 100  # errored case excluded from latency
        assert s.latency_p95_ms == 300
        assert s.total_tokens == 30
        assert s.cost_usd == pytest.approx(0.03)

    def test_empty_run(self) -> None:
        s = analysis.summarise([])
        assert s.total == 0 and s.pass_rate == 0

    def test_percentile_nearest_rank(self) -> None:
        assert analysis.percentile(list(range(1, 101)), 95) == 95
        assert analysis.percentile([], 50) == 0

    def test_weighted_score(self) -> None:
        assert analysis.weighted_score([(1.0, 3), (0.0, 1)]) == 0.75
        assert analysis.weighted_score([]) == 0


class TestClassify:
    @pytest.mark.parametrize(
        ("base", "head", "bucket"),
        [
            (CaseSide(True, 1), CaseSide(False, 0.5), CompareBucket.regressed),
            (CaseSide(False, 0), CaseSide(True, 1), CompareBucket.improved),
            (CaseSide(True, 1), CaseSide(True, 0.9), CompareBucket.unchanged),
            (CaseSide(True, 1), CaseSide(True, 0.7), CompareBucket.regressed),
            (CaseSide(False, 0.1), CaseSide(False, 0.5), CompareBucket.improved),
            (None, CaseSide(True, 1), CompareBucket.added),
            (CaseSide(True, 1), None, CompareBucket.removed),
        ],
    )
    def test_buckets(
        self, base: CaseSide | None, head: CaseSide | None, bucket: CompareBucket
    ) -> None:
        assert analysis.classify(base, head) == bucket

    def test_pct_change(self) -> None:
        assert analysis.pct_change(1.0, 1.5) == 50
        assert analysis.pct_change(0, 1) is None


class TestGateVerdict:
    def inputs(self, **kw: object) -> GateInputs:
        base: dict[str, object] = dict(
            head_status="succeeded",
            head_error=None,
            head_pass_rate=0.9,
            regressions=0,
            cost_increase_pct=5.0,
            has_baseline=True,
        )
        base.update(kw)
        return GateInputs(**base)  # type: ignore[arg-type]

    def test_passes_when_all_checks_pass(self) -> None:
        ok, reasons = analysis.gate_verdict(POLICY, self.inputs())
        assert ok and len(reasons) == 3

    @pytest.mark.parametrize(
        "kw",
        [{"head_pass_rate": 0.5}, {"regressions": 2}, {"cost_increase_pct": 50.0}],
    )
    def test_fails_on_any_threshold(self, kw: dict[str, object]) -> None:
        ok, _ = analysis.gate_verdict(POLICY, self.inputs(**kw))
        assert not ok

    def test_failed_head_run_fails(self) -> None:
        ok, reasons = analysis.gate_verdict(
            POLICY, self.inputs(head_status="failed", head_error="boom")
        )
        assert not ok and "boom" in reasons[0]

    def test_without_baseline_only_pass_rate_counts(self) -> None:
        ok, reasons = analysis.gate_verdict(
            POLICY, self.inputs(has_baseline=False, regressions=None, cost_increase_pct=None)
        )
        assert ok and any("no baseline" in r for r in reasons)
