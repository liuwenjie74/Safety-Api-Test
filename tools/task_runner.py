# -*- coding: utf-8 -*-
"""Command-line helper for generate/test/Allure tasks."""
from __future__ import annotations

from pathlib import Path
from typing import List, Sequence
import argparse
import os
import shutil
import subprocess
import sys


ROOT_DIR = Path(__file__).resolve().parents[1]


def _build_env(env_name: str) -> dict:
    env = os.environ.copy()
    env["ENV"] = env_name
    return env


def _run(command: Sequence[str], env_name: str) -> None:
    result = subprocess.run(command, cwd=ROOT_DIR, env=_build_env(env_name), check=False)
    if result.returncode != 0:
        raise SystemExit(result.returncode)


def _allure_command() -> str:
    command = shutil.which("allure")
    if not command:
        raise SystemExit("allure command was not found in PATH.")
    return command


def generate(env_name: str, force: bool = True) -> None:
    command: List[str] = [sys.executable, "-m", "data.loader.test_generator"]
    if force:
        command.append("--force")
    _run(command, env_name)


def test(env_name: str, extra_args: Sequence[str] | None = None) -> None:
    command: List[str] = [sys.executable, "-m", "pytest", "-q"]
    if extra_args:
        command.extend(extra_args)
    _run(command, env_name)


def allure_results(env_name: str) -> None:
    _run(
        [
            sys.executable,
            "-m",
            "pytest",
            "-q",
            "--alluredir=allure-results",
            "--clean-alluredir",
        ],
        env_name,
    )


def generate_report(env_name: str) -> None:
    _run(
        [
            _allure_command(),
            "generate",
            "allure-results",
            "-o",
            "allure-report",
            "--clean",
        ],
        env_name,
    )


def open_report(env_name: str) -> None:
    _run([_allure_command(), "open", "allure-report"], env_name)


def serve_report(env_name: str) -> None:
    _run([_allure_command(), "serve", "allure-results"], env_name)


def ci(env_name: str) -> None:
    generate(env_name=env_name, force=True)
    allure_results(env_name=env_name)
    generate_report(env_name=env_name)


def main() -> None:
    parser = argparse.ArgumentParser(description="Framework task runner.")
    parser.add_argument(
        "command",
        choices=["generate", "test", "allure", "report", "open", "serve", "ci"],
        help="Task to execute.",
    )
    parser.add_argument(
        "--env",
        default=os.getenv("ENV", "dev"),
        help="Target environment name, for example dev or prod.",
    )
    parser.add_argument(
        "--no-force",
        action="store_true",
        help="Do not overwrite existing generated testcase files.",
    )
    parser.add_argument(
        "pytest_args",
        nargs="*",
        help="Extra pytest arguments when command=test.",
    )
    args = parser.parse_args()

    if args.command == "generate":
        generate(env_name=args.env, force=not args.no_force)
        return

    if args.command == "test":
        generate(env_name=args.env, force=not args.no_force)
        test(env_name=args.env, extra_args=args.pytest_args)
        return

    if args.command == "allure":
        generate(env_name=args.env, force=not args.no_force)
        allure_results(env_name=args.env)
        return

    if args.command == "report":
        ci(env_name=args.env)
        return

    if args.command == "open":
        open_report(env_name=args.env)
        return

    if args.command == "serve":
        generate(env_name=args.env, force=not args.no_force)
        allure_results(env_name=args.env)
        serve_report(env_name=args.env)
        return

    if args.command == "ci":
        ci(env_name=args.env)


if __name__ == "__main__":
    main()
