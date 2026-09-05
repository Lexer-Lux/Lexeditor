from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE = (ROOT / "games" / "rdr2" / "editor.html").read_text(encoding="utf-8")


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


require("vec3 srgbToLinear(vec3 color)" in SOURCE,
        "installed diffuse maps must be decoded from sRGB before lighting")
require("srgbToLinear(texture(uLayer0Diffuse" in SOURCE,
        "standard materials must light a linear diffuse sample")
require("srgbToLinear(layer0.rgb)" in SOURCE,
        "layered weapon materials must light a linear diffuse sample")
require("layer0.rgb*vec3(.30,.38,.50)" not in SOURCE,
        "the viewer must not force a blue-grey tint onto installed weapon textures")
require("color*=1.34;color=color/(color+vec3(.72))" not in SOURCE,
        "standard materials must not use the old bleaching exposure curve")
require("color*=1.48;color=color/(color+vec3(.76))" not in SOURCE,
        "layered materials must not use the old bleaching exposure curve")

print("RDR2 model color issue 2 source contract passed")
