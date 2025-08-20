from __future__ import annotations
from typing import Protocol
from domain.models import Message, SentMessageResult, MessageStatusUpdate


class MessageProvider(Protocol):
	async def send_message(self, message: Message) -> SentMessageResult: ...


class StatusNotifier(Protocol):
	async def notify_status(self, status: MessageStatusUpdate) -> None: ...
