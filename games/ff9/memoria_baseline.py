"""Prepare a verified FF9 CSV baseline from Memoria's pinned official release."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import threading
import urllib.request

from . import paths


RELEASE = "v2025.07.04"
SOURCE = f"https://github.com/Albeoris/Memoria/tree/{RELEASE}/Memoria.Patcher/StreamingAssets/Data"
RAW_ROOT = f"https://raw.githubusercontent.com/Albeoris/Memoria/{RELEASE}/Memoria.Patcher/StreamingAssets/Data"
FILES = {
    'Battle/Actions.csv': 'd0d93ae1e0ae42daa295b5b4cf9cd9c00d495e64305a79da5b0dfcb94133742e',
    'Battle/MagicSwordSets.csv': '52c13f473d69b4c31e4466b766bef1a60b3221a7cddfa2e5f4a000b3f9b61ec6',
    'Battle/StatusData.csv': 'd84e0e77ee3c16085a35a5e6100fd03a1246544a730d77778bcec03a028eead6',
    'Battle/StatusSets.csv': '620f86a4146b46432d5696c2463dc74551ed5d75e4f072e0f0732cf8a09abfcf',
    'Characters/Abilities/AbilityGems.csv': '8ac6a22345dcc49355349deb296411b736b13637df5726a1e042b733893b744a',
    'Characters/Abilities/Amarant.csv': '636a0e8c65d6989e6c162438e82f5e067dfa788a9f9df8774da11d8bfa63fd07',
    'Characters/Abilities/Beatrix1.csv': 'aa17b1b1c9c0dfc7abd47ca88dcedf44ef317a107f0717bf5dc68881d67f6ddc',
    'Characters/Abilities/Beatrix2.csv': '63834dbfd81cb8a007f4860699be764b8de625861668a7cc140c7190b559b7cc',
    'Characters/Abilities/Blank1.csv': '7d565d36a2afe812a907afce25f920e099afdfc2e04fa2da57ba832124b4b960',
    'Characters/Abilities/Blank2.csv': '06832abc61eb22bcae9c11ef17ca5ee2ab2ddd4c7929b18b5c736d6194281a4a',
    'Characters/Abilities/Cinna1.csv': '298f5eeb9d488ec93b4a031d0a65dd89018aaf19762c0ea396c3548a09cf33c2',
    'Characters/Abilities/Cinna2.csv': '288e0d7c84aba72718e35e49e1e9710401cb74fa6f3f4d5a331a20f1768b7802',
    'Characters/Abilities/Eiko.csv': 'bf9919a711a30453758adcebfefbf22c9f14711a1483c8f92992f6586e3fb047',
    'Characters/Abilities/Freya.csv': 'e1d5fd79b4a4c92bdf3a364dae9564dfa7f74608efbd7343c1a5bd43ec9a1023',
    'Characters/Abilities/Garnet.csv': '5f89d55480c74094bfc61b6fdf3aa3e600847551a08c1ff3dfd9cb6a9b408658',
    'Characters/Abilities/Marcus1.csv': '145e0999f42263ddc3496c66021b99e9b97c6333e0469cc011856066268e5e44',
    'Characters/Abilities/Marcus2.csv': '41a9b36fd9e9f51a39192e5a1833c61a2b5344ac474303c126248c1ea89fecbd',
    'Characters/Abilities/Quina.csv': '00ca5e549373b00515c231a603b7cc37990be89a43766888044cc036739da142',
    'Characters/Abilities/Steiner.csv': 'e2755c85b1fb0ff8e49fdb7015cba8f2a583967ef33d5317408bf15cf24d17a7',
    'Characters/Abilities/Vivi.csv': '33c7bf463049dd3865365fd55ef2f91c9576613a26667ce6ea98880b865001c4',
    'Characters/Abilities/Zidane.csv': 'dbc576bf00c1840bd4a382238f597a042ca1817026246fd667c438555a95fe09',
    'Characters/BaseStats.csv': '02314fae328e63ad5aa716a0ea6593d88441ee79d12807bec44373de23f6506e',
    'Characters/BattleParameters.csv': '04accb69451aa8266b5bbaf6e810ee8a612cf659ae534b0ea7e8fc9c96270ca6',
    'Characters/CharacterParameters.csv': 'e39dd5f569e8e246a4a12d44cde56fead21dfeb7d8350087fe1aa01bb2693c70',
    'Characters/CommandSets.csv': 'bd9d4f1974de99eb28e4620ecf92361b28042a369ba10ed3e958a085c7f7fc32',
    'Characters/Commands.csv': 'b7b00f683a096c4b464fc0b87f100bcefe96842c7b728711df095881b7a3d3f0',
    'Characters/DefaultEquipment.csv': 'a3bda7ccb831e6d9b4468d55dea748fc8dcf785ccebd28435edf5751039840b0',
    'Characters/Leveling.csv': '8802cd5fd74f9c9936cd0f39c05a6094ee417c04ccc986457bacb033c82bf7ec',
    'Items/Armors.csv': '216c21b16648c8bc51b8d76b5cda64e8434647f02b6c786bc2a0b20281a8b771',
    'Items/InitialItems.csv': '0f7459bdf679991ccfe0998581c944a15785e258d06a7f4ed0743be7f9e1322d',
    'Items/ItemEffects.csv': '9753fa025443ce2e8c8cf59733cad98c7023ef902949e299b1a3fa9d6cdce7b4',
    'Items/Items.csv': '966fee1bc4986ec94c2b05bf1e5299c9fc3497df4377dc002cd58bac96f9076f',
    'Items/MixItems.csv': '2ad95b1e449e5caddaa772953268e2f8af73e09efc934e8531cc6e5d8290dece',
    'Items/ShopItems.csv': '589f12ccc6b2ee8a606f998dc068f945100c0a1928ee016d73b6b9b9e9897906',
    'Items/Stats.csv': '1b87662fd13ce46b1175bd0faf3b9b2bc3ca7336a510a92837af542deb990f8e',
    'Items/Synthesis.csv': '1cd6d012696685ae5d40ff788b8ad64e2fb814f930788b80a7aa81c7d9f3a8a0',
    'Items/Weapons.csv': '830e66a6ced06b92d22b487d4449ed5b873b712a21f83543202e7273f7b70527',
    'SpecialEffects/Common/SHP.csv': 'f8d9e80788ae8941ecca7a051fa70345d2df54e7faa12a8f8ffa6b161c6b4195',
    'SpecialEffects/Common/SPS.csv': '147480f1443de9c9f19aa371be4eff08d76e417efc03c51205df341bf2cab123',
    'TetraMaster/TripleTriad.csv': 'ac4db583706a870a62033b174ee9caf80ec447db5e51f0b3fbd539bb72392371',
    'World/TransportControls.csv': 'e80216b2c65114dcceb9e1896d25de3135fc89b6e7c0767d9dd33c4cdab364eb',
    'World/WeatherColors.csv': 'e6d5ed8da9febda71adace2131989d8c16c58960d97fd37963b7ac0d07102683',
}
MAX_FILE_BYTES = 2 * 1024 * 1024
_lock = threading.Lock()
_last: dict | None = None


def _hash(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _download(relative: str) -> bytes:
    request = urllib.request.Request(
        f"{RAW_ROOT}/{relative}", headers={"User-Agent": "Lexeditor/1.0"},
    )
    with urllib.request.urlopen(request, timeout=12) as response:
        data = response.read(MAX_FILE_BYTES + 1)
    if len(data) > MAX_FILE_BYTES:
        raise RuntimeError(f"Memoria baseline file is unexpectedly large: {relative}")
    return data


def ensure(root: Path | None = None, downloader=_download, force: bool = False) -> dict:
    """Download/verify every pinned CSV independently into Lexeditor's private cache."""
    global _last
    baseline = Path(root or paths.DATA_ROOT) / "StreamingAssets" / "Data"
    with _lock:
        if root is None and _last is not None and not force:
            return _last
        prepared, problems = 0, []
        for relative, expected in FILES.items():
            target = baseline / Path(relative)
            try:
                current = target.read_bytes() if target.is_file() else b""
                if current and _hash(current) == expected:
                    prepared += 1
                    continue
                data = downloader(relative)
                if _hash(data) != expected:
                    raise RuntimeError(f"Official Memoria baseline checksum failed: {relative}")
                target.parent.mkdir(parents=True, exist_ok=True)
                temporary = target.with_name(target.name + ".lexeditor.tmp")
                temporary.write_bytes(data)
                temporary.replace(target)
                prepared += 1
            except Exception as error:
                problems.append(f"{relative}: {error}")
        manifest = {
            "release": RELEASE, "source": SOURCE, "prepared": prepared,
            "expected": len(FILES), "ready": prepared == len(FILES), "problems": problems,
        }
        if prepared:
            baseline.mkdir(parents=True, exist_ok=True)
            manifest_path = baseline.parent / "memoria-baseline.json"
            temporary = manifest_path.with_name(manifest_path.name + ".tmp")
            temporary.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
            temporary.replace(manifest_path)
        if root is None:
            _last = manifest
        return manifest
