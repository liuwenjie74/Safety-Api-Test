# -*- coding: utf-8 -*-
"""
热加载器：
- 根据时间戳自动同步 Excel → YAML；
- 确保测试执行时 YAML 与 Excel 一致。
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional, Tuple

import pandas as pd

from config import settings
from data.loader.excel_to_yaml import export_excel_to_yaml, export_sheet_to_yaml


def ensure_yaml_for_test(test_name: str) -> Path:
    """
    按测试函数名映射 Excel 与 YAML：
    - Excel: data/excel/<test_name>.xlsx
    - YAML : data/yaml/<test_name>.yaml
    """
    excel_path = settings.EXCEL_DIR / f"{test_name}.xlsx"
    yaml_path = settings.YAML_DIR / f"{test_name}.yaml"

    # 1) 优先匹配同名 Excel
    if excel_path.exists():
        if not yaml_path.exists() or excel_path.stat().st_mtime > yaml_path.stat().st_mtime:
            export_excel_to_yaml(excel_path, settings.YAML_DIR)
        return yaml_path

    # 2) 其次匹配“多 Sheet → 多模块”映射
    owner = _find_sheet_owner(test_name)
    if owner is None:
        raise FileNotFoundError(
            f"未找到 Excel 数据源：{excel_path} 或包含 Sheet={test_name} 的 Excel"
        )

    excel_path, sheet_name = owner
    if not yaml_path.exists() or excel_path.stat().st_mtime > yaml_path.stat().st_mtime:
        export_sheet_to_yaml(excel_path, sheet_name, settings.YAML_DIR, yaml_name=test_name)
    return yaml_path


def sync_all_excels() -> None:
    """同步所有 Excel 文件到 YAML 目录。"""
    for excel in settings.EXCEL_DIR.glob("*.xlsx"):
        export_excel_to_yaml(excel, settings.YAML_DIR)


def _find_sheet_owner(test_name: str) -> Optional[Tuple[Path, str]]:
    """在所有 Excel 中寻找与 test_name 同名的 Sheet。"""
    for excel in settings.EXCEL_DIR.glob("*.xlsx"):
        try:
            xls = pd.ExcelFile(excel)
            for sheet in xls.sheet_names:
                if sheet == test_name or sheet.strip().lower() == test_name.lower():
                    return excel, sheet
        except Exception:
            continue
    return None
