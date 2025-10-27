"""
Structured logging configuration using structlog.
Provides consistent, structured logging across the application.
"""

import logging
import sys
from typing import Any, Dict

import structlog
from structlog.stdlib import LoggerFactory

from app.core.config import get_settings


def setup_logging() -> None:
    """Configure structured logging for the application."""
    settings = get_settings()
    
    # Configure structlog
    structlog.configure(
        processors=[
            # Add timestamp
            structlog.stdlib.filter_by_level,
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            structlog.stdlib.PositionalArgumentsFormatter(),
            structlog.processors.TimeStamper(fmt="ISO"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.UnicodeDecoder(),
            # JSON output for production, human-readable for development
            structlog.processors.JSONRenderer() 
            if settings.is_production 
            else structlog.dev.ConsoleRenderer(colors=True)
        ],
        context_class=dict,
        logger_factory=LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )
    
    # Configure standard library logging
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=getattr(logging, settings.LOG_LEVEL.upper()),
    )
    
    # Set log levels for third-party libraries
    logging.getLogger("uvicorn.error").setLevel(logging.INFO)
    logging.getLogger("uvicorn.access").setLevel(logging.INFO)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
    logging.getLogger("anthropic").setLevel(logging.INFO)


def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    """Get a structured logger instance."""
    return structlog.get_logger(name)


class LoggingMixin:
    """Mixin to add logging capabilities to classes."""
    
    @property
    def logger(self) -> structlog.stdlib.BoundLogger:
        """Get logger for this class."""
        return get_logger(self.__class__.__name__)


def log_function_call(func_name: str, **kwargs: Any) -> Dict[str, Any]:
    """Create a log context for function calls."""
    return {
        "function": func_name,
        "parameters": {k: v for k, v in kwargs.items() if not k.startswith("_")}
    }


def log_request(method: str, url: str, **kwargs: Any) -> Dict[str, Any]:
    """Create a log context for HTTP requests."""
    return {
        "request": {
            "method": method,
            "url": url,
            **kwargs
        }
    }


def log_database_operation(operation: str, table: str, **kwargs: Any) -> Dict[str, Any]:
    """Create a log context for database operations."""
    return {
        "database": {
            "operation": operation,
            "table": table,
            **kwargs
        }
    }


def log_websocket_event(event: str, session_id: str, **kwargs: Any) -> Dict[str, Any]:
    """Create a log context for WebSocket events."""
    return {
        "websocket": {
            "event": event,
            "session_id": session_id,
            **kwargs
        }
    }