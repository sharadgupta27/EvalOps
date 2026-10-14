"""Hook tests: run the real scripts as subprocesses against a throwaway git repo.

Run: python -m unittest discover -s agent-hooks/tests -v
"""

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HOOKS = Path(__file__).resolve().parents[1]


def git(repo: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True, timeout=30)


class HookTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.repo = Path(self.tmp.name)
        git(self.repo, "init", "-q")
        git(self.repo, "config", "user.email", "t@example.com")
        git(self.repo, "config", "user.name", "t")
        # Throwaway fixture repo: never prompt for a signing key here.
        git(self.repo, "config", "commit.gpgsign", "false")
        mig = self.repo / "backend/migrations/versions/0001_initial.py"
        mig.parent.mkdir(parents=True)
        mig.write_text("# applied\n")
        (self.repo / "openapi.yaml").write_text("openapi: 3.1.0\n")
        git(self.repo, "add", ".")
        git(self.repo, "commit", "-qm", "init")

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def hook(self, script: str, event: dict[str, object], *args: str) -> subprocess.CompletedProcess[str]:
        env = os.environ | {"CLAUDE_PROJECT_DIR": str(self.repo)}
        return subprocess.run(
            [sys.executable, str(HOOKS / script), *args],
            input=json.dumps(event),
            capture_output=True,
            text=True,
            env=env,
            check=False,
        )

    def edit(self, path: str, tool: str = "Edit") -> subprocess.CompletedProcess[str]:
        event = {"hook_event_name": "PreToolUse", "tool_name": tool, "tool_input": {"file_path": str(self.repo / path)}}
        return self.hook("guard.py", event)

    def bash(self, command: str) -> subprocess.CompletedProcess[str]:
        event = {"hook_event_name": "PreToolUse", "tool_name": "Bash", "tool_input": {"command": command}}
        return self.hook("guard.py", event)


class GuardTests(HookTestCase):
    def test_allows_normal_edits_and_logs_them(self) -> None:
        self.assertEqual(self.edit("backend/app/main.py").returncode, 0)
        log = (self.repo / "agent-hooks/logs/audit.jsonl").read_text().splitlines()
        self.assertEqual(json.loads(log[-1])["decision"], "allow")

    def test_blocks_secrets(self) -> None:
        for tool in ("Read", "Edit", "Write"):
            r = self.edit(".env", tool)
            self.assertEqual(r.returncode, 2, tool)
            self.assertIn("secrets", r.stderr)
        self.assertEqual(self.edit(".env.example").returncode, 0)
        self.assertEqual(self.edit("backend/.env.production", "Read").returncode, 2)

    def test_blocks_committed_migrations_but_allows_new_ones(self) -> None:
        r = self.edit("backend/migrations/versions/0001_initial.py")
        self.assertEqual(r.returncode, 2)
        self.assertIn("alembic revision", r.stderr)
        self.assertEqual(self.edit("backend/migrations/versions/0002_new.py", "Write").returncode, 0)
        self.assertEqual(self.edit("backend/migrations/versions/0001_initial.py", "Read").returncode, 0)

    def test_blocks_generated_client(self) -> None:
        r = self.edit("frontend/src/api/schema.d.ts")
        self.assertEqual(r.returncode, 2)
        self.assertIn("gen:api", r.stderr)

    def test_openapi_requires_fresh_approval(self) -> None:
        r = self.edit("openapi.yaml")
        self.assertEqual(r.returncode, 2)
        self.assertIn("review-api-change", r.stderr)
        approve = self.hook("approve_contract_change.py", {}, "add pagination to runs")
        self.assertEqual(approve.returncode, 0, approve.stderr)
        self.assertEqual(self.edit("openapi.yaml").returncode, 0)
        # A new commit invalidates the approval.
        (self.repo / "x.txt").write_text("x")
        git(self.repo, "add", "x.txt")
        git(self.repo, "commit", "-qm", "next")
        r = self.edit("openapi.yaml")
        self.assertEqual(r.returncode, 2)
        self.assertIn("previous commit", r.stderr)

    def test_blocks_destructive_commands(self) -> None:
        for cmd in (
            "rm -rf backend",
            "git push --force origin main",
            "git push -f",
            "git reset --hard HEAD~1",
            "docker volume rm evalops_pgdata",
            "docker compose down -v",
            "psql -c 'DROP TABLE users'",
            "cat .env",
            "Get-Content backend/.env",
        ):
            self.assertEqual(self.bash(cmd).returncode, 2, cmd)

    def test_allows_ordinary_commands(self) -> None:
        for cmd in ("git status", "uv run pytest -q", "cat .env.example", "rm build.log", "git push origin feature"):
            self.assertEqual(self.bash(cmd).returncode, 0, cmd)


class StopHookTests(HookTestCase):
    def test_nothing_changed_means_instant_stop(self) -> None:
        r = self.hook("stop_tests.py", {"hook_event_name": "Stop"})
        self.assertEqual(r.returncode, 0, r.stderr)

    def test_does_not_loop(self) -> None:
        (self.repo / "backend/app.py").write_text("x = 1\n")
        r = self.hook("stop_tests.py", {"hook_event_name": "Stop", "stop_hook_active": True})
        self.assertEqual(r.returncode, 0)


if __name__ == "__main__":
    unittest.main()
