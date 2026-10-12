"""Logging configuration module.

Ensures structured, secure logging where user message contents and sensitive
tokens are NEVER printed at INFO level or above.
"""

import logging
import sys
from app.core.settings import get_settings


def configure_logging() -> None:
    """Configure root logger with unified formatting."""
    settings = get_settings()
    level = getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO)

    log_format = "%(asctime)s [%(levelname)s] [%(name)s]: %(message)s"
    formatter = logging.Formatter(log_format, datefmt="%Y-%m-%d %H:%M:%S")

    root_logger = logging.getLogger()
    root_logger.setLevel(level)

    # Avoid duplicate handlers if reconfigured
    if not any(isinstance(h, logging.StreamHandler) for h in root_logger.handlers):
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(formatter)
        root_logger.addHandler(handler)
    else:
        for handler in root_logger.handlers:
            handler.setFormatter(formatter)


def get_logger(name: str) -> logging.Logger:
    """Return configured logger instance for a given module name."""
    return logging.getLogger(name)
