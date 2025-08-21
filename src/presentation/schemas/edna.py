from __future__ import annotations
from typing import Optional
from pydantic import BaseModel
from datetime import datetime


# This model is for status updates, which seem to have a different structure.
class EdnaStatusUpdate(BaseModel):
	id: str
	status: str


# New models for incoming messages based on the provided log
class EdnaSubscriber(BaseModel):
    id: int
    identifier: str


class EdnaUserInfo(BaseModel):
    userName: Optional[str] = None
    firstName: Optional[str] = None
    lastName: Optional[str] = None
    avatarUrl: Optional[str] = None


class EdnaAttachment(BaseModel):
    url: str
    mimeType: Optional[str] = None
    name: Optional[str] = None
    size: Optional[int] = None


class EdnaMessageContent(BaseModel):
    type: str
    attachment: Optional[EdnaAttachment] = None
    text: Optional[str] = None
    caption: Optional[str] = None


class EdnaIncomingMessage(BaseModel):
    id: int
    subject: str
    subjectId: int
    subscriber: EdnaSubscriber
    userInfo: EdnaUserInfo
    messageContent: EdnaMessageContent
    receivedAt: datetime
    replyOutMessageId: Optional[str] = None
    replyOutMessageExternalRequestId: Optional[str] = None
    replyInMessageId: Optional[str] = None
