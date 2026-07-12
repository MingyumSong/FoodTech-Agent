"""enable row level security on all tables

Revision ID: 099fd24371d6
Revises: 59dda42e7213
Create Date: 2026-07-13 00:08:40.989421

"""

from collections.abc import Sequence

from alembic import op

revision: str = "099fd24371d6"
down_revision: str | None = "59dda42e7213"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# 정책(policy) 없이 RLS만 켠다 = PostgREST 등 비소유자 접근 전면 거부.
# 앱은 테이블 소유자로 접속하므로 영향 없음 (T-002b).
TABLES = [
    "members",
    "member_programs",
    "newsletters",
    "send_logs",
    "engagement_events",
    "alembic_version",
]


def upgrade() -> None:
    for table in TABLES:
        op.execute(f'ALTER TABLE "{table}" ENABLE ROW LEVEL SECURITY')


def downgrade() -> None:
    for table in TABLES:
        op.execute(f'ALTER TABLE "{table}" DISABLE ROW LEVEL SECURITY')
