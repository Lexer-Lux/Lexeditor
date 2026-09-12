"""A small Chrome DevTools Protocol client for Lexeditor's browser verifiers.

Ninety-nine verifiers drive a headless browser, and every one of them used to
import this from a module sitting outside the repository, on one developer's
machine. That made those checks unrunnable anywhere else, which is the whole
reason they could not run on GitHub. The code lives here now so a checkout is
enough to run them.

The out-of-repo module is still preferred when it is present, so nothing about
how these verifiers behave on that machine changes; see
`render_crime_editors_55_62.py` beside this file for the shim that arranges it.
"""

from __future__ import annotations

import base64
import json
import os
from pathlib import Path
import socket
import sys
import tempfile
import time
from urllib.request import urlopen

import websocket

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "worklog" / "issues" / "rendered"

# Every verifier spawns its own browser. Popen only ever kills the process it
# was handed, orphaning the browser's child renderers, and a `finally` does not
# run when a script is stopped by a timeout, so browsers accumulated until the
# machine froze. Installing the job object here fixes every verifier at once,
# including ones not yet written, because the kernel does the killing.
sys.path.insert(0, str(ROOT / "tools"))
try:  # a missing guard must never stop a verifier running
    import browser_guard

    browser_guard.install_autoadopt()
except Exception:
    pass


def free_port() -> int:
    """Return a port no other verifier is about to take.

    Binding port 0, closing the socket and returning the number is a race: the
    port is free again the instant it is reported, so with verifiers running in
    parallel two of them get the same one, the loser never brings its server up,
    and it dies later on a timeout that looks like an unrelated flake. The port
    is therefore claimed with an exclusive lock file, which works across
    processes rather than only across threads.
    """
    claims = Path(tempfile.gettempdir()) / "lexeditor-ports"
    claims.mkdir(parents=True, exist_ok=True)
    now = time.time()
    for stale in claims.glob("*.port"):
        try:
            if now - stale.stat().st_mtime > 900:
                stale.unlink()  # a crashed run must not sterilise a port
        except OSError:
            pass
    for _ in range(200):
        with socket.socket() as sock:
            sock.bind(("127.0.0.1", 0))
            port = int(sock.getsockname()[1])
        claim = claims / f"{port}.port"
        try:
            handle = os.open(str(claim), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError:
            continue  # another verifier already holds this one
        os.write(handle, str(os.getpid()).encode())
        os.close(handle)
        return port
    raise RuntimeError("no free port could be claimed")


def wait_json(url: str, timeout: float = 30.0):
    deadline = time.time() + timeout
    error = None
    while time.time() < deadline:
        try:
            with urlopen(url, timeout=2) as response:
                return json.load(response)
        except Exception as ex:  # process startup races are expected
            error = ex
            time.sleep(0.15)
    raise RuntimeError(f"timed out waiting for {url}: {error}")


class Cdp:
    def __init__(self, url: str):
        self.ws = websocket.create_connection(url, timeout=60, suppress_origin=True)
        self.ident = 0

    def call(self, method: str, params: dict | None = None):
        self.ident += 1
        ident = self.ident
        self.ws.send(json.dumps({"id": ident, "method": method, "params": params or {}}))
        while True:
            message = json.loads(self.ws.recv())
            if message.get("id") != ident:
                continue
            if "error" in message:
                raise RuntimeError(f"{method}: {message['error']}")
            return message.get("result", {})

    def eval(self, expression: str, await_promise: bool = False):
        result = self.call("Runtime.evaluate", {
            "expression": expression,
            "awaitPromise": await_promise,
            "returnByValue": True,
        })["result"]
        if result.get("subtype") == "error":
            raise RuntimeError(result.get("description", "browser evaluation failed"))
        return result.get("value")

    def close(self):
        self.ws.close()


def wait_eval(cdp: Cdp, expression: str, timeout: float = 45.0):
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            if cdp.eval(expression):
                return
        except Exception:
            pass
        time.sleep(0.2)
    raise AssertionError(f"browser condition timed out: {expression}")


def screenshot(cdp: Cdp, name: str, width: int, height: int):
    cdp.call("Emulation.setDeviceMetricsOverride", {
        "width": width, "height": height, "deviceScaleFactor": 1, "mobile": False,
    })
    time.sleep(0.2)
    payload = cdp.call("Page.captureScreenshot", {
        "format": "png", "captureBeyondViewport": True, "fromSurface": True,
    })
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / name
    path.write_bytes(base64.b64decode(payload["data"]))
    return path
