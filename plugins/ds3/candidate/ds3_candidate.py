r"""Isolated launcher for the DS3 PR candidate.

This bypasses global plugin discovery and opens only the Dark Souls III plugin.
It never runs Lexeditor's normal C:\Lexeditor installer.
"""
from __future__ import annotations

import argparse

from runtime_bootstrap import bootstrap_environment

bootstrap_environment()

from plugins.ds3.plugin import PLUGIN
from plugin_api import validate_plugin


def check() -> int:
    validate_plugin(PLUGIN)
    problems = PLUGIN.check()
    if problems:
        for problem in problems:
            print(f"FAIL: {problem}")
        return 1
    print("PASS: Dark Souls III plugin descriptor and packaged support files are valid")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    if args.check:
        return check()
    result = check()
    if result:
        return result
    from desktop_host import run_host
    return int(run_host({"ds3": PLUGIN}, "ds3") or 0)


if __name__ == "__main__":
    raise SystemExit(main())
