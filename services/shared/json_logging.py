# json_logging.py
import logging
import sys
import time
import uuid
from typing import Optional

import structlog
from fastapi import FastAPI, Request, Response
from structlog.types import EventDict
from uvicorn.protocols.utils import get_path_with_query_string


def drop_color_message_key(_, __, event_dict: EventDict) -> EventDict:
    """Uvicorn логирует message дважды в color_message, убираем дубликат"""
    event_dict.pop("color_message", None)
    return event_dict


def setup_logging(json_logs: bool = True, log_level: str = "INFO"):
    """Настройка JSON логирования для FastAPI + Uvicorn"""

    timestamper = structlog.processors.TimeStamper(fmt="iso")

    shared_processors = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        drop_color_message_key,
        timestamper,
        structlog.processors.StackInfoRenderer(),
    ]

    if json_logs:
        # Для JSON переименовываем event -> message
        shared_processors.append(
            structlog.processors.EventRenamer("message")
        )
        shared_processors.append(structlog.processors.format_exc_info)

    structlog.configure(
        processors=shared_processors + [
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )

    log_renderer = (
        structlog.processors.JSONRenderer()
        if json_logs
        else structlog.dev.ConsoleRenderer()
    )

    formatter = structlog.stdlib.ProcessorFormatter(
        foreign_pre_chain=shared_processors,
        processors=[
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            log_renderer,
        ],
    )

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)

    root_logger = logging.getLogger()
    root_logger.handlers.clear()  # Фикс двойных логов в dev режиме
    root_logger.addHandler(handler)
    root_logger.setLevel(log_level.upper())

    # Перехватываем uvicorn логгеры
    for logger_name in ["uvicorn", "uvicorn.error"]:
        logging.getLogger(logger_name).handlers.clear()
        logging.getLogger(logger_name).propagate = True

    # uvicorn.access отключаем, будем логировать сами
    logging.getLogger("uvicorn.access").handlers.clear()
    logging.getLogger("uvicorn.access").propagate = False


def setup_middleware(app: FastAPI):
    """Middleware для добавления request_id и idempotency_key в контекст"""

    access_logger = structlog.stdlib.get_logger("api.access")

    @app.middleware("http")
    async def logging_middleware(request: Request, call_next) -> Response:
        structlog.contextvars.clear_contextvars()

        # Получаем или генерируем request_id
        request_id: str = request.headers.get("x-request-id") or str(uuid.uuid4())

        # Получаем idempotency_key если есть
        idempotency_key: Optional[str] = request.headers.get("idempotency-key")

        # Биндим в контекст для всех логов
        bind_dict = {"request_id": request_id}
        if idempotency_key:
            bind_dict["idempotency_key"] = idempotency_key

        structlog.contextvars.bind_contextvars(**bind_dict)

        start_time = time.perf_counter_ns()
        response = Response(status_code=500)

        try:
            response = await call_next(request)
        except Exception:
            structlog.stdlib.get_logger("api.error").exception("Uncaught exception")
            raise
        finally:
            process_time = time.perf_counter_ns() - start_time
            status_code = response.status_code
            url = get_path_with_query_string(request.scope)
            client_host = request.client.host if request.client else "unknown"
            client_port = request.client.port if request.client else 0
            http_method = request.method
            http_version = request.scope.get("http_version", "1.1")

            # Access log в формате uvicorn, но с JSON структурой
            access_logger.info(
                f'{client_host}:{client_port} - "{http_method} {url} HTTP/{http_version}" {status_code}',
                http={
                    "url": str(request.url),
                    "status_code": status_code,
                    "method": http_method,
                    "version": http_version,
                },
                network={"client": {"ip": client_host, "port": client_port}},
                duration_ns=process_time,
                duration_ms=round(process_time / 1_000_000, 2),
            )

            # Опционально: добавляем request_id в response headers
            response.headers["X-Request-ID"] = request_id

        return response
