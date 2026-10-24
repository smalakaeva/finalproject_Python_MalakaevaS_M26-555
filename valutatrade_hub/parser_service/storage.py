"""Чтение и запись файлов курсов: снимок rates.json и история exchange_rates.json."""

from pathlib import Path

from valutatrade_hub.core.utils import now_iso, parse_iso
from valutatrade_hub.infra.database import DatabaseManager
from valutatrade_hub.parser_service.config import ParserConfig


def make_history_id(from_code: str, to_code: str, timestamp: str) -> str:
    """Собирает идентификатор записи истории: BTC_USD_2025-10-10T12:00:00Z."""
    return f"{from_code}_{to_code}_{timestamp}"


def make_history_entry(
    from_code: str,
    to_code: str,
    rate: float,
    timestamp: str,
    source: str,
    meta: dict | None = None,
) -> dict:
    """Готовит одну запись для exchange_rates.json."""
    return {
        "id": make_history_id(from_code, to_code, timestamp),
        "from_currency": from_code,
        "to_currency": to_code,
        "rate": rate,
        "timestamp": timestamp,
        "source": source,
        "meta": meta or {},
    }


class RatesStorage:
    """Хранилище курсов Parser Service.

    rates.json - снимок текущих курсов (его читает Core Service),
    exchange_rates.json - журнал всех замеров (история).
    """

    def __init__(self, config: ParserConfig | None = None):
        self.config = config or ParserConfig()
        self.rates_path = Path(self.config.RATES_FILE_PATH)
        self.history_path = Path(self.config.HISTORY_FILE_PATH)
        self.database = DatabaseManager()

    # --- снимок текущих курсов -------------------------------------------

    def load_snapshot(self) -> dict:
        """Читает rates.json."""
        snapshot = self.database.read_json(self.rates_path, {"pairs": {}, "last_refresh": None})
        if "pairs" not in snapshot:
            snapshot = {"pairs": {}, "last_refresh": None}
        return snapshot

    def save_snapshot(self, new_pairs: dict) -> dict:
        """Обновляет rates.json новыми курсами.

        Для каждой пары хранится только один, самый свежий срез: если в
        файле уже лежит более новое значение, оно не перезаписывается.
        """
        snapshot = self.load_snapshot()
        pairs = snapshot.get("pairs", {})
        for pair, value in new_pairs.items():
            old = pairs.get(pair)
            if old and not self._is_newer(value.get("updated_at"), old.get("updated_at")):
                continue
            pairs[pair] = value
        snapshot["pairs"] = pairs
        snapshot["last_refresh"] = now_iso()
        self.database.write_json(self.rates_path, snapshot)
        return snapshot

    @staticmethod
    def _is_newer(new_time: str, old_time: str) -> bool:
        """Сравнивает метки времени двух срезов курса."""
        new_moment = parse_iso(new_time)
        old_moment = parse_iso(old_time)
        if new_moment is None:
            return False
        if old_moment is None:
            return True
        return new_moment >= old_moment

    # --- история ----------------------------------------------------------

    def load_history(self) -> list:
        """Читает exchange_rates.json."""
        history = self.database.read_json(self.history_path, [])
        return history if isinstance(history, list) else []

    def append_history(self, entries: list) -> int:
        """Дописывает замеры в историю, пропуская дубликаты по id."""
        history = self.load_history()
        known_ids = {record.get("id") for record in history}
        added = 0
        for entry in entries:
            if entry["id"] in known_ids:
                continue
            history.append(entry)
            known_ids.add(entry["id"])
            added += 1
        if added:
            self.database.write_json(self.history_path, history)
        return added
