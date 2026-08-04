"""PostToolUse 훅: .py 파일 Edit/Write 후 ruff 자동 포맷 + 줄길이 위반 즉시 경고. 항상 exit 0.

`ruff format`은 **긴 한글 주석·문자열의 E501을 고치지 못한다**(줄을 쪼갤 수 없는 토큰이라).
그래서 위반이 조용히 살아남아 세션 끝 check.sh에서야 터진다 — 그 사이 커밋까지 간 사고도 있었다.
차단(exit 2)이 아니라 stderr 경고로 알린다: 긴 URL·데이터 리터럴처럼 정당한 초과가 있다.
"""

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
    lint = subprocess.run(
        [
            "uv",
            "run",
            "--no-sync",
            "ruff",
            "check",
            "--select",
            "E501",
            "--output-format",
            "concise",
            path,
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    if lint.returncode != 0 and lint.stdout.strip():
        print(f"⚠️ 줄길이 초과(E501) — 지금 고칠 것:\n{lint.stdout.strip()}", file=sys.stderr)

sys.exit(0)
