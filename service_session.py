"""Shared lifecycle for plugin-owned local services."""

from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Callable
from runtime_bootstrap import service_command


def free_port(configured_name: str | None = None) -> int:
    configured = os.environ.get(configured_name, "") if configured_name else ""
    if configured:
        port = int(configured)
        if not 0 <= port <= 65535:
            raise ValueError(f"{configured_name} must be between 0 and 65535")
        if port:
            return port
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
        listener.bind(("127.0.0.1", 0))
        return int(listener.getsockname()[1])


def request_json(url: str, body: dict | None = None) -> dict:
    data = None if body is None else json.dumps(body).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=data,
        method="GET" if body is None else "POST",
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(request, timeout=10) as response:
        return json.loads(response.read().decode("utf-8"))


class LocalPluginSession:
    """One hidden loopback service owned by the Lexeditor window."""

    def __init__(self, *, module: str, plugin_id: str, app_root: Path,
                 check: Callable[[], list[str]], port_env: str | None = None,
                 extra_env: dict[str, str] | None = None):
        self.module = module
        self.plugin_id = plugin_id
        self.app_root = app_root
        self.check = check
        self.port = free_port(port_env)
        self.url = f"http://127.0.0.1:{self.port}/"
        self.extra_env = extra_env or {}
        self.process: subprocess.Popen[str] | None = None

    def start(self) -> dict:
        problems = self.check()
        if problems:
            raise RuntimeError("\n".join(problems))
        environment = os.environ.copy()
        environment.update(self.extra_env)
        environment["LEXEDITOR_PORT"] = str(self.port)
        environment["LEXEDITOR_PLUGIN_HOSTED"] = "1"
        environment["LEXEDITOR_WINDOW_HOST"] = "webview2"
        creation_flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
        self.process = subprocess.Popen(
            service_command(self.module),
            cwd=str(self.app_root),
            env=environment,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            creationflags=creation_flags,
        )
        deadline = time.monotonic() + 15.0
        last_error = "service did not answer"
        while time.monotonic() < deadline:
            if self.process.poll() is not None:
                output = self.process.communicate()[0].strip()
                raise RuntimeError(output or f"{self.plugin_id} service exited with {self.process.returncode}")
            try:
                identity = request_json(self.url + "api/plugin")
                if identity.get("pluginId") != self.plugin_id or not identity.get("hosted"):
                    raise RuntimeError(f"{self.plugin_id} service returned the wrong identity")
                return identity
            except (OSError, RuntimeError, ValueError, urllib.error.URLError) as error:
                last_error = str(error)
                time.sleep(0.05)
        self.stop()
        raise RuntimeError(f"{self.plugin_id} service did not become ready: {last_error}")

    def stop(self) -> None:
        if not self.process:
            return
        try:
            if self.process.poll() is None:
                self.process.terminate()
                try:
                    self.process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    self.process.kill()
                    self.process.wait(timeout=5)
        finally:
            if self.process.stdout is not None:
                self.process.stdout.close()

    def wait_closed(self, timeout: float = 2.0) -> bool:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
                probe.settimeout(0.2)
                if probe.connect_ex(("127.0.0.1", self.port)) != 0:
                    return True
            time.sleep(0.05)
        return False

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, _kind, _value, _traceback):
        self.stop()
