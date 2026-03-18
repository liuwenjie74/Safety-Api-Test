# -*- coding: utf-8 -*-
"""
Pytest 全局配置：
1) Session 级 HTTPClient 注入；
2) 跨进程 Token 单例与缓存；
3) YAML 动态用例注入；
4) Allure 日志步骤注入。
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple
import json
import logging
import os
import threading
import time
import traceback
import sys

import pytest
import requests
import yaml
from filelock import FileLock

# 将项目根目录加入 sys.path，确保 core/ 可导入
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from core.request_client import HTTPClient, TokenProvider  # noqa: E402


def _safe_import_allure() -> Optional[Any]:
    """安全导入 allure，避免在未安装时引发硬错误。"""
    try:
        import allure  # type: ignore

        return allure
    except Exception:
        return None


def _read_settings_attr(name: str) -> Optional[Any]:
    """从 config.settings 中读取配置（若存在）。"""
    try:
        from config import settings as _settings  # type: ignore

        return getattr(_settings, name, None)
    except Exception:
        return None


def _get_setting(name: str, default: Any = None, cast: Optional[Any] = None) -> Any:
    """
    获取配置的统一入口：
    1) 优先读取 config.settings；
    2) 再读取环境变量；
    3) 最后回退默认值。
    """
    value = _read_settings_attr(name)
    if value is not None:
        return value

    raw = os.getenv(name)
    if raw is None:
        return default

    if cast is not None:
        try:
            return cast(raw)
        except Exception:
            return default

    # 尝试 JSON 解析（适用于 dict/list）
    if isinstance(default, (dict, list)) or name.endswith("_PAYLOAD") or name.endswith("_HEADERS"):
        try:
            return json.loads(raw)
        except Exception:
            return default

    return raw


def _as_bool(raw: str) -> bool:
    return raw.strip().lower() in {"1", "true", "yes", "y", "on"}


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


def _parse_expires_at(value: Any) -> Optional[float]:
    """解析 expires_at 支持时间戳或 ISO 字符串。"""
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            # 尝试作为时间戳
            return float(value)
        except Exception:
            pass
        try:
            dt = datetime.fromisoformat(value)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt.timestamp()
        except Exception:
            return None
    return None


@dataclass
class TokenCache:
    """Token 缓存数据结构。"""

    token: str
    expires_at: Optional[float]
    issued_at: float


class TokenManager(TokenProvider):
    """
    跨进程 Token 管理单例：
    - 线程安全：__new__ + threading.Lock；
    - 进程安全：FileLock + 本地缓存文件。
    """

    _instance: Optional["TokenManager"] = None
    _instance_lock = threading.Lock()

    def __new__(cls, *args: Any, **kwargs: Any) -> "TokenManager":
        if cls._instance is None:
            with cls._instance_lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self) -> None:
        if getattr(self, "_initialized", False):
            return
        self._initialized = True

        # 登录配置（按接口文档默认值，可被 settings/env 覆盖）
        self.auth_url: str = _get_setting(
            "AUTH_URL", "http://test.lenszl.cn:30275/api/common/sys/login"
        )
        self.auth_method: str = _get_setting("AUTH_METHOD", "POST")
        self.auth_headers: Dict[str, Any] = _get_setting(
            "AUTH_HEADERS", {"Content-Type": "application/json"}
        )
        self.auth_payload: Optional[Any] = _get_setting(
            "AUTH_PAYLOAD",
            {
                "password": "pbzRaHGAq8oRynAGGf8h2PIGweN1xFSYOBR7/3irtr4xfttk+Uiew+s5zWtozRSpAfE9OyIDHRtQbTO9Tp8oPTXpMQCGPSDp+b5nGvZWF54Hh26IldZSeJQBYY6qmCpXFkF96ZwbRQC5g1ciDRCL3BNGn4/DGdlh6hT0Y9/pxzc=",
                "userAccount": "WQFoB58NSEdBpqJXn2xk4+EBzIjdY1QNDW3Z/EW4YXNaiPKMW1GQEaA2lXiGnLLjV2OvDU+yUjhOV59r7qHbjrzquoH0SYIFdRWWXj0ghg+zKeUeeMpW0QDhZ29FUVmcnsUPiFfPRHYkH22E6kpd7YdyrCW2n/WYSyr0efxofPg=",
            },
        )
        self.auth_verify: bool = _get_setting("AUTH_VERIFY", True, cast=_as_bool)
        self.auth_timeout: float = float(_get_setting("AUTH_TIMEOUT", 15))

        # Token 解析路径
        self.token_response_path: str = _get_setting("TOKEN_RESPONSE_PATH", "data")
        self.expires_in_path: Optional[str] = _get_setting("EXPIRES_IN_PATH", None)
        self.expires_at_path: Optional[str] = _get_setting("EXPIRES_AT_PATH", None)
        self.token_ttl_skew: int = int(_get_setting("TOKEN_TTL_SKEW", 30))

        # 缓存路径
        self.cache_path: str = _get_setting(
            "TOKEN_CACHE_PATH", ".pytest_cache/auth_token.json"
        )
        cache_file = Path(self.cache_path)
        cache_file.parent.mkdir(parents=True, exist_ok=True)
        self._file_lock = FileLock(str(cache_file) + ".lock")

        # 运行态缓存
        self._token_cache: Optional[TokenCache] = None
        self._lock = threading.Lock()

    def get_token(self, force_refresh: bool = False) -> str:
        """
        获取有效 Token：
        - 先读内存；
        - 再读跨进程缓存；
        - 最后发起真实登录。
        """
        with self._lock:
            if not force_refresh and self._token_cache and self._is_valid(self._token_cache):
                return self._token_cache.token

        with self._file_lock:
            cache = self._read_cache()
            if not force_refresh and cache and self._is_valid(cache):
                self._token_cache = cache
                return cache.token

            # 执行真实登录
            new_cache = self._login()
            self._write_cache(new_cache)
            self._token_cache = new_cache
            return new_cache.token

    # ------------------------- 内部实现 -------------------------

    def _is_valid(self, cache: TokenCache) -> bool:
        """判断缓存是否有效。"""
        if not cache.token:
            return False
        if cache.expires_at is None:
            return True
        now = time.time()
        return now < (cache.expires_at - self.token_ttl_skew)

    def _login(self) -> TokenCache:
        """调用登录接口获取 Token。"""
        payload = self.auth_payload
        kwargs: Dict[str, Any] = {
            "method": self.auth_method.upper(),
            "url": self.auth_url,
            "headers": self.auth_headers,
            "timeout": self.auth_timeout,
            "verify": self.auth_verify,
        }
        if isinstance(payload, (dict, list)):
            kwargs["json"] = payload
        elif payload is not None:
            kwargs["data"] = payload

        response = requests.request(**kwargs)
        response.raise_for_status()
        try:
            body = response.json()
        except Exception as exc:
            raise RuntimeError(f"登录接口返回非 JSON：{response.text}") from exc

        token = _extract_by_path(body, self.token_response_path)
        if not token:
            raise RuntimeError(f"未从响应中解析到 Token，path={self.token_response_path}")

        now = time.time()
        expires_at = None
        if self.expires_at_path:
            expires_at = _parse_expires_at(_extract_by_path(body, self.expires_at_path))
        elif self.expires_in_path:
            expires_in = _extract_by_path(body, self.expires_in_path)
            try:
                expires_at = now + float(expires_in)
            except Exception:
                expires_at = None

        return TokenCache(token=str(token), expires_at=expires_at, issued_at=now)

    def _read_cache(self) -> Optional[TokenCache]:
        """读取本地缓存文件。"""
        cache_file = Path(self.cache_path)
        if not cache_file.exists():
            return None
        try:
            data = json.loads(cache_file.read_text(encoding="utf-8"))
            return TokenCache(
                token=str(data.get("token") or ""),
                expires_at=data.get("expires_at"),
                issued_at=float(data.get("issued_at") or 0),
            )
        except Exception:
            return None

    def _write_cache(self, cache: TokenCache) -> None:
        """写入本地缓存文件。"""
        cache_file = Path(self.cache_path)
        cache_file.write_text(
            json.dumps(
                {
                    "token": cache.token,
                    "expires_at": cache.expires_at,
                    "issued_at": cache.issued_at,
                },
                ensure_ascii=False,
                indent=4,
            ),
            encoding="utf-8",
        )


class AllureStepHandler(logging.Handler):
    """将日志自动包装为 Allure step 的 Handler。"""

    _is_allure_step_handler = True

    def emit(self, record: logging.LogRecord) -> None:
        allure = _safe_import_allure()
        if allure is None:
            return
        try:
            message = self.format(record)
            with allure.step(message):
                pass
        except Exception:
            # 避免日志处理异常影响测试流程
            return


def _install_allure_logging_handler() -> None:
    """安装 Allure 日志 Handler（去重）。"""
    logger = logging.getLogger()
    for h in logger.handlers:
        if getattr(h, "_is_allure_step_handler", False):
            return
    handler = AllureStepHandler()
    handler.setLevel(logging.INFO)
    logger.addHandler(handler)


def pytest_configure(config: pytest.Config) -> None:
    """pytest 启动时安装 Allure 日志 Handler。"""
    _install_allure_logging_handler()


@pytest.fixture(scope="session", autouse=True)
def http_client() -> Iterable[HTTPClient]:
    """
    全局 Session 级 HTTPClient。
    - 自动注入 TokenManager；
    - 默认按接口文档使用 token Header。
    """
    token_manager = TokenManager()

    base_url = _get_setting("BASE_URL", None)
    token_in = _get_setting("TOKEN_IN", "header")
    token_header = _get_setting("TOKEN_HEADER", "token")
    token_query_param = _get_setting("TOKEN_QUERY_PARAM", "access_token")
    token_prefix = _get_setting("TOKEN_PREFIX", None)
    refresh_lock_path = _get_setting("REFRESH_LOCK_PATH", ".pytest_cache/auth_refresh.lock")

    client = HTTPClient(
        base_url=base_url,
        token_provider=token_manager,
        token_in=token_in,
        token_header=token_header,
        token_query_param=token_query_param,
        token_prefix=token_prefix,
        refresh_lock_path=refresh_lock_path,
    )

    yield client
    client.close()


def pytest_generate_tests(metafunc: pytest.Metafunc) -> None:
    """
    根据 data/yaml/<test_func>.yaml 自动注入参数。

    YAML 约定：
    - 顶层为 list；
    - 每个元素为 dict 或 list；
    - dict 中可含 id 或 name 用作测试 ID。
    """
    yaml_path = PROJECT_ROOT / "data" / "yaml" / f"{metafunc.function.__name__}.yaml"
    if not yaml_path.exists():
        return

    try:
        raw = yaml.safe_load(yaml_path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise RuntimeError(f"解析 YAML 失败：{yaml_path}") from exc

    if not isinstance(raw, list):
        raise RuntimeError(f"YAML 顶层必须是 list：{yaml_path}")

    argnames = list(metafunc.fixturenames)
    if not argnames:
        return

    ids: List[str] = []
    values: List[Any] = []
    for idx, item in enumerate(raw):
        case_id = None
        if isinstance(item, dict):
            case_id = item.get("id") or item.get("name")
        ids.append(str(case_id) if case_id else f"case_{idx}")

        if len(argnames) == 1:
            values.append(item)
            continue

        if isinstance(item, dict):
            values.append(tuple(item.get(name) for name in argnames))
        elif isinstance(item, (list, tuple)):
            if len(item) != len(argnames):
                raise RuntimeError(
                    f"用例参数数量不匹配：{yaml_path} 第 {idx} 条"
                )
            values.append(tuple(item))
        else:
            raise RuntimeError(f"用例格式非法：{yaml_path} 第 {idx} 条")

    if len(argnames) == 1:
        metafunc.parametrize(argnames[0], values, ids=ids)
    else:
        metafunc.parametrize(argnames, values, ids=ids)
