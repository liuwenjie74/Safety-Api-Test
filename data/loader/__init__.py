# -*- coding: utf-8 -*-
"""Loader utilities for Excel/YAML sync and testcase generation."""
from __future__ import annotations

from importlib import import_module
from typing import Any


_EXPORTS = {
    "export_excel_to_yaml": ("data.loader.excel_to_yaml", "export_excel_to_yaml"),
    "export_sheet_to_yaml": ("data.loader.excel_to_yaml", "export_sheet_to_yaml"),
    "ensure_yaml_for_test": ("data.loader.hot_loader", "ensure_yaml_for_test"),
    "sync_all_excels": ("data.loader.hot_loader", "sync_all_excels"),
    "generate_excel_template": (
        "data.loader.template_generator",
        "generate_excel_template",
    ),
    "generate_default_template": (
        "data.loader.template_generator",
        "generate_default_template",
    ),
    "generate_all": ("data.loader.test_generator", "generate_all"),
}

__all__ = list(_EXPORTS)


def __getattr__(name: str) -> Any:
    """Lazily import loader helpers to avoid package import side effects."""
    if name not in _EXPORTS:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

    module_name, attr_name = _EXPORTS[name]
    value = getattr(import_module(module_name), attr_name)
    globals()[name] = value
    return value
