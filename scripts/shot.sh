#!/usr/bin/env bash
# HTML을 데스크톱·모바일 두 폭으로 캡처하고 좌우 비교 페이지까지 만든다.
#
#   bash scripts/shot.sh docs/branding/newsletter-v2.html
#   bash scripts/shot.sh out.html 이름          # 산출물 접두사 지정
#
# 왜 스크립트인가: 손이 가는 건 판단이 아니라 플래그다 — 공백 들어간 Chrome 경로,
# --headless --hide-scrollbars --window-size, 폭 바꿔 두 번 반복, 비교 페이지 조립.
# "보고 판단하는" 부분은 사람/에이전트 몫이라 자동화하지 않는다.
#
# 마지막에 **절대경로를 출력**한다 — 그 경로를 Read로 열어 눈으로 확인하는 것이 이 스크립트의 목적이다.
# 캡처만 하고 안 보면 아무 의미가 없다.
set -euo pipefail
cd "$(dirname "$0")/.."

SRC="${1:-}"
NAME="${2:-shot}"
if [ -z "$SRC" ]; then
  echo "사용법: bash scripts/shot.sh <파일.html> [이름]" >&2
  exit 2
fi
[ -f "$SRC" ] || { echo "파일 없음: $SRC" >&2; exit 2; }

CHROME="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
[ -x "$CHROME" ] || { echo "Chrome을 찾을 수 없다: $CHROME" >&2; exit 3; }

OUT="${SHOT_DIR:-$(mktemp -d)}"
ABS_SRC="$(cd "$(dirname "$SRC")" && pwd)/$(basename "$SRC")"

shoot() {  # 폭 높이 출력파일
  "$CHROME" --headless --disable-gpu --hide-scrollbars \
    --allow-file-access-from-files --force-device-scale-factor=2 \
    --virtual-time-budget=3000 \
    --window-size="$1,$2" --screenshot="$3" "file://$ABS_SRC" 2>/dev/null
}

shoot 900 1400 "$OUT/$NAME-desktop.png"
shoot 390 1600 "$OUT/$NAME-mobile.png"

# 좌우 비교 페이지 — 한 장으로 두 폭을 같이 본다
cat > "$OUT/$NAME-compare.html" <<EOF
<!DOCTYPE html><html><head><meta charset="utf-8"></head>
<body style="margin:0;background:#22262C;font-family:-apple-system,sans-serif;">
<table cellpadding="0" cellspacing="0"><tr>
<td valign="top" style="padding:12px;">
  <div style="color:#fff;font-size:14px;font-weight:700;padding:6px;">데스크톱 900px</div>
  <iframe src="$ABS_SRC" style="width:900px;height:1400px;border:0;background:#fff;"></iframe></td>
<td valign="top" style="padding:12px;">
  <div style="color:#fff;font-size:14px;font-weight:700;padding:6px;">모바일 390px</div>
  <iframe src="$ABS_SRC" style="width:390px;height:1400px;border:0;background:#fff;"></iframe></td>
</tr></table></body></html>
EOF
"$CHROME" --headless --disable-gpu --hide-scrollbars --allow-file-access-from-files \
  --force-device-scale-factor=1.5 --virtual-time-budget=3000 \
  --window-size=1360,1450 --screenshot="$OUT/$NAME-compare.png" \
  "file://$OUT/$NAME-compare.html" 2>/dev/null

echo "캡처 완료 — 아래 경로를 Read로 열어 직접 확인할 것:"
echo "  $OUT/$NAME-compare.png   (데스크톱·모바일 나란히)"
echo "  $OUT/$NAME-desktop.png"
echo "  $OUT/$NAME-mobile.png"
echo "브라우저로 보려면: open \"$OUT/$NAME-compare.html\""
