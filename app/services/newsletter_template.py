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
# 흰 배경 위 11~12px 글자에 쓰는 색이라 대비를 4.5:1 위로 올렸다(#8A93A6는 3.1:1이었다).
# 연한 회색은 "깔끔해 보이는" 대신 출처·날짜를 못 읽게 만든다.
GRAY_SOFT = "#6E7689"
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
        f"background:{BRAND};color:#FFFFFF;" if solid else f"background:{BRAND_SOFT};color:{BRAND};"
    )
    # 모서리를 2px로 — 둥근 알약 칩은 화면 UI 언어라 지면에선 붕 뜬다.
    return (
        f'<span style="{style}border-radius:2px;padding:3px 8px;'
        f'font-size:11px;font-weight:700;">{_esc(label)}</span>'
    )


def _meta_row(item: dict[str, Any], *, solid_chip: bool) -> str:
    """분야 칩 + 출처. **본문과 같은 글꼴을 쓴다** — 여기에 모노스페이스를 쓰면
    메일이 콘솔 출력처럼 보인다(발행물이 아니라)."""
    return (
        f'<div style="margin-bottom:6px;">{_chip(item, solid=solid_chip)}'
        f'<span style="font-size:11.5px;color:{GRAY_SOFT};">'
        f"&nbsp;&nbsp;{_esc(_source_line(item))}</span></div>"
    )


def _section_label(name: str) -> str:
    """코너 이름 한 줄. 골드 세로줄이 대시보드의 액센트를 그대로 옮긴 자리다.

    번호(`01`)와 설명(`가볍게 훑는 2`)을 뺐다 — 코너가 셋뿐이라 번호가 정보를 더하지 않고,
    "깊이 보는 3" 같은 자기 설명은 지면을 부풀리기만 한다.
    """
    return (
        f'<div style="margin:30px 0 6px;padding-left:11px;border-left:3px solid {GOLD};'
        f'font-size:13px;font-weight:800;color:{NAVY};letter-spacing:.04em;">{_esc(name)}</div>'
    )


def _headline_item(item: dict[str, Any]) -> str:
    """에피타이저 — 메인과 같은 순서(칩 → 제목)로 통일. 코너가 달라도 읽는 순서는 같아야 한다.

    좌측 컬러 레일을 뺐다 — 모든 꼭지에 레일을 두르면 강조가 아니라 배경 무늬가 된다.
    꼭지를 가르는 건 얇은 밑줄 하나면 충분하다(신문 지면의 방식).
    """
    return f"""<table width="100%" cellpadding="0" cellspacing="0">
<tr>
  <td style="padding:13px 0;border-bottom:1px solid {LINE};">
    {_meta_row(item, solid_chip=False)}
    <a href="{item["url"]}" style="color:{INK};font-weight:700;font-size:15.5px;
       text-decoration:none;line-height:1.5;">{_esc(item["title"])}</a>
  </td>
</tr>
</table>"""


def _main_card(item: dict[str, Any], *, summary_limit: int = 170) -> str:
    """메인 — 에피타이저와 같은 지면 위에서 **글자 크기·칩 농도·요약 유무**로만 위계를 만든다.

    연회색 블록과 레일을 뺐다. 배경색으로 강조하면 카드가 넷 다섯 겹치는 순간
    지면 전체가 얼룩덜룩해지고, 그 인상이 "자동 생성물" 느낌의 큰 몫이었다.
    """
    summary = (item.get("summary") or "").strip()
    if len(summary) > summary_limit:
        summary = summary[: summary_limit - 1].rstrip() + "…"
    summary_html = (
        f'<p style="margin:8px 0 0;font-size:13.5px;line-height:1.7;color:{GRAY};">'
        f"{_esc(summary)}</p>"
        if summary
        else ""
    )
    # 지역 구분은 메타 줄의 KR/GLOBAL 라벨이 한다 — 색으로 나누면 해외 기사가 덜 중요해 보였다.
    return f"""<table width="100%" cellpadding="0" cellspacing="0">
<tr>
  <td style="padding:16px 0;border-bottom:1px solid {LINE};">
    {_meta_row(item, solid_chip=True)}
    <a href="{item["url"]}" style="color:{INK};font-weight:800;font-size:17.5px;
       text-decoration:none;line-height:1.4;">{_esc(item["title"])}</a>
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
    return f"""<tr><td style="background:{BLOCK_BG};padding:15px 30px;
  border-bottom:1px solid {LINE};">
  <span style="font-size:11.5px;font-weight:700;color:{GRAY_SOFT};
    letter-spacing:.06em;">오늘의 분야</span>
  <span style="font-size:13px;color:{NAVY};font-weight:600;">&nbsp;&nbsp;{
        _esc(" · ".join(seen))
    }</span>
</td></tr>"""


def _dessert() -> str:
    """디저트 — 원클릭 반응 3버튼. 클릭 한 번이 참여 신호이자 체류 대체 지표가 된다.

    지면에서 유일하게 바탕색을 쓰는 자리다. 골드를 여기 한 번만 쓰면 "눌러야 할 곳"이
    저절로 눈에 든다 — 강조는 아껴 쓸 때만 강조로 남는다.
    """
    buttons = []
    for i, (value, label) in enumerate(REACTIONS):
        style = (
            f"background:{BRAND};color:#FFFFFF;border:1px solid {BRAND};"
            if i == 0
            else f"background:#FFFFFF;color:{NAVY};border:1px solid #D7DEEA;"
        )
        buttons.append(
            f'<a href="{REACTION_BASE_PLACEHOLDER}/{value}" style="display:inline-block;'
            f"{style}border-radius:4px;padding:10px 17px;margin:0 5px 6px 0;"
            f'font-size:13px;font-weight:700;text-decoration:none;">{label}</a>'
        )
    return f"""<table width="100%" cellpadding="0" cellspacing="0"
       style="margin-top:14px;background:{GOLD_SOFT};">
<tr><td style="padding:18px 20px;border-left:3px solid {GOLD};">
  <div style="font-size:14.5px;font-weight:700;color:{NAVY};">오늘 편은 어떠셨나요?</div>
  <div style="font-size:12.5px;color:{GRAY};margin:5px 0 14px;">한 번의 클릭이 다음 편을
    다듬습니다</div>
  {"".join(buttons)}
</td></tr>
</table>"""


def _header(issue_no: int, issue_date: str, icon_url: str | None) -> str:
    icon = (
        f'<img src="{icon_url}" width="77" height="57" alt="" style="display:block;border:0;">'
        if icon_url
        else "&nbsp;"
    )
    # 골드 띠 → 네이비 헤더. 대시보드 히어로의 배색을 그대로 옮긴 자리다.
    # 제호의 체크마크(푸디픽✓)를 뺐다 — 로고가 아니라 글자에 붙인 장식이라 급조한 티가 났다.
    return f"""<tr><td style="background:{NAVY};padding:24px 30px;border-top:3px solid {GOLD};">
  <table width="100%" cellpadding="0" cellspacing="0"><tr>
    <td valign="middle">
      <div style="font-size:11px;font-weight:700;color:{GOLD};
        letter-spacing:.16em;">FOODIE'S PICK</div>
      <div style="font-size:28px;font-weight:800;letter-spacing:-.02em;color:#FFFFFF;
        margin-top:7px;">푸디픽</div>
      <div style="font-size:12px;color:{NAVY_SOFT};margin-top:8px;">
        제{issue_no}호 · {_esc(issue_date.replace("-", "."))} · 푸드테크센터</div>
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

  {_section_label("에피타이저")}
  {headlines}

  {_section_label("메인")}
  {mains}

  {_section_label("디저트")}
  {_dessert()}

  <div style="margin:24px 0 0;font-size:13px;color:{GRAY};line-height:1.65;">
    오늘 픽은 여기까지입니다. 내일 또 차릴게요. — <b style="color:{NAVY};">푸디 드림</b>
  </div>

</td></tr>

<tr><td class="fp-pad" style="padding:22px 30px 26px;">
  <div style="border-top:1px solid {LINE};padding-top:16px;font-size:11.5px;
       color:{GRAY_SOFT};line-height:1.85;">
    푸디픽은 <a href="https://foodtech-center.org" style="color:{BRAND};
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
