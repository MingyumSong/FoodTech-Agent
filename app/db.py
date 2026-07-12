from collections.abc import Iterator

from sqlalchemy import Engine
from sqlmodel import Session, create_engine

from app.config import settings

engine: Engine = create_engine(settings.database_url, pool_pre_ping=True)


def get_session() -> Iterator[Session]:
    with Session(engine) as session:
        yield session
