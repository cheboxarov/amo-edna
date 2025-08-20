from __future__ import annotations
from typing import Optional, List
from pydantic import BaseModel, Field


class AmoMessage(BaseModel):
	id: str
	text: Optional[str] = None
	media: Optional[str] = None
	file_name: Optional[str] = None
	file_size: Optional[int] = None
	mime_type: Optional[str] = None
	timestamp: int = Field(..., alias="date")


class AmoSender(BaseModel):
	id: str
	name: str


class AmoConversation(BaseModel):
	id: str


class AmoAccount(BaseModel):
	id: str
	subdomain: str


class AmoIncomingWebhook(BaseModel):
	message: AmoMessage
	sender: AmoSender
	conversation: AmoConversation
	account: AmoAccount
