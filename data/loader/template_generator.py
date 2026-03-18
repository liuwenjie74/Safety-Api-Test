# -*- coding: utf-8 -*-
"""
Excel 模板生成器：
- 生成标准用例模板；
- 便于统一维护字段与格式。
"""
from __future__ import annotations

from pathlib import Path
from typing import List

import pandas as pd

from config import settings


DEFAULT_COLUMNS: List[str] = [
    "id",
    "name",
    "method",
    "url",
    "headers",
    "params",
    "json",
    "data",
    "expected_status",
    "expected_code",
    "asserts",
    "use_settings_login",
]


def generate_excel_template(
    output_path: Path, sheet_name: str = "cases", columns: List[str] = None
) -> Path:
    """
    生成 Excel 模板。

    :param output_path: 目标 Excel 路径
    :param sheet_name: Sheet 名称
    :param columns: 列定义，默认使用标准字段
    :return: 生成的 Excel 路径
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)
    cols = columns or DEFAULT_COLUMNS
    df = pd.DataFrame(columns=cols)
    df.to_excel(output_path, index=False, sheet_name=sheet_name)
    return output_path


def generate_default_template() -> Path:
    """
    在 data/excel 下生成默认模板文件：api_cases.xlsx
    """
    return generate_excel_template(settings.EXCEL_DIR / settings.EXCEL_MAIN)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Excel 模板生成器")
    parser.add_argument(
        "--path",
        type=str,
        default=str(settings.EXCEL_DIR / settings.EXCEL_MAIN),
        help="模板输出路径",
    )
    parser.add_argument("--sheet", type=str, default="cases", help="Sheet 名称")
    args = parser.parse_args()

    output = generate_excel_template(Path(args.path), sheet_name=args.sheet)
    print(f"模板已生成：{output}")
