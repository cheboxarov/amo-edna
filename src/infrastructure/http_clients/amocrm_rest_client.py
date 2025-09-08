import logging
from typing import Any, Dict, Optional, List

import httpx
from core.config import AmoCrmSettings
from core.error_logger import get_error_reporter


class AmoCrmRestClient:
	def __init__(self, settings: AmoCrmSettings):
		self._logger = logging.getLogger("amocrm.rest")
		self._base_url = settings.base_url.rstrip("/")
		self._token = settings.token
		self._client = httpx.AsyncClient(
			base_url=self._base_url,
			headers={
				"Authorization": f"Bearer {self._token}",
				"Content-Type": "application/json",
			},
			timeout=10.0,
		)

	async def _get(self, path: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
		resp = await self._client.get(path, params=params)
		self._logger.debug("REST GET %s params=%s status=%s", path, params, resp.status_code)
		resp.raise_for_status()
		return resp.json() if resp.content else {}

	async def _patch(self, path: str, json: Any) -> Dict[str, Any]:
		resp = await self._client.patch(path, json=json)
		self._logger.debug("REST PATCH %s status=%s payload_len=%s", path, resp.status_code, len(str(json)))
		resp.raise_for_status()
		return resp.json() if resp.content else {}

	async def get_contact_id_by_chat_id(self, chat_id: str) -> Optional[int]:
		try:
			params = {"chat_id": chat_id}
			data = await self._get("/api/v4/contacts/chats", params=params)
			embedded = data.get("_embedded", {})
			chats = embedded.get("chats", [])
			if not chats:
				self._logger.debug("No contacts bound to chat_id=%s", chat_id)
				return None
			contact_id = chats[0].get("contact_id")
			self._logger.info("Resolved contact_id=%s for chat_id=%s", contact_id, chat_id)
			return int(contact_id) if contact_id is not None else None
		except Exception as e:
			self._logger.error("Failed to resolve contact by chat_id=%s: %s", chat_id, str(e))
			try:
				reporter = get_error_reporter()
				reporter.log_api_error(
					error=e,
					service_name="AmoCRM",
					endpoint="/api/v4/contacts/chats",
					request_data={"chat_id": chat_id},
				)
			except Exception:
				pass
			return None

	async def update_contact_phone(self, contact_id: int, phone_e164: str, enum_code: str = "WORK") -> None:
		payload = [
			{
				"id": contact_id,
				"custom_fields_values": [
					{
						"field_code": "PHONE",
						"values": [
							{"value": phone_e164, "enum_code": enum_code}
						]
					}
				]
			}
		]
		try:
			self._logger.info("Попытка обновления телефона для контакта id=%s. Новый телефон: %s", contact_id, phone_e164)
			await self._patch("/api/v4/contacts", json=payload)
			self._logger.info("Телефон для контакта id=%s успешно обновлен.", contact_id)
		except Exception as e:
			self._logger.error("Failed to update phone for contact_id=%s: %s", contact_id, str(e))
			try:
				reporter = get_error_reporter()
				reporter.log_api_error(
					error=e,
					service_name="AmoCRM",
					endpoint="/api/v4/contacts",
					request_data=payload,
				)
			except Exception:
				pass

	async def get_contact_links(self, contacts_id: List[int] = None, chats_id: List[str] = None) -> Dict[str, Any]:
		"""Получить связи контактов с чатами по contact_id или chat_id"""
		params = {}
		if contacts_id is not None:
			params["contact_id"] = contacts_id
		if chats_id is not None:
			# Для массива chat_id используем формат chat_id[] как в документации AmoCRM
			for chat_id in chats_id:
				params["chat_id[]"] = chat_id
		self._logger.info(f"chat_id: {chats_id}")
		try:
			self._logger.debug("Получение связей контактов: contacts_id=%s, chats_id=%s", contacts_id, chats_id)
			data = await self._get("/api/v4/contacts/chats", params=params)
			self._logger.debug("Получены связи контактов: total_items=%s", data.get("_total_items", 0))
			if data.get("_total_items", 0) > 0:
				self._logger.info("Найдены связи контактов: %s", data["_embedded"]["chats"])
			return data
		except Exception as e:
			self._logger.error("Failed to get contact links: %s", str(e))
			try:
				reporter = get_error_reporter()
				reporter.log_api_error(
					error=e,
					service_name="AmoCRM",
					endpoint="/api/v4/contacts/chats",
					request_data={"contacts_id": contacts_id, "chats_id": chats_id},
				)
			except Exception:
				pass
			return {"_total_items": 0, "_embedded": {"chats": []}}

