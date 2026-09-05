"""Apply the proved Better Targeting renderer change to pinned FFNx source."""

from __future__ import annotations

import argparse
import subprocess
from pathlib import Path


PINNED_FFNX_REVISION = "1e291885da4ddb482188b81a5198d56a1915fde6"


def replace_once(path: Path, old: bytes, new: bytes) -> None:
    data = path.read_bytes()
    count = data.count(old)
    if count != 1:
        raise RuntimeError(f"Expected one Better Targeting anchor in {path}, found {count}")
    path.write_bytes(data.replace(old, new, 1))


def apply(root: Path, *, check_revision: bool = True) -> None:
    root = root.resolve()
    if check_revision:
        revision = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=root, text=True
        ).strip()
        if revision != PINNED_FFNX_REVISION:
            raise RuntimeError(
                f"Unsupported FFNx revision {revision}; expected {PINNED_FFNX_REVISION}"
            )

    replace_once(
        root / "src/cfg.cpp",
        b"bool enable_devtools;\r\n",
        b"bool enable_devtools;\r\nbool enable_ff8_better_targeting;\r\n",
    )
    replace_once(
        root / "src/cfg.cpp",
        b'\tenable_devtools = config["enable_devtools"].value_or(false);\r\n',
        b'\tenable_devtools = config["enable_devtools"].value_or(false);\r\n'
        b'\tenable_ff8_better_targeting = config["enable_ff8_better_targeting"].value_or(false);\r\n',
    )
    replace_once(
        root / "src/cfg.h",
        b"extern bool enable_devtools;\r\n",
        b"extern bool enable_devtools;\r\nextern bool enable_ff8_better_targeting;\r\n",
    )
    replace_once(
        root / "misc/FFNx.toml",
        b"enable_devtools = false\r\n",
        b"enable_devtools = false\r\n\r\n"
        b"# Make Lexeditor's marked FF8 battle target hand fully opaque.\r\n"
        b"enable_ff8_better_targeting = false\r\n",
    )
    replace_once(
        root / "src/ff8_opengl.cpp",
        b"\tbool yfix = false\r\n) {\r\n",
        b"\tbool yfix = false, bool force_opaque = false\r\n) {\r\n",
    )
    replace_once(
        root / "src/ff8_opengl.cpp",
        b"\t\t\tdraw_infos->field_8 = no_a6_mask ? a6 | (((sp1_section_data[0] >> 26) & 2) << 24) : (a6 & 0x3FFFFFF) | (((sp1_section_data[0] >> 26) & 2 | 0x64) << 24);\r\n",
        b"\t\t\tconst int descriptor_alpha = force_opaque ? 0 : (((sp1_section_data[0] >> 26) & 2) << 24);\r\n"
        b"\t\t\tdraw_infos->field_8 = no_a6_mask ? a6 | descriptor_alpha : (a6 & 0x3FFFFFF) | (0x64000000 | descriptor_alpha);\r\n",
    )
    replace_once(
        root / "src/ff8_opengl.cpp",
        b"{\r\n\treturn ff8_draw_icon_or_key(a1, draw_infos, icon_id, x, y, a6, 0, true);\r\n}\r\n\r\nff8_draw_menu_sprite_texture_infos *ff8_draw_icon_or_key4",
        b"{\r\n\tconstexpr unsigned int opaque_target_marker = 0x80000000U;\r\n"
        b"\tconst bool force_opaque = ff8 && enable_ff8_better_targeting && icon_id == 0 &&\r\n"
        b"\t\t(static_cast<unsigned int>(a6) & opaque_target_marker) != 0;\r\n"
        b"\ta6 = static_cast<int>(static_cast<unsigned int>(a6) & ~opaque_target_marker);\r\n"
        b"\treturn ff8_draw_icon_or_key(a1, draw_infos, icon_id, x, y, a6, 0, true, false, false, force_opaque);\r\n"
        b"}\r\n\r\nff8_draw_menu_sprite_texture_infos *ff8_draw_icon_or_key4",
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("ffnx_source", type=Path)
    args = parser.parse_args()
    apply(args.ffnx_source)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
