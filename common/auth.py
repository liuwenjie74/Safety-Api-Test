# -*- coding: utf-8 -*-
"""
登录鉴权模块：
- 登录接口独立封装；
- 从 response.data 中提取 token；
- 存入会话上下文。
"""
from __future__ import annotations

from typing import Any, Optional, Tuple
from urllib.parse import urljoin
import json

import requests

from config import settings
from common.context import SessionContext
from common.logger import get_logger, mask_value


def _safe_import_allure():
    try:
        import allure  # type: ignore

        return allure
    except Exception:
        return None


def _extract_by_path(data: Any, path: str) -> Any:
    """支持 a.b.c 的点路径提取。"""
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
    """登录服务封装。"""

    def __init__(self) -> None:
        self._logger = get_logger(self.__class__.__name__)

    def login(self, context: SessionContext) -> str:
        """
        执行登录并保存 Token。

        :param context: 会话上下文
        :return: Token 字符串
        """
        allure = _safe_import_allure()
        step = allure.step if allure else None

        def _do_login() -> str:
            response = None
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
                    raise RuntimeError(f"登录响应非 JSON：{response.text}") from exc

                token = _extract_by_path(body, settings.TOKEN_PATH)
                if not token:
                    raise RuntimeError(f"未找到 Token，path={settings.TOKEN_PATH}")

                context.set_token(str(token))
                self._logger.info(
                    "登录成功，Token=%s", mask_value(str(token), settings.MASK_TOKEN_VISIBLE)
                )
                return str(token)
            except Exception:
                self._attach_login_failure(response)
                raise

        if step:
            with step("登录获取 Token"):
                return _do_login()
        return _do_login()

    def _attach_login_failure(self, response: Optional[requests.Response]) -> None:
        """登录失败时自动附加请求/响应。"""
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

    def request_login(
        self,
        payload: Optional[Any] = None,
        headers: Optional[dict] = None,
        method: Optional[str] = None,
        url: Optional[str] = None,
        timeout: Optional[float] = None,
        raise_for_status: bool = False,
    ) -> requests.Response:
        """
        发起登录请求（用于登录测试或自定义登录流程）。

        :param payload: 请求体（dict/list 走 json，其他走 data）
        :param headers: 自定义 headers
        :param method: HTTP 方法
        :param url: 登录 URL
        :param timeout: 超时
        :param raise_for_status: 是否抛出 HTTP 错误
        """
        req_method = (method or settings.LOGIN_METHOD).upper()
        req_url = url or settings.LOGIN_URL
        if not str(req_url).lower().startswith(("http://", "https://")):
            base = settings.BASE_URL.rstrip("/") + "/"
            req_url = urljoin(base, str(req_url).lstrip("/"))
        req_headers = headers or settings.LOGIN_HEADERS
        req_timeout = timeout or settings.REQUEST_TIMEOUT

        kwargs: dict = {
            "method": req_method,
            "url": req_url,
            "headers": req_headers,
            "timeout": req_timeout,
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
