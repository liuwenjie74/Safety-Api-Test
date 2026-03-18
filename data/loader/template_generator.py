# -*- coding: utf-8 -*-
"""Generate Excel templates for the single-source test data workbook."""
from __future__ import annotations

from pathlib import Path
from typing import List, Optional

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
    output_path: Path,
    sheet_name: str = "cases",
    columns: Optional[List[str]] = None,
) -> Path:
    """
    Create an empty Excel template.

    :param output_path: Output workbook path.
    :param sheet_name: Initial sheet name.
    :param columns: Column names for the first sheet.
    :return: Created workbook path.
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)
    dataframe = pd.DataFrame(columns=columns or DEFAULT_COLUMNS)
    dataframe.to_excel(output_path, index=False, sheet_name=sheet_name)
    return output_path


def generate_default_template() -> Path:
    """Create the default ``api_cases.xlsx`` template under ``data/excel``."""
    return generate_excel_template(settings.EXCEL_DIR / settings.EXCEL_MAIN)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Generate an Excel template workbook.")
    parser.add_argument(
        "--path",
        type=str,
        default=str(settings.EXCEL_DIR / settings.EXCEL_MAIN),
        help="Output workbook path.",
    )
    parser.add_argument(
        "--sheet",
        type=str,
        default="cases",
        help="Initial sheet name.",
    )
    args = parser.parse_args()

    output = generate_excel_template(Path(args.path), sheet_name=args.sheet)
    print(f"generated: {output}")
