"""Планировщик: периодически запускает обновление курсов.

Запуск вручную:
    python -m valutatrade_hub.parser_service.scheduler 300
"""

import sys
import time

from valutatrade_hub.logging_config import PARSER_LOGGER, get_logger
from valutatrade_hub.parser_service.updater import build_updater

DEFAULT_INTERVAL_SECONDS = 300


def run_scheduler(interval_seconds: int = DEFAULT_INTERVAL_SECONDS, iterations: int | None = None):
    """Обновляет курсы каждые interval_seconds секунд.

    iterations=None - работать до Ctrl+C, иначе сделать столько кругов.
    """
    logger = get_logger(PARSER_LOGGER)
    logger.info("Планировщик запущен с интервалом %s с", interval_seconds)
    updater = build_updater()
    done = 0
    try:
        while iterations is None or done < iterations:
            report = updater.run_update()
            print(
                f"[{report['last_refresh']}] обновлено курсов: {report['updated']}, "
                f"ошибок: {len(report['errors'])}"
            )
            done += 1
            if iterations is not None and done >= iterations:
                break
            time.sleep(interval_seconds)
    except KeyboardInterrupt:
        logger.info("Планировщик остановлен пользователем")
        print("\nПланировщик остановлен")
    return done


def main() -> int:
    """Точка входа планировщика: первым аргументом можно задать интервал."""
    interval = DEFAULT_INTERVAL_SECONDS
    if len(sys.argv) > 1:
        try:
            interval = int(sys.argv[1])
        except ValueError:
            print("Интервал должен быть числом секунд")
            return 1
    run_scheduler(interval)
    return 0


if __name__ == "__main__":
    sys.exit(main())
