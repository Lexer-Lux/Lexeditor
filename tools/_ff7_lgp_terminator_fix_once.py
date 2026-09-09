"""One-shot fix for FF7 LGP terminator/no-op preservation."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def replace_one(path: Path, old: str, new: str) -> None:
    text = path.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{path}: expected one marker, found {count}")
    path.write_text(text.replace(old, new), encoding="utf-8")


archives = ROOT / "games/ff7/archives.py"
replace_one(
    archives,
    "from .format_codec import bounds, read_int, lzs_decode, lzs_encode\n\n\nclass LGP:\n",
    "from .format_codec import bounds, read_int, lzs_decode, lzs_encode\n\n\nLGP_TERMINATOR = b'FINAL FANTASY 7'\n\n\nclass LGP:\n",
)
replace_one(
    archives,
    "        if not data.startswith(b'\\0\\0SQUARESOFT') or not data.endswith(b'FINAL FANTASY 7'):\n",
    "        if not data.startswith(b'\\0\\0SQUARESOFT') or not data.endswith(LGP_TERMINATOR):\n",
)
replace_one(
    archives,
    "            if start+24+size>len(data)-14: raise ValueError('LGP member overlaps its terminator')\n",
    "            if start+24+size>len(data)-len(LGP_TERMINATOR): raise ValueError('LGP member overlaps its terminator')\n",
)
replace_one(
    archives,
    "        result=bytearray(self.original[:-14])\n",
    "        result=bytearray(self.original[:-len(LGP_TERMINATOR)])\n",
)
replace_one(
    archives,
    "        result.extend(b'FINAL FANTASY 7')\n",
    "        result.extend(LGP_TERMINATOR)\n",
)
replace_one(
    archives,
    "    def to_bytes(self):\n        self.lgp.changes[self.index]=bytes(self.data)\n        return self.lgp.to_bytes()\n",
    "    def to_bytes(self):\n"
    "        raw=bytes(self.data);_,at,size=self.lgp.entries[self.index]\n"
    "        if raw==self.lgp.original[at+24:at+24+size]:return self.lgp.original\n"
    "        self.lgp.changes[self.index]=raw\n"
    "        return self.lgp.to_bytes()\n",
)

completion = ROOT / "tools/verify_ff7_completion.py"
replace_one(
    completion,
    "        self.assertEqual(saved.member(0),b'a longer replacement');self.assertEqual(saved.member(1),b'beta')\n",
    "        self.assertEqual(saved.member(0),b'a longer replacement');self.assertEqual(saved.member(1),b'beta')\n"
    "        self.assertEqual(len(out),len(raw)+24+len(b'a longer replacement'))\n",
)
