"""Asynchronous, private cache for Steam library box art."""

from __future__ import annotations

from io import BytesIO
import base64
import os
from pathlib import Path
import tempfile
import threading
import urllib.request
from typing import Callable

from PIL import Image

from plugin_api import GamePlugin


ROOT = Path(os.environ.get("LOCALAPPDATA", Path(__file__).resolve().parent / "out")) / "Lexeditor" / "cover-art"
MAX_COVER_BYTES = 5 * 1024 * 1024
TRANSITION_COVER_SIZE = (320, 480)
TRANSITION_JPEG_QUALITY = 72
CoverFetcher = Callable[[str], bytes]


def _url(app_id: str) -> str:
    return f"https://cdn.cloudflare.steamstatic.com/steam/apps/{app_id}/library_600x900.jpg"


def _validate(payload: bytes) -> tuple[int, int]:
    if len(payload) > MAX_COVER_BYTES:
        raise ValueError("cover art is larger than 5 MB")
    with Image.open(BytesIO(payload)) as image:
        image.verify()
    with Image.open(BytesIO(payload)) as image:
        if image.format != "JPEG":
            raise ValueError("Steam cover art is not a JPEG")
        width, height = image.size
    if width < 300 or height < 450 or height <= width:
        raise ValueError(f"Steam cover art has an unexpected size: {width} x {height}")
    return width, height


def _valid_file(path: Path) -> tuple[int, int] | None:
    if not path.is_file():
        return None
    try:
        return _validate(path.read_bytes())
    except (OSError, ValueError):
        return None


def _fetch(url: str) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": "Lexeditor/1.0"})
    with urllib.request.urlopen(request, timeout=20) as response:
        content_type = response.headers.get_content_type()
        if content_type != "image/jpeg":
            raise ValueError(f"Steam returned {content_type}, not image/jpeg")
        length = response.headers.get("Content-Length")
        if length and int(length) > MAX_COVER_BYTES:
            raise ValueError("cover art is larger than 5 MB")
        payload = response.read(MAX_COVER_BYTES + 1)
    return payload


def _steam_roots() -> tuple[Path, ...]:
    """Return bounded Steam client roots that can own local library artwork."""
    roots: list[Path] = []
    try:
        import winreg
        for hive, key_name, value_name in (
            (winreg.HKEY_CURRENT_USER, r"Software\Valve\Steam", "SteamPath"),
            (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Valve\Steam", "InstallPath"),
            (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Valve\Steam", "InstallPath"),
        ):
            try:
                with winreg.OpenKey(hive, key_name) as key:
                    roots.append(Path(winreg.QueryValueEx(key, value_name)[0]))
            except OSError:
                pass
    except ImportError:
        pass
    unique: list[Path] = []
    for root in roots:
        resolved = root.expanduser()
        if resolved not in unique:
            unique.append(resolved)
    return tuple(unique)


def _local_steam_cover(app_id: str, roots: tuple[Path, ...]) -> Path | None:
    """Find Steam's validated portrait capsule without scanning a whole library."""
    for root in roots:
        cache = root / "appcache" / "librarycache"
        direct = (
            cache / f"{app_id}_library_600x900.jpg",
            cache / app_id / "library_600x900.jpg",
        )
        candidates = list(direct)
        app_cache = cache / app_id
        if app_cache.is_dir():
            candidates.extend(app_cache.glob("*/library_capsule.jpg"))
        for candidate in candidates:
            if _valid_file(candidate):
                return candidate
    return None


def _save_payload(target: Path, payload: bytes) -> None:
    """Atomically replace one private cached image."""
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="wb", delete=False, dir=target.parent,
            prefix=f".{target.name}.", suffix=".tmp",
        ) as stream:
            temporary = Path(stream.name)
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        temporary.replace(target)
        temporary = None
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def _packaged_dimensions(path: Path) -> tuple[int, int] | None:
    if path.suffix.casefold() == ".svg":
        try:
            text = path.read_text(encoding="utf-8")
        except OSError:
            return None
        return (600, 900) if "<svg" in text and len(text.encode("utf-8")) <= MAX_COVER_BYTES else None
    if path.suffix.casefold() in {".png", ".webp"}:
        try:
            with Image.open(path) as image:
                image.verify()
            with Image.open(path) as image:
                width, height = image.size
            return (width, height) if width >= 300 and height >= 450 and height > width else None
        except (OSError, ValueError):
            return None
    return _valid_file(path)


class CoverArtCache:
    """Download each declared Steam cover once without blocking the chooser."""

    def __init__(self, plugins: dict[str, GamePlugin], root: Path | None = None,
                 fetcher: CoverFetcher = _fetch, auto_download: bool = True,
                 steam_roots: tuple[Path, ...] | None = None):
        self.root = Path(root or ROOT)
        self._plugins = plugins
        self._fetcher = fetcher
        self._lock = threading.RLock()
        self._states: dict[str, dict] = {}
        self._paths: dict[str, Path] = {}
        self._threads: list[threading.Thread] = []
        local_roots = _steam_roots() if steam_roots is None else tuple(steam_roots)
        for plugin_id, plugin in plugins.items():
            if plugin.cover_art is not None:
                dimensions = _packaged_dimensions(plugin.cover_art)
                if dimensions:
                    self._paths[plugin_id] = plugin.cover_art
                    self._states[plugin_id] = self._state(
                        "ready", plugin.cover_art.as_uri(), plugin.cover_art.as_uri(), dimensions,
                    )
                else:
                    self._states[plugin_id] = self._state(
                        "missing", "", plugin.cover_art.as_uri(), error="Packaged cover art is invalid",
                    )
                continue
            specification = plugin.installation
            if specification is None:
                self._states[plugin_id] = self._state("unavailable", "", "")
                continue
            app_id = specification.steam_app_id
            target = self.root / f"{plugin_id}-{app_id}.jpg"
            dimensions = _valid_file(target)
            if dimensions:
                self._paths[plugin_id] = target
                self._states[plugin_id] = self._state(
                    "ready", target.as_uri(), _url(app_id), dimensions,
                )
            elif local_cover := _local_steam_cover(app_id, local_roots):
                payload = local_cover.read_bytes()
                dimensions = _validate(payload)
                _save_payload(target, payload)
                self._paths[plugin_id] = target
                self._states[plugin_id] = self._state(
                    "ready", target.as_uri(), local_cover.as_uri(), dimensions,
                )
            elif auto_download:
                self._states[plugin_id] = self._state("loading", "", _url(app_id))
                thread = threading.Thread(
                    target=self._download,
                    args=(plugin_id, target, _url(app_id)),
                    daemon=True,
                    name=f"lexeditor-cover-{plugin_id}",
                )
                self._threads.append(thread)
                thread.start()
            else:
                self._states[plugin_id] = self._state("missing", "", _url(app_id))

    @staticmethod
    def _state(state: str, uri: str, source: str,
               dimensions: tuple[int, int] | None = None, error: str = "") -> dict:
        return {
            "state": state,
            "uri": uri,
            "source": source,
            "width": dimensions[0] if dimensions else 0,
            "height": dimensions[1] if dimensions else 0,
            "error": error,
        }

    def _download(self, plugin_id: str, target: Path, url: str) -> None:
        try:
            payload = self._fetcher(url)
            dimensions = _validate(payload)
            _save_payload(target, payload)
            state = self._state("ready", target.as_uri(), url, dimensions)
        except Exception as error:
            state = self._state("missing", "", url, error=str(error))
        with self._lock:
            if state["state"] == "ready":
                self._paths[plugin_id] = target
            self._states[plugin_id] = state

    def snapshot(self, plugin_id: str) -> dict:
        with self._lock:
            return dict(self._states.get(plugin_id, self._state("unavailable", "", "")))

    def data_uri(self, plugin_id: str) -> str:
        """Return one ready cached cover for a self-contained UI transition."""
        state = self.snapshot(plugin_id)
        if state.get("state") != "ready":
            return ""
        target = self._paths.get(plugin_id)
        if target is None or _packaged_dimensions(target) is None:
            return ""
        # The transition is visible for only a fraction of a second. Embed a
        # bounded display-size JPEG instead of every original cover. Full-size
        # files made the combined menu HTML exceed the host limit and blocked
        # every plugin from opening.
        try:
            with Image.open(target) as source:
                image = source.convert("RGB")
                image.thumbnail(TRANSITION_COVER_SIZE, Image.Resampling.LANCZOS)
                output = BytesIO()
                image.save(
                    output, format="JPEG", quality=TRANSITION_JPEG_QUALITY,
                    optimize=True, progressive=True,
                )
                payload = output.getvalue()
        except (OSError, ValueError):
            return ""
        encoded = base64.b64encode(payload).decode("ascii")
        return f"data:image/jpeg;base64,{encoded}"

    def wait(self, timeout: float = 30) -> bool:
        for thread in self._threads:
            thread.join(timeout)
        return all(not thread.is_alive() for thread in self._threads)
