"""Иерархия валют: абстрактный класс Currency и наследники Fiat/Crypto."""

from abc import ABC, abstractmethod

from valutatrade_hub.core.exceptions import CurrencyNotFoundError, ValidationError

MIN_CODE_LENGTH = 2
MAX_CODE_LENGTH = 5


class Currency(ABC):
    """Абстрактная валюта.

    Хранит код (тикер) и человекочитаемое имя. Наследники обязаны
    реализовать get_display_info().
    """

    def __init__(self, code: str, name: str):
        self.code = self._validate_code(code)
        self.name = self._validate_name(name)

    @staticmethod
    def _validate_code(code: str) -> str:
        """Проверяет код валюты: верхний регистр, 2-5 символов, без пробелов."""
        if not isinstance(code, str):
            raise ValidationError("Код валюты должен быть строкой")
        code = code.strip().upper()
        if not code.isalnum():
            raise ValidationError("Код валюты не должен содержать пробелов и знаков")
        if not MIN_CODE_LENGTH <= len(code) <= MAX_CODE_LENGTH:
            raise ValidationError(
                f"Код валюты должен быть длиной {MIN_CODE_LENGTH}-{MAX_CODE_LENGTH} символов"
            )
        return code

    @staticmethod
    def _validate_name(name: str) -> str:
        """Проверяет, что имя валюты не пустое."""
        if not isinstance(name, str) or not name.strip():
            raise ValidationError("Имя валюты не может быть пустым")
        return name.strip()

    @abstractmethod
    def get_display_info(self) -> str:
        """Возвращает строку для вывода в CLI и логи."""

    def __str__(self) -> str:
        return self.get_display_info()


class FiatCurrency(Currency):
    """Фиатная валюта (доллар, евро, рубль и т.д.)."""

    def __init__(self, code: str, name: str, issuing_country: str):
        super().__init__(code, name)
        self.issuing_country = issuing_country

    def get_display_info(self) -> str:
        """Например: [FIAT] USD — US Dollar (Issuing: United States)."""
        return f"[FIAT] {self.code} — {self.name} (Issuing: {self.issuing_country})"


class CryptoCurrency(Currency):
    """Криптовалюта (биткоин, эфир и т.д.)."""

    def __init__(self, code: str, name: str, algorithm: str, market_cap: float):
        super().__init__(code, name)
        self.algorithm = algorithm
        self.market_cap = float(market_cap)

    def get_display_info(self) -> str:
        """Например: [CRYPTO] BTC — Bitcoin (Algo: SHA-256, MCAP: 1.12e12)."""
        # формат 1.12e+12 приводим к короткому виду 1.12e12
        market_cap = f"{self.market_cap:.2e}".replace("e+", "e")
        return f"[CRYPTO] {self.code} — {self.name} (Algo: {self.algorithm}, MCAP: {market_cap})"


# Реестр поддерживаемых валют: код -> объект валюты
CURRENCY_REGISTRY: dict[str, Currency] = {
    "USD": FiatCurrency("USD", "US Dollar", "United States"),
    "EUR": FiatCurrency("EUR", "Euro", "Eurozone"),
    "GBP": FiatCurrency("GBP", "Pound Sterling", "United Kingdom"),
    "RUB": FiatCurrency("RUB", "Russian Ruble", "Russia"),
    "BTC": CryptoCurrency("BTC", "Bitcoin", "SHA-256", 1.12e12),
    "ETH": CryptoCurrency("ETH", "Ethereum", "Ethash", 4.40e11),
    "SOL": CryptoCurrency("SOL", "Solana", "Proof-of-History", 7.00e10),
}


def get_currency(code: str) -> Currency:
    """Фабричный метод: возвращает валюту по коду.

    Если код неизвестен, выбрасывает CurrencyNotFoundError.
    """
    if not isinstance(code, str) or not code.strip():
        raise CurrencyNotFoundError(str(code))
    normalized = code.strip().upper()
    if normalized not in CURRENCY_REGISTRY:
        raise CurrencyNotFoundError(normalized)
    return CURRENCY_REGISTRY[normalized]


def is_crypto(code: str) -> bool:
    """Проверяет, является ли валюта криптовалютой."""
    return isinstance(get_currency(code), CryptoCurrency)


def supported_codes() -> list[str]:
    """Список всех поддерживаемых кодов валют."""
    return sorted(CURRENCY_REGISTRY)
