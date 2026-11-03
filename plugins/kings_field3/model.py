"""Player preference schema from Verdite3's own native controls."""
from core.native_port_settings import NativePortSettings

FIELDS = (
    {"section": "Mouse", "key": "kf3.mouse.turn", "label": "Mouse turn sensitivity", "kind": "number", "min": .1, "max": 5, "step": .1, "default": 1},
    {"section": "Mouse", "key": "kf3.mouse.look", "label": "Mouse look sensitivity", "kind": "number", "min": .1, "max": 5, "step": .1, "default": 1},
    {"section": "Mouse", "key": "kf3.mouse.inverty", "label": "Invert mouse look", "kind": "boolean", "default": False},
    {"section": "Controller", "key": "kf3.analog.turn", "label": "Stick turn sensitivity", "kind": "number", "min": .1, "max": 3, "step": .1, "default": 1},
    {"section": "Controller", "key": "kf3.analog.pitch", "label": "Stick look sensitivity", "kind": "number", "min": .1, "max": 3, "step": .1, "default": 1},
    {"section": "Controller", "key": "kf3.analog.invertpitch", "label": "Invert stick look", "kind": "boolean", "default": False},
    {"section": "World", "key": "kf3.renderdistance", "label": "View distance (tiles)", "kind": "number", "min": 0, "max": 30, "nonzeroMin": 1, "step": .1, "default": 16,
     "help": "Draws scenery farther away. Zero keeps the game's changing view limit. Shorter values cannot reduce the game's own visibility."},
    {"section": "World", "key": "kf3.renderdistance.fade", "label": "Smooth distance fade", "kind": "boolean", "encoding": "positive", "nativeDefault": 3, "nativeMax": 8, "default": True,
     "help": "Gradually hides scenery near the view limit. Requires GPU geometry. Keeps view distance and fog unchanged."},
)

MODEL = NativePortSettings(__file__, FIELDS)
