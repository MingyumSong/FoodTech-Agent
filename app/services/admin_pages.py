"""관리자 탭 페이지 (T-012) — 회원관리 · 인기분야 · 발송검토. 서버 렌더 HTML.

인증은 라우트(require_admin_basic)에서. 회원 관리 탭은 관리 목적상 PII를 화면에 표시하되
로그·커밋엔 남기지 않는다(C6). 팔레트·바 렌더는 현황판(admin_status)과 통일.
"""

import html
from collections import Counter
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import func
from sqlmodel import Session, col, select

from app.models.engagement_event import EngagementEvent
from app.models.member import Member
from app.models.member_program import MemberProgram
from app.models.news_item import NewsItem
from app.models.newsletter import Newsletter
from app.models.send_log import SendLog
from app.services.admin_status import (
    ACCENT,
    BG,
    FONT,
    GRAY,
    GRAY_SOFT,
    INK,
    LINE,
    _bar_rows,
)
from app.services.dwell import (
    BOUNCE_SECONDS,
    ENGAGED_SECONDS,
    MAX_GAP_SECONDS,
    collect_dwell_stats,
    format_seconds,
)
from app.services.newsletter import _recipients
from app.services.newsletter_template import CATEGORY_LABELS_KO
from app.services.pilot_daily import PILOT_PROGRAM, _todays_pilot_newsletter
from app.services.send_settings import SendSettings, get_send_settings

PER_PAGE = 40
_TABS = [
    ("/admin/status", "현황"),
    ("/admin/members", "회원 관리"),
    ("/admin/popular", "인기 분야"),
    ("/admin/review", "발송 검토"),
]

# 반복되는 인라인 스타일 — 줄 길이·중복을 줄이려고 상수화
_FIELD = f"padding:7px 9px;border:1px solid {LINE};border-radius:8px;font-size:13px;"
_INPUT = _FIELD + "margin:0 6px 6px 0;"
_BTN = (
    f"padding:7px 16px;background:{ACCENT};color:#FFF;border:0;border-radius:8px;"
    "font-size:13px;font-weight:700;cursor:pointer;"
)
_CARD = f"background:#FFF;border:1px solid {LINE};border-radius:12px;"


def _esc(s: Any) -> str:
    return html.escape(str(s)) if s is not None else ""


def _nav(active: str) -> str:
    links = []
    for href, label in _TABS:
        on = href == active
        color = f"background:{ACCENT};color:#FFF;" if on else f"color:{GRAY};background:#FFF;"
        style = (
            "padding:8px 14px;border-radius:8px;font-size:13.5px;font-weight:700;"
            "text-decoration:none;margin-right:6px;" + color
        )
        links.append(f'<a href="{href}" style="{style}">{label}</a>')
    return f'<div style="margin-bottom:20px;">{"".join(links)}</div>'


def _shell(active: str, inner: str) -> str:
    head = (
        '<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
    )
    title = (
        f'<div style="font-size:22px;font-weight:800;color:{ACCENT};margin-bottom:14px;">'
        f'FoodTech Hub <span style="color:{INK};">관리자</span></div>'
    )
    return (
        f'<!DOCTYPE html><html lang="ko"><head>{head}</head>'
        f'<body style="margin:0;background:{BG};font-family:{FONT};color:{INK};">'
        f'<div style="max-width:860px;margin:0 auto;padding:26px 16px;">'
        f"{title}{_nav(active)}{inner}</div></body></html>"
    )


# ------------------------------------------------------------------ 탭 1: 회원 관리


def collect_members_page(
    session: Session,
    *,
    program: str | None,
    category: str | None,
    q: str | None,
    page: int,
) -> dict[str, Any]:
    programs = list(
        session.exec(
            select(MemberProgram.program).distinct().order_by(col(MemberProgram.program))
        ).all()
    )
    categories = list(
        session.exec(
            select(Member.category)
            .distinct()
            .where(col(Member.category).is_not(None))
            .order_by(col(Member.category))
        ).all()
    )

    base = select(Member)
    if program:
        ids = select(MemberProgram.member_id).where(MemberProgram.program == program)
        base = base.where(col(Member.id).in_(ids))
    if category:
        base = base.where(Member.category == category)
    if q:
        like = f"%{q}%"
        base = base.where(col(Member.name).ilike(like) | col(Member.email).ilike(like))

    total = session.exec(select(func.count()).select_from(base.subquery())).one()
    members = list(
        session.exec(base.order_by(col(Member.id)).limit(PER_PAGE).offset(page * PER_PAGE)).all()
    )
    return {
        "programs": programs,
        "categories": categories,
        "members": members,
        "total": total,
        "page": page,
        "program": program or "",
        "category": category or "",
        "q": q or "",
    }


def _sel(name: str, current: str, options: list[str], placeholder: str) -> str:
    opts = [f'<option value="">{placeholder}</option>']
    for o in options:
        picked = " selected" if o == current else ""
        opts.append(f'<option value="{_esc(o)}"{picked}>{_esc(o)}</option>')
    style = f"padding:7px 9px;border:1px solid {LINE};border-radius:8px;font-size:13px;"
    return f'<select name="{name}" style="{style}">{"".join(opts)}</select>'


def _text_input(name: str, placeholder: str, *, required: bool = False) -> str:
    req = " required" if required else ""
    return f'<input name="{name}" placeholder="{placeholder}"{req} style="{_INPUT}">'


def _add_form(programs: list[str]) -> str:
    prog_opts = "".join(f'<option value="{_esc(p)}">{_esc(p)}</option>' for p in programs)
    prog_sel = (
        f'<select name="program" style="{_INPUT}">'
        f'<option value="">프로그램 없음</option>{prog_opts}</select>'
    )
    fields = (
        _text_input("name", "이름*", required=True)
        + _text_input("email", "이메일")
        + _text_input("category", "구분(기업/개인 등)")
        + _text_input("organization", "소속")
        + _text_input("position", "직위")
        + prog_sel
    )
    return (
        f'<form method="post" action="/admin/members" style="{_CARD}padding:14px 16px;'
        f'margin-bottom:16px;">'
        f'<div style="font-size:13px;font-weight:800;color:{INK};margin-bottom:8px;">'
        f"회원 직접 추가</div>{fields}"
        f'<button type="submit" style="{_BTN}">추가</button></form>'
    )


def _member_row(m: Member) -> str:
    sub = "✅" if m.subscribed else "🚫"
    del_btn = (
        "padding:3px 8px;background:#FCE8E8;color:#B42318;border:0;border-radius:6px;"
        "font-size:11.5px;cursor:pointer;"
    )
    del_form = (
        f'<form method="post" action="/admin/members/{m.id}/delete" style="margin:0;" '
        f"onsubmit=\"return confirm('{_esc(m.name)} 회원을 삭제할까요?');\">"
        f'<button type="submit" style="{del_btn}">삭제</button></form>'
    )
    return (
        f'<tr style="border-top:1px solid {LINE};font-size:12.5px;color:{INK};">'
        f'<td style="padding:6px 8px;">{_esc(m.name)}</td>'
        f"<td>{_esc(m.email)}</td><td>{_esc(m.category)}</td>"
        f"<td>{_esc(m.organization)}</td><td>{_esc(m.position)}</td>"
        f'<td style="text-align:center;">{sub}</td><td>{del_form}</td></tr>'
    )


def _pager(page: int, total: int, qs: str) -> str:
    start = page * PER_PAGE
    prev = (
        f'<a href="/admin/members?{qs}&page={page - 1}" style="color:{ACCENT};">← 이전</a>'
        if page > 0
        else f'<span style="color:{GRAY_SOFT};">← 이전</span>'
    )
    nxt = (
        f'<a href="/admin/members?{qs}&page={page + 1}" style="color:{ACCENT};">다음 →</a>'
        if start + PER_PAGE < total
        else f'<span style="color:{GRAY_SOFT};">다음 →</span>'
    )
    return (
        f'<div style="font-size:12.5px;color:{GRAY};margin-top:10px;">'
        f"총 {total:,}명 · {start + 1}–{min(start + PER_PAGE, total)} · "
        f"{prev} &nbsp; {nxt}</div>"
    )


def render_members_page(data: dict[str, Any]) -> str:
    programs = data["programs"]
    search = (
        f'<input name="q" value="{_esc(data["q"])}" '
        f'placeholder="이름·이메일 검색" style="{_FIELD}">'
    )
    filt = (
        '<form method="get" action="/admin/members" style="margin-bottom:14px;">'
        f"{_sel('program', data['program'], programs, '프로그램 전체')} "
        f"{_sel('category', data['category'], data['categories'], '구분 전체')} "
        f'{search} <button type="submit" style="{_BTN}">필터</button></form>'
    )
    header = (
        f'<tr style="text-align:left;color:{GRAY_SOFT};font-size:11.5px;">'
        f"<th style='padding:6px 8px;'>이름</th><th>이메일</th><th>구분</th><th>소속</th>"
        f"<th>직위</th><th>구독</th><th></th></tr>"
    )
    rows = "".join(_member_row(m) for m in data["members"]) or (
        f'<tr><td colspan="7" style="padding:14px 8px;color:{GRAY_SOFT};font-size:13px;">'
        "조건에 맞는 회원이 없습니다.</td></tr>"
    )
    table = (
        f'<div style="{_CARD}padding:8px 12px;overflow-x:auto;">'
        f'<table width="100%" cellspacing="0" cellpadding="0">{header}{rows}</table></div>'
    )
    qs = f"program={_esc(data['program'])}&category={_esc(data['category'])}&q={_esc(data['q'])}"
    inner = filt + _add_form(programs) + table + _pager(data["page"], data["total"], qs)
    return _shell("/admin/members", inner)


# ------------------------------------------------------------------ 탭 2: 인기 분야


def collect_popular(session: Session, *, days: int = 7) -> dict[str, Any]:
    cutoff = datetime.now(UTC) - timedelta(days=days)
    urls = session.exec(
        select(EngagementEvent.url).where(
            EngagementEvent.event_type == "clicked",
            col(EngagementEvent.occurred_at) >= cutoff,
            col(EngagementEvent.url).is_not(None),
        )
    ).all()
    news_cat = dict(session.exec(select(NewsItem.url, NewsItem.category)).all())
    counter: Counter[str] = Counter()
    for u in urls:
        cat = news_cat.get(u or "")
        if cat:
            counter[cat] += 1
    return {
        "days": days,
        "ranked": counter.most_common(),
        "clicks_total": len(urls),
        "matched": sum(counter.values()),
        "dwell": collect_dwell_stats(session, days=days),
    }


def _dwell_card(d: dict[str, Any]) -> str:
    """읽은 깊이(추정) — 연속 클릭 간격 (T-015).

    표본이 왜 줄었는지를 숫자와 함께 보여준다. 측정 가능 표본만 크게 띄우면
    "클릭 128건을 다 쟀다"로 읽혀서 지표를 과신하게 된다.
    """
    if not d["measurable"]:
        body = (
            f'<div style="font-size:13px;color:{GRAY_SOFT};padding:6px 0;line-height:1.7;">'
            "아직 잴 수 있는 간격이 없습니다 — 한 사람이 <b>한 편에서 두 번 이상</b> 눌러야 "
            "그 사이 시간을 읽은 시간으로 볼 수 있습니다.</div>"
        )
    else:
        rows = [
            ("🤔 정독", d["engaged"], f"{ENGAGED_SECONDS}초 이상 안 돌아옴"),
            ("· 중간", d["middle"], f"{BOUNCE_SECONDS}~{ENGAGED_SECONDS}초"),
            ("💨 튕김", d["bounce"], f"{BOUNCE_SECONDS}초 안에 다음 기사"),
        ]
        bars = _bar_rows(
            [(label, n) for label, n, _ in rows],
            d["measurable"],
            {label: f"{label}  ({note})" for label, _, note in rows},
        )
        body = (
            f'<div style="font-size:22px;font-weight:800;color:{ACCENT};margin:2px 0 12px;">'
            f"중앙값 {format_seconds(d['median_seconds'])}</div>{bars}"
        )

    caveat = (
        f"클릭 {d['clicks_total']}건 중 <b>{d['measurable']}건만 측정 가능</b> — "
        f"각 사람의 편별 마지막 클릭 {d['unmeasurable_last']}건은 다음 클릭이 없어 잴 수 없고, "
        f"{d['over_cap']}건은 간격이 {MAX_GAP_SECONDS // 60}분을 넘어 제외했습니다."
    )
    note = (
        "원문 기사 페이지의 실제 체류는 측정할 수 없습니다(남의 서버). "
        "이건 <b>다음 기사를 누르기까지 걸린 시간</b>이며, 정밀 지표가 아니라 상대 비교용입니다."
    )
    return (
        f'<div style="{_CARD}padding:20px 22px;margin-top:16px;">'
        f'<div style="font-size:16px;font-weight:800;color:{INK};">읽은 깊이 (추정)</div>'
        f'<div style="font-size:12px;color:{GRAY_SOFT};margin:2px 0 14px;line-height:1.7;">'
        f"{caveat}</div>{body}"
        f'<div style="font-size:11.5px;color:{GRAY_SOFT};margin-top:14px;line-height:1.7;'
        f'border-top:1px solid {LINE};padding-top:10px;">{note}</div></div>'
    )


def render_popular_page(data: dict[str, Any]) -> str:
    matched = data["matched"]
    if data["ranked"]:
        bars = _bar_rows(data["ranked"], matched, CATEGORY_LABELS_KO)
    else:
        bars = (
            f'<div style="font-size:13px;color:{GRAY_SOFT};padding:6px 0;">'
            "아직 집계할 클릭이 없습니다 — 발송·추적이 쌓이면 채워집니다.</div>"
        )
    meta = (
        f"클릭 {data['clicks_total']:,}건 중 분야 매칭 {matched:,}건 · 개인정보는 표시하지 않습니다"
    )
    inner = (
        f'<div style="{_CARD}padding:20px 22px;">'
        f'<div style="font-size:16px;font-weight:800;color:{INK};">'
        f"최근 {data['days']}일 인기 분야</div>"
        f'<div style="font-size:12px;color:{GRAY_SOFT};margin:2px 0 14px;">{meta}</div>'
        f"{bars}</div>" + _dwell_card(data["dwell"])
    )
    return _shell("/admin/popular", inner)


# ------------------------------------------------------------------ 탭 4: 발송 검토


def collect_review(session: Session) -> dict[str, Any]:
    nl = _todays_pilot_newsletter(session)
    recipients = len(_recipients(session, PILOT_PROGRAM))
    already_sent = 0
    if nl is not None:
        already_sent = session.exec(
            select(func.count())
            .select_from(SendLog)
            .where(SendLog.newsletter_id == nl.id, SendLog.status == "sent")
        ).one()
    return {
        "newsletter": nl,
        "recipients": recipients,
        "already_sent": already_sent,
        "settings": get_send_settings(session),
    }


def _num_field(name: str, label: str, value: int) -> str:
    style = f"width:56px;padding:6px 8px;border:1px solid {LINE};border-radius:8px;font-size:13px;"
    return (
        f'<label style="font-size:12.5px;color:{GRAY};margin-right:14px;'
        'display:inline-block;margin-bottom:6px;">'
        f'{label} <input type="number" name="{name}" value="{value}" style="{style}"></label>'
    )


def _settings_form(cfg: SendSettings) -> str:
    """발송 조립 설정 폼 (T-014) — 배포 없이 꼭지 수·비율을 바꾼다."""
    fields = (
        _num_field("n_headlines", "에피타이저", cfg.n_headlines)
        + _num_field("n_mains", "메인", cfg.n_mains)
        + _num_field("n_domestic", "국내", cfg.n_domestic)
        + _num_field("n_overseas", "해외", cfg.n_overseas)
        + _num_field("days", "최근 일수", cfg.days)
    )
    note = (
        f"에피타이저+메인({cfg.total})과 국내+해외({cfg.n_domestic + cfg.n_overseas})의 합이 "
        "같아야 저장됩니다. 저장해도 이미 조립된 오늘 편에는 반영되지 않습니다 — 다시 조립하세요."
    )
    return (
        f'<form method="post" action="/admin/review/settings" style="{_CARD}padding:16px 18px;'
        'margin-bottom:16px;">'
        f'<div style="font-size:13px;font-weight:800;color:{INK};margin-bottom:10px;">'
        "발송 구성</div>"
        f"{fields}"
        f'<div style="font-size:11.5px;color:{GRAY_SOFT};margin:4px 0 12px;line-height:1.6;">'
        f"{note}</div>"
        f'<button type="submit" style="{_BTN}">설정 저장</button></form>'
    )


def _review_empty(recipients: int, cfg: SendSettings) -> str:
    note = (
        f"수신자 {recipients}명 · 조립하면 최근 {cfg.days}일 뉴스로 오늘 편을 만듭니다 "
        f"(게이트 통과분 국내{cfg.n_domestic}:해외{cfg.n_overseas})."
    )
    btn = (
        f"padding:9px 18px;background:{ACCENT};color:#FFF;border:0;border-radius:8px;"
        "font-size:13.5px;font-weight:700;cursor:pointer;"
    )
    return _shell(
        "/admin/review",
        _settings_form(cfg) + f'<div style="{_CARD}padding:22px;">'
        f'<div style="font-size:15px;font-weight:700;color:{INK};">'
        "오늘의 파일럿 편이 아직 없습니다</div>"
        f'<div style="font-size:13px;color:{GRAY};margin:6px 0 14px;">{note}</div>'
        '<form method="post" action="/admin/review/build" style="margin:0;">'
        f'<button type="submit" style="{btn}">오늘 편 조립</button></form></div>',
    )


def _review_action(recipients: int, sent: bool) -> str:
    if sent:
        return (
            '<span style="padding:9px 18px;background:#E8F5E9;color:#1B7F3B;'
            'border-radius:8px;font-size:13.5px;font-weight:700;">발송 완료</span>'
        )
    guard = recipients == 0 or recipients > 100
    note = (
        f'<div style="font-size:12px;color:#B42318;margin-bottom:8px;">'
        f"수신자 {recipients}명 — 발송 가드(1~100)를 벗어나 발송할 수 없습니다.</div>"
        if guard
        else ""
    )
    disabled = " disabled" if guard else ""
    bg = GRAY_SOFT if guard else ACCENT
    btn = (
        f"padding:9px 18px;background:{bg};color:#FFF;border:0;border-radius:8px;"
        "font-size:13.5px;font-weight:700;cursor:pointer;"
    )
    confirm = f"return confirm('수신자 {recipients}명에게 지금 발송할까요?');"
    return (
        f"{note}"
        f'<form method="post" action="/admin/review/send" style="margin:0;" '
        f'onsubmit="{confirm}">'
        f'<button type="submit"{disabled} style="{btn}">지금 발송</button></form>'
    )


def render_review_page(data: dict[str, Any]) -> str:
    nl: Newsletter | None = data["newsletter"]
    recipients, already_sent = data["recipients"], data["already_sent"]
    cfg: SendSettings = data["settings"]
    if nl is None:
        return _review_empty(recipients, cfg)

    sent = nl.status == "sent" or already_sent >= recipients > 0
    preview = (
        '<a href="/admin/review/preview" target="_blank" '
        f'style="color:{ACCENT};">미리보기 열기 ↗</a>'
    )
    status_line = f"상태: {_esc(nl.status)} · 발송 {already_sent}/{recipients} · {preview}"
    inner = (
        _settings_form(cfg) + f'<div style="{_CARD}padding:22px;">'
        f'<div style="font-size:12px;color:{GRAY_SOFT};">오늘의 파일럿 편 (pilot-daily)</div>'
        f'<div style="font-size:16px;font-weight:800;color:{INK};margin:4px 0 8px;">'
        f"{_esc(nl.subject)}</div>"
        f'<div style="font-size:12.5px;color:{GRAY};margin-bottom:16px;">{status_line}</div>'
        f"{_review_action(recipients, sent)}</div>"
    )
    return _shell("/admin/review", inner)
