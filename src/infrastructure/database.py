"""Подключение к БД"""

from sqlalchemy import NullPool
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import declarative_base

DATABASE_URL = "postgresql+asyncpg://postgres:postgres@db:5432/events_db"

# Создание асинхронного двигателя
engine = create_async_engine(DATABASE_URL, poolclass=NullPool, echo=False)

# Фабрика сессий
async_session = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)

# Базовый класс для моделей
Base = declarative_base()


async def get_db() -> AsyncSession:
    async with async_session() as session:
        yield session
