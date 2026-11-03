"""KF2 source mods use the shared native loader adapter."""
from core.native_source_mods import LEDGER, RECOVERY, NativeSourceModAdapter
from .model import MODEL

class VerditeModAdapter(NativeSourceModAdapter):
    verified = True
    message = "Verdite2's built-in C# source-mod loader. Close the game before changing mods."

    def __init__(self):
        # This pinned runtime orders by dependency and ID, without a priority setting.
        super().__init__(MODEL, priority_key=None)
