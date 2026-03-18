# -*- coding: utf-8 -*-
"""
核心请求客户端：
1) 基于 requests.Session 的门面模式封装；
2) 401 无感刷新（带跨进程刷新锁与熔断阈值）；
3) 自动 Allure 附件（请求/响应载荷 + 异常快照）。
"""
from __future__ import annotations

from typing import Any, Dict, Iterable, Mapping, Optional, Protocol
import json
import traceback
from pathlib import Path
from urllib.parse import urljoin

import requests
from filelock import FileLock


def _safe_import_allure() -> Optional[Any]:
    """安全导入 allure，避免在未安装时引发硬错误。"""
    try:
        import allure  # type: ignore

        return allure
    except Exception:
        return None


class TokenProvider(Protocol):
    """Token 提供者协议，用于解耦鉴权实现与请求客户端。"""

    def get_token(self, force_refresh: bool = False) -> str:
        """
        获取 Token。

        :param force_refresh: 是否强制刷新（绕过缓存）。
        :return: 有效的 Token 字符串。
        """


class HTTPClient:
    """
    基于 requests.Session 的请求门面。

    设计目标：
    - 高内聚：请求重试/鉴权/附件逻辑全部封装；
    - 低耦合：仅依赖 TokenProvider 协议；
    - 无感刷新：401 时自动刷新并重放请求（2 次熔断阈值）。
    """

    def __init__(
        self,
        session: Optional[requests.Session] = None,
        base_url: Optional[str] = None,
        token_provider: Optional[TokenProvider] = None,
        token_in: str = "header",
        token_header: str = "token",
        token_query_param: str = "access_token",
        token_prefix: Optional[str] = None,
        refresh_lock_path: str = ".pytest_cache/auth_refresh.lock",
        max_retry_401: int = 2,
        attach_allure: bool = True,
        timeout: Optional[float] = None,
    ) -> None:
        """
        :param session: 自定义 requests.Session；缺省则新建。
        :param base_url: 统一前缀（相对路径自动拼接）。
        :param token_provider: Token 提供者（可选）。
        :param token_in: Token 注入位置：'header' 或 'query'。
        :param token_header: Header 注入时的字段名。
        :param token_query_param: Query 注入时的字段名。
        :param token_prefix: Header 注入时的前缀（如 'Bearer '）。
        :param refresh_lock_path: 跨进程刷新锁路径。
        :param max_retry_401: 401 重试次数（熔断阈值）。
        :param attach_allure: 是否自动附加 Allure 附件。
        :param timeout: 默认超时（可被单次请求覆盖）。
        """
        self._session = session or requests.Session()
        self._base_url = base_url
        self._token_provider = token_provider
        self._token_in = token_in
        self._token_header = token_header
        self._token_query_param = token_query_param
        self._token_prefix = token_prefix
        self._refresh_lock = FileLock(str(Path(refresh_lock_path)))
        self._max_retry_401 = max_retry_401
        self._attach_allure = attach_allure
        self._timeout = timeout

    def close(self) -> None:
        """关闭底层 Session 连接。"""
        self._session.close()

    def request(self, method: str, url: str, **kwargs: Any) -> requests.Response:
        """
        统一请求入口，内部自动注入 Token 与处理 401 刷新。

        :param method: HTTP 方法。
        :param url: 绝对或相对路径。
        :param kwargs: 原生 requests.request 参数。
        :return: requests.Response 对象。
        """
        base_kwargs = self._normalize_kwargs(kwargs)
        retries = 0

        while True:
            token = self._get_token_safely(force_refresh=False)
            attempt_kwargs = self._apply_token(base_kwargs, token)

            try:
                response = self._send(method, url, attempt_kwargs, attempt=retries)
            except Exception:
                # 异常快照已在 _send 中处理
                raise

            if (
                response.status_code != 401
                or self._token_provider is None
                or retries >= self._max_retry_401
                or not self._is_replayable(base_kwargs)
            ):
                return response

            # 401 触发刷新，使用跨进程锁避免并发风暴
            self._refresh_token_with_lock()
            retries += 1

    def get(self, url: str, **kwargs: Any) -> requests.Response:
        """GET 请求便捷方法。"""
        return self.request("GET", url, **kwargs)

    def post(self, url: str, **kwargs: Any) -> requests.Response:
        """POST 请求便捷方法。"""
        return self.request("POST", url, **kwargs)

    def put(self, url: str, **kwargs: Any) -> requests.Response:
        """PUT 请求便捷方法。"""
        return self.request("PUT", url, **kwargs)

    def delete(self, url: str, **kwargs: Any) -> requests.Response:
        """DELETE 请求便捷方法。"""
        return self.request("DELETE", url, **kwargs)

    # ------------------------- 内部工具方法 -------------------------

    def _join_url(self, url: str) -> str:
        """拼接 base_url 与相对路径，保留绝对路径原样。"""
        if self._base_url and not url.lower().startswith(("http://", "https://")):
            return urljoin(self._base_url.rstrip("/") + "/", url.lstrip("/"))
        return url

    def _normalize_kwargs(self, kwargs: Mapping[str, Any]) -> Dict[str, Any]:
        """标准化请求参数，确保 headers/params 为可写 dict。"""
        normalized = dict(kwargs)
        normalized["headers"] = dict(kwargs.get("headers") or {})
        normalized["params"] = dict(kwargs.get("params") or {})
        if "timeout" not in normalized and self._timeout is not None:
            normalized["timeout"] = self._timeout
        return normalized

    def _apply_token(self, base_kwargs: Mapping[str, Any], token: Optional[str]) -> Dict[str, Any]:
        """将 token 写入 headers 或 query。"""
        kwargs = dict(base_kwargs)
        headers = dict(base_kwargs.get("headers") or {})
        params = dict(base_kwargs.get("params") or {})

        if token:
            if self._token_in == "header":
                value = f"{self._token_prefix}{token}" if self._token_prefix else token
                headers[self._token_header] = value
            else:
                params[self._token_query_param] = token

        kwargs["headers"] = headers
        kwargs["params"] = params
        return kwargs

    def _get_token_safely(self, force_refresh: bool) -> Optional[str]:
        """安全获取 token；若未配置 TokenProvider，则返回 None。"""
        if not self._token_provider:
            return None
        try:
            return self._token_provider.get_token(force_refresh=force_refresh)
        except Exception:
            # 不在这里吞异常，交由上层处理
            raise

    def _refresh_token_with_lock(self) -> None:
        """使用跨进程锁刷新 Token，避免并发风暴。"""
        if not self._token_provider:
            return
        with self._refresh_lock:
            # 401 语义下强制刷新，确保旧 token 被替换
            self._token_provider.get_token(force_refresh=True)

    def _is_replayable(self, base_kwargs: Mapping[str, Any]) -> bool:
        """
        判断请求是否可重放。

        - 文件流/生成器等不可重放；
        - 其余常见类型（dict/str/bytes）允许重放。
        """
        if base_kwargs.get("files") is not None:
            return False

        data = base_kwargs.get("data")
        if data is None:
            return True

        if hasattr(data, "read"):
            return False

        # 迭代器/生成器不可重放
        if hasattr(data, "__iter__") and not isinstance(
            data, (dict, list, tuple, str, bytes, bytearray)
        ):
            return False

        return True

    def _send(
        self, method: str, url: str, kwargs: Mapping[str, Any], attempt: int
    ) -> requests.Response:
        """
        发送请求并负责 Allure 附件收集。
        """
        full_url = self._join_url(url)
        try:
            response = self._session.request(method, full_url, **kwargs)
            self._attach_request_response(method, full_url, kwargs, response, attempt)
            return response
        except Exception:
            self._attach_exception_snapshot(method, full_url, kwargs)
            raise

    def _attach_request_response(
        self,
        method: str,
        url: str,
        kwargs: Mapping[str, Any],
        response: requests.Response,
        attempt: int,
    ) -> None:
        """为请求与响应自动附加 Allure 富文本。"""
        if not self._attach_allure:
            return
        allure = _safe_import_allure()
        if allure is None:
            return

        request_snapshot = self._build_request_snapshot(method, url, kwargs)
        self._attach_as_json(allure, f"request_snapshot_attempt_{attempt}", request_snapshot)

        # 响应元数据
        response_meta = {
            "status_code": response.status_code,
            "headers": dict(response.headers),
        }
        self._attach_as_json(allure, f"response_meta_attempt_{attempt}", response_meta)

        # 响应体
        body_name = f"response_body_attempt_{attempt}"
        self._attach_response_body(allure, body_name, response)

    def _attach_exception_snapshot(
        self, method: str, url: str, kwargs: Mapping[str, Any]
    ) -> None:
        """异常时附加 traceback 与请求快照。"""
        if not self._attach_allure:
            return
        allure = _safe_import_allure()
        if allure is None:
            return

        request_snapshot = self._build_request_snapshot(method, url, kwargs)
        self._attach_as_json(allure, "exception_request_snapshot", request_snapshot)

        tb = traceback.format_exc()
        allure.attach(
            tb,
            name="exception_traceback",
            attachment_type=getattr(allure.attachment_type, "TEXT", None),
        )

    def _build_request_snapshot(
        self, method: str, url: str, kwargs: Mapping[str, Any]
    ) -> Dict[str, Any]:
        """构建请求快照，保证可序列化。"""
        return {
            "method": method,
            "url": url,
            "headers": dict(kwargs.get("headers") or {}),
            "params": dict(kwargs.get("params") or {}),
            "json": kwargs.get("json"),
            "data": self._safe_to_text(kwargs.get("data")),
        }

    def _attach_response_body(self, allure: Any, name: str, response: requests.Response) -> None:
        """根据 Content-Type 自动附加响应内容。"""
        content_type = (response.headers.get("Content-Type") or "").lower()

        if "application/json" in content_type:
            try:
                payload = response.json()
                self._attach_as_json(allure, name, payload)
                return
            except Exception:
                # 回退为文本
                pass

        if "text/html" in content_type:
            allure.attach(
                response.text,
                name=name,
                attachment_type=getattr(allure.attachment_type, "HTML", None),
            )
            return

        if content_type.startswith("text/"):
            allure.attach(
                response.text,
                name=name,
                attachment_type=getattr(allure.attachment_type, "TEXT", None),
            )
            return

        # 兜底：尝试文本
        allure.attach(
            response.text,
            name=name,
            attachment_type=getattr(allure.attachment_type, "TEXT", None),
        )

    def _attach_as_json(self, allure: Any, name: str, payload: Any) -> None:
        """以 JSON 形式附加（支持非 ASCII 字符）。"""
        try:
            text = json.dumps(payload, ensure_ascii=False, indent=4)
        except Exception:
            text = str(payload)
        allure.attach(
            text,
            name=name,
            attachment_type=getattr(allure.attachment_type, "JSON", None),
        )

    def _safe_to_text(self, value: Any) -> Any:
        """将可能不可序列化的对象转为可读文本。"""
        if value is None:
            return None
        if isinstance(value, (str, int, float, bool, list, dict)):
            return value
        if isinstance(value, (bytes, bytearray)):
            try:
                return value.decode("utf-8", errors="ignore")
            except Exception:
                return repr(value)
        return repr(value)
