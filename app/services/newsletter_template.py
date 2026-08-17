"""푸디픽(FOODIE's PICK) HTML 조립 — v2 (T-013).

파일럿 수신자 피드백으로 구성을 뒤집었다: 이전은 아뮤즈부슈 + 에피타이저 3 + 메인 2였고,
지금은 **에피타이저 2 + 메인 3 + 디저트**다. 큐레이션 뉴스레터의 표준(리드 스토리 + 큐레이션
묶음 + 단일 CTA)과도 맞다 — 깊이 볼 것을 늘리고 흘려볼 것을 줄였다.

시각 언어는 B안(브리핑): 다크 네이비 헤더 + 좌측 컬러 레일 + 고밀도. 매일 발송이라 스크롤이
짧은 쪽이 유리하다는 판단.

- 아뮤즈부슈(숫자 하나) 제거 → 그 자리에 "오늘의 분야" 줄. 숫자보다 그 편에 뭐가 실렸는지
  보여주는 게 낫고, "10대 분류 표시가 좋았다"는 피드백과도 맞다.
- 기사 링크는 DB 저장 원본 URL 그대로 — 클릭 웹훅의 URL 문자열 매칭(T-003) 전제라 변형 금지.
- 헤더 네이비(#042A4F)는 배너 에셋에서 뽑은 값 — 아이콘 PNG와 이음매가 없어야 해서 고정이다.
- 폭은 고정 600px이 아니라 max-width — 좁은 화면에서 가로로 잘리지 않게 (피드백 검수에서 발견).
"""

import html as html_lib
from typing import Any

# 팔레트 — 대시보드(`/admin/dashboard`)의 WFTC 토큰을 메일로 옮긴 값이다.
#
# **대시보드는 다크 배경이지만 메일은 밝게 간다.** 색만 가져오고 지면은 흰색으로 두는 이유:
# 메일 클라이언트의 다크모드가 배경·글자색을 제멋대로 반전시켜 다크 디자인이 오히려 깨지고,
# Outlook은 그라데이션을 아예 못 그린다. 브랜드 인상은 **블루+골드 액센트**가 만든다.
#
# NAVY는 예전엔 foodie-icon.png 배경에서 샘플링한 값이라 "바꾸지 말 것"이었는데,
# 아이콘이 **배경 없는 투명 PNG**라 그 제약은 실재하지 않는다(2026-08-18 확인).
NAVY = "#0B122C"  # 대시보드 --snu-navy. 헤더 바탕 + 제목 글자
NAVY_SOFT = "#A9B0D0"  # 네이비 위 보조 텍스트 (대시보드 --snu-ink-2 계열)
BRAND = "#005CB9"  # WFTC 메인 블루
BRAND_SOFT = "#EAF2FB"
GOLD = "#FFD338"  # WFT 골드 — 대시보드의 서명 액센트
GOLD_SOFT = "#FFF7DC"
INK = "#0B122C"
GRAY = "#4A5568"
GRAY_SOFT = "#8A93A6"
LINE = "#E4E9F2"
BLOCK_BG = "#FFFFFF"
BG = "#F5F7FB"

FONT = "'Apple SD Gothic Neo','Malgun Gothic','Segoe UI',sans-serif"

# 발송 시 수신자별로 치환되는 자리표시자 (send_newsletter가 채운다).
REACTION_BASE_PLACEHOLDER = "__REACTION_BASE__"

# 이모지를 뺐다 — 세 버튼에 이모지를 달면 본문 어디에도 없는 장식이 여기만 튄다.
REACTIONS = [("good", "좋았어요"), ("ok", "보통"), ("bad", "별로")]


def _esc(text: str) -> str:
    return html_lib.escape(text, quote=True)


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


def _label(item: dict[str, Any]) -> str:
    return CATEGORY_LABELS_KO.get(item.get("category") or "", "")


def _source_line(item: dict[str, Any]) -> str:
    region = "KR" if item.get("region") == "domestic" else "GLOBAL"
    source = (item.get("source") or "").strip()
    return f"{region} · {source}" if source else region


def _chip(item: dict[str, Any], *, solid: bool) -> str:
    """분야 칩. 메인은 채운 칩, 에피타이저는 연한 칩으로 위계를 준다."""
    label = _label(item)
    if not label:
        return ""
    style = (
        f"background:{ACCENT};color:#FFFFFF;"
        if solid
        else f"background:{ACCENT_SOFT};color:{ACCENT};"
    )
    return (
        f'<span style="{style}border-radius:3px;padding:2px 8px;'
        f'font-size:11px;font-weight:700;">{_esc(label)}</span>'
    )


def _meta_row(item: dict[str, Any], *, solid_chip: bool) -> str:
    return (
        f'<div style="margin-bottom:5px;">{_chip(item, solid=solid_chip)}'
        f'<span style="font-family:{MONO};font-size:10.5px;color:#A3AEB8;">'
        f"&nbsp; {_esc(_source_line(item))}</span></div>"
    )


def _section_label(no: str, name: str, desc: str) -> str:
    return (
        f'<div style="margin:26px 0 2px;font-family:{MONO};font-size:10.5px;'
        f'font-weight:700;color:{ACCENT};letter-spacing:.12em;">{no} &nbsp;{_esc(name)} '
        f'&nbsp;<span style="color:#B4C2CE;font-weight:400;">{_esc(desc)}</span></div>'
    )


def _headline_item(item: dict[str, Any]) -> str:
    """에피타이저 — 메인과 같은 순서(칩 → 제목)로 통일. 코너가 달라도 읽는 순서는 같아야 한다."""
    return f"""<table width="100%" cellpadding="0" cellspacing="0" style="margin-top:8px;">
<tr>
  <td style="width:3px;background:#9EC5E4;font-size:0;">&nbsp;</td>
  <td style="padding:9px 0 9px 12px;">
    {_meta_row(item, solid_chip=False)}
    <a href="{item["url"]}" style="color:{INK};font-weight:700;font-size:15px;
       text-decoration:none;line-height:1.5;">{_esc(item["title"])}</a>
  </td>
</tr>
</table>"""


def _main_card(item: dict[str, Any], *, summary_limit: int = 170) -> str:
    """메인 — 좌측 레일 + 연회색 블록. 해외는 레일 색으로 구분."""
    summary = (item.get("summary") or "").strip()
    if len(summary) > summary_limit:
        summary = summary[: summary_limit - 1].rstrip() + "…"
    summary_html = (
        f'<p style="margin:7px 0 0;font-size:13px;line-height:1.68;color:{GRAY};">'
        f"{_esc(summary)}</p>"
        if summary
        else ""
    )
    # 레일 색은 국내·해외를 가리지 않는다 — 회색을 쓰니 해외 기사가 덜 중요해 보였다.
    # 지역 구분은 메타 줄의 KR/GLOBAL 라벨이 이미 하고 있다.
    return f"""<table width="100%" cellpadding="0" cellspacing="0" style="margin-top:8px;">
<tr>
  <td style="width:4px;background:{ACCENT};font-size:0;">&nbsp;</td>
  <td style="background:{BLOCK_BG};padding:14px 16px;">
    {_meta_row(item, solid_chip=True)}
    <a href="{item["url"]}" style="color:{INK};font-weight:800;font-size:16.5px;
       text-decoration:none;line-height:1.42;">{_esc(item["title"])}</a>
    {summary_html}
  </td>
</tr>
</table>"""


def _today_strip(items: list[dict[str, Any]]) -> str:
    """헤더 아래 '오늘의 분야' 한 줄 — 아뮤즈부슈를 대체한다. 중복 제거, 등장 순서 유지."""
    seen: list[str] = []
    for it in items:
        label = _label(it)
        if label and label not in seen:
            seen.append(label)
    if not seen:
        return ""
    return f"""<tr><td style="background:{
        BLOCK_BG
    };padding:12px 30px;border-bottom:1px solid #DFE7EE;">
  <span style="font-family:{MONO};font-size:10px;font-weight:700;color:#7C93A6;
    letter-spacing:.1em;">TODAY</span>
  <span style="font-size:12.5px;color:#33526B;font-weight:600;">&nbsp; {
        _esc(" · ".join(seen))
    }</span>
</td></tr>"""


def _dessert() -> str:
    """디저트 — 원클릭 반응 3버튼. 클릭 한 번이 참여 신호이자 체류 대체 지표가 된다.

    헤더와 같은 네이비를 쓰면 위아래가 무겁게 닫혀서 연한 하늘색으로 바꿨다.
    """
    buttons = []
    for i, (value, label) in enumerate(REACTIONS):
        style = (
            f"background:{ACCENT};color:#FFFFFF;"
            if i == 0
            else f"background:#FFFFFF;color:{ACCENT};border:1px solid #C9D9E7;"
        )
        buttons.append(
            f'<a href="{REACTION_BASE_PLACEHOLDER}/{value}" style="display:inline-block;'
            f"{style}border-radius:6px;padding:9px 15px;margin:0 4px 6px 0;"
            f'font-size:13px;font-weight:700;text-decoration:none;">{label}</a>'
        )
    return f"""<table width="100%" cellpadding="0" cellspacing="0"
       style="margin-top:10px;background:{ACCENT_SOFT};border-radius:8px;">
<tr><td style="padding:18px 20px;">
  <div style="font-size:14px;font-weight:700;color:{INK};">오늘 코스는 어떠셨나요?</div>
  <div style="font-size:12px;color:#4A6C88;margin:4px 0 13px;">눌러주신 한 번이 다음 픽을
    더 정확하게 만듭니다</div>
  {"".join(buttons)}
</td></tr>
</table>"""


def _header(issue_no: int, issue_date: str, icon_url: str | None) -> str:
    icon = (
        f'<img src="{icon_url}" width="77" height="57" alt="" style="display:block;border:0;">'
        if icon_url
        else "&nbsp;"
    )
    return f"""<tr><td style="background:{NAVY};padding:22px 30px;">
  <table width="100%" cellpadding="0" cellspacing="0"><tr>
    <td valign="middle">
      <div style="font-size:27px;font-weight:800;letter-spacing:-.02em;color:#FFFFFF;">푸디픽<span
        style="color:{HIGHLIGHT};">✓</span></div>
      <div style="font-family:{MONO};font-size:11px;color:{NAVY_SOFT};margin-top:5px;
        letter-spacing:.06em;">FOODIE'S PICK · 데일리 브리핑</div>
      <div style="font-family:{MONO};font-size:11px;color:{NAVY_SOFT};margin-top:6px;">
        #{issue_no:03d} · {_esc(issue_date)}</div>
    </td>
    <td align="right" valign="middle" style="width:77px;">{icon}</td>
  </tr></table>
</td></tr>"""


def render_foodie_pick(
    *,
    issue_no: int,
    issue_date: str,
    main_items: list[dict[str, Any]],
    headline_items: list[dict[str, Any]],
    unsubscribe_url: str,
    icon_url: str | None = None,
) -> str:
    """푸디픽 1호분 HTML. 아이템 dict = news_items 행(title/url/summary/source/region/category).

    코너 순서는 에피타이저(headline_items) → 메인(main_items) → 디저트다.
    반응 버튼 URL은 자리표시자로 남고 발송 시 수신자별로 치환된다.
    """
    headlines = "".join(_headline_item(it) for it in headline_items)
    mains = "".join(_main_card(it) for it in main_items)
    today = _today_strip(headline_items + main_items)
    return f"""<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<style>
  @media only screen and (max-width:480px) {{
    .fp-pad {{ padding-left:18px !important; padding-right:18px !important; }}
  }}
</style>
</head>
<body style="margin:0;padding:0;background:{BG};">
<table width="100%" cellpadding="0" cellspacing="0" style="background:{BG};">
<tr><td align="center" style="padding:20px 8px;">
<!--[if mso]><table width="600" cellpadding="0" cellspacing="0"><tr><td><![endif]-->
<table cellpadding="0" cellspacing="0"
       style="width:100%;max-width:600px;background:#FFFFFF;font-family:{FONT};color:{INK};">

{_header(issue_no, issue_date, icon_url)}
{today}

<tr><td class="fp-pad" style="padding:0 30px;">

  {_section_label("01", "에피타이저", "가볍게 훑는 2")}
  {headlines}

  {_section_label("02", "메인", "깊이 보는 3")}
  {mains}

  {_section_label("03", "디저트", "한 번만 눌러주세요")}
  {_dessert()}

  <div style="margin:22px 0 0;font-size:13px;color:{GRAY};line-height:1.65;">
    오늘 브리핑은 여기까지입니다. 내일 더 신선한 픽으로 차릴게요. — <b>푸디 드림</b>
  </div>

</td></tr>

<tr><td class="fp-pad" style="padding:22px 30px 26px;">
  <div style="border-top:1px solid {LINE};padding-top:16px;font-size:11.5px;
       color:{GRAY_SOFT};line-height:1.85;">
    푸디픽은 <a href="https://foodtech-center.org" style="color:{ACCENT};
    text-decoration:none;">푸드테크센터</a>가 발행합니다.<br>
    이 메일에 <b style="color:{GRAY};">답장</b>하시면 운영진에게 바로 전달됩니다.<br>
    <a href="{unsubscribe_url}" style="color:#6B7280;">수신거부</a>
  </div>
</td></tr>

</table>
<!--[if mso]></td></tr></table><![endif]-->
</td></tr>
</table>
</body>
</html>"""


def render_text_fallback(
    *,
    main_items: list[dict[str, Any]],
    headline_items: list[dict[str, Any]],
) -> str:
    categories = []
    for it in headline_items + main_items:
        label = _label(it)
        if label and label not in categories:
            categories.append(label)

    lines = ["푸디픽 — 푸디가 고른 푸드테크", ""]
    if categories:
        lines += [f"오늘의 분야: {' · '.join(categories)}", ""]
    lines += ["[에피타이저]"]
    lines += [f"- {it['title']} ({it['url']})" for it in headline_items]
    lines += ["", "[메인]"]
    lines += [f"- {it['title']} ({it['url']})" for it in main_items]
    lines += ["", "오늘 브리핑은 여기까지입니다. — 푸디 드림"]
    return "\n".join(lines)
