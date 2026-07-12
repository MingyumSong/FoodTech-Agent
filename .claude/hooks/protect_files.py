"""PreToolUse 훅: 보호 파일(.env*, uv.lock) 수정 차단. exit 2 = 차단."""

import json
import os
import sys

data = json.load(sys.stdin)
path = data.get("tool_input", {}).get("file_path", "")
base = os.path.basename(path)

if base == "uv.lock":
    print("uv.lock은 uv 명령으로만 갱신한다 (rules/uv-only.md)", file=sys.stderr)
    sys.exit(2)

if base.startswith(".env") and base != ".env.example":
    print(".env 직접 수정 금지 — 사용자에게 요청할 것 (rules/secrets.md)", file=sys.stderr)
    sys.exit(2)

sys.exit(0)
