"""Настройки проекта. Реализован паттерн Singleton (SettingsLoader)."""

import json
import os
from pathlib import Path
from typing import Any

# Корень проекта: .../valutatrade_hub/infra/settings.py -> на два уровня вверх.
# Если пакет установлен как библиотека, корень можно задать переменной окружения.
PROJECT_ROOT = Path(os.getenv("VALUTATRADE_HOME", Path(__file__).resolve().parents[2]))
CONFIG_FILE_NAME = "config.json"

# Значения по умолчанию - на случай, если config.json отсутствует или неполный
DEFAULT_SETTINGS: dict[str, Any] = {
    "data_dir": "data",
    "users_file": "data/users.json",
    "portfolios_file": "data/portfolios.json",
    "rates_file": "data/rates.json",
    "history_file": "data/exchange_rates.json",
    "log_dir": "logs",
    "actions_log": "logs/actions.log",
    "parser_log": "logs/parser.log",
    "log_level": "INFO",
    "log_max_bytes": 1048576,
    "log_backup_count": 3,
    "log_format": "text",
    "rates_ttl_seconds": 300,
    "base_currency": "USD",
    "confirm_trades": True,
}


class SettingsLoader:
    """Загружает и кеширует конфигурацию проекта.

    Синглтон сделан через __new__, а не через метакласс: так проще и
    понятнее читать код, а задача всего одна - не перечитывать config.json
    при каждом импорте модуля.
    """

    _instance = None

    def __new__(cls) -> "SettingsLoader":
        if cls._instance is None:
            instance = super().__new__(cls)
            instance._settings = {}
            instance.reload()
            cls._instance = instance
        return cls._instance

    def reload(self) -> None:
        """Перечитывает config.json и накладывает его на значения по умолчанию."""
        settings = dict(DEFAULT_SETTINGS)
        config_path = PROJECT_ROOT / CONFIG_FILE_NAME
        if config_path.exists():
            try:
                with open(config_path, encoding="utf-8") as config_file:
                    settings.update(json.load(config_file))
            except (OSError, json.JSONDecodeError):
                # битый конфиг не должен ломать приложение - работаем на дефолтах
                pass
        self._settings = settings

    def get(self, key: str, default: Any = None) -> Any:
        """Возвращает значение настройки по ключу."""
        return self._settings.get(key, default)

    def path(self, key: str) -> Path:
        """Возвращает абсолютный путь для настройки, в которой лежит путь."""
        return PROJECT_ROOT / str(self.get(key))

    @property
    def project_root(self) -> Path:
        """Корневая папка проекта."""
        return PROJECT_ROOT

    def as_dict(self) -> dict:
        """Копия всех настроек (для отладки)."""
        return dict(self._settings)
