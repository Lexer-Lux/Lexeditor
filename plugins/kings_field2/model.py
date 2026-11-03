"""KF2 preferences, using the shared native-port settings implementation."""
from core.native_port_settings import NativePortSettings
from .port import status

# Bounds match the fork's native MousePage, AnalogPage and DistancePage controls.
FIELDS = (
    {"section": "Mouse", "key": "kf2.mouse.turn", "label": "Mouse turn sensitivity", "kind": "number", "min": .1, "max": 5, "step": .1, "default": 1},
    {"section": "Mouse", "key": "kf2.mouse.look", "label": "Mouse look sensitivity", "kind": "number", "min": .1, "max": 5, "step": .1, "default": 1},
    {"section": "Mouse", "key": "kf2.mouse.inverty", "label": "Invert mouse look", "kind": "boolean", "default": False},
    {"section": "Controller", "key": "kf2.analog.turn", "label": "Stick turn sensitivity", "kind": "number", "min": .1, "max": 3, "step": .1, "default": 3},
    {"section": "Controller", "key": "kf2.analog.pitch", "label": "Stick look sensitivity", "kind": "number", "min": .1, "max": 3, "step": .1, "default": 3},
    {"section": "Controller", "key": "kf2.controls.separaterun", "label": "Separate run input", "kind": "boolean", "default": True,
     "help": "Run uses the L3 binding in the port's Input settings: Shift on keyboard or Circle on controller by default. Interact no longer doubles as Run."},
    {"section": "World", "key": "kf2.renderdistance", "label": "View distance (tiles)", "kind": "number", "min": 10.5, "max": 15, "step": .5, "default": 10.5},
    {"section": "World", "key": "kf2.distancefade.on", "label": "Smooth distance fade", "kind": "boolean", "default": False,
     "help": "Gradually hides scenery near the view limit. Requires GPU geometry; keeps fog and view distance unchanged."},
)

MODEL = NativePortSettings(__file__, FIELDS, readiness=status)
