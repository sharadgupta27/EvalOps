"""Record that an API contract change was reviewed, unlocking openapi.yaml edits.

Usage: python agent-hooks/approve_contract_change.py "<reason>"
The approval is bound to the current commit and expires after 2 hours.
"""

import json
import sys
import time

from common import APPROVAL, head_sha


def main() -> None:
    if len(sys.argv) < 2 or not sys.argv[1].strip():
        print('usage: approve_contract_change.py "<reason>"', file=sys.stderr)
        sys.exit(1)
    APPROVAL.parent.mkdir(parents=True, exist_ok=True)
    APPROVAL.write_text(
        json.dumps({"approved_at": time.time(), "head": head_sha(), "reason": sys.argv[1]}),
        encoding="utf-8",
    )
    print(f"openapi.yaml unlocked for 2 hours at {head_sha()[:12]}: {sys.argv[1]}")


if __name__ == "__main__":
    main()
