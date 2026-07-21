"""푸디픽(FOODIE's PICK) HTML 조립 (T-008).

- 팔레트: 하늘·파랑 계열 (07-22 희정 피드백) — 목업 newsletter-mockup.html과 동기화.
- 이메일 클라이언트 호환을 위해 전부 인라인 스타일.
- 기사 링크는 DB 저장 원본 URL 그대로 — 클릭 웹훅의 URL 문자열 매칭(T-003) 전제라 변형 금지.
- 파일럿 코너: 아뮤즈부슈(숫자) + 에피타이저(헤드라인 3) + 메인(심층 2).
  사이드(논문)는 OpenAlex 미구현, 디저트(행사 CTA)는 "(광고)" 표기 법무 미해결로 제외 (티켓 8).
"""

import html as html_lib
from typing import Any

# 파란 팔레트 (목업 라이트 모드와 동일)
ACCENT = "#1F6FB2"
ACCENT_SOFT = "#E4EFF8"
INK = "#1E242B"
INK_SOFT = "#55606B"
LINE = "#D6DDE5"
BG = "#E7EDF4"

CATEGORY_LABELS_KO = {
    "cell_cultured": "세포배양식품",
    "plant_based": "식물기반식품",
    "convenience": "간편식",
    "food_printing": "식품프린팅",
    "smart_manufacturing": "스마트제조",
    "smart_distribution": "스마트유통",
    "customizing": "커스터마이징",
    "food_service": "외식 푸드테크",
    "upcycling": "업사이클링",
    "eco_packaging": "친환경포장",
    "general": "일반",
}


def _esc(text: str) -> str:
    return html_lib.escape(text, quote=True)


def _chip(category: str) -> str:
    label = CATEGORY_LABELS_KO.get(category, category)
    return (
        f'<span style="background:{ACCENT_SOFT};color:{ACCENT};border-radius:999px;'
        f'padding:2px 10px;font-size:12px;">{_esc(label)}</span>'
    )


def _section_header(no: str, title: str, sub: str) -> str:
    return (
        f'<div style="margin:28px 0 12px;">'
        f'<div style="font-size:12px;font-weight:700;color:{ACCENT};'
        f'letter-spacing:.1em;">{no}</div>'
        f'<div style="font-size:18px;font-weight:700;color:{INK};">{_esc(title)}</div>'
        f'<div style="font-size:13px;color:{INK_SOFT};">{_esc(sub)}</div>'
        f"</div>"
    )


def _main_card(item: dict[str, Any]) -> str:
    summary = _esc((item.get("summary") or "").strip())
    source = _esc(item.get("source") or "")
    source_html = (
        f'<div style="font-size:12px;color:{INK_SOFT};margin-top:8px;">{source}</div>'
        if source
        else ""
    )
    return (
        f'<div style="background:#FFFFFF;border:1px solid {LINE};border-radius:10px;'
        f'padding:18px 20px;margin-bottom:12px;">'
        f"{_chip(item['category'])}"
        f'<h3 style="margin:10px 0 6px;font-size:16px;line-height:1.45;">'
        f'<a href="{item["url"]}" style="color:{INK};text-decoration:none;">'
        f"{_esc(item['title'])}</a></h3>"
        f'<p style="margin:0;font-size:14px;line-height:1.6;color:{INK_SOFT};">{summary}</p>'
        f"{source_html}"
        f"</div>"
    )


def _headline_row(item: dict[str, Any]) -> str:
    return (
        f'<div style="padding:10px 0;border-bottom:1px solid {LINE};">'
        f"{_chip(item['category'])} "
        f'<a href="{item["url"]}" style="color:{INK};font-size:14.5px;font-weight:600;'
        f'text-decoration:none;">{_esc(item["title"])}</a>'
        f"</div>"
    )


def render_foodie_pick(
    *,
    amuse_text: str,
    main_items: list[dict[str, Any]],
    headline_items: list[dict[str, Any]],
    unsubscribe_url: str,
) -> str:
    """푸디픽 1호분 HTML. 아이템 dict는 news_items 행(title/url/summary/source/category)."""
    mains = "".join(_main_card(it) for it in main_items)
    headlines = "".join(_headline_row(it) for it in headline_items)
    return f"""<!DOCTYPE html>
<html lang="ko">
<body style="margin:0;padding:0;background:{BG};">
<div style="max-width:600px;margin:0 auto;padding:28px 16px;
            font-family:'Apple SD Gothic Neo','Malgun Gothic',Segoe UI,sans-serif;">
  <div style="background:#FFFFFF;border:1px solid {LINE};border-radius:12px;padding:28px 26px;">
    <div style="font-size:13px;font-weight:700;color:{ACCENT};letter-spacing:.12em;">FOODIE'S
    PICK</div>
    <h1 style="margin:6px 0 4px;font-size:24px;color:{INK};">푸디픽</h1>
    <p style="margin:0;font-size:14px;color:{INK_SOFT};">푸디가 골라온 이번 주 푸드테크 소식</p>

    {_section_header("01", "아뮤즈부슈", "숫자로 여는 이번 주")}
    <div style="background:{ACCENT_SOFT};border-radius:10px;padding:16px 18px;
                font-size:15px;color:{INK};">{_esc(amuse_text)}</div>

    {_section_header("02", "에피타이저", "가볍게 훑는 헤드라인")}
    {headlines}

    {_section_header("03", "메인 디시", "이번 주의 심층 두 접시")}
    {mains}
  </div>

  <div style="text-align:center;padding:20px 8px;font-size:12px;color:{INK_SOFT};">
    푸디 by 푸드테크센터 · 매주 목요일<br>
    더 이상 받고 싶지 않으시면
    <a href="{unsubscribe_url}" style="color:{ACCENT};">수신거부</a>를 눌러주세요.
  </div>
</div>
</body>
</html>"""


def render_text_fallback(
    *, amuse_text: str, main_items: list[dict[str, Any]], headline_items: list[dict[str, Any]]
) -> str:
    lines = ["푸디픽 — 이번 주 푸드테크 소식", "", f"[아뮤즈부슈] {amuse_text}", "", "[에피타이저]"]
    lines += [f"- {it['title']} ({it['url']})" for it in headline_items]
    lines += ["", "[메인 디시]"]
    lines += [f"- {it['title']} ({it['url']})" for it in main_items]
    return "\n".join(lines)
