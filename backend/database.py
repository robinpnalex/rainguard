"""SQLAlchemy engine/session setup. SQLite, single file, no server needed."""
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from config import DATABASE_URL

engine = create_engine(
    DATABASE_URL,
    # SQLite + FastAPI's threadpool need this; harmless for a prototype.
    connect_args={"check_same_thread": False},
)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


class Base(DeclarativeBase):
    pass


def get_db():
    """FastAPI dependency: one session per request."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    import models  # noqa: F401  (registers the tables on Base)

    Base.metadata.create_all(bind=engine)
