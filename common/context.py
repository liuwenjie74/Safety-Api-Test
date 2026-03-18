# -*- coding: utf-8 -*-
"""Session-scoped context for token storage and request snapshots."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional
import threading


@dataclass
class RequestSnapshot:
    """Serializable request data used for failure attachments."""

    method: str
    url: str
    headers: Dict[str, Any]
    params: Dict[str, Any]
    json: Any
    data: Any


@dataclass
class ResponseSnapshot:
    """Serializable response data used for failure attachments."""

    status_code: int
    headers: Dict[str, Any]
    body: Any


class SessionContext:
    """Thread-safe session context shared by all testcases."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._store: Dict[str, Any] = {}

    def set_token(self, token: str) -> None:
        """Store the current token."""
        with self._lock:
            self._store["token"] = token

    def get_token(self) -> Optional[str]:
        """Return the current token if it exists."""
        with self._lock:
            return self._store.get("token")

    def clear_token(self) -> None:
        """Clear the current token."""
        with self._lock:
            self._store.pop("token", None)

    def set_last_snapshot(
        self,
        request: RequestSnapshot,
        response: Optional[ResponseSnapshot],
    ) -> None:
        """Store the latest request and response snapshots."""
        with self._lock:
            self._store["last_request"] = request
            self._store["last_response"] = response

    def get_last_snapshot(self) -> Optional[Dict[str, Any]]:
        """Return the latest request and response snapshots."""
        with self._lock:
            request = self._store.get("last_request")
            response = self._store.get("last_response")
            if not request:
                return None
            return {"request": request, "response": response}
