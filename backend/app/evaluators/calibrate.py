"""`python -m app.evaluators.calibrate`: measure how often the LLM judge agrees with human labels.

A judge is itself a model that can be wrong, so we "judge the judge" against a small
human-labelled set (calibration/judge_calibration.jsonl). Agreement = share of examples
where judge pass/fail equals the human label. Uses LLM_PROVIDER (fake by default).

Exit code 1 when agreement is below --min-agreement, so CI can gate judge-prompt changes.
"""

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from app.config import get_settings
from app.db import run_async
from app.evaluators import CaseData, EvalDeps, build_evaluator, validate_config
from app.llm import LLMError, build_provider
from app.models import EvaluatorType

CALIBRATION_SET = Path(__file__).parent / "calibration" / "judge_calibration.jsonl"


async def calibrate(rows: list[dict[str, Any]], threshold: int) -> dict[str, Any]:
    settings = get_settings()
    deps = EvalDeps(build_provider(settings), settings.judge_model, settings.judge_effort)
    details = []
    for row in rows:
        config = validate_config(
            EvaluatorType.llm_judge, {"rubric": row["rubric"], "threshold": threshold}
        )
        judge = build_evaluator(EvaluatorType.llm_judge, "judge", config, deps)
        case = CaseData(inputs=row["inputs"], expected_output=row.get("expected_output"))
        try:
            score = await judge.evaluate(case, row["output"])
            judge_pass: bool | None = score.passed
            reason = score.reason
        except LLMError as e:
            judge_pass, reason = None, f"error: {e}"
        details.append(
            {
                "note": row.get("note", ""),
                "human_pass": row["human_pass"],
                "judge_pass": judge_pass,
                "agree": judge_pass == row["human_pass"],
                "reason": reason,
            }
        )
    agree = sum(d["agree"] for d in details)
    tp = sum(d["human_pass"] and d["judge_pass"] for d in details)
    fp = sum((not d["human_pass"]) and d["judge_pass"] for d in details)
    fn = sum(d["human_pass"] and d["judge_pass"] is False for d in details)
    return {
        "provider": settings.llm_provider,
        "judge_model": settings.judge_model if settings.llm_provider != "fake" else "fake",
        "examples": len(details),
        "agreement": round(agree / len(details), 4) if details else 0.0,
        "false_passes": fp,
        "false_fails": fn,
        "true_passes": tp,
        "disagreements": [d for d in details if not d["agree"]],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--set", type=Path, default=CALIBRATION_SET)
    parser.add_argument("--threshold", type=int, default=4)
    parser.add_argument("--min-agreement", type=float, default=0.8)
    args = parser.parse_args()
    rows = [json.loads(ln) for ln in args.set.read_text(encoding="utf-8").splitlines() if ln]
    report = run_async(calibrate(rows, args.threshold))
    print(json.dumps(report, indent=2))
    if report["agreement"] < args.min_agreement:
        print(
            f"judge agreement {report['agreement']:.0%} < required {args.min_agreement:.0%}",
            file=sys.stderr,
        )
        sys.exit(1)


if __name__ == "__main__":
    main()
