"""Pinned Crow source and its review-only upstream entry in the helper panel."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from core.upstream_fetch import fetch_json

RUNTIME = Path(__file__).with_name('runtime')


def source() -> dict:
    return json.loads((RUNTIME / 'overhaul/SOURCE.json').read_text(encoding='utf-8'))


def upstream(*, fetch=None) -> dict:
    pinned = source()
    repository = pinned['repository']
    owner_repo = repository.removeprefix('https://github.com/')
    fetch = fetch or (lambda url: fetch_json(url, user_agent='Lexeditor', size_error='Crow upstream response is too large'))
    latest = fetch(f'https://api.github.com/repos/{owner_repo}/commits/master')
    revision = latest.get('sha', '')
    if len(revision) != 40 or any(c not in '0123456789abcdef' for c in revision):
        raise ValueError('Crow upstream did not return a commit revision')
    return {'source': repository, 'pinned': pinned['revision'][:12], 'latest': revision[:12],
            'published': latest['commit']['committer']['date'], 'behind': revision != pinned['revision'],
            'releaseNotes': f'{repository}/compare/{pinned["revision"]}...{revision}'}


def status(game_root: Path | None) -> dict:
    manifest = json.loads((RUNTIME / 'package/online/runtime-manifest.json').read_text(encoding='utf-8'))
    dll = Path(game_root) / 'dinput8.dll' if game_root else None
    if dll is None or not dll.is_file():
        return {'installed': False, 'version': '', 'integrity': 'not installed'}
    # A different DLL must not be credited with protections we cannot identify.
    digest = hashlib.sha256(dll.read_bytes()).hexdigest() if dll.stat().st_size <= 32 * 1024**2 else ''
    if digest != manifest['sha256']:
        return {'installed': False, 'version': '', 'integrity': 'different loader',
                'message': 'The installed DLL is not the current player-protection build.'}
    return {'installed': True, 'version': source()['revision'][:12], 'integrity': 'ok'}
