# -*- coding: utf-8 -*-
"""
测试用例与 YAML 自动生成器：
- 根据 api_cases.xlsx 的 Sheet 自动生成 testcases/test_<sheet>.py；
- 同步生成 data/yaml/<sheet>.yaml；
- Sheet 名必须以 test_ 开头（与 pytest 规范一致）。
"""
from __future__ import annotations

from pathlib import Path
from typing import List

import pandas as pd

from config import settings
from data.loader.excel_to_yaml import export_sheet_to_yaml


TEST_TEMPLATE = """# -*- coding: utf-8 -*-
\"\"\"
自动生成用例：{sheet_name}
- 数据来自 api_cases.xlsx 的 Sheet: {sheet_name}
\"\"\"
from __future__ import annotations

from typing import Any, Dict

from base.request_client import RequestClient
from common.assertions import assert_response


def {test_func}(case: Dict[str, Any], client: RequestClient) -> None:
    \"\"\"
    YAML 驱动的测试用例：
    - case 来自 data/yaml/{sheet_name}.yaml
    \"\"\"
    method = case.get(\"method\", \"GET\")
    url = case[\"url\"]

    response = client.request(
        method=method,
        url=url,
        headers=case.get(\"headers\"),
        params=case.get(\"params\"),
        json=case.get(\"json\"),
        data=case.get(\"data\"),
    )

    assert_response(case, response)
"""


def generate_all(force: bool = False) -> List[Path]:
    """
    生成全部用例与 YAML。

    :param force: 是否覆盖已存在的 testcases 文件
    :return: 生成的测试文件路径列表
    """
    excel_path = settings.EXCEL_DIR / settings.EXCEL_MAIN
    if not excel_path.exists():
        raise FileNotFoundError(f"Excel 不存在：{excel_path}")

    xls = pd.ExcelFile(excel_path)
    created: List[Path] = []
    for sheet in xls.sheet_names:
        sheet_name = sheet.strip()
        if not sheet_name.startswith("test_"):
            continue

        # 生成 YAML
        export_sheet_to_yaml(excel_path, sheet_name, settings.YAML_DIR, yaml_name=sheet_name)

        # 生成 test 文件
        test_file = settings.BASE_DIR / "testcases" / f"{sheet_name}.py"
        if test_file.exists() and not force:
            continue

        test_content = TEST_TEMPLATE.format(sheet_name=sheet_name, test_func=sheet_name)
        test_file.write_text(test_content, encoding="utf-8")
        created.append(test_file)

    return created


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="自动生成 testcases 与 YAML")
    parser.add_argument("--force", action="store_true", help="覆盖已存在的测试文件")
    args = parser.parse_args()

    files = generate_all(force=args.force)
    for f in files:
        print(f"generated: {f}")
