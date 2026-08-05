"""파일럿(랩실) 매일발송 자동화 (T-011).

scratchpad 수동 스크립트(build_today→send_today→backfill_pilot)를 앱 서비스로 승격.
설계 요점:
- 전원 동일 1편: pilot-daily 세그먼트 전원이 같은 편을 받는다.
- 일별 분야 회전: 날짜(ordinal)로 분야 우선순위를 회전 → 연속 2일이면 서로 다른 분야 집합.
  콜드스타트에서 회원이 다양한 분야를 보게 해 Activity Score 신호를 고르게 모은다.
- 조립 순서: `_blocked`(비뉴스 도메인) → `curate_dicts`(묶음기사 제외·중복 병합, T-009)
  → `filter_foodtech_relevant`(2차 LLM 게이트) → `select_picks`(분야 distinct·비율).
- 꼭지 수·국내외 비율·기간은 `get_send_settings`(T-014)에서 온다 — 국내4:해외1은 코드 기본값일 뿐
  관리자가 화면에서 바꿀 수 있다.
- 발송은 send_newsletter 재사용(멱등·100명 가드·provider_id 저장) — 잡 트리거만 자동화.
- 통계 롤업: send_logs·engagement_events → pilot_members(멱등 upsert).
"""

from collections import defaultdict
from datetime import UTC, datetime
from typing import Any

import httpx
from sqlmodel import Session, col, select

from app.db import engine
from app.lib.logger import get_logger
from app.models.engagement_event import EngagementEvent
from app.models.member import Member
from app.models.member_program import MemberProgram
from app.models.news_item import NewsItem
from app.models.newsletter import Newsletter
from app.models.pilot_member import PilotMember
from app.models.send_log import SendLog
from app.services.activity_score import score_members
from app.services.curation import curate_dicts
from app.services.news_classify import SLUG_BY_KO, filter_foodtech_relevant, is_non_news_url
from app.services.newsletter import (
    MIN_ITEMS,
    UNSUB_PLACEHOLDER,
    _item_dict,
    _recent_items,
    icon_url,
    send_newsletter,
)
from app.services.newsletter_template import render_foodie_pick, render_text_fallback
from app.services.send_settings import get_send_settings

logger = get_logger("pilot_daily")

PILOT_PROGRAM = "pilot-daily"
DEFAULT_DAYS = 7  # 설정 행이 없을 때의 폴백 (SendSettings.days 기본값과 같아야 함)
# T-013: "국내 기사 위주로" 피드백 반영 — 3:2에서 4:1로. 해외 1건은 메인에 배치해
# 글로벌 흐름을 놓치지 않되 지면 대부분을 국내에 준다.
N_DOMESTIC = 4  # 국내 꼭지 수 (메인2 + 에피타이저2)
N_OVERSEAS = 1  # 해외 꼭지 수 (메인1)
N_MAINS = 3
N_HEADLINES = 2

# 회전 대상 분야 = 정부 10대 분야 슬러그(general 제외), 표준 순서. 날짜로 이 리스트를 회전시킨다.
ROTATION_CATEGORIES = [slug for slug in SLUG_BY_KO.values() if slug != "general"]

# 파일럿 안내 배너 — 아직 시범 단계라 "몇 개만 눌러봐도 된다"는 안내를 유지 (항목 5 디자인 때 정리).
PILOT_BANNER = (
    '<div style="background:#FFF7E6;border:1px solid #FFE1A8;border-radius:8px;'
    'padding:14px 16px;margin:14px 0 4px;font-size:13.5px;color:#8A6D1B;line-height:1.65;">'
    "<b>🧪 시범 운영 중</b><br>"
    "푸드테크센터가 뉴스레터 <b>푸디픽</b>을 시범 운영하고 있습니다. 관심 가는 "
    "<b>기사 제목 몇 개만</b> 눌러봐 주세요 — 전부 누르실 필요는 없습니다. "
    "눌러주신 흔적이 앞으로 뉴스레터를 다듬는 데 큰 도움이 됩니다. 감사합니다!"
    "</div>"
)
_BANNER_ANCHOR = '<tr><td class="fp-pad" style="padding:0 30px;">'


def _blocked(url: str | None) -> bool:
    """비뉴스 도메인 차단 — 수집 단계와 **같은 호스트 기준** 판정을 쓴다 (T-009).

    이전엔 `dom in url` 부분일치라 경로에 도메인 문자열이 들어간 정상 기사도 걸릴 수 있었고,
    수집 단계(`is_non_news_url`)와 판정이 달랐다.
    """
    return is_non_news_url(url or "")


def _take_rotated(
    src: list[dict[str, Any]], n: int, priority: list[str], used: set[str]
) -> list[dict[str, Any]]:
    """회전 우선순위대로 분야마다 1건씩 골라 분야 distinct n건을 만든다.

    src는 최신순 정렬 전제(_recent_items) — 각 분야에서 가장 최신 기사가 뽑힌다.
    used는 이슈 전체(국내+해외)가 공유해 분야가 겹치지 않게 한다.
    부족하면 남은 분야로, 그래도 부족하면 분야 중복이라도 채운다.
    """
    chosen: list[dict[str, Any]] = []
    for cat in priority:  # 1) 회전 순서대로 분야당 최신 1건
        if len(chosen) >= n:
            break
        if cat in used:
            continue
        for it in src:
            if (it.get("category") or "") == cat and it not in chosen:
                chosen.append(it)
                used.add(cat)
                break
    if len(chosen) < n:  # 2) 우선순위에 없던 분야까지 포함해 distinct 채움
        for it in src:
            if len(chosen) >= n:
                break
            c = it.get("category") or ""
            if it not in chosen and c not in used:
                chosen.append(it)
                used.add(c)
    if len(chosen) < n:  # 3) 정말 부족하면 분야 중복이라도 채움(빈 코너 방지)
        for it in src:
            if len(chosen) >= n:
                break
            if it not in chosen:
                chosen.append(it)
    return chosen


def select_picks(
    pool: list[dict[str, Any]],
    day_index: int,
    *,
    n_domestic: int = N_DOMESTIC,
    n_overseas: int = N_OVERSEAS,
    n_mains: int = N_MAINS,
) -> list[dict[str, Any]]:
    """게이트 통과분에서 국내:해외 비율 + 분야 distinct + 일별 회전으로 꼭지 선정.

    day_index = 날짜의 ordinal(toordinal). 이 값으로 분야 우선순위를 회전시켜
    연속한 날이면 서로 다른 분야가 앞에 오게 한다.

    반환 순서 = 메인 → 에피타이저. 기본값 기준으로는
    [메인 국내, 메인 국내, 메인 해외, 에피 국내, 에피 국내].
    개수는 관리자 설정(T-014)이 바꿀 수 있어 인자로 받는다 — 안 넘기면 코드 기본값.
    """
    dom = [it for it in pool if it.get("region") == "domestic"]
    ov = [it for it in pool if it.get("region") == "overseas"]
    offset = day_index % len(ROTATION_CATEGORIES)
    rotated = ROTATION_CATEGORIES[offset:] + ROTATION_CATEGORIES[:offset]

    used: set[str] = set()
    d = _take_rotated(dom, n_domestic, rotated, used)
    o = _take_rotated(ov, n_overseas, rotated, used)
    if len(d) < n_domestic or len(o) < n_overseas:
        raise ValueError(
            f"꼭지 부족 — 국내 {len(d)}/{n_domestic}, 해외 {len(o)}/{n_overseas} "
            "(게이트 통과분이 얇음). 발송 중단."
        )
    # 해외는 메인에 먼저 넣는다 — 국내 위주로 가되(4:1) 글로벌 흐름은 깊이 보는 자리에 둔다.
    # 남는 메인 자리를 국내로 채우고 나머지가 에피타이저. 해외 0건이어도 성립한다.
    n_main_ov = min(n_overseas, n_mains)
    n_main_dom = n_mains - n_main_ov
    return d[:n_main_dom] + o[:n_main_ov] + d[n_main_dom:] + o[n_main_ov:]


def _todays_pilot_newsletter(session: Session) -> Newsletter | None:
    """오늘 만든 pilot-daily 뉴스레터가 있으면 반환(멱등 — 같은 날 재호출 시 재사용)."""
    today_start = datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0)
    cands = session.exec(
        select(Newsletter)
        .where(col(Newsletter.created_at) >= today_start)
        .order_by(col(Newsletter.id).desc())
    ).all()
    for nl in cands:
        if (nl.target_filter or {}).get("program") == PILOT_PROGRAM:
            return nl
    return None


def build_pilot_daily(
    session: Session, *, client: httpx.Client | None = None, days: int | None = None
) -> Newsletter:
    """최근 뉴스로 오늘의 파일럿 편을 조립. 같은 날 편이 있으면 재사용(멱등).

    꼭지 수·국내외 비율·기간은 관리자 설정(T-014)에서 읽는다. 설정 행이 없으면 코드 기본값이라
    마이그레이션 직후에도 그대로 돈다. days를 넘기면 설정보다 우선(테스트·수동 조립용).
    """
    existing = _todays_pilot_newsletter(session)
    if existing is not None:
        logger.info(f"pilot newsletter reused: id={existing.id}")
        return existing

    cfg = get_send_settings(session)
    days = cfg.days if days is None else days

    items = _recent_items(session, days)
    pool = [
        _item_dict(it) for it in items if (it.category or "") != "general" and not _blocked(it.url)
    ]
    # 묶음기사 제외 + 같은 사건 중복 병합 (T-009). 분야 회전(_take_rotated)은 분야가 다르면
    # 중복을 못 막으므로 — 같은 사건이 다른 분야로 분류되는 일이 실제로 있다 — 회전 앞에서
    # 정리해야 한다. LLM 게이트보다도 앞이라 호출 비용도 함께 줄어든다.
    before = len(pool)
    pool = curate_dicts(pool)
    if len(pool) < before:
        logger.info(f"pilot curate: {before} → {len(pool)} (묶음·중복 {before - len(pool)}건 제외)")

    # 꼭지 수를 관리자가 늘렸으면 최소 풀도 그만큼 커야 한다.
    min_items = max(MIN_ITEMS, cfg.total)
    if len(pool) < min_items:
        raise ValueError(f"분야 분류된 최근 뉴스가 {len(pool)}건 — 최소 {min_items}건 필요")

    kept, dropped = filter_foodtech_relevant(pool, client)
    logger.info(f"pilot gate: keep={len(kept)} drop={len(dropped)}")

    day_index = datetime.now(UTC).date().toordinal()
    picks = select_picks(
        kept,
        day_index,
        n_domestic=cfg.n_domestic,
        n_overseas=cfg.n_overseas,
        n_mains=cfg.n_mains,
    )
    mains, headlines = picks[: cfg.n_mains], picks[cfg.n_mains : cfg.total]

    now = datetime.now(UTC)
    issue_no = len(session.exec(select(Newsletter.id)).all())
    top_title = (mains[0].get("title") or "")[:30]

    rendered = render_foodie_pick(
        issue_no=issue_no,
        issue_date=now.strftime("%Y-%m-%d"),
        main_items=mains,
        headline_items=headlines,
        unsubscribe_url=UNSUB_PLACEHOLDER,
        icon_url=icon_url(),
    )
    if _BANNER_ANCHOR not in rendered:
        # 템플릿이 바뀌면 배너가 조용히 사라진다 — 실패로 드러내야 알아챈다.
        raise ValueError("파일럿 배너 삽입 지점을 템플릿에서 찾지 못함 — 앵커 문자열 확인 필요")
    html = rendered.replace(_BANNER_ANCHOR, _BANNER_ANCHOR + PILOT_BANNER, 1)

    newsletter = Newsletter(
        subject=f"푸디픽 #{issue_no:03d} | 오늘의 푸드테크 {cfg.total}선 — {top_title}",
        html_body=html,
        text_body=render_text_fallback(
            main_items=mains,
            headline_items=headlines,
        ),
        target_filter={"program": PILOT_PROGRAM},
        status="draft",
    )
    session.add(newsletter)
    session.commit()
    session.refresh(newsletter)
    logger.info(f"pilot newsletter built: id={newsletter.id} picks={len(picks)}")
    return newsletter


def _group_no_by_member(session: Session) -> dict[int, int]:
    """pilot-lab-N 링크에서 회원별 그룹 번호(있으면). 없으면 비어 있음 — 롤업엔 선택적."""
    out: dict[int, int] = {}
    for link in session.exec(
        select(MemberProgram).where(col(MemberProgram.program).like("pilot-lab-%"))
    ).all():
        try:
            out[link.member_id] = int(link.program.rsplit("-", 1)[-1])
        except ValueError:
            continue
    return out


def refresh_pilot_stats(session: Session) -> dict[str, int]:
    """pilot-daily 회원의 발송·추적을 pilot_members로 멱등 롤업(upsert).

    send_logs(sent) → emails_sent/last_sent_at,
    engagement_events → emails_opened/links_clicked/last_*_at + category_clicks(뉴스 분야별),
    Activity Score(T-017) → activity_score/activity_tier/score_updated_at.

    집계 컬럼은 원시 관측(재열람 포함)을 그대로 담고, 점수는 편당 1회·봇 열람 제외로 따로 센다 —
    화면에서 "열람 22회인데 점수는 낮다"가 보이는 건 의도된 것이다(원시 수는 못 믿는다).
    """
    links = session.exec(select(MemberProgram).where(MemberProgram.program == PILOT_PROGRAM)).all()
    news_cat = dict(session.exec(select(NewsItem.url, NewsItem.category)).all())
    group_by_member = _group_no_by_member(session)
    scored_at = datetime.now(UTC)
    scores = score_members(session, [link.member_id for link in links], now=scored_at)

    created = updated = 0
    for link in links:
        m = session.get(Member, link.member_id)
        if m is None or m.id is None:
            continue

        sent_logs = session.exec(
            select(SendLog).where(SendLog.member_id == m.id, SendLog.status == "sent")
        ).all()
        evs = session.exec(select(EngagementEvent).where(EngagementEvent.member_id == m.id)).all()
        opens = [e for e in evs if e.event_type == "opened"]
        clicks = [e for e in evs if e.event_type == "clicked"]
        cat_clicks: dict[str, int] = defaultdict(int)
        for e in clicks:
            cat = news_cat.get(e.url or "")
            if cat:
                cat_clicks[cat] += 1

        pm = session.exec(select(PilotMember).where(PilotMember.member_id == m.id)).first()
        if pm is None:
            pm = PilotMember(member_id=m.id, name=m.name)
            created += 1
        else:
            updated += 1
        pm.name = m.name
        pm.email = m.email
        pm.position = m.position
        pm.organization = m.organization
        pm.subscribed = m.subscribed
        pm.unsubscribe_token = m.unsubscribe_token
        if m.id in group_by_member:
            pm.group_no = group_by_member[m.id]
        pm.emails_sent = len(sent_logs)
        pm.last_sent_at = max((log.created_at for log in sent_logs), default=None)
        pm.emails_opened = len(opens)
        pm.last_opened_at = max((e.occurred_at for e in opens), default=None)
        pm.links_clicked = len(clicks)
        pm.last_clicked_at = max((e.occurred_at for e in clicks), default=None)
        pm.category_clicks = dict(cat_clicks)
        score = scores.get(m.id)
        if score is not None:
            pm.activity_score = score.score
            pm.activity_tier = score.tier
            pm.score_updated_at = scored_at
        pm.updated_at = datetime.now(UTC)
        session.add(pm)
    session.commit()
    stats = {"members": len(links), "created": created, "updated": updated}
    logger.info(f"pilot stats refreshed: {stats}")
    return stats


def run_pilot_daily(
    session: Session | None = None, client: httpx.Client | None = None
) -> dict[str, Any]:
    """매일발송 잡 본체: 통계 롤업 → 오늘 편 조립 → 발송 → 재롤업. 크론이 트리거한다.

    멱등: 같은 날 재실행해도 편을 재사용하고 send_newsletter가 이미 sent를 스킵한다.
    """
    if session is None:
        with Session(engine) as own:
            return run_pilot_daily(session=own, client=client)
    if client is None:
        with httpx.Client() as own_client:
            return run_pilot_daily(session=session, client=own_client)

    refresh_pilot_stats(session)  # 지난 발송분의 열람·클릭을 먼저 반영
    nl = build_pilot_daily(session, client=client)
    assert nl.id is not None  # commit·refresh 후라 항상 존재
    stats = send_newsletter(nl.id, session=session, client=client)
    refresh_pilot_stats(session)  # 오늘 발송분(emails_sent) 반영
    result = {"newsletter_id": nl.id, **stats}
    logger.info(f"pilot daily send done: {result}")
    return result


def send_reviewed(newsletter_id: int) -> dict[str, Any]:
    """관리자 검토 화면의 [지금 발송]용 — 이미 조립된 편을 발송하고 통계를 롤업(자체 세션).

    run_pilot_daily와 달리 재조립하지 않는다(검토한 그 편을 그대로 보낸다). 멱등: 이미 sent 스킵.
    """
    with Session(engine) as session, httpx.Client() as client:
        stats = send_newsletter(newsletter_id, session=session, client=client)
        refresh_pilot_stats(session)
    logger.info(f"pilot reviewed send done: {stats}")
    return stats
