import logging
from typing import Protocol, Optional
from domain.models import (
    ChatCreationRequest,
    ChatCreationResult,
    ChatUser,
    ChatUserProfile,
    ChatSource,
    ConversationLink,
)
from domain.ports.message_provider import MessageProvider
from core.config import AmoCrmSettings
from core.error_logger import get_error_reporter


class ConversationLinkRepository(Protocol):
    async def get_edna_conversation_id(self, amocrm_chat_id: str) -> str | None: ...
    async def get_amocrm_chat_id(self, edna_conversation_id: str) -> str | None: ...
    async def get_phone_by_chat_id(self, amocrm_chat_id: str) -> str | None: ...
    async def save_link(self, link: ConversationLink) -> None: ...
    async def save_phone_for_chat(self, amocrm_chat_id: str, phone_number: str) -> None: ...


class CreateChatUseCase:
    """
    Use case для создания чата в AmoCRM при получении сообщения от Edna.

    Логика:
    1. Проверить, существует ли уже чат для данного номера телефона
    2. Если нет - создать новый чат с номером телефона из Edna
    3. Сохранить связь между Edna conversation_id и AmoCRM chat_id
    4. Вернуть ID созданного/найденного чата
    """

    def __init__(
        self,
        amocrm_provider: MessageProvider,
        conv_links: ConversationLinkRepository,
        amocrm_settings: AmoCrmSettings,
        logger: Optional[logging.Logger] = None,
    ) -> None:
        self._amocrm_provider = amocrm_provider
        self._conv_links = conv_links
        self._amocrm_settings = amocrm_settings
        self._logger = logger or logging.getLogger(__name__)

    async def execute(
        self,
        edna_conversation_id: str,
        phone_number: str,
        user_name: Optional[str] = None,
        source_external_id: Optional[str] = None
    ) -> ChatCreationResult:
        """
        Создает чат в AmoCRM для номера телефона из Edna.

        Args:
            edna_conversation_id: ID разговора в Edna
            phone_number: Номер телефона клиента
            user_name: Имя пользователя (опционально)
            source_external_id: ID источника для маршрутизации (опционально)

        Returns:
            ChatCreationResult: Результат создания чата
        """
        self._logger.debug(
            "Начало создания чата: edna_conversation_id=%s, phone=%s, user_name=%s",
            edna_conversation_id,
            phone_number,
            user_name
        )

        # Проверяем, есть ли уже чат для этого номера телефона
        existing_chat_id = await self._find_existing_chat_by_phone(phone_number)

        if existing_chat_id:
            self._logger.info(
                "Найден существующий чат для номера %s: chat_id=%s",
                phone_number,
                existing_chat_id
            )

            # Сохраняем связь между Edna conversation и существующим AmoCRM чатом
            link = ConversationLink(
                edna_conversation_id=edna_conversation_id,
                amocrm_chat_id=existing_chat_id,
            )
            await self._conv_links.save_link(link)

            # Возвращаем результат с существующим чатом
            return ChatCreationResult(
                id=existing_chat_id,
                user=ChatUser(
                    id=f"user_{phone_number}",
                    name=user_name or phone_number,
                    profile=ChatUserProfile(phone=phone_number)
                ),
                conversation_id=edna_conversation_id
            )

        # Создаем новый чат
        self._logger.info(
            "Создание нового чата для номера %s в AmoCRM",
            phone_number
        )

        # Формируем запрос на создание чата
        user_id = f"edna_{phone_number}"  # Уникальный ID для пользователя
        user_name_final = user_name or f"Клиент {phone_number}"

        user = ChatUser(
            id=user_id,
            name=user_name_final,
            profile=ChatUserProfile(phone=phone_number)
        )

        request = ChatCreationRequest(
            conversation_id=edna_conversation_id,
            user=user
        )

        # Добавляем источник чата
        source_id = source_external_id or self._amocrm_settings.default_chat_source_external_id
        if source_id:
            request.source = ChatSource(external_id=source_id)

        # Создаем чат через AmoCRM провайдер
        # Примечание: нам нужно добавить метод create_chat в интерфейс MessageProvider
        # или использовать прямой доступ к AmoCrmHttpClient
        try:
            if hasattr(self._amocrm_provider, 'create_chat'):
                result = await self._amocrm_provider.create_chat(request)
            else:
                raise AttributeError("AmoCRM provider does not support chat creation")
        except Exception as e:
            self._logger.error(
                "Failed to create chat in AmoCRM for phone=%s: %s",
                phone_number,
                str(e)
            )

            try:
                error_reporter = get_error_reporter()
                error_reporter.log_chat_creation_error(
                    error=e,
                    phone_number=phone_number,
                    conversation_id=edna_conversation_id,
                    provider="amocrm",
                    error_details="Failed to create chat via API"
                )
            except Exception as report_error:
                self._logger.error("Не удалось создать отчет об ошибке создания чата: %s", str(report_error))

            raise

        # Сохраняем связь между Edna conversation и новым AmoCRM чатом
        link = ConversationLink(
            edna_conversation_id=edna_conversation_id,
            amocrm_chat_id=result.id,
        )
        await self._conv_links.save_link(link)

        # Сохраняем номер телефона для чата
        await self._conv_links.save_phone_for_chat(result.id, phone_number)

        self._logger.info(
            "Чат успешно создан и связан: edna_conversation_id=%s -> amocrm_chat_id=%s, phone=%s",
            edna_conversation_id,
            result.id,
            phone_number
        )

        return result

    async def _find_existing_chat_by_phone(self, phone_number: str) -> Optional[str]:
        """
        Ищет существующий чат в AmoCRM по номеру телефона.

        Args:
            phone_number: Номер телефона для поиска

        Returns:
            ID чата в AmoCRM или None, если чат не найден
        """
        # Используем репозиторий для поиска существующего чата по номеру телефона
        return await self._conv_links.get_chat_id_by_phone(phone_number)
