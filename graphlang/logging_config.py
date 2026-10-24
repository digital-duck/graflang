"""GraphLang's logging: the `graflang` logger tree on top of dd-logging.

    from graphlang.logging_config import get_logger, log_event
    _log = get_logger("grafr.runtime")            # -> graflang.grafr.runtime

`setup_logging` (called by `graf run`) writes `<log_dir>/<run_name>-<adapter>-<timestamp>.log` and/or `.jsonl`.
Until it is called every logger is silent, so using the runtime as a library logs nothing.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, Optional

from dd_logging import ProjectLogging

DEBUG, INFO, WARNING, ERROR = logging.DEBUG, logging.INFO, logging.WARNING, logging.ERROR
ROOT = "graflang"
_pl = ProjectLogging(ROOT)

get_logger = _pl.get_logger
log_event = _pl.log_event
_active: Dict[str, Any] = {}          # what the last setup_logging chose, so procedure runs can log alongside


def setup_logging(run_name: str, **kw: Any) -> Path:
    """Start file logging for this process (see dd_logging.setup_logging for the keywords)."""
    path = _pl.setup_logging(run_name, **kw)
    _active.clear()
    _active.update(log_dir=path.parent, log_level=kw.get("log_level"), log_format=kw.get("log_format"))
    return path


def disable_logging() -> None:
    _active.clear()
    _pl.disable_logging()


def active_settings() -> Optional[Dict[str, Any]]:
    """The log_dir/log_level/log_format passed to the last `setup_logging`, or None when logging is off."""
    return dict(_active) if _active else None
