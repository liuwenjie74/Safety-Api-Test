# -*- coding: utf-8 -*-
"""Pytest fixtures and hooks for the API automation framework."""
from __future__ import annotations

from typing import Any, Iterable, List, Optional
import json

import pytest
import yaml

from base.request_client import RequestClient
from common.auth import AuthService
from common.context import SessionContext
from data.loader.hot_loader import ensure_yaml_for_test


def _safe_import_allure() -> Optional[Any]:
    try:
        import allure  # type: ignore

        return allure
    except Exception:
        return None


@pytest.fixture(scope="session")
def session_context() -> SessionContext:
    """Provide a session-scoped storage object for token and snapshots."""
    return SessionContext()


@pytest.fixture(scope="session")
def auth_service() -> AuthService:
    """Provide the login service used by session login and login testcases."""
    return AuthService()


@pytest.fixture(scope="session", autouse=True)
def session_login(session_context: SessionContext, auth_service: AuthService) -> None:
    """Login once per pytest session."""
    auth_service.login(session_context)


@pytest.fixture(scope="session")
def client(session_context: SessionContext, auth_service: AuthService) -> Iterable[RequestClient]:
    """Provide the shared request client with 401 refresh enabled."""
    http_client = RequestClient(
        context=session_context,
        auth_service=auth_service,
        max_retry_401=1,
    )
    yield http_client
    http_client.close()


def pytest_generate_tests(metafunc: pytest.Metafunc) -> None:
    """Load testcase data from the YAML file that matches the test function name."""
    fixture_names = list(metafunc.fixturenames)
    if not fixture_names:
        return

    param_name = None
    if "case" in fixture_names:
        param_name = "case"
    elif "data" in fixture_names:
        param_name = "data"
    else:
        return

    yaml_path = ensure_yaml_for_test(metafunc.function.__name__)
    if not yaml_path.exists():
        return

    dataset = yaml.safe_load(yaml_path.read_text(encoding="utf-8")) or []
    if not isinstance(dataset, list):
        raise RuntimeError(f"YAML root must be a list: {yaml_path}")

    ids: List[str] = []
    values: List[Any] = []
    for index, item in enumerate(dataset):
        case_id = None
        if isinstance(item, dict):
            case_id = item.get("id") or item.get("name")
        ids.append(str(case_id) if case_id else f"case_{index}")
        values.append(item)

    metafunc.parametrize(param_name, values, ids=ids)


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item: pytest.Item, call: pytest.CallInfo):
    """Attach the latest request/response snapshot to Allure on test failure."""
    outcome = yield
    report = outcome.get_result()
    if report.when != "call" or not report.failed:
        return

    allure = _safe_import_allure()
    if allure is None:
        return

    try:
        context: SessionContext = item._request.getfixturevalue("session_context")
    except Exception:
        return

    snapshot = context.get_last_snapshot()
    if not snapshot:
        return

    allure.attach(
        json.dumps(snapshot, ensure_ascii=False, indent=4, default=lambda obj: obj.__dict__),
        name="request_response_snapshot",
        attachment_type=getattr(allure.attachment_type, "JSON", None),
    )
