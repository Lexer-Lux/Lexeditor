"""Final Fantasy VIII (2013) Lexeditor plugin."""

# Keep small feature integrations out of the already-large format/settings
# modules. Importing the package installs wrappers exactly once before the HTTP
# server imports those modules for request handling.
from . import reptile_integration as _reptile_integration

_reptile_integration.install()
