"""PreToolUse guardrail. Blocks, with a reason the agent can act on:

1. Reading or writing secrets: `.env*` files (except `.env.example`).
2. Editing already-committed Alembic migrations (create a new migration instead).
3. Editing `openapi.yaml` without a fresh contract-review approval
   (run the review-api-change skill, then agent-hooks/approve_contract_change.py).
4. Hand-editing the generated client `frontend/src/api/schema.d.ts`.
5. Destructive shell commands (rm -rf, force push, reset --hard, dropping volumes/tables).
"""

import json
import re
import time
from typing import Any

from common import APPROVAL, APPROVAL_TTL_SECONDS, audit, block, git, head_sha, read_event, rel

FILE_TOOLS = {"Edit", "Write", "MultiEdit", "NotebookEdit", "Read"}
WRITE_TOOLS = {"Edit", "Write", "MultiEdit", "NotebookEdit"}

DANGEROUS_COMMANDS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"\brm\s+(-[a-zA-Z]*r[a-zA-Z]*f|-[a-zA-Z]*f[a-zA-Z]*r)\b"), "rm -rf"),
    (re.compile(r"\bgit\s+push\b.*(--force\b|\s-f\b|--force-with-lease)"), "git force push"),
    (re.compile(r"\bgit\s+reset\s+--hard\b"), "git reset --hard"),
    (re.compile(r"\bgit\s+clean\s+-[a-zA-Z]*f"), "git clean -f"),
    (re.compile(r"\bdocker\s+volume\s+(rm|prune)\b"), "deleting Docker volumes"),
    (re.compile(r"\bdocker\s+compose\b.*\bdown\b.*(-v\b|--volumes\b)"), "compose down -v (deletes the database)"),
    (re.compile(r"\bdrop\s+(table|database|schema)\b", re.I), "dropping database objects"),
    (re.compile(r"\btruncate\s+table\b", re.I), "truncating tables"),
    (re.compile(r"\b(cat|type|more|less|head|tail|Get-Content)\b[^|;&]*\.env(?!\.example)\b"), "reading .env secrets"),
    (re.compile(r"\baws\s+\S+\s+(delete|terminate|rm)\b"), "deleting AWS resources"),
]


def is_secret_file(path: str) -> bool:
    name = path.rsplit("/", 1)[-1]
    return name.startswith(".env") and name != ".env.example"


def is_committed_migration(path: str) -> bool:
    if not re.match(r"^backend/migrations/versions/[^/]+\.py$", path):
        return False
    return git("ls-files", "--error-unmatch", path).returncode == 0


def contract_approved() -> tuple[bool, str]:
    if not APPROVAL.exists():
        return False, "no approval recorded"
    try:
        data: dict[str, Any] = json.loads(APPROVAL.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False, "approval file unreadable"
    if time.time() - float(data.get("approved_at", 0)) > APPROVAL_TTL_SECONDS:
        return False, "approval expired (older than 2 hours)"
    if data.get("head") != head_sha():
        return False, "approval was for a previous commit"
    return True, data.get("reason", "")


def check_file(event: dict[str, Any], tool: str, path: str) -> None:
    if is_secret_file(path):
        block(event, f"{path} may contain secrets. Use .env.example to document variables.")
    if tool not in WRITE_TOOLS:
        return
    if is_committed_migration(path):
        block(
            event,
            f"{path} is a committed migration and may already be applied. "
            "Create a new one: cd backend && uv run alembic revision --autogenerate -m '<msg>'",
        )
    if path == "frontend/src/api/schema.d.ts":
        block(event, "schema.d.ts is generated. Edit openapi.yaml, then run: cd frontend && npm run gen:api")
    if path == "openapi.yaml":
        ok, why = contract_approved()
        if not ok:
            block(
                event,
                f"openapi.yaml is the API contract ({why}). Follow the review-api-change skill: "
                "get the api-contract-reviewer subagent's approval, then run "
                "`python agent-hooks/approve_contract_change.py \"<reason>\"` and retry.",
            )


def main() -> None:
    event = read_event()
    tool = event.get("tool_name", "")
    tool_input = event.get("tool_input") or {}
    if tool in FILE_TOOLS:
        check_file(event, tool, rel(tool_input.get("file_path") or tool_input.get("notebook_path")))
    elif tool == "Bash":
        command = tool_input.get("command", "")
        for pattern, label in DANGEROUS_COMMANDS:
            if pattern.search(command):
                block(event, f"{label} is not allowed without explicit human approval. Ask the user.")
    audit(event, "allow")


if __name__ == "__main__":
    main()
