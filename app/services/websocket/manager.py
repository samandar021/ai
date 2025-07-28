"""
WebSocket manager for handling real-time connections and message broadcasting.
Manages WebSocket connections, session subscriptions, and message routing.
"""

import asyncio
import json
import uuid
from datetime import datetime
from typing import Dict, List, Optional, Set, Any

from fastapi import WebSocket, WebSocketDisconnect
import structlog

from app.core.config import get_settings
from app.core.logging import LoggingMixin
from app.models.schemas import WebSocketEventType, WebSocketMessage

logger = structlog.get_logger(__name__)
settings = get_settings()


class ConnectionManager(LoggingMixin):
    """Manages individual WebSocket connections."""
    
    def __init__(self):
        # Active connections: {connection_id: WebSocketConnection}
        self.active_connections: Dict[str, "WebSocketConnection"] = {}
        
        # Session subscriptions: {session_id: set of connection_ids}
        self.session_subscriptions: Dict[str, Set[str]] = {}
        
        # Connection to session mapping: {connection_id: session_id}
        self.connection_sessions: Dict[str, str] = {}
        
        # Heartbeat task
        self._heartbeat_task: Optional[asyncio.Task] = None
        self._start_heartbeat()
    
    def _start_heartbeat(self):
        """Start the heartbeat task."""
        if self._heartbeat_task is None or self._heartbeat_task.done():
            self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())
    
    async def _heartbeat_loop(self):
        """Send periodic heartbeat messages to all connections."""
        while True:
            try:
                await asyncio.sleep(settings.WS_HEARTBEAT_INTERVAL)
                
                # Send heartbeat to all connections
                heartbeat_message = {
                    "event_type": WebSocketEventType.HEARTBEAT.value,
                    "timestamp": datetime.utcnow().isoformat(),
                    "data": {"status": "alive"}
                }
                
                # Remove disconnected connections
                disconnected = []
                for connection_id, connection in self.active_connections.items():
                    try:
                        await connection.send_json(heartbeat_message)
                    except Exception:
                        disconnected.append(connection_id)
                
                # Clean up disconnected connections
                for connection_id in disconnected:
                    await self.disconnect(connection_id)
                    
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error("Error in heartbeat loop", error=str(e))
    
    async def connect(self, websocket: WebSocket, session_id: str, client_id: Optional[str] = None) -> str:
        """
        Accept a new WebSocket connection.
        
        Args:
            websocket: WebSocket instance
            session_id: Session ID to subscribe to
            client_id: Optional client identifier
            
        Returns:
            Connection ID
        """
        await websocket.accept()
        
        connection_id = client_id or str(uuid.uuid4())
        connection = WebSocketConnection(
            connection_id=connection_id,
            websocket=websocket,
            session_id=session_id,
            connected_at=datetime.utcnow()
        )
        
        # Store connection
        self.active_connections[connection_id] = connection
        self.connection_sessions[connection_id] = session_id
        
        # Subscribe to session
        if session_id not in self.session_subscriptions:
            self.session_subscriptions[session_id] = set()
        self.session_subscriptions[session_id].add(connection_id)
        
        self.logger.info(
            "WebSocket connected",
            connection_id=connection_id,
            session_id=session_id,
            total_connections=len(self.active_connections)
        )
        
        # Send connection confirmation
        await connection.send_json({
            "event_type": WebSocketEventType.MESSAGE.value,
            "session_id": session_id,
            "data": {
                "type": "connection_established",
                "connection_id": connection_id,
                "message": "Connected to session"
            },
            "timestamp": datetime.utcnow().isoformat()
        })
        
        return connection_id
    
    async def disconnect(self, connection_id: str):
        """
        Disconnect a WebSocket connection.
        
        Args:
            connection_id: Connection ID
        """
        connection = self.active_connections.get(connection_id)
        if not connection:
            return
        
        session_id = self.connection_sessions.get(connection_id)
        
        # Remove from subscriptions
        if session_id and session_id in self.session_subscriptions:
            self.session_subscriptions[session_id].discard(connection_id)
            
            # Clean up empty session subscriptions
            if not self.session_subscriptions[session_id]:
                del self.session_subscriptions[session_id]
        
        # Remove from active connections
        del self.active_connections[connection_id]
        if connection_id in self.connection_sessions:
            del self.connection_sessions[connection_id]
        
        self.logger.info(
            "WebSocket disconnected",
            connection_id=connection_id,
            session_id=session_id,
            total_connections=len(self.active_connections)
        )
    
    async def send_personal_message(self, connection_id: str, message: Dict[str, Any]):
        """
        Send a message to a specific connection.
        
        Args:
            connection_id: Connection ID
            message: Message to send
        """
        connection = self.active_connections.get(connection_id)
        if connection:
            try:
                await connection.send_json(message)
            except Exception as e:
                self.logger.error(
                    "Failed to send personal message",
                    connection_id=connection_id,
                    error=str(e)
                )
                await self.disconnect(connection_id)
    
    async def broadcast_to_session(self, session_id: str, message: Dict[str, Any]):
        """
        Broadcast a message to all connections subscribed to a session.
        
        Args:
            session_id: Session ID
            message: Message to broadcast
        """
        connection_ids = self.session_subscriptions.get(session_id, set()).copy()
        
        if not connection_ids:
            return
        
        self.logger.debug(
            "Broadcasting to session",
            session_id=session_id,
            connection_count=len(connection_ids),
            event_type=message.get("event_type")
        )
        
        # Send to all connections
        disconnected = []
        for connection_id in connection_ids:
            connection = self.active_connections.get(connection_id)
            if connection:
                try:
                    await connection.send_json(message)
                except Exception as e:
                    self.logger.error(
                        "Failed to broadcast message",
                        connection_id=connection_id,
                        session_id=session_id,
                        error=str(e)
                    )
                    disconnected.append(connection_id)
        
        # Clean up disconnected connections
        for connection_id in disconnected:
            await self.disconnect(connection_id)
    
    async def broadcast_to_all(self, message: Dict[str, Any]):
        """
        Broadcast a message to all active connections.
        
        Args:
            message: Message to broadcast
        """
        connection_ids = list(self.active_connections.keys())
        
        self.logger.debug(
            "Broadcasting to all connections",
            connection_count=len(connection_ids),
            event_type=message.get("event_type")
        )
        
        disconnected = []
        for connection_id in connection_ids:
            connection = self.active_connections.get(connection_id)
            if connection:
                try:
                    await connection.send_json(message)
                except Exception:
                    disconnected.append(connection_id)
        
        # Clean up disconnected connections
        for connection_id in disconnected:
            await self.disconnect(connection_id)
    
    def get_session_connections(self, session_id: str) -> List[str]:
        """
        Get all connection IDs for a session.
        
        Args:
            session_id: Session ID
            
        Returns:
            List of connection IDs
        """
        return list(self.session_subscriptions.get(session_id, set()))
    
    def get_connection_info(self, connection_id: str) -> Optional[Dict[str, Any]]:
        """
        Get information about a connection.
        
        Args:
            connection_id: Connection ID
            
        Returns:
            Connection information or None
        """
        connection = self.active_connections.get(connection_id)
        if connection:
            return {
                "connection_id": connection.connection_id,
                "session_id": connection.session_id,
                "connected_at": connection.connected_at.isoformat(),
                "is_alive": connection.is_alive
            }
        return None
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Get WebSocket manager statistics.
        
        Returns:
            Statistics dictionary
        """
        return {
            "total_connections": len(self.active_connections),
            "total_sessions": len(self.session_subscriptions),
            "connections_per_session": {
                session_id: len(connections) 
                for session_id, connections in self.session_subscriptions.items()
            },
            "heartbeat_interval": settings.WS_HEARTBEAT_INTERVAL,
            "max_connections": settings.WS_MAX_CONNECTIONS
        }
    
    async def cleanup(self):
        """Clean up the connection manager."""
        if self._heartbeat_task:
            self._heartbeat_task.cancel()
            try:
                await self._heartbeat_task
            except asyncio.CancelledError:
                pass
        
        # Close all connections
        for connection in list(self.active_connections.values()):
            try:
                await connection.websocket.close()
            except Exception:
                pass
        
        self.active_connections.clear()
        self.session_subscriptions.clear()
        self.connection_sessions.clear()


class WebSocketConnection:
    """Represents an individual WebSocket connection."""
    
    def __init__(
        self, 
        connection_id: str, 
        websocket: WebSocket, 
        session_id: str,
        connected_at: datetime
    ):
        self.connection_id = connection_id
        self.websocket = websocket
        self.session_id = session_id
        self.connected_at = connected_at
        self._is_alive = True
    
    @property
    def is_alive(self) -> bool:
        """Check if the connection is alive."""
        return self._is_alive and self.websocket.client_state.name == "CONNECTED"
    
    async def send_json(self, data: Dict[str, Any]):
        """
        Send JSON data through the WebSocket.
        
        Args:
            data: Data to send
        """
        try:
            await self.websocket.send_json(data)
        except Exception as e:
            self._is_alive = False
            raise e
    
    async def send_text(self, text: str):
        """
        Send text through the WebSocket.
        
        Args:
            text: Text to send
        """
        try:
            await self.websocket.send_text(text)
        except Exception as e:
            self._is_alive = False
            raise e
    
    async def receive_json(self) -> Dict[str, Any]:
        """
        Receive JSON data from the WebSocket.
        
        Returns:
            Received data
        """
        try:
            data = await self.websocket.receive_json()
            return data
        except Exception as e:
            self._is_alive = False
            raise e
    
    async def receive_text(self) -> str:
        """
        Receive text from the WebSocket.
        
        Returns:
            Received text
        """
        try:
            text = await self.websocket.receive_text()
            return text
        except Exception as e:
            self._is_alive = False
            raise e


# Global WebSocket manager instance
class WebSocketManager:
    """Global WebSocket manager wrapper."""
    
    def __init__(self):
        self._manager = ConnectionManager()
    
    async def connect(self, websocket: WebSocket, session_id: str, client_id: Optional[str] = None) -> str:
        """Connect a WebSocket."""
        return await self._manager.connect(websocket, session_id, client_id)
    
    async def disconnect(self, connection_id: str):
        """Disconnect a WebSocket."""
        await self._manager.disconnect(connection_id)
    
    async def send_personal_message(self, connection_id: str, message: Dict[str, Any]):
        """Send a personal message."""
        await self._manager.send_personal_message(connection_id, message)
    
    async def broadcast_to_session(self, session_id: str, message: Dict[str, Any]):
        """Broadcast to a session."""
        await self._manager.broadcast_to_session(session_id, message)
    
    async def broadcast_to_all(self, message: Dict[str, Any]):
        """Broadcast to all connections."""
        await self._manager.broadcast_to_all(message)
    
    def get_session_connections(self, session_id: str) -> List[str]:
        """Get session connections."""
        return self._manager.get_session_connections(session_id)
    
    def get_connection_info(self, connection_id: str) -> Optional[Dict[str, Any]]:
        """Get connection info."""
        return self._manager.get_connection_info(connection_id)
    
    def get_stats(self) -> Dict[str, Any]:
        """Get statistics."""
        return self._manager.get_stats()
    
    async def cleanup(self):
        """Clean up the manager."""
        await self._manager.cleanup()


# Global instance
websocket_manager = WebSocketManager()