"""
Database configuration and connection management.
Provides async SQLAlchemy engine, session factory, and database initialization.
"""

from typing import AsyncGenerator, Optional

from sqlalchemy import create_engine, MetaData
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import structlog

from app.core.config import get_settings

logger = structlog.get_logger(__name__)
settings = get_settings()

# Database metadata and base model
metadata = MetaData()
Base = declarative_base(metadata=metadata)

# Global engine instances
_async_engine: Optional[AsyncEngine] = None
_sync_engine = None
_async_session_factory: Optional[async_sessionmaker[AsyncSession]] = None


def get_sync_engine():
    """Get synchronous SQLAlchemy engine (for migrations)."""
    global _sync_engine
    if _sync_engine is None:
        _sync_engine = create_engine(
            settings.DATABASE_URL,
            echo=settings.DEBUG,
            pool_pre_ping=True,
        )
    return _sync_engine


def get_async_engine() -> AsyncEngine:
    """Get async SQLAlchemy engine."""
    global _async_engine
    if _async_engine is None:
        _async_engine = create_async_engine(
            settings.DATABASE_URL_ASYNC,
            echo=settings.DEBUG,
            pool_pre_ping=True,
            pool_recycle=3600,  # Recycle connections every hour
        )
        logger.info("Created async database engine", url=settings.DATABASE_URL_ASYNC)
    return _async_engine


def get_async_session_factory() -> async_sessionmaker[AsyncSession]:
    """Get async session factory."""
    global _async_session_factory
    if _async_session_factory is None:
        engine = get_async_engine()
        _async_session_factory = async_sessionmaker(
            engine,
            class_=AsyncSession,
            expire_on_commit=False,
        )
        logger.info("Created async session factory")
    return _async_session_factory


async def get_async_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Dependency to get async database session.
    Use this as a FastAPI dependency.
    """
    session_factory = get_async_session_factory()
    async with session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def create_db_and_tables():
    """Create database and tables."""
    try:
        # Import all models to ensure they're registered
        from app.models.database import Session, Message  # noqa
        
        engine = get_async_engine()
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        
        logger.info("Database tables created successfully")
    except Exception as e:
        logger.error("Failed to create database tables", error=str(e))
        raise


async def drop_db_and_tables():
    """Drop all database tables (for testing)."""
    try:
        engine = get_async_engine()
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
        
        logger.info("Database tables dropped successfully")
    except Exception as e:
        logger.error("Failed to drop database tables", error=str(e))
        raise


class DatabaseManager:
    """Database manager for handling connections and sessions."""
    
    def __init__(self):
        self.engine = get_async_engine()
        self.session_factory = get_async_session_factory()
    
    async def get_session(self) -> AsyncSession:
        """Get a new database session."""
        return self.session_factory()
    
    async def close(self):
        """Close database connections."""
        if self.engine:
            await self.engine.dispose()
            logger.info("Database connections closed")
    
    async def health_check(self) -> bool:
        """Check database connectivity."""
        try:
            async with self.session_factory() as session:
                await session.execute("SELECT 1")
            return True
        except Exception as e:
            logger.error("Database health check failed", error=str(e))
            return False


# Global database manager instance
db_manager = DatabaseManager()