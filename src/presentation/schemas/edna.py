from __future__ import annotations
from typing import Optional
from pydantic import BaseModel
from datetime import datetime


# Model for status updates from Edna Cascade API
class EdnaPaymentData(BaseModel):
    type: str
    conversationId: str
    conversationType: str
    chargeable: Optional[bool] = None
    at_type: Optional[str] = None  # for @type field


class EdnaStatusUpdate(BaseModel):
    requestId: str
    messageId: int
    cascadeId: int
    cascadeStageUUID: str
    subject: str
    subjectId: int
    status: str
    statusAt: datetime
    paymentData: Optional[EdnaPaymentData] = None
    error: Optional[str] = None


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


class EdnaChannel(BaseModel):
    id: int
    name: str
    subjectId: Optional[int] = None
    channelAttribute: Optional[str] = None
    subject: str
    active: bool
    registrationStatus: str
    type: str
    instruction: Optional[str] = None
    limit: Optional[str] = None
    qualityScore: Optional[str] = None
    qualityStatus: Optional[str] = None


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
