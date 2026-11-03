"""Lexeditor's application core: the desktop host, settings, plugin API and
shared services. `app.py` at the repository root is the entry point."""

from .network_policy import install as _install_network_policy
_install_network_policy()
