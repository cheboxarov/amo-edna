import logging
import time
from typing import Optional

from domain.models import Source
from domain.ports.source_provider import SourceProvider
from core.config import AmoCrmSettings
from core.error_logger import get_error_reporter


class SourceManager:
	"""Менеджер для управления источниками чатов в AmoCRM"""

	DEFAULT_SOURCE_NAME = "TeMa Edna"

	def __init__(
		self,
		source_provider: SourceProvider,
		amocrm_settings: AmoCrmSettings,
		logger: Optional[logging.Logger] = None,
	) -> None:
		self._source_provider = source_provider
		self._amocrm_settings = amocrm_settings
		self._logger = logger or logging.getLogger(__name__)
		self._cached_tema_edna_source: Optional[Source] = None

	async def ensure_tema_edna_source_exists(self) -> Source:
		"""
		Гарантирует существование источника 'TeMa Edna'.
		Если источник уже существует - возвращает его.
		Если не существует - создает новый.
		"""
		try:
			# Сначала проверим кеш
			if self._cached_tema_edna_source:
				self._logger.debug("Используем кешированный источник 'TeMa Edna' (ID: %s)", self._cached_tema_edna_source.id)
				return self._cached_tema_edna_source

			# Ищем существующий источник по названию
			self._logger.info("Ищем существующий источник '%s'", self.DEFAULT_SOURCE_NAME)
			existing_source = await self._source_provider.get_source_by_name(self.DEFAULT_SOURCE_NAME)

			if existing_source:
				self._logger.info("Найден существующий источник '%s' с ID: %s", self.DEFAULT_SOURCE_NAME, existing_source.id)
				self._cached_tema_edna_source = existing_source
				return existing_source

			# Источник не найден, создаем новый
			self._logger.info("Источник '%s' не найден, создаем новый", self.DEFAULT_SOURCE_NAME)

			# Проверяем, что pipeline_id задан
			pipeline_id = self._amocrm_settings.source_pipeline_id
			if not pipeline_id:
				self._logger.warning("pipeline_id не задан в настройках. Попытка получить pipeline_id из существующих источников")

				# Пытаемся получить pipeline_id из существующего источника
				all_sources = await self._source_provider.get_all_sources()
				if all_sources:
					pipeline_id = all_sources[0].pipeline_id
					self._logger.info("Используем pipeline_id=%s из существующего источника", pipeline_id)

			if not pipeline_id:
				self._logger.error("Не удалось определить pipeline_id для создания источника")
				return self._create_fallback_source()

			new_source = Source(
				name=self.DEFAULT_SOURCE_NAME,
				external_id=self._generate_external_id(),
				pipeline_id=pipeline_id,
				origin_code="chat",  # Тип источника для чатов
				is_default=False,
			)

			created_source = await self._source_provider.create_source(new_source)
			self._logger.info("Успешно создан источник '%s' с ID: %s", self.DEFAULT_SOURCE_NAME, created_source.id)

			# Кешируем созданный источник
			self._cached_tema_edna_source = created_source
			return created_source

		except Exception as e:
			error_msg = f"Ошибка при работе с источником '{self.DEFAULT_SOURCE_NAME}': {str(e)}"
			self._logger.error(error_msg)

			# Создаем отчет об ошибке
			try:
				error_reporter = get_error_reporter()
				error_reporter.log_error(
					error=e,
					context={
						"source_name": self.DEFAULT_SOURCE_NAME,
						"operation": "ensure_tema_edna_source_exists"
					},
					message="Failed to ensure TeMa Edna source exists"
				)
			except Exception:
				pass

			# В случае ошибки возвращаем временный источник для fallback
			return self._create_fallback_source()

	async def get_tema_edna_source(self) -> Source:
		"""
		Получает источник 'TeMa Edna'.
		Ожидает что источник уже существует.
		"""
		try:
			# Сначала проверим кеш
			if self._cached_tema_edna_source:
				return self._cached_tema_edna_source

			# Ищем источник по названию
			source = await self._source_provider.get_source_by_name(self.DEFAULT_SOURCE_NAME)

			if source:
				self._cached_tema_edna_source = source
				return source
			else:
				self._logger.warning("Источник '%s' не найден при вызове get_tema_edna_source", self.DEFAULT_SOURCE_NAME)
				return self._create_fallback_source()

		except Exception as e:
			self._logger.error("Ошибка при получении источника '%s': %s", self.DEFAULT_SOURCE_NAME, str(e))
			return self._create_fallback_source()

	async def validate_source_name(self, name: str) -> bool:
		"""Проверяет что название источника соответствует ожидаемому"""
		return name == self.DEFAULT_SOURCE_NAME

	async def clear_cache(self) -> None:
		"""Очищает кеш источника"""
		self._logger.debug("Очищаем кеш источника 'TeMa Edna'")
		self._cached_tema_edna_source = None

	def _generate_external_id(self) -> str:
		"""Генерирует уникальный external_id для нового источника"""
		timestamp = int(time.time())
		return f"tema_edna_{timestamp}"

	def _create_fallback_source(self) -> Source:
		"""
		Создает временный источник для fallback в случае ошибок.
		Этот источник не будет сохранен в AmoCRM, но позволит продолжить работу.
		"""
		self._logger.warning("Создаем fallback источник для '%s'", self.DEFAULT_SOURCE_NAME)

		return Source(
			name=self.DEFAULT_SOURCE_NAME,
			external_id="tema_edna_fallback",
			pipeline_id=self._amocrm_settings.source_pipeline_id,
			origin_code="chat",
			is_default=False,
		)
