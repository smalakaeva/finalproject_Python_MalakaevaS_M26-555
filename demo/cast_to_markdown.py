"""Достаёт текст сессии из demo/demo.cast и складывает его в demo/demo_session.md."""

import json
import pathlib

CAST_PATH = pathlib.Path(__file__).parent / "demo.cast"
MARKDOWN_PATH = pathlib.Path(__file__).parent / "demo_session.md"

HEADER = """# Демо-сессия ValutaTrade Hub

Полный сценарий работы: регистрация -> вход -> пополнение -> update-rates ->
покупка/продажа -> show-portfolio -> get-rate -> show-rates, плюс обработка ошибок.

Запись терминала: [demo.cast](demo.cast) (`asciinema play demo/demo.cast`).
Сценарий команд: [demo_commands.txt](demo_commands.txt).

```console
"""


def main() -> None:
    """Собирает вывод программы из событий записи asciinema."""
    chunks = []
    with open(CAST_PATH, encoding="utf-8") as cast_file:
        cast_file.readline()  # первая строка - заголовок записи
        for line in cast_file:
            event = json.loads(line)
            if event[1] == "o":
                chunks.append(event[2])

    text = "".join(chunks).replace("\r\n", "\n")
    MARKDOWN_PATH.write_text(HEADER + text + "```\n", encoding="utf-8")
    print(f"Готово: {MARKDOWN_PATH}")


if __name__ == "__main__":
    main()
