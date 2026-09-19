// Vignette.fx - Lexeditor's vignette for ReShade.
//
// Darkens the edges of the screen, the way common open-source vignettes do:
// a smooth falloff by distance from the centre. Self-contained.

uniform float Amount <
    ui_type = "slider"; ui_min = 0.0; ui_max = 1.0; ui_step = 0.01;
    ui_label = "Amount";
    ui_tooltip = "How dark the edges get. 0 turns it off.";
> = 0.4;

uniform float Size <
    ui_type = "slider"; ui_min = 0.0; ui_max = 1.0; ui_step = 0.01;
    ui_label = "Size";
    ui_tooltip = "How far the darkening reaches in from the edges.";
> = 0.5;

uniform float Softness <
    ui_type = "slider"; ui_min = 0.01; ui_max = 1.0; ui_step = 0.01;
    ui_label = "Softness";
    ui_tooltip = "How gradual the fade from the centre to the edges is.";
> = 0.5;

uniform int Shape <
    ui_type = "combo"; ui_items = "Round\0Screen-shaped\0";
    ui_label = "Shape";
    ui_tooltip = "A circle, or an oval stretched to the screen's proportions.";
> = 0;

texture VignetteBackBufferTex : COLOR;
sampler VignetteBackBuffer { Texture = VignetteBackBufferTex; };

void VignetteVS(in uint id : SV_VertexID, out float4 position : SV_Position, out float2 texcoord : TEXCOORD)
{
    texcoord.x = (id == 2) ? 2.0 : 0.0;
    texcoord.y = (id == 1) ? 2.0 : 0.0;
    position = float4(texcoord * float2(2.0, -2.0) + float2(-1.0, 1.0), 0.0, 1.0);
}

float3 VignettePS(float4 position : SV_Position, float2 texcoord : TEXCOORD) : SV_Target
{
    float3 color = tex2D(VignetteBackBuffer, texcoord).rgb;
    float2 centred = texcoord - 0.5;
    if (Shape == 0)
        centred.x *= float(BUFFER_WIDTH) / float(BUFFER_HEIGHT);
    float distance = length(centred) * 1.4142;
    float inner = 1.0 - Size;
    float falloff = smoothstep(inner, inner + Softness, distance);
    return color * (1.0 - falloff * Amount);
}

technique Vignette <
    ui_tooltip = "Darkens the edges of the screen.";
>
{
    pass { VertexShader = VignetteVS; PixelShader = VignettePS; }
}
