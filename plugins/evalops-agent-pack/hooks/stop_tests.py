"""Stop hook: before the agent declares "done", run the fast tests for what it changed.

Only suites whose files changed run (backend unit tests and/or frontend Vitest), so a docs-only
session stops instantly. On failure the agent is told to keep working (exit 2), once: if it is
already continuing because of this hook, we let it stop to avoid loops.
"""

import shutil
import subprocess
import sys

from common import ROOT, audit, git, read_event


def changed_paths() -> list[str]:
    out = git("status", "--porcelain", "--untracked-files=all")
    return [line[3:].strip().strip('"') for line in out.stdout.splitlines() if len(line) > 3]


def run(cmd: list[str], cwd: str) -> tuple[bool, str]:
    proc = subprocess.run(  # noqa: S603
        cmd, cwd=ROOT / cwd, capture_output=True, text=True, check=False, timeout=600
    )
    return proc.returncode == 0, (proc.stdout + proc.stderr)[-3000:]


def main() -> None:
    event = read_event()
    if event.get("stop_hook_active"):
        audit(event, "skip", "already continuing after a failed test run")
        return
    paths = changed_paths()
    failures: list[str] = []
    if any(p.startswith("backend/") and p.endswith(".py") for p in paths) and shutil.which("uv"):
        ok, out = run(["uv", "run", "pytest", "-m", "not integration", "-q", "-x", "-p", "no:warnings"], "backend")
        if not ok:
            failures.append(f"backend unit tests failed:\n{out}")
    if any(p.startswith("frontend/src/") for p in paths) and (npx := shutil.which("npx")):
        ok, out = run([npx, "--no-install", "vitest", "run"], "frontend")
        if not ok:
            failures.append(f"frontend tests failed:\n{out}")
    if failures:
        audit(event, "block", "tests failing")
        print("Tests are failing; fix them before finishing.\n\n" + "\n\n".join(failures), file=sys.stderr)
        sys.exit(2)
    audit(event, "allow", "tests green or nothing to test")


if __name__ == "__main__":
    main()
