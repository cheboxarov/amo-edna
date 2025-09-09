from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel
from typing import Union, Optional

from presentation.schemas.edna import EdnaIncomingMessage, EdnaStatusUpdate
from presentation.schemas.amocrm import AmoIncomingWebhook
from use_cases import (
	RouteMessageFromAmoCrmUseCase,
	RouteMessageFromEdnaUseCase,
	UpdateMessageStatusUseCase,
	CreateChatUseCase,
)
from infrastructure.http_clients.amocrm_client import AmoCrmHttpClient
from infrastructure.http_clients.edna_client import EdnaHttpClient
from infrastructure.http_clients.amocrm_rest_client import AmoCrmRestClient
from infrastructure.repositories.in_memory_links import (
	InMemoryConversationLinkRepository,
	InMemoryMessageLinkRepository,
)
from infrastructure.http_clients.source_client import AmoCrmSourceProvider
from use_cases.source_manager import SourceManager
from core.config import settings
from core.error_logger import get_error_reporter

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
	CreateChatUseCase,
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
		self.amocrm_rest_client = AmoCrmRestClient(settings=settings.amocrm)

		# Инициализация SourceManager для работы с источниками
		self.source_provider = AmoCrmSourceProvider(settings=settings.amocrm)
		self.source_manager = SourceManager(
			source_provider=self.source_provider,
			amocrm_settings=settings.amocrm,
			logger=logger,
		)

		self.create_chat_uc = CreateChatUseCase(
			amocrm_provider=self.amocrm_client,
			conv_links=self.conv_link_repo,
			amocrm_settings=settings.amocrm,
			source_manager=self.source_manager,
			logger=logger,
		)
		self.route_from_edna_uc = RouteMessageFromEdnaUseCase(
			amocrm_provider=self.amocrm_client,
			amocrm_rest=self.amocrm_rest_client,
			conv_links=self.conv_link_repo,
			msg_links=self.msg_link_repo,
			create_chat_usecase=self.create_chat_uc if settings.amocrm.auto_create_chats else None,
			logger=logger,
		)
		self.route_from_amocrm_uc = RouteMessageFromAmoCrmUseCase(
			edna_provider=self.edna_client,
			amocrm_provider=self.amocrm_client,
			conv_links=self.conv_link_repo,
			msg_links=self.msg_link_repo,
			logger=logger,
		)
		self.update_status_uc = UpdateMessageStatusUseCase(
			amocrm_notifier=self.amocrm_client, msg_links=self.msg_link_repo, logger=logger
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


@router.post("/amocrm/{secret_key}_{account_id}", response_model=Ok)
async def amocrm_webhook(
	secret_key: str,
	account_id: str,
	payload: AmoIncomingWebhook,
	# В amoCRM валидация обычно идет по секретному ключу в URL или подписи
	route_uc: RouteMessageFromAmoCrmUseCase = Depends(
		lambda: container.route_from_amocrm_uc
	),
):
	logger = logging.getLogger("amocrm_webhook")

	logger.info(
		"Получен вебхук от AmoCRM: secret_key=%s, account_id=%s, sender=%s, conversation_id=%s, message_type=%s",
		secret_key,
		account_id,
		payload.message.sender.name,
		payload.message.conversation.id,
		payload.message.message.type
	)

	logger.debug(
		"Детали вебхука: time=%s, receiver=%s, message_id=%s, text='%s'",
		payload.time,
		payload.message.receiver.name,
		payload.message.message.id,
		payload.message.message.text[:100] + "..." if payload.message.message.text and len(payload.message.message.text) > 100 else payload.message.message.text
	)

	# TODO: Реализовать валидацию вебхука
	# Можно добавить валидацию secret_key здесь
	try:
		await route_uc.execute(payload)
		logger.info("Вебхук от AmoCRM успешно обработан")
		return Ok()
	except Exception as e:
		logger.exception("Ошибка при обработке вебхука от AmoCRM: %s", str(e))

		# Создаем детальный отчет об ошибке вебхука
		try:
			error_reporter = get_error_reporter()
			error_reporter.log_error(
				error=e,
				context={
					"webhook_source": "amocrm",
					"secret_key": secret_key,
					"account_id": account_id,
					"sender": payload.message.sender.name if hasattr(payload, 'message') else "unknown",
					"conversation_id": payload.message.conversation.id if hasattr(payload, 'message') else "unknown",
					"message_type": payload.message.message.type if hasattr(payload, 'message') and hasattr(payload.message, 'message') else "unknown"
				},
				message="Webhook processing error from AmoCRM"
			)
		except Exception as report_error:
			logger.error("Не удалось создать отчет об ошибке вебхука: %s", str(report_error))

		# В случае ошибки все равно возвращаем 200, чтобы AmoCRM не повторял запрос
		return Ok()
