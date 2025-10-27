"""
Messages API endpoints for managing session messages.
Provides CRUD operations for messages within sessions.
"""

from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.models.schemas import (
    MessageCreate,
    MessageResponse,
    MessageListResponse,
    PaginationParams,
    MessageFilter
)
from app.services.sessions.session_service import SessionService
from app.core.logging import get_logger

logger = get_logger(__name__)

router = APIRouter()


def get_session_service() -> SessionService:
    """Dependency injection for session service."""
    return SessionService()


@router.get("/sessions/{session_id}/messages/", response_model=MessageListResponse)
async def get_session_messages(
    session_id: str,
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(50, ge=1, le=200, description="Items per page"),
    message_type: Optional[str] = Query(None, description="Filter by message type"),
    content_search: Optional[str] = Query(None, description="Search in message content"),
    session_service: SessionService = Depends(get_session_service)
):
    """
    Get messages for a session.
    
    - **session_id**: Session ID
    - **page**: Page number (default: 1)
    - **page_size**: Items per page (default: 50, max: 200)
    - **message_type**: Filter by message type
    - **content_search**: Search in message content
    """
    # Verify session exists
    session = await session_service.get_session(session_id)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session {session_id} not found"
        )
    
    pagination = PaginationParams(page=page, page_size=page_size)
    filters = MessageFilter(
        message_type=message_type,
        content_search=content_search
    ) if (message_type or content_search) else None
    
    messages = await session_service.get_messages(session_id, pagination, filters)
    
    # Calculate pagination info (simplified)
    total = len(messages)  # This is a simplified approach
    has_next = len(messages) == page_size
    has_previous = page > 1
    
    return MessageListResponse(
        messages=messages,
        total=total,
        page=page,
        page_size=page_size,
        has_next=has_next,
        has_previous=has_previous
    )


@router.post("/sessions/{session_id}/messages/", response_model=MessageResponse, status_code=status.HTTP_201_CREATED)
async def create_message(
    session_id: str,
    message_data: MessageCreate,
    session_service: SessionService = Depends(get_session_service)
):
    """
    Create a new message in a session.
    
    - **session_id**: Session ID
    - **content**: Message content
    - **message_type**: Message type (user, assistant, system, tool_call, tool_result, error)
    - **tool_name**: Optional tool name for tool messages
    - **tool_call_id**: Optional tool call ID
    - **metadata**: Optional additional metadata
    """
    # Verify session exists
    session = await session_service.get_session(session_id)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session {session_id} not found"
        )
    
    try:
        message = await session_service.add_message(
            session_id=session_id,
            content=message_data.content,
            message_type=message_data.message_type,
            tool_name=message_data.tool_name,
            tool_call_id=message_data.tool_call_id,
            metadata=message_data.metadata
        )
        
        logger.info("Message created via API", session_id=session_id, message_id=message.id)
        return message
        
    except Exception as e:
        logger.error("Failed to create message", session_id=session_id, error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create message: {str(e)}"
        )


@router.get("/sessions/{session_id}/messages/{message_id}", response_model=MessageResponse)
async def get_message(
    session_id: str,
    message_id: str,
    session_service: SessionService = Depends(get_session_service)
):
    """
    Get a specific message by ID.
    
    - **session_id**: Session ID
    - **message_id**: Message ID
    """
    # Verify session exists
    session = await session_service.get_session(session_id)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session {session_id} not found"
        )
    
    message = await session_service.get_message(message_id)
    if not message:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Message {message_id} not found"
        )
    
    # Verify message belongs to session
    if message.session_id != session_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Message {message_id} not found in session {session_id}"
        )
    
    return message


@router.delete("/sessions/{session_id}/messages/{message_id}")
async def delete_message(
    session_id: str,
    message_id: str,
    session_service: SessionService = Depends(get_session_service)
):
    """
    Delete a message.
    
    - **session_id**: Session ID
    - **message_id**: Message ID
    """
    # Verify session exists
    session = await session_service.get_session(session_id)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session {session_id} not found"
        )
    
    # Verify message exists and belongs to session
    message = await session_service.get_message(message_id)
    if not message or message.session_id != session_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Message {message_id} not found in session {session_id}"
        )
    
    deleted = await session_service.delete_message(message_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete message"
        )
    
    logger.info("Message deleted via API", session_id=session_id, message_id=message_id)
    return {"message": f"Message {message_id} deleted successfully"}