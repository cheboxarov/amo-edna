from __future__ import annotations
from typing import Optional
from pydantic import BaseModel, Field


class EdnaAttachment(BaseModel):
	url: str
	mimeType: Optional[str] = None
	name: Optional[str] = None
	size: Optional[int] = None


class EdnaIncomingMessage(BaseModel):
	id: str
	imType: str
	subject: str
	text: Optional[str] = None
	attachment: Optional[EdnaAttachment] = None
	from_client: bool = Field(..., alias="fromClient")


class EdnaStatusUpdate(BaseModel):
	id: str
	status: str
