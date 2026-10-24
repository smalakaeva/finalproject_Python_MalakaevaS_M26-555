"""Клиенты внешних API. У всех один интерфейс: fetch_rates() -> dict."""

import time
from abc import ABC, abstractmethod

import requests

from valutatrade_hub.core.exceptions import ApiRequestError
from valutatrade_hub.parser_service.config import ParserConfig

HTTP_OK = 200
HTTP_UNAUTHORIZED = 401
HTTP_FORBIDDEN = 403
HTTP_TOO_MANY_REQUESTS = 429


class BaseApiClient(ABC):
    """Базовый клиент внешнего API.

    Наследники должны вернуть курсы в едином формате:
    {"BTC_USD": 59337.21, "EUR_USD": 1.0786}
    """

    source_name = "BaseApi"

    def __init__(self, config: ParserConfig | None = None):
        self.config = config or ParserConfig()
        self.last_meta: dict = {}

    @abstractmethod
    def fetch_rates(self) -> dict:
        """Получает курсы и приводит их к стандартному формату."""

    def _get(self, url: str, params: dict | None = None) -> dict:
        """Общий GET-запрос с обработкой ошибок сети и кодов ответа."""
        started = time.time()
        try:
            response = requests.get(url, params=params, timeout=self.config.REQUEST_TIMEOUT)
        except requests.exceptions.Timeout as error:
            raise ApiRequestError(
                f"{self.source_name}: превышен таймаут {self.config.REQUEST_TIMEOUT} c"
            ) from error
        except requests.exceptions.RequestException as error:
            raise ApiRequestError(f"{self.source_name}: сеть недоступна ({error})") from error

        self.last_meta = {
            "status_code": response.status_code,
            "request_ms": int((time.time() - started) * 1000),
        }

        if response.status_code == HTTP_TOO_MANY_REQUESTS:
            raise ApiRequestError(f"{self.source_name}: превышен лимит запросов (429)")
        if response.status_code in (HTTP_UNAUTHORIZED, HTTP_FORBIDDEN):
            raise ApiRequestError(f"{self.source_name}: неверный API-ключ ({response.status_code})")
        if response.status_code != HTTP_OK:
            raise ApiRequestError(f"{self.source_name}: код ответа {response.status_code}")

        try:
            return response.json()
        except ValueError as error:
            raise ApiRequestError(f"{self.source_name}: ответ не является JSON") from error


class CoinGeckoClient(BaseApiClient):
    """Курсы криптовалют с CoinGecko (ключ не нужен)."""

    source_name = "CoinGecko"

    def fetch_rates(self) -> dict:
        """Запрашивает цены криптовалют в долларах."""
        ids = [
            self.config.CRYPTO_ID_MAP[code]
            for code in self.config.CRYPTO_CURRENCIES
            if code in self.config.CRYPTO_ID_MAP
        ]
        if not ids:
            raise ApiRequestError(f"{self.source_name}: не задан список криптовалют")

        base = self.config.BASE_CURRENCY.lower()
        data = self._get(
            self.config.COINGECKO_URL,
            params={"ids": ",".join(ids), "vs_currencies": base},
        )

        rates = {}
        for code in self.config.CRYPTO_CURRENCIES:
            coin_id = self.config.CRYPTO_ID_MAP.get(code)
            price = data.get(coin_id, {}).get(base)
            if isinstance(price, (int, float)) and price > 0:
                rates[f"{code}_{self.config.BASE_CURRENCY}"] = float(price)
        if not rates:
            raise ApiRequestError(f"{self.source_name}: в ответе нет ни одного курса")
        return rates


class ExchangeRateApiClient(BaseApiClient):
    """Курсы фиатных валют с ExchangeRate-API (нужен ключ)."""

    source_name = "ExchangeRate-API"

    def fetch_rates(self) -> dict:
        """Запрашивает курсы фиата относительно базовой валюты."""
        if not self.config.EXCHANGERATE_API_KEY:
            raise ApiRequestError(
                f"{self.source_name}: не задан ключ, добавьте EXCHANGERATE_API_KEY в .env"
            )

        url = (
            f"{self.config.EXCHANGERATE_API_URL}/{self.config.EXCHANGERATE_API_KEY}"
            f"/latest/{self.config.BASE_CURRENCY}"
        )
        data = self._get(url)
        if data.get("result") != "success":
            raise ApiRequestError(
                f"{self.source_name}: {data.get('error-type', 'неизвестная ошибка')}"
            )

        api_rates = data.get("conversion_rates") or data.get("rates") or {}
        rates = {}
        for code in self.config.FIAT_CURRENCIES:
            value = api_rates.get(code)
            # API отдаёт "сколько единиц валюты в одном долларе",
            # а нам нужен обратный курс - сколько долларов стоит валюта
            if isinstance(value, (int, float)) and value > 0:
                rates[f"{code}_{self.config.BASE_CURRENCY}"] = round(1 / float(value), 8)
        if not rates:
            raise ApiRequestError(f"{self.source_name}: в ответе нет нужных валют")
        return rates


def build_clients(source: str | None = None, config: ParserConfig | None = None) -> list:
    """Возвращает список клиентов: все или только один указанный источник."""
    config = config or ParserConfig()
    all_clients = {
        "coingecko": CoinGeckoClient(config),
        "exchangerate": ExchangeRateApiClient(config),
    }
    if source is None:
        return list(all_clients.values())
    source = source.strip().lower()
    if source not in all_clients:
        raise ApiRequestError(
            f"неизвестный источник '{source}', доступны: {', '.join(all_clients)}"
        )
    return [all_clients[source]]
