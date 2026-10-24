"""Точка входа приложения ValutaTrade Hub.

Запуск интерактивного режима:
    python main.py
Запуск одной команды:
    python main.py get-rate --from USD --to BTC
"""

import sys

from valutatrade_hub.cli.interface import main

if __name__ == "__main__":
    sys.exit(main())
