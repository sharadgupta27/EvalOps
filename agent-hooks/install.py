"""Sync the agent extension pack from its sources into the places agents load it from.

Sources (edit these):              Generated copies (do not edit):
  agent-capabilities/<skill>/       → .claude/skills/<skill>/              (Claude Code, this repo)
  agent-capabilities/subagents/*.md → .claude/agents/*.md
  both + agent-hooks/*.py           → plugins/evalops-agent-pack/...       (reusable plugin)

Usage: python agent-hooks/install.py          # sync
       python agent-hooks/install.py --check  # exit 1 if any copy is stale (used in CI)
"""

import filecmp
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CAPS = ROOT / "agent-capabilities"
PLUGIN = ROOT / "plugins" / "evalops-agent-pack"
HOOK_SCRIPTS = ["common.py", "guard.py", "format_on_save.py", "stop_tests.py", "approve_contract_change.py"]


def planned_copies() -> list[tuple[Path, Path]]:
    pairs: list[tuple[Path, Path]] = []
    for skill in sorted(p for p in CAPS.iterdir() if (p / "SKILL.md").exists()):
        for f in sorted(skill.rglob("*")):
            if f.is_file():
                rel = f.relative_to(CAPS)
                pairs.append((f, ROOT / ".claude" / "skills" / rel))
                pairs.append((f, PLUGIN / "skills" / rel))
    for agent in sorted((CAPS / "subagents").glob("*.md")):
        pairs.append((agent, ROOT / ".claude" / "agents" / agent.name))
        pairs.append((agent, PLUGIN / "agents" / agent.name))
    for script in HOOK_SCRIPTS:
        pairs.append((ROOT / "agent-hooks" / script, PLUGIN / "hooks" / script))
    pairs.append((ROOT / "mcp-server" / "server.py", PLUGIN / "mcp-server" / "server.py"))
    pairs.append((ROOT / "mcp-server" / "pyproject.toml", PLUGIN / "mcp-server" / "pyproject.toml"))
    return pairs


def main() -> int:
    check = "--check" in sys.argv
    stale = [dst for src, dst in planned_copies() if not dst.exists() or not filecmp.cmp(src, dst, shallow=False)]
    if check:
        for dst in stale:
            print(f"stale: {dst.relative_to(ROOT).as_posix()}")
        if stale:
            print("run: python agent-hooks/install.py", file=sys.stderr)
        return 1 if stale else 0
    for src, dst in planned_copies():
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(src, dst)
    print(f"synced {len(planned_copies())} files ({len(stale)} changed)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
