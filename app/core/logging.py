"""Loguru-based structured logging, wired to intercept stdlib logging (uvicorn, sqlalchemy)."""

import logging
import sys
from types import FrameType

from loguru import logger

from app.core.config import settings


class InterceptHandler(logging.Handler):
    """Redirects stdlib `logging` records (uvicorn, gunicorn, sqlalchemy) into loguru."""

    def emit(self, record: logging.LogRecord) -> None:
        try:
            level = logger.level(record.levelname).name
        except ValueError:
            level = record.levelno

        frame: FrameType | None = logging.currentframe()
        depth = 2
        while frame and frame.f_code.co_filename == logging.__file__:
            frame = frame.f_back
            depth += 1

        logger.opt(depth=depth, exception=record.exc_info).log(level, record.getMessage())


def configure_logging() -> None:
    logger.remove()

    log_format = (
        "{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | "
        "{extra[request_id]} | {name}:{function}:{line} - {message}"
    )
    logger.configure(extra={"request_id": "-"})

    logger.add(
        sys.stdout,
        level=settings.LOG_LEVEL,
        serialize=settings.LOG_JSON,
        format=log_format if not settings.LOG_JSON else "{message}",
        backtrace=not settings.is_production,
        diagnose=not settings.is_production,
        enqueue=True,
    )

    logging.basicConfig(handlers=[InterceptHandler()], level=0, force=True)
    for name in ("uvicorn", "uvicorn.access", "uvicorn.error", "gunicorn.error", "sqlalchemy.engine", "celery"):
        logging.getLogger(name).handlers = [InterceptHandler()]
        logging.getLogger(name).propagate = False


__all__ = ["configure_logging", "logger"]
