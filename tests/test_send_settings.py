"""발송 조립 설정 (T-014) — 기본값 폴백과 저장 검증.

가장 중요한 계약: **설정 행이 없어도 발송이 돌아야 한다.** 마이그레이션 직후가 그 상태다.
"""

import pytest
from sqlmodel import Session

from app.models.app_setting import AppSetting
from app.services.send_settings import (
    SETTINGS_KEY,
    SendSettings,
    get_send_settings,
    save_send_settings,
    validate,
)


def test_defaults_when_no_row(session: Session):
    """저장된 적 없으면 코드 기본값 — 현재 발송 구성(에피2·메인3·국내4:해외1·7일)."""
    s = get_send_settings(session)
    assert (s.n_headlines, s.n_mains, s.n_domestic, s.n_overseas, s.days) == (2, 3, 4, 1, 7)
    assert s.total == 5


def test_saved_values_round_trip(session: Session):
    saved = SendSettings(n_headlines=3, n_mains=4, n_domestic=6, n_overseas=1, days=10)
    save_send_settings(session, saved)
    assert get_send_settings(session) == saved


def test_region_counts_must_match_corner_counts():
    """국내+해외와 에피+메인의 합이 어긋나면 조립이 불가능하다 — 저장 단계에서 막는다."""
    errors = validate(SendSettings(n_headlines=2, n_mains=3, n_domestic=2, n_overseas=1))
    assert any("같아야 합니다" in e for e in errors)


@pytest.mark.parametrize(
    "kwargs",
    [
        {"n_mains": 0},  # 메인 없는 편은 없다
        {"n_headlines": -1},
        {"n_headlines": 6, "n_mains": 8, "n_domestic": 14, "n_overseas": 0},  # 상한 초과
        {"days": 0},
        {"days": 999},
    ],
)
def test_invalid_settings_are_rejected(session: Session, kwargs):
    bad = SendSettings(**kwargs)
    assert validate(bad)
    with pytest.raises(ValueError):
        save_send_settings(session, bad)


def test_corrupt_row_falls_back_to_defaults(session: Session):
    """DB를 손으로 고쳐 값이 깨져도 발송을 멈추느니 기본값으로 돈다."""
    session.add(AppSetting(key=SETTINGS_KEY, value={"n_mains": "세 개", "days": None}))
    session.commit()
    assert get_send_settings(session) == SendSettings()


def test_row_violating_rules_falls_back_to_defaults(session: Session):
    """형식은 맞지만 규칙에 어긋나는 값(합 불일치)도 기본값으로 폴백."""
    session.add(
        AppSetting(
            key=SETTINGS_KEY,
            value={"n_headlines": 2, "n_mains": 3, "n_domestic": 99, "n_overseas": 0, "days": 7},
        )
    )
    session.commit()
    assert get_send_settings(session) == SendSettings()
