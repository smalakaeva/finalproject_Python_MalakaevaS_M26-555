"""Настройка логирования: формат, уровень и ротация файлов.

Логов два:
  * valutatrade.actions -> logs/actions.log  (операции пользователя: BUY/SELL/...)
  * valutatrade.parser  -> logs/parser.log   (работа Parser Service)
Формат выбран строковый (а не JSON), потому что логи читает человек.
"""

import logging
from logging.handlers import RotatingFileHandler

from valutatrade_hub.infra.settings import SettingsLoader

ACTIONS_LOGGER = "valutatrade.actions"
PARSER_LOGGER = "valutatrade.parser"

LOG_FORMAT = "%(levelname)s %(asctime)s %(message)s"
DATE_FORMAT = "%Y-%m-%dT%H:%M:%S"

_is_configured = False


def _build_logger(name: str, file_path, level: str, max_bytes: int, backup_count: int) -> None:
    """Создаёт логгер с ротацией файла."""
    logger = logging.getLogger(name)
    logger.setLevel(level)
    logger.propagate = False
    if logger.handlers:
        return
    handler = RotatingFileHandler(
        file_path,
        maxBytes=max_bytes,
        backupCount=backup_count,
        encoding="utf-8",
    )
    handler.setFormatter(logging.Formatter(LOG_FORMAT, datefmt=DATE_FORMAT))
    logger.addHandler(handler)


def setup_logging() -> None:
    """Настраивает логгеры приложения. Повторный вызов ничего не делает."""
    global _is_configured
    if _is_configured:
        return

    settings = SettingsLoader()
    settings.path("log_dir").mkdir(parents=True, exist_ok=True)
    level = str(settings.get("log_level", "INFO")).upper()
    max_bytes = int(settings.get("log_max_bytes", 1048576))
    backup_count = int(settings.get("log_backup_count", 3))

    _build_logger(ACTIONS_LOGGER, settings.path("actions_log"), level, max_bytes, backup_count)
    _build_logger(PARSER_LOGGER, settings.path("parser_log"), level, max_bytes, backup_count)
    _is_configured = True


def get_logger(name: str = ACTIONS_LOGGER) -> logging.Logger:
    """Возвращает настроенный логгер по имени."""
    setup_logging()
    return logging.getLogger(name)
