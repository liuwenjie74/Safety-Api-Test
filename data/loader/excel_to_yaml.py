# -*- coding: utf-8 -*-
"""Convert the single Excel workbook into YAML runtime data."""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional
import json

import pandas as pd
import yaml


def _parse_cell(value: Any) -> Any:
    """Normalize Excel cell values and parse JSON-like strings."""
    if value is None:
        return None
    if isinstance(value, float) and pd.isna(value):
        return None
    if isinstance(value, str):
        text = value.strip()
        if not text or text.lower() == "null":
            return None
        if (text.startswith("{") and text.endswith("}")) or (
            text.startswith("[") and text.endswith("]")
        ):
            try:
                return json.loads(text)
            except Exception:
                return text
        return text
    return value


def _auto_build_asserts(item: Dict[str, Any]) -> None:
    """Populate default assertion rules when ``asserts`` is omitted."""
    if "asserts" in item:
        return

    rules: List[Dict[str, Any]] = []
    if "expected_status" in item:
        rules.append({"type": "status_code", "expected": item.get("expected_status")})
    if "expected_code" in item:
        rules.append(
            {"type": "json_path_eq", "path": "code", "expected": item.get("expected_code")}
        )

    if rules:
        item["asserts"] = rules


def _normalize_records(dataframe: pd.DataFrame) -> List[Dict[str, Any]]:
    """Convert a sheet into a list of testcase dictionaries."""
    dataframe = dataframe.dropna(how="all")
    records: List[Dict[str, Any]] = []

    for _, row in dataframe.iterrows():
        item: Dict[str, Any] = {}
        for column, value in row.items():
            parsed = _parse_cell(value)
            if parsed is not None:
                item[str(column).strip()] = parsed

        _auto_build_asserts(item)
        if item:
            records.append(item)

    return records


def export_sheet_to_yaml(
    excel_path: Path,
    sheet_name: str,
    yaml_dir: Path,
    yaml_name: Optional[str] = None,
) -> Path:
    """
    Export a single sheet from the Excel source workbook into YAML.

    :param excel_path: Source Excel workbook path.
    :param sheet_name: Name of the sheet to export.
    :param yaml_dir: Output YAML directory.
    :param yaml_name: Optional YAML file stem.
    :return: Output YAML file path.
    """
    yaml_dir.mkdir(parents=True, exist_ok=True)
    dataframe = pd.read_excel(excel_path, sheet_name=sheet_name)
    records = _normalize_records(dataframe)
    safe_name = (yaml_name or sheet_name).strip().replace(" ", "_")
    output_path = yaml_dir / f"{safe_name}.yaml"
    output_path.write_text(
        yaml.safe_dump(records, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )
    return output_path


def export_excel_to_yaml(excel_path: Path, yaml_dir: Path) -> List[Path]:
    """Export every sheet in the workbook to a standalone YAML file."""
    if not excel_path.exists():
        raise FileNotFoundError(f"Excel file not found: {excel_path}")

    yaml_dir.mkdir(parents=True, exist_ok=True)
    sheets = pd.read_excel(excel_path, sheet_name=None)
    output_paths: List[Path] = []

    for sheet_name, dataframe in sheets.items():
        records = _normalize_records(dataframe)
        safe_sheet_name = str(sheet_name).strip().replace(" ", "_")
        output_path = yaml_dir / f"{safe_sheet_name}.yaml"
        output_path.write_text(
            yaml.safe_dump(records, allow_unicode=True, sort_keys=False),
            encoding="utf-8",
        )
        output_paths.append(output_path)

    return output_paths
