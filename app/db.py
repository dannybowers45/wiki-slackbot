import os
from urllib.parse import urlparse
from sqlmodel import SQLModel, create_engine, Session
from dotenv import load_dotenv

load_dotenv()


def _build_engine_from_env():
    """Create SQLAlchemy engine supporting SQLite and Postgres."""
    database_url = os.getenv("DATABASE_URL", "sqlite:///./wikipedia_bot.db")

    # Railway often provides a DATABASE_URL starting with postgres:// which SQLAlchemy
    # expects as postgresql+psycopg://. Normalize when necessary.
    if database_url.startswith("postgres://"):
        database_url = database_url.replace("postgres://", "postgresql+psycopg://", 1)
    elif database_url.startswith("postgresql://") and "+" not in database_url:
        database_url = database_url.replace("postgresql://", "postgresql+psycopg://", 1)

    connect_args = {}
    # For SQLite, ensure check_same_thread=False for multi-threaded FastAPI
    if database_url.startswith("sqlite"):
        connect_args = {"check_same_thread": False}

    return create_engine(database_url, echo=False, connect_args=connect_args)


engine = _build_engine_from_env()


def create_db_and_tables():
    """Create database tables"""
    SQLModel.metadata.create_all(engine)


def get_session():
    """Get database session"""
    with Session(engine) as session:
        yield session


def get_db_session():
    """Get database session for direct use"""
    return Session(engine)
