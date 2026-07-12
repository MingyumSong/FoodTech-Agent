"""PostToolUse 훅: .py 파일 Edit/Write 후 ruff 자동 포맷. 항상 exit 0."""

import json
import subprocess
import sys

data = json.load(sys.stdin)
path = data.get("tool_input", {}).get("file_path", "")

if path.endswith(".py") and "/archive/" not in path:
    subprocess.run(
        ["uv", "run", "--no-sync", "ruff", "format", path],
        capture_output=True,
        check=False,
    )

sys.exit(0)
