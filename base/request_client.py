# -*- coding: utf-8 -*-
"""
Requests 二次封装：
- 自动注入 Token（来自 SessionContext）；
- 失败时自动附加请求/响应到 Allure；
- 维护最后一次请求/响应快照用于失败分析。
"""
from __future__ import annotations

from typing import Any, Dict, Optional
import json
from urllib.parse import urljoin

import requests

from config import settings
from common.context import SessionContext, RequestSnapshot, ResponseSnapshot
from common.logger import get_logger, mask_headers


def _safe_import_allure():
    try:
        import allure  # type: ignore

        return allure
    except Exception:
        return None


class RequestClient:
    """HTTP 请求客户端（自动携带 Token）。"""

    def __init__(
        self,
        context: SessionContext,
        base_url: Optional[str] = None,
        token_header: Optional[str] = None,
        token_prefix: Optional[str] = None,
        timeout: Optional[float] = None,
        attach_on_fail: bool = True,
    ) -> None:
        self._context = context
        self._session = requests.Session()
        self._base_url = base_url or settings.BASE_URL
        self._token_header = token_header or settings.TOKEN_HEADER
        self._token_prefix = token_prefix if token_prefix is not None else settings.TOKEN_PREFIX
        self._timeout = timeout or settings.REQUEST_TIMEOUT
        self._attach_on_fail = attach_on_fail
        self._logger = get_logger(self.__class__.__name__)

    def request(self, method: str, url: str, **kwargs: Any) -> requests.Response:
        """
        发送请求并自动注入 Token。

        :param method: HTTP 方法
        :param url: 绝对或相对路径
        :param kwargs: 原生 requests 参数
        """
        full_url = self._join_url(url)
        headers = dict(kwargs.get("headers") or {})
        self._inject_token(headers)
        kwargs["headers"] = headers
        kwargs.setdefault("timeout", self._timeout)

        request_snapshot = RequestSnapshot(
            method=method.upper(),
            url=full_url,
            headers=mask_headers(headers),
            params=dict(kwargs.get("params") or {}),
            json=self._safe_value(kwargs.get("json")),
            data=self._safe_value(kwargs.get("data")),
        )

        try:
            response = self._session.request(method=method, url=full_url, **kwargs)
            response_snapshot = ResponseSnapshot(
                status_code=response.status_code,
                headers=mask_headers(response.headers),
                body=self._safe_value(self._safe_response_body(response)),
            )
            self._context.set_last_snapshot(request_snapshot, response_snapshot)

            if self._attach_on_fail and not response.ok:
                self._attach_failure(request_snapshot, response_snapshot)
            return response
        except Exception as exc:
            self._context.set_last_snapshot(request_snapshot, None)
            if self._attach_on_fail:
                self._attach_exception(request_snapshot, exc)
            raise

    def get(self, url: str, **kwargs: Any) -> requests.Response:
        """GET 请求。"""
        return self.request("GET", url, **kwargs)

    def post(self, url: str, **kwargs: Any) -> requests.Response:
        """POST 请求。"""
        return self.request("POST", url, **kwargs)

    def close(self) -> None:
        """关闭底层 Session。"""
        self._session.close()

    # ------------------------- 内部方法 -------------------------

    def _join_url(self, url: str) -> str:
        if url.lower().startswith(("http://", "https://")):
            return url
        return urljoin(self._base_url.rstrip("/") + "/", url.lstrip("/"))

    def _inject_token(self, headers: Dict[str, Any]) -> None:
        token = self._context.get_token()
        if not token:
            self._logger.warning("Token 未初始化，当前请求不携带 Token。")
            return
        value = f"{self._token_prefix}{token}" if self._token_prefix else token
        headers[self._token_header] = value

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
        """将不可序列化对象转换为字符串，避免附件序列化失败。"""
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
