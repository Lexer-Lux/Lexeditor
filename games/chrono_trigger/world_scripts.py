"""Read-only disassembly for Chrono Trigger Steam overworld scripts.

CTViewer documents fixed argument widths for world-script opcodes 0x00 through
0x52.  PC/DS-specific opcodes 0x53 and 0x54 remain unknown, so this decoder
stops at the first unknown/truncated command instead of guessing a boundary.
"""

from __future__ import annotations

from dataclasses import dataclass

from .data import OverlayStore, sha256
from .worlds import load_worlds


@dataclass(frozen=True)
class WorldOpcode:
    code: int
    name: str
    argument_bytes: int

    @property
    def size(self) -> int:
        return 1 + self.argument_bytes


# Argument widths are transcribed from CTViewer's documented world-script op
# table.  Values are bytes following the opcode; destination is two bytes.
_SPECS = (
    (0x00,"initialize",0),(0x01,"colofs",1),(0x02,"priset",1),(0x03,"grp",9),
    (0x04,"pal",3),(0x05,"mapjump",2),(0x06,"mappos",0),(0x07,"putmap",4),
    (0x08,"bind",3),(0x09,"newevent",3),(0x0A,"clr",1),(0x0B,"incr",1),
    (0x0C,"decr",1),(0x0D,"setr",2),(0x0E,"bitsetr",2),(0x0F,"bitclr",2),
    (0x10,"memclr",1),(0x11,"meminc",1),(0x12,"memdec",1),(0x13,"memset",2),
    (0x14,"membitset",2),(0x15,"membitclr",2),(0x16,"trnlg",3),(0x17,"trngl",4),
    (0x18,"trnr",2),(0x19,"trnmem",4),(0x1A,"jp",2),(0x1B,"jdjnz",2),
    (0x1C,"jz",2),(0x1D,"jnz",3),(0x1E,"jcpnz",3),(0x1F,"jcpz",3),
    (0x20,"jandnz",3),(0x21,"jandz",3),(0x22,"jz_g",3),(0x23,"jnz_g",3),
    (0x24,"jcpnz_g",4),(0x25,"jcpz_g",4),(0x26,"jandnz_g",4),(0x27,"jandz_g",4),
    (0x28,"fadeout",1),(0x29,"fadein",1),(0x2A,"mozin",1),(0x2B,"mozout",1),
    (0x2C,"pos",4),(0x2D,"unknown_2d",1),(0x2E,"vecx",4),(0x2F,"vecy",4),
    (0x30,"anmseq",1),(0x31,"move",1),(0x32,"scroll",1),(0x33,"bganm",7),
    (0x34,"func",2),(0x35,"link",2),(0x36,"call",2),(0x37,"return",0),
    (0x38,"wait",1),(0x39,"anmwait",1),(0x3A,"timer",1),(0x3B,"effect1",2),
    (0x3C,"effect2",2),(0x3D,"sound",1),(0x3E,"initscreen",1),(0x3F,"tpxmove",4),
    (0x40,"tpymove",4),(0x41,"trigger",0),(0x42,"slink",2),(0x43,"s_newevent",3),
    (0x44,"wake",2),(0x45,"sleep",2),(0x46,"addr",2),(0x47,"subr",2),
    (0x48,"memadd",3),(0x49,"memsub",3),(0x4A,"s_sound",1),(0x4B,"musiccmd",4),
    (0x4C,"jcpcc",4),(0x4D,"jcpcs",4),(0x4E,"func2",3),(0x4F,"copymap",8),
    (0x50,"putmapr",4),(0x51,"scrollr",2),(0x52,"taskend",0),
)
OPCODES = {code: WorldOpcode(code, name, width) for code, name, width in _SPECS}


def _script_path(store: OverlayStore, world_id: int, source: str) -> tuple[int, str]:
    worlds = load_worlds(store, source)
    world_id = int(world_id)
    if not 0 <= world_id < len(worlds["rows"]):
        raise ValueError(f"World index is outside the world table: {world_id}")
    script_id = int(worlds["rows"][world_id]["values"]["script"])
    return script_id, f"Game/world/esl/Event_{script_id:04d}.dat"


def disassemble_world_script(raw: bytes, *, max_commands: int = 20000) -> dict:
    """Decode known fixed-width commands from byte zero, failing closed."""
    cursor = 0
    commands = []
    problem = None
    while cursor < len(raw):
        if len(commands) >= max_commands:
            problem = {"offset": cursor, "reason": "command-limit"}
            break
        code = raw[cursor]
        spec = OPCODES.get(code)
        if spec is None:
            problem = {
                "offset": cursor,
                "opcode": code,
                "reason": "unknown-opcode",
                "remainingPreview": raw[cursor:cursor + 32].hex(" ").upper(),
            }
            break
        end = cursor + spec.size
        if end > len(raw):
            problem = {
                "offset": cursor,
                "opcode": code,
                "name": spec.name,
                "reason": "truncated-command",
                "expectedSize": spec.size,
                "availableBytes": len(raw) - cursor,
            }
            break
        arguments = raw[cursor + 1:end]
        commands.append({
            "index": len(commands),
            "offset": cursor,
            "opcode": code,
            "name": spec.name,
            "size": spec.size,
            "argumentsHex": arguments.hex(" ").upper(),
            "bytesHex": raw[cursor:end].hex(" ").upper(),
        })
        cursor = end
    return {
        "commands": commands,
        "decodedBytes": cursor,
        "totalBytes": len(raw),
        "complete": cursor == len(raw),
        "problem": problem,
    }


def load_world_script(store: OverlayStore, world_id: int, source: str = "mine") -> dict:
    script_id, path = _script_path(store, world_id, source)
    raw, origin = store.read(path, source)
    return {
        "kind": "world-script",
        "worldId": int(world_id),
        "scriptId": script_id,
        "path": path,
        "source": origin,
        "readOnly": True,
        "sha256": sha256(raw),
        **disassemble_world_script(raw),
    }
