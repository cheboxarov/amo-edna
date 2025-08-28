"""
Модуль для логирования ошибок в отдельные файлы.
Предоставляет структурированное логирование ошибок с детальной информацией.
"""

import logging
import json
import traceback
from typing import Any, Dict, Optional
from datetime import datetime


class ErrorReporter:
    """Класс для структурированного логирования ошибок"""

    def __init__(self, logger: logging.Logger):
        self.logger = logger

    def log_error(
        self,
        error: Exception,
        context: Optional[Dict[str, Any]] = None,
        message: str = "",
        include_traceback: bool = True
    ) -> None:
        """
        Логирует ошибку с детальной информацией

        Args:
            error: Исключение для логирования
            context: Дополнительный контекст ошибки (account_id, message_id, etc.)
            message: Дополнительное сообщение об ошибке
            include_traceback: Включать ли traceback в лог
        """
        error_info = {
            "error_type": type(error).__name__,
            "error_message": str(error),
            "timestamp": datetime.now().isoformat(),
            "context": context or {},
            "custom_message": message
        }

        if include_traceback:
            error_info["traceback"] = traceback.format_exc()

        # Формируем сообщение для логирования
        log_message = f"Error: {error_info['error_type']} - {error_info['error_message']}"
        if message:
            log_message = f"{message} | {log_message}"
        if context:
            log_message += f" | Context: {json.dumps(context, ensure_ascii=False, default=str)}"

        # Логируем с полной информацией
        self.logger.error(log_message, exc_info=include_traceback, extra={
            "error_info": error_info
        })

    def log_api_error(
        self,
        error: Exception,
        service_name: str,
        endpoint: str,
        request_data: Optional[Dict[str, Any]] = None,
        response_data: Optional[Dict[str, Any]] = None,
        status_code: Optional[int] = None
    ) -> None:
        """Логирует ошибки API запросов"""
        context = {
            "service": service_name,
            "endpoint": endpoint,
            "status_code": status_code,
            "request": request_data,
            "response": response_data
        }

        message = f"API Error in {service_name}"
        self.log_error(error, context, message)

    def log_message_processing_error(
        self,
        error: Exception,
        source_provider: str,
        target_provider: str,
        message_id: str,
        conversation_id: str,
        account_id: Optional[str] = None
    ) -> None:
        """Логирует ошибки обработки сообщений"""
        context = {
            "source_provider": source_provider,
            "target_provider": target_provider,
            "message_id": message_id,
            "conversation_id": conversation_id,
            "account_id": account_id
        }

        message = f"Message processing error: {source_provider} -> {target_provider}"
        self.log_error(error, context, message)

    def log_delivery_status_error(
        self,
        error: Exception,
        provider: str,
        message_id: str,
        status_code: Optional[int] = None,
        error_details: Optional[str] = None
    ) -> None:
        """Логирует ошибки отправки статуса доставки"""
        context = {
            "provider": provider,
            "message_id": message_id,
            "status_code": status_code,
            "error_details": error_details
        }

        message = f"Delivery status error in {provider}"
        self.log_error(error, context, message)


# Глобальный экземпляр ErrorReporter (будет инициализирован в main.py)
error_reporter: Optional[ErrorReporter] = None


def get_error_reporter() -> ErrorReporter:
    """Получить глобальный экземпляр ErrorReporter"""
    if error_reporter is None:
        raise RuntimeError("Error reporter not initialized. Call setup_error_reporting() first.")
    return error_reporter


def setup_error_reporting(error_logger: logging.Logger) -> None:
    """Инициализировать глобальный ErrorReporter"""
    global error_reporter
    error_reporter = ErrorReporter(error_logger)
