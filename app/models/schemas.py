"""
Pydantic schemas for API request/response validation and serialization.
Defines the data structures used for API communication.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional
from enum import Enum

from pydantic import BaseModel, Field, ConfigDict, validator

from app.models.database import SessionStatus, MessageType


# Base schemas
class BaseSchema(BaseModel):
    """Base schema with common configuration."""
    model_config = ConfigDict(from_attributes=True)


# Session schemas
class SessionCreate(BaseModel):
    """Schema for creating a new session."""
    title: str = Field(..., min_length=1, max_length=500, description="Session title")
    max_tool_calls: Optional[int] = Field(default=50, ge=1, le=200, description="Maximum tool calls allowed")
    timeout_seconds: Optional[int] = Field(default=3600, ge=60, le=14400, description="Session timeout in seconds")
    agent_config: Optional[Dict[str, Any]] = Field(default=None, description="Agent configuration")


class SessionUpdate(BaseModel):
    """Schema for updating a session."""
    title: Optional[str] = Field(None, min_length=1, max_length=500, description="Session title")
    status: Optional[SessionStatus] = Field(None, description="Session status")
    agent_config: Optional[Dict[str, Any]] = Field(None, description="Agent configuration")


class SessionResponse(BaseSchema):
    """Schema for session response."""
    id: str
    title: str
    status: SessionStatus
    created_at: datetime
    updated_at: datetime
    completed_at: Optional[datetime] = None
    max_tool_calls: int
    timeout_seconds: int
    agent_config: Optional[Dict[str, Any]] = None
    message_count: int = 0


class SessionListResponse(BaseModel):
    """Schema for session list response."""
    sessions: List[SessionResponse]
    total: int
    page: int
    page_size: int
    has_next: bool
    has_previous: bool


# Message schemas
class MessageCreate(BaseModel):
    """Schema for creating a new message."""
    content: str = Field(..., min_length=1, description="Message content")
    message_type: MessageType = Field(default=MessageType.USER, description="Message type")
    tool_name: Optional[str] = Field(None, max_length=100, description="Tool name for tool messages")
    tool_call_id: Optional[str] = Field(None, max_length=255, description="Tool call ID")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Additional metadata")


class MessageResponse(BaseSchema):
    """Schema for message response."""
    id: str
    session_id: str
    content: str
    message_type: MessageType
    sequence_number: int
    tool_name: Optional[str] = None
    tool_call_id: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    error_code: Optional[str] = None
    error_details: Optional[str] = None
    created_at: datetime


class MessageListResponse(BaseModel):
    """Schema for message list response."""
    messages: List[MessageResponse]
    total: int
    page: int
    page_size: int
    has_next: bool
    has_previous: bool


# WebSocket schemas
class WebSocketEventType(str, Enum):
    """WebSocket event types."""
    MESSAGE = "message"
    TOOL_CALL = "tool_call"
    TOOL_RESULT = "tool_result"
    ERROR = "error"
    STATUS_UPDATE = "status_update"
    HEARTBEAT = "heartbeat"
    DISCONNECT = "disconnect"


class WebSocketMessage(BaseModel):
    """Schema for WebSocket messages."""
    event_type: WebSocketEventType
    session_id: str
    data: Dict[str, Any]
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class WebSocketConnect(BaseModel):
    """Schema for WebSocket connection."""
    session_id: str
    client_id: Optional[str] = None


# Agent interaction schemas
class AgentStartRequest(BaseModel):
    """Schema for starting agent processing."""
    message: str = Field(..., min_length=1, description="User message to process")
    stream: bool = Field(default=True, description="Enable streaming responses")


class AgentStopRequest(BaseModel):
    """Schema for stopping agent processing."""
    reason: Optional[str] = Field(None, description="Reason for stopping")


class AgentStatus(str, Enum):
    """Agent status enumeration."""
    IDLE = "idle"
    PROCESSING = "processing"
    WAITING_FOR_TOOL = "waiting_for_tool"
    COMPLETED = "completed"
    ERROR = "error"
    STOPPED = "stopped"


class AgentStatusResponse(BaseModel):
    """Schema for agent status response."""
    session_id: str
    status: AgentStatus
    current_message: Optional[str] = None
    tool_calls_count: int = 0
    started_at: Optional[datetime] = None
    last_activity: Optional[datetime] = None


# Tool schemas
class ToolCall(BaseModel):
    """Schema for tool call."""
    id: str
    name: str
    parameters: Dict[str, Any]
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class ToolResult(BaseModel):
    """Schema for tool result."""
    call_id: str
    name: str
    result: Any
    error: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class ToolStatus(BaseModel):
    """Schema for tool status."""
    name: str
    available: bool
    description: str
    parameters: Dict[str, Any]


# Error schemas
class ErrorResponse(BaseModel):
    """Schema for error responses."""
    error: str
    message: str
    code: Optional[str] = None
    details: Optional[Dict[str, Any]] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class ValidationErrorResponse(BaseModel):
    """Schema for validation error responses."""
    error: str = "validation_error"
    message: str = "Validation failed"
    details: List[Dict[str, Any]]
    timestamp: datetime = Field(default_factory=datetime.utcnow)


# Health and status schemas
class HealthResponse(BaseModel):
    """Schema for health check response."""
    status: str
    version: str
    environment: str
    database: bool
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class SystemStatusResponse(BaseModel):
    """Schema for system status response."""
    api: str
    database: bool
    anthropic_api: bool
    vnc_connection: bool
    active_sessions: int
    total_sessions: int
    uptime_seconds: int
    timestamp: datetime = Field(default_factory=datetime.utcnow)


# Pagination schemas
class PaginationParams(BaseModel):
    """Schema for pagination parameters."""
    page: int = Field(default=1, ge=1, description="Page number")
    page_size: int = Field(default=20, ge=1, le=100, description="Items per page")
    
    @property
    def offset(self) -> int:
        """Calculate offset for database queries."""
        return (self.page - 1) * self.page_size


# Query filter schemas
class SessionFilter(BaseModel):
    """Schema for session filtering."""
    status: Optional[SessionStatus] = None
    created_after: Optional[datetime] = None
    created_before: Optional[datetime] = None
    title_search: Optional[str] = None


class MessageFilter(BaseModel):
    """Schema for message filtering."""
    message_type: Optional[MessageType] = None
    created_after: Optional[datetime] = None
    created_before: Optional[datetime] = None
    content_search: Optional[str] = None


# VNC schemas
class VNCConnectionInfo(BaseModel):
    """Schema for VNC connection information."""
    host: str
    port: int
    password: Optional[str] = None
    url: str
    status: str


class VNCScreenshot(BaseModel):
    """Schema for VNC screenshot."""
    session_id: str
    image_data: str  # Base64 encoded image
    width: int
    height: int
    timestamp: datetime = Field(default_factory=datetime.utcnow)