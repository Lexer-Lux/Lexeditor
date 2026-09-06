#!/usr/bin/env python3
"""Lexeditor desktop shell and game-plugin launcher."""

from __future__ import annotations

import argparse
import ctypes
import importlib
import sys
from pathlib import Path

from runtime_bootstrap import bootstrap_environment, dispatch_service
bootstrap_environment()

from desktop_host import run_host, smoke_host_switch
from plugin_api import GamePlugin, validate_plugin


ROOT = Path(__file__).resolve().parent


def discover_plugins() -> dict[str, GamePlugin]:
    plugins: dict[str, GamePlugin] = {}
    for directory in sorted((ROOT / "games").iterdir()):
        if not directory.is_dir() or not (directory / "plugin.py").is_file():
            continue
        module = importlib.import_module(f"games.{directory.name}.plugin")
        plugin = getattr(module, "PLUGIN", None)
        if not isinstance(plugin, GamePlugin):
            raise TypeError(f"games/{directory.name}/plugin.py does not export GamePlugin PLUGIN")
        validate_plugin(plugin)
        if plugin.plugin_id in plugins:
            raise ValueError(f"duplicate plugin id: {plugin.plugin_id}")
        plugins[plugin.plugin_id] = plugin
    if not plugins:
        raise RuntimeError("Lexeditor found no game plugins")
    return plugins


def _print_health(plugins: dict[str, GamePlugin]) -> int:
    failed = False
    for plugin in plugins.values():
        problems = plugin.check()
        if problems:
            failed = True
            print(f"{plugin.plugin_id}: unavailable")
            for problem in problems:
                print(f"  {problem}")
        else:
            print(f"{plugin.plugin_id}: ready")
    return 1 if failed else 0


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if dispatch_service(argv):
        return 0
    parser = argparse.ArgumentParser(description="Lexeditor game-plugin shell")
    parser.add_argument("--game", help="open or inspect one plugin")
    parser.add_argument("--list", action="store_true", help="list discovered plugins")
    parser.add_argument("--check", action="store_true", help="check plugin paths")
    parser.add_argument("--smoke", action="store_true", help="run the selected plugin's safe smoke test")
    parser.add_argument("--smoke-host", action="store_true", help="test two editable plugins in one hidden WebView2 window")
    parser.add_argument("--smoke-service", metavar="RESULT", help="test the bundled Blank child service without game files")
    args = parser.parse_args(argv)
    plugins = discover_plugins()
    if args.smoke_service:
        import json
        session = plugins["blank"].session_factory()
        try:
            identity = session.start()
            if identity.get("pluginId") != "blank":
                raise RuntimeError("Wrong bundled service identity")
        finally:
            session.stop()
        if not session.wait_closed():
            raise RuntimeError("Bundled child service did not stop")
        Path(args.smoke_service).write_text(json.dumps({"passed": True, "plugins": list(plugins), "identity": identity, "childStopped": True}), encoding="utf-8")
        return 0
    selected = {args.game: plugins[args.game]} if args.game in plugins else plugins
    if args.game and args.game not in plugins:
        parser.error(f"unknown game plugin: {args.game}")
    if args.list:
        for plugin in selected.values():
            print(f"{plugin.plugin_id}\t{plugin.name}")
        return 0
    if args.check:
        return _print_health(selected)
    if args.smoke:
        if len(selected) != 1:
            parser.error("--smoke requires --game")
        plugin = next(iter(selected.values()))
        if not plugin.smoke:
            parser.error(f"{plugin.plugin_id} has no smoke test")
        for line in plugin.smoke():
            print(f"PASS: {line}")
        return 0
    if args.smoke_host:
        if args.game:
            parser.error("--smoke-host selects its editable plugins; do not use --game")
        if len(plugins) < 2:
            parser.error("--smoke-host requires at least two plugins")
        plugin_ids = [plugin_id for plugin_id, plugin in plugins.items() if plugin.projects is not None]
        if len(plugin_ids) < 2:
            parser.error("--smoke-host requires two plugins with editable project controls")
        for line in smoke_host_switch(plugins, plugin_ids[0], plugin_ids[1]):
            print(f"PASS: {line}")
        return 0
    return run_host(plugins, args.game)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        if "pythonw" in Path(sys.executable).name.casefold():
            ctypes.windll.user32.MessageBoxW(0, str(error), "Lexeditor", 0x10)
        else:
            raise
