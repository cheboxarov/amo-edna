from __future__ import annotations
from enum import Enum
from typing import Optional
from datetime import datetime
from pydantic import BaseModel


class ProviderName(str, Enum):
	edna = "edna"
	amocrm = "amocrm"


class ParticipantRole(str, Enum):
	client = "client"
	agent = "agent"


class MessageContentType(str, Enum):
	text = "text"
	image = "image"
	file = "file"


class MessageDirection(str, Enum):
	inbound = "inbound"
	outbound = "outbound"


class MessageStatus(str, Enum):
	sent = "sent"
	delivered = "delivered"
	read = "read"


class Attachment(BaseModel):
	url: str
	mime_type: Optional[str] = None
	filename: Optional[str] = None
	size_bytes: Optional[int] = None


class Participant(BaseModel):
	provider_user_id: str
	role: ParticipantRole
	display_name: Optional[str] = None


class Message(BaseModel):
	id: str
	direction: MessageDirection
	content_type: MessageContentType
	text: Optional[str] = None
	attachment: Optional[Attachment] = None
	source_provider: ProviderName
	source_conversation_id: Optional[str] = None
	source_message_id: Optional[str] = None
	target_provider: ProviderName
	target_conversation_id: Optional[str] = None
	request_id: Optional[str] = None
	sent_at: Optional[datetime] = None
	sender: Participant
	recipient: Participant


class ProviderMessageRef(BaseModel):
	provider: ProviderName
	conversation_id: str
	message_id: str


class SentMessageResult(BaseModel):
	reference: ProviderMessageRef


class MessageStatusUpdate(BaseModel):
	provider: ProviderName
	conversation_id: str
	message_id: str
	status: MessageStatus
	occurred_at: datetime


class ConversationLink(BaseModel):
	edna_conversation_id: str
	amocrm_chat_id: str


class MessageLink(BaseModel):
	source_provider: ProviderName
	source_message_id: str
	target_provider: ProviderName
	target_message_id: str
	target_conversation_id: str


class ChatSource(BaseModel):
	external_id: str


class ChatUserProfile(BaseModel):
	phone: Optional[str] = None
	email: Optional[str] = None


class ChatUser(BaseModel):
	id: str
	ref_id: Optional[str] = None
	name: str
	avatar: Optional[str] = None
	profile: Optional[ChatUserProfile] = None
	profile_link: Optional[str] = None
	client_id: Optional[str] = None


class ChatCreationRequest(BaseModel):
	conversation_id: str
	source: Optional[ChatSource] = None
	user: ChatUser


class ChatCreationResult(BaseModel):
	id: str
	user: ChatUser
	conversation_id: str


class Source(BaseModel):
	"""Модель источника чатов в AmoCRM"""
	id: Optional[int] = None
	name: str
	external_id: str
	pipeline_id: Optional[int] = None
	services: list[dict] = []
	is_default: bool = False
	origin_code: Optional[str] = None  # Тип источника (chat, etc.)
	request_id: Optional[str] = None
	created_at: Optional[datetime] = None
	updated_at: Optional[datetime] = None
