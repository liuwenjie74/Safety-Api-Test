# -*- coding: utf-8 -*-
"""
Pytest 全局配置：
- Session 级登录一次；
- RequestClient 全局注入；
- YAML 动态参数化；
- 失败时 Allure 自动附加请求/响应快照。
"""
from __future__ import annotations

from typing import Any, Iterable, List
import json

import pytest
import yaml

from common.auth import AuthService
from common.context import SessionContext
from base.request_client import RequestClient
from data.loader.hot_loader import ensure_yaml_for_test


def _safe_import_allure():
    try:
        import allure  # type: ignore

        return allure
    except Exception:
        return None


@pytest.fixture(scope="session")
def session_context() -> SessionContext:
    """会话上下文（保存 Token 和快照）。"""
    return SessionContext()


@pytest.fixture(scope="session")
def auth_service() -> AuthService:
    """登录服务实例。"""
    return AuthService()


@pytest.fixture(scope="session", autouse=True)
def session_login(session_context: SessionContext, auth_service: AuthService) -> None:
    """
    Session 级别登录，只执行一次。
    禁止在 import 阶段调用。
    """
    auth_service.login(session_context)


@pytest.fixture(scope="session")
def client(session_context: SessionContext, auth_service: AuthService) -> Iterable[RequestClient]:
    """注入 RequestClient。"""
    c = RequestClient(context=session_context, auth_service=auth_service, max_retry_401=1)
    yield c
    c.close()


def pytest_generate_tests(metafunc: pytest.Metafunc) -> None:
    """
    根据 Excel 同步生成的 YAML 动态注入参数。
    YAML 路径：data/yaml/<test_func>.yaml
    """
    argnames = list(metafunc.fixturenames)
    if not argnames:
        return

    param_name = None
    if "case" in argnames:
        param_name = "case"
    elif "data" in argnames:
        param_name = "data"
    else:
        return

    yaml_path = ensure_yaml_for_test(metafunc.function.__name__)
    if not yaml_path.exists():
        return

    data = yaml.safe_load(yaml_path.read_text(encoding="utf-8")) or []
    if not isinstance(data, list):
        raise RuntimeError(f"YAML 顶层必须是 list：{yaml_path}")

    ids: List[str] = []
    values: List[Any] = []
    for idx, item in enumerate(data):
        case_id = None
        if isinstance(item, dict):
            case_id = item.get("id") or item.get("name")
        ids.append(str(case_id) if case_id else f"case_{idx}")

        values.append(item)

    metafunc.parametrize(param_name, values, ids=ids)


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item: pytest.Item, call: pytest.CallInfo):
    """失败时自动附加请求/响应快照到 Allure。"""
    outcome = yield
    report = outcome.get_result()
    if report.when != "call" or not report.failed:
        return

    allure = _safe_import_allure()
    if allure is None:
        return

    try:
        ctx: SessionContext = item._request.getfixturevalue("session_context")
    except Exception:
        return

    snapshot = ctx.get_last_snapshot()
    if not snapshot:
        return

    allure.attach(
        json.dumps(snapshot, ensure_ascii=False, indent=4, default=lambda o: o.__dict__),
        name="request_response_snapshot",
        attachment_type=getattr(allure.attachment_type, "JSON", None),
    )
