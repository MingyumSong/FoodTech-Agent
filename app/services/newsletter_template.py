"""푸디픽(FOODIE's PICK) HTML 조립 (T-008).

목업(docs/branding/newsletter-mockup.html)의 "최종 시안" 시각 언어를 이메일 제약
(600px·인라인 CSS·텍스트 우선) 안에서 재구현한다. 색만 파랑 계열(07-22 희정 피드백).
- 기사 링크는 DB 저장 원본 URL 그대로 — 클릭 웹훅의 URL 문자열 매칭(T-003) 전제라 변형 금지.
- 파일럿 코너: 01 아뮤즈부슈(숫자) · 02 에피타이저(헤드라인 3) · 03 메인(심층 2).
  04 사이드(논문)는 OpenAlex 미구현, 05 디저트(행사 CTA)는 "(광고)" 법무 미해결로 제외 (티켓 8).
"""

import html as html_lib
from typing import Any

# 파란 팔레트 (목업 accent #0B9F6A(초록)를 파랑으로 치환, 중립색은 목업 그대로)
ACCENT = "#1F6FB2"
ACCENT_SOFT = "#E4EFF8"
INK = "#16181D"
GRAY = "#4B5563"
GRAY_SOFT = "#9CA3AF"
LINE = "#E5E7EB"
LINE_SOFT = "#F0F1F3"
BG = "#E7EDF4"

FONT = "'Apple SD Gothic Neo','Malgun Gothic','Segoe UI',sans-serif"
MONO = "'SF Mono','Menlo','Consolas',monospace"


def _esc(text: str) -> str:
    return html_lib.escape(text, quote=True)


def _source_label(item: dict[str, Any]) -> str:
    region = "KR" if item.get("region") == "domestic" else "GLOBAL"
    source = (item.get("source") or "").strip()
    return f"{region} · {source}" if source else region


def _course_header(no: str, name: str, desc: str) -> str:
    """코스 뱃지 + 이름 + 설명 + 우측으로 뻗는 헤어라인 (목업 .fp-course)."""
    return f"""<table width="100%" cellpadding="0" cellspacing="0" style="margin:30px 0 6px;">
<tr>
  <td style="width:1%;white-space:nowrap;padding-right:10px;">
    <span style="font-family:{MONO};font-size:11px;font-weight:700;color:{ACCENT};
      background:{ACCENT_SOFT};padding:4px 8px;border-radius:4px;">{no}</span>
  </td>
  <td style="width:1%;white-space:nowrap;font-size:13px;font-weight:800;
      letter-spacing:.06em;color:{INK};padding-right:10px;">{_esc(name)}</td>
  <td style="width:1%;white-space:nowrap;font-size:12px;color:{GRAY_SOFT};
      padding-right:12px;">{_esc(desc)}</td>
  <td style="border-top:1px solid {LINE_SOFT};font-size:0;">&nbsp;</td>
</tr>
</table>"""


def _item(item: dict[str, Any], *, summary_limit: int = 200, last: bool = False) -> str:
    """기사 1건 — 소스 라벨 + 제목 링크 + 요약 (목업 .fp-item)."""
    border = "" if last else f"border-bottom:1px solid {LINE_SOFT};"
    summary = (item.get("summary") or "").strip()
    if len(summary) > summary_limit:
        summary = summary[: summary_limit - 1].rstrip() + "…"
    summary_html = (
        f'<p style="margin:4px 0 0;font-size:13.5px;line-height:1.6;color:{GRAY};">'
        f"{_esc(summary)}</p>"
        if summary
        else ""
    )
    return f"""<div style="padding:12px 0;{border}">
  <div style="font-family:{MONO};font-size:11px;color:{GRAY_SOFT};">{
        _esc(_source_label(item))
    }</div>
  <a href="{item["url"]}" style="color:{INK};font-weight:700;font-size:15.5px;
     text-decoration:none;line-height:1.5;">{_esc(item["title"])}</a>
  {summary_html}
</div>"""


def render_foodie_pick(
    *,
    issue_no: int,
    issue_date: str,
    amuse_big: str,
    amuse_caption: str,
    main_items: list[dict[str, Any]],
    headline_items: list[dict[str, Any]],
    unsubscribe_url: str,
) -> str:
    """푸디픽 1호분 HTML. 아이템 dict = news_items 행(title/url/summary/source/region/category)."""
    headlines = "".join(
        _item(it, summary_limit=90, last=(i == len(headline_items) - 1))
        for i, it in enumerate(headline_items)
    )
    mains = "".join(_item(it, last=(i == len(main_items) - 1)) for i, it in enumerate(main_items))
    return f"""<!DOCTYPE html>
<html lang="ko">
<body style="margin:0;padding:0;background:{BG};">
<table width="100%" cellpadding="0" cellspacing="0" style="background:{BG};">
<tr><td align="center" style="padding:26px 10px;">
<table width="600" cellpadding="0" cellspacing="0"
       style="width:600px;max-width:100%;background:#FFFFFF;font-family:{FONT};color:{INK};">

<tr><td style="padding:30px 32px 22px;border-bottom:1px solid {LINE};">
  <table width="100%" cellpadding="0" cellspacing="0"><tr>
    <td>
      <div style="font-size:26px;font-weight:800;letter-spacing:-.02em;">푸디픽<span
        style="color:{ACCENT};">✓</span></div>
      <div style="font-size:12px;color:#6B7280;margin-top:2px;">FOODIE's PICK —
        푸디가 고른 푸드테크, 매주 목요일</div>
    </td>
    <td align="right" valign="bottom" style="font-family:{MONO};font-size:12px;
        color:#6B7280;white-space:nowrap;">#{issue_no:03d} · {_esc(issue_date)}</td>
  </tr></table>
</td></tr>

<tr><td style="padding:0 32px 8px;">

  {_course_header("01", "아뮤즈부슈", "이번 주 숫자 하나")}
  <div style="border-left:3px solid {ACCENT};padding:2px 0 2px 18px;margin:8px 0 6px;">
    <div style="font-size:34px;font-weight:800;letter-spacing:-.02em;">{_esc(amuse_big)}</div>
    <div style="font-size:14px;color:{GRAY};margin-top:2px;">{_esc(amuse_caption)}</div>
  </div>

  {_course_header("02", "에피타이저", "헤드라인 픽 3")}
  {headlines}

  {_course_header("03", "메인", "깊이 볼 뉴스 2")}
  {mains}

  <div style="margin:26px 0 0;padding:14px 18px;background:#F5F7FA;border-radius:8px;
       font-size:13.5px;color:{GRAY};">
    오늘 코스는 여기까지입니다. 다음 주 목요일에 더 신선한 픽으로 차릴게요. — 푸디 드림
  </div>

</td></tr>

<tr><td style="padding:22px 32px 30px;font-size:12px;color:{GRAY_SOFT};
     border-top:1px solid {LINE};line-height:1.7;">
  푸디픽은 푸드테크센터(foodtech-center.org)가 매주 목요일 발행합니다.<br>
  이 메일에 답장하시면 운영진이 직접 읽습니다.<br>
  <a href="{unsubscribe_url}" style="color:#6B7280;">수신거부</a>
</td></tr>

</table>
</td></tr>
</table>
</body>
</html>"""


def render_text_fallback(
    *,
    amuse_big: str,
    amuse_caption: str,
    main_items: list[dict[str, Any]],
    headline_items: list[dict[str, Any]],
) -> str:
    lines = [
        "푸디픽 — 푸디가 고른 푸드테크",
        "",
        f"[아뮤즈부슈] {amuse_big} — {amuse_caption}",
        "",
        "[에피타이저]",
    ]
    lines += [f"- {it['title']} ({it['url']})" for it in headline_items]
    lines += ["", "[메인]"]
    lines += [f"- {it['title']} ({it['url']})" for it in main_items]
    lines += ["", "오늘 코스는 여기까지입니다. — 푸디 드림"]
    return "\n".join(lines)
