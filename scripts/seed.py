"""개발용 시드 데이터. 실행: uv run python scripts/seed.py"""

import random

from sqlmodel import Session, select

from app.db import engine
from app.lib.logger import get_logger
from app.models.member import Member
from app.models.member_program import MemberProgram

logger = get_logger("seed")

PROGRAMS = ["최고책임자과정", "푸드테크학과", "사업화교육", "월드푸드테크협의회"]
SURNAMES = ["김", "이", "박", "최", "정", "송", "강", "조"]
GIVEN = ["민준", "서연", "지훈", "하은", "도윤", "수아", "예준", "지우"]


def seed_members(session: Session, count: int = 30) -> int:
    existing = session.exec(select(Member).limit(1)).first()
    if existing is not None:
        logger.info("members already seeded, skipping")
        return 0
    rng = random.Random(42)
    for i in range(count):
        name = rng.choice(SURNAMES) + rng.choice(GIVEN)
        member = Member(
            name=name,
            email=f"member{i:03d}@example.com",
            subscribed=rng.random() > 0.1,
        )
        session.add(member)
        session.flush()
        assert member.id is not None
        session.add(MemberProgram(member_id=member.id, program=rng.choice(PROGRAMS)))
    session.commit()
    return count


if __name__ == "__main__":
    with Session(engine) as session:
        created = seed_members(session)
    logger.info(f"seeded {created} members")
