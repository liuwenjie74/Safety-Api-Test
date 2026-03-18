# -*- coding: utf-8 -*-
"""Requests facade with automatic token injection and 401 retry support."""
from __future__ import annotations

from typing import Any, Dict, Optional
from urllib.parse import urljoin
import json
import threading

import requests

from common.auth import AuthService
from common.context import RequestSnapshot, ResponseSnapshot, SessionContext
from common.logger import get_logger, mask_headers
from config import settings


def _safe_import_allure() -> Optional[Any]:
    try:
        import allure  # type: ignore

        return allure
    except Exception:
        return None


class RequestClient:
    """HTTP client that automatically injects the current session token."""

    _refresh_lock = threading.Lock()

    def __init__(
        self,
        context: SessionContext,
        base_url: Optional[str] = None,
        token_header: Optional[str] = None,
        token_prefix: Optional[str] = None,
        timeout: Optional[float] = None,
        attach_on_fail: bool = True,
        auth_service: Optional[AuthService] = None,
        max_retry_401: int = 1,
    ) -> None:
        self._context = context
        self._session = requests.Session()
        self._base_url = base_url or settings.BASE_URL
        self._token_header = token_header or settings.TOKEN_HEADER
        self._token_prefix = token_prefix if token_prefix is not None else settings.TOKEN_PREFIX
        self._timeout = timeout or settings.REQUEST_TIMEOUT
        self._attach_on_fail = attach_on_fail
        self._auth_service = auth_service
        self._max_retry_401 = max_retry_401
        self._logger = get_logger(self.__class__.__name__)

    def request(self, method: str, url: str, **kwargs: Any) -> requests.Response:
        """Send a request, inject the token, and retry once on 401 if enabled."""
        full_url = self._join_url(url)
        base_kwargs = dict(kwargs)
        base_kwargs.setdefault("timeout", self._timeout)

        retries = 0
        while True:
            stale_token = self._context.get_token()
            headers = dict(base_kwargs.get("headers") or {})
            self._inject_token(headers, stale_token)

            attempt_kwargs = dict(base_kwargs)
            attempt_kwargs["headers"] = headers

            request_snapshot = RequestSnapshot(
                method=method.upper(),
                url=full_url,
                headers=mask_headers(headers),
                params=dict(attempt_kwargs.get("params") or {}),
                json=self._safe_value(attempt_kwargs.get("json")),
                data=self._safe_value(attempt_kwargs.get("data")),
            )

            try:
                response = self._session.request(method=method, url=full_url, **attempt_kwargs)
                response_snapshot = ResponseSnapshot(
                    status_code=response.status_code,
                    headers=mask_headers(response.headers),
                    body=self._safe_value(self._safe_response_body(response)),
                )
                self._context.set_last_snapshot(request_snapshot, response_snapshot)

                if (
                    response.status_code == 401
                    and self._auth_service is not None
                    and retries < self._max_retry_401
                    and self._is_replayable(base_kwargs)
                ):
                    self._logger.warning("Received 401, refreshing token and retrying request.")
                    self._refresh_token(stale_token)
                    retries += 1
                    continue

                if self._attach_on_fail and not response.ok:
                    self._attach_failure(request_snapshot, response_snapshot)
                return response
            except Exception as exc:
                self._context.set_last_snapshot(request_snapshot, None)
                if self._attach_on_fail:
                    self._attach_exception(request_snapshot, exc)
                raise

    def get(self, url: str, **kwargs: Any) -> requests.Response:
        """Send a GET request."""
        return self.request("GET", url, **kwargs)

    def post(self, url: str, **kwargs: Any) -> requests.Response:
        """Send a POST request."""
        return self.request("POST", url, **kwargs)

    def close(self) -> None:
        """Close the underlying session."""
        self._session.close()

    def _join_url(self, url: str) -> str:
        if url.lower().startswith(("http://", "https://")):
            return url
        return urljoin(self._base_url.rstrip("/") + "/", url.lstrip("/"))

    def _inject_token(self, headers: Dict[str, Any], token: Optional[str]) -> None:
        if not token:
            self._logger.warning("Token is not initialized; request will be sent without it.")
            return
        headers[self._token_header] = (
            f"{self._token_prefix}{token}" if self._token_prefix else token
        )

    def _refresh_token(self, stale_token: Optional[str]) -> None:
        """
        Refresh the token after a 401 response.

        If another thread has already replaced the token while the current thread
        was waiting on the refresh lock, the second login is skipped.
        """
        if self._auth_service is None:
            return

        with self._refresh_lock:
            current_token = self._context.get_token()
            if current_token and current_token != stale_token:
                return
            self._auth_service.login(self._context)

    def _safe_response_body(self, response: requests.Response) -> Any:
        try:
            return response.json()
        except Exception:
            return response.text

    def _attach_failure(self, req: RequestSnapshot, resp: ResponseSnapshot) -> None:
        allure = _safe_import_allure()
        if allure is None:
            return

        allure.attach(
            json.dumps(req.__dict__, ensure_ascii=False, indent=4, default=str),
            name="request_on_fail",
            attachment_type=getattr(allure.attachment_type, "JSON", None),
        )
        allure.attach(
            json.dumps(resp.__dict__, ensure_ascii=False, indent=4, default=str),
            name="response_on_fail",
            attachment_type=getattr(allure.attachment_type, "JSON", None),
        )

    def _attach_exception(self, req: RequestSnapshot, exc: Exception) -> None:
        allure = _safe_import_allure()
        if allure is None:
            return

        allure.attach(
            json.dumps(req.__dict__, ensure_ascii=False, indent=4, default=str),
            name="request_on_exception",
            attachment_type=getattr(allure.attachment_type, "JSON", None),
        )
        allure.attach(
            f"{type(exc).__name__}: {exc}",
            name="exception",
            attachment_type=getattr(allure.attachment_type, "TEXT", None),
        )

    def _safe_value(self, value: Any) -> Any:
        """Convert non-serializable values into readable strings."""
        if value is None:
            return None
        if isinstance(value, (str, int, float, bool, dict, list)):
            return value
        if isinstance(value, (bytes, bytearray)):
            try:
                return value.decode("utf-8", errors="ignore")
            except Exception:
                return repr(value)
        return repr(value)

    def _is_replayable(self, base_kwargs: Dict[str, Any]) -> bool:
        """Return whether the request body can be safely replayed."""
        if base_kwargs.get("files") is not None:
            return False

        data = base_kwargs.get("data")
        if data is None:
            return True
        if hasattr(data, "read"):
            return False
        if hasattr(data, "__iter__") and not isinstance(
            data, (dict, list, tuple, str, bytes, bytearray)
        ):
            return False
        return True
