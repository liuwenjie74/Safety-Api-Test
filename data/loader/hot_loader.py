# -*- coding: utf-8 -*-
"""Hot-load YAML data from the single Excel source file."""
from __future__ import annotations

from pathlib import Path
from typing import Optional

import pandas as pd

from config import settings
from data.loader.excel_to_yaml import export_excel_to_yaml, export_sheet_to_yaml


def ensure_yaml_for_test(test_name: str) -> Path:
    """
    Ensure the YAML file for a test function exists and is up to date.

    The framework uses one Excel file (``api_cases.xlsx``) and maps each
    ``test_*`` sheet to ``data/yaml/<sheet_name>.yaml``.
    """
    yaml_path = settings.YAML_DIR / f"{test_name}.yaml"
    excel_path = settings.EXCEL_DIR / settings.EXCEL_MAIN

    if not excel_path.exists():
        raise FileNotFoundError(f"Excel source file not found: {excel_path}")

    owner = _find_sheet_owner_in_excel(excel_path, test_name)
    if owner is None:
        raise FileNotFoundError(
            f"Sheet {test_name!r} was not found in {excel_path}. "
            f"Please add a sheet with the same name as the test function."
        )

    if not yaml_path.exists() or excel_path.stat().st_mtime > yaml_path.stat().st_mtime:
        export_sheet_to_yaml(excel_path, owner, settings.YAML_DIR, yaml_name=test_name)

    return yaml_path


def sync_all_excels() -> None:
    """Export all sheets in the single Excel source file to YAML."""
    excel_path = settings.EXCEL_DIR / settings.EXCEL_MAIN
    if excel_path.exists():
        export_excel_to_yaml(excel_path, settings.YAML_DIR)


def _find_sheet_owner_in_excel(excel: Path, test_name: str) -> Optional[str]:
    """Return the matching sheet name for a test function."""
    try:
        xls = pd.ExcelFile(excel)
    except Exception:
        return None

    for sheet in xls.sheet_names:
        if sheet == test_name or sheet.strip().lower() == test_name.lower():
            return sheet

    return None
