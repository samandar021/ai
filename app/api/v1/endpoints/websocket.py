"""
WebSocket API endpoints for real-time communication.
Provides WebSocket connections for live session updates.
"""

from typing import Optional
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends, Query, HTTPException
import structlog

from app.services.websocket.manager import websocket_manager
from app.services.sessions.session_service import SessionService
from app.core.logging import get_logger

logger = get_logger(__name__)

router = APIRouter()


def get_session_service() -> SessionService:
    """Dependency injection for session service."""
    return SessionService()


@router.websocket("/sessions/{session_id}/ws")
async def websocket_endpoint(
    websocket: WebSocket,
    session_id: str,
    client_id: Optional[str] = Query(None, description="Optional client identifier"),
    session_service: SessionService = Depends(get_session_service)
):
    """
    WebSocket endpoint for real-time session communication.
    
    Connects to a specific session and receives real-time updates including:
    - Agent status changes
    - Message streaming
    - Tool call executions
    - Tool results
    - Error messages
    
    Query Parameters:
    - **client_id**: Optional client identifier for connection tracking
    
    WebSocket Message Format:
    ```json
    {
        "event_type": "message|tool_call|tool_result|status_update|error|heartbeat",
        "session_id": "session_id",
        "data": {
            // Event-specific data
        },
        "timestamp": "2024-01-01T00:00:00Z"
    }
    ```
    
    Event Types:
    - **message**: Agent message content (streaming)
    - **tool_call**: Tool execution started
    - **tool_result**: Tool execution completed
    - **status_update**: Agent status changed
    - **error**: Error occurred
    - **heartbeat**: Connection health check
    """
    # Verify session exists
    session = await session_service.get_session(session_id)
    if not session:
        await websocket.close(code=4004, reason=f"Session {session_id} not found")
        return
    
    connection_id = None
    try:
        # Connect to WebSocket manager
        connection_id = await websocket_manager.connect(
            websocket=websocket,
            session_id=session_id,
            client_id=client_id
        )
        
        logger.info(
            "WebSocket connection established",
            connection_id=connection_id,
            session_id=session_id,
            client_id=client_id
        )
        
        # Keep connection alive and handle incoming messages
        while True:
            try:
                # Receive message from client
                data = await websocket.receive_json()
                
                # Handle client messages (if needed)
                await handle_client_message(
                    connection_id=connection_id,
                    session_id=session_id,
                    message=data
                )
                
            except WebSocketDisconnect:
                logger.info(
                    "WebSocket client disconnected",
                    connection_id=connection_id,
                    session_id=session_id
                )
                break
            except Exception as e:
                logger.error(
                    "Error in WebSocket message handling",
                    connection_id=connection_id,
                    session_id=session_id,
                    error=str(e)
                )
                # Send error to client
                await websocket_manager.send_personal_message(
                    connection_id=connection_id,
                    message={
                        "event_type": "error",
                        "session_id": session_id,
                        "data": {"error": f"Message handling error: {str(e)}"},
                        "timestamp": "2024-01-01T00:00:00Z"  # This should be actual timestamp
                    }
                )
    
    except Exception as e:
        logger.error(
            "WebSocket connection error",
            session_id=session_id,
            client_id=client_id,
            error=str(e)
        )
        try:
            await websocket.close(code=4000, reason=f"Connection error: {str(e)}")
        except:
            pass
    
    finally:
        # Clean up connection
        if connection_id:
            await websocket_manager.disconnect(connection_id)
            logger.info(
                "WebSocket connection cleaned up",
                connection_id=connection_id,
                session_id=session_id
            )


async def handle_client_message(connection_id: str, session_id: str, message: dict):
    """
    Handle incoming messages from WebSocket clients.
    
    Args:
        connection_id: Connection ID
        session_id: Session ID
        message: Message from client
    """
    message_type = message.get("type")
    
    if message_type == "ping":
        # Respond to ping with pong
        await websocket_manager.send_personal_message(
            connection_id=connection_id,
            message={
                "event_type": "message",
                "session_id": session_id,
                "data": {"type": "pong", "message": "Connection alive"},
                "timestamp": "2024-01-01T00:00:00Z"  # This should be actual timestamp
            }
        )
    
    elif message_type == "subscribe":
        # Client wants to subscribe to specific events
        event_types = message.get("event_types", [])
        logger.info(
            "Client subscription request",
            connection_id=connection_id,
            session_id=session_id,
            event_types=event_types
        )
        # TODO: Implement selective event subscription
    
    elif message_type == "get_status":
        # Client requests current status
        # This would be handled by the sessions API, but we can acknowledge
        await websocket_manager.send_personal_message(
            connection_id=connection_id,
            message={
                "event_type": "status_update",
                "session_id": session_id,
                "data": {"status": "acknowledged", "message": "Status request received"},
                "timestamp": "2024-01-01T00:00:00Z"  # This should be actual timestamp
            }
        )
    
    else:
        logger.warning(
            "Unknown client message type",
            connection_id=connection_id,
            session_id=session_id,
            message_type=message_type
        )


@router.get("/websocket/stats")
async def get_websocket_stats():
    """
    Get WebSocket connection statistics.
    
    Returns information about active connections, sessions, and performance metrics.
    """
    stats = websocket_manager.get_stats()
    return {
        "websocket_stats": stats,
        "description": "Real-time WebSocket connection statistics"
    }


@router.get("/websocket/sessions/{session_id}/connections")
async def get_session_websocket_connections(session_id: str):
    """
    Get WebSocket connections for a specific session.
    
    Args:
        session_id: Session ID
        
    Returns:
        List of connection information for the session
    """
    connection_ids = websocket_manager.get_session_connections(session_id)
    
    connections = []
    for connection_id in connection_ids:
        info = websocket_manager.get_connection_info(connection_id)
        if info:
            connections.append(info)
    
    return {
        "session_id": session_id,
        "connections": connections,
        "connection_count": len(connections)
    }


@router.post("/websocket/sessions/{session_id}/broadcast")
async def broadcast_to_session(
    session_id: str,
    message: dict,
    session_service: SessionService = Depends(get_session_service)
):
    """
    Broadcast a message to all WebSocket connections for a session.
    
    This is primarily for testing and administrative purposes.
    
    Args:
        session_id: Session ID
        message: Message to broadcast
    """
    # Verify session exists
    session = await session_service.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail=f"Session {session_id} not found")
    
    # Add required fields to message
    broadcast_message = {
        "event_type": message.get("event_type", "message"),
        "session_id": session_id,
        "data": message.get("data", message),
        "timestamp": "2024-01-01T00:00:00Z"  # This should be actual timestamp
    }
    
    await websocket_manager.broadcast_to_session(session_id, broadcast_message)
    
    connection_count = len(websocket_manager.get_session_connections(session_id))
    
    return {
        "message": "Broadcast sent",
        "session_id": session_id,
        "connections_reached": connection_count
    }