from __future__ import annotations

import logging
import sys

from pythonjsonlogger.jsonlogger import JsonFormatter

from app.config import get_settings


def configure_logging() -> None:
    settings = get_settings()
    log_level = getattr(logging, settings.log_level.upper(), logging.INFO)

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter("%(asctime)s %(levelname)s %(name)s %(message)s %(job)s"))

    root = logging.getLogger()
    root.handlers.clear()
    root.setLevel(log_level)
    root.addHandler(handler)
