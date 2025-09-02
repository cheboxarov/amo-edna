from datetime import datetime
from uuid import uuid4
from domain.models import (
	Message,
	Attachment,
	Participant,
	MessageContentType,
	MessageDirection,
	ParticipantRole,
	ProviderName,
)
from presentation.schemas.amocrm import AmoIncomingWebhook


def amocrm_to_domain(payload: AmoIncomingWebhook) -> Message:
	content_type = MessageContentType.text
	attachment = None

	if payload.message.message.type == "file":
		content_type = MessageContentType.file
	elif payload.message.message.type == "image":
		content_type = MessageContentType.image
	else:
		content_type = MessageContentType.text

	if payload.message.message.media:
		attachment = Attachment(
			url=payload.message.message.media,
			mime_type=None,  # В новых данных нет mime_type
			filename=payload.message.message.file_name,
			size_bytes=payload.message.message.file_size,
		)

	sender = Participant(
		provider_user_id=payload.message.sender.id,
		role=ParticipantRole.agent,
		display_name=payload.message.sender.name,
	)

	# Получатель - это клиент из receiver
	# Для Edna нужен номер телефона, но в AmoCRM webhook его нет
	# Используем client_id как временный идентификатор
	recipient = Participant(
		provider_user_id=payload.message.receiver.client_id,
		role=ParticipantRole.client,
		display_name=payload.message.receiver.name,
	)

	return Message(
		id=str(uuid4()),
		direction=MessageDirection.outbound,  # Исходящее из amoCRM к клиенту
		content_type=content_type,
		text=payload.message.message.text,
		attachment=attachment,
		source_provider=ProviderName.amocrm,
		source_conversation_id=payload.message.conversation.id,
		source_message_id=payload.message.message.id,
		target_provider=ProviderName.edna,
		sent_at=datetime.fromtimestamp(payload.message.timestamp),
		sender=sender,
		recipient=recipient,
	)
