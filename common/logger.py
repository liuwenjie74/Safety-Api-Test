# -*- coding: utf-8 -*-
"""Logging helpers with token masking."""
from __future__ import annotations

from typing import Any, Mapping
import logging
import re

from config import settings


_TOKEN_PATTERNS = [
    re.compile(r"(token=)([^&\\s]+)", re.IGNORECASE),
    re.compile(r"(authorization:)([^\\n]+)", re.IGNORECASE),
    re.compile(r"(token:)([^\\n]+)", re.IGNORECASE),
]


def mask_value(value: str, visible: int = 4) -> str:
    """Mask a sensitive value while preserving a small prefix and suffix."""
    if not value:
        return value
    if len(value) <= visible * 2:
        return "*" * len(value)
    return value[:visible] + "*" * (len(value) - visible * 2) + value[-visible:]


def mask_headers(headers: Mapping[str, Any]) -> dict:
    """Mask token-like header values before logging or attaching them."""
    masked = dict(headers or {})
    token_key = settings.TOKEN_HEADER.lower()
    for key, value in list(masked.items()):
        if key.lower() == token_key or key.lower() == "authorization":
            masked[key] = mask_value(str(value), settings.MASK_TOKEN_VISIBLE)
    return masked


def mask_message(message: str) -> str:
    """Mask token strings that appear in log messages."""
    result = message
    for pattern in _TOKEN_PATTERNS:
        result = pattern.sub(lambda m: m.group(1) + mask_value(m.group(2)), result)
    return result


class TokenMaskFilter(logging.Filter):
    """Filter that masks token values before records are emitted."""

    def filter(self, record: logging.LogRecord) -> bool:
        try:
            record.msg = mask_message(record.getMessage())
            record.args = ()
        except Exception:
            pass
        return True


def get_logger(name: str = "framework") -> logging.Logger:
    """Return a configured logger with token masking enabled."""
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger

    logger.setLevel(logging.INFO)
    handler = logging.StreamHandler()
    handler.setFormatter(
        logging.Formatter(
            fmt="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
    )
    handler.addFilter(TokenMaskFilter())
    logger.addHandler(handler)
    logger.propagate = False
    return logger
