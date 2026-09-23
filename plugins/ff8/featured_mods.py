"""Discover and install featured FF8 mods without importing another loader."""

from __future__ import annotations

import fnmatch
import hashlib
import json
import os
from pathlib import Path
import re
import tempfile
from typing import Callable
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from . import iroj_archive, runtime_layout


CATALOG_FILE = Path(__file__).with_name("featured_mods.json")
MAX_RELEASE_DOCUMENT_BYTES = 2 * 1024 * 1024
MAX_MOD_BYTES = 8 * 1024 * 1024 * 1024
GITHUB_ASSET_HOSTS = {
    "github.com", "objects.githubusercontent.com",
    "release-assets.githubusercontent.com", "github-releases.githubusercontent.com",
}
JsonFetcher = Callable[[str], dict]
FileFetcher = Callable[[str, Path, int, str], str]


def _https_url(value: str, *, hosts: set[str]) -> str:
    parsed = urlparse(str(value).strip())
    if parsed.scheme != "https" or parsed.username or parsed.password:
        raise ValueError("Featured mod URLs must use HTTPS without embedded credentials")
    host = (parsed.hostname or "").casefold()
    if host not in hosts:
        raise ValueError(f"Featured mod URL host is not allowed: {host or '(missing)'}")
    return parsed.geturl()


def _github_repository(value: str) -> tuple[str, str, str]:
    url = _https_url(value, hosts={"github.com"})
    parts = [part for part in urlparse(url).path.split("/") if part]
    if len(parts) != 2:
        raise ValueError("A featured GitHub repository must identify one owner and repository")
    owner, repository = parts
    if repository.endswith(".git"):
        repository = repository[:-4]
    valid = re.compile(r"^[A-Za-z0-9_.-]+$")
    if not owner or not repository or not valid.fullmatch(owner) or not valid.fullmatch(repository):
        raise ValueError("The featured GitHub repository name is invalid")
    return owner, repository, f"https://github.com/{owner}/{repository}"


def _source(entry: dict) -> dict:
    source = entry.get("source")
    source = {"repository": source} if isinstance(source, str) else source
    if not isinstance(source, dict):
        raise ValueError(f"Featured mod {entry.get('id', '(unknown)')} has no source repository")
    owner, repository, repository_url = _github_repository(str(source.get("repository", "")))
    expected_feed = f"https://api.github.com/repos/{owner}/{repository}/releases/latest"
    feed = str(source.get("releaseFeed") or expected_feed)
    feed = _https_url(feed, hosts={"api.github.com"})
    if feed.rstrip("/").casefold() != expected_feed.casefold():
        raise ValueError("The featured release feed must match its GitHub repository")
    pattern = str(source.get("assetPattern") or "*.iroj")
    if not pattern or "/" in pattern or "\\" in pattern:
        raise ValueError("The featured release asset pattern is invalid")
    return {
        "repository": repository_url,
        "releaseFeed": feed,
        "assetPattern": pattern,
    }


def catalog(path: Path = CATALOG_FILE) -> list[dict]:
    try:
        document = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError) as error:
        raise RuntimeError(f"Featured FF8 mod catalog is invalid: {error}") from error
    if not isinstance(document, list):
        raise ValueError("Featured FF8 mod catalog must be a list")
    rows: list[dict] = []
    seen: set[str] = set()
    for value in document:
        if not isinstance(value, dict) or value.get("featured") is not True:
            raise ValueError("Every featured catalog entry must be marked featured")
        mod_id = str(value.get("id") or "").strip()
        name = str(value.get("name") or mod_id).strip()
        if not mod_id or not name or any(char in mod_id for char in "/\\"):
            raise ValueError("Featured mod identity is invalid")
        if mod_id.casefold() in seen:
            raise ValueError(f"Duplicate featured FF8 mod id: {mod_id}")
        seen.add(mod_id.casefold())
        rows.append({"id": mod_id, "name": name, "featured": True,
                     "source": _source(value)})
    return rows


def availability(project_root: Path, mods_root: Path,
                 path: Path = CATALOG_FILE) -> list[dict]:
    installed = {row["id"].casefold(): row
                 for row in runtime_layout.catalog(project_root, mods_root)}
    return [{**entry, "installed": installed.get(entry["id"].casefold())}
            for entry in catalog(path)]


def _fetch_json(url: str) -> dict:
    request = Request(url, headers={
        "Accept": "application/vnd.github+json",
        "User-Agent": "Lexeditor-FF8-featured-mods",
        "X-GitHub-Api-Version": "2022-11-28",
    })
    try:
        with urlopen(request, timeout=20) as response:
            _https_url(response.geturl(), hosts={"api.github.com"})
            length = int(response.headers.get("Content-Length") or 0)
            if length > MAX_RELEASE_DOCUMENT_BYTES:
                raise RuntimeError("The featured release response is too large")
            data = response.read(MAX_RELEASE_DOCUMENT_BYTES + 1)
    except HTTPError as error:
        if error.code in (401, 403, 404):
            raise RuntimeError(
                "The latest release is not available. The repository may be private or have no published release."
            ) from error
        raise RuntimeError(f"GitHub release lookup failed with HTTP {error.code}") from error
    except URLError as error:
        raise RuntimeError(f"GitHub release lookup failed: {error.reason}") from error
    if len(data) > MAX_RELEASE_DOCUMENT_BYTES:
        raise RuntimeError("The featured release response is too large")
    try:
        value = json.loads(data.decode("utf-8"))
    except (UnicodeError, ValueError, TypeError) as error:
        raise RuntimeError("The featured release response is not valid JSON") from error
    if not isinstance(value, dict):
        raise RuntimeError("The featured release response is not an object")
    return value


def _download(url: str, destination: Path, expected_size: int, expected_sha256: str) -> str:
    _https_url(url, hosts=GITHUB_ASSET_HOSTS)
    request = Request(url, headers={"User-Agent": "Lexeditor-FF8-featured-mods"})
    digest = hashlib.sha256()
    total = 0
    try:
        with urlopen(request, timeout=60) as response, destination.open("wb") as output:
            _https_url(response.geturl(), hosts=GITHUB_ASSET_HOSTS)
            declared = int(response.headers.get("Content-Length") or 0)
            if declared > MAX_MOD_BYTES or (expected_size and declared and declared != expected_size):
                raise RuntimeError("The featured mod download size does not match its release metadata")
            while True:
                block = response.read(1024 * 1024)
                if not block:
                    break
                total += len(block)
                if total > MAX_MOD_BYTES:
                    raise RuntimeError("The featured mod download is too large")
                output.write(block)
                digest.update(block)
            output.flush()
            os.fsync(output.fileno())
    except (HTTPError, URLError) as error:
        raise RuntimeError(f"The featured mod download failed: {error}") from error
    if expected_size and total != expected_size:
        raise RuntimeError("The featured mod download ended before the advertised size")
    actual = digest.hexdigest()
    if actual.casefold() != expected_sha256.casefold():
        raise RuntimeError("The featured mod download failed its SHA-256 check")
    return actual


def latest_release(entry: dict, fetch_json: JsonFetcher = _fetch_json) -> dict:
    source = _source(entry)
    document = fetch_json(source["releaseFeed"])
    if document.get("draft") is True or document.get("prerelease") is True:
        raise RuntimeError("The latest featured mod release is not a stable published release")
    matches = []
    pattern = source["assetPattern"].casefold()
    for asset in document.get("assets", []):
        if not isinstance(asset, dict) or not fnmatch.fnmatch(str(asset.get("name", "")).casefold(), pattern):
            continue
        digest = str(asset.get("digest") or "")
        if not re.fullmatch(r"sha256:[0-9a-fA-F]{64}", digest):
            raise RuntimeError("The featured mod release asset has no valid SHA-256 digest")
        size = int(asset.get("size") or 0)
        if size <= 0 or size > MAX_MOD_BYTES:
            raise RuntimeError("The featured mod release asset size is invalid")
        matches.append({
            "name": str(asset.get("name") or ""),
            "url": _https_url(str(asset.get("browser_download_url") or ""),
                              hosts=GITHUB_ASSET_HOSTS),
            "size": size,
            "sha256": digest.partition(":")[2].lower(),
        })
    if len(matches) != 1:
        raise RuntimeError("The latest featured mod release must contain exactly one matching IROJ asset")
    release_id = str(document.get("id") or "")
    version = str(document.get("tag_name") or document.get("name") or "").strip()
    release_url = _https_url(str(document.get("html_url") or source["repository"]),
                             hosts={"github.com"})
    if not release_id or not version:
        raise RuntimeError("The featured mod release has no stable identity or version")
    return {"id": release_id, "version": version, "releaseUrl": release_url,
            "asset": matches[0], "source": source}


def install_latest(mod_id: str, project_root: Path, mods_root: Path,
                   path: Path = CATALOG_FILE, fetch_json: JsonFetcher = _fetch_json,
                   fetch_file: FileFetcher = _download) -> dict:
    entry = next((row for row in catalog(path) if row["id"] == mod_id), None)
    if entry is None:
        raise ValueError(f"Unknown featured FF8 mod: {mod_id}")
    current = next((row for row in runtime_layout.catalog(project_root, mods_root)
                    if row["id"].casefold() == mod_id.casefold()), None)
    if current and current["selected"]:
        raise ValueError(
            "This featured mod is the selected editable project. Lexeditor will not replace it with a download."
        )
    release = latest_release(entry, fetch_json)
    library = Path(mods_root).resolve()
    library.mkdir(parents=True, exist_ok=True)
    handle, temporary_name = tempfile.mkstemp(prefix=".featured-", suffix=".iroj", dir=library.parent)
    os.close(handle)
    temporary = Path(temporary_name)
    try:
        actual = fetch_file(
            release["asset"]["url"], temporary,
            release["asset"]["size"], release["asset"]["sha256"],
        )
        if str(actual).casefold() != release["asset"]["sha256"].casefold():
            raise RuntimeError("The featured mod downloader did not return the verified SHA-256")
        archive = iroj_archive.Archive(temporary)
        incoming = runtime_layout._metadata(temporary)
        if incoming["id"].casefold() != mod_id.casefold() or not archive.has("mod.xml"):
            raise RuntimeError("The featured release package identity does not match its catalog entry")
        return runtime_layout.install_iroj(
            temporary, project_root, mods_root, release["asset"]["name"],
            replace_existing=current is not None,
            metadata={
                "featured": True, "source": release["source"],
                "version": release["version"], "releaseUrl": release["releaseUrl"],
                "releaseId": release["id"], "assetSha256": release["asset"]["sha256"],
            },
        )
    finally:
        temporary.unlink(missing_ok=True)
