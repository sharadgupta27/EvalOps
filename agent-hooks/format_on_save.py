"""PostToolUse hook: format and lint the file the agent just edited.

Python under backend/ → ruff format + ruff check --fix. TS/TSX/CSS under frontend/ → prettier.
Remaining lint errors are reported back to the agent (exit 2) so it fixes them immediately.
"""

import shutil
import subprocess
import sys

from common import ROOT, audit, read_event, rel


def run(cmd: list[str], cwd: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, cwd=ROOT / cwd, capture_output=True, text=True, check=False)  # noqa: S603


def main() -> None:
    event = read_event()
    path = rel((event.get("tool_input") or {}).get("file_path"))
    if path.startswith("backend/") and path.endswith(".py") and shutil.which("uv"):
        target = path.removeprefix("backend/")
        run(["uv", "run", "--quiet", "ruff", "format", target], "backend")
        lint = run(["uv", "run", "--quiet", "ruff", "check", "--fix", target], "backend")
        if lint.returncode != 0:
            audit(event, "lint-errors", path)
            print(f"ruff found problems in {path}:\n{lint.stdout[-2000:]}", file=sys.stderr)
            sys.exit(2)
        audit(event, "formatted", path)
    elif path.startswith("frontend/src/") and path.endswith((".ts", ".tsx", ".css")):
        npx = shutil.which("npx")
        if npx:
            run([npx, "--no-install", "prettier", "--write", path.removeprefix("frontend/")], "frontend")
            audit(event, "formatted", path)


if __name__ == "__main__":
    main()
