"""Вспомогательные функции: валидация, хеширование, конвертация и форматирование."""

import hashlib
import secrets
import time
from datetime import UTC, datetime

from valutatrade_hub.core.currencies import CryptoCurrency, get_currency
from valutatrade_hub.core.exceptions import (
    CurrencyNotFoundError,
    RateUnavailableError,
    ValidationError,
)

MIN_PASSWORD_LENGTH = 4
SALT_LENGTH = 8
CRYPTO_DIGITS = 4
FIAT_DIGITS = 2
BASE_CODE = "USD"


# --- пароли -----------------------------------------------------------------


def generate_salt() -> str:
    """Генерирует случайную соль для пароля."""
    return secrets.token_hex(SALT_LENGTH)


def hash_password(password: str, salt: str) -> str:
    """Считает односторонний псевдо-хеш пароля: sha256(password + salt)."""
    return hashlib.sha256((password + salt).encode("utf-8")).hexdigest()


def validate_username(username: str) -> str:
    """Проверяет, что имя пользователя не пустое."""
    if not isinstance(username, str) or not username.strip():
        raise ValidationError("Имя пользователя не может быть пустым")
    return username.strip()


def validate_password(password: str) -> str:
    """Проверяет минимальную длину пароля."""
    if not isinstance(password, str) or len(password) < MIN_PASSWORD_LENGTH:
        raise ValidationError(f"Пароль должен быть не короче {MIN_PASSWORD_LENGTH} символов")
    return password


# --- валюты и суммы ---------------------------------------------------------


def normalize_currency_code(code: str) -> str:
    """Приводит код валюты к верхнему регистру и проверяет, что он не пустой."""
    if not isinstance(code, str) or not code.strip():
        raise ValidationError("Код валюты не может быть пустым")
    return code.strip().upper()


def validate_amount(amount) -> float:
    """Проверяет, что сумма - положительное число, и возвращает её как float."""
    try:
        amount = float(amount)
    except (TypeError, ValueError) as error:
        raise ValidationError("'amount' должен быть положительным числом") from error
    if amount <= 0:
        raise ValidationError("'amount' должен быть положительным числом")
    return amount


def get_usd_price(code: str, pairs: dict) -> float | None:
    """Сколько стоит одна единица валюты в долларах (или None, если курса нет)."""
    code = normalize_currency_code(code)
    if code == BASE_CODE:
        return 1.0
    direct = pairs.get(f"{code}_{BASE_CODE}")
    if direct:
        return float(direct)
    reverse = pairs.get(f"{BASE_CODE}_{code}")
    if reverse:
        return 1 / float(reverse)
    return None


def convert_amount(amount: float, from_code: str, to_code: str, pairs: dict) -> float:
    """Переводит сумму из одной валюты в другую через курс к доллару."""
    from_price = get_usd_price(from_code, pairs)
    to_price = get_usd_price(to_code, pairs)
    if from_price is None or to_price is None:
        raise RateUnavailableError(from_code, to_code)
    return amount * from_price / to_price


# --- форматирование ---------------------------------------------------------


def format_money(value: float) -> str:
    """Формат суммы в базовой валюте: 3,329.00."""
    return f"{value:,.2f}"


def format_amount(code: str, value: float) -> str:
    """Формат баланса: у крипты 4 знака после запятой, у фиата - 2."""
    try:
        currency = get_currency(code)
    except CurrencyNotFoundError:
        return f"{value:.2f}"
    digits = CRYPTO_DIGITS if isinstance(currency, CryptoCurrency) else FIAT_DIGITS
    return f"{value:.{digits}f}"


def format_rate(value: float) -> str:
    """Формат курса: большие числа с разделителями, мелкие - с 8 знаками."""
    if value >= 1000:
        return f"{value:,.2f}"
    if value >= 1:
        return f"{value:.4f}"
    return f"{value:.8f}"


# --- время ------------------------------------------------------------------


def now_iso() -> str:
    """Текущее время UTC в формате ISO, например 2025-10-10T12:00:00Z."""
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def parse_iso(value: str) -> datetime | None:
    """Разбирает ISO-строку в datetime (или None, если строка битая)."""
    if not value:
        return None
    try:
        moment = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=UTC)
    return moment


def seconds_since(value: str) -> float | None:
    """Сколько секунд прошло с момента, записанного в ISO-строке."""
    moment = parse_iso(value)
    if moment is None:
        return None
    return (datetime.now(UTC) - moment).total_seconds()


def pretty_time(value: str) -> str:
    """Переводит ISO-строку в читаемый вид 2025-10-09 00:03:22."""
    moment = parse_iso(value)
    if moment is None:
        return "неизвестно"
    return moment.strftime("%Y-%m-%d %H:%M:%S")


# --- кеширование на замыкании ----------------------------------------------


def cache_with_ttl(ttl_seconds: float):
    """Декоратор-замыкание: кеширует результат функции на ttl_seconds секунд.

    Словарь cache живёт в замыкании, поэтому для каждой обёрнутой функции
    он свой. У обёртки есть метод clear() - он нужен, когда данные на диске
    поменялись (например, после update-rates).
    """

    def decorator(func):
        cache = {}

        def wrapper(*args):
            key = args
            now = time.monotonic()
            if key in cache:
                value, saved_at = cache[key]
                if now - saved_at < ttl_seconds:
                    return value
            value = func(*args)
            cache[key] = (value, now)
            return value

        wrapper.clear = cache.clear
        wrapper.__name__ = func.__name__
        wrapper.__doc__ = func.__doc__
        return wrapper

    return decorator
