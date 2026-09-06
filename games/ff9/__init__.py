"""Final Fantasy IX Lexeditor plugin."""
from . import memoria_catalog as _memoria_catalog
from . import memoria_update as _memoria_update
_memoria_catalog.install()
_memoria_update.install()
