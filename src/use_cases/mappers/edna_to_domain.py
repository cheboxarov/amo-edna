from datetime import datetime
from uuid import uuid4
from domain.models import (
	Message,
	Attachment,
	Participant,
	MessageContentType,
	MessageDirection,
	MessageStatus,
	MessageStatusUpdate,
	ParticipantRole,
	ProviderName,
)
from presentation.schemas.edna import EdnaIncomingMessage, EdnaStatusUpdate


def edna_message_to_domain(payload: EdnaIncomingMessage) -> Message:
	content_type = MessageContentType.text
	attachment = None
	if payload.attachment:
		content_type = (
			MessageContentType.image
			if "image" in (payload.attachment.mimeType or "")
			else MessageContentType.file
		)
		attachment = Attachment(
			url=payload.attachment.url,
			mime_type=payload.attachment.mimeType,
			filename=payload.attachment.name,
			size_bytes=payload.attachment.size,
		)

	sender = Participant(
		provider_user_id=payload.subject,
		role=ParticipantRole.client,
	)
	# В edna получатель — это сам канал/линия, у него нет ID.
	# Мы должны будем найти ID менеджера/бота amoCRM для ответа.
	recipient = Participant(
		provider_user_id="unknown",  # Будет определен позже
		role=ParticipantRole.agent,
	)

	return Message(
		id=str(uuid4()),
		direction=MessageDirection.inbound,  # Входящее от клиента в amoCRM
		content_type=content_type,
		text=payload.text,
		attachment=attachment,
		source_provider=ProviderName.edna,
		source_conversation_id=payload.subject,
		source_message_id=payload.id,
		target_provider=ProviderName.amocrm,
		sent_at=datetime.now(),
		sender=sender,
		recipient=recipient,
	)


def edna_status_to_domain(payload: EdnaStatusUpdate) -> MessageStatusUpdate:
	status_map = {
		"sent": MessageStatus.sent,
		"delivered": MessageStatus.delivered,
		"read": MessageStatus.read,
	}
	return MessageStatusUpdate(
		provider=ProviderName.edna,
		conversation_id="unknown",  # Не приходит в статусе, нужно будет найти
		message_id=payload.id,
		status=status_map.get(payload.status, MessageStatus.sent),
		occurred_at=datetime.now(),
	)
