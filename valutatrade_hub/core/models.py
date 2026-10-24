"""Основные модели приложения: User, Wallet и Portfolio."""

from datetime import UTC, datetime

from valutatrade_hub.core.exceptions import (
    InsufficientFundsError,
    ValidationError,
)
from valutatrade_hub.core.utils import (
    convert_amount,
    format_amount,
    generate_salt,
    hash_password,
    normalize_currency_code,
    validate_amount,
    validate_password,
    validate_username,
)


class User:
    """Пользователь системы.

    Пароль никогда не хранится в открытом виде: в объекте лежат только
    хеш sha256(password + salt) и сама соль.
    """

    def __init__(
        self,
        user_id: int,
        username: str,
        hashed_password: str,
        salt: str,
        registration_date: datetime,
    ):
        self._user_id = int(user_id)
        self._username = validate_username(username)
        self._hashed_password = hashed_password
        self._salt = salt
        self._registration_date = registration_date

    @classmethod
    def create(cls, user_id: int, username: str, password: str) -> "User":
        """Создаёт нового пользователя, сразу хешируя пароль."""
        validate_username(username)
        validate_password(password)
        salt = generate_salt()
        return cls(
            user_id=user_id,
            username=username,
            hashed_password=hash_password(password, salt),
            salt=salt,
            registration_date=datetime.now(UTC),
        )

    # --- свойства ---------------------------------------------------------

    @property
    def user_id(self) -> int:
        """Уникальный идентификатор пользователя (только чтение)."""
        return self._user_id

    @property
    def username(self) -> str:
        """Имя пользователя."""
        return self._username

    @username.setter
    def username(self, value: str) -> None:
        self._username = validate_username(value)

    @property
    def salt(self) -> str:
        """Соль пользователя (нужна при проверке пароля)."""
        return self._salt

    @property
    def hashed_password(self) -> str:
        """Хеш пароля (только чтение)."""
        return self._hashed_password

    @property
    def registration_date(self) -> datetime:
        """Дата регистрации (только чтение)."""
        return self._registration_date

    # --- методы -----------------------------------------------------------

    def get_user_info(self) -> str:
        """Возвращает информацию о пользователе без пароля."""
        return (
            f"Пользователь #{self._user_id}: {self._username} "
            f"(регистрация: {self._registration_date.strftime('%Y-%m-%d %H:%M:%S')})"
        )

    def change_password(self, new_password: str) -> None:
        """Меняет пароль пользователя, пересчитывая хеш с новой солью."""
        validate_password(new_password)
        self._salt = generate_salt()
        self._hashed_password = hash_password(new_password, self._salt)

    def verify_password(self, password: str) -> bool:
        """Проверяет, совпадает ли введённый пароль с сохранённым хешем."""
        if not isinstance(password, str):
            return False
        return hash_password(password, self._salt) == self._hashed_password

    # --- сериализация -----------------------------------------------------

    def to_dict(self) -> dict:
        """Готовит пользователя к записи в users.json."""
        return {
            "user_id": self._user_id,
            "username": self._username,
            "hashed_password": self._hashed_password,
            "salt": self._salt,
            "registration_date": self._registration_date.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: dict) -> "User":
        """Создаёт пользователя из словаря, прочитанного из users.json."""
        registration_date = datetime.fromisoformat(data["registration_date"])
        return cls(
            user_id=data["user_id"],
            username=data["username"],
            hashed_password=data["hashed_password"],
            salt=data.get("salt", ""),
            registration_date=registration_date,
        )

    def __repr__(self) -> str:
        return f"User(user_id={self._user_id}, username='{self._username}')"


class Wallet:
    """Кошелёк пользователя для одной конкретной валюты."""

    def __init__(self, currency_code: str, balance: float = 0.0):
        self.currency_code = normalize_currency_code(currency_code)
        self._balance = 0.0
        self.balance = balance

    @property
    def balance(self) -> float:
        """Текущий баланс кошелька."""
        return self._balance

    @balance.setter
    def balance(self, value) -> None:
        """Запрещает отрицательные значения и нечисловые типы."""
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValidationError(f"Баланс кошелька '{self.currency_code}' должен быть числом")
        if value < 0:
            raise ValidationError(
                f"Баланс кошелька '{self.currency_code}' не может быть отрицательным"
            )
        self._balance = float(value)

    def deposit(self, amount: float) -> float:
        """Пополняет баланс на amount и возвращает новый баланс."""
        amount = validate_amount(amount)
        self.balance = self._balance + amount
        return self._balance

    def withdraw(self, amount: float) -> float:
        """Снимает amount с баланса, если средств достаточно."""
        amount = validate_amount(amount)
        if amount > self._balance:
            raise InsufficientFundsError(self.currency_code, self._balance, amount)
        self.balance = self._balance - amount
        return self._balance

    def get_balance_info(self) -> str:
        """Строка с текущим балансом, например 'BTC: 0.0500'."""
        return f"{self.currency_code}: {format_amount(self.currency_code, self._balance)}"

    def to_dict(self) -> dict:
        """Готовит кошелёк к записи в portfolios.json."""
        return {"currency_code": self.currency_code, "balance": self._balance}

    @classmethod
    def from_dict(cls, currency_code: str, data: dict) -> "Wallet":
        """Создаёт кошелёк из словаря портфеля."""
        return cls(data.get("currency_code", currency_code), data.get("balance", 0.0))

    def __repr__(self) -> str:
        return f"Wallet(currency_code='{self.currency_code}', balance={self._balance})"


class Portfolio:
    """Портфель пользователя - все его кошельки."""

    def __init__(self, user_id: int, wallets: dict | None = None, user: User | None = None):
        self._user_id = int(user_id)
        self._wallets = dict(wallets) if wallets else {}
        # объект пользователя не обязателен: портфель можно загрузить
        # только по user_id, а пользователя подставить позже
        self._user = user

    # --- свойства ---------------------------------------------------------

    @property
    def user_id(self) -> int:
        """Идентификатор владельца портфеля."""
        return self._user_id

    @property
    def user(self) -> User | None:
        """Владелец портфеля (только чтение)."""
        return self._user

    @property
    def wallets(self) -> dict:
        """Копия словаря кошельков, чтобы снаружи его не меняли напрямую."""
        return dict(self._wallets)

    # --- методы -----------------------------------------------------------

    def add_currency(self, currency_code: str) -> Wallet:
        """Добавляет новый кошелёк, если такой валюты ещё нет."""
        currency_code = normalize_currency_code(currency_code)
        if currency_code not in self._wallets:
            self._wallets[currency_code] = Wallet(currency_code)
        return self._wallets[currency_code]

    def get_wallet(self, currency_code: str) -> Wallet | None:
        """Возвращает кошелёк по коду валюты или None, если его нет."""
        return self._wallets.get(normalize_currency_code(currency_code))

    def get_total_value(self, base_currency: str = "USD", pairs: dict | None = None) -> float:
        """Считает суммарную стоимость всех кошельков в базовой валюте."""
        base_currency = normalize_currency_code(base_currency)
        pairs = pairs or {}
        total = 0.0
        for wallet in self._wallets.values():
            if wallet.balance == 0:
                continue
            total += convert_amount(wallet.balance, wallet.currency_code, base_currency, pairs)
        return total

    def to_dict(self) -> dict:
        """Готовит портфель к записи в portfolios.json."""
        return {
            "user_id": self._user_id,
            "wallets": {code: wallet.to_dict() for code, wallet in self._wallets.items()},
        }

    @classmethod
    def from_dict(cls, data: dict, user: User | None = None) -> "Portfolio":
        """Создаёт портфель из словаря, прочитанного из portfolios.json."""
        wallets = {}
        for code, wallet_data in data.get("wallets", {}).items():
            wallets[code] = Wallet.from_dict(code, wallet_data)
        return cls(user_id=data["user_id"], wallets=wallets, user=user)

    def __repr__(self) -> str:
        return f"Portfolio(user_id={self._user_id}, currencies={list(self._wallets)})"
