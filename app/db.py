from sqlmodel import SQLModel, create_engine
from sqlalchemy.pool import QueuePool
import os

DATABASE_URL = os.environ["DATABASE_URL"]  # fail fast if missing

engine = create_engine(
    DATABASE_URL,
    poolclass=QueuePool,
    pool_pre_ping=True,
    pool_size=5,
    max_overflow=5,
    pool_recycle=1800,
)

def init_db():
    from . import models  # ensure models are imported
    SQLModel.metadata.create_all(engine)
