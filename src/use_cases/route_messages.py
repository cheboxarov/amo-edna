from __future__ import annotations
from typing import Protocol
from domain.models import Message, MessageLink
from domain.ports.message_provider import MessageProvider
from use_cases.mappers.amocrm_to_domain import amocrm_to_domain
from use_cases.mappers.edna_to_domain import edna_message_to_domain
from presentation.schemas.amocrm import AmoIncomingWebhook
from presentation.schemas.edna import EdnaIncomingMessage


class ConversationLinkRepository(Protocol):
	async def get_edna_conversation_id(self, amocrm_chat_id: str) -> str | None: ...
	async def get_amocrm_chat_id(self, edna_conversation_id: str) -> str | None: ...


class MessageLinkRepository(Protocol):
	async def get_link_by_source_id(self, source_message_id: str) -> MessageLink | None: ...
	async def save_link(self, link: MessageLink) -> None: ...


class RouteMessageFromEdnaUseCase:
	def __init__(
		self,
		amocrm_provider: MessageProvider,
		conv_links: ConversationLinkRepository,
		msg_links: MessageLinkRepository,
	) -> None:
		self._amocrm_provider = amocrm_provider
		self._conv_links = conv_links
		self._msg_links = msg_links

	async def execute(self, payload: EdnaIncomingMessage) -> None:
		message = edna_message_to_domain(payload)
		target_conversation_id = await self._conv_links.get_amocrm_chat_id(
			message.source_conversation_id
		)
		if target_conversation_id:
			message.target_conversation_id = target_conversation_id
			result = await self._amocrm_provider.send_message(message)
			# Сохраняем связь ID сообщений
			link = MessageLink(
				source_provider=message.source_provider,
				source_message_id=message.source_message_id,
				target_provider=result.reference.provider,
				target_message_id=result.reference.message_id,
				target_conversation_id=result.reference.conversation_id,
			)
			await self._msg_links.save_link(link)


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
