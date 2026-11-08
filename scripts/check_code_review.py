import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path

SENTINEL_PATH = Path(".claude/.last_reviewed_diff")


def _staged_diff_hash() -> str:
    diff = subprocess.run(
        ["git", "diff", "--cached"], capture_output=True, text=True
    ).stdout
    return hashlib.sha256(diff.encode()).hexdigest()


def main() -> int:
    data = json.load(sys.stdin)
    command = data.get("tool_input", {}).get("command", "")
    if not re.search(r"\bgit\s+commit\b", command):
        return 0

    diff_hash = _staged_diff_hash()
    if not diff_hash or diff_hash == hashlib.sha256(b"").hexdigest():
        return 0  # нема застейджених змін — нема що ревʼюїти

    if SENTINEL_PATH.exists() and SENTINEL_PATH.read_text().strip() == diff_hash:
        return 0  # цей самий diff вже пройшов рев'ю

    print(
        "Перед комітом запусти code-review-skill (~/.claude/skills/code-review-skill) "
        "на застейджені зміни. Після рев'ю збережи хеш поточного diff і повтори коміт:\n\n"
        f'  echo "{diff_hash}" > {SENTINEL_PATH}\n',
        file=sys.stderr,
    )
    return 2


if __name__ == "__main__":
    sys.exit(main())
