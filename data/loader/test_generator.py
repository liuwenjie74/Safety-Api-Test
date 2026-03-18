# -*- coding: utf-8 -*-
"""Generate YAML files and pytest modules from sheets in ``api_cases.xlsx``."""
from __future__ import annotations

from pathlib import Path
from typing import List

import pandas as pd

from config import settings
from data.loader.excel_to_yaml import export_sheet_to_yaml


REQUEST_TEST_TEMPLATE = """# -*- coding: utf-8 -*-
\"\"\"
Auto-generated testcase: {sheet_name}
- Data source: data/yaml/{sheet_name}.yaml
\"\"\"
from __future__ import annotations

from typing import Any, Dict

from base.request_client import RequestClient
from common.assertions import assert_response


def {test_func}(case: Dict[str, Any], client: RequestClient) -> None:
    \"\"\"Run the API testcase described in the matching YAML file.\"\"\"
    method = case.get("method", "GET")
    url = case["url"]

    response = client.request(
        method=method,
        url=url,
        headers=case.get("headers"),
        params=case.get("params"),
        json=case.get("json"),
        data=case.get("data"),
    )

    assert_response(case, response)
"""


LOGIN_TEST_TEMPLATE = """# -*- coding: utf-8 -*-
\"\"\"
Auto-generated testcase: {sheet_name}
- Data source: data/yaml/{sheet_name}.yaml
\"\"\"
from __future__ import annotations

from typing import Any, Dict

from common.auth import AuthService
from common.assertions import assert_response
from config import settings


def _as_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    return str(value).strip().lower() in {{"1", "true", "yes", "y", "on"}}


def {test_func}(case: Dict[str, Any], auth_service: AuthService) -> None:
    \"\"\"Run the login testcase without affecting the session login fixture.\"\"\"
    use_settings = _as_bool(case.get("use_settings_login", True))
    method = case.get("method", settings.LOGIN_METHOD)
    url = case.get("url", settings.LOGIN_URL)

    if use_settings:
        payload = settings.LOGIN_PAYLOAD
        headers = settings.LOGIN_HEADERS
    else:
        payload = case.get("json") or case.get("data")
        headers = case.get("headers") or settings.LOGIN_HEADERS

    response = auth_service.request_login(
        payload=payload,
        headers=headers,
        method=method,
        url=url,
        raise_for_status=False,
    )

    assert_response(case, response)
"""


def _build_test_content(sheet_name: str) -> str:
    """Choose the proper template for the target sheet."""
    template = LOGIN_TEST_TEMPLATE if sheet_name == "test_login" else REQUEST_TEST_TEMPLATE
    return template.format(sheet_name=sheet_name, test_func=sheet_name)


def generate_all(force: bool = False) -> List[Path]:
    """
    Generate YAML data and pytest modules for all ``test_*`` sheets.

    :param force: Overwrite existing test modules when set to ``True``.
    :return: Paths of newly created or overwritten test files.
    """
    excel_path = settings.EXCEL_DIR / settings.EXCEL_MAIN
    if not excel_path.exists():
        raise FileNotFoundError(f"Excel file does not exist: {excel_path}")

    testcases_dir = settings.BASE_DIR / "testcases"
    testcases_dir.mkdir(parents=True, exist_ok=True)

    xls = pd.ExcelFile(excel_path)
    created: List[Path] = []

    for sheet in xls.sheet_names:
        sheet_name = sheet.strip()
        if not sheet_name.startswith("test_"):
            continue

        export_sheet_to_yaml(excel_path, sheet_name, settings.YAML_DIR, yaml_name=sheet_name)

        test_file = testcases_dir / f"{sheet_name}.py"
        if test_file.exists() and not force:
            continue

        test_file.write_text(_build_test_content(sheet_name), encoding="utf-8")
        created.append(test_file)

    return created


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Generate YAML files and pytest modules from api_cases.xlsx"
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite existing test modules.",
    )
    args = parser.parse_args()

    for file_path in generate_all(force=args.force):
        print(f"generated: {file_path}")
