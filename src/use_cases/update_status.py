import logging
from domain.models import MessageStatusUpdate, ProviderName, MessageStatus
from domain.ports.message_provider import StatusNotifier
from presentation.schemas.edna import EdnaStatusUpdate
from use_cases.mappers.edna_to_domain import edna_status_to_domain
from use_cases.route_messages import MessageLinkRepository


class UpdateMessageStatusUseCase:
	def __init__(
		self,
		amocrm_notifier: StatusNotifier,
		msg_links: MessageLinkRepository,
		logger: logging.Logger | None = None,
	) -> None:
		self._amocrm_notifier = amocrm_notifier
		self._msg_links = msg_links
		self._logger = logger or logging.getLogger(__name__)

	async def execute(self, payload: EdnaStatusUpdate) -> None:
		self._logger.debug(
			"Получен статус от Edna: requestId=%s, messageId=%s, status=%s, subject=%s",
			payload.requestId, payload.messageId, payload.status, payload.subject
		)

		status_update = edna_status_to_domain(payload)
		self._logger.debug(
			"Преобразованный статус: provider=%s, conversation_id=%s, message_id=%s, status=%s",
			status_update.provider, status_update.conversation_id, status_update.message_id, status_update.status
		)

		# Находим связанное сообщение в amoCRM по requestId (который мы использовали как source_message_id при отправке)
		link = await self._msg_links.get_link_by_source_id(payload.requestId)

		self._logger.debug(
			"Найденная связь: requestId=%s, link=%s",
			payload.requestId, link.model_dump() if link else None
		)

		# Проверяем, что сообщение было отправлено ИЗ AmoCRM В Edna
		if link and link.source_provider == ProviderName.amocrm and link.target_provider == ProviderName.edna:
			# Маппинг статусов Edna -> AmoCRM
			edna_to_amocrm_status = {
				MessageStatus.sent: 1,      # SENT -> доставлено
				MessageStatus.delivered: 1, # DELIVERED -> доставлено
				MessageStatus.read: 2,      # READ -> прочитано
			}

			amocrm_status = edna_to_amocrm_status.get(status_update.status)
			amocrm_message_id = link.source_message_id  # ID сообщения в AmoCRM

			self._logger.info(
				"Подготовка к обновлению статуса: edna_status=%s -> amocrm_status=%s, amocrm_message_id=%s",
				payload.status, amocrm_status, amocrm_message_id
			)

			if amocrm_status:
				self._logger.debug(
					"Обновление статуса сообщения в AmoCRM: edna_status=%s, amocrm_status=%d, message_id=%s",
					payload.status, amocrm_status, amocrm_message_id
				)

				try:
					await self._amocrm_notifier.update_message_status(
						message_id=amocrm_message_id,
						status=amocrm_status
					)
					self._logger.info("✅ Статус сообщения успешно обновлен в AmoCRM")
				except Exception as e:
					self._logger.error("❌ Ошибка при обновлении статуса в AmoCRM: %s", str(e))
					# Можно добавить дополнительную обработку ошибки здесь
			else:
				self._logger.debug(
					"Статус %s от Edna не требует обновления в AmoCRM",
					payload.status
				)
		else:
			self._logger.warning(
				"❌ Связь с сообщением не найдена или некорректна: requestId=%s, link=%s",
				payload.requestId, link.model_dump() if link else None
			)
			if link:
				self._logger.warning(
					"Детали связи: source_provider=%s, target_provider=%s, ожидаем source=amocrm, target=edna",
					link.source_provider, link.target_provider
				)
