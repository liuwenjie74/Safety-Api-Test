# -*- coding: utf-8 -*-
"""
登录接口测试：
- 使用 AuthService 直接发起登录请求；
- 支持从 Excel/YAML 驱动断言。
"""
from __future__ import annotations

from typing import Any, Dict

from common.auth import AuthService
from common.assertions import assert_response
from config import settings


def _as_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    return str(value).strip().lower() in {"1", "true", "yes", "y", "on"}


def test_login(case: Dict[str, Any], auth_service: AuthService) -> None:
    """
    登录接口测试示例：
    - case 来自 data/yaml/test_login.yaml
    """
    use_settings = _as_bool(case.get("use_settings_login", True))
    method = case.get("method", settings.LOGIN_METHOD)
    url = case.get("url", settings.LOGIN_URL)

    if use_settings:
        payload = settings.LOGIN_PAYLOAD
        headers = settings.LOGIN_HEADERS
    else:
        payload = case.get("json") or case.get("data")
        headers = case.get("headers") or settings.LOGIN_HEADERS

    response = auth_service.request_login(
        payload=payload,
        headers=headers,
        method=method,
        url=url,
        raise_for_status=False,
    )

    assert_response(case, response)
