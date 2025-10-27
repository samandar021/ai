"""
FastAPI application entry point for Computer Use Agent Backend.
"""

import asyncio
import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse
import structlog

from app.api.v1.endpoints import sessions, messages, websocket
from app.core.config import get_settings
from app.core.logging import setup_logging
from app.db.database import create_db_and_tables, get_async_engine


# Setup structured logging
setup_logging()
logger = structlog.get_logger(__name__)

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """
    Async context manager for FastAPI lifespan events.
    Handles startup and shutdown tasks.
    """
    # Startup
    logger.info("Starting Computer Use Agent Backend", version=app.version)
    
    # Initialize database
    try:
        await create_db_and_tables()
        logger.info("Database initialized successfully")
    except Exception as e:
        logger.error("Failed to initialize database", error=str(e))
        raise
    
    # Startup complete
    logger.info("Application startup complete")
    
    yield
    
    # Shutdown
    logger.info("Shutting down Computer Use Agent Backend")
    
    # Close database connections
    engine = get_async_engine()
    if engine:
        await engine.dispose()
        logger.info("Database connections closed")
    
    logger.info("Application shutdown complete")


def create_application() -> FastAPI:
    """Create and configure FastAPI application."""
    
    app = FastAPI(
        title="Computer Use Agent Backend",
        description="A production-ready FastAPI backend for Anthropic's Computer Use capabilities",
        version="1.0.0",
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
        lifespan=lifespan,
    )
    
    # Add trusted host middleware
    if not settings.DEBUG:
        app.add_middleware(
            TrustedHostMiddleware,
            allowed_hosts=["localhost", "127.0.0.1", "0.0.0.0"]
        )
    
    # Add CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.ALLOWED_ORIGINS,
        allow_credentials=True,
        allow_methods=settings.ALLOWED_METHODS,
        allow_headers=settings.ALLOWED_HEADERS,
    )
    
    # Global exception handler
    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        """Global exception handler for unhandled exceptions."""
        logger.error(
            "Unhandled exception",
            method=request.method,
            url=str(request.url),
            error=str(exc),
            exc_info=True
        )
        
        if settings.DEBUG:
            return JSONResponse(
                status_code=500,
                content={
                    "detail": "Internal server error",
                    "error": str(exc),
                    "type": type(exc).__name__
                }
            )
        else:
            return JSONResponse(
                status_code=500,
                content={"detail": "Internal server error"}
            )
    
    # Health check endpoint
    @app.get("/health")
    async def health_check():
        """Health check endpoint."""
        return {
            "status": "healthy",
            "version": app.version,
            "environment": settings.ENVIRONMENT
        }
    
    # Root endpoint
    @app.get("/")
    async def root():
        """Root endpoint with API information."""
        return {
            "message": "Computer Use Agent Backend API",
            "version": app.version,
            "docs_url": "/docs",
            "redoc_url": "/redoc"
        }
    
    # Include API routers
    app.include_router(
        sessions.router,
        prefix="/api/v1",
        tags=["sessions"]
    )
    
    app.include_router(
        messages.router,
        prefix="/api/v1",
        tags=["messages"]
    )
    
    app.include_router(
        websocket.router,
        prefix="/api/v1",
        tags=["websocket"]
    )
    
    return app


# Create the FastAPI application instance
app = create_application()


if __name__ == "__main__":
    import uvicorn
    
    # Run the application
    uvicorn.run(
        "app.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.RELOAD,
        log_level=settings.LOG_LEVEL.lower(),
        access_log=settings.ACCESS_LOG,
        workers=settings.WORKERS if not settings.RELOAD else 1,
    )