"""
Session service for managing chat sessions and messages.
Provides CRUD operations and business logic for session management.
"""

from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
from sqlalchemy import func, or_, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

import structlog

from app.core.logging import LoggingMixin
from app.db.database import get_async_session
from app.models.database import Session, Message, SessionStatus, MessageType
from app.models.schemas import (
    SessionCreate,
    SessionUpdate,
    SessionResponse,
    MessageCreate,
    MessageResponse,
    PaginationParams,
    SessionFilter,
    MessageFilter
)

logger = structlog.get_logger(__name__)


class SessionService(LoggingMixin):
    """Service for managing chat sessions and messages."""
    
    async def create_session(self, session_data: SessionCreate) -> SessionResponse:
        """
        Create a new chat session.
        
        Args:
            session_data: Session creation data
            
        Returns:
            Created session response
        """
        self.logger.info("Creating new session", title=session_data.title)
        
        async for db in get_async_session():
            # Create new session
            session = Session(
                title=session_data.title,
                max_tool_calls=session_data.max_tool_calls or 50,
                timeout_seconds=session_data.timeout_seconds or 3600,
                agent_config=session_data.agent_config,
                status=SessionStatus.ACTIVE
            )
            
            db.add(session)
            await db.commit()
            await db.refresh(session)
            
            self.logger.info("Session created", session_id=session.id)
            return SessionResponse.model_validate(session)
    
    async def get_session(self, session_id: str) -> Optional[SessionResponse]:
        """
        Get a session by ID.
        
        Args:
            session_id: Session ID
            
        Returns:
            Session response or None if not found
        """
        async for db in get_async_session():
            session = await db.get(Session, session_id)
            if session:
                return SessionResponse.model_validate(session)
            return None
    
    async def update_session(
        self, 
        session_id: str, 
        session_data: SessionUpdate
    ) -> Optional[SessionResponse]:
        """
        Update a session.
        
        Args:
            session_id: Session ID
            session_data: Session update data
            
        Returns:
            Updated session response or None if not found
        """
        self.logger.info("Updating session", session_id=session_id)
        
        async for db in get_async_session():
            session = await db.get(Session, session_id)
            if not session:
                return None
            
            # Update fields
            if session_data.title is not None:
                session.title = session_data.title
            if session_data.status is not None:
                session.status = session_data.status
                if session_data.status in [SessionStatus.COMPLETED, SessionStatus.ERROR, SessionStatus.TERMINATED]:
                    session.completed_at = datetime.utcnow()
            if session_data.agent_config is not None:
                session.agent_config = session_data.agent_config
            
            session.updated_at = datetime.utcnow()
            
            await db.commit()
            await db.refresh(session)
            
            self.logger.info("Session updated", session_id=session_id)
            return SessionResponse.model_validate(session)
    
    async def delete_session(self, session_id: str) -> bool:
        """
        Delete a session and all its messages.
        
        Args:
            session_id: Session ID
            
        Returns:
            True if deleted, False if not found
        """
        self.logger.info("Deleting session", session_id=session_id)
        
        async for db in get_async_session():
            session = await db.get(Session, session_id)
            if not session:
                return False
            
            await db.delete(session)
            await db.commit()
            
            self.logger.info("Session deleted", session_id=session_id)
            return True
    
    async def list_sessions(
        self,
        pagination: PaginationParams,
        filters: Optional[SessionFilter] = None
    ) -> Dict[str, Any]:
        """
        List sessions with pagination and filtering.
        
        Args:
            pagination: Pagination parameters
            filters: Optional filters
            
        Returns:
            Dictionary with sessions, total count, and pagination info
        """
        async for db in get_async_session():
            # Build query
            query = db.query(Session).options(selectinload(Session.messages))
            
            # Apply filters
            if filters:
                if filters.status:
                    query = query.filter(Session.status == filters.status)
                if filters.created_after:
                    query = query.filter(Session.created_at >= filters.created_after)
                if filters.created_before:
                    query = query.filter(Session.created_at <= filters.created_before)
                if filters.title_search:
                    query = query.filter(Session.title.ilike(f"%{filters.title_search}%"))
            
            # Get total count
            total_query = query.with_entities(func.count(Session.id))
            total = await db.execute(total_query)
            total_count = total.scalar()
            
            # Apply pagination
            query = query.order_by(Session.created_at.desc())
            query = query.offset(pagination.offset).limit(pagination.page_size)
            
            # Execute query
            result = await db.execute(query)
            sessions = result.scalars().all()
            
            # Convert to response objects
            session_responses = [SessionResponse.model_validate(session) for session in sessions]
            
            return {
                "sessions": session_responses,
                "total": total_count,
                "page": pagination.page,
                "page_size": pagination.page_size,
                "has_next": pagination.offset + pagination.page_size < total_count,
                "has_previous": pagination.page > 1
            }
    
    async def add_message(
        self,
        session_id: str,
        content: str,
        message_type: MessageType,
        tool_name: Optional[str] = None,
        tool_call_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        error_code: Optional[str] = None,
        error_details: Optional[str] = None
    ) -> MessageResponse:
        """
        Add a message to a session.
        
        Args:
            session_id: Session ID
            content: Message content
            message_type: Message type
            tool_name: Optional tool name
            tool_call_id: Optional tool call ID
            metadata: Optional metadata
            error_code: Optional error code
            error_details: Optional error details
            
        Returns:
            Created message response
        """
        async for db in get_async_session():
            # Get current message count for sequence number
            message_count_query = db.query(func.count(Message.id)).filter(
                Message.session_id == session_id
            )
            result = await db.execute(message_count_query)
            sequence_number = result.scalar() + 1
            
            # Create message
            message = Message(
                session_id=session_id,
                content=content,
                message_type=message_type,
                sequence_number=sequence_number,
                tool_name=tool_name,
                tool_call_id=tool_call_id,
                metadata=metadata,
                error_code=error_code,
                error_details=error_details
            )
            
            db.add(message)
            
            # Update session updated_at
            session = await db.get(Session, session_id)
            if session:
                session.updated_at = datetime.utcnow()
            
            await db.commit()
            await db.refresh(message)
            
            return MessageResponse.model_validate(message)
    
    async def get_messages(
        self,
        session_id: str,
        pagination: Optional[PaginationParams] = None,
        filters: Optional[MessageFilter] = None
    ) -> List[MessageResponse]:
        """
        Get messages for a session.
        
        Args:
            session_id: Session ID
            pagination: Optional pagination parameters
            filters: Optional filters
            
        Returns:
            List of message responses
        """
        async for db in get_async_session():
            # Build query
            query = db.query(Message).filter(Message.session_id == session_id)
            
            # Apply filters
            if filters:
                if filters.message_type:
                    query = query.filter(Message.message_type == filters.message_type)
                if filters.created_after:
                    query = query.filter(Message.created_at >= filters.created_after)
                if filters.created_before:
                    query = query.filter(Message.created_at <= filters.created_before)
                if filters.content_search:
                    query = query.filter(Message.content.ilike(f"%{filters.content_search}%"))
            
            # Apply ordering
            query = query.order_by(Message.sequence_number.asc())
            
            # Apply pagination if provided
            if pagination:
                query = query.offset(pagination.offset).limit(pagination.page_size)
            
            # Execute query
            result = await db.execute(query)
            messages = result.scalars().all()
            
            return [MessageResponse.model_validate(message) for message in messages]
    
    async def get_message(self, message_id: str) -> Optional[MessageResponse]:
        """
        Get a message by ID.
        
        Args:
            message_id: Message ID
            
        Returns:
            Message response or None if not found
        """
        async for db in get_async_session():
            message = await db.get(Message, message_id)
            if message:
                return MessageResponse.model_validate(message)
            return None
    
    async def delete_message(self, message_id: str) -> bool:
        """
        Delete a message.
        
        Args:
            message_id: Message ID
            
        Returns:
            True if deleted, False if not found
        """
        async for db in get_async_session():
            message = await db.get(Message, message_id)
            if not message:
                return False
            
            await db.delete(message)
            await db.commit()
            
            return True
    
    async def get_session_stats(self, session_id: str) -> Dict[str, Any]:
        """
        Get statistics for a session.
        
        Args:
            session_id: Session ID
            
        Returns:
            Dictionary with session statistics
        """
        async for db in get_async_session():
            # Get session
            session = await db.get(Session, session_id)
            if not session:
                return {}
            
            # Get message counts by type
            message_stats_query = db.query(
                Message.message_type,
                func.count(Message.id)
            ).filter(
                Message.session_id == session_id
            ).group_by(Message.message_type)
            
            result = await db.execute(message_stats_query)
            message_stats = dict(result.fetchall())
            
            # Get tool usage stats
            tool_stats_query = db.query(
                Message.tool_name,
                func.count(Message.id)
            ).filter(
                and_(
                    Message.session_id == session_id,
                    Message.tool_name.isnot(None)
                )
            ).group_by(Message.tool_name)
            
            result = await db.execute(tool_stats_query)
            tool_stats = dict(result.fetchall())
            
            return {
                "session_id": session_id,
                "status": session.status.value,
                "created_at": session.created_at.isoformat(),
                "updated_at": session.updated_at.isoformat(),
                "duration_seconds": session.duration_seconds,
                "message_count": session.message_count,
                "message_stats": message_stats,
                "tool_stats": tool_stats,
                "max_tool_calls": session.max_tool_calls,
                "timeout_seconds": session.timeout_seconds
            }
    
    async def cleanup_old_sessions(self, days: int = 30) -> int:
        """
        Clean up old completed sessions.
        
        Args:
            days: Number of days to keep sessions
            
        Returns:
            Number of sessions deleted
        """
        cutoff_date = datetime.utcnow() - timedelta(days=days)
        
        async for db in get_async_session():
            # Delete old completed sessions
            query = db.query(Session).filter(
                and_(
                    Session.status.in_([SessionStatus.COMPLETED, SessionStatus.ERROR]),
                    Session.completed_at < cutoff_date
                )
            )
            
            sessions = await db.execute(query)
            sessions_to_delete = sessions.scalars().all()
            
            count = len(sessions_to_delete)
            
            for session in sessions_to_delete:
                await db.delete(session)
            
            await db.commit()
            
            self.logger.info("Cleaned up old sessions", count=count, cutoff_date=cutoff_date)
            return count