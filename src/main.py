import logging
import logging.handlers
import os
from datetime import datetime
from pathlib import Path
from fastapi import FastAPI
from presentation.routers.health import router as health_router
from presentation.routers.webhooks import router as webhooks_router, container
from presentation.middleware.logging import log_request_body_middleware
import uvicorn

# Создаем директорию для логов
logs_dir = Path("logs")
logs_dir.mkdir(exist_ok=True)

# Настраиваем базовое логирование
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(),  # Логи в консоль
        logging.handlers.RotatingFileHandler(
            logs_dir / "app.log",
            maxBytes=10*1024*1024,  # 10MB
            backupCount=5,
            encoding='utf-8'
        )
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
logging.getLogger("edna").setLevel(logging.DEBUG)
logging.getLogger("amocrm_webhook").setLevel(logging.INFO)
logging.getLogger("request_body_logger").setLevel(logging.INFO)

# Отключаем propagation для error_logger чтобы избежать дублирования
error_logger.propagate = False

# Импортируем и инициализируем ErrorReporter
from core.error_logger import setup_error_reporting

# Создаем глобальную переменную для доступа к error_logger из других модулей
ERROR_LOGGER = error_logger

# Инициализируем ErrorReporter
setup_error_reporting(error_logger)

print(f"Логирование настроено. Логи сохраняются в директорию: {logs_dir.absolute()}")

app = FastAPI(title="edna-amocrm-integration")

app.middleware("http")(log_request_body_middleware)

app.include_router(health_router)
app.include_router(webhooks_router)


@app.on_event("startup")
async def startup() -> None:
	await container.amocrm_client.ensure_ready()
	await container.edna_client.ensure_ready()


if __name__ == "__main__":
	# Исключаем директорию logs из отслеживания изменений для предотвращения бесконечных перезапусков
	uvicorn.run(
		"main:app",
		host="0.0.0.0",
		port=8000,
		reload=True,
		reload_excludes=["logs/*", "logs/**/*", "*.log"],
		log_level="debug"
	)
