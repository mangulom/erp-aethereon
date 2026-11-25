from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from .config import get_settings


def _sqlalchemy_database_url(url: str) -> str:
    # Supabase commonly provides postgresql:// URLs. Select the installed
    # Psycopg 3 driver explicitly rather than relying on SQLAlchemy defaults.
    if url.startswith("postgresql+psycopg2://"):
        return url.replace("postgresql+psycopg2://", "postgresql+psycopg://", 1)
    if url.startswith("postgresql+psycopg://"):
        return url
    if url.startswith("postgresql://"):
        return url.replace("postgresql://", "postgresql+psycopg://", 1)
    if url.startswith("postgres://"):
        return url.replace("postgres://", "postgresql+psycopg://", 1)
    return url


database_url = _sqlalchemy_database_url(get_settings().database_url)
is_local = "localhost" in database_url or "127.0.0.1" in database_url
connect_args = {} if is_local else ({"sslmode": "require"} if database_url.startswith("postgresql+") else {})
engine = create_engine(database_url, connect_args=connect_args, pool_pre_ping=True, pool_size=2, max_overflow=1)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
