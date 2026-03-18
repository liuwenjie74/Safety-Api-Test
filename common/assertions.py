# -*- coding: utf-8 -*-
"""Assertion helpers driven by Excel/YAML rule definitions."""
from __future__ import annotations

from typing import Any, Dict, List
import json
import re

import requests


_PATH_TOKEN_RE = re.compile(r"[^.\[\]]+|\[\d+\]")
_MISSING = object()


def _extract_by_path(data: Any, path: str) -> Any:
    """Extract values from objects using paths like ``a.b[0].c``."""
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
            index = int(token[1:-1])
            if index < 0 or index >= len(current):
                return _MISSING
            current = current[index]
            continue

        if isinstance(current, dict) and token in current:
            current = current[token]
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
    Return assertion rules for a testcase.

    If ``case["asserts"]`` exists and is a list, it is used directly. Otherwise
    default rules are built from ``expected_status`` and ``expected_code``.
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
    """Execute all configured assertion rules against a response object."""
    rules = build_assertions(case)
    if not rules:
        return

    body = _response_body(response)

    for index, rule in enumerate(rules):
        rule_type = str(rule.get("type") or "").strip()
        expected = rule.get("expected")
        path = rule.get("path")

        if rule_type == "status_code":
            assert (
                response.status_code == expected
            ), f"[rule#{index}] expected status_code={expected}, actual={response.status_code}"
            continue

        if rule_type == "json_path_eq":
            value = _extract_by_path(body, path)
            assert value is not _MISSING, f"[rule#{index}] JSON path not found: {path}"
            assert value == expected, f"[rule#{index}] expected {path}={expected}, actual={value}"
            continue

        if rule_type == "json_path_ne":
            value = _extract_by_path(body, path)
            assert value is not _MISSING, f"[rule#{index}] JSON path not found: {path}"
            assert value != expected, f"[rule#{index}] expected {path}!={expected}"
            continue

        if rule_type == "json_path_contains":
            value = _extract_by_path(body, path)
            assert value is not _MISSING, f"[rule#{index}] JSON path not found: {path}"
            assert expected in value, f"[rule#{index}] {path} does not contain {expected}"
            continue

        if rule_type == "json_path_in":
            value = _extract_by_path(body, path)
            assert value is not _MISSING, f"[rule#{index}] JSON path not found: {path}"
            assert value in expected, f"[rule#{index}] {path}={value} is not in {expected}"
            continue

        if rule_type == "exists":
            value = _extract_by_path(body, path)
            assert value is not _MISSING, f"[rule#{index}] JSON path not found: {path}"
            continue

        if rule_type == "not_exists":
            value = _extract_by_path(body, path)
            assert value is _MISSING, f"[rule#{index}] JSON path should not exist: {path}"
            continue

        if rule_type == "length_eq":
            value = _extract_by_path(body, path)
            assert value is not _MISSING, f"[rule#{index}] JSON path not found: {path}"
            assert hasattr(value, "__len__"), f"[rule#{index}] {path} has no length"
            assert len(value) == expected, (
                f"[rule#{index}] expected len({path})={expected}, actual={len(value)}"
            )
            continue

        if rule_type == "body_contains":
            text = body if isinstance(body, str) else json.dumps(body, ensure_ascii=False)
            assert expected in text, f"[rule#{index}] body does not contain {expected}"
            continue

        raise AssertionError(f"[rule#{index}] unsupported assertion type: {rule_type}")
