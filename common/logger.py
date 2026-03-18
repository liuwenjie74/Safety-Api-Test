# -*- coding: utf-8 -*-
"""
日志工具：
- 全局 logger 获取；
- Token 脱敏过滤；
- 避免明文输出敏感信息。
"""
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
    """对敏感值进行脱敏，仅保留前后可见位。"""
    if not value:
        return value
    if len(value) <= visible * 2:
        return "*" * len(value)
    return value[:visible] + "*" * (len(value) - visible * 2) + value[-visible:]


def mask_headers(headers: Mapping[str, Any]) -> dict:
    """脱敏 Header 中的 Token 信息。"""
    masked = dict(headers or {})
    token_key = settings.TOKEN_HEADER.lower()
    for key, value in list(masked.items()):
        if key.lower() == token_key or key.lower() == "authorization":
            masked[key] = mask_value(str(value), settings.MASK_TOKEN_VISIBLE)
    return masked


def mask_message(message: str) -> str:
    """对字符串中的 token/authorization 进行脱敏处理。"""
    result = message
    for pattern in _TOKEN_PATTERNS:
        result = pattern.sub(lambda m: m.group(1) + mask_value(m.group(2)), result)
    return result


class TokenMaskFilter(logging.Filter):
    """日志脱敏过滤器。"""

    def filter(self, record: logging.LogRecord) -> bool:
        try:
            msg = record.getMessage()
            record.msg = mask_message(msg)
            record.args = ()
        except Exception:
            # 失败时不影响日志输出
            pass
        return True


def get_logger(name: str = "framework") -> logging.Logger:
    """
    获取统一 logger：
    - 自动安装 Token 脱敏过滤器；
    - 控制台输出。
    """
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger

    logger.setLevel(logging.INFO)
    handler = logging.StreamHandler()
    formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    handler.setFormatter(formatter)
    handler.addFilter(TokenMaskFilter())
    logger.addHandler(handler)
    logger.propagate = False
    return logger
