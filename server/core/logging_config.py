from __future__ import annotations

import logging
import sys

try:
    from pythonjsonlogger.json import JsonFormatter as _JsonFormatter
except ImportError:
    from pythonjsonlogger.jsonlogger import JsonFormatter as _JsonFormatter  # type: ignore[no-redef]

try:
    import colorlog as colorlog
    _HAS_COLORLOG = True
except ImportError:
    colorlog = None  # type: ignore[assignment]
    _HAS_COLORLOG = False

_LEVEL_COLORS = {
    "DEBUG":    "cyan",
    "INFO":     "green",
    "WARNING":  "yellow",
    "ERROR":    "red",
    "CRITICAL": "bold_red",
}

_COLOR_FMT = (
    "%(log_color)s%(levelname)-8s%(reset)s "
    "%(blue)s%(name)s%(reset)s "
    "%(message)s"
)


def configure_logging() -> None:
    handler = logging.StreamHandler(sys.stdout)

    if sys.stdout.isatty() and _HAS_COLORLOG:
        # Local dev — colored human-readable output
        formatter = colorlog.ColoredFormatter(  # type: ignore[union-attr]
            _COLOR_FMT,
            log_colors=_LEVEL_COLORS,
            reset=True,
            style="%",
        )
    else:
        # Deployed (Render, CI) — structured JSON for log aggregators
        formatter = _JsonFormatter(
            fmt="%(asctime)s %(levelname)s %(name)s %(message)s",
            datefmt="%Y-%m-%dT%H:%M:%SZ",
        )

    handler.setFormatter(formatter)
    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(logging.INFO)
    # Suppress INFO chatter from HTTP client libraries — their retry/redirect
    # logs drown out application-level events in production aggregators.
    logging.getLogger("gspread").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
