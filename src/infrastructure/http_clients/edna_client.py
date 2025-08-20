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
		self._logger.debug("Edna send payload=%s", payload)
		response = await self._client.post(self._send_path, json=payload)
		self._logger.debug("Edna send response %s %s", response.status_code, response.text)
		response.raise_for_status()
		data: Dict[str, Any] = response.json() if response.content else {}
		returned_id: Optional[str] = (
			data.get("id")
			or data.get("messageId")
			or data.get("message_id")
			or message.source_message_id
		)
		conversation_id = message.target_conversation_id or message.recipient.provider_user_id or ""
		return SentMessageResult(
			reference=ProviderMessageRef(
				provider=ProviderName.edna,
				conversation_id=conversation_id,
				message_id=returned_id or "unknown",
			)
		)

	async def notify_status(self, status: MessageStatusUpdate) -> None:
		return None
