"""Package the locally built DX11 add-on and the user's original shader chains."""
from pathlib import Path
import shutil
import sys


def main():
    build = Path(sys.argv[1]).resolve()
    out = build / "package"
    for source, target in [("ReShade64.dll", "dxgi.dll"), ("librashader.dll", "librashader_capi.dll")]:
        shutil.copy2(build / source, out / target)
    shaders = out / "LexerCRT" / "Shaders"
    shaders.mkdir(exist_ok=True)
    (shaders / "LexerCRT.fx").write_text('''texture2D BackBuffer : COLOR;
sampler2D BackBufferSampler { Texture = BackBuffer; };
void VS(uint id : SV_VertexID, out float4 pos : SV_Position, out float2 uv : TEXCOORD) {
    uv = float2((id << 1) & 2, id & 2);
    pos = float4(uv * float2(2, -2) + float2(-1, 1), 0, 1);
}
float4 PS(float4 pos : SV_Position, float2 uv : TEXCOORD) : SV_Target { return tex2D(BackBufferSampler, uv); }
technique Lexer_CRT < ui_label = "Lexer CRT"; ui_tooltip = "Runs the original PS1 or N64 shader chain. Select Lexer-PS1.ini or Lexer-N64.ini above."; > {
    pass { VertexShader = VS; PixelShader = PS; }
}
''')
    for name in ["PS1", "N64"]:
        (out / f"Lexer-{name}.ini").write_text("Techniques=Lexer_CRT@LexerCRT.fx\nTechniqueSorting=Lexer_CRT@LexerCRT.fx\n")
    (out / "ReShade.ini").write_text(r'''[GENERAL]
EffectSearchPaths=.\LexerCRT\Shaders
TextureSearchPaths=.\LexerCRT
PresetPath=.\Lexer-PS1.ini
PerformanceMode=1

[INPUT]
KeyOverlay=36,0,0,0
KeyEffects=145,0,0,0

[OVERLAY]
TutorialProgress=4
''')
    shutil.copy2(Path(__file__).resolve().parents[1] / "README.md", out / "LexerCRT" / "README.md")
    print(f"Prepared {out}")


if __name__ == "__main__":
    main()
