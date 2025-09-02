from domain.models import MessageStatusUpdate, ProviderName
from domain.ports.message_provider import StatusNotifier
from presentation.schemas.edna import EdnaStatusUpdate
from use_cases.mappers.edna_to_domain import edna_status_to_domain
from use_cases.route_messages import MessageLinkRepository


class UpdateMessageStatusUseCase:
	def __init__(
		self,
		amocrm_notifier: StatusNotifier,
		msg_links: MessageLinkRepository,
	) -> None:
		self._amocrm_notifier = amocrm_notifier
		self._msg_links = msg_links

	async def execute(self, payload: EdnaStatusUpdate) -> None:
		status_update = edna_status_to_domain(payload)
		# Находим связанное сообщение в amoCRM по requestId (который мы использовали как source_message_id при отправке)
		link = await self._msg_links.get_link_by_source_id(payload.requestId)
		if link and link.target_provider == ProviderName.amocrm:
			# Обогащаем событие информацией о чате и сообщении в amoCRM
			status_update_for_amocrm = MessageStatusUpdate(
				provider=ProviderName.amocrm,
				conversation_id=link.target_conversation_id,
				message_id=link.target_message_id,
				status=status_update.status,
				occurred_at=status_update.occurred_at,
			)
			await self._amocrm_notifier.notify_status(status_update_for_amocrm)
