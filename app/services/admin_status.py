"""파이프라인 현황판 (T-010) — 읽기 전용 통계 수집 + HTML 렌더.

PII(이름·이메일)는 표시하지 않는다 — 집계 숫자만 (C6).
팔레트는 푸디픽 템플릿(newsletter_template)과 동일한 파랑 계열.
"""

from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import func
from sqlmodel import Session, col, select

from app.models.engagement_event import EngagementEvent
from app.models.member import Member
from app.models.member_program import MemberProgram
from app.models.news_item import NewsItem
from app.models.newsletter import Newsletter
from app.services.newsletter_template import CATEGORY_LABELS_KO

ACCENT = "#1F6FB2"
ACCENT_SOFT = "#E4EFF8"
INK = "#16181D"
GRAY = "#4B5563"
GRAY_SOFT = "#9CA3AF"
LINE = "#E5E7EB"
BG = "#F2F5F9"
FONT = "'Apple SD Gothic Neo','Malgun Gothic','Segoe UI',sans-serif"


def collect_stats(session: Session) -> dict[str, Any]:
    now = datetime.now(UTC)
    day_ago = now - timedelta(hours=24)

    members_total = session.exec(select(func.count()).select_from(Member)).one()
    members_subscribed = session.exec(
        select(func.count()).select_from(Member).where(Member.subscribed == True)  # noqa: E712
    ).one()
    programs = session.exec(
        select(MemberProgram.program, func.count())
        .group_by(col(MemberProgram.program))
        .order_by(func.count().desc())
    ).all()

    news_total = session.exec(select(func.count()).select_from(NewsItem)).one()
    news_24h = session.exec(
        select(func.count()).select_from(NewsItem).where(col(NewsItem.collected_at) >= day_ago)
    ).one()
    news_latest = session.exec(select(func.max(NewsItem.collected_at))).one()
    categories = session.exec(
        select(NewsItem.category, func.count())
        .group_by(col(NewsItem.category))
        .order_by(func.count().desc())
    ).all()

    newsletters = session.exec(
        select(Newsletter).order_by(col(Newsletter.id).desc()).limit(5)
    ).all()

    events = session.exec(
        select(EngagementEvent.event_type, func.count())
        .group_by(col(EngagementEvent.event_type))
        .order_by(func.count().desc())
    ).all()
    events_linked = session.exec(
        select(func.count())
        .select_from(EngagementEvent)
        .where(col(EngagementEvent.member_id).is_not(None))
    ).one()
    events_total = sum(c for _, c in events)

    return {
        "generated_at": now,
        "members": {"total": members_total, "subscribed": members_subscribed, "programs": programs},
        "news": {
            "total": news_total,
            "last_24h": news_24h,
            "latest_at": news_latest,
            "categories": categories,
        },
        "newsletters": newsletters,
        "engagement": {"by_type": events, "total": events_total, "linked": events_linked},
    }


def _card(step: str, title: str, live: bool, body: str) -> str:
    badge = (
        f'<span style="background:{ACCENT};color:#FFF;border-radius:4px;padding:3px 8px;'
        f'font-size:11px;font-weight:700;">{step}</span>'
    )
    dot = "🟢" if live else "⚪"
    return f"""<div style="background:#FFF;border:1px solid {LINE};border-radius:12px;
     padding:20px 22px;margin-bottom:14px;">
  <div style="margin-bottom:12px;">{badge}
    <span style="font-size:16px;font-weight:800;color:{INK};margin-left:6px;">{title}</span>
    <span style="float:right;font-size:13px;">{dot} {"가동 중" if live else "미구현"}</span>
  </div>
  {body}
</div>"""


def _big(value: str, label: str) -> str:
    return (
        f'<td style="padding:4px 18px 4px 0;"><div style="font-size:26px;font-weight:800;'
        f'color:{ACCENT};">{value}</div>'
        f'<div style="font-size:12px;color:{GRAY_SOFT};">{label}</div></td>'
    )


def _bar_rows(pairs: list[tuple[str, int]], total: int, label_map: dict[str, str]) -> str:
    rows = []
    for key, count in pairs:
        pct = int(count / total * 100) if total else 0
        label = label_map.get(key, key)
        rows.append(
            f'<tr><td style="font-size:12.5px;color:{GRAY};padding:2px 10px 2px 0;'
            f'white-space:nowrap;">{label}</td>'
            f'<td style="width:100%;"><div style="background:{ACCENT_SOFT};border-radius:4px;">'
            f'<div style="background:{ACCENT};height:8px;border-radius:4px;'
            f'width:{max(pct, 2)}%;"></div></div></td>'
            f'<td style="font-size:12px;color:{GRAY_SOFT};padding-left:8px;">{count}</td></tr>'
        )
    return f'<table width="100%" cellpadding="0" cellspacing="2">{"".join(rows)}</table>'


def render_status(stats: dict[str, Any]) -> str:
    m = stats["members"]
    n = stats["news"]
    e = stats["engagement"]

    programs_html = _bar_rows(list(m["programs"])[:5], m["total"], {})
    categories_html = _bar_rows(list(n["categories"]), n["total"], CATEGORY_LABELS_KO)
    latest = n["latest_at"].astimezone(UTC).strftime("%m-%d %H:%M UTC") if n["latest_at"] else "—"

    nl_rows = (
        "".join(
            f'<tr><td style="font-size:13px;color:{INK};padding:4px 10px 4px 0;">'
            f"{nl.subject[:44]}</td>"
            f'<td style="font-size:12px;color:{GRAY_SOFT};white-space:nowrap;">'
            f"{nl.status} · {nl.sent_count}/{nl.total_recipients}</td></tr>"
            for nl in stats["newsletters"]
        )
        or f'<tr><td style="font-size:13px;color:{GRAY_SOFT};">발송 이력 없음</td></tr>'
    )

    ev_html = _bar_rows(list(e["by_type"]), e["total"], {})

    body = f"""<!DOCTYPE html><html lang="ko">
<body style="margin:0;background:{BG};font-family:{FONT};color:{INK};">
<div style="max-width:720px;margin:0 auto;padding:30px 16px;">
  <div style="margin-bottom:20px;">
    <div style="font-size:24px;font-weight:800;color:{ACCENT};">FoodTech Hub
      <span style="color:{INK};">파이프라인 현황</span></div>
    <div style="font-size:12.5px;color:{GRAY_SOFT};">읽기 전용 ·
      {stats["generated_at"].strftime("%Y-%m-%d %H:%M UTC")} 기준</div>
  </div>

  {
        _card(
            "①",
            "회원",
            True,
            f'''<table cellpadding="0" cellspacing="0"><tr>
      {_big(f"{m['total']:,}", "총 회원")}
      {_big(f"{m['subscribed']:,}", "구독 중")}
    </tr></table>
    <div style="font-size:12px;color:{GRAY_SOFT};margin:10px 0 4px;">프로그램별</div>
    {programs_html}''',
        )
    }

  {
        _card(
            "③",
            "뉴스 수집·분류",
            True,
            f'''<table cellpadding="0" cellspacing="0"><tr>
      {_big(f"{n['total']:,}", "누적 기사")}
      {_big(f"{n['last_24h']:,}", "최근 24시간")}
      {_big(latest, "마지막 수집")}
    </tr></table>
    <div style="font-size:12px;color:{GRAY_SOFT};margin:10px 0 4px;">카테고리 분포 (11종)</div>
    {categories_html}''',
        )
    }

  {
        _card(
            "④",
            "뉴스레터 발송",
            True,
            f'<table width="100%" cellpadding="0" cellspacing="0">{nl_rows}</table>',
        )
    }

  {
        _card(
            "⑤",
            "참여 추적",
            True,
            f'''<table cellpadding="0" cellspacing="0"><tr>
      {_big(f"{e['total']:,}", "누적 이벤트")}
      {_big(f"{e['linked']:,}", "회원 연결됨")}
    </tr></table>
    <div style="height:8px;"></div>{ev_html}''',
        )
    }

  {
        _card(
            "⑥",
            "Activity Score",
            False,
            f'''<div style="font-size:13px;color:{GRAY};">
    파일럿 발송 데이터가 쌓이면 열람&lt;클릭&lt;전달 가중합으로 산출 예정 (결정 5).
    추적 데이터는 이미 회원 단위로 적재 중.</div>''',
        )
    }

  <div style="font-size:11.5px;color:{GRAY_SOFT};margin-top:8px;">
    ②(세그먼트 선택)는 발송 시 target_filter로 동작 · 개인정보는 표시하지 않습니다</div>
</div>
</body></html>"""
    return body
