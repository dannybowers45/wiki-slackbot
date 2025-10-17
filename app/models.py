from sqlmodel import SQLModel, Field
from typing import Optional
from datetime import datetime

class QARequest(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    team_id: str
    channel_id: str
    user_id: str
    question: str
    answer: str
    citations_json: str
    thread_ts: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
