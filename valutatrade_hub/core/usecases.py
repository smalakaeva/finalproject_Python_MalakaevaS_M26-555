"""Бизнес-логика приложения: регистрация, вход, покупка, продажа и курсы.

CLI не содержит логики - он только вызывает функции из этого модуля.
"""

from valutatrade_hub.core.currencies import get_currency, is_crypto
from valutatrade_hub.core.exceptions import (
    CurrencyNotFoundError,
    InvalidPasswordError,
    UserAlreadyExistsError,
    UserNotFoundError,
    ValidationError,
    ValutaTradeError,
    WalletNotFoundError,
)
from valutatrade_hub.core.models import Portfolio, User
from valutatrade_hub.core.utils import (
    cache_with_ttl,
    convert_amount,
    get_usd_price,
    normalize_currency_code,
    seconds_since,
    validate_amount,
    validate_password,
    validate_username,
)
from valutatrade_hub.decorators import log_action
from valutatrade_hub.infra.database import DatabaseManager
from valutatrade_hub.infra.settings import SettingsLoader
from valutatrade_hub.parser_service.updater import build_updater

# результат чтения rates.json кешируется на несколько секунд,
# чтобы одна команда не перечитывала файл несколько раз
RATES_CACHE_SECONDS = 5


@cache_with_ttl(RATES_CACHE_SECONDS)
def _load_snapshot() -> dict:
    """Читает снимок курсов из rates.json."""
    return DatabaseManager().load_rates()


def _base_currency() -> str:
    """Базовая валюта из настроек (по умолчанию USD)."""
    return normalize_currency_code(SettingsLoader().get("base_currency", "USD"))


def _rates_ttl() -> int:
    """Срок годности кеша курсов в секундах."""
    return int(SettingsLoader().get("rates_ttl_seconds", 300))


def _pair_values(snapshot: dict) -> dict:
    """Превращает снимок курсов в простой словарь {"BTC_USD": 59337.21}."""
    values = {}
    for pair, data in snapshot.get("pairs", {}).items():
        if isinstance(data, dict) and data.get("rate"):
            values[pair] = float(data["rate"])
    return values


def _pair_updated_at(snapshot: dict, code: str) -> str | None:
    """Когда последний раз обновлялся курс валюты к базовой."""
    pair = f"{code}_{_base_currency()}"
    data = snapshot.get("pairs", {}).get(pair, {})
    return data.get("updated_at")


def _is_fresh(snapshot: dict, code: str) -> bool:
    """Проверяет, что курс валюты есть в кеше и он не устарел."""
    if code == _base_currency():
        return True
    age = seconds_since(_pair_updated_at(snapshot, code))
    if age is None:
        return False
    return age <= _rates_ttl()


def _get_snapshot(codes: list) -> tuple[dict, bool]:
    """Возвращает снимок курсов и признак того, что данные устарели.

    Если по какой-то валюте курс старше TTL, пробуем обновить его через
    Parser Service. Если обновление не удалось - отдаём старые данные и
    сообщаем об этом вторым значением.
    """
    snapshot = _load_snapshot()
    if all(_is_fresh(snapshot, code) for code in codes):
        return snapshot, False
    try:
        update_rates()
    except ValutaTradeError:
        # парсер недоступен - работаем с тем, что есть в кеше
        pass
    snapshot = _load_snapshot()
    return snapshot, not all(_is_fresh(snapshot, code) for code in codes)


# --- пользователи -----------------------------------------------------------


def _find_user_data(username: str) -> dict | None:
    """Ищет пользователя в users.json по имени."""
    for user_data in DatabaseManager().load_users():
        if user_data.get("username") == username:
            return user_data
    return None


@log_action("REGISTER")
def register(username: str, password: str) -> User:
    """Создаёт нового пользователя и пустой портфель для него."""
    username = validate_username(username)
    validate_password(password)

    database = DatabaseManager()
    if _find_user_data(username) is not None:
        raise UserAlreadyExistsError(username)

    user = User.create(database.next_user_id(), username, password)
    users = database.load_users()
    users.append(user.to_dict())
    database.save_users(users)

    portfolios = database.load_portfolios()
    portfolios.append(Portfolio(user.user_id, user=user).to_dict())
    database.save_portfolios(portfolios)
    return user


@log_action("LOGIN")
def login(username: str, password: str) -> User:
    """Проверяет пару логин/пароль и возвращает пользователя."""
    username = validate_username(username)
    user_data = _find_user_data(username)
    if user_data is None:
        raise UserNotFoundError(username)

    user = User.from_dict(user_data)
    if not user.verify_password(password):
        raise InvalidPasswordError()
    return user


# --- портфель ---------------------------------------------------------------


def _load_portfolio(user: User) -> Portfolio:
    """Загружает портфель пользователя из portfolios.json."""
    for portfolio_data in DatabaseManager().load_portfolios():
        if portfolio_data.get("user_id") == user.user_id:
            return Portfolio.from_dict(portfolio_data, user=user)
    return Portfolio(user.user_id, user=user)


def _save_portfolio(portfolio: Portfolio) -> None:
    """Сохраняет портфель: читаем файл, меняем одну запись, пишем обратно."""
    database = DatabaseManager()
    portfolios = database.load_portfolios()
    for index, portfolio_data in enumerate(portfolios):
        if portfolio_data.get("user_id") == portfolio.user_id:
            portfolios[index] = portfolio.to_dict()
            break
    else:
        portfolios.append(portfolio.to_dict())
    database.save_portfolios(portfolios)


def _check_base(base: str) -> str:
    """Проверяет базовую валюту конвертации."""
    base = normalize_currency_code(base)
    try:
        get_currency(base)
    except CurrencyNotFoundError as error:
        raise ValidationError(f"Неизвестная базовая валюта '{base}'") from error
    return base


def get_portfolio_view(user: User, base: str = "USD") -> dict:
    """Собирает данные для команды show-portfolio."""
    base = _check_base(base)
    portfolio = _load_portfolio(user)
    wallets = portfolio.wallets

    snapshot, stale = _get_snapshot([*wallets.keys(), base])
    pairs = _pair_values(snapshot)

    rows = []
    total = 0.0
    for code in sorted(wallets):
        wallet = wallets[code]
        try:
            value = convert_amount(wallet.balance, code, base, pairs)
        except ValutaTradeError:
            value = None
        else:
            total += value
        rows.append({"code": code, "balance": wallet.balance, "value": value})

    return {
        "username": user.username,
        "base": base,
        "rows": rows,
        "total": total,
        "stale": stale,
    }


# --- сделки -----------------------------------------------------------------


def _rate_to_base(code: str, base: str) -> tuple[float, str | None, bool]:
    """Курс валюты к базовой: значение, время обновления и признак устаревания."""
    if code == base:
        return 1.0, None, False
    snapshot, stale = _get_snapshot([code, base])
    pairs = _pair_values(snapshot)
    rate = convert_amount(1.0, code, base, pairs)
    return rate, _pair_updated_at(snapshot, code), stale


@log_action("BUY", verbose=True)
def buy(user: User, currency_code: str, amount: float) -> dict:
    """Покупает валюту: списывает стоимость с базового кошелька.

    Покупка базовой валюты (USD) трактуется как пополнение счёта.
    """
    currency = get_currency(normalize_currency_code(currency_code))
    amount = validate_amount(amount)
    base = _base_currency()
    rate, updated_at, stale = _rate_to_base(currency.code, base)

    portfolio = _load_portfolio(user)
    wallet = portfolio.add_currency(currency.code)
    balance_before = wallet.balance
    cost = amount * rate

    result = {
        "currency": currency.code,
        "amount": amount,
        "rate": rate,
        "base": base,
        "cost": cost,
        "balance_before": balance_before,
        "updated_at": updated_at,
        "stale": stale,
        "is_deposit": currency.code == base,
        "base_balance_before": None,
        "base_balance_after": None,
    }

    if currency.code == base:
        # пополнение счёта в базовой валюте
        wallet.deposit(amount)
    else:
        base_wallet = portfolio.add_currency(base)
        result["base_balance_before"] = base_wallet.balance
        base_wallet.withdraw(cost)
        wallet.deposit(amount)
        result["base_balance_after"] = base_wallet.balance

    result["balance_after"] = wallet.balance
    _save_portfolio(portfolio)
    return result


@log_action("SELL", verbose=True)
def sell(user: User, currency_code: str, amount: float) -> dict:
    """Продаёт валюту: начисляет выручку на базовый кошелёк."""
    currency = get_currency(normalize_currency_code(currency_code))
    amount = validate_amount(amount)
    base = _base_currency()

    portfolio = _load_portfolio(user)
    wallet = portfolio.get_wallet(currency.code)
    if wallet is None:
        raise WalletNotFoundError(currency.code)

    rate, updated_at, stale = _rate_to_base(currency.code, base)
    balance_before = wallet.balance
    wallet.withdraw(amount)
    revenue = amount * rate

    result = {
        "currency": currency.code,
        "amount": amount,
        "rate": rate,
        "base": base,
        "revenue": revenue,
        "balance_before": balance_before,
        "balance_after": wallet.balance,
        "updated_at": updated_at,
        "stale": stale,
        "is_withdraw": currency.code == base,
        "base_balance_before": None,
        "base_balance_after": None,
    }

    if currency.code != base:
        base_wallet = portfolio.add_currency(base)
        result["base_balance_before"] = base_wallet.balance
        base_wallet.deposit(revenue)
        result["base_balance_after"] = base_wallet.balance

    _save_portfolio(portfolio)
    return result


# --- курсы ------------------------------------------------------------------


def get_rate(from_code: str, to_code: str) -> dict:
    """Возвращает курс одной валюты к другой (команда get-rate)."""
    from_currency = get_currency(normalize_currency_code(from_code))
    to_currency = get_currency(normalize_currency_code(to_code))

    snapshot, stale = _get_snapshot([from_currency.code, to_currency.code])
    pairs = _pair_values(snapshot)

    rate = convert_amount(1.0, from_currency.code, to_currency.code, pairs)
    reverse_rate = convert_amount(1.0, to_currency.code, from_currency.code, pairs)
    updated_at = _pair_updated_at(snapshot, from_currency.code) or _pair_updated_at(
        snapshot, to_currency.code
    )

    return {
        "from": from_currency.code,
        "to": to_currency.code,
        "rate": rate,
        "reverse_rate": reverse_rate,
        "updated_at": updated_at,
        "stale": stale,
    }


def update_rates(source: str | None = None) -> dict:
    """Запускает Parser Service и сбрасывает кеш чтения rates.json."""
    report = build_updater(source).run_update()
    _load_snapshot.clear()
    return report


def get_cached_rates(
    currency: str | None = None,
    top: int | None = None,
    base: str | None = None,
) -> dict:
    """Готовит данные для команды show-rates (только чтение кеша)."""
    snapshot = _load_snapshot()
    pairs = _pair_values(snapshot)
    base = _check_base(base) if base else _base_currency()

    rows = []
    for pair, data in snapshot.get("pairs", {}).items():
        from_code = pair.split("_")[0]
        rate = pairs.get(pair)
        if rate is None:
            continue
        if base != _base_currency():
            # пересчитываем курс относительно другой базы
            price = get_usd_price(from_code, pairs)
            base_price = get_usd_price(base, pairs)
            if price is None or base_price is None:
                continue
            rate = price / base_price
            pair = f"{from_code}_{base}"
        rows.append(
            {
                "pair": pair,
                "code": from_code,
                "rate": rate,
                "updated_at": data.get("updated_at"),
                "source": data.get("source", "-"),
            }
        )

    if currency:
        code = normalize_currency_code(currency)
        rows = [row for row in rows if row["code"] == code or row["pair"].endswith(f"_{code}")]

    if top:
        crypto_rows = []
        for row in rows:
            try:
                if is_crypto(row["code"]):
                    crypto_rows.append(row)
            except CurrencyNotFoundError:
                continue
        rows = sorted(crypto_rows, key=lambda row: row["rate"], reverse=True)[:top]
    else:
        rows = sorted(rows, key=lambda row: row["pair"])

    return {
        "rows": rows,
        "last_refresh": snapshot.get("last_refresh"),
        "cache_empty": not snapshot.get("pairs"),
        "base": base,
    }
