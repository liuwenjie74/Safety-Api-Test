# -*- coding: utf-8 -*-
"""
断言模板化引擎：
- 支持从 YAML 中读取断言规则；
- 提供多种断言类型（状态码、JSON 路径、包含、长度等）。
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional
import json
import re

import requests


_PATH_TOKEN_RE = re.compile(r"[^.\[\]]+|\[\d+\]")
_MISSING = object()


def _extract_by_path(data: Any, path: str) -> Any:
    """
    支持 a.b.c 与 a[0].b 的路径提取。
    """
    if not path:
        return _MISSING
    current = data
    tokens = _PATH_TOKEN_RE.findall(path)
    if not tokens:
        return _MISSING
    for token in tokens:
        if token.startswith("[") and token.endswith("]"):
            if not isinstance(current, list):
                return _MISSING
            idx = int(token[1:-1])
            if idx < 0 or idx >= len(current):
                return _MISSING
            current = current[idx]
            continue

        key = token
        if isinstance(current, dict) and key in current:
            current = current[key]
        else:
            return _MISSING
    return current


def _response_body(response: requests.Response) -> Any:
    try:
        return response.json()
    except Exception:
        return response.text


def build_assertions(case: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    构建断言规则：
    - 若 case.asserts 存在且为 list，优先使用；
    - 否则根据 expected_status / expected_code 自动生成默认断言。
    """
    rules = case.get("asserts")
    if isinstance(rules, list):
        return rules

    defaults: List[Dict[str, Any]] = []
    if "expected_status" in case:
        defaults.append({"type": "status_code", "expected": case.get("expected_status")})
    if "expected_code" in case:
        defaults.append(
            {"type": "json_path_eq", "path": "code", "expected": case.get("expected_code")}
        )
    return defaults


def assert_response(case: Dict[str, Any], response: requests.Response) -> None:
    """
    执行断言规则。

    :param case: 用例数据（来自 YAML）
    :param response: HTTP 响应
    """
    rules = build_assertions(case)
    if not rules:
        return

    body = _response_body(response)

    for idx, rule in enumerate(rules):
        rtype = (rule.get("type") or "").strip()
        expected = rule.get("expected")
        path = rule.get("path")

        if rtype == "status_code":
            assert (
                response.status_code == expected
            ), f"[rule#{idx}] status_code 期望={expected} 实际={response.status_code}"
            continue

        if rtype == "json_path_eq":
            value = _extract_by_path(body, path)
            assert (
                value is not _MISSING
            ), f"[rule#{idx}] JSON 路径不存在：{path}"
            assert value == expected, f"[rule#{idx}] {path} 期望={expected} 实际={value}"
            continue

        if rtype == "json_path_ne":
            value = _extract_by_path(body, path)
            assert value is not _MISSING, f"[rule#{idx}] JSON 路径不存在：{path}"
            assert value != expected, f"[rule#{idx}] {path} 不应等于 {expected}"
            continue

        if rtype == "json_path_contains":
            value = _extract_by_path(body, path)
            assert value is not _MISSING, f"[rule#{idx}] JSON 路径不存在：{path}"
            assert expected in value, f"[rule#{idx}] {path} 不包含 {expected}"
            continue

        if rtype == "json_path_in":
            value = _extract_by_path(body, path)
            assert value is not _MISSING, f"[rule#{idx}] JSON 路径不存在：{path}"
            assert value in expected, f"[rule#{idx}] {path}={value} 不在 {expected}"
            continue

        if rtype == "exists":
            value = _extract_by_path(body, path)
            assert value is not _MISSING, f"[rule#{idx}] JSON 路径不存在：{path}"
            continue

        if rtype == "not_exists":
            value = _extract_by_path(body, path)
            assert value is _MISSING, f"[rule#{idx}] JSON 路径应不存在：{path}"
            continue

        if rtype == "length_eq":
            value = _extract_by_path(body, path)
            assert value is not _MISSING, f"[rule#{idx}] JSON 路径不存在：{path}"
            assert hasattr(value, "__len__"), f"[rule#{idx}] {path} 不可计算长度"
            assert len(value) == expected, f"[rule#{idx}] {path} 长度期望={expected} 实际={len(value)}"
            continue

        if rtype == "body_contains":
            text = body
            if not isinstance(text, str):
                text = json.dumps(text, ensure_ascii=False)
            assert expected in text, f"[rule#{idx}] body 不包含 {expected}"
            continue

        raise AssertionError(f"[rule#{idx}] 未支持的断言类型：{rtype}")
