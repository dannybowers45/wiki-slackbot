from datetime import datetime
from typing import Optional, List
from sqlmodel import SQLModel, Field, Relationship
from pydantic import BaseModel


class InstallationBase(SQLModel):
    """
    Shared SQLModel fields describing a Slack app installation.

    These attributes capture workspace identity, bot credentials, and scope
    metadata that are common to both persisted rows and DTOs built on top of
    them.
    """
    team_id: str = Field(index=True)
    team_name: str
    bot_user_id: str
    bot_token: str
    access_token: str
    scope: str
    user_id: str
    is_active: bool = Field(default=True)


class Installation(InstallationBase, table=True):
    """
    Persistence model for Slack installations stored in our database.

    Includes audit timestamps and the ORM relationship to emitted Q&A requests.
    """
    id: Optional[int] = Field(default=None, primary_key=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    
    # Relationships
    qa_requests: List["QARequest"] = Relationship(back_populates="installation")


class QARequestBase(SQLModel):
    """
    Base fields describing a single answered question delivered through Slack.

    Stores the verbatim question, generated answer, serialized citations, and
    identifiers that tie the exchange back to Slack.
    """
    question: str
    answer: str
    citations: str  # JSON string of citations
    user_id: str
    channel_id: str
    thread_ts: Optional[str] = None
    conversation_id: Optional[str] = None


class QARequest(QARequestBase, table=True):
    """
    Database table capturing every Q&A interaction handled by the bot.

    Rows link back to the originating installation to support workspace-level
    analytics and access controls.
    """
    id: Optional[int] = Field(default=None, primary_key=True)
    installation_id: int = Field(foreign_key="installation.id")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    
    # Relationships
    installation: Installation = Relationship(back_populates="qa_requests")


class ConversationStateBase(SQLModel):
    """
    Shared columns for representing persisted conversation context.

    The serialized context blob allows the QA service to resume multi-turn
    conversations with relevant history.
    """
    conversation_id: str = Field(index=True)
    context: str  # JSON string of conversation context
    last_updated: datetime = Field(default_factory=datetime.utcnow)


class ConversationState(ConversationStateBase, table=True):
    """Persistence model storing per-conversation context per installation."""
    id: Optional[int] = Field(default=None, primary_key=True)
    installation_id: int = Field(foreign_key="installation.id")


# Pydantic models for API responses
class QARequestResponse(BaseModel):
    """
    API response schema for returning stored Q&A exchanges via FastAPI.

    Mirrors the persisted model but omits internal relationships and secrets.
    """
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
    """
    API response schema for exposing installation metadata to clients.

    Provides identifying characteristics without leaking sensitive tokens.
    """
    id: int
    team_id: str
    team_name: str
    bot_user_id: str
    is_active: bool
    created_at: datetime
