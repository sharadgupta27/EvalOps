"""Shared helpers for EvalOps agent hooks. Standard library only (runs before any venv exists).

Hook protocol (Claude Code; other agents can call the same scripts):
- The event arrives as JSON on stdin: tool_name, tool_input, cwd, hook_event_name, ...
- Exit 0 = allow / nothing to say. Exit 2 = block; stderr is shown to the agent as the reason.
"""

import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, NoReturn

ROOT = Path(os.environ.get("CLAUDE_PROJECT_DIR") or Path(__file__).resolve().parent.parent)
LOG = ROOT / "agent-hooks" / "logs" / "audit.jsonl"
APPROVAL = ROOT / ".claude" / "state" / "contract-approval.json"
APPROVAL_TTL_SECONDS = 2 * 60 * 60


def read_event() -> dict[str, Any]:
    raw = sys.stdin.read()
    try:
        event: dict[str, Any] = json.loads(raw) if raw.strip() else {}
    except json.JSONDecodeError:
        event = {}
    return event


def audit(event: dict[str, Any], decision: str, reason: str = "") -> None:
    """Append one line per hook decision: the agent audit trail (no file contents, no secrets)."""
    tool_input = event.get("tool_input") or {}
    entry = {
        "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "event": event.get("hook_event_name"),
        "tool": event.get("tool_name"),
        "target": tool_input.get("file_path") or (tool_input.get("command") or "")[:200],
        "decision": decision,
        "reason": reason,
        "session": event.get("session_id"),
    }
    try:
        LOG.parent.mkdir(parents=True, exist_ok=True)
        with LOG.open("a", encoding="utf-8") as f:
            f.write(json.dumps(entry) + "\n")
    except OSError:
        pass  # never let logging break the agent


def block(event: dict[str, Any], reason: str) -> NoReturn:
    audit(event, "block", reason)
    print(f"BLOCKED by EvalOps guardrail: {reason}", file=sys.stderr)
    sys.exit(2)


def rel(path: str | None) -> str:
    if not path:
        return ""
    p = Path(path)
    try:
        return p.resolve().relative_to(ROOT.resolve()).as_posix()
    except ValueError:
        return p.as_posix()


def git(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(  # noqa: S603
        ["git", *args], cwd=ROOT, capture_output=True, text=True, check=False  # noqa: S607
    )


def head_sha() -> str:
    out = git("rev-parse", "HEAD")
    return out.stdout.strip() if out.returncode == 0 else "no-commits"
