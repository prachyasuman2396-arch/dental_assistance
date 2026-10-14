import logging
import sys
from typing import Any, Dict


class SafeLogFilter(logging.Filter):
    """Filter that masks sensitive tokens, API keys, and authorization headers."""
    SENSITIVE_KEYS = ("api_key", "token", "password", "authorization", "secret")

    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.msg, str):
            # Mask potential bearer tokens or generic keys
            for word in record.msg.split():
                if any(k in word.lower() for k in self.SENSITIVE_KEYS) and "=" in word:
                    parts = word.split("=", 1)
                    record.msg = record.msg.replace(word, f"{parts[0]}=***MASKED***")
        return True


def setup_logging(debug: bool = False) -> logging.Logger:
    level = logging.DEBUG if debug else logging.INFO
    logger = logging.getLogger("study_agent")
    logger.setLevel(level)

    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setLevel(level)
        formatter = logging.Formatter(
            fmt="%(asctime)s [%(levelname)s] [%(name)s] %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        handler.setFormatter(formatter)
        handler.addFilter(SafeLogFilter())
        logger.addHandler(handler)

    return logger


logger = setup_logging()
