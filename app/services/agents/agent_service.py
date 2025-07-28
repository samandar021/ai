"""
Agent service for orchestrating Computer Use capabilities.
Manages agent execution, tool calling, and real-time streaming.
"""

import asyncio
import json
import uuid
from datetime import datetime
from typing import Any, AsyncGenerator, Dict, List, Optional, Callable

import anthropic
import structlog
from anthropic.types.beta import BetaMessage, BetaTextBlock, BetaToolUseBlock

from app.core.config import get_settings
from app.core.logging import LoggingMixin
from app.models.database import SessionStatus, MessageType
from app.models.schemas import (
    AgentStatus, 
    WebSocketEventType, 
    WebSocketMessage, 
    ToolCall, 
    ToolResult
)
from app.services.sessions.session_service import SessionService
from app.services.websocket.manager import WebSocketManager
from app.tools import ToolCollection
from app.tools.collection import ToolResult as ComputerToolResult

logger = structlog.get_logger(__name__)
settings = get_settings()


class AgentService(LoggingMixin):
    """
    Service for managing Computer Use agent interactions.
    
    Handles agent execution, tool calling, message streaming,
    and coordination with the session management system.
    """
    
    def __init__(
        self,
        session_service: SessionService,
        websocket_manager: WebSocketManager
    ):
        self.session_service = session_service
        self.websocket_manager = websocket_manager
        self.anthropic_client = anthropic.AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)
        self.tool_collection = ToolCollection()
        
        # Active agent sessions
        self._active_sessions: Dict[str, "AgentSession"] = {}
        
        # Agent configuration
        self.model = "claude-3-5-sonnet-20241022"
        self.max_tokens = 4096
        self.system_prompt = self._build_system_prompt()
    
    def _build_system_prompt(self) -> str:
        """Build the system prompt for the agent."""
        return """You are a helpful AI assistant with computer use capabilities. 
        You can interact with a computer desktop environment to help users accomplish tasks.
        
        You have access to the following tools:
        - Computer: Take screenshots, click, type, scroll, and interact with GUI elements
        - Text Editor: Edit and create text files  
        - Bash: Execute shell commands
        
        When helping users:
        1. Always take a screenshot first to see the current state
        2. Break down complex tasks into clear steps
        3. Provide clear explanations of what you're doing
        4. Ask for clarification if the request is ambiguous
        5. Be patient and methodical in your approach
        
        Remember to be helpful, accurate, and safe in your interactions."""
    
    async def start_agent_session(
        self, 
        session_id: str, 
        message: str,
        stream_callback: Optional[Callable] = None
    ) -> str:
        """
        Start a new agent session to process a user message.
        
        Args:
            session_id: The session ID
            message: User message to process
            stream_callback: Optional callback for streaming updates
            
        Returns:
            Agent session ID
        """
        self.logger.info(
            "Starting agent session",
            session_id=session_id,
            message_preview=message[:100]
        )
        
        # Check if session is already active
        if session_id in self._active_sessions:
            raise ValueError(f"Agent session {session_id} is already active")
        
        # Verify session exists and is active
        session = await self.session_service.get_session(session_id)
        if not session or not session.is_active:
            raise ValueError(f"Session {session_id} not found or not active")
        
        # Create user message
        await self.session_service.add_message(
            session_id=session_id,
            content=message,
            message_type=MessageType.USER
        )
        
        # Create agent session
        agent_session = AgentSession(
            session_id=session_id,
            anthropic_client=self.anthropic_client,
            tool_collection=self.tool_collection,
            session_service=self.session_service,
            websocket_manager=self.websocket_manager,
            system_prompt=self.system_prompt,
            model=self.model,
            max_tokens=self.max_tokens,
            stream_callback=stream_callback
        )
        
        self._active_sessions[session_id] = agent_session
        
        # Start processing in background
        asyncio.create_task(self._run_agent_session(session_id, message))
        
        return session_id
    
    async def stop_agent_session(self, session_id: str, reason: Optional[str] = None) -> bool:
        """
        Stop an active agent session.
        
        Args:
            session_id: The session ID
            reason: Optional reason for stopping
            
        Returns:
            True if session was stopped, False if not active
        """
        agent_session = self._active_sessions.get(session_id)
        if not agent_session:
            return False
        
        self.logger.info(
            "Stopping agent session",
            session_id=session_id,
            reason=reason
        )
        
        await agent_session.stop(reason)
        del self._active_sessions[session_id]
        
        return True
    
    async def get_agent_status(self, session_id: str) -> Optional[AgentStatus]:
        """Get the status of an agent session."""
        agent_session = self._active_sessions.get(session_id)
        if not agent_session:
            return None
        
        return agent_session.status
    
    async def list_active_sessions(self) -> List[str]:
        """Get list of active agent session IDs."""
        return list(self._active_sessions.keys())
    
    async def _run_agent_session(self, session_id: str, initial_message: str):
        """Run the agent session processing loop."""
        agent_session = self._active_sessions.get(session_id)
        if not agent_session:
            return
        
        try:
            await agent_session.process_message(initial_message)
        except Exception as e:
            self.logger.error(
                "Error in agent session",
                session_id=session_id,
                error=str(e),
                exc_info=True
            )
            await agent_session.handle_error(e)
        finally:
            # Clean up
            if session_id in self._active_sessions:
                del self._active_sessions[session_id]


class AgentSession(LoggingMixin):
    """
    Individual agent session for processing messages.
    Handles the conversation loop with Claude and tool execution.
    """
    
    def __init__(
        self,
        session_id: str,
        anthropic_client: anthropic.AsyncAnthropic,
        tool_collection: ToolCollection,
        session_service: SessionService,
        websocket_manager: WebSocketManager,
        system_prompt: str,
        model: str,
        max_tokens: int,
        stream_callback: Optional[Callable] = None
    ):
        self.session_id = session_id
        self.anthropic_client = anthropic_client
        self.tool_collection = tool_collection
        self.session_service = session_service
        self.websocket_manager = websocket_manager
        self.system_prompt = system_prompt
        self.model = model
        self.max_tokens = max_tokens
        self.stream_callback = stream_callback
        
        self.status = AgentStatus.IDLE
        self.started_at = datetime.utcnow()
        self.last_activity = datetime.utcnow()
        self.tool_calls_count = 0
        self.current_message = None
        self._stop_requested = False
    
    async def process_message(self, message: str):
        """Process a user message through the agent loop."""
        self.status = AgentStatus.PROCESSING
        self.current_message = message
        self.last_activity = datetime.utcnow()
        
        await self._emit_status_update()
        
        # Get conversation history
        messages = await self._build_conversation_history()
        
        # Start the conversation loop
        response_message = ""
        tool_calls = []
        
        try:
            # Create message with Anthropic
            async with self.anthropic_client.messages.stream(
                model=self.model,
                max_tokens=self.max_tokens,
                system=self.system_prompt,
                messages=messages,
                tools=self.tool_collection.to_params(),
            ) as stream:
                async for event in stream:
                    if self._stop_requested:
                        break
                    
                    await self._handle_stream_event(event, response_message, tool_calls)
            
            # Process final message
            final_message = await stream.get_final_message()
            await self._process_final_message(final_message)
            
        except Exception as e:
            await self.handle_error(e)
        
        self.status = AgentStatus.COMPLETED
        await self._emit_status_update()
    
    async def _handle_stream_event(self, event, response_message: str, tool_calls: List):
        """Handle individual stream events from Anthropic."""
        self.last_activity = datetime.utcnow()
        
        if event.type == "content_block_start":
            if event.content_block.type == "text":
                await self._emit_message_start()
        
        elif event.type == "content_block_delta":
            if event.delta.type == "text_delta":
                response_message += event.delta.text
                await self._emit_message_delta(event.delta.text)
        
        elif event.type == "content_block_stop":
            if hasattr(event.content_block, 'type') and event.content_block.type == "tool_use":
                tool_calls.append(event.content_block)
                await self._emit_tool_call(event.content_block)
    
    async def _process_final_message(self, message: BetaMessage):
        """Process the final message from Anthropic."""
        # Save assistant response
        if message.content:
            content_text = ""
            tool_calls = []
            
            for content_block in message.content:
                if isinstance(content_block, BetaTextBlock):
                    content_text += content_block.text
                elif isinstance(content_block, BetaToolUseBlock):
                    tool_calls.append(content_block)
            
            if content_text:
                await self.session_service.add_message(
                    session_id=self.session_id,
                    content=content_text,
                    message_type=MessageType.ASSISTANT
                )
            
            # Execute tool calls
            for tool_call in tool_calls:
                await self._execute_tool_call(tool_call)
    
    async def _execute_tool_call(self, tool_call: BetaToolUseBlock):
        """Execute a tool call and save the result."""
        self.status = AgentStatus.WAITING_FOR_TOOL
        self.tool_calls_count += 1
        await self._emit_status_update()
        
        try:
            # Save tool call message
            await self.session_service.add_message(
                session_id=self.session_id,
                content=json.dumps({
                    "name": tool_call.name,
                    "parameters": tool_call.input
                }),
                message_type=MessageType.TOOL_CALL,
                tool_name=tool_call.name,
                tool_call_id=tool_call.id
            )
            
            # Execute tool
            result = await self.tool_collection.run(
                name=tool_call.name,
                tool_input=tool_call.input
            )
            
            # Save tool result
            result_content = result.output if isinstance(result, ComputerToolResult) else str(result)
            await self.session_service.add_message(
                session_id=self.session_id,
                content=result_content,
                message_type=MessageType.TOOL_RESULT,
                tool_name=tool_call.name,
                tool_call_id=tool_call.id
            )
            
            # Emit tool result
            await self._emit_tool_result(tool_call.name, tool_call.id, result_content)
            
        except Exception as e:
            error_message = f"Tool execution failed: {str(e)}"
            await self.session_service.add_message(
                session_id=self.session_id,
                content=error_message,
                message_type=MessageType.ERROR,
                tool_name=tool_call.name,
                tool_call_id=tool_call.id,
                error_code="TOOL_EXECUTION_ERROR"
            )
            
            await self._emit_error(error_message)
    
    async def _build_conversation_history(self) -> List[Dict[str, Any]]:
        """Build conversation history for Anthropic API."""
        messages = await self.session_service.get_messages(self.session_id)
        
        conversation = []
        for msg in messages:
            if msg.message_type == MessageType.USER:
                conversation.append({
                    "role": "user",
                    "content": msg.content
                })
            elif msg.message_type == MessageType.ASSISTANT:
                conversation.append({
                    "role": "assistant", 
                    "content": msg.content
                })
        
        return conversation
    
    async def stop(self, reason: Optional[str] = None):
        """Stop the agent session."""
        self.logger.info("Stopping agent session", session_id=self.session_id, reason=reason)
        self._stop_requested = True
        self.status = AgentStatus.STOPPED
        await self._emit_status_update()
    
    async def handle_error(self, error: Exception):
        """Handle agent session errors."""
        self.logger.error(
            "Agent session error",
            session_id=self.session_id,
            error=str(error),
            exc_info=True
        )
        
        self.status = AgentStatus.ERROR
        await self._emit_error(str(error))
        
        # Save error message
        await self.session_service.add_message(
            session_id=self.session_id,
            content=f"Agent error: {str(error)}",
            message_type=MessageType.ERROR,
            error_code="AGENT_ERROR"
        )
    
    # WebSocket event emitters
    async def _emit_status_update(self):
        """Emit status update via WebSocket."""
        message = WebSocketMessage(
            event_type=WebSocketEventType.STATUS_UPDATE,
            session_id=self.session_id,
            data={
                "status": self.status.value,
                "tool_calls_count": self.tool_calls_count,
                "started_at": self.started_at.isoformat(),
                "last_activity": self.last_activity.isoformat(),
                "current_message": self.current_message
            }
        )
        await self.websocket_manager.broadcast_to_session(self.session_id, message.dict())
    
    async def _emit_message_start(self):
        """Emit message start event."""
        message = WebSocketMessage(
            event_type=WebSocketEventType.MESSAGE,
            session_id=self.session_id,
            data={"type": "start"}
        )
        await self.websocket_manager.broadcast_to_session(self.session_id, message.dict())
    
    async def _emit_message_delta(self, delta: str):
        """Emit message delta event."""
        message = WebSocketMessage(
            event_type=WebSocketEventType.MESSAGE,
            session_id=self.session_id,
            data={"type": "delta", "content": delta}
        )
        await self.websocket_manager.broadcast_to_session(self.session_id, message.dict())
    
    async def _emit_tool_call(self, tool_call: BetaToolUseBlock):
        """Emit tool call event."""
        message = WebSocketMessage(
            event_type=WebSocketEventType.TOOL_CALL,
            session_id=self.session_id,
            data={
                "id": tool_call.id,
                "name": tool_call.name,
                "parameters": tool_call.input
            }
        )
        await self.websocket_manager.broadcast_to_session(self.session_id, message.dict())
    
    async def _emit_tool_result(self, tool_name: str, call_id: str, result: str):
        """Emit tool result event."""
        message = WebSocketMessage(
            event_type=WebSocketEventType.TOOL_RESULT,
            session_id=self.session_id,
            data={
                "call_id": call_id,
                "name": tool_name,
                "result": result
            }
        )
        await self.websocket_manager.broadcast_to_session(self.session_id, message.dict())
    
    async def _emit_error(self, error: str):
        """Emit error event."""
        message = WebSocketMessage(
            event_type=WebSocketEventType.ERROR,
            session_id=self.session_id,
            data={"error": error}
        )
        await self.websocket_manager.broadcast_to_session(self.session_id, message.dict())