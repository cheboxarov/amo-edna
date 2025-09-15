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

	amo_type = (payload.message.message.type or "").lower()
	if amo_type in ("file", "document"):
		content_type = MessageContentType.file
	elif amo_type in ("image", "picture"):
		content_type = MessageContentType.image
	else:
		content_type = MessageContentType.text

	if payload.message.message.media:
		attachment = Attachment(
			url=payload.message.message.media,
			mime_type=None,
			filename=payload.message.message.file_name,
			size_bytes=payload.message.message.file_size,
		)

	sender = Participant(
		provider_user_id=payload.message.sender.id,
		role=ParticipantRole.agent,
		display_name=payload.message.sender.name,
	)

	recipient_provider_id = payload.message.receiver.client_id
	recipient = Participant(
		provider_user_id=recipient_provider_id,
		role=ParticipantRole.client,
		display_name=payload.message.receiver.name,
	)

	return Message(
		id=str(uuid4()),
		direction=MessageDirection.outbound,
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
