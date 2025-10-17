from datetime import datetime
from typing import Optional, List
from sqlmodel import SQLModel, Field, Relationship
from pydantic import BaseModel


class InstallationBase(SQLModel):
    team_id: str = Field(index=True)
    team_name: str
    bot_user_id: str
    bot_token: str
    access_token: str
    scope: str
    user_id: str
    is_active: bool = Field(default=True)


class Installation(InstallationBase, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    
    # Relationships
    qa_requests: List["QARequest"] = Relationship(back_populates="installation")


class QARequestBase(SQLModel):
    question: str
    answer: str
    citations: str  # JSON string of citations
    user_id: str
    channel_id: str
    thread_ts: Optional[str] = None
    conversation_id: Optional[str] = None


class QARequest(QARequestBase, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    installation_id: int = Field(foreign_key="installation.id")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    
    # Relationships
    installation: Installation = Relationship(back_populates="qa_requests")


class ConversationStateBase(SQLModel):
    conversation_id: str = Field(index=True)
    context: str  # JSON string of conversation context
    last_updated: datetime = Field(default_factory=datetime.utcnow)


class ConversationState(ConversationStateBase, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    installation_id: int = Field(foreign_key="installation.id")


# Pydantic models for API responses
class QARequestResponse(BaseModel):
    id: int
    question: str
    answer: str
    citations: str
    user_id: str
    channel_id: str
    thread_ts: Optional[str]
    conversation_id: Optional[str]
    created_at: datetime


class InstallationResponse(BaseModel):
    id: int
    team_id: str
    team_name: str
    bot_user_id: str
    is_active: bool
    created_at: datetime
