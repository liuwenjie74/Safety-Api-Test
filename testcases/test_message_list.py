# -*- coding: utf-8 -*-
"""
Auto-generated testcase: test_message_list
- Data source: data/yaml/test_message_list.yaml
"""
from __future__ import annotations

from typing import Any, Dict

from base.request_client import RequestClient
from common.assertions import assert_response


def test_message_list(case: Dict[str, Any], client: RequestClient) -> None:
    """Run the API testcase described in the matching YAML file."""
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
