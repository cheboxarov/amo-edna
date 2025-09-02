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
		self._logger.info(
			"Получен статус от Edna: requestId=%s, messageId=%s, status=%s, subject=%s",
			payload.requestId, payload.messageId, payload.status, payload.subject
		)

		status_update = edna_status_to_domain(payload)
		# Находим связанное сообщение в amoCRM по requestId (который мы использовали как source_message_id при отправке)
		link = await self._msg_links.get_link_by_source_id(payload.requestId)
		if link and link.target_provider == ProviderName.amocrm:
			# Маппинг статусов Edna -> AmoCRM
			edna_to_amocrm_status = {
				MessageStatus.sent: 1,      # SENT -> доставлено
				MessageStatus.delivered: 1, # DELIVERED -> доставлено
				MessageStatus.read: 2,      # READ -> прочитано
			}

			amocrm_status = edna_to_amocrm_status.get(status_update.status)
			if amocrm_status:
				self._logger.info(
					"Обновление статуса сообщения в AmoCRM: edna_status=%s, amocrm_status=%d, message_id=%s",
					payload.status, amocrm_status, link.target_message_id
				)

				try:
					await self._amocrm_notifier.update_message_status(
						message_id=link.target_message_id,
						status=amocrm_status
					)
					self._logger.info("Статус сообщения успешно обновлен в AmoCRM")
				except Exception as e:
					self._logger.error("Ошибка при обновлении статуса в AmoCRM: %s", str(e))
			else:
				self._logger.info(
					"Статус %s от Edna не требует обновления в AmoCRM",
					payload.status
				)
		else:
			self._logger.warning(
				"Связь с сообщением не найдена в AmoCRM: requestId=%s, link=%s",
				payload.requestId, link
			)
