from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel
from typing import Union, Optional

from presentation.schemas.edna import EdnaIncomingMessage, EdnaStatusUpdate
from presentation.schemas.amocrm import AmoIncomingWebhook
from use_cases import (
	RouteMessageFromAmoCrmUseCase,
	RouteMessageFromEdnaUseCase,
	UpdateMessageStatusUseCase,
)
from infrastructure.http_clients.amocrm_client import AmoCrmHttpClient
from infrastructure.http_clients.edna_client import EdnaHttpClient
from infrastructure.repositories.in_memory_links import (
	InMemoryConversationLinkRepository,
	InMemoryMessageLinkRepository,
)
from core.config import settings

router = APIRouter(prefix="/webhooks")


import logging
from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel
from typing import Union, Optional

from presentation.schemas.edna import EdnaIncomingMessage, EdnaStatusUpdate
from presentation.schemas.amocrm import AmoIncomingWebhook
from use_cases import (
	RouteMessageFromAmoCrmUseCase,
	RouteMessageFromEdnaUseCase,
	UpdateMessageStatusUseCase,
)
from infrastructure.http_clients.amocrm_client import AmoCrmHttpClient
from infrastructure.http_clients.edna_client import EdnaHttpClient
from infrastructure.repositories.in_memory_links import (
	InMemoryConversationLinkRepository,
	InMemoryMessageLinkRepository,
)
from core.config import settings

router = APIRouter(prefix="/webhooks")


# --- DI Container ---
class Container:
	def __init__(self):
		logger = logging.getLogger("use_cases")
		logger.setLevel(logging.INFO)

		self.conv_link_repo = InMemoryConversationLinkRepository()
		self.msg_link_repo = InMemoryMessageLinkRepository()
		self.edna_client = EdnaHttpClient(settings=settings.edna)
		self.amocrm_client = AmoCrmHttpClient(settings=settings.amocrm)
		self.route_from_edna_uc = RouteMessageFromEdnaUseCase(
			amocrm_provider=self.amocrm_client,
			conv_links=self.conv_link_repo,
			msg_links=self.msg_link_repo,
			logger=logger,
		)
		self.route_from_amocrm_uc = RouteMessageFromAmoCrmUseCase(
			edna_provider=self.edna_client,
			conv_links=self.conv_link_repo,
			msg_links=self.msg_link_repo,
		)
		self.update_status_uc = UpdateMessageStatusUseCase(
			amocrm_notifier=self.amocrm_client, msg_links=self.msg_link_repo
		)


container = Container()


class Ok(BaseModel):
	code: str = "ok"


@router.get("/edna", response_model=Ok)
async def edna_webhook_validation():
	"""Handles Edna webhook validation GET request."""
	return Ok()


@router.head("/edna", response_model=Ok)
async def edna_webhook_validation_head():
	"""Handles Edna webhook validation HEAD request."""
	return Ok()


@router.post("/edna", response_model=Ok)
async def edna_webhook(
	payload: Union[EdnaIncomingMessage, EdnaStatusUpdate],
	# В реальном проекте здесь была бы проверка подписи или токена
	x_auth_token: Optional[str] = Header(None),
	route_uc: RouteMessageFromEdnaUseCase = Depends(
		lambda: container.route_from_edna_uc
	),
	status_uc: UpdateMessageStatusUseCase = Depends(
		lambda: container.update_status_uc
	),
):
	# TODO: Реализовать валидацию вебхука (например, по токену)
	# if x_auth_token != "some_secret_token":
	#     raise HTTPException(status_code=403, detail="Forbidden")

	if isinstance(payload, EdnaIncomingMessage):
		await route_uc.execute(payload)
	elif isinstance(payload, EdnaStatusUpdate):
		await status_uc.execute(payload)
	return Ok()


@router.post("/amocrm", response_model=Ok)
async def amocrm_webhook(
	payload: AmoIncomingWebhook,
	# В amoCRM валидация обычно идет по секретному ключу в URL или подписи
	route_uc: RouteMessageFromAmoCrmUseCase = Depends(
		lambda: container.route_from_amocrm_uc
	),
):
	# TODO: Реализовать валидацию вебхука
	await route_uc.execute(payload)
	return Ok()
