from __future__ import annotations
import logging
import asyncio
from typing import Protocol, Optional
from domain.models import Message, MessageLink, ConversationLink
from domain.ports.message_provider import MessageProvider
from use_cases.mappers.amocrm_to_domain import amocrm_to_domain
from use_cases.mappers.edna_to_domain import edna_message_to_domain
from presentation.schemas.amocrm import AmoIncomingWebhook
from presentation.schemas.edna import EdnaIncomingMessage
from core.error_logger import get_error_reporter
from .create_chat import CreateChatUseCase
from infrastructure.http_clients.amocrm_rest_client import AmoCrmRestClient


class ConversationLinkRepository(Protocol):
	async def get_edna_conversation_id(self, amocrm_chat_id: str) -> str | None: ...
	async def get_amocrm_chat_id(self, edna_conversation_id: str) -> str | None: ...
	async def get_phone_by_chat_id(self, amocrm_chat_id: str) -> str | None: ...
	async def get_chat_id_by_phone(self, phone_number: str) -> str | None: ...
	async def save_link(self, link: ConversationLink) -> None: ...
	async def save_phone_for_chat(self, amocrm_chat_id: str, phone_number: str) -> None: ...


class MessageLinkRepository(Protocol):
	async def get_link_by_source_id(self, source_message_id: str) -> MessageLink | None: ...
	async def save_link(self, link: MessageLink) -> None: ...


class RouteMessageFromEdnaUseCase:
	def __init__(
		self,
		amocrm_provider: MessageProvider,
		amocrm_rest: AmoCrmRestClient,
		conv_links: ConversationLinkRepository,
		msg_links: MessageLinkRepository,
		create_chat_usecase: Optional[CreateChatUseCase] = None,
		logger: Optional[logging.Logger] = None,
	) -> None:
		self._amocrm_provider = amocrm_provider
		self._amocrm_rest = amocrm_rest
		self._conv_links = conv_links
		self._msg_links = msg_links
		self._create_chat_usecase = create_chat_usecase
		self._logger = logger or logging.getLogger(__name__)

	async def execute(self, payload: EdnaIncomingMessage) -> None:
		self._logger.debug("Routing message from Edna, payload=%s", payload.model_dump_json())
		message = edna_message_to_domain(payload)
		self._logger.debug("Mapped Edna message to domain model: %s", message.model_dump_json())

		# Извлекаем номер телефона из сообщения Edna
		phone_number = payload.subscriber.identifier
		user_name = payload.userInfo.userName

		target_conversation_id = await self._conv_links.get_amocrm_chat_id(
			message.source_conversation_id
		)

		if not target_conversation_id:
			self._logger.warning(
				"No AmoCRM chat link found for Edna conversation_id=%s. Creating a new chat.",
				message.source_conversation_id,
			)

			# Создаем чат в AmoCRM, если указан use case для создания чатов
			if self._create_chat_usecase:
				try:
					chat_result = await self._create_chat_usecase.execute(
						edna_conversation_id=message.source_conversation_id,
						phone_number=phone_number,
						user_name=user_name
					)
					target_conversation_id = chat_result.id
					self._logger.info(
						"Created new chat in AmoCRM: chat_id=%s for phone=%s",
						target_conversation_id,
						phone_number
					)
				except Exception as e:
					self._logger.error(
						"Failed to create chat in AmoCRM for phone=%s: %s",
						phone_number,
						str(e)
					)
					# Fallback: используем ID из Edna как временный
					target_conversation_id = message.source_conversation_id
			else:
				self._logger.warning(
					"No create chat use case provided, using Edna conversation_id as temporary chat_id"
				)
				target_conversation_id = message.source_conversation_id
		else:
			self._logger.debug(
				"Found linked AmoCRM chat_id=%s for Edna conversation_id=%s",
				target_conversation_id,
				message.source_conversation_id,
			)

		message.target_conversation_id = target_conversation_id

		# Запускаем фоновую задачу для получения contact_id через 10 секунд
		self._logger.info("Запускаем фоновую задачу для поиска контакта через 10 секунд: conversation_id=%s, phone=%s",
						 target_conversation_id, phone_number)
		asyncio.create_task(
			self._delayed_contact_lookup(
				target_conversation_id,
				phone_number,
				message.source_message_id
			)
		)

		try:
			# Отправляем сообщение в AmoCRM
			result = await self._amocrm_provider.send_message(message)
			self._logger.debug(
				"Message sent to AmoCRM, result: %s", result.model_dump_json()
			)

			# Сохраняем связь ID сообщений
			msg_link = MessageLink(
				source_provider=message.source_provider,
				source_message_id=message.source_message_id,
				target_provider=result.reference.provider,
				target_message_id=result.reference.message_id,
				target_conversation_id=result.reference.conversation_id,
			)
			await self._msg_links.save_link(msg_link)
			self._logger.debug("Saved message link: %s", msg_link.model_dump_json())

		except Exception:
			self._logger.exception(
				"Failed to send message to AmoCRM for Edna conversation_id=%s",
				message.source_conversation_id,
			)

	async def _delayed_contact_lookup(self, conversation_id: str, phone_number: str, message_id: str) -> None:
		"""Фоновая задача для получения contact_id через 10 секунд после отправки сообщения"""
		try:
			self._logger.info("Запущена фоновая задача поиска контакта для conversation_id=%s", conversation_id)

			# Ждем 10 секунд
			await asyncio.sleep(10)

			self._logger.info("Начинаем поиск контакта для conversation_id=%s через 10 секунд", conversation_id)

			# Пытаемся получить контакт по conversation_id
			contact_links = await self._amocrm_rest.get_contact_links(chats_id=[conversation_id])

			if contact_links["_total_items"] > 0:
				contact_link = contact_links["_embedded"]["chats"][0]
				contact_id = contact_link.get("contact_id")

				if contact_id:
					self._logger.info("Найден контакт id=%s для чата id=%s через фоновую задачу", contact_id, conversation_id)

					# Нормализуем номер телефона
					raw_phone = phone_number or ""
					norm = raw_phone.strip().replace(" ", "").replace("-", "")
					if norm.startswith("+"):
						phone_e164 = norm
					elif norm.startswith("8") and len(norm) == 11:
						phone_e164 = "+7" + norm[1:]
					elif norm.startswith("7") and len(norm) == 11:
						phone_e164 = "+" + norm
					else:
						# Если начинается с 9 и длина 10 — считаем РФ
						if len(norm) == 10 and norm.startswith("9"):
							phone_e164 = "+7" + norm
						else:
							phone_e164 = "+" + norm if norm and not norm.startswith("+") else norm

					self._logger.info("Нормализован номер телефона: '%s' -> '%s'", raw_phone, phone_e164)

					# Обновляем телефон у контакта
					await self._amocrm_rest.update_contact_phone(contact_id, phone_e164)
					self._logger.info("Телефон контакта успешно обновлен в фоновой задаче")
				else:
					self._logger.warning("Contact_id не найден в ответе API для conversation_id=%s", conversation_id)
			else:
				self._logger.warning("Контакт не найден для conversation_id=%s даже через 10 секунд", conversation_id)

		except Exception as e:
			self._logger.exception(
				"Ошибка в фоновой задаче поиска контакта для conversation_id=%s: %s",
				conversation_id, str(e)
			)


class RouteMessageFromAmoCrmUseCase:
	def __init__(
		self,
		edna_provider: MessageProvider,
		amocrm_provider: MessageProvider,
		conv_links: ConversationLinkRepository,
		msg_links: MessageLinkRepository,
		logger: Optional[logging.Logger] = None,
	) -> None:
		self._edna_provider = edna_provider
		self._amocrm_provider = amocrm_provider
		self._conv_links = conv_links
		self._msg_links = msg_links
		self._logger = logger or logging.getLogger(__name__)

	async def execute(self, payload: AmoIncomingWebhook) -> None:
		# Сохраняем ID сообщения из AmoCRM для отправки статуса ошибки
		amocrm_message_id = payload.message.message.id

		self._logger.debug(
			"Начата обработка сообщения из AmoCRM, account_id=%s, time=%s, message_id=%s",
			payload.account_id, payload.time, amocrm_message_id
		)

		try:
			message = amocrm_to_domain(payload)
			self._logger.debug(
				"Сообщение преобразовано в доменную модель: id=%s, sender=%s, recipient=%s, conversation_id=%s",
				message.id, message.sender.display_name, message.recipient.display_name, message.source_conversation_id
			)
			self._logger.debug("Детали сообщения: %s", message.model_dump_json())

			target_conversation_id = await self._conv_links.get_edna_conversation_id(
				message.source_conversation_id
			)

			if not target_conversation_id:
				self._logger.warning(
					"Связь с Edna не найдена для AmoCRM conversation_id=%s. Используем исходный ID как временный.",
					message.source_conversation_id
				)
				message.target_conversation_id = message.source_conversation_id
			else:
				self._logger.debug(
					"Найдена связь: AmoCRM conversation_id=%s -> Edna conversation_id=%s",
					message.source_conversation_id, target_conversation_id
				)
				message.target_conversation_id = target_conversation_id

				# Проверяем, есть ли сохраненный номер телефона для этого чата
				saved_phone = await self._conv_links.get_phone_by_chat_id(message.source_conversation_id)
				if saved_phone:
					message.recipient.provider_user_id = saved_phone
					self._logger.debug(
						"Используем сохраненный номер телефона: %s для чата %s",
						saved_phone, message.source_conversation_id
					)
				else:
					message.recipient.provider_user_id = target_conversation_id
					self._logger.warning(
						"Сохраненный номер телефона не найден для чата %s, используем conversation_id",
						message.source_conversation_id
					)

			self._logger.debug(
				"Отправка сообщения в Edna: conversation_id=%s, sender=%s, text='%s'",
				message.target_conversation_id, message.sender.display_name, message.text[:100] + "..." if message.text and len(message.text) > 100 else message.text
			)

			result = await self._edna_provider.send_message(message)

			self._logger.info(
				"Сообщение успешно отправлено в Edna: target_message_id=%s, target_conversation_id=%s",
				result.reference.message_id, result.reference.conversation_id
			)
			self._logger.debug("Результат отправки: %s", result.model_dump_json())

			# Сохраняем связь ID сообщений
			link = MessageLink(
				source_provider=message.source_provider,
				source_message_id=message.source_message_id,
				target_provider=result.reference.provider,
				target_message_id=result.reference.message_id,
				target_conversation_id=result.reference.conversation_id,
			)

			self._logger.debug(
				"Сохраняем связь сообщений: source_provider=%s, source_message_id=%s -> target_provider=%s, target_message_id=%s, target_conversation_id=%s",
				message.source_provider, message.source_message_id,
				result.reference.provider, result.reference.message_id, result.reference.conversation_id
			)

			await self._msg_links.save_link(link)
			self._logger.debug(
				"Связь сообщений сохранена: source_id=%s -> target_id=%s",
				message.source_message_id, result.reference.message_id
			)

			# Если чат был новым, сохраняем связь разговоров
			if not target_conversation_id:
				new_conv_link = ConversationLink(
					edna_conversation_id=result.reference.conversation_id,
					amocrm_chat_id=message.source_conversation_id,
				)
				await self._conv_links.save_link(new_conv_link)
				self._logger.debug(
					"Сохранена новая связь разговоров: AmoCRM=%s -> Edna=%s",
					message.source_conversation_id, result.reference.conversation_id
				)

				# Если у нас есть номер телефона получателя, сохраняем его для будущих сообщений
				if (message.recipient.provider_user_id and
					message.recipient.provider_user_id.isdigit()):
					await self._conv_links.save_phone_for_chat(
						message.source_conversation_id,
						message.recipient.provider_user_id
					)
					self._logger.debug(
						"Сохранен номер телефона для чата: AmoCRM_chat_id=%s -> phone=%s",
						message.source_conversation_id, message.recipient.provider_user_id
					)

		except Exception as e:
			error_message = str(e)

			# Логируем ошибку в обычный лог
			self._logger.exception(
				"Ошибка при обработке сообщения из AmoCRM: account_id=%s, conversation_id=%s, message_id=%s, error=%s",
				payload.account_id, payload.message.conversation.id, amocrm_message_id, error_message
			)

			# Создаем детальный отчет об ошибке
			error_reporter = get_error_reporter()
			error_reporter.log_message_processing_error(
				error=e,
				source_provider="amocrm",
				target_provider="edna",
				message_id=amocrm_message_id,
				conversation_id=payload.message.conversation.id,
				account_id=payload.account_id
			)

			# Определяем код ошибки на основе типа исключения
			error_code = 903  # Внутренняя ошибка сервера по умолчанию
			if "404" in error_message:
				error_code = 904  # Невозможно создать чат
			elif "403" in error_message or "401" in error_message:
				error_code = 902  # Интеграция отключена
			elif "timeout" in error_message.lower() or "connection" in error_message.lower():
				error_code = 905  # Сетевая ошибка

			# Отправляем статус ошибки в AmoCRM
			try:
				await self._amocrm_provider.notify_delivery_error(
					message_id=amocrm_message_id,
					error_code=error_code,
					error_text=f"Ошибка при отправке в Edna: {error_message}"
				)
			except Exception as notify_error:
				self._logger.error(
					"Не удалось отправить статус ошибки в AmoCRM: %s", str(notify_error)
				)
				# Логируем и эту ошибку в error_reports
				error_reporter.log_delivery_status_error(
					error=notify_error,
					provider="amocrm",
					message_id=amocrm_message_id,
					error_details="Failed to send delivery error status"
				)

			# Повторно выбрасываем оригинальную ошибку
			raise
