"""
Session API endpoints for managing chat sessions.
Provides CRUD operations for sessions and agent interaction.
"""

from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import JSONResponse

from app.models.schemas import (
    SessionCreate,
    SessionUpdate, 
    SessionResponse,
    SessionListResponse,
    PaginationParams,
    SessionFilter,
    AgentStartRequest,
    AgentStopRequest,
    AgentStatusResponse,
    ErrorResponse
)
from app.services.sessions.session_service import SessionService
from app.services.agents.agent_service import AgentService
from app.services.websocket.manager import websocket_manager
from app.core.logging import get_logger

logger = get_logger(__name__)

router = APIRouter()

# Dependency injection
def get_session_service() -> SessionService:
    return SessionService()

def get_agent_service() -> AgentService:
    session_service = get_session_service()
    return AgentService(session_service, websocket_manager)


@router.post("/sessions/", response_model=SessionResponse, status_code=status.HTTP_201_CREATED)
async def create_session(
    session_data: SessionCreate,
    session_service: SessionService = Depends(get_session_service)
):
    """
    Create a new chat session.
    
    - **title**: Session title
    - **max_tool_calls**: Maximum tool calls allowed (default: 50)
    - **timeout_seconds**: Session timeout in seconds (default: 3600)
    - **agent_config**: Optional agent configuration
    """
    try:
        session = await session_service.create_session(session_data)
        logger.info("Session created via API", session_id=session.id)
        return session
    except Exception as e:
        logger.error("Failed to create session", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create session: {str(e)}"
        )


@router.get("/sessions/", response_model=SessionListResponse)
async def list_sessions(
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    status_filter: Optional[str] = Query(None, description="Filter by session status"),
    title_search: Optional[str] = Query(None, description="Search in session titles"),
    session_service: SessionService = Depends(get_session_service)
):
    """
    List sessions with pagination and filtering.
    
    - **page**: Page number (default: 1)
    - **page_size**: Items per page (default: 20, max: 100)
    - **status_filter**: Filter by session status
    - **title_search**: Search in session titles
    """
    try:
        pagination = PaginationParams(page=page, page_size=page_size)
        filters = SessionFilter(
            status=status_filter,
            title_search=title_search
        ) if (status_filter or title_search) else None
        
        result = await session_service.list_sessions(pagination, filters)
        return SessionListResponse(**result)
    except Exception as e:
        logger.error("Failed to list sessions", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list sessions: {str(e)}"
        )


@router.get("/sessions/{session_id}", response_model=SessionResponse)
async def get_session(
    session_id: str,
    session_service: SessionService = Depends(get_session_service)
):
    """
    Get a specific session by ID.
    
    - **session_id**: Session ID
    """
    session = await session_service.get_session(session_id)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session {session_id} not found"
        )
    return session


@router.put("/sessions/{session_id}", response_model=SessionResponse)
async def update_session(
    session_id: str,
    session_data: SessionUpdate,
    session_service: SessionService = Depends(get_session_service)
):
    """
    Update a session.
    
    - **session_id**: Session ID
    - **title**: New session title (optional)
    - **status**: New session status (optional)
    - **agent_config**: New agent configuration (optional)
    """
    session = await session_service.update_session(session_id, session_data)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session {session_id} not found"
        )
    
    logger.info("Session updated via API", session_id=session_id)
    return session


@router.delete("/sessions/{session_id}")
async def delete_session(
    session_id: str,
    session_service: SessionService = Depends(get_session_service),
    agent_service: AgentService = Depends(get_agent_service)
):
    """
    Delete a session and all its messages.
    
    - **session_id**: Session ID
    """
    # Stop any active agent session first
    await agent_service.stop_agent_session(session_id, "Session deleted")
    
    deleted = await session_service.delete_session(session_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session {session_id} not found"
        )
    
    logger.info("Session deleted via API", session_id=session_id)
    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content={"message": f"Session {session_id} deleted successfully"}
    )


@router.post("/sessions/{session_id}/start")
async def start_agent_session(
    session_id: str,
    request: AgentStartRequest,
    agent_service: AgentService = Depends(get_agent_service),
    session_service: SessionService = Depends(get_session_service)
):
    """
    Start agent processing for a session.
    
    - **session_id**: Session ID
    - **message**: User message to process
    - **stream**: Enable streaming responses (default: True)
    """
    # Verify session exists
    session = await session_service.get_session(session_id)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session {session_id} not found"
        )
    
    try:
        agent_session_id = await agent_service.start_agent_session(
            session_id=session_id,
            message=request.message
        )
        
        logger.info("Agent session started via API", session_id=session_id)
        return {
            "message": "Agent session started",
            "session_id": session_id,
            "agent_session_id": agent_session_id,
            "streaming": request.stream
        }
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error("Failed to start agent session", session_id=session_id, error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to start agent session: {str(e)}"
        )


@router.post("/sessions/{session_id}/stop")
async def stop_agent_session(
    session_id: str,
    request: AgentStopRequest,
    agent_service: AgentService = Depends(get_agent_service)
):
    """
    Stop agent processing for a session.
    
    - **session_id**: Session ID  
    - **reason**: Optional reason for stopping
    """
    stopped = await agent_service.stop_agent_session(session_id, request.reason)
    
    if not stopped:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No active agent session found for {session_id}"
        )
    
    logger.info("Agent session stopped via API", session_id=session_id)
    return {
        "message": "Agent session stopped",
        "session_id": session_id,
        "reason": request.reason
    }


@router.get("/sessions/{session_id}/status", response_model=AgentStatusResponse)
async def get_agent_status(
    session_id: str,
    agent_service: AgentService = Depends(get_agent_service)
):
    """
    Get the status of an agent session.
    
    - **session_id**: Session ID
    """
    status = await agent_service.get_agent_status(session_id)
    
    if status is None:
        # No active agent session, return idle status
        return AgentStatusResponse(
            session_id=session_id,
            status="idle",
            tool_calls_count=0
        )
    
    return AgentStatusResponse(
        session_id=session_id,
        status=status,
        tool_calls_count=0  # TODO: Get from agent session
    )


@router.get("/sessions/{session_id}/stats")
async def get_session_stats(
    session_id: str,
    session_service: SessionService = Depends(get_session_service)
):
    """
    Get statistics for a session.
    
    - **session_id**: Session ID
    """
    stats = await session_service.get_session_stats(session_id)
    
    if not stats:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session {session_id} not found"
        )
    
    return stats


@router.get("/sessions/active")
async def list_active_sessions(
    agent_service: AgentService = Depends(get_agent_service)
):
    """
    List all active agent sessions.
    """
    active_sessions = await agent_service.list_active_sessions()
    
    return {
        "active_sessions": active_sessions,
        "count": len(active_sessions)
    }