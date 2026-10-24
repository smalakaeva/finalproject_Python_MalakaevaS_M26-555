#!/bin/sh
# Запись демо-сессии.
#
#   sh demo/record_demo.sh            - прогнать сценарий и обновить demo/demo_session.md
#   sh demo/record_demo.sh asciinema  - записать demo/demo.cast через asciinema
#
# Сценарий команд: demo/demo_commands.txt

set -e
cd "$(dirname "$0")/.."

if [ "$1" = "asciinema" ]; then
    asciinema rec demo/demo.cast --overwrite \
        --command "uv run python main.py < demo/demo_commands.txt"
    echo "Готово: demo/demo.cast (загрузить: asciinema upload demo/demo.cast)"
    exit 0
fi

{
    echo "# Демо-сессия ValutaTrade Hub"
    echo
    echo "Запись полного сценария работы: регистрация -> вход -> пополнение -> update-rates ->"
    echo "покупка/продажа -> show-portfolio -> get-rate -> show-rates, а также обработка ошибок."
    echo
    echo "Сценарий команд лежит в \`demo/demo_commands.txt\`, запись сделана скриптом \`demo/record_demo.sh\`."
    echo
    echo '```console'
    uv run python main.py < demo/demo_commands.txt
    echo '```'
} > demo/demo_session.md

echo "Готово: demo/demo_session.md"
