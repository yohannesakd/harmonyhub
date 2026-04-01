from __future__ import annotations

import logging
import signal
import time

from app.config import get_settings
from app.jobs import build_scheduler
from app.logging import configure_logging

configure_logging()
logger = logging.getLogger(__name__)


def run() -> None:
    settings = get_settings()
    scheduler = build_scheduler(settings)
    scheduler.start()
    logger.info("Worker scheduler started", extra={"job": "scheduler"})

    running = True

    def _stop(*_: object) -> None:
        nonlocal running
        running = False

    signal.signal(signal.SIGINT, _stop)
    signal.signal(signal.SIGTERM, _stop)

    while running:
        time.sleep(1)

    scheduler.shutdown(wait=False)
    logger.info("Worker scheduler stopped", extra={"job": "scheduler"})


if __name__ == "__main__":
    run()
