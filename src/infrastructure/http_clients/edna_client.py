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
		self._send_path = settings.send_path
		self._callback_path = settings.callback_path
		self._im_type = settings.im_type
		self._subject_id = settings.subject_id
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

	async def ensure_ready(self) -> None:
		if self._subject_id and (self._status_cb or self._in_msg_cb or self._matcher_cb):
			await self.set_callbacks(
				subject_id=self._subject_id,
				status_url=self._status_cb,
				in_message_url=self._in_msg_cb,
				matcher_url=self._matcher_cb,
			)

	def _build_payload(self, message: Message) -> Dict[str, Any]:
		subject = message.recipient.provider_user_id or message.target_conversation_id or ""
		payload: Dict[str, Any] = {
			"imType": self._im_type,
			"subject": subject,
		}
		if message.attachment is not None:
			attachment = {
				"url": message.attachment.url,
				"mimeType": message.attachment.mime_type,
				"name": message.attachment.filename,
				"size": message.attachment.size_bytes,
			}
			payload["attachment"] = {k: v for k, v in attachment.items() if v is not None}
		if message.text is not None:
			payload["text"] = message.text
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

		self._logger.debug("Полный payload для Edna: %s", json.dumps(payload, indent=2, ensure_ascii=False))

		try:
			self._logger.info("Выполнение HTTP запроса к Edna API: %s%s", self._base_url, self._send_path)
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
				data.get("id")
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
