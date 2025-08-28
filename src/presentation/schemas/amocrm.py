from __future__ import annotations
from typing import Optional, List
from pydantic import BaseModel, Field


class AmoMessage(BaseModel):
	id: str
	type: str
	text: Optional[str] = None
	markup: Optional[str] = None
	tag: str = ""
	media: str = ""
	thumbnail: str = ""
	file_name: str = ""
	file_size: int = 0


class AmoReceiver(BaseModel):
	id: str
	name: str
	client_id: str


class AmoSender(BaseModel):
	id: str
	name: str


class AmoConversation(BaseModel):
	id: str
	client_id: str


class AmoIncomingMessage(BaseModel):
	receiver: AmoReceiver
	sender: AmoSender
	conversation: AmoConversation
	timestamp: int
	msec_timestamp: int
	message: AmoMessage


class AmoIncomingWebhook(BaseModel):
	account_id: str
	time: int
	message: AmoIncomingMessage
