# ValutaTrade Hub

Итоговый проект по Python: консольная платформа для отслеживания курсов валют и
симуляции торговли. Пользователь регистрируется, пополняет виртуальный счёт,
покупает и продаёт фиатные и криптовалюты, смотрит стоимость своего портфеля и
актуальные курсы.

Проект состоит из двух сервисов:

- **Core Service** — основное приложение: пользователи, кошельки, портфели,
  сделки и командный интерфейс (CLI). Курсы берёт из локального кеша
  `data/rates.json`.
- **Parser Service** — отдельный сервис, который обращается к публичным API
  (CoinGecko для крипты и ExchangeRate-API для фиата), приводит ответы к единому
  формату, обновляет кеш и ведёт историю замеров в `data/exchange_rates.json`.

Данные хранятся в JSON-файлах, курсы — в кеше со сроком годности (TTL).

## Структура проекта

```
finalproject_Python_MalakaevaS_M26-555/
│
├── data/
│    ├── users.json             # пользователи
│    ├── portfolios.json        # портфели и кошельки
│    ├── rates.json             # кеш текущих курсов (его читает Core Service)
│    └── exchange_rates.json    # история замеров Parser Service
├── valutatrade_hub/
│    ├── __init__.py
│    ├── logging_config.py      # настройка логов (формат, уровень, ротация)
│    ├── decorators.py          # @log_action, @confirm_action
│    ├── core/
│    │    ├── __init__.py
│    │    ├── currencies.py     # Currency и наследники FiatCurrency/CryptoCurrency
│    │    ├── exceptions.py     # пользовательские исключения
│    │    ├── models.py         # User, Wallet, Portfolio
│    │    ├── usecases.py       # бизнес-логика (register, login, buy, sell, ...)
│    │    └── utils.py          # валидация, хеширование, конвертация, кеш
│    ├── infra/
│    │    ├── __init__.py
│    │    ├── settings.py       # SettingsLoader (Singleton)
│    │    └── database.py       # DatabaseManager (Singleton)
│    ├── parser_service/
│    │    ├── __init__.py
│    │    ├── config.py         # ParserConfig: ключи, URL, списки валют
│    │    ├── api_clients.py    # BaseApiClient, CoinGeckoClient, ExchangeRateApiClient
│    │    ├── updater.py        # RatesUpdater.run_update()
│    │    ├── storage.py        # запись rates.json и exchange_rates.json
│    │    └── scheduler.py      # периодическое обновление курсов
│    └── cli/
│         ├── __init__.py
│         └── interface.py      # команды CLI
│
├── demo/                       # сценарий и запись демо-сессии
├── logs/                       # actions.log и parser.log (в git не попадают)
├── config.json                 # настройки приложения (пути, TTL, логи)
├── main.py                     # точка входа
├── pyproject.toml
├── uv.lock
├── README.md
└── .gitignore
```

## Установка

Нужен Python 3.12+ и [uv](https://docs.astral.sh/uv/).

```bash
git clone https://github.com/smalakaeva/finalproject_Python_MalakaevaS_M26-555.git
cd finalproject_Python_MalakaevaS_M26-555
uv sync
```

Внешние зависимости: `prettytable` (таблицы в CLI), `requests` (запросы к API),
`ruff` (линтер и форматтер, группа dev).

## Запуск

Интерактивный режим:

```bash
uv run python main.py
```

В интерактивном режиме покупка и продажа спрашивают подтверждение (декоратор
`@confirm_action`); отключается ключом `confirm_trades` в `config.json`.

Одна команда без входа в интерактивный режим:

```bash
uv run python main.py get-rate --from USD --to BTC
```

Проект можно собрать и установить как пакет — тогда появится команда `valutatrade`:

```bash
uv build
uv pip install dist/finalproject_malakaevas_m26_555-0.1.0-py3-none-any.whl
valutatrade
```

Проверка стиля кода:

```bash
uv run ruff check .
uv run ruff format .
```

## Команды CLI

| Команда                                                          | Назначение                                      |
| ---------------------------------------------------------------- | ----------------------------------------------- |
| `register --username <имя> --password <пароль>`                  | регистрация (пароль не короче 4 символов)       |
| `login --username <имя> --password <пароль>`                     | вход в систему                                  |
| `logout`                                                         | выход из сессии                                 |
| `show-portfolio [--base <валюта>]`                               | кошельки и итоговая стоимость в базовой валюте  |
| `buy --currency <валюта> --amount <число>`                       | покупка валюты (покупка USD = пополнение счёта) |
| `sell --currency <валюта> --amount <число>`                      | продажа валюты, выручка идёт на USD-кошелёк     |
| `get-rate --from <валюта> --to <валюта>`                         | курс одной валюты к другой                      |
| `update-rates [--source coingecko\|exchangerate]`                | обновить курсы через Parser Service             |
| `show-rates [--currency <валюта>] [--top <N>] [--base <валюта>]` | курсы из кеша таблицей                          |
| `currencies`                                                     | список поддерживаемых валют                     |
| `help [команда]`                                                 | справка                                         |
| `exit`                                                           | выход                                           |

Поддерживаемые валюты: USD, EUR, GBP, RUB (фиат) и BTC, ETH, SOL (крипта).

### Примеры

```console
> register --username alice --password 1234
Пользователь 'alice' зарегистрирован (id=1). Войдите: login --username alice --password ****

> login --username alice --password 1234
Вы вошли как 'alice'

> buy --currency USD --amount 10000
Счёт пополнен: 10,000.00 USD
Изменения в портфеле:
- USD: было 0.00 → стало 10000.00

> buy --currency BTC --amount 0.05
Покупка выполнена: 0.0500 BTC по курсу 80,190.00 USD/BTC
Изменения в портфеле:
- BTC: было 0.0000 → стало 0.0500
- USD: было 10000.00 → стало 5990.50
Оценочная стоимость покупки: 4,009.50 USD

> show-portfolio
Портфель пользователя 'alice' (база: USD):
- BTC: 0.0500  → 4,009.50 USD
- ETH: 1.0000  → 2,322.33 USD
- USD: 3668.17  → 3,668.17 USD
---------------------------------
ИТОГО: 10,000.00 USD

> get-rate --from USD --to BTC
Курс USD→BTC: 0.00001247 (обновлено: 2026-10-24 18:10:52)
Обратный курс BTC→USD: 80,190.00

> show-rates --top 2
Rates from cache (updated at 2026-10-24T18:10:52Z):
+---------+-----------+---------------------+-----------+
| Пара    | Курс      | Обновлено           | Источник  |
+---------+-----------+---------------------+-----------+
| BTC_USD | 80,190.00 | 2026-10-24 18:10:52 | CoinGecko |
| ETH_USD | 2,322.33  | 2026-10-24 18:10:52 | CoinGecko |
+---------+-----------+---------------------+-----------+
```

Сообщения об ошибках:

```console
> sell --currency BTC --amount 5
Недостаточно средств: доступно 0.0400 BTC, требуется 5.0000 BTC

> sell --currency SOL --amount 1
У вас нет кошелька 'SOL'. Добавьте валюту: она создаётся автоматически при первой покупке.

> get-rate --from USD --to ABC
Неизвестная валюта 'ABC'
Поддерживаемые валюты: BTC, ETH, EUR, GBP, RUB, SOL, USD
Подсказка: help get-rate

> buy --currency BTC --amount 0.01
Сначала выполните login
```

## Кеш курсов и TTL

- `data/rates.json` — снимок текущего состояния: для каждой пары хранится один
  последний курс, время обновления и источник. Core Service читает только этот файл.
- `data/exchange_rates.json` — история всех замеров. У каждой записи уникальный
  `id` вида `BTC_USD_2026-10-24T18:10:52Z`, поэтому дубликаты не появляются.
- TTL задаётся в `config.json` ключом `rates_ttl_seconds` (по умолчанию 300 секунд).
  Если курс в кеше старше TTL, приложение само пробует обновить его через
  Parser Service. Когда обновление не удалось, сделка проходит по старому курсу,
  но выводится предупреждение: `Внимание: курсы в кеше устарели. Обновите их
командой update-rates.`
- Запись в файлы атомарная: сначала во временный файл, потом `rename`.

## Parser Service

Запуск вручную из CLI:

```console
> update-rates
INFO: Starting rates update...
INFO: Fetching from CoinGecko... OK (3 rates)
INFO: Fetching from ExchangeRate-API... OK (3 rates)
INFO: Writing 6 rates to data/rates.json...
Update successful. Total rates updated: 6. Last refresh: 2026-10-24T18:10:52Z
```

Если один источник недоступен, обновление не прерывается: данные второго
источника всё равно сохраняются, а ошибка попадает в `logs/parser.log`.

Периодическое обновление по таймеру (интервал в секундах):

```bash
uv run python -m valutatrade_hub.parser_service.scheduler 300
```

### Где хранить API-ключ

CoinGecko для учебных задач работает без ключа. Для фиатных валют нужен
бесплатный ключ с [exchangerate-api.com](https://www.exchangerate-api.com/).
Ключ в код не пишется — он берётся из переменной окружения
`EXCHANGERATE_API_KEY` или из файла `.env` в корне проекта (файл добавлен в
`.gitignore`):

```
EXCHANGERATE_API_KEY=ваш_ключ
```

Либо так:

```bash
export EXCHANGERATE_API_KEY=ваш_ключ
uv run python main.py update-rates
```

Без ключа команда `update-rates` обновит только криптовалюты и напишет об
отсутствии ключа — остальная логика продолжит работать на фиатных курсах из кеша.

## Логи

Настройка в `logging_config.py`, параметры — в `config.json`. Формат строковый,
уровень по умолчанию INFO, файлы с ротацией (1 МБ, 3 архива):

- `logs/actions.log` — операции пользователя (декоратор `@log_action`);
- `logs/parser.log` — работа Parser Service.

Пример записей:

```
INFO 2026-10-24T21:10:52 BUY user='alice' currency='BTC' amount=0.0500 rate=80190.00 base='USD' was=0.0000 now=0.0500 result=OK elapsed_ms=0
ERROR 2026-10-24T21:10:53 SELL user='alice' currency='BTC' amount=5.0000 result=ERROR error_type=InsufficientFundsError error_message='Недостаточно средств: доступно 0.0400 BTC, требуется 5.0000 BTC'
```

## Демо

Полный сценарий (регистрация → вход → пополнение → update-rates → покупка/продажа →
show-portfolio → get-rate → show-rates → ошибки) записан в
[demo/demo.cast](demo/demo.cast), текстовая версия той же сессии —
в [demo/demo_session.md](demo/demo_session.md).

Посмотреть запись:

```bash
asciinema play demo/demo.cast
```

Перезаписать демо (сценарий команд — `demo/demo_commands.txt`):

```bash
sh demo/record_demo.sh
```
