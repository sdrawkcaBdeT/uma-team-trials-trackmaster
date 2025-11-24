import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from trackmaster.config import settings

logger = logging.getLogger(__name__)

class DatabaseSessionManager:
    def __init__(self):
        self._engine = None
        self._sessionmaker = None

    def init(self, host: str = "localhost"):
        # Construct the async database URL
        # Note: We use the postgresql+asyncpg driver
        db_url = f"postgresql+asyncpg://{settings.DB_USER}:{settings.DB_PASSWORD}@{host}:{settings.DB_PORT}/{settings.DB_NAME}"
        
        self._engine = create_async_engine(
            db_url,
            echo=False, # Set to True for SQL debugging
            pool_size=10,
            max_overflow=20
        )
        
        self._sessionmaker = async_sessionmaker(
            bind=self._engine,
            expire_on_commit=False,
            class_=AsyncSession
        )
        logger.info("Database session manager initialized (Async).")

    async def close(self):
        if self._engine is None:
            return
        await self._engine.dispose()
        self._engine = None
        self._sessionmaker = None
        logger.info("Database session manager closed.")

    @asynccontextmanager
    async def session(self) -> AsyncGenerator[AsyncSession, None]:
        if self._sessionmaker is None:
            raise Exception("DatabaseSessionManager is not initialized")

        session = self._sessionmaker()
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()

# Global instance
db_manager = DatabaseSessionManager()
