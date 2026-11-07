import json
import os
import re
import subprocess
import sys


def main() -> int:
    data = json.load(sys.stdin)
    command = data.get("tool_input", {}).get("command", "")
    if not re.search(r"\bgit\s+(add|commit)\b", command):
        return 0

    staged_files = subprocess.run(
        ["git", "diff", "--cached", "--name-only"], capture_output=True, text=True
    ).stdout.splitlines()
    if ".env" in staged_files:
        print("Blocked: .env is staged for commit/add.", file=sys.stderr)
        return 2

    if os.path.exists(".env"):
        token = None
        with open(".env") as f:
            for line in f:
                if line.startswith("TELEGRAM_BOT_TOKEN="):
                    token = line.split("=", 1)[1].strip()
                    break
        if token:
            diff = subprocess.run(
                ["git", "diff", "--cached"], capture_output=True, text=True
            ).stdout
            if token in diff:
                print("Blocked: TELEGRAM_BOT_TOKEN value found in staged changes.", file=sys.stderr)
                return 2

    return 0


if __name__ == "__main__":
    sys.exit(main())
