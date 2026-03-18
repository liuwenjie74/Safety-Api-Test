# -*- coding: utf-8 -*-
"""
Excel → YAML 转换器：
- Excel 为唯一数据源；
- YAML 为运行时数据格式；
- 自动清洗空值并解析 JSON 字符串。
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional
import json

import pandas as pd
import yaml

from config import settings

def _parse_cell(value: Any) -> Any:
    """解析单元格内容，支持 JSON 字符串与空值清理。"""
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


def _normalize_records(df: pd.DataFrame) -> List[Dict[str, Any]]:
    """清洗 DataFrame，输出列表形式的用例数据。"""
    df = df.dropna(how="all")
    records: List[Dict[str, Any]] = []
    for _, row in df.iterrows():
        item: Dict[str, Any] = {}
        for col, val in row.items():
            parsed = _parse_cell(val)
            if parsed is not None:
                item[str(col).strip()] = parsed
        _auto_build_asserts(item)
        if item:
            records.append(item)
    return records


def _auto_build_asserts(item: Dict[str, Any]) -> None:
    """
    自动生成断言：
    - 如果 asserts 未配置且 expected_status/expected_code 存在，则生成默认断言。
    """
    if "asserts" in item:
        return

    rules: List[Dict[str, Any]] = []
    if "expected_status" in item:
        rules.append({"type": "status_code", "expected": item.get("expected_status")})
    if "expected_code" in item:
        rules.append({"type": "json_path_eq", "path": "code", "expected": item.get("expected_code")})

    if rules:
        item["asserts"] = rules


def export_sheet_to_yaml(
    excel_path: Path, sheet_name: str, yaml_dir: Path, yaml_name: Optional[str] = None
) -> Path:
    """
    仅导出指定 Sheet 为 YAML。

    :param excel_path: Excel 文件路径
    :param sheet_name: Sheet 名称
    :param yaml_dir: YAML 输出目录
    :param yaml_name: YAML 文件名（不含 .yaml），为空则使用 sheet_name
    """
    df = pd.read_excel(excel_path, sheet_name=sheet_name)
    records = _normalize_records(df)
    safe_name = (yaml_name or sheet_name).strip().replace(" ", "_")
    out_path = yaml_dir / f"{safe_name}.yaml"
    out_path.write_text(
        yaml.safe_dump(records, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )
    return out_path


def export_excel_to_yaml(excel_path: Path, yaml_dir: Path) -> List[Path]:
    """
    将 Excel 导出为 YAML：
    - 单 Sheet: 生成 <excel_stem>.yaml
    - 多 Sheet: 生成 <excel_stem>__<sheet>.yaml
    """
    if not excel_path.exists():
        raise FileNotFoundError(f"Excel 文件不存在：{excel_path}")

    yaml_dir.mkdir(parents=True, exist_ok=True)
    sheets = pd.read_excel(excel_path, sheet_name=None)
    output_paths: List[Path] = []

    if len(sheets) == 1:
        _, df = next(iter(sheets.items()))
        records = _normalize_records(df)
        out_path = yaml_dir / f"{excel_path.stem}.yaml"
        out_path.write_text(
            yaml.safe_dump(records, allow_unicode=True, sort_keys=False),
            encoding="utf-8",
        )
        output_paths.append(out_path)
        return output_paths

    for sheet_name, df in sheets.items():
        records = _normalize_records(df)
        safe_sheet = str(sheet_name).strip().replace(" ", "_")

        if settings.MULTI_SHEET_MODE.lower() == "excel_sheet":
            file_name = f"{excel_path.stem}__{safe_sheet}"
        else:
            file_name = safe_sheet

        out_path = yaml_dir / f"{file_name}.yaml"
        out_path.write_text(
            yaml.safe_dump(records, allow_unicode=True, sort_keys=False),
            encoding="utf-8",
        )
        output_paths.append(out_path)

    return output_paths
