from __future__ import annotations

import logging
import sys

try:
    from pythonjsonlogger.json import JsonFormatter as _JsonFormatter
except ImportError:
    from pythonjsonlogger.jsonlogger import JsonFormatter as _JsonFormatter  # type: ignore[no-redef]


def configure_logging() -> None:
    """Configure root logger to emit structured JSON to stdout."""
    handler = logging.StreamHandler(sys.stdout)
    formatter = _JsonFormatter(
        fmt="%(asctime)s %(levelname)s %(name)s %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%SZ",
    )
    handler.setFormatter(formatter)
    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(logging.INFO)
    logging.getLogger("gspread").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
