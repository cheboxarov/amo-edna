from use_cases import ConversationLinkRepository
from domain.models import ConversationLink, MessageLink
import logging


class InMemoryConversationLinkRepository(ConversationLinkRepository):
	def __init__(self):
		self._links: dict[str, str] = {}  # amocrm_chat_id <-> edna_conversation_id
		self._phones: dict[str, str] = {}  # amocrm_chat_id -> phone_number

	async def get_edna_conversation_id(self, amocrm_chat_id: str) -> str | None:
		return self._links.get(amocrm_chat_id)

	async def get_amocrm_chat_id(self, edna_conversation_id: str) -> str | None:
		# Для двунаправленного поиска
		for amocrm_id, edna_id in self._links.items():
			if edna_id == edna_conversation_id:
				return amocrm_id
		return None

	async def get_phone_by_chat_id(self, amocrm_chat_id: str) -> str | None:
		"""Получить номер телефона по ID чата AmoCRM"""
		return self._phones.get(amocrm_chat_id)

	async def save_link(self, link: ConversationLink) -> None:
		self._links[link.amocrm_chat_id] = link.edna_conversation_id

	async def save_phone_for_chat(self, amocrm_chat_id: str, phone_number: str) -> None:
		"""Сохранить номер телефона для чата AmoCRM"""
		self._phones[amocrm_chat_id] = phone_number


class InMemoryMessageLinkRepository:
	def __init__(self):
		self._links: dict[str, MessageLink] = {}  # source_message_id -> MessageLink
		self._logger = logging.getLogger("message_links_repo")

	async def get_link_by_source_id(self, source_message_id: str) -> MessageLink | None:
		link = self._links.get(source_message_id)
		self._logger.debug(
			"Поиск связи по source_message_id=%s: найдено=%s",
			source_message_id, link is not None
		)
		if link:
			self._logger.debug(
				"Найденная связь: source_provider=%s, source_id=%s -> target_provider=%s, target_id=%s",
				link.source_provider, link.source_message_id, link.target_provider, link.target_message_id
			)
		else:
			self._logger.debug("Всего сохраненных связей: %d", len(self._links))
			if self._links:
				self._logger.debug("Сохраненные source_ids: %s", list(self._links.keys())[:5])  # Показываем первые 5
		return link

	async def save_link(self, link: MessageLink) -> None:
		self._logger.debug(
			"Сохраняем связь: source_provider=%s, source_id=%s -> target_provider=%s, target_id=%s",
			link.source_provider, link.source_message_id, link.target_provider, link.target_message_id
		)
		self._links[link.source_message_id] = link
		self._logger.debug("Всего связей после сохранения: %d", len(self._links))