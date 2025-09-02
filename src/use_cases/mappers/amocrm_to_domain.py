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
	# В AmoCRM webhook номер телефона находится в receiver.client_id
	recipient_provider_id = payload.message.receiver.client_id

	# Проверяем, является ли это номером телефона (только цифры)
	if recipient_provider_id and recipient_provider_id.isdigit():
		# Это номер телефона, используем его напрямую
		pass  # recipient_provider_id уже содержит номер телефона
	else:
		# Это не номер телефона, возможно ID клиента
		# В будущем можно добавить логику получения телефона через AmoCRM API
		pass

	recipient = Participant(
		provider_user_id=recipient_provider_id,
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
