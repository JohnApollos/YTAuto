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

def get_db():
    """FastAPI dependency — yields a session and closes on exit."""
    with SessionLocal() as session:
        yield session
