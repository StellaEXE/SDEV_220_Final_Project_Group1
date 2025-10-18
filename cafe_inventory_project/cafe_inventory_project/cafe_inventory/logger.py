"""
logger.py
---------
Project-wide logging (rotating file).
"""
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

_LOGGER = None

def get_logger(name: str = "cafe") -> logging.Logger:
    global _LOGGER
    if _LOGGER:
        return _LOGGER
    log_dir = Path("./logs")
    log_dir.mkdir(parents=True, exist_ok=True)
    handler = RotatingFileHandler(log_dir / "app.log", maxBytes=512_000, backupCount=3)
    fmt = logging.Formatter("%(asctime)s | %(levelname)s | %(message)s")
    handler.setFormatter(fmt)

    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)
    logger.addHandler(handler)
    # Don’t duplicate to root logger
    logger.propagate = False

    _LOGGER = logger
    return logger
