import base64
import hashlib
import hmac
import json
import logging
from datetime import datetime, timezone
from email.utils import formatdate
from typing import Any, Dict, Optional

import httpx
from domain.models import (
	Message,
	SentMessageResult,
	ProviderMessageRef,
	ProviderName,
	MessageStatusUpdate,
	MessageContentType,
	MessageStatus,
)
from domain.ports.message_provider import MessageProvider, StatusNotifier
from core.config import AmoCrmSettings
from core.error_logger import get_error_reporter


class AmoCrmHttpClient(MessageProvider, StatusNotifier):
	def __init__(self, settings: AmoCrmSettings):
		self._logger = logging.getLogger("amocrm.amojo")
		self._amojo_base_url = settings.amojo_base_url.rstrip("/")
		self._scope_id = settings.scope_id or ""
		self._channel_id = settings.channel_id
		self._account_id = settings.account_id
		self._connect_title = settings.connect_title
		self._hook_api_version = settings.hook_api_version
		self._channel_secret = settings.channel_secret.encode()
		self._client = httpx.AsyncClient(base_url=self._amojo_base_url, timeout=10.0)
		self._logger.info(
			"Amojo client initialized base_url=%s channel_id=%s account_id=%s scope_id_present=%s",
			self._amojo_base_url,
			self._channel_id,
			self._account_id,
			bool(self._scope_id),
		)

	async def ensure_ready(self) -> None:
		await self._ensure_scope_id()

	def _build_signature(self, method: str, content_md5_hex: str, content_type: str, date_str: str, path: str) -> str:
		canonical = "\n".join([method.upper(), content_md5_hex, content_type, date_str, path])
		self._logger.debug("Signature canonical=%r", canonical)
		digest = hmac.new(self._channel_secret, canonical.encode(), hashlib.sha1).hexdigest().lower()
		return digest

	def _headers_for(self, method: str, path: str, body_bytes: bytes) -> Dict[str, str]:
		content_type = "application/json"
		md5_hex = hashlib.md5(body_bytes).hexdigest().lower()
		date_str = formatdate(timeval=None, usegmt=True)
		signature = self._build_signature(method, md5_hex, content_type, date_str, path)
		self._logger.debug(
			"Headers build path=%s len(body)=%d content_md5_hex=%s date=%s signature=%s",
			path,
			len(body_bytes),
			md5_hex,
			date_str,
			signature,
		)
		return {
			"Content-Type": content_type,
			"Date": date_str,
			"Content-MD5": md5_hex,
			"X-Signature": signature,
		}

	async def _post(self, path: str, payload: Dict[str, Any]) -> Dict[str, Any]:
		body_bytes = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode()
		headers = self._headers_for("POST", path, body_bytes)
		self._logger.debug(
			"POST %s headers={Date=%s, Content-MD5=%s, X-Signature=%s} payload=%s",
			path,
			headers.get("Date"),
			headers.get("Content-MD5"),
			headers.get("X-Signature"),
			payload,
		)
		response = await self._client.post(path, content=body_bytes, headers=headers)
		self._logger.debug("Response %s %s", response.status_code, response.text)
		response.raise_for_status()
		if response.content:
			return response.json()
		return {}

	async def _ensure_scope_id(self) -> None:
		if self._scope_id:
			return
		if not self._channel_id or not self._account_id:
			raise ValueError("channel_id and account_id are required to obtain scope_id")
		path = f"/v2/origin/custom/{self._channel_id}/connect"
		payload = {
			"account_id": self._account_id,
			"title": self._connect_title,
			"hook_api_version": self._hook_api_version,
		}
		self._logger.debug(
			"Connecting to amojo: base_url=%s path=%s channel_id=%s account_id=%s title=%s hook_api_version=%s",
			self._amojo_base_url,
			path,
			self._channel_id,
			self._account_id,
			self._connect_title,
			self._hook_api_version,
		)
		data = await self._post(path, payload)
		scope = data.get("scope_id")
		if not scope and self._channel_id and self._account_id:
			scope = f"{self._channel_id}_{self._account_id}"
		self._scope_id = scope or ""
		if not self._scope_id:
			raise RuntimeError("Failed to obtain scope_id from amojo connect response")
		self._logger.info("Obtained scope_id=%s", self._scope_id)

	def _build_text_message_payload(self, conversation_id: str, text: str, msg_id: Optional[str], *, sender_id: str, sender_name: str | None) -> Dict[str, Any]:
		return {
			"event_type": "new_message",
			"payload": {
				"timestamp": int(datetime.now(timezone.utc).timestamp()),
				"conversation_id": conversation_id,
				"sender": {
					"id": sender_id,
					"name": sender_name or "",
				},
				"message": {
					"type": "text",
					"text": text or "",
				},
				"msgid": msg_id or "",
			},
		}

	def _build_media_message_payload(self, conversation_id: str, msg_id: Optional[str], media_type: MessageContentType, *, url: str, name: Optional[str], size: Optional[int], sender_id: str, sender_name: str | None) -> Dict[str, Any]:
		amo_type = "picture" if media_type == MessageContentType.image else "file"
		message_obj: Dict[str, Any] = {"type": amo_type, "media": url}
		if name:
			message_obj["file_name"] = name
		if size is not None:
			message_obj["file_size"] = size
		return {
			"event_type": "new_message",
			"payload": {
				"timestamp": int(datetime.now(timezone.utc).timestamp()),
				"conversation_id": conversation_id,
				"sender": {
					"id": sender_id,
					"name": sender_name or "",
				},
				"message": message_obj,
				"msgid": msg_id or "",
			},
		}

	async def send_message(self, message: Message) -> SentMessageResult:
		await self._ensure_scope_id()
		conversation_id = message.target_conversation_id or message.source_conversation_id or ""
		if not conversation_id:
			raise ValueError("conversation_id is required to send message to amoCRM")
		path = f"/v2/origin/custom/{self._scope_id}"

		if message.content_type == MessageContentType.text or message.attachment is None:
			text = message.text or ""
			payload = self._build_text_message_payload(
				conversation_id=conversation_id,
				text=text,
				msg_id=message.source_message_id,
				sender_id=message.sender.provider_user_id,
				sender_name=message.sender.display_name,
			)
		else:
			att = message.attachment
			payload = self._build_media_message_payload(
				conversation_id=conversation_id,
				msg_id=message.source_message_id,
				media_type=message.content_type,
				url=att.url,
				name=att.filename,
				size=att.size_bytes,
				sender_id=message.sender.provider_user_id,
				sender_name=message.sender.display_name,
			)

		data = await self._post(path, payload)
		returned_message_id = (
			data.get("new_message", {}).get("msgid")
			or data.get("message_id")
			or data.get("id")
			or data.get("message", {}).get("id")
			or message.source_message_id
			or ""
		)
		return SentMessageResult(
			reference=ProviderMessageRef(
				provider=ProviderName.amocrm,
				conversation_id=conversation_id,
				message_id=returned_message_id or "unknown",
			)
		)

	async def notify_status(self, status: MessageStatusUpdate) -> None:
		await self._ensure_scope_id()
		delivery_status_map: Dict[MessageStatus, int] = {
			MessageStatus.delivered: 1,
			MessageStatus.read: 2,
		}
		if status.status not in delivery_status_map:
			return
		path = f"/v2/origin/custom/{self._scope_id}/{status.message_id}/delivery_status"
		payload = {
			"msgid": status.message_id,
			"delivery_status": delivery_status_map[status.status],
			"error_code": 905 if delivery_status_map[status.status] == -1 else 0,
			"error": "" if delivery_status_map[status.status] in (1, 2) else "Error",
		}
		await self._post(path, payload)

	async def update_message_status(self, message_id: str, status: int, error_code: int = 0, error_text: str = "") -> None:
		"""Обновляет статус доставки сообщения в AmoCRM"""
		await self._ensure_scope_id()

		if status not in [1, 2, -1]:
			self._logger.error("Неверный статус доставки: %d. Допустимые значения: 1 (доставлено), 2 (прочитано), -1 (ошибка)", status)
			return

		path = f"/v2/origin/custom/{self._scope_id}/{message_id}/delivery_status"
		payload = {
			"msgid": message_id,
			"delivery_status": status,
		}

		# Добавляем код ошибки только для статусов ошибок
		if status == -1:
			if not error_text:
				error_messages = {
					901: "Пользователь удалил чат",
					902: "Интеграция отключена на стороне канала",
					903: "Внутренняя ошибка сервера",
					904: "Невозможно создать чат",
					905: "Произошла неизвестная ошибка",
				}
				error_text = error_messages.get(error_code, "Произошла ошибка при отправке сообщения")

			payload["error_code"] = error_code
			payload["error"] = error_text

		try:
			status_text = {1: "доставлено", 2: "прочитано", -1: "ошибка"}.get(status, "неизвестно")
			self._logger.debug(
				"Обновление статуса сообщения в AmoCRM: message_id=%s, status=%s (%d)",
				message_id, status_text, status
			)
			await self._post(path, payload)
			self._logger.info("Статус сообщения успешно обновлен в AmoCRM")
		except Exception as e:
			self._logger.error(
				"Не удалось обновить статус сообщения в AmoCRM: message_id=%s, error=%s",
				message_id, str(e)
			)

			# Создаем детальный отчет об ошибке
			try:
				error_reporter = get_error_reporter()
				error_reporter.log_delivery_status_error(
					error=e,
					provider="amocrm",
					message_id=message_id,
					error_details=f"Failed to update message status to {status}"
				)
			except Exception as report_error:
				self._logger.error("Не удалось создать отчет об ошибке обновления статуса: %s", str(report_error))

	async def notify_delivery_error(self, message_id: str, error_code: int = 903, error_text: str = "") -> None:
		"""Отправляет статус ошибки доставки для сообщения в AmoCRM"""
		await self.update_message_status(message_id, -1, error_code, error_text)
