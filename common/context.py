# -*- coding: utf-8 -*-
"""
会话上下文：
- 负责保存与获取 Token；
- 避免使用全局变量；
- 线程安全。
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional
import threading


@dataclass
class RequestSnapshot:
    """请求快照（用于失败时附件）。"""

    method: str
    url: str
    headers: Dict[str, Any]
    params: Dict[str, Any]
    json: Any
    data: Any


@dataclass
class ResponseSnapshot:
    """响应快照（用于失败时附件）。"""

    status_code: int
    headers: Dict[str, Any]
    body: Any


class SessionContext:
    """
    会话上下文（Session 级别）：
    - 保存 Token；
    - 保存最近一次请求与响应快照。
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._store: Dict[str, Any] = {}

    def set_token(self, token: str) -> None:
        """保存 Token。"""
        with self._lock:
            self._store["token"] = token

    def get_token(self) -> Optional[str]:
        """获取 Token。"""
        with self._lock:
            return self._store.get("token")

    def clear_token(self) -> None:
        """清理 Token。"""
        with self._lock:
            self._store.pop("token", None)

    def set_last_snapshot(
        self, request: RequestSnapshot, response: Optional[ResponseSnapshot]
    ) -> None:
        """保存最近一次请求/响应快照。"""
        with self._lock:
            self._store["last_request"] = request
            self._store["last_response"] = response

    def get_last_snapshot(
        self,
    ) -> Optional[Dict[str, Any]]:
        """获取最近一次请求/响应快照。"""
        with self._lock:
            req = self._store.get("last_request")
            resp = self._store.get("last_response")
            if not req:
                return None
            return {"request": req, "response": resp}
