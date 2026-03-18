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
    yaml_path = settings.YAML_DIR / f"{test_name}.yaml"

    # 唯一 Excel 文件（多 Sheet）
    excel_path = settings.EXCEL_DIR / settings.EXCEL_MAIN
    if not excel_path.exists():
        raise FileNotFoundError(
            f"未找到唯一 Excel 数据源：{excel_path}（请确保 api_cases.xlsx 存在）"
        )

    owner = _find_sheet_owner_in_excel(excel_path, test_name)
    if owner is None:
        raise FileNotFoundError(
            f"未找到 Sheet={test_name}，请在 {excel_path} 中新增同名 Sheet"
        )

    if not yaml_path.exists() or excel_path.stat().st_mtime > yaml_path.stat().st_mtime:
        export_sheet_to_yaml(excel_path, owner, settings.YAML_DIR, yaml_name=test_name)
    return yaml_path


def sync_all_excels() -> None:
    """同步唯一 Excel 文件到 YAML 目录。"""
    excel = settings.EXCEL_DIR / settings.EXCEL_MAIN
    if excel.exists():
        export_excel_to_yaml(excel, settings.YAML_DIR)


def _find_sheet_owner_in_excel(excel: Path, test_name: str) -> Optional[str]:
    """在指定 Excel 中寻找与 test_name 同名的 Sheet。"""
    try:
        xls = pd.ExcelFile(excel)
        for sheet in xls.sheet_names:
            if sheet == test_name or sheet.strip().lower() == test_name.lower():
                return sheet
    except Exception:
        return None
    return None
