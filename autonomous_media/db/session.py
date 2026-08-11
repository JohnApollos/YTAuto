from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from autonomous_media.config import settings

engine = create_engine(settings.database_url, pool_pre_ping=True)

# Context-manager-compatible session factory
# Usage: with SessionLocal() as session: ...
SessionLocal = sessionmaker(
    bind=engine,
    class_=Session,
    autocommit=False,
    autoflush=False,
    expire_on_commit=False,
)

_db_initialized = False

def init_db():
    """Ensure all SQLAlchemy tables exist in Postgres DB safely and idempotently."""
    global _db_initialized
    if _db_initialized:
        return
    try:
        from autonomous_media.db.base import Base
        import autonomous_media.db.models  # noqa
        Base.metadata.create_all(bind=engine, checkfirst=True)
        _db_initialized = True
    except Exception:
        pass

# Auto-initialize database tables on import
init_db()

def get_db():
    """FastAPI dependency — yields a session and closes on exit."""
    with SessionLocal() as session:
        yield session
