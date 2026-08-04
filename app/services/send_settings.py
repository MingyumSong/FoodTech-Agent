"""발송 조립 설정 — 관리자가 배포 없이 바꾸는 값들 (T-014).

파일럿 동안 "한 편에 몇 꼭지, 국내 몇 대 해외 몇"이 계속 바뀐다. 코드 상수로 두면 실험 주기가
배포 주기에 묶여서 app_settings(key/value)로 뺀다.

설계 요점:
- **행이 없으면 코드 기본값**. 마이그레이션 직후나 설정을 한 번도 저장하지 않은 상태에서도
  발송이 그대로 돌아야 한다.
- 저장 단계에서 검증한다. 조립 시점에 터지면 크론이 조용히 실패하고 그날 발송이 통째로 빠진다.
- 수신자 상한(PILOT_MAX_RECIPIENTS)은 여기 없다 — 결정 4의 안전장치라 코드 상수로 남긴다.
"""

from dataclasses import asdict, dataclass
from datetime import UTC, datetime

from sqlmodel import Session

from app.lib.logger import get_logger
from app.models.app_setting import AppSetting

logger = get_logger("send_settings")

SETTINGS_KEY = "send"

# 상한은 취향이 아니라 안전장치다. 꼭지를 크게 잡으면 게이트 통과분이 모자라 발송이 멈추고,
# 기간을 길게 잡으면 철 지난 기사가 올라온다.
MAX_ITEMS_TOTAL = 12
MAX_DAYS = 30


@dataclass(frozen=True)
class SendSettings:
    n_headlines: int = 2  # 에피타이저
    n_mains: int = 3  # 메인
    n_domestic: int = 4  # 국내 꼭지 수
    n_overseas: int = 1  # 해외 꼭지 수
    days: int = 7  # 최근 며칠 뉴스에서 고를지

    @property
    def total(self) -> int:
        return self.n_headlines + self.n_mains


def validate(s: SendSettings) -> list[str]:
    """설정의 문제를 사람이 읽을 수 있는 문장 목록으로 돌려준다. 비어 있으면 통과."""
    errors: list[str] = []
    if s.n_mains < 1:
        errors.append("메인은 최소 1건이어야 합니다.")
    if s.n_headlines < 0:
        errors.append("에피타이저는 0 이상이어야 합니다.")
    if s.n_domestic < 0 or s.n_overseas < 0:
        errors.append("국내·해외 꼭지 수는 0 이상이어야 합니다.")
    if s.total > MAX_ITEMS_TOTAL:
        errors.append(f"한 편의 꼭지 수는 최대 {MAX_ITEMS_TOTAL}건입니다 (지금 {s.total}건).")
    if s.n_domestic + s.n_overseas != s.total:
        errors.append(
            f"국내({s.n_domestic}) + 해외({s.n_overseas}) = {s.n_domestic + s.n_overseas}인데 "
            f"에피타이저({s.n_headlines}) + 메인({s.n_mains}) = {s.total}입니다. "
            "두 합이 같아야 합니다."
        )
    if not 1 <= s.days <= MAX_DAYS:
        errors.append(f"최근 일수는 1~{MAX_DAYS} 사이여야 합니다.")
    return errors


def get_send_settings(session: Session) -> SendSettings:
    """저장된 설정을 읽는다. 행이 없거나 값이 깨졌으면 코드 기본값으로 돌아간다."""
    row = session.get(AppSetting, SETTINGS_KEY)
    if row is None:
        return SendSettings()
    known = {f: v for f, v in (row.value or {}).items() if f in SendSettings.__dataclass_fields__}
    try:
        settings = SendSettings(**{k: int(v) for k, v in known.items()})
    except (TypeError, ValueError):
        logger.warning("app_settings.send 값이 깨져 기본값으로 폴백")
        return SendSettings()
    if validate(settings):
        # 저장 시 검증하지만 DB를 손으로 고쳤을 수도 있다 — 발송을 멈추느니 기본값으로 돈다.
        logger.warning("app_settings.send 값이 유효하지 않아 기본값으로 폴백")
        return SendSettings()
    return settings


def save_send_settings(session: Session, settings: SendSettings) -> None:
    """설정 저장. 유효하지 않으면 ValueError(사유 전부를 줄바꿈으로 이어붙임)."""
    errors = validate(settings)
    if errors:
        raise ValueError("\n".join(errors))

    row = session.get(AppSetting, SETTINGS_KEY)
    if row is None:
        row = AppSetting(key=SETTINGS_KEY)
    row.value = asdict(settings)
    row.updated_at = datetime.now(UTC)
    session.add(row)
    session.commit()
    logger.info(f"send settings saved: {row.value}")
