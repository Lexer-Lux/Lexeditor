"""Distribution-level external network restriction; loopback remains available.

This governs the application's Python networking and network command helpers.
It is not a security sandbox for arbitrary third-party native code.
"""
import ipaddress
from pathlib import Path
import sys

from disable_networking import disabled

MESSAGE = 'External networking is disabled in this distribution. See disable_networking.py in the program folder.'
_installed = False


def require_network():
    if disabled():
        raise OSError(MESSAGE)


def _local(host):
    if isinstance(host, bytes):
        host = host.decode('ascii', errors='replace')
    if str(host).lower() == 'localhost':
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


def _audit(event, args):
    if not disabled():
        return
    if event in ('socket.connect', 'socket.sendto'):
        address = args[1] if event == 'socket.connect' else args[-1]
        if isinstance(address, tuple) and not _local(address[0]):
            raise OSError(MESSAGE)
    elif event == 'socket.getaddrinfo':
        if args[0] is not None and not _local(args[0]):
            raise OSError(MESSAGE)
    elif event in ('socket.gethostbyname', 'socket.gethostbyaddr'):
        if not _local(args[0]):
            raise OSError(MESSAGE)
    elif event == 'urllib.Request':
        from urllib.parse import urlsplit
        url = urlsplit(args[0])
        if url.scheme in ('http', 'https', 'ftp') and not _local(url.hostname):
            raise OSError(MESSAGE)
    elif event == 'subprocess.Popen':
        executable, command = args[:2]
        words = list(command) if isinstance(command, (list, tuple)) else str(command).split()
        name = Path(str(executable or (words[0] if words else '')).strip('"')).stem.lower()
        if (name in ('curl', 'wget', 'ftp', 'ssh', 'scp')
                or (name == 'git' and any(str(word).lower() in
                    ('fetch', 'pull', 'push', 'clone', 'ls-remote', 'submodule') for word in words))
                or any(str(word).lower().startswith(('https://', 'http://', 'git@', 'ssh://')) for word in words)):
            raise OSError(MESSAGE)


def install():
    global _installed
    if not _installed:
        sys.addaudithook(_audit)
        _installed = True


def notice():
    return {'disabled': disabled(), 'file': 'disable_networking.py', 'message':
        'This Nexus distribution has internet features disabled because Nexus Mods restricts internet communication '
        'and explicitly excludes automatic updates from its essential-function exception. '
        'Online downloads and updates are unavailable. Local editing still works. '
        'To re-enable network features, open disable_networking.py in the program folder, change any character '
        'inside the quoted DO_NOT_EDIT setting, save it, and restart Lexeditor.'}
