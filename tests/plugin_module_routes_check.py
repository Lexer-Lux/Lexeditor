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
SERVERS = {"palworld": "plugins.palworld.build_server"}


def modules(page: str) -> list[str]:
    return (re.findall(r'<script src="(?!/shared/)/?([A-Za-z0-9_./-]+\.js)"', page)
            + re.findall(r'<link rel="stylesheet" href="(?!/shared/)/?([A-Za-z0-9_./-]+\.css)"', page))


def check(name: str) -> list[str]:
    import importlib
    module = importlib.import_module(SERVERS.get(name, f"plugins.{name}.server"))
    handler = getattr(module, "Handler", None)
    if handler is None:
        return [f"{name}: no request handler"]
    class Quiet(HTTPServer):
        # Closing the browser mid-request aborts the connection, and the default
        # handler prints a traceback for it. That is not a finding.
        def handle_error(self, request, client_address):
            return

    server = Quiet(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    problems = []
    base = f"http://127.0.0.1:{server.server_port}"
    try:
        page = (ROOT / "plugins" / name / "editor.html").read_text(encoding="utf-8")
        for asset in modules(page):
            # Browsers resolve a leading ./ before sending; request the same path.
            request = asset.lstrip('/')
            while request.startswith('./'):
                request = request[2:]
            try:
                with urllib.request.urlopen(f"{base}/{request}", timeout=10) as reply:
                    if not reply.read():
                        problems.append(f"{name}: {asset} served empty")
            except Exception as error:  # noqa: BLE001 - the failure is the result
                problems.append(f"{name}: {asset} -> {error}")
        problems += boot(base, name)
    finally:
        server.shutdown()
        server.server_close()
        thread.join()
    return problems


def boot(base: str, name: str) -> list[str]:
    """Load the page and report anything the modules said on the way up.

    A module that runs before the one it reads from says so here - "X is not
    defined" - which a served-file check cannot see.
    """
    from playwright.sync_api import sync_playwright
    fatal = []
    with sync_playwright() as play:
        browser = play.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1280, "height": 800})
        page.on("pageerror", lambda error: fatal.append(str(error)))
        try:
            page.goto(base + "/", wait_until="domcontentloaded", timeout=20000)
            page.wait_for_timeout(900)
        except Exception as error:  # noqa: BLE001 - the failure is the result
            fatal.append(str(error))
        browser.close()
    # A plugin without its game data still loads its modules; what matters here
    # is whether they could see each other.
    return [f"{name}: {message}" for message in fatal
            if "is not defined" in message or "SyntaxError" in message
            or "is not a function" in message]


def main() -> int:
    problems = []
    for page in sorted((ROOT / "plugins").glob("*/editor.html")):
        problems += check(page.parent.name)
    if problems:
        print("FAIL:", *problems, sep="\n  ")
        return 1
    print("PASS: every plugin serves the modules its page loads")
    return 0


if __name__ == "__main__":
    sys.exit(main())
