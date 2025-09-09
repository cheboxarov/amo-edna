import logging
import logging.handlers
import os
from datetime import datetime
from pathlib import Path
from contextlib import asynccontextmanager
from fastapi import FastAPI
from presentation.routers.health import router as health_router
from presentation.routers.webhooks import router as webhooks_router, container
from presentation.middleware.logging import log_request_body_middleware
from infrastructure.http_clients.source_client import AmoCrmSourceProvider
from use_cases.source_manager import SourceManager
from core.config import settings
import uvicorn

# Создаем директорию для логов
logs_dir = Path("/app/logs")
logs_dir.mkdir(exist_ok=True)

# Настраиваем базовое логирование
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.DEBUG)  # Консоль показывает DEBUG+

file_handler = logging.handlers.RotatingFileHandler(
    logs_dir / "app.log",
    maxBytes=10*1024*1024,  # 10MB
    backupCount=5,
    encoding='utf-8'
)
file_handler.setLevel(logging.WARNING)  # Файлы пишут только WARNING+

logging.basicConfig(
    level=logging.DEBUG,  # Корневой уровень DEBUG для всех логгеров
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    handlers=[
        console_handler,
        file_handler
    ]
)

# Настраиваем отдельный логгер для ошибок
error_logger = logging.getLogger("error_reports")
error_logger.setLevel(logging.ERROR)

# Создаем форматтер для детального логирования ошибок
error_formatter = logging.Formatter(
    fmt="""%(asctime)s - ERROR REPORT
=====================================
Logger: %(name)s
Level: %(levelname)s
Message: %(message)s
Module: %(module)s
Function: %(funcName)s
Line: %(lineno)d
Process: %(process)d
Thread: %(thread)d
Exception Type: %(exc_info)s

--- END ERROR REPORT ---
""",
    datefmt="%Y-%m-%d %H:%M:%S"
)

# FileHandler для ошибок с ротацией по дням
error_file_handler = logging.handlers.TimedRotatingFileHandler(
    logs_dir / "errors.log",
    when="midnight",
    interval=1,
    backupCount=30,  # Храним 30 дней
    encoding='utf-8'
)
error_file_handler.setFormatter(error_formatter)
error_file_handler.setLevel(logging.ERROR)

# JSON форматтер для структурированного логирования
json_error_formatter = logging.Formatter(
    '{"timestamp": "%(asctime)s", "level": "%(levelname)s", "logger": "%(name)s", '
    '"message": "%(message)s", "module": "%(module)s", "function": "%(funcName)s", '
    '"line": %(lineno)d, "exception": "%(exc_info)s"}'
)
json_error_handler = logging.handlers.RotatingFileHandler(
    logs_dir / "errors.json",
    maxBytes=50*1024*1024,  # 50MB
    backupCount=10,
    encoding='utf-8'
)
json_error_handler.setFormatter(json_error_formatter)
json_error_handler.setLevel(logging.ERROR)

# Добавляем обработчики к error_logger
error_logger.addHandler(error_file_handler)
error_logger.addHandler(json_error_handler)

# Настраиваем уровни логирования для существующих логгеров
logging.getLogger("amocrm.amojo").setLevel(logging.DEBUG)
logging.getLogger("amocrm.rest").setLevel(logging.DEBUG)
logging.getLogger("edna").setLevel(logging.DEBUG)
logging.getLogger("amocrm_webhook").setLevel(logging.INFO)
logging.getLogger("request_body_logger").setLevel(logging.INFO)
logging.getLogger("use_cases").setLevel(logging.DEBUG)
logging.getLogger("message_links_repo").setLevel(logging.DEBUG)

# Отключаем propagation для error_logger чтобы избежать дублирования
error_logger.propagate = False

# Импортируем и инициализируем ErrorReporter
from core.error_logger import setup_error_reporting

# Создаем глобальную переменную для доступа к error_logger из других модулей
ERROR_LOGGER = error_logger

# Инициализируем ErrorReporter
setup_error_reporting(error_logger)

@asynccontextmanager
async def lifespan(app: FastAPI):
	await container.amocrm_client.ensure_ready()
	await container.edna_client.ensure_ready()

	# Инициализация источника "TeMa Edna" при запуске приложения
	if settings.amocrm.auto_create_sources:
		try:
			logger = logging.getLogger("startup")
			logger.info("Инициализация источника 'TeMa Edna'...")
			source = await container.source_manager.ensure_tema_edna_source_exists()
			logger.info("Источник 'TeMa Edna' успешно инициализирован (ID: %s, external_id: %s)",
					   source.id, source.external_id)
		except Exception as e:
			logger = logging.getLogger("startup")
			logger.error("Ошибка при инициализации источника 'TeMa Edna': %s", str(e))
			logger.warning("Приложение продолжит работу без источника, но функциональность может быть ограничена")

	yield

print(f"Логирование настроено. Логи сохраняются в директорию: {logs_dir.absolute()}")

app = FastAPI(title="edna-amocrm-integration", lifespan=lifespan)

app.middleware("http")(log_request_body_middleware)

app.include_router(health_router)
app.include_router(webhooks_router)

if __name__ == "__main__":
	# Исключаем директорию logs из отслеживания изменений для предотвращения бесконечных перезапусков
	uvicorn.run(
		"main:app",
		host="0.0.0.0",
		port=8000,
		reload_excludes=["logs/*", "logs/**/*", "*.log"],
		log_level="debug"
	)
