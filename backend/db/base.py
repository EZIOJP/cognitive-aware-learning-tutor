from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker
from sqlalchemy.pool import NullPool

from backend.config import get_settings


class Base(DeclarativeBase):
    pass


_settings = get_settings()
_engine_kwargs: dict = {}
if _settings.database_url.startswith("sqlite"):
    # NullPool: API + desktop tracker share one SQLite file. QueuePool (default)
    # exhausts under concurrent gate/WS load and makes /health hang for 30s.
    _engine_kwargs["connect_args"] = {"check_same_thread": False}
    _engine_kwargs["poolclass"] = NullPool
engine = create_engine(_settings.database_url, **_engine_kwargs)
if _settings.database_url.startswith("sqlite"):
    from backend.db.sqlite_utils import configure_sqlite_engine

    configure_sqlite_engine(engine)
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)


def init_db() -> None:
    """
    Deprecated — schema changes must go through Alembic only.
    Raises if called so models cannot drift from migrations.
    """
    raise RuntimeError(
        "init_db()/create_all() is disabled. Apply schema with: python -m alembic upgrade head"
    )
