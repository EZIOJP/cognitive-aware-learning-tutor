from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from backend.config import get_settings


class Base(DeclarativeBase):
    pass


_settings = get_settings()
engine = create_engine(
    _settings.database_url,
    connect_args={"check_same_thread": False} if _settings.database_url.startswith("sqlite") else {},
)
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)


def init_db() -> None:
    """
    Deprecated — schema changes must go through Alembic only.
    Raises if called so models cannot drift from migrations.
    """
    raise RuntimeError(
        "init_db()/create_all() is disabled. Apply schema with: python -m alembic upgrade head"
    )
