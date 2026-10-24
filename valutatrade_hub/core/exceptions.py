"""Пользовательские исключения приложения.

Все исключения наследуются от ValutaTradeError, поэтому в CLI можно
перехватить одну базовую ошибку и показать пользователю её текст.
"""


class ValutaTradeError(Exception):
    """Базовое исключение приложения."""


class ValidationError(ValutaTradeError):
    """Некорректные данные, пришедшие от пользователя."""


class InsufficientFundsError(ValutaTradeError):
    """Недостаточно средств на кошельке."""

    def __init__(self, code: str, available: float, required: float):
        self.code = code
        self.available = available
        self.required = required
        super().__init__(
            f"Недостаточно средств: доступно {available:.4f} {code}, "
            f"требуется {required:.4f} {code}"
        )


class CurrencyNotFoundError(ValutaTradeError):
    """Запрошена валюта, которой нет в реестре."""

    def __init__(self, code: str):
        self.code = code
        super().__init__(f"Неизвестная валюта '{code}'")


class ApiRequestError(ValutaTradeError):
    """Сбой при обращении к внешнему API."""

    def __init__(self, reason: str):
        self.reason = reason
        super().__init__(f"Ошибка при обращении к внешнему API: {reason}")


class RateUnavailableError(ValutaTradeError):
    """Курс не найден ни в кеше, ни у Parser Service."""

    def __init__(self, from_code: str, to_code: str):
        self.from_code = from_code
        self.to_code = to_code
        super().__init__(f"Курс {from_code}→{to_code} недоступен. Повторите попытку позже.")


class WalletNotFoundError(ValutaTradeError):
    """В портфеле нет кошелька для указанной валюты."""

    def __init__(self, code: str):
        self.code = code
        super().__init__(
            f"У вас нет кошелька '{code}'. Добавьте валюту: она создаётся автоматически "
            "при первой покупке."
        )


class UserAlreadyExistsError(ValutaTradeError):
    """Имя пользователя уже занято."""

    def __init__(self, username: str):
        super().__init__(f"Имя пользователя '{username}' уже занято")


class UserNotFoundError(ValutaTradeError):
    """Пользователь не найден в users.json."""

    def __init__(self, username: str):
        super().__init__(f"Пользователь '{username}' не найден")


class InvalidPasswordError(ValutaTradeError):
    """Пароль не совпал с сохранённым хешем."""

    def __init__(self):
        super().__init__("Неверный пароль")


class AuthRequiredError(ValutaTradeError):
    """Команда доступна только залогиненному пользователю."""

    def __init__(self):
        super().__init__("Сначала выполните login")
