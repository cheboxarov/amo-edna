import logging
from typing import Any, Dict, Optional, List
from datetime import datetime

import httpx
from domain.models import Source
from domain.ports.source_provider import SourceProvider
from core.config import AmoCrmSettings
from core.error_logger import get_error_reporter


class AmoCrmSourceProvider(SourceProvider):
	"""Реализация SourceProvider для работы с API источников AmoCRM"""

	def __init__(self, settings: AmoCrmSettings):
		self._logger = logging.getLogger("amocrm.sources")
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
		self._logger.info("AmoCRM Source Provider initialized")

	async def _get(self, path: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
		"""Вспомогательный метод для GET запросов"""
		resp = await self._client.get(path, params=params)
		self._logger.debug("REST GET %s params=%s status=%s", path, params, resp.status_code)
		resp.raise_for_status()
		return resp.json() if resp.content else {}

	async def _post(self, path: str, json: Any) -> Dict[str, Any]:
		"""Вспомогательный метод для POST запросов"""
		resp = await self._client.post(path, json=json)
		self._logger.debug("REST POST %s status=%s payload_len=%s", path, resp.status_code, len(str(json)))
		resp.raise_for_status()
		return resp.json() if resp.content else {}

	async def _patch(self, path: str, json: Any) -> Dict[str, Any]:
		"""Вспомогательный метод для PATCH запросов"""
		resp = await self._client.patch(path, json=json)
		self._logger.debug("REST PATCH %s status=%s payload_len=%s", path, resp.status_code, len(str(json)))
		resp.raise_for_status()
		return resp.json() if resp.content else {}

	async def _delete(self, path: str) -> None:
		"""Вспомогательный метод для DELETE запросов"""
		resp = await self._client.delete(path)
		self._logger.debug("REST DELETE %s status=%s", path, resp.status_code)
		resp.raise_for_status()

	def _source_from_api_response(self, data: Dict[str, Any]) -> Source:
		"""Преобразовать ответ API в модель Source"""
		# API может возвращать поля как массивы или как простые значения
		# Извлекаем первый элемент массива, если это массив, иначе используем значение напрямую
		def extract_value(field_name: str, default=""):
			value = data.get(field_name, default)
			if isinstance(value, list) and len(value) > 0:
				return value[0]
			return value

		return Source(
			id=data.get("id"),
			name=extract_value("name", ""),
			external_id=extract_value("external_id", ""),
			pipeline_id=extract_value("pipeline_id"),
			services=data.get("services", []),
			is_default=data.get("default", False),
			origin_code=data.get("origin_code"),
			request_id=data.get("request_id"),
			created_at=datetime.fromisoformat(data["created_at"]) if data.get("created_at") else None,
			updated_at=datetime.fromisoformat(data["updated_at"]) if data.get("updated_at") else None,
		)

	async def get_source_by_name(self, name: str) -> Optional[Source]:
		"""Получить источник по названию"""
		try:
			self._logger.debug("Ищем источник по названию: %s", name)
			data = await self._get("/api/v4/sources")

			embedded = data.get("_embedded", {})
			sources_data = embedded.get("sources", [])

			for source_data in sources_data:
				if source_data.get("name") == name:
					source = self._source_from_api_response(source_data)
					self._logger.debug("Найден источник: %s (ID: %s)", name, source.id)
					return source

			self._logger.debug("Источник с названием '%s' не найден", name)
			return None

		except Exception as e:
			self._logger.error("Ошибка при поиске источника по названию '%s': %s", name, str(e))
			try:
				error_reporter = get_error_reporter()
				error_reporter.log_api_error(
					error=e,
					service_name="AmoCRM",
					endpoint="/api/v4/sources",
					request_data={"search_by": "name", "name": name}
				)
			except Exception:
				pass
			return None

	async def get_source_by_external_id(self, external_id: str) -> Optional[Source]:
		"""Получить источник по внешнему ID"""
		try:
			self._logger.debug("Ищем источник по external_id: %s", external_id)
			data = await self._get("/api/v4/sources")

			embedded = data.get("_embedded", {})
			sources_data = embedded.get("sources", [])

			for source_data in sources_data:
				if source_data.get("external_id") == external_id:
					source = self._source_from_api_response(source_data)
					self._logger.debug("Найден источник по external_id: %s (ID: %s)", external_id, source.id)
					return source

			self._logger.debug("Источник с external_id '%s' не найден", external_id)
			return None

		except Exception as e:
			self._logger.error("Ошибка при поиске источника по external_id '%s': %s", external_id, str(e))
			try:
				error_reporter = get_error_reporter()
				error_reporter.log_api_error(
					error=e,
					service_name="AmoCRM",
					endpoint="/api/v4/sources",
					request_data={"search_by": "external_id", "external_id": external_id}
				)
			except Exception:
				pass
			return None

	async def get_all_sources(self) -> List[Source]:
		"""Получить все источники"""
		try:
			self._logger.debug("Получаем все источники")
			data = await self._get("/api/v4/sources")

			embedded = data.get("_embedded", {})
			sources_data = embedded.get("sources", [])

			sources = []
			for source_data in sources_data:
				sources.append(self._source_from_api_response(source_data))

			self._logger.debug("Получено %d источников", len(sources))
			return sources

		except Exception as e:
			self._logger.error("Ошибка при получении списка источников: %s", str(e))
			try:
				error_reporter = get_error_reporter()
				error_reporter.log_api_error(
					error=e,
					service_name="AmoCRM",
					endpoint="/api/v4/sources"
				)
			except Exception:
				pass
			return []

	async def create_source(self, source: Source) -> Source:
		"""Создать новый источник"""
		try:
			self._logger.info("Создаем новый источник: name='%s', external_id='%s'", source.name, source.external_id)

			# API требует массив объектов источников
			source_payload = {
				"name": source.name,
				"external_id": source.external_id,
				"default": source.is_default,
			}

			if source.pipeline_id:
				source_payload["pipeline_id"] = source.pipeline_id
				self._logger.debug("Добавлен pipeline_id=%s в payload", source.pipeline_id)

			# Добавляем пустой массив services для совместимости с API
			source_payload["services"] = []

			# Оборачиваем в массив, как требует API
			payload = [source_payload]

			self._logger.debug("Полный payload для создания источника: %s", payload)

			data = await self._post("/api/v4/sources", payload)

			# API возвращает массив созданных источников
			if isinstance(data, dict) and "_embedded" in data:
				sources_data = data["_embedded"]["sources"]
				if sources_data:
					created_source = self._source_from_api_response(sources_data[0])
					self._logger.info("Источник успешно создан: name='%s', id=%s", created_source.name, created_source.id)
					return created_source

			# Fallback: если структура ответа отличается
			if isinstance(data, list) and len(data) > 0:
				created_source = self._source_from_api_response(data[0])
				self._logger.info("Источник успешно создан: name='%s', id=%s", created_source.name, created_source.id)
				return created_source

			# Последний fallback
			created_source = self._source_from_api_response(data)
			self._logger.info("Источник успешно создан: name='%s', id=%s", created_source.name, created_source.id)
			return created_source

		except Exception as e:
			self._logger.error("Ошибка при создании источника '%s': %s", source.name, str(e))
			self._logger.error("Payload, который вызвал ошибку: %s", payload)

			# Если это HTTP ошибка, попробуем получить детали
			if hasattr(e, 'response'):
				try:
					response_text = e.response.text if hasattr(e.response, 'text') else str(e.response)
					self._logger.error("Ответ сервера: %s", response_text)
				except Exception:
					pass

			try:
				error_reporter = get_error_reporter()
				error_reporter.log_api_error(
					error=e,
					service_name="AmoCRM",
					endpoint="/api/v4/sources",
					request_data=payload
				)
			except Exception:
				pass
			raise

	async def update_source(self, source: Source) -> Source:
		"""Обновить существующий источник"""
		try:
			if not source.id:
				raise ValueError("Cannot update source without ID")

			self._logger.info("Обновляем источник: id=%s, name='%s'", source.id, source.name)

			# API требует массив объектов источников для обновления
			source_payload = {
				"id": source.id,
				"name": source.name,
				"external_id": source.external_id,
				"default": source.is_default,
			}

			if source.pipeline_id:
				source_payload["pipeline_id"] = source.pipeline_id

			# Добавляем пустой массив services для совместимости с API
			source_payload["services"] = []

			# Оборачиваем в массив, как требует API
			payload = [source_payload]

			data = await self._patch("/api/v4/sources", payload)

			# API возвращает массив обновленных источников
			if isinstance(data, dict) and "_embedded" in data:
				sources_data = data["_embedded"]["sources"]
				if sources_data:
					updated_source = self._source_from_api_response(sources_data[0])
					self._logger.info("Источник успешно обновлен: id=%s, name='%s'", updated_source.id, updated_source.name)
					return updated_source

			# Fallback: если структура ответа отличается
			if isinstance(data, list) and len(data) > 0:
				updated_source = self._source_from_api_response(data[0])
				self._logger.info("Источник успешно обновлен: id=%s, name='%s'", updated_source.id, updated_source.name)
				return updated_source

			# Последний fallback
			updated_source = self._source_from_api_response(data)
			self._logger.info("Источник успешно обновлен: id=%s, name='%s'", updated_source.id, updated_source.name)
			return updated_source

		except Exception as e:
			self._logger.error("Ошибка при обновлении источника id=%s: %s", source.id, str(e))
			try:
				error_reporter = get_error_reporter()
				error_reporter.log_api_error(
					error=e,
					service_name="AmoCRM",
					endpoint=f"/api/v4/sources/{source.id}",
					request_data=payload
				)
			except Exception:
				pass
			raise

	async def delete_source(self, external_id: str) -> None:
		"""Удалить источник по внешнему ID"""
		try:
			# Сначала найдем источник по external_id, чтобы получить его ID
			source = await self.get_source_by_external_id(external_id)
			if not source or not source.id:
				self._logger.warning("Источник с external_id '%s' не найден для удаления", external_id)
				return

			self._logger.info("Удаляем источник: external_id='%s', id=%s", external_id, source.id)

			# Используем DELETE с ID в URL, как указано в документации
			await self._delete(f"/api/v4/sources/{source.id}")

			self._logger.info("Источник успешно удален: external_id='%s', id=%s", external_id, source.id)

		except Exception as e:
			self._logger.error("Ошибка при удалении источника external_id='%s': %s", external_id, str(e))
			try:
				error_reporter = get_error_reporter()
				error_reporter.log_api_error(
					error=e,
					service_name="AmoCRM",
					endpoint=f"/api/v4/sources/{source.id if source else 'unknown'}"
				)
			except Exception:
				pass
			raise
