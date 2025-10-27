"""
SQLAlchemy database models for the Computer Use Agent Backend.
Defines the database schema for sessions, messages, and related entities.
"""

import uuid
from datetime import datetime
from enum import Enum
from typing import List, Optional

from sqlalchemy import Column, DateTime, Enum as SQLEnum, ForeignKey, Integer, String, Text, Boolean, JSON
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship, Mapped, mapped_column
from sqlalchemy.sql import func

from app.db.database import Base


class SessionStatus(str, Enum):
    """Session status enumeration."""
    ACTIVE = "active"
    COMPLETED = "completed"
    ERROR = "error"
    TERMINATED = "terminated"


class MessageType(str, Enum):
    """Message type enumeration."""
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"
    TOOL_CALL = "tool_call"
    TOOL_RESULT = "tool_result"
    ERROR = "error"


class Session(Base):
    """
    Session model representing a chat session with the Computer Use Agent.
    
    Each session contains multiple messages and tracks the conversation state.
    """
    __tablename__ = "sessions"
    
    # Primary key
    id: Mapped[str] = mapped_column(
        String(255), 
        primary_key=True, 
        default=lambda: str(uuid.uuid4()),
        index=True
    )
    
    # Session metadata
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    status: Mapped[SessionStatus] = mapped_column(
        SQLEnum(SessionStatus),
        default=SessionStatus.ACTIVE,
        nullable=False,
        index=True
    )
    
    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        index=True
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True
    )
    
    # Session configuration
    max_tool_calls: Mapped[int] = mapped_column(Integer, default=50)
    timeout_seconds: Mapped[int] = mapped_column(Integer, default=3600)  # 1 hour
    
    # Agent configuration (stored as JSON)
    agent_config: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    
    # Relationships
    messages: Mapped[List["Message"]] = relationship(
        "Message",
        back_populates="session",
        cascade="all, delete-orphan",
        order_by="Message.created_at"
    )
    
    def __repr__(self) -> str:
        return f"<Session(id={self.id}, title={self.title}, status={self.status})>"
    
    @property
    def message_count(self) -> int:
        """Get the number of messages in this session."""
        return len(self.messages) if self.messages else 0
    
    @property
    def is_active(self) -> bool:
        """Check if the session is active."""
        return self.status == SessionStatus.ACTIVE
    
    @property
    def is_completed(self) -> bool:
        """Check if the session is completed."""
        return self.status == SessionStatus.COMPLETED
    
    @property
    def duration_seconds(self) -> Optional[int]:
        """Get session duration in seconds."""
        if self.completed_at:
            return int((self.completed_at - self.created_at).total_seconds())
        return None


class Message(Base):
    """
    Message model representing individual messages within a session.
    
    Messages can be user queries, assistant responses, tool calls, or tool results.
    """
    __tablename__ = "messages"
    
    # Primary key
    id: Mapped[str] = mapped_column(
        String(255),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
        index=True
    )
    
    # Foreign key to session
    session_id: Mapped[str] = mapped_column(
        String(255),
        ForeignKey("sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    
    # Message content
    content: Mapped[str] = mapped_column(Text, nullable=False)
    message_type: Mapped[MessageType] = mapped_column(
        SQLEnum(MessageType),
        nullable=False,
        index=True
    )
    
    # Message metadata
    sequence_number: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    
    # Tool-specific fields
    tool_name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    tool_call_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    
    # Additional metadata (stored as JSON)
    metadata: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    
    # Error information
    error_code: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    error_details: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        index=True
    )
    
    # Relationships
    session: Mapped[Session] = relationship(
        "Session",
        back_populates="messages"
    )
    
    def __repr__(self) -> str:
        return f"<Message(id={self.id}, type={self.message_type}, session={self.session_id})>"
    
    @property
    def is_user_message(self) -> bool:
        """Check if this is a user message."""
        return self.message_type == MessageType.USER
    
    @property
    def is_assistant_message(self) -> bool:
        """Check if this is an assistant message."""
        return self.message_type == MessageType.ASSISTANT
    
    @property
    def is_tool_call(self) -> bool:
        """Check if this is a tool call message."""
        return self.message_type == MessageType.TOOL_CALL
    
    @property
    def is_tool_result(self) -> bool:
        """Check if this is a tool result message."""
        return self.message_type == MessageType.TOOL_RESULT
    
    @property
    def is_error(self) -> bool:
        """Check if this is an error message."""
        return self.message_type == MessageType.ERROR
    
    @property
    def content_preview(self) -> str:
        """Get a preview of the message content (first 100 characters)."""
        return self.content[:100] + "..." if len(self.content) > 100 else self.content


# Additional indexes for performance
from sqlalchemy import Index

# Composite indexes for common queries
Index("ix_messages_session_type", Message.session_id, Message.message_type)
Index("ix_messages_session_sequence", Message.session_id, Message.sequence_number)
Index("ix_sessions_status_created", Session.status, Session.created_at)