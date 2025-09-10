import logging
from pathlib import Path
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy import event
from .models import Base

logger = logging.getLogger(__name__)


def create_database_engine(db_url: str):
    """Создает асинхронный движок SQLAlchemy для SQLite"""
    engine = create_async_engine(
        db_url,
        echo=False,  # Установить True для отладки SQL запросов
        pool_pre_ping=True,
    )

    # Настройки SQLite для лучшей производительности и надежности
    @event.listens_for(engine.sync_engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA synchronous=NORMAL")
        cursor.close()

    return engine


async def init_db(engine):
    """Инициализирует базу данных - создает все таблицы"""
    try:
        logger.info("Инициализация базы данных...")

        # Создаем директорию для БД если она не существует
        db_path = Path("data")
        db_path.mkdir(exist_ok=True)

        # Создаем все таблицы
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        logger.info("База данных успешно инициализирована")
    except Exception as e:
        logger.error(f"Ошибка при инициализации базы данных: {e}")
        raise


def create_session_factory(engine):
    """Создает фабрику асинхронных сессий"""
    return async_sessionmaker(
        bind=engine,
        class_=AsyncSession,
        expire_on_commit=False
    )
