#!/usr/bin/env python3
"""EvalOps CI gate client. Standard library only, so any CI runner can use it.

Starts a gate (POST /api/v1/gate), polls until the verdict is in, prints the reasons,
writes a GitHub step summary when available, and exits:
  0 = pass, 1 = fail, 2 = usage/infrastructure error.

Example:
  EVALOPS_API_KEY=eo_... python scripts/evalops_gate.py --url https://evalops.example.com \
      --dataset-id 1 --head-label pr-42-abc1234 --template-file prompts/support-reply.txt \
      --baseline-label v1 --git-sha "$GITHUB_SHA"
"""

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any


def call(method: str, url: str, key: str, body: dict[str, Any] | None = None) -> dict[str, Any]:
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method)  # noqa: S310  (URL from CLI flag)
    req.add_header("X-API-Key", key)
    req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:  # noqa: S310
            result: dict[str, Any] = json.loads(resp.read())
            return result
    except urllib.error.HTTPError as e:
        detail = e.read().decode(errors="replace")
        raise SystemExit(f"EvalOps API error {e.code} on {method} {url}: {detail}") from e


def summary_markdown(result: dict[str, Any], url: str) -> str:
    icon = {"pass": "✅", "fail": "❌"}.get(result["verdict"], "⏳")
    lines = [
        f"### {icon} EvalOps gate: **{result['verdict'].upper()}**",
        "",
        f"- Head run: `{result['run_id']}`  baseline run: `{result['baseline_run_id']}`",
        f"- Compare: {url}/compare?base={result['baseline_run_id']}&head={result['run_id']}",
        "",
        *[f"- {r}" for r in result["reasons"]],
    ]
    return "\n".join(lines) + "\n"


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    p.add_argument("--url", default=os.environ.get("EVALOPS_URL", "http://localhost:5173"))
    p.add_argument("--dataset-id", type=int, required=True)
    p.add_argument("--head-label", required=True)
    p.add_argument("--template-file", type=Path, help="prompt template to evaluate as head")
    p.add_argument("--model")
    p.add_argument("--baseline-label")
    p.add_argument("--baseline-run-id", type=int)
    p.add_argument("--git-sha")
    p.add_argument("--timeout", type=int, default=900, help="seconds to wait for the verdict")
    args = p.parse_args()
    # Windows consoles default to a legacy code page that cannot print the status emoji.
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    key = os.environ.get("EVALOPS_API_KEY")
    if not key:
        print("EVALOPS_API_KEY is not set", file=sys.stderr)
        return 2
    base = args.url.rstrip("/")
    body: dict[str, Any] = {
        "dataset_id": args.dataset_id,
        "head_label": args.head_label,
        "template": args.template_file.read_text(encoding="utf-8") if args.template_file else None,
        "model": args.model,
        "baseline_label": args.baseline_label,
        "baseline_run_id": args.baseline_run_id,
        "git_sha": args.git_sha,
    }
    try:
        result = call("POST", f"{base}/api/v1/gate", key, {k: v for k, v in body.items() if v is not None})
        print(f"gate started: head run {result['run_id']}, baseline run {result['baseline_run_id']}")
        deadline = time.monotonic() + args.timeout
        while result["verdict"] == "pending":
            if time.monotonic() > deadline:
                print(f"timed out after {args.timeout}s waiting for the verdict", file=sys.stderr)
                return 2
            time.sleep(2)
            result = call("GET", f"{base}/api/v1/gate/{result['run_id']}", key)
    except SystemExit as e:
        print(e, file=sys.stderr)
        return 2
    except (urllib.error.URLError, TimeoutError) as e:
        print(f"cannot reach EvalOps at {base}: {e}", file=sys.stderr)
        return 2

    report = summary_markdown(result, base)
    print(report)
    if step_summary := os.environ.get("GITHUB_STEP_SUMMARY"):
        with open(step_summary, "a", encoding="utf-8") as f:
            f.write(report)
    return 0 if result["verdict"] == "pass" else 1


if __name__ == "__main__":
    sys.exit(main())
