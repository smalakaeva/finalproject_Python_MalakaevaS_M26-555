"""Обновление курсов: опрос всех клиентов и сохранение результата."""

import time
from pathlib import Path

from valutatrade_hub.core.exceptions import ApiRequestError
from valutatrade_hub.core.utils import now_iso
from valutatrade_hub.infra.settings import SettingsLoader
from valutatrade_hub.logging_config import PARSER_LOGGER, get_logger
from valutatrade_hub.parser_service.api_clients import build_clients
from valutatrade_hub.parser_service.config import ParserConfig
from valutatrade_hub.parser_service.storage import RatesStorage, make_history_entry


def short_path(full_path: str) -> str:
    """Короткий путь к файлу относительно корня проекта (для сообщений)."""
    path = Path(full_path)
    try:
        return str(path.relative_to(SettingsLoader().project_root))
    except ValueError:
        return str(path)


class RatesUpdater:
    """Координатор обновления курсов.

    Опрашивает все API-клиенты, объединяет результаты и передаёт их в
    хранилище. Если один клиент упал - остальные всё равно отработают.
    """

    def __init__(self, clients: list, storage: RatesStorage, config: ParserConfig | None = None):
        self.clients = clients
        self.storage = storage
        self.config = config or ParserConfig()
        self.logger = get_logger(PARSER_LOGGER)

    def run_update(self) -> dict:
        """Запускает обновление и возвращает отчёт о проделанной работе."""
        self.logger.info("Старт обновления курсов")
        report = {
            "sources": [],
            "errors": [],
            "updated": 0,
            "history_added": 0,
            "last_refresh": None,
            "rates_file": short_path(self.config.RATES_FILE_PATH),
        }

        collected = {}
        history_entries = []

        for client in self.clients:
            started = time.time()
            try:
                rates = client.fetch_rates()
            except ApiRequestError as error:
                self.logger.error("Источник %s не ответил: %s", client.source_name, error)
                report["errors"].append({"source": client.source_name, "message": str(error)})
                report["sources"].append(
                    {"source": client.source_name, "ok": False, "count": 0, "error": str(error)}
                )
                continue

            timestamp = now_iso()
            for pair, rate in rates.items():
                from_code, to_code = pair.split("_")
                collected[pair] = {
                    "rate": rate,
                    "updated_at": timestamp,
                    "source": client.source_name,
                }
                meta = dict(client.last_meta)
                meta["raw_id"] = self.config.CRYPTO_ID_MAP.get(from_code, from_code.lower())
                history_entries.append(
                    make_history_entry(
                        from_code, to_code, rate, timestamp, client.source_name, meta
                    )
                )

            elapsed_ms = int((time.time() - started) * 1000)
            self.logger.info(
                "Источник %s вернул курсов: %s (за %s мс)",
                client.source_name,
                len(rates),
                elapsed_ms,
            )
            report["sources"].append(
                {"source": client.source_name, "ok": True, "count": len(rates), "error": None}
            )

        if collected:
            snapshot = self.storage.save_snapshot(collected)
            report["history_added"] = self.storage.append_history(history_entries)
            report["updated"] = len(collected)
            report["last_refresh"] = snapshot.get("last_refresh")
            self.logger.info("Записано курсов: %s в файл %s", len(collected), report["rates_file"])
        else:
            self.logger.error("Обновление завершено без данных")

        return report


def build_updater(source: str | None = None) -> RatesUpdater:
    """Собирает RatesUpdater с нужными клиентами (фабрика для CLI)."""
    config = ParserConfig()
    clients = build_clients(source, config)
    return RatesUpdater(clients, RatesStorage(config), config)
