"""Logging configuration for StreamGrab."""

from __future__ import annotations

import logging


LOGGER_NAME = "streamgrab"


def configure_logging(debug: bool = False) -> logging.Logger:
    """Configure and return the application logger."""

    logger = logging.getLogger(LOGGER_NAME)
    logger.setLevel(logging.DEBUG if debug else logging.INFO)
    logger.propagate = False

    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter("%(levelname)s: %(message)s"))
        logger.addHandler(handler)

    return logger

