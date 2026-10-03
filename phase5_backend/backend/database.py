# phase5_backend/backend/database.py
"""
SQLAlchemy Async Database Layer.
Connection pooling, session management, migration support.
"""
from contextlib import asynccontextmanager
from typing import AsyncGenerator, Optional
from pathlib import Path
import logging

from sqlalchemy.ext.asyncio import (
    create_async_engine, 
    AsyncSession, 
    async_sessionmaker,
    AsyncEngine
)
from sqlalchemy import text

from .config import get_settings
from .models import Base

logger = logging.getLogger(__name__)

class DatabaseManager:
    def __init__(self):
        self.settings = get_settings()
        self.engine: Optional[AsyncEngine] = None
        self.session_factory: Optional[async_sessionmaker[AsyncSession]] = None
    
    async def initialize(self):
        """Create engine and session factory."""
        db_url = self.settings.database.url
        if "sqlite" in db_url and "///" in db_url:
            db_path_str = db_url.split("///")[-1]
            if db_path_str and db_path_str != ":memory:":
                Path(db_path_str).parent.mkdir(parents=True, exist_ok=True)
        
        kwargs = {
            "echo": self.settings.database.echo,
        }
        if "sqlite" in db_url:
            from sqlalchemy.pool import StaticPool
            kwargs["connect_args"] = {"check_same_thread": False, "timeout": 30}
            if ":memory:" in db_url:
                kwargs["poolclass"] = StaticPool
        else:
            kwargs.update({
                "pool_size": self.settings.database.pool_size,
                "max_overflow": self.settings.database.max_overflow,
                "pool_timeout": self.settings.database.pool_timeout,
                "pool_pre_ping": True,
            })
            
        self.engine = create_async_engine(db_url, **kwargs)
        
        self.session_factory = async_sessionmaker(
            self.engine,
            class_=AsyncSession,
            expire_on_commit=False,
            autoflush=False,
        )
        
        logger.info("Database engine initialized")
    
    async def create_tables(self):
        """Create all tables (development only - use Alembic for prod)."""
        if not self.engine:
            await self.initialize()
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
            await conn.run_sync(Base.metadata.create_all)
        logger.info("Database tables created")
    
    async def drop_tables(self):
        """Drop all tables (testing only)."""
        if not self.engine:
            await self.initialize()
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
        logger.info("Database tables dropped")
    
    async def close(self):
        """Close engine."""
        if self.engine:
            await self.engine.dispose()
            self.engine = None
            self.session_factory = None
            logger.info("Database engine closed")
    
    @asynccontextmanager
    async def session(self) -> AsyncGenerator[AsyncSession, None]:
        """Get database session with automatic commit/rollback."""
        if not self.session_factory or not self.engine:
            await self.initialize()
        
        async with self.session_factory() as session:
            try:
                yield session
                if session.is_active:
                    await session.commit()
            except Exception:
                await session.rollback()
                raise
    
    async def health_check(self) -> bool:
        """Check database connectivity."""
        try:
            async with self.session() as session:
                await session.execute(text("SELECT 1"))
            return True
        except Exception as e:
            logger.error(f"Database health check failed: {e}")
            return False


# Global instance
db_manager = DatabaseManager()


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency for database session."""
    async with db_manager.session() as session:
        yield session
