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
	if payload.message.media:
		content_type = (
			MessageContentType.image
			if "image" in (payload.message.mime_type or "")
			else MessageContentType.file
		)
		attachment = Attachment(
			url=payload.message.media,
			mime_type=payload.message.mime_type,
			filename=payload.message.file_name,
			size_bytes=payload.message.file_size,
		)

	sender = Participant(
		provider_user_id=payload.sender.id,
		role=ParticipantRole.agent,
		display_name=payload.sender.name,
	)
	# В amoCRM получатель — это сам канал, у него нет ID.
	# Мы должны будем найти ID клиента edna по ID чата amoCRM.
	recipient = Participant(
		provider_user_id="unknown",  # Будет определен позже
		role=ParticipantRole.client,
	)

	return Message(
		id=str(uuid4()),
		direction=MessageDirection.outbound,  # Исходящее из amoCRM к клиенту
		content_type=content_type,
		text=payload.message.text,
		attachment=attachment,
		source_provider=ProviderName.amocrm,
		source_conversation_id=payload.conversation.id,
		source_message_id=payload.message.id,
		target_provider=ProviderName.edna,
		sent_at=datetime.fromtimestamp(payload.message.timestamp),
		sender=sender,
		recipient=recipient,
	)
