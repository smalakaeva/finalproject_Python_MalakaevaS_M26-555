#!/bin/sh
# Запись демо-сессии: asciinema-ролик + текстовый транскрипт.
#
#   sh demo/record_demo.sh
#
# Сценарий команд лежит в demo/demo_commands.txt.
# Перед записью стоит очистить data/users.json и data/portfolios.json (вписать []),
# иначе команда register ответит, что имя пользователя уже занято.

set -e
cd "$(dirname "$0")/.."

asciinema rec demo/demo.cast --overwrite --quiet \
    --command "uv run python main.py < demo/demo_commands.txt"

python3 demo/cast_to_markdown.py
echo "Готово: demo/demo.cast и demo/demo_session.md"
