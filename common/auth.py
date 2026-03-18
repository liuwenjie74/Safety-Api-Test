# -*- coding: utf-8 -*-
"""Login service and token extraction helpers."""
from __future__ import annotations

from typing import Any, Optional
from urllib.parse import urljoin
import json

import requests

from common.context import SessionContext
from common.logger import get_logger, mask_value
from config import settings


def _safe_import_allure() -> Optional[Any]:
    try:
        import allure  # type: ignore

        return allure
    except Exception:
        return None


def _extract_by_path(data: Any, path: str) -> Any:
    """Extract a nested value using dotted paths such as ``data.token``."""
    if not path:
        return None

    current = data
    for part in path.split("."):
        if isinstance(current, dict) and part in current:
            current = current[part]
        else:
            return None
    return current


class AuthService:
    """Encapsulate login requests and token persistence."""

    def __init__(self) -> None:
        self._logger = get_logger(self.__class__.__name__)

    def login(self, context: SessionContext) -> str:
        """Perform the configured login flow and store the token in context."""
        allure = _safe_import_allure()
        step = allure.step if allure else None

        def _do_login() -> str:
            response: Optional[requests.Response] = None
            try:
                response = self.request_login(
                    payload=settings.LOGIN_PAYLOAD,
                    headers=settings.LOGIN_HEADERS,
                    method=settings.LOGIN_METHOD,
                    url=settings.LOGIN_URL,
                    timeout=settings.REQUEST_TIMEOUT,
                    raise_for_status=True,
                )
                try:
                    body = response.json()
                except Exception as exc:
                    raise RuntimeError(f"Login response is not JSON: {response.text}") from exc

                token = _extract_by_path(body, settings.TOKEN_PATH)
                if not token:
                    raise RuntimeError(
                        f"Token was not found in response, path={settings.TOKEN_PATH}"
                    )

                context.set_token(str(token))
                self._logger.info(
                    "Login successful, token=%s",
                    mask_value(str(token), settings.MASK_TOKEN_VISIBLE),
                )
                return str(token)
            except Exception:
                self._attach_login_failure(response)
                raise

        if step:
            with step("登录获取 Token"):
                return _do_login()
        return _do_login()

    def request_login(
        self,
        payload: Optional[Any] = None,
        headers: Optional[dict] = None,
        method: Optional[str] = None,
        url: Optional[str] = None,
        timeout: Optional[float] = None,
        raise_for_status: bool = False,
    ) -> requests.Response:
        """Send a login request for session auth or login testcase validation."""
        request_method = (method or settings.LOGIN_METHOD).upper()
        request_url = url or settings.LOGIN_URL

        if not str(request_url).lower().startswith(("http://", "https://")):
            request_url = urljoin(settings.BASE_URL.rstrip("/") + "/", str(request_url).lstrip("/"))

        request_headers = headers or settings.LOGIN_HEADERS
        request_timeout = timeout or settings.REQUEST_TIMEOUT

        kwargs: dict = {
            "method": request_method,
            "url": request_url,
            "headers": request_headers,
            "timeout": request_timeout,
        }
        if payload is not None:
            if isinstance(payload, (dict, list)):
                kwargs["json"] = payload
            else:
                kwargs["data"] = payload

        response = requests.request(**kwargs)
        if raise_for_status:
            response.raise_for_status()
        return response

    def _attach_login_failure(self, response: Optional[requests.Response]) -> None:
        """Attach login response details to Allure when login fails."""
        allure = _safe_import_allure()
        if allure is None or response is None:
            return

        try:
            allure.attach(
                json.dumps(
                    {
                        "status_code": response.status_code,
                        "headers": dict(response.headers),
                        "body": response.text,
                    },
                    ensure_ascii=False,
                    indent=4,
                ),
                name="login_response_on_fail",
                attachment_type=getattr(allure.attachment_type, "JSON", None),
            )
        except Exception:
            return
