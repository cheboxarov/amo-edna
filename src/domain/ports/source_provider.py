from __future__ import annotations
from typing import Protocol, Optional, List
from domain.models import Source


class SourceProvider(Protocol):
	"""Интерфейс для работы с источниками чатов в AmoCRM"""

	async def get_source_by_name(self, name: str) -> Optional[Source]:
		"""Получить источник по названию"""
		...

	async def get_source_by_external_id(self, external_id: str) -> Optional[Source]:
		"""Получить источник по внешнему ID"""
		...

	async def get_all_sources(self) -> List[Source]:
		"""Получить все источники"""
		...

	async def create_source(self, source: Source) -> Source:
		"""Создать новый источник"""
		...

	async def update_source(self, source: Source) -> Source:
		"""Обновить существующий источник"""
		...

	async def delete_source(self, external_id: str) -> None:
		"""Удалить источник по внешнему ID"""
		...
