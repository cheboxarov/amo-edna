from __future__ import annotations
import logging
from typing import Protocol, Optional
from domain.models import Message, MessageLink, ConversationLink
from domain.ports.message_provider import MessageProvider
from use_cases.mappers.amocrm_to_domain import amocrm_to_domain
from use_cases.mappers.edna_to_domain import edna_message_to_domain
from presentation.schemas.amocrm import AmoIncomingWebhook
from presentation.schemas.edna import EdnaIncomingMessage


class ConversationLinkRepository(Protocol):
	async def get_edna_conversation_id(self, amocrm_chat_id: str) -> str | None: ...
	async def get_amocrm_chat_id(self, edna_conversation_id: str) -> str | None: ...
	async def save_link(self, link: ConversationLink) -> None: ...


class MessageLinkRepository(Protocol):
	async def get_link_by_source_id(self, source_message_id: str) -> MessageLink | None: ...
	async def save_link(self, link: MessageLink) -> None: ...


class RouteMessageFromEdnaUseCase:
	def __init__(
		self,
		amocrm_provider: MessageProvider,
		conv_links: ConversationLinkRepository,
		msg_links: MessageLinkRepository,
		logger: Optional[logging.Logger] = None,
	) -> None:
		self._amocrm_provider = amocrm_provider
		self._conv_links = conv_links
		self._msg_links = msg_links
		self._logger = logger or logging.getLogger(__name__)

	async def execute(self, payload: EdnaIncomingMessage) -> None:
		self._logger.info("Routing message from Edna, payload=%s", payload.model_dump_json())
		message = edna_message_to_domain(payload)
		self._logger.debug("Mapped Edna message to domain model: %s", message.model_dump_json())

		target_conversation_id = await self._conv_links.get_amocrm_chat_id(
			message.source_conversation_id
		)

		if not target_conversation_id:
			self._logger.warning(
				"No AmoCRM chat link found for Edna conversation_id=%s. Creating a new one.",
				message.source_conversation_id,
			)
			# Используем ID из Edna как временный ID для создания чата в AmoCRM
			message.target_conversation_id = message.source_conversation_id
		else:
			self._logger.info(
				"Found linked AmoCRM chat_id=%s for Edna conversation_id=%s",
				target_conversation_id,
				message.source_conversation_id,
			)
			message.target_conversation_id = target_conversation_id

		try:
			result = await self._amocrm_provider.send_message(message)
			self._logger.info(
				"Message sent to AmoCRM, result: %s", result.model_dump_json()
			)

			# Если чат был новым, сохраняем связь
			if not target_conversation_id:
				new_link = ConversationLink(
					edna_conversation_id=message.source_conversation_id,
					amocrm_chat_id=result.reference.conversation_id,
				)
				await self._conv_links.save_link(new_link)
				self._logger.info("Saved new conversation link: %s", new_link.model_dump_json())

			# Сохраняем связь ID сообщений
			msg_link = MessageLink(
				source_provider=message.source_provider,
				source_message_id=message.source_message_id,
				target_provider=result.reference.provider,
				target_message_id=result.reference.message_id,
				target_conversation_id=result.reference.conversation_id,
			)
			await self._msg_links.save_link(msg_link)
			self._logger.info("Saved message link: %s", msg_link.model_dump_json())

		except Exception:
			self._logger.exception(
				"Failed to send message to AmoCRM for Edna conversation_id=%s",
				message.source_conversation_id,
			)


class RouteMessageFromAmoCrmUseCase:
	def __init__(
		self,
		edna_provider: MessageProvider,
		conv_links: ConversationLinkRepository,
		msg_links: MessageLinkRepository,
	) -> None:
		self._edna_provider = edna_provider
		self._conv_links = conv_links
		self._msg_links = msg_links

	async def execute(self, payload: AmoIncomingWebhook) -> None:
		message = amocrm_to_domain(payload)
		target_conversation_id = await self._conv_links.get_edna_conversation_id(
			message.source_conversation_id
		)
		if target_conversation_id:
			message.target_conversation_id = target_conversation_id
			message.recipient.provider_user_id = target_conversation_id
			result = await self._edna_provider.send_message(message)
			# Сохраняем связь ID сообщений
			link = MessageLink(
				source_provider=message.source_provider,
				source_message_id=message.source_message_id,
				target_provider=result.reference.provider,
				target_message_id=result.reference.message_id,
				target_conversation_id=result.reference.conversation_id,
			)
			await self._msg_links.save_link(link)
