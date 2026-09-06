"""Reproduce the bundled WSE2 package from the exact publisher ZIP (offline).

Usage: python tools/build_wse2_bundle.py path/to/WSE2.zip [output-directory]
Never downloads, executes, or installs upstream programs. Unchanged engine and
Steam binaries, pinned by SHA-256, are repackaged without the updating launcher.
"""
from pathlib import Path
import hashlib
import json
import sys
import zipfile

UPSTREAM_SHA256 = '755cbe31bd757595a1e83aea120029d5b35e0c41bd377413eb39d395b3cff503'
PACKAGE_SHA256 = '43dc883e0f78cd1fad49dea696080154be0b498000980f63d91e96712707cd31'


def build(source: Path, destination: Path) -> Path:
    if hashlib.sha256(source.read_bytes()).hexdigest() != UPSTREAM_SHA256:
        raise ValueError('Expected the exact upstream WSE2 1.1.5.1 ZIP, not another release or modified archive.')
    names={'mb_warband_wse2.exe','mb_warband_wse2_x64.exe','fmodex_wse2.dll','fmodex64.dll',
           'lua51.dll','lua5164.dll','msvcr120.dll','steam_api_wse2.dll','steam_api64.dll',
           'steam_appid.txt','Fxaa3_11.h','postFX.fx','postFX_WSE2.fx','wse2_shaders.ini'}
    with zipfile.ZipFile(source) as archive:
        names.update(n for n in archive.namelist() if not n.endswith(('/','.bat','.cmd'))
                     and n.startswith(('CommonRes/','languages/','WSE2 SDK/')))
        files={n:archive.read(n) for n in sorted(names)}
    destination.mkdir(parents=True,exist_ok=True)
    target=destination/'wse2-1.1.5.1-lex1.zip'
    with zipfile.ZipFile(target,'w',zipfile.ZIP_STORED) as out:
        for name,raw in files.items():
            info=zipfile.ZipInfo(name,(2026,8,28,0,0,0));info.create_system=3
            info.external_attr=0o100644<<16;out.writestr(info,raw)
    if hashlib.sha256(target.read_bytes()).hexdigest() != PACKAGE_SHA256:
        target.unlink()
        raise ValueError('Rebuilt WSE2 package differs from the reviewed package.')
    manifest={'schema':1,'runtime':'WSE2','version':'v1.1.5.1','packageVersion':'1.1.5.1-lex1',
              'published':'2026-08-28T20:12:29Z','upstream':'https://github.com/Ruslan-700/WSE2-Releases',
              'upstreamAsset':'https://github.com/Ruslan-700/WSE2-Releases/releases/download/v1.1.5.1/WSE2.zip',
              'upstreamSha256':UPSTREAM_SHA256,'archive':target.name,'sha256':PACKAGE_SHA256,
              'steamAppId':'48700','files':{name:{'sha256':hashlib.sha256(raw).hexdigest(),'size':len(raw)} for name,raw in files.items()}}
    (destination/'manifest.json').write_text(json.dumps(manifest,indent=2,sort_keys=True)+'\n',encoding='utf-8',newline='\n')
    return target


if __name__=='__main__':
    if len(sys.argv) not in (2,3):
        raise SystemExit(__doc__)
    dest=Path(sys.argv[2]) if len(sys.argv)>2 else Path(__file__).resolve().parents[1]/'games/warband/runtime'
    print(build(Path(sys.argv[1]),dest))
