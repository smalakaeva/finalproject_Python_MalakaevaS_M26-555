"""Командный интерфейс ValutaTrade Hub.

Здесь нет бизнес-логики: команды только разбирают аргументы, вызывают
функции из core/usecases.py и печатают результат.
"""

import shlex
import sys

from prettytable import PrettyTable

from valutatrade_hub.core import usecases
from valutatrade_hub.core.currencies import get_currency, supported_codes
from valutatrade_hub.core.exceptions import (
    ApiRequestError,
    AuthRequiredError,
    CurrencyNotFoundError,
    InsufficientFundsError,
    ValidationError,
    ValutaTradeError,
)
from valutatrade_hub.core.utils import (
    format_amount,
    format_money,
    format_rate,
    pretty_time,
)
from valutatrade_hub.decorators import confirm_action
from valutatrade_hub.logging_config import setup_logging

PROMPT = "> "
SEPARATOR = "-" * 33

HELP_TEXT = {
    "register": "register --username <имя> --password <пароль> - регистрация нового пользователя",
    "login": "login --username <имя> --password <пароль> - вход в систему",
    "logout": "logout - выйти из текущей сессии",
    "show-portfolio": "show-portfolio [--base <валюта>] - показать кошельки и итоговую стоимость",
    "buy": "buy --currency <валюта> --amount <число> - купить валюту (USD - пополнение счёта)",
    "sell": "sell --currency <валюта> --amount <число> - продать валюту",
    "get-rate": "get-rate --from <валюта> --to <валюта> - курс одной валюты к другой",
    "update-rates": "update-rates [--source coingecko|exchangerate] - обновить курсы из API",
    "show-rates": "show-rates [--currency <валюта>] [--top <N>] [--base <валюта>] - курсы из кеша",
    "currencies": "currencies - список поддерживаемых валют",
    "help": "help [команда] - справка по командам",
    "exit": "exit - выход из программы",
}


def parse_options(tokens: list, allowed: tuple) -> dict:
    """Разбирает аргументы вида --ключ значение."""
    options = {}
    index = 0
    while index < len(tokens):
        token = tokens[index]
        if not token.startswith("--"):
            raise ValidationError(f"Непонятный аргумент '{token}', ожидался --ключ значение")
        name = token[2:]
        if name not in allowed:
            raise ValidationError(
                f"Неизвестный аргумент '--{name}'. Доступны: {', '.join('--' + a for a in allowed)}"
            )
        if index + 1 >= len(tokens):
            raise ValidationError(f"Не указано значение для '--{name}'")
        options[name] = tokens[index + 1]
        index += 2
    return options


def require_options(options: dict, names: tuple) -> None:
    """Проверяет, что обязательные аргументы переданы."""
    for name in names:
        if not options.get(name):
            raise ValidationError(f"Аргумент '--{name}' обязателен")


class CommandLineApp:
    """Консольное приложение: хранит текущую сессию и выполняет команды."""

    def __init__(self):
        setup_logging()
        self.current_user = None
        self.handlers = {
            "register": self._cmd_register,
            "login": self._cmd_login,
            "logout": self._cmd_logout,
            "show-portfolio": self._cmd_show_portfolio,
            "buy": self._cmd_buy,
            "sell": self._cmd_sell,
            "get-rate": self._cmd_get_rate,
            "update-rates": self._cmd_update_rates,
            "show-rates": self._cmd_show_rates,
            "currencies": self._cmd_currencies,
            "help": self._cmd_help,
        }

    # --- запуск -----------------------------------------------------------

    def run_interactive(self) -> None:
        """Основной цикл: читает команды до exit или Ctrl+D."""
        print("ValutaTrade Hub. Введите 'help' для списка команд, 'exit' для выхода.")
        while True:
            try:
                line = input(PROMPT)
            except (EOFError, KeyboardInterrupt):
                print("\nДо встречи!")
                return
            line = line.strip()
            if not line:
                continue
            if line in ("exit", "quit"):
                print("До встречи!")
                return
            self.run_command(shlex.split(line))

    def run_command(self, tokens: list) -> int:
        """Выполняет одну команду и возвращает код результата (0 - успех)."""
        if not tokens:
            return 0
        name = tokens[0]
        handler = self.handlers.get(name)
        if handler is None:
            print(f"Неизвестная команда '{name}'. Введите 'help'.")
            return 1

        try:
            handler(tokens[1:])
        except InsufficientFundsError as error:
            print(error)
            return 1
        except CurrencyNotFoundError as error:
            print(error)
            print(f"Поддерживаемые валюты: {', '.join(supported_codes())}")
            print("Подсказка: help get-rate")
            return 1
        except ApiRequestError as error:
            print(error)
            print("Проверьте подключение к сети и повторите попытку позже.")
            return 1
        except ValutaTradeError as error:
            print(error)
            return 1
        except Exception as error:
            print(f"Непредвиденная ошибка: {error}")
            return 1
        return 0

    # --- вспомогательное --------------------------------------------------

    def _require_login(self):
        """Возвращает текущего пользователя или сообщает о необходимости входа."""
        if self.current_user is None:
            raise AuthRequiredError()
        return self.current_user

    @staticmethod
    def _warn_if_stale(data: dict) -> None:
        """Печатает предупреждение, если курсы в кеше устарели."""
        if data.get("stale"):
            print("Внимание: курсы в кеше устарели. Обновите их командой update-rates.")

    @staticmethod
    def _print_wallet_change(code: str, before, after) -> None:
        """Строка 'было -> стало' для одного кошелька."""
        if before is None or after is None:
            return
        print(f"- {code}: было {format_amount(code, before)} → стало {format_amount(code, after)}")

    # --- команды ----------------------------------------------------------

    def _cmd_register(self, tokens: list) -> None:
        """Команда register."""
        options = parse_options(tokens, ("username", "password"))
        require_options(options, ("username", "password"))
        user = usecases.register(username=options["username"], password=options["password"])
        print(
            f"Пользователь '{user.username}' зарегистрирован (id={user.user_id}). "
            f"Войдите: login --username {user.username} --password ****"
        )

    def _cmd_login(self, tokens: list) -> None:
        """Команда login."""
        options = parse_options(tokens, ("username", "password"))
        require_options(options, ("username", "password"))
        user = usecases.login(username=options["username"], password=options["password"])
        self.current_user = user
        print(f"Вы вошли как '{user.username}'")

    def _cmd_logout(self, tokens: list) -> None:
        """Команда logout."""
        parse_options(tokens, ())
        user = self._require_login()
        self.current_user = None
        print(f"Пользователь '{user.username}' вышел из системы")

    def _cmd_show_portfolio(self, tokens: list) -> None:
        """Команда show-portfolio."""
        options = parse_options(tokens, ("base",))
        user = self._require_login()
        view = usecases.get_portfolio_view(user=user, base=options.get("base", "USD"))

        print(f"Портфель пользователя '{view['username']}' (база: {view['base']}):")
        if not view["rows"]:
            print("Кошельков пока нет. Пополните счёт: buy --currency USD --amount 1000")
            return

        for row in view["rows"]:
            balance = format_amount(row["code"], row["balance"])
            if row["value"] is None:
                print(f"- {row['code']}: {balance}  → курс недоступен")
            else:
                print(f"- {row['code']}: {balance}  → {format_money(row['value'])} {view['base']}")
        print(SEPARATOR)
        print(f"ИТОГО: {format_money(view['total'])} {view['base']}")
        self._warn_if_stale(view)

    @confirm_action("Подтвердить покупку?")
    def _cmd_buy(self, tokens: list) -> None:
        """Команда buy."""
        options = parse_options(tokens, ("currency", "amount"))
        require_options(options, ("currency", "amount"))
        user = self._require_login()
        result = usecases.buy(
            user=user,
            currency_code=options["currency"],
            amount=options["amount"],
        )

        code = result["currency"]
        if result["is_deposit"]:
            print(f"Счёт пополнен: {format_money(result['amount'])} {code}")
        else:
            print(
                f"Покупка выполнена: {format_amount(code, result['amount'])} {code} "
                f"по курсу {format_rate(result['rate'])} {result['base']}/{code}"
            )
        print("Изменения в портфеле:")
        self._print_wallet_change(code, result["balance_before"], result["balance_after"])
        self._print_wallet_change(
            result["base"], result["base_balance_before"], result["base_balance_after"]
        )
        if not result["is_deposit"]:
            print(f"Оценочная стоимость покупки: {format_money(result['cost'])} {result['base']}")
        self._warn_if_stale(result)

    @confirm_action("Подтвердить продажу?")
    def _cmd_sell(self, tokens: list) -> None:
        """Команда sell."""
        options = parse_options(tokens, ("currency", "amount"))
        require_options(options, ("currency", "amount"))
        user = self._require_login()
        result = usecases.sell(
            user=user,
            currency_code=options["currency"],
            amount=options["amount"],
        )

        code = result["currency"]
        if result["is_withdraw"]:
            print(f"Со счёта снято: {format_money(result['amount'])} {code}")
        else:
            print(
                f"Продажа выполнена: {format_amount(code, result['amount'])} {code} "
                f"по курсу {format_rate(result['rate'])} {result['base']}/{code}"
            )
        print("Изменения в портфеле:")
        self._print_wallet_change(code, result["balance_before"], result["balance_after"])
        self._print_wallet_change(
            result["base"], result["base_balance_before"], result["base_balance_after"]
        )
        if not result["is_withdraw"]:
            print(f"Оценочная выручка: {format_money(result['revenue'])} {result['base']}")
        self._warn_if_stale(result)

    def _cmd_get_rate(self, tokens: list) -> None:
        """Команда get-rate."""
        options = parse_options(tokens, ("from", "to"))
        require_options(options, ("from", "to"))
        result = usecases.get_rate(from_code=options["from"], to_code=options["to"])
        print(
            f"Курс {result['from']}→{result['to']}: {format_rate(result['rate'])} "
            f"(обновлено: {pretty_time(result['updated_at'])})"
        )
        print(
            f"Обратный курс {result['to']}→{result['from']}: {format_rate(result['reverse_rate'])}"
        )
        self._warn_if_stale(result)

    def _cmd_update_rates(self, tokens: list) -> None:
        """Команда update-rates."""
        options = parse_options(tokens, ("source",))
        print("INFO: Starting rates update...")
        report = usecases.update_rates(source=options.get("source"))

        for item in report["sources"]:
            if item["ok"]:
                print(f"INFO: Fetching from {item['source']}... OK ({item['count']} rates)")
            else:
                print(f"ERROR: Failed to fetch from {item['source']}: {item['error']}")

        if report["updated"]:
            print(f"INFO: Writing {report['updated']} rates to {report['rates_file']}...")

        if report["errors"]:
            print("Update completed with errors. Check logs/parser.log for details.")
        elif report["updated"]:
            print(
                f"Update successful. Total rates updated: {report['updated']}. "
                f"Last refresh: {report['last_refresh']}"
            )
        else:
            print("Обновить курсы не удалось. Проверьте logs/parser.log.")

    def _cmd_show_rates(self, tokens: list) -> None:
        """Команда show-rates."""
        options = parse_options(tokens, ("currency", "top", "base"))
        top = None
        if options.get("top"):
            try:
                top = int(options["top"])
            except ValueError as error:
                raise ValidationError("'--top' должен быть целым числом") from error
            if top <= 0:
                raise ValidationError("'--top' должен быть больше нуля")

        data = usecases.get_cached_rates(
            currency=options.get("currency"),
            top=top,
            base=options.get("base"),
        )

        if data["cache_empty"]:
            print("Локальный кеш курсов пуст. Выполните 'update-rates', чтобы загрузить данные.")
            return
        if not data["rows"]:
            print(f"Курс для '{options.get('currency', '')}' не найден в кеше.")
            return

        print(f"Rates from cache (updated at {data['last_refresh']}):")
        table = PrettyTable()
        table.field_names = ["Пара", "Курс", "Обновлено", "Источник"]
        table.align = "l"
        for row in data["rows"]:
            table.add_row(
                [
                    row["pair"],
                    format_rate(row["rate"]),
                    pretty_time(row["updated_at"]),
                    row["source"],
                ]
            )
        print(table)

    def _cmd_currencies(self, tokens: list) -> None:
        """Команда currencies - список поддерживаемых валют."""
        parse_options(tokens, ())
        for code in supported_codes():
            print(get_currency(code).get_display_info())

    def _cmd_help(self, tokens: list) -> None:
        """Команда help."""
        if tokens and not tokens[0].startswith("--"):
            name = tokens[0]
            if name not in HELP_TEXT:
                print(f"Нет справки по команде '{name}'")
                return
            print(HELP_TEXT[name])
            return
        print("Доступные команды:")
        for text in HELP_TEXT.values():
            print(f"  {text}")


def main(argv: list | None = None) -> int:
    """Точка входа CLI: без аргументов запускает интерактивный режим."""
    arguments = list(sys.argv[1:] if argv is None else argv)
    app = CommandLineApp()
    if arguments:
        return app.run_command(arguments)
    app.run_interactive()
    return 0


if __name__ == "__main__":
    sys.exit(main())
