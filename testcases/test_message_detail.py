# -*- coding: utf-8 -*-
"""
示例用例：消息详情查询
- 数据来自 api_cases.xlsx 的 Sheet: test_message_detail
- 不感知登录与 Token 传递。
"""
from __future__ import annotations

from typing import Any, Dict

from base.request_client import RequestClient
from common.assertions import assert_response


def test_message_detail(case: Dict[str, Any], client: RequestClient) -> None:
    """
    YAML 驱动的测试用例示例：
    - case 来自 data/yaml/test_message_detail.yaml
    """
    method = case.get("method", "GET")
    url = case["url"]

    response = client.request(
        method=method,
        url=url,
        headers=case.get("headers"),
        params=case.get("params"),
        json=case.get("json"),
        data=case.get("data"),
    )

    assert_response(case, response)
