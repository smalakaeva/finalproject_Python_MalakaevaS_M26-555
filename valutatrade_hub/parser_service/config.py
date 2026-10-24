"""Конфигурация Parser Service: эндпоинты, списки валют, таймауты, ключи."""

import os
from dataclasses import dataclass, field

from valutatrade_hub.infra.settings import SettingsLoader

ENV_FILE_NAME = ".env"
API_KEY_ENV_NAME = "EXCHANGERATE_API_KEY"


def read_api_key() -> str:
    """Берёт ключ ExchangeRate-API из переменной окружения или из файла .env.

    Ключ намеренно не хранится в коде: файл .env добавлен в .gitignore.
    """
    key = os.getenv(API_KEY_ENV_NAME, "")
    if key:
        return key.strip()

    env_path = SettingsLoader().project_root / ENV_FILE_NAME
    if not env_path.exists():
        return ""
    try:
        with open(env_path, encoding="utf-8") as env_file:
            for line in env_file:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                name, value = line.split("=", 1)
                if name.strip() == API_KEY_ENV_NAME:
                    return value.strip().strip("'\"")
    except OSError:
        return ""
    return ""


@dataclass
class ParserConfig:
    """Все настройки парсера в одном месте."""

    # ключ подставляется в URL запроса к ExchangeRate-API
    EXCHANGERATE_API_KEY: str = field(default_factory=read_api_key)

    # эндпоинты внешних сервисов
    COINGECKO_URL: str = "https://api.coingecko.com/api/v3/simple/price"
    EXCHANGERATE_API_URL: str = "https://v6.exchangerate-api.com/v6"

    # какие валюты отслеживаем
    BASE_CURRENCY: str = "USD"
    FIAT_CURRENCIES: tuple = ("EUR", "GBP", "RUB")
    CRYPTO_CURRENCIES: tuple = ("BTC", "ETH", "SOL")
    CRYPTO_ID_MAP: dict = field(
        default_factory=lambda: {
            "BTC": "bitcoin",
            "ETH": "ethereum",
            "SOL": "solana",
        }
    )

    # пути к файлам берём из общих настроек проекта
    RATES_FILE_PATH: str = field(default_factory=lambda: str(SettingsLoader().path("rates_file")))
    HISTORY_FILE_PATH: str = field(
        default_factory=lambda: str(SettingsLoader().path("history_file"))
    )

    # сетевые параметры
    REQUEST_TIMEOUT: int = 10
