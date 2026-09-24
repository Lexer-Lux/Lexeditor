"""Fetch pinned upstream release metadata over plain HTTPS.

Shared by game plugins that check a pinned helper's upstream releases
(FF7R repak, Warband WSE2). One capped GET with a caller-supplied
User-Agent; oversized bodies fail loudly instead of being parsed.
"""
from __future__ import annotations

import json
import urllib.request

MAX_BYTES = 1024 * 1024


def fetch_json(url: str, *, user_agent: str, size_error: str) -> dict:
    """GET url as JSON, capped at 1 MiB. Never follows into installs."""
    request = urllib.request.Request(url, headers={"User-Agent": user_agent})
    with urllib.request.urlopen(request, timeout=15) as response:
        raw = response.read(MAX_BYTES + 1)
    if len(raw) > MAX_BYTES:
        raise RuntimeError(size_error)
    return json.loads(raw)
