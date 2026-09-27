from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
from rdr2_editor_source import editor_source
EDITOR = editor_source()
SERVER = (ROOT / "plugins" / "rdr2" / "server.py").read_text(encoding="utf-8")


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


require('mobView: "archetypes"' in EDITOR,
        "Mobs must open on the real editable archetype data")
require('id:"combat",label:"Combat profiles"' in EDITOR
        and 'id:"health",label:"Health archetypes"' in EDITOR
        and 'id:"models",label:"Observed Models"' in EDITOR
        and 'if(f.mobView==="models")return renderMobModels()' in EDITOR,
        "the read-only probe evidence must not be presented as an editable Mobs model table")
require("r.observedHealth!==null" in EDITOR,
        "Observed Models must omit empty rows with no probe evidence")
require("mobModelEdits" not in EDITOR and "/api/mob-models/save" not in EDITOR,
        "the client must not retain the no-op model-to-archetype editor")
require("MOB_OVERRIDE_FILE" not in SERVER and "/api/mob-models/save" not in SERVER,
        "the server must not accept or store model assignments that the game does not consume")
require('"observedHealth": observed' in SERVER,
        "the read-only model view must still expose real MobProbe evidence")

print("RDR2 Mobs issue 18 source contract passed")

# Exercise the server scalar contract without loading files or saving a dataset.
import ast
import re
node = next(node for node in ast.parse(SERVER).body
            if isinstance(node, ast.FunctionDef) and node.name == "_validate_mob_value")
namespace = {"re": re}
exec(compile(ast.Module(body=[node], type_ignores=[]), "<mob-value-validation>", "exec"), namespace)
validate = namespace["_validate_mob_value"]
for original, value, choices in [("10", "-2.5", set()), ("true", "false", set()),
                                  ("CA_Poor", "CA_Average", {"CA_Average"})]:
    assert validate(original, value, choices) == value
for original, value, choices in [("10", "NaN", set()), ("10", "Infinity", set()),
                                  ("10", "", set()), ("true", "yes", set()),
                                  ("CA_Poor", "invented ability", {"CA_Average"})]:
    try:
        validate(original, value, choices)
    except ValueError:
        pass
    else:
        raise AssertionError(f"Invalid scalar accepted: {original!r} -> {value!r}")
print("Mobs numeric, Boolean, and source-enum validation passed")
