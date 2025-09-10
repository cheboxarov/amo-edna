import logging
from typing import Optional
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from domain.models import ConversationLink, MessageLink
from use_cases.route_messages import ConversationLinkRepository, MessageLinkRepository
from infrastructure.db.models import ConversationLinkORM, MessageLinkORM
from infrastructure.db.mappers import (
    to_conversation_link_model,
    to_conversation_link_orm,
    to_message_link_model,
    to_message_link_orm,
)
from core.error_logger import get_error_reporter

logger = logging.getLogger(__name__)


class SQLiteConversationLinkRepository(ConversationLinkRepository):
    """SQLAlchemy реализация репозитория связей между чатами"""

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]):
        self._session_factory = session_factory
        self._logger = logger

    async def initialize(self) -> None:
        """Инициализация репозитория (не требуется для SQLAlchemy)"""
        pass

    async def get_edna_conversation_id(self, amocrm_chat_id: str) -> Optional[str]:
        """Получить ID разговора Edna по ID чата AmoCRM"""
        try:
            async with self._session_factory() as session:
                stmt = select(ConversationLinkORM).where(
                    ConversationLinkORM.amocrm_chat_id == amocrm_chat_id
                )
                result = await session.execute(stmt)
                orm_obj = result.scalar_one_or_none()

                if orm_obj:
                    return orm_obj.edna_conversation_id

                return None
        except Exception as e:
            self._logger.error(
                f"Ошибка при получении edna_conversation_id для chat_id={amocrm_chat_id}: {e}"
            )
            try:
                error_reporter = get_error_reporter()
                error_reporter.log_error(
                    error=e,
                    context={"operation": "get_edna_conversation_id", "amocrm_chat_id": amocrm_chat_id}
                )
            except Exception:
                pass
            return None

    async def get_amocrm_chat_id(self, edna_conversation_id: str) -> Optional[str]:
        """Получить ID чата AmoCRM по ID разговора Edna"""
        try:
            async with self._session_factory() as session:
                stmt = select(ConversationLinkORM).where(
                    ConversationLinkORM.edna_conversation_id == edna_conversation_id
                )
                result = await session.execute(stmt)
                orm_obj = result.scalar_one_or_none()

                if orm_obj:
                    return orm_obj.amocrm_chat_id

                return None
        except Exception as e:
            self._logger.error(
                f"Ошибка при получении amocrm_chat_id для conversation_id={edna_conversation_id}: {e}"
            )
            try:
                error_reporter = get_error_reporter()
                error_reporter.log_error(
                    error=e,
                    context={"operation": "get_amocrm_chat_id", "edna_conversation_id": edna_conversation_id}
                )
            except Exception:
                pass
            return None

    async def get_phone_by_chat_id(self, amocrm_chat_id: str) -> Optional[str]:
        """Получить номер телефона по ID чата AmoCRM"""
        try:
            async with self._session_factory() as session:
                stmt = select(ConversationLinkORM.phone).where(
                    ConversationLinkORM.amocrm_chat_id == amocrm_chat_id
                )
                result = await session.execute(stmt)
                phone = result.scalar_one_or_none()
                return phone
        except Exception as e:
            self._logger.error(
                f"Ошибка при получении телефона для chat_id={amocrm_chat_id}: {e}"
            )
            try:
                error_reporter = get_error_reporter()
                error_reporter.log_error(
                    error=e,
                    context={"operation": "get_phone_by_chat_id", "amocrm_chat_id": amocrm_chat_id}
                )
            except Exception:
                pass
            return None

    async def get_chat_id_by_phone(self, phone_number: str) -> Optional[str]:
        """Получить ID чата AmoCRM по номеру телефона"""
        try:
            async with self._session_factory() as session:
                stmt = select(ConversationLinkORM.amocrm_chat_id).where(
                    ConversationLinkORM.phone == phone_number
                )
                result = await session.execute(stmt)
                chat_id = result.scalar_one_or_none()
                return chat_id
        except Exception as e:
            self._logger.error(
                f"Ошибка при получении chat_id для телефона {phone_number}: {e}"
            )
            try:
                error_reporter = get_error_reporter()
                error_reporter.log_error(
                    error=e,
                    context={"operation": "get_chat_id_by_phone", "phone_number": phone_number}
                )
            except Exception:
                pass
            return None

    async def save_link(self, link: ConversationLink) -> None:
        """Сохранить связь между чатами"""
        try:
            async with self._session_factory() as session:
                async with session.begin():
                    orm_obj = to_conversation_link_orm(link)
                    # Используем merge для upsert
                    session.merge(orm_obj)
                    await session.commit()

            self._logger.debug(
                f"Сохранена связь: amocrm_chat_id={link.amocrm_chat_id} -> edna_conversation_id={link.edna_conversation_id}"
            )
        except Exception as e:
            self._logger.error(f"Ошибка при сохранении связи: {e}")
            try:
                error_reporter = get_error_reporter()
                error_reporter.log_error(
                    error=e,
                    context={
                        "operation": "save_link",
                        "amocrm_chat_id": link.amocrm_chat_id,
                        "edna_conversation_id": link.edna_conversation_id
                    }
                )
            except Exception:
                pass
            raise

    async def save_phone_for_chat(self, amocrm_chat_id: str, phone_number: str) -> None:
        """Сохранить номер телефона для чата AmoCRM"""
        try:
            async with self._session_factory() as session:
                async with session.begin():
                    stmt = (
                        update(ConversationLinkORM)
                        .where(ConversationLinkORM.amocrm_chat_id == amocrm_chat_id)
                        .values(phone=phone_number)
                    )
                    await session.execute(stmt)
                    await session.commit()

            self._logger.debug(f"Сохранен телефон {phone_number} для чата {amocrm_chat_id}")
        except Exception as e:
            self._logger.error(f"Ошибка при сохранении телефона для чата: {e}")
            try:
                error_reporter = get_error_reporter()
                error_reporter.log_error(
                    error=e,
                    context={
                        "operation": "save_phone_for_chat",
                        "amocrm_chat_id": amocrm_chat_id,
                        "phone_number": phone_number
                    }
                )
            except Exception:
                pass
            raise


class SQLiteMessageLinkRepository(MessageLinkRepository):
    """SQLAlchemy реализация репозитория связей между сообщениями"""

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]):
        self._session_factory = session_factory
        self._logger = logger

    async def initialize(self) -> None:
        """Инициализация репозитория (не требуется для SQLAlchemy)"""
        pass

    async def get_link_by_source_id(self, source_message_id: str) -> Optional[MessageLink]:
        """Получить связь по ID исходного сообщения"""
        try:
            async with self._session_factory() as session:
                stmt = select(MessageLinkORM).where(
                    MessageLinkORM.source_message_id == source_message_id
                )
                result = await session.execute(stmt)
                orm_obj = result.scalar_one_or_none()

                if orm_obj:
                    return to_message_link_model(orm_obj)

                return None
        except Exception as e:
            self._logger.error(
                f"Ошибка при получении связи для source_message_id={source_message_id}: {e}"
            )
            try:
                error_reporter = get_error_reporter()
                error_reporter.log_error(
                    error=e,
                    context={"operation": "get_link_by_source_id", "source_message_id": source_message_id}
                )
            except Exception:
                pass
            return None

    async def save_link(self, link: MessageLink) -> None:
        """Сохранить связь между сообщениями"""
        try:
            async with self._session_factory() as session:
                async with session.begin():
                    orm_obj = to_message_link_orm(link)
                    # Используем merge для upsert
                    session.merge(orm_obj)
                    await session.commit()

            self._logger.debug(
                f"Сохранена связь сообщений: source_id={link.source_message_id} -> target_id={link.target_message_id}"
            )
        except Exception as e:
            self._logger.error(f"Ошибка при сохранении связи сообщений: {e}")
            try:
                error_reporter = get_error_reporter()
                error_reporter.log_error(
                    error=e,
                    context={
                        "operation": "save_link",
                        "source_message_id": link.source_message_id,
                        "target_message_id": link.target_message_id
                    }
                )
            except Exception:
                pass
            raise
