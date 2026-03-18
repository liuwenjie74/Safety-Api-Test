# -*- coding: utf-8 -*-
"""
全局配置模块：
- 支持 .env 环境变量加载；
- 提供登录与路径等核心配置。
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Optional
import json
import os


BASE_DIR = Path(__file__).resolve().parents[1]


def _load_env_file(path: Path) -> None:
    """从 .env 文件加载环境变量（若存在）。"""
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


_load_env_file(BASE_DIR / ".env")


def _get_env_json(name: str, default: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """读取 JSON 格式环境变量，失败时回退默认值。"""
    raw = os.getenv(name)
    if not raw:
        return default or {}
    try:
        data = json.loads(raw)
        if isinstance(data, dict):
            return data
    except Exception:
        pass
    return default or {}


def _get_env_str(name: str, default: str) -> str:
    value = os.getenv(name)
    return value if value is not None else default


def _get_env_float(name: str, default: float) -> float:
    value = os.getenv(name)
    if value is None:
        return default
    try:
        return float(value)
    except Exception:
        return default


# 基础服务配置
BASE_URL: str = _get_env_str("BASE_URL", "http://test.lenszl.cn:30275")

# 登录接口配置（按接口文档默认值）
LOGIN_URL: str = _get_env_str("LOGIN_URL", f"{BASE_URL}/api/common/sys/login")
LOGIN_METHOD: str = _get_env_str("LOGIN_METHOD", "POST")
LOGIN_HEADERS: Dict[str, Any] = _get_env_json(
    "LOGIN_HEADERS", {"Content-Type": "application/json"}
)
LOGIN_PAYLOAD: Dict[str, Any] = _get_env_json(
    "LOGIN_PAYLOAD",
    {
        "password": "pbzRaHGAq8oRynAGGf8h2PIGweN1xFSYOBR7/3irtr4xfttk+Uiew+s5zWtozRSpAfE9OyIDHRtQbTO9Tp8oPTXpMQCGPSDp+b5nGvZWF54Hh26IldZSeJQBYY6qmCpXFkF96ZwbRQC5g1ciDRCL3BNGn4/DGdlh6hT0Y9/pxzc=",
        "userAccount": "WQFoB58NSEdBpqJXn2xk4+EBzIjdY1QNDW3Z/EW4YXNaiPKMW1GQEaA2lXiGnLLjV2OvDU+yUjhOV59r7qHbjrzquoH0SYIFdRWWXj0ghg+zKeUeeMpW0QDhZ29FUVmcnsUPiFfPRHYkH22E6kpd7YdyrCW2n/WYSyr0efxofPg=",
    },
)

# Token 提取路径（response.data）
TOKEN_PATH: str = _get_env_str("TOKEN_PATH", "data")
TOKEN_HEADER: str = _get_env_str("TOKEN_HEADER", "token")
TOKEN_PREFIX: str = _get_env_str("TOKEN_PREFIX", "")

# 请求超时
REQUEST_TIMEOUT: float = _get_env_float("REQUEST_TIMEOUT", 15.0)

# 数据目录
DATA_DIR = BASE_DIR / "data"
EXCEL_DIR = DATA_DIR / "excel"
YAML_DIR = DATA_DIR / "yaml"

# 日志脱敏
MASK_TOKEN_VISIBLE: int = int(os.getenv("MASK_TOKEN_VISIBLE", "4"))
