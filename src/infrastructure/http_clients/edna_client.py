import json
import logging
from typing import Any, Dict, Optional

import httpx
from domain.models import (
	Message,
	SentMessageResult,
	MessageStatusUpdate,
	ProviderMessageRef,
	ProviderName,
)
from domain.ports.message_provider import MessageProvider, StatusNotifier
from core.config import EdnaSettings
from core.error_logger import get_error_reporter


class EdnaHttpClient(MessageProvider, StatusNotifier):
	def __init__(self, settings: EdnaSettings):
		self._logger = logging.getLogger("edna")
		self._api_key = settings.api_key
		self._base_url = settings.base_url.rstrip("/")
		self._send_path = "/api/cascade/schedule"
		self._callback_path = settings.callback_path
		self._im_type = settings.im_type
		self._subject_id = settings.subject_id
		self._cascade_id = settings.cascade_id
		self._subscriber_id_type = (settings.subscriber_id_type or "PHONE").upper()
		self._status_cb = settings.status_callback_url
		self._in_msg_cb = settings.in_message_callback_url
		self._matcher_cb = settings.message_matcher_callback_url
		self._headers = {"X-API-KEY": self._api_key, "Content-Type": "application/json"}
		self._client = httpx.AsyncClient(base_url=self._base_url, headers=self._headers, timeout=10.0)
		self._logger.info(
			"Edna client initialized base_url=%s subject_id=%s callbacks_configured=%s",
			self._base_url,
			self._subject_id,
			bool(self._status_cb or self._in_msg_cb or self._matcher_cb),
		)

	async def get_channels(self, types: Optional[str] = None) -> list[Dict[str, Any]]:
		"""Получить список каналов edna для диагностики"""
		if types is None:
			types = self._im_type.upper()  # Преобразуем whatsapp в WHATSAPP

		try:
			params = {"types": types}
			self._logger.info("Получение списка каналов edna: types=%s", types)

			response = await self._client.get("/api/channel-profile", params=params)
			response.raise_for_status()

			channels = response.json()
			self._logger.info(f"Получено {len(channels)} каналов edna: {channels}")

			# Логируем информацию о каналах
			for channel in channels:
				self._logger.debug(
					"Канал: id=%s, name='%s', subjectId=%s, type=%s, active=%s, registrationStatus=%s",
					channel.get("id"),
					channel.get("name"),
					channel.get("subjectId"),
					channel.get("type"),
					channel.get("active"),
					channel.get("registrationStatus")
				)

			return channels

		except Exception as e:
			self._logger.error("Не удалось получить список каналов edna: %s", str(e))

			# Логируем ошибку в error_reporter
			try:
				error_reporter = get_error_reporter()
				error_reporter.log_api_error(
					error=e,
					service_name="Edna",
					endpoint="/api/channel-profile",
					request_data={"types": types}
				)
			except Exception as report_error:
				self._logger.error("Не удалось создать отчет об ошибке получения каналов: %s", str(report_error))

			# Возвращаем пустой список, чтобы не прерывать инициализацию
			return []

	def _validate_callback_url(self, url: str) -> bool:
		"""Простая валидация URL для callback"""
		if not url:
			return False
		if len(url) > 500:
			self._logger.warning("URL слишком длинный (>%d символов): %s", 500, url)
			return False
		if not url.startswith("https://"):
			self._logger.warning("URL должен использовать HTTPS: %s", url)
			return False
		return True

	async def ensure_ready(self) -> None:
		# Если заданы callback URL, получаем каналы и устанавливаем коллбеки для всех каналов
		if self._status_cb or self._in_msg_cb or self._matcher_cb:
			# Валидируем URL
			valid_urls = []
			if self._status_cb and self._validate_callback_url(self._status_cb):
				valid_urls.append(("status", self._status_cb))
			if self._in_msg_cb and self._validate_callback_url(self._in_msg_cb):
				valid_urls.append(("in_message", self._in_msg_cb))
			if self._matcher_cb and self._validate_callback_url(self._matcher_cb):
				valid_urls.append(("matcher", self._matcher_cb))

			if not valid_urls:
				self._logger.warning("Все callback URL невалидны или не заданы, пропускаем настройку коллбеков")
				return

			# Получаем список каналов для диагностики
			try:
				channels = await self.get_channels()
				if channels:
					active_channels = [c for c in channels if c.get("active")]
					self._logger.info("Найдено %d активных каналов из %d", len(active_channels), len(channels))
				else:
					self._logger.warning("Не удалось получить список каналов, но продолжаем настройку коллбеков")
			except Exception as e:
				self._logger.warning("Ошибка при получении каналов, но продолжаем настройку коллбеков: %s", str(e))

			try:
				await self.set_callbacks_global(
					status_url=self._status_cb if self._status_cb else None,
					in_message_url=self._in_msg_cb if self._in_msg_cb else None,
					matcher_url=self._matcher_cb if self._matcher_cb else None,
				)
				self._logger.info("Коллбеки успешно установлены для всех каналов")
			except Exception as e:
				self._logger.error("Не удалось установить коллбеки: %s", str(e))
				try:
					error_reporter = get_error_reporter()
					error_reporter.log_api_error(
						error=e,
						service_name="Edna",
						endpoint=self._callback_path,
						request_data={
							"statusCallbackUrl": self._status_cb,
							"inMessageCallbackUrl": self._in_msg_cb,
							"messageMatcherCallbackUrl": self._matcher_cb
						}
					)
				except Exception as report_error:
					self._logger.error("Не удалось создать отчет об ошибке настройки коллбеков: %s", str(report_error))

	def _build_payload(self, message: Message) -> Dict[str, Any]:
		if not self._cascade_id:
			raise ValueError("EDNA cascade_id is required for cascade scheduling")

		request_id = message.source_message_id or message.id
		address = (
			message.recipient.provider_user_id
			or message.target_conversation_id
			or message.source_conversation_id
			or ""
		)
		if not address:
			raise ValueError("Address for subscriberFilter is empty")

		content: Dict[str, Any] = {}
		channel = (self._im_type or "whatsapp").lower()

		if channel == "sms":
			content["smsContent"] = {
				"text": message.text or ""
			}
		else:
			whatsapp_obj: Dict[str, Any] = {}
			if message.attachment is None:
				whatsapp_obj["contentType"] = "TEXT"
				whatsapp_obj["text"] = message.text or ""
			else:
				att = message.attachment
				if message.content_type.name.lower() == "image":
					whatsapp_obj["contentType"] = "IMAGE"
					whatsapp_obj["attachment"] = {
						"url": att.url,
						"name": att.filename or "image"
					}
				else:
					whatsapp_obj["contentType"] = "DOCUMENT"
					whatsapp_obj["attachment"] = {
						"url": att.url,
						"name": att.filename or "file"
					}
			content["whatsappContent"] = whatsapp_obj

		payload: Dict[str, Any] = {
			"requestId": request_id,
			"cascadeId": self._cascade_id,
			"subscriberFilter": {
				"address": address,
				"type": self._subscriber_id_type,
			},
			"content": content,
		}

		return payload

	async def set_callbacks(
		self,
		subject_id: int,
		status_url: Optional[str] = None,
		in_message_url: Optional[str] = None,
		matcher_url: Optional[str] = None,
	) -> None:
		body: Dict[str, Any] = {"subjectId": subject_id}
		if status_url:
			body["statusCallbackUrl"] = status_url
		if in_message_url:
			body["inMessageCallbackUrl"] = in_message_url
		if matcher_url:
			body["messageMatcherCallbackUrl"] = matcher_url
		self._logger.info("Setting edna callbacks subject_id=%s", subject_id)
		resp = await self._client.post(self._callback_path, json=body)
		self._logger.debug("Edna callback set response %s %s", resp.status_code, resp.text)
		resp.raise_for_status()

	async def set_callbacks_global(
		self,
		status_url: Optional[str] = None,
		in_message_url: Optional[str] = None,
		matcher_url: Optional[str] = None,
	) -> None:
		"""Установить коллбеки для всех каналов тенанты (без указания subject_id)"""
		body: Dict[str, Any] = {}
		if status_url:
			body["statusCallbackUrl"] = status_url
		if in_message_url:
			body["inMessageCallbackUrl"] = in_message_url
		if matcher_url:
			body["messageMatcherCallbackUrl"] = matcher_url

		if not body:
			self._logger.warning("Не указаны URL для коллбеков, пропускаем настройку")
			return

		self._logger.info("Установка коллбеков для всех каналов (глобально)")
		resp = await self._client.post(self._callback_path, json=body)
		self._logger.debug("Edna global callback set response %s %s", resp.status_code, resp.text)
		resp.raise_for_status()

		# Логируем успешную настройку
		enabled_callbacks = []
		if status_url:
			enabled_callbacks.append("status")
		if in_message_url:
			enabled_callbacks.append("in_message")
		if matcher_url:
			enabled_callbacks.append("matcher")
		self._logger.info("Глобальные коллбеки установлены: %s", ", ".join(enabled_callbacks))

	async def send_message(self, message: Message) -> SentMessageResult:
		payload = self._build_payload(message)

		self._logger.info(
			"Отправка сообщения в Edna: conversation_id=%s, recipient=%s, has_text=%s, has_attachment=%s",
			message.target_conversation_id,
			message.recipient.display_name,
			bool(message.text),
			bool(message.attachment)
		)

		if message.text:
			self._logger.info(
				"Текст сообщения: '%s'",
				message.text[:200] + "..." if len(message.text) > 200 else message.text
			)

		if message.attachment:
			self._logger.info(
				"Вложение: filename=%s, size=%s bytes, mime_type=%s, url=%s",
				message.attachment.filename,
				message.attachment.size_bytes,
				message.attachment.mime_type,
				message.attachment.url
			)

		self._logger.debug("Полный payload для Edna Cascade Schedule: %s", json.dumps(payload, indent=2, ensure_ascii=False))

		try:
			self._logger.info("Выполнение HTTP запроса к Edna API: %s%s", self._base_url, self._send_path)
			self._logger.info("Отправляемый payload в Edna: %s", json.dumps(payload, ensure_ascii=False))
			response = await self._client.post(self._send_path, json=payload)

			self._logger.info(
				"Получен ответ от Edna API: status=%s, content_length=%s bytes",
				response.status_code,
				len(response.content) if response.content else 0
			)

			if response.status_code >= 400:
				self._logger.error(
					"Ошибка от Edna API: status=%s, response_body=%s",
					response.status_code,
					response.text
				)

			response.raise_for_status()

			data: Dict[str, Any] = response.json() if response.content else {}
			self._logger.debug("Ответ от Edna API: %s", json.dumps(data, indent=2, ensure_ascii=False))

			returned_id: Optional[str] = (
				data.get("requestId")
				or data.get("id")
				or data.get("messageId")
				or data.get("message_id")
				or message.source_message_id
			)

			conversation_id = message.target_conversation_id or message.recipient.provider_user_id or ""

			result = SentMessageResult(
				reference=ProviderMessageRef(
					provider=ProviderName.edna,
					conversation_id=conversation_id,
					message_id=returned_id or "unknown",
				)
			)

			self._logger.info(
				"Сообщение успешно отправлено в Edna: edna_message_id=%s, conversation_id=%s",
				result.reference.message_id,
				result.reference.conversation_id
			)

			return result

		except httpx.HTTPStatusError as e:
			self._logger.error(
				"HTTP ошибка при отправке в Edna: status=%s, response=%s",
				e.response.status_code,
				e.response.text
			)
			self._logger.error(
				"Детальный ответ Edna API при ошибке: %s",
				json.dumps({"status_code": e.response.status_code, "response_body": e.response.text}, ensure_ascii=False)
			)

			# Создаем детальный отчет об ошибке API
			try:
				error_reporter = get_error_reporter()
				error_reporter.log_api_error(
					error=e,
					service_name="Edna",
					endpoint=self._send_path,
					request_data=payload,
					response_data={"status_code": e.response.status_code, "response": e.response.text},
					status_code=e.response.status_code
				)
			except Exception as report_error:
				self._logger.error("Не удалось создать отчет об ошибке: %s", str(report_error))

			raise
		except Exception as e:
			self._logger.exception("Неожиданная ошибка при отправке в Edna: %s", str(e))

			# Создаем детальный отчет об ошибке
			try:
				error_reporter = get_error_reporter()
				error_reporter.log_api_error(
					error=e,
					service_name="Edna",
					endpoint=self._send_path,
					request_data=payload
				)
			except Exception as report_error:
				self._logger.error("Не удалось создать отчет об ошибке: %s", str(report_error))

			raise

	async def notify_status(self, status: MessageStatusUpdate) -> None:
		return None
