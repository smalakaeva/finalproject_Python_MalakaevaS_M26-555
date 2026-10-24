"""Работа с JSON-хранилищем. Реализован паттерн Singleton (DatabaseManager)."""

import json
import os
from pathlib import Path
from typing import Any

from valutatrade_hub.infra.settings import SettingsLoader


class DatabaseManager:
    """Простая обёртка над JSON-файлами из папки data/.

    Синглтон через __new__ по той же причине, что и в SettingsLoader:
    хранилище одно на всё приложение, а код остаётся простым.
    """

    _instance = None

    def __new__(cls) -> "DatabaseManager":
        if cls._instance is None:
            instance = super().__new__(cls)
            instance._settings = SettingsLoader()
            instance._prepare_files()
            cls._instance = instance
        return cls._instance

    # --- пути -------------------------------------------------------------

    @property
    def users_path(self) -> Path:
        """Путь к users.json."""
        return self._settings.path("users_file")

    @property
    def portfolios_path(self) -> Path:
        """Путь к portfolios.json."""
        return self._settings.path("portfolios_file")

    @property
    def rates_path(self) -> Path:
        """Путь к rates.json."""
        return self._settings.path("rates_file")

    @property
    def history_path(self) -> Path:
        """Путь к exchange_rates.json."""
        return self._settings.path("history_file")

    def _prepare_files(self) -> None:
        """Создаёт папку data/ и пустые файлы, если их ещё нет."""
        self._settings.path("data_dir").mkdir(parents=True, exist_ok=True)
        if not self.users_path.exists():
            self.write_json(self.users_path, [])
        if not self.portfolios_path.exists():
            self.write_json(self.portfolios_path, [])
        if not self.rates_path.exists():
            self.write_json(self.rates_path, {"pairs": {}, "last_refresh": None})
        if not self.history_path.exists():
            self.write_json(self.history_path, [])

    # --- базовые операции -------------------------------------------------

    @staticmethod
    def read_json(path: Path, default: Any) -> Any:
        """Читает JSON-файл. Если файла нет или он битый - возвращает default."""
        try:
            with open(path, encoding="utf-8") as data_file:
                return json.load(data_file)
        except (OSError, json.JSONDecodeError):
            return default

    @staticmethod
    def write_json(path: Path, data: Any) -> None:
        """Атомарно записывает JSON: сначала во временный файл, потом rename."""
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        temp_path = path.with_suffix(path.suffix + ".tmp")
        with open(temp_path, "w", encoding="utf-8") as data_file:
            json.dump(data, data_file, ensure_ascii=False, indent=2)
        os.replace(temp_path, path)

    # --- пользователи -----------------------------------------------------

    def load_users(self) -> list[dict]:
        """Список пользователей из users.json."""
        return self.read_json(self.users_path, [])

    def save_users(self, users: list[dict]) -> None:
        """Записывает список пользователей в users.json."""
        self.write_json(self.users_path, users)

    def next_user_id(self) -> int:
        """Следующий свободный user_id (автоинкремент)."""
        users = self.load_users()
        if not users:
            return 1
        return max(user["user_id"] for user in users) + 1

    # --- портфели ---------------------------------------------------------

    def load_portfolios(self) -> list[dict]:
        """Список портфелей из portfolios.json."""
        return self.read_json(self.portfolios_path, [])

    def save_portfolios(self, portfolios: list[dict]) -> None:
        """Записывает список портфелей в portfolios.json."""
        self.write_json(self.portfolios_path, portfolios)

    # --- курсы ------------------------------------------------------------

    def load_rates(self) -> dict:
        """Снимок курсов из rates.json."""
        return self.read_json(self.rates_path, {"pairs": {}, "last_refresh": None})

    def save_rates(self, rates: dict) -> None:
        """Записывает снимок курсов в rates.json."""
        self.write_json(self.rates_path, rates)
