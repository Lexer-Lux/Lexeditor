"""Every plugin serves the modules its page loads.

A page that links a module the service does not route is a blank editor with a
404 in the console, which is exactly what splitting these pages could have
caused. This starts each plugin's own service and asks it for the page and for
every module that page names.
"""
import re
import sys
import threading
import urllib.request
from http.server import HTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

# The service each plugin's page is served by, where it is not the plugin's own
# server module.
SERVERS = {"palworld": "games.palworld.build_server"}


def modules(page: str) -> list[str]:
    return (re.findall(r'<script src="(?!/shared/)/?([A-Za-z0-9_./-]+\.js)"', page)
            + re.findall(r'<link rel="stylesheet" href="(?!/shared/)/?([A-Za-z0-9_./-]+\.css)"', page))


def check(name: str) -> list[str]:
    import importlib
    module = importlib.import_module(SERVERS.get(name, f"games.{name}.server"))
    handler = getattr(module, "Handler", None)
    if handler is None:
        return [f"{name}: no request handler"]
    server = HTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    problems = []
    base = f"http://127.0.0.1:{server.server_port}"
    try:
        page = (ROOT / "games" / name / "editor.html").read_text(encoding="utf-8")
        for asset in modules(page):
            try:
                with urllib.request.urlopen(f"{base}/{asset.lstrip('/')}", timeout=10) as reply:
                    if not reply.read():
                        problems.append(f"{name}: {asset} served empty")
            except Exception as error:  # noqa: BLE001 - the failure is the result
                problems.append(f"{name}: {asset} -> {error}")
    finally:
        server.shutdown()
        server.server_close()
        thread.join()
    return problems


def main() -> int:
    problems = []
    for page in sorted((ROOT / "games").glob("*/editor.html")):
        problems += check(page.parent.name)
    if problems:
        print("FAIL:", *problems, sep="\n  ")
        return 1
    print("PASS: every plugin serves the modules its page loads")
    return 0


if __name__ == "__main__":
    sys.exit(main())
