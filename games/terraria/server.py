"""Loopback service for Terraria / tModLoader source projects."""

from __future__ import annotations

from hashlib import sha256
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import mimetypes
import os
from pathlib import Path
import subprocess
import tempfile
import threading
from urllib.parse import parse_qs, urlparse

from .build_metadata import BOOLEAN_KEYS, parse_build_text, update_build_text
from .localization import apply_localization_changes, parse_localization_text, try_get_culture_and_prefix
from .plugin import DEFAULT_PROJECT_ROOT, TMODLOADER_SAVE_ROOT


ROOT = Path(__file__).resolve().parents[2]
PLUGIN_ROOT = Path(__file__).resolve().parent
PORT = int(os.environ.get("LEXEDITOR_PORT", "0"))
MAX_BODY = 64 * 1024
MAX_REQUEST_BODY = 512 * 1024
MAX_LOCALIZATION = 2 * 1024 * 1024
MAX_BUILD_OUTPUT = 64 * 1024
MAX_ENABLED_STATE = 1024 * 1024
BUILD_TIMEOUT_SECONDS = 15 * 60
UTF8_BOM = b"\xef\xbb\xbf"
_BUILD_LOCK = threading.Lock()


def project_root() -> Path:
    return Path(os.environ.get("LEXEDITOR_TERRARIA_PROJECT", DEFAULT_PROJECT_ROOT)).resolve()


def _build_file() -> Path:
    root = project_root()
    target = (root / "build.txt").resolve()
    if root != target.parent:
        raise ValueError("Invalid build.txt path")
    return target


def _read_build() -> tuple[bytes, str]:
    target = _build_file()
    data = target.read_bytes()
    if len(data) > MAX_BODY:
        raise ValueError("build.txt is too large for structured editing")
    try:
        text = data.decode("utf-8-sig")
    except UnicodeDecodeError as error:
        raise ValueError("build.txt is not UTF-8 text") from error
    return data, text


def build_state() -> dict:
    data, text = _read_build()
    parsed = parse_build_text(text)
    values: dict[str, object] = dict(parsed.values)
    for key in BOOLEAN_KEYS:
        if key in values:
            values[key] = str(values[key]).casefold() == "true"
    return {
        "path": "build.txt",
        "sha256": sha256(data).hexdigest(),
        "values": values,
        "duplicates": list(parsed.duplicates),
        "editable": not bool(parsed.duplicates),
    }


def _atomic_replace(target: Path, data: bytes) -> None:
    temp_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile("wb", dir=target.parent, prefix=".lexeditor-", delete=False) as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
            temp_path = Path(handle.name)
        os.replace(temp_path, target)
        temp_path = None
    finally:
        if temp_path is not None:
            temp_path.unlink(missing_ok=True)


def save_build(updates: dict[str, object], expected_sha256: str) -> dict:
    target = _build_file()
    data, text = _read_build()
    current_sha = sha256(data).hexdigest()
    if expected_sha256 != current_sha:
        raise ValueError("build.txt changed outside Lexeditor; reload before saving")

    changed = update_build_text(text, updates)
    if changed == text:
        return build_state()

    encoded = (UTF8_BOM if data.startswith(UTF8_BOM) else b"") + changed.encode("utf-8")
    _atomic_replace(target, encoded)
    return build_state()


def _localization_target(relative: str) -> Path:
    if not isinstance(relative, str) or not relative.strip():
        raise ValueError("Localization path is required")
    root = project_root()
    target = (root / relative).resolve()
    if target == root or root not in target.parents or target.suffix.casefold() != ".hjson":
        raise ValueError("Invalid localization path")
    return target


def _read_localization(relative: str) -> tuple[Path, bytes, str, str, str | None, str]:
    root = project_root()
    target = _localization_target(relative)
    if not target.is_file():
        raise ValueError("Localization file does not exist")
    data = target.read_bytes()
    if len(data) > MAX_LOCALIZATION:
        raise ValueError("Localization file is too large for structured editing")
    try:
        text = data.decode("utf-8-sig")
    except UnicodeDecodeError as error:
        raise ValueError("Localization file is not UTF-8 text") from error
    canonical = target.relative_to(root).as_posix()
    culture_info = try_get_culture_and_prefix(canonical)
    culture, prefix = culture_info if culture_info is not None else (None, "")
    return target, data, text, canonical, culture, prefix


def localization_file_state(relative: str) -> dict:
    _target, data, text, canonical, culture, prefix = _read_localization(relative)
    document = parse_localization_text(text, prefix)
    file_editable = culture is not None and not document.duplicates
    entries = []
    for entry in document.entries:
        payload = entry.public()
        payload["editable"] = bool(payload["editable"] and file_editable)
        entries.append(payload)
    return {
        "path": canonical,
        "sha256": sha256(data).hexdigest(),
        "culture": culture,
        "prefix": prefix,
        "loadable": culture is not None,
        "editable": file_editable,
        "duplicates": list(document.duplicates),
        "unsupported": document.unsupported,
        "entries": entries,
    }


def localization_index() -> dict:
    root = project_root()
    files: list[dict] = []
    if not root.is_dir():
        return {"root": str(root), "files": files}
    ignored = {".git", ".pytest_cache", "__pycache__", "out", "obj", "bin"}
    candidates = sorted(
        (
            path for path in root.rglob("*.hjson")
            if path.is_file() and not ignored.intersection(path.relative_to(root).parts)
        ),
        key=lambda path: path.relative_to(root).as_posix().casefold(),
    )
    for path in candidates:
        relative = path.relative_to(root).as_posix()
        try:
            state = localization_file_state(relative)
            files.append({
                "path": state["path"],
                "culture": state["culture"],
                "prefix": state["prefix"],
                "loadable": state["loadable"],
                "editable": state["editable"],
                "entries": len(state["entries"]),
                "editableEntries": sum(1 for entry in state["entries"] if entry["editable"]),
                "duplicates": state["duplicates"],
                "unsupported": state["unsupported"],
                "error": "",
            })
        except (OSError, ValueError) as error:
            files.append({
                "path": relative,
                "culture": None,
                "prefix": "",
                "loadable": False,
                "editable": False,
                "entries": 0,
                "editableEntries": 0,
                "duplicates": [],
                "unsupported": 0,
                "error": str(error),
            })
    return {"root": str(root), "files": files}


def save_localization(
    relative: str,
    updates: dict[str, object],
    expected_sha256: str,
    creates: dict[str, object] | None = None,
) -> dict:
    target, data, text, canonical, culture, prefix = _read_localization(relative)
    if culture is None:
        raise ValueError("Localization filename does not identify a tModLoader culture")
    current_sha = sha256(data).hexdigest()
    if expected_sha256 != current_sha:
        raise ValueError(f"{canonical} changed outside Lexeditor; reload before saving")
    changed = apply_localization_changes(text, updates, creates or {}, prefix)
    if changed == text:
        return localization_file_state(canonical)
    encoded = (UTF8_BOM if data.startswith(UTF8_BOM) else b"") + changed.encode("utf-8")
    _atomic_replace(target, encoded)
    return localization_file_state(canonical)


def _installation_root() -> Path:
    configured = os.environ.get("LEXEDITOR_TERRARIA_ROOT", "").strip()
    if not configured:
        raise ValueError("tModLoader installation is not configured")
    root = Path(configured).resolve()
    required = (
        "tModLoader.dll",
        "LaunchUtils/busybox64.exe",
        "LaunchUtils/ScriptCaller.sh",
    )
    missing = [relative for relative in required if not (root / relative).is_file()]
    if not root.is_dir() or missing:
        detail = ", ".join(missing) if missing else str(root)
        raise ValueError(f"tModLoader build bootstrap is incomplete: {detail}")
    return root


def _source_project_root() -> Path:
    root = project_root()
    if not root.is_dir() or not (root / "build.txt").is_file():
        raise ValueError("The selected Terraria project is missing build.txt")
    if not any(path.is_file() for path in root.glob("*.csproj")):
        raise ValueError("The selected Terraria project has no .csproj file")
    return root


def _mods_root() -> Path:
    return Path(TMODLOADER_SAVE_ROOT).resolve() / "Mods"


def _artifact_path(project: Path) -> Path:
    return _mods_root() / f"{project.name}.tmod"


def local_mod_state(project: Path | None = None) -> dict:
    """Read tModLoader's local package/enabled state without mutating it."""
    selected = project_root() if project is None else Path(project).resolve()
    artifact = _artifact_path(selected)
    enabled_path = _mods_root() / "enabled.json"
    state = {
        "expectedArtifact": str(artifact),
        "artifactExists": artifact.is_file(),
        "enabled": False,
        "enabledStatePath": str(enabled_path),
        "enabledStateExists": False,
        "enabledStateValid": True,
        "enabledStateError": "",
    }
    try:
        data = enabled_path.read_bytes()
    except FileNotFoundError:
        return state
    except OSError as error:
        state["enabledStateValid"] = False
        state["enabledStateError"] = f"Could not read tModLoader enabled.json: {error}"
        return state

    state["enabledStateExists"] = True
    if len(data) > MAX_ENABLED_STATE:
        state["enabledStateValid"] = False
        state["enabledStateError"] = "tModLoader enabled.json is unexpectedly large"
        return state
    try:
        payload = json.loads(data.decode("utf-8-sig"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        state["enabledStateValid"] = False
        state["enabledStateError"] = f"Could not parse tModLoader enabled.json: {error}"
        return state
    if not isinstance(payload, list) or any(not isinstance(value, str) for value in payload):
        state["enabledStateValid"] = False
        state["enabledStateError"] = "tModLoader enabled.json must contain a JSON array of mod names"
        return state
    state["enabled"] = selected.name in set(payload)
    return state


def _trim_output(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        text = value.decode("utf-8", errors="replace")
    else:
        text = str(value)
    if len(text) <= MAX_BUILD_OUTPUT:
        return text
    return "[earlier output truncated]\n" + text[-MAX_BUILD_OUTPUT:]


def _read_log_tail(path: Path) -> str:
    try:
        data = path.read_bytes()
    except OSError:
        return ""
    if len(data) > MAX_BUILD_OUTPUT:
        data = data[-MAX_BUILD_OUTPUT:]
        prefix = b"[earlier output truncated]\n"
    else:
        prefix = b""
    return (prefix + data).decode("utf-8", errors="replace")


def build_status(platform_name: str | None = None) -> dict:
    platform_name = os.name if platform_name is None else platform_name
    project = project_root()
    payload = {
        "available": False,
        "building": _BUILD_LOCK.locked(),
        "project": str(project),
        "saveRoot": str(Path(TMODLOADER_SAVE_ROOT).resolve()),
        **local_mod_state(project),
        "reason": "",
    }
    if platform_name != "nt":
        payload["reason"] = "Native Terraria build handoff is supported on Windows only."
        return payload
    try:
        install = _installation_root()
        _source_project_root()
    except ValueError as error:
        payload["reason"] = str(error)
        return payload
    payload["installRoot"] = str(install)
    if payload["building"]:
        payload["reason"] = "A Terraria build is already running."
        return payload
    payload["available"] = True
    return payload


def _result_local_state(project: Path) -> dict:
    state = local_mod_state(project)
    state["artifact"] = state.pop("expectedArtifact")
    return state


def build_project(run_command=None, platform_name: str | None = None) -> dict:
    platform_name = os.name if platform_name is None else platform_name
    if platform_name != "nt":
        raise ValueError("Native Terraria build handoff is supported on Windows only.")

    install = _installation_root()
    project = _source_project_root()
    save_root = Path(TMODLOADER_SAVE_ROOT).resolve()
    artifact = _artifact_path(project)
    runner = subprocess.run if run_command is None else run_command

    if not _BUILD_LOCK.acquire(blocking=False):
        raise ValueError("A Terraria build is already running.")
    try:
        command = [
            str(install / "LaunchUtils" / "busybox64.exe"),
            "bash",
            "./LaunchUtils/ScriptCaller.sh",
            "-build",
            str(project),
            "-tmlsavedirectory",
            str(save_root),
        ]
        kwargs = {
            "cwd": str(install),
            "capture_output": True,
            "text": True,
            "encoding": "utf-8",
            "errors": "replace",
            "timeout": BUILD_TIMEOUT_SECONDS,
            "check": False,
            "creationflags": getattr(subprocess, "CREATE_NO_WINDOW", 0),
        }
        try:
            completed = runner(command, **kwargs)
            stdout = _trim_output(completed.stdout)
            stderr = _trim_output(completed.stderr)
            native_log = _read_log_tail(install / "tModLoader-Logs" / "Natives.log")
            state = _result_local_state(project)
            ok = completed.returncode == 0 and state["artifactExists"]
            result = {
                "ok": ok,
                "exitCode": int(completed.returncode),
                "timedOut": False,
                **state,
                "stdout": stdout,
                "stderr": stderr,
                "nativeLog": native_log,
            }
            if completed.returncode == 0 and not state["artifactExists"]:
                result["error"] = "tModLoader exited successfully but the expected .tmod was not found."
            return result
        except subprocess.TimeoutExpired as error:
            return {
                "ok": False,
                "exitCode": None,
                "timedOut": True,
                **_result_local_state(project),
                "stdout": _trim_output(error.stdout),
                "stderr": _trim_output(error.stderr),
                "nativeLog": _read_log_tail(install / "tModLoader-Logs" / "Natives.log"),
                "error": "tModLoader build exceeded Lexeditor's build timeout.",
            }
    finally:
        _BUILD_LOCK.release()


def data_map() -> dict:
    root = project_root()
    rows: list[dict] = []
    if not root.is_dir():
        return {"root": str(root), "rows": rows}
    for path in sorted((item for item in root.rglob("*") if item.is_file()), key=lambda p: str(p).casefold()):
        relative = path.relative_to(root).as_posix()
        suffix = path.suffix.casefold()
        if relative == "build.txt":
            status, family = "structured", "tModLoader metadata"
        elif suffix == ".cs":
            status, family = "recognized", "C# source"
        elif suffix == ".hjson":
            status, family = "structured", "Localization"
        elif relative.startswith("Content/"):
            status, family = "recognized", "Content asset"
        elif suffix == ".csproj":
            status, family = "recognized", "MSBuild project"
        else:
            status, family = "unknown", "Other"
        rows.append({"path": relative, "family": family, "status": status})
    return {"root": str(root), "rows": rows}


class Handler(BaseHTTPRequestHandler):
    def log_message(self, _format, *_args):
        return

    def send_json(self, payload, status=200):
        data = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def send_file(self, target: Path):
        data = target.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", mimetypes.guess_type(target.name)[0] or "application/octet-stream")
        self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def read_json(self) -> object:
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError as error:
            raise ValueError("Invalid Content-Length") from error
        if length <= 0 or length > MAX_REQUEST_BODY:
            raise ValueError("Invalid request size")
        try:
            return json.loads(self.rfile.read(length))
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise ValueError("Invalid JSON") from error

    @staticmethod
    def _query_path(parsed) -> str:
        values = parse_qs(parsed.query, keep_blank_values=True).get("path", [])
        if len(values) != 1 or not values[0]:
            raise ValueError("Localization path query is required")
        return values[0]

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        try:
            if path == "/":
                self.send_file(PLUGIN_ROOT / "editor.html")
            elif path.startswith("/shared/"):
                shared = (ROOT / "ui").resolve()
                target = (shared / path.removeprefix("/shared/")).resolve()
                if shared in target.parents and target.is_file():
                    self.send_file(target)
                else:
                    self.send_json({"error": "Shared UI asset not found"}, 404)
            elif path == "/api/plugin":
                self.send_json({
                    "apiVersion": 1,
                    "pluginId": "terraria",
                    "name": "Terraria",
                    "hosted": True,
                    "windowHost": "webview2",
                    "capabilities": [
                        "build-metadata", "localization", "native-build",
                        "local-mod-status", "data-map",
                    ],
                })
            elif path == "/api/build-metadata":
                self.send_json(build_state())
            elif path == "/api/localization":
                self.send_json(localization_index())
            elif path == "/api/localization/file":
                self.send_json(localization_file_state(self._query_path(parsed)))
            elif path == "/api/build":
                self.send_json(build_status())
            elif path == "/api/data-map":
                self.send_json(data_map())
            else:
                self.send_json({"error": "Not found"}, 404)
        except (OSError, ValueError) as error:
            self.send_json({"error": str(error)}, 400)

    def do_POST(self):
        parsed = urlparse(self.path)
        path = parsed.path
        try:
            if path == "/api/build":
                payload = self.read_json()
                if payload != {}:
                    raise ValueError("Terraria build request must be an empty object")
                self.send_json(build_project())
                return
            if path == "/api/localization/file":
                payload = self.read_json()
                if not isinstance(payload, dict):
                    raise ValueError("Invalid localization request")
                required = {"path", "updates", "expectedSha256"}
                allowed = required | {"creates"}
                if not required.issubset(payload) or not set(payload).issubset(allowed):
                    raise ValueError("Expected path, updates, optional creates and expectedSha256 only")
                relative = payload["path"]
                updates = payload["updates"]
                creates = payload.get("creates", {})
                expected = payload["expectedSha256"]
                if (
                    not isinstance(relative, str)
                    or not isinstance(updates, dict)
                    or not isinstance(creates, dict)
                    or not isinstance(expected, str)
                ):
                    raise ValueError("Invalid localization request")
                self.send_json(save_localization(relative, updates, expected, creates))
                return
            if path != "/api/build-metadata":
                self.send_json({"error": "Not found"}, 404)
                return
            payload = self.read_json()
            if not isinstance(payload, dict) or set(payload) != {"updates", "expectedSha256"}:
                raise ValueError("Expected updates and expectedSha256 only")
            updates = payload["updates"]
            expected = payload["expectedSha256"]
            if not isinstance(updates, dict) or not isinstance(expected, str):
                raise ValueError("Invalid build metadata request")
            self.send_json(save_build(updates, expected))
        except (OSError, ValueError) as error:
            self.send_json({"error": str(error)}, 400)


if __name__ == "__main__":
    ThreadingHTTPServer(("127.0.0.1", PORT), Handler).serve_forever()
