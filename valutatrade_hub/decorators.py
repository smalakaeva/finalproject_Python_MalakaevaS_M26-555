"""Декораторы приложения: логирование операций и подтверждение действий."""

import functools
import sys
import time

from valutatrade_hub.infra.settings import SettingsLoader
from valutatrade_hub.logging_config import ACTIONS_LOGGER, get_logger

YES_ANSWERS = ("y", "yes", "д", "да")


def _describe_arguments(kwargs: dict) -> str:
    """Собирает часть строки лога из аргументов функции.

    Декорируемые функции вызываются с именованными аргументами
    (user=..., currency_code=..., amount=...), поэтому достаточно
    посмотреть в kwargs.
    """
    parts = []
    user = kwargs.get("user")
    username = getattr(user, "username", None) or kwargs.get("username")
    if username:
        parts.append(f"user='{username}'")
    if kwargs.get("currency_code"):
        parts.append(f"currency='{kwargs['currency_code']}'")
    if kwargs.get("amount") is not None:
        try:
            parts.append(f"amount={float(kwargs['amount']):.4f}")
        except (TypeError, ValueError):
            parts.append(f"amount={kwargs['amount']}")
    return " ".join(parts)


def _describe_result(result, verbose: bool) -> str:
    """Добавляет в лог курс, базовую валюту и (при verbose) состояние кошелька."""
    if not isinstance(result, dict):
        return ""
    parts = []
    if result.get("rate") is not None:
        parts.append(f"rate={result['rate']:.2f}")
    if result.get("base"):
        parts.append(f"base='{result['base']}'")
    if verbose and result.get("balance_before") is not None:
        parts.append(f"was={result['balance_before']:.4f}")
        parts.append(f"now={result['balance_after']:.4f}")
    return " ".join(parts)


def log_action(action: str, verbose: bool = False):
    """Логирует доменную операцию (BUY, SELL, REGISTER, LOGIN).

    В лог уровня INFO попадают: действие, пользователь, валюта, сумма,
    курс, базовая валюта и результат (OK/ERROR). Исключения декоратор не
    глотает - он пишет их в лог и пробрасывает дальше.
    """

    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            logger = get_logger(ACTIONS_LOGGER)
            arguments = _describe_arguments(kwargs)
            started = time.time()
            try:
                result = func(*args, **kwargs)
            except Exception as error:
                logger.error(
                    "%s result=ERROR error_type=%s error_message='%s'",
                    " ".join(part for part in (action, arguments) if part),
                    type(error).__name__,
                    error,
                )
                raise
            elapsed_ms = int((time.time() - started) * 1000)
            details = _describe_result(result, verbose)
            logger.info(
                "%s result=OK elapsed_ms=%s",
                " ".join(part for part in (action, arguments, details) if part),
                elapsed_ms,
            )
            return result

        return wrapper

    return decorator


def confirm_action(question: str):
    """Спрашивает у пользователя подтверждение перед выполнением функции.

    Подтверждение отключается настройкой confirm_trades в config.json,
    а также автоматически, если ввод идёт не с терминала (например,
    команды подаются из файла при записи демо).
    """

    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            settings = SettingsLoader()
            if not settings.get("confirm_trades", True) or not sys.stdin.isatty():
                return func(*args, **kwargs)
            answer = input(f"{question} [y/n]: ").strip().lower()
            if answer not in YES_ANSWERS:
                print("Операция отменена")
                return None
            return func(*args, **kwargs)

        return wrapper

    return decorator
