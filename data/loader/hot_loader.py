# -*- coding: utf-8 -*-
"""
热加载器：
- 根据时间戳自动同步 Excel → YAML；
- 确保测试执行时 YAML 与 Excel 一致。
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional

from config import settings
from data.loader.excel_to_yaml import export_excel_to_yaml


def ensure_yaml_for_test(test_name: str) -> Path:
    """
    按测试函数名映射 Excel 与 YAML：
    - Excel: data/excel/<test_name>.xlsx
    - YAML : data/yaml/<test_name>.yaml
    """
    excel_path = settings.EXCEL_DIR / f"{test_name}.xlsx"
    yaml_path = settings.YAML_DIR / f"{test_name}.yaml"

    if not excel_path.exists():
        raise FileNotFoundError(
            f"未找到 Excel 数据源：{excel_path}（Excel 为唯一数据源）"
        )

    if not yaml_path.exists() or excel_path.stat().st_mtime > yaml_path.stat().st_mtime:
        export_excel_to_yaml(excel_path, settings.YAML_DIR)

    return yaml_path


def sync_all_excels() -> None:
    """同步所有 Excel 文件到 YAML 目录。"""
    for excel in settings.EXCEL_DIR.glob("*.xlsx"):
        export_excel_to_yaml(excel, settings.YAML_DIR)
