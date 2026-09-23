// Sharpen.fx - Lexeditor's sharpening for ReShade.
//
// AMD FidelityFX Contrast Adaptive Sharpening (CAS), MIT licensed: sharpens
// soft, low-contrast detail more than edges that are already sharp, so it
// undoes TAA softness without halos. Self-contained.

uniform float Strength <
    ui_type = "slider"; ui_min = 0.0; ui_max = 1.0; ui_step = 0.01;
    ui_label = "Strength";
    ui_tooltip = "How much detail is sharpened. 0 turns it off.";
> = 0.5;

uniform float Limit <
    ui_type = "slider"; ui_min = 0.0; ui_max = 1.0; ui_step = 0.01;
    ui_label = "Limit";
    ui_tooltip = "How far any pixel may change. Lower stops halos and shimmer on high-contrast edges.";
> = 1.0;

texture SharpenBackBufferTex : COLOR;
sampler SharpenBackBuffer { Texture = SharpenBackBufferTex; MagFilter = POINT; MinFilter = POINT; MipFilter = POINT; };

void SharpenVS(in uint id : SV_VertexID, out float4 position : SV_Position, out float2 texcoord : TEXCOORD)
{
    texcoord.x = (id == 2) ? 2.0 : 0.0;
    texcoord.y = (id == 1) ? 2.0 : 0.0;
    position = float4(texcoord * float2(2.0, -2.0) + float2(-1.0, 1.0), 0.0, 1.0);
}

float3 SharpenPS(float4 position : SV_Position, float2 texcoord : TEXCOORD) : SV_Target
{
    // 3x3 neighbourhood:  a b c / d e f / g h i
    float3 a = tex2Doffset(SharpenBackBuffer, texcoord, int2(-1, -1)).rgb;
    float3 b = tex2Doffset(SharpenBackBuffer, texcoord, int2( 0, -1)).rgb;
    float3 c = tex2Doffset(SharpenBackBuffer, texcoord, int2( 1, -1)).rgb;
    float3 d = tex2Doffset(SharpenBackBuffer, texcoord, int2(-1,  0)).rgb;
    float3 e = tex2D(SharpenBackBuffer, texcoord).rgb;
    float3 f = tex2Doffset(SharpenBackBuffer, texcoord, int2( 1,  0)).rgb;
    float3 g = tex2Doffset(SharpenBackBuffer, texcoord, int2(-1,  1)).rgb;
    float3 h = tex2Doffset(SharpenBackBuffer, texcoord, int2( 0,  1)).rgb;
    float3 i = tex2Doffset(SharpenBackBuffer, texcoord, int2( 1,  1)).rgb;

    // Soft min and max over the cross, then the whole 3x3.
    float3 mnRGB = min(min(min(d, e), min(f, b)), h);
    float3 mnRGB2 = min(mnRGB, min(min(a, c), min(g, i)));
    mnRGB += mnRGB2;
    float3 mxRGB = max(max(max(d, e), max(f, b)), h);
    float3 mxRGB2 = max(mxRGB, max(max(a, c), max(g, i)));
    mxRGB += mxRGB2;

    // Less sharpening where local contrast is already high.
    float3 amp = saturate(min(mnRGB, 2.0 - mxRGB) / mxRGB);
    amp = sqrt(amp);

    float peak = -1.0 / lerp(8.0, 5.0, Strength);
    float3 w = amp * peak;
    float3 sharpened = ((b + d + f + h) * w + e) / (1.0 + 4.0 * w);
    sharpened = saturate(sharpened);

    // Limit: never move further than this from the original.
    float3 delta = clamp(sharpened - e, -Limit, Limit);
    return lerp(e, e + delta, Strength > 0.0 ? 1.0 : 0.0);
}

technique Sharpen <
    ui_tooltip = "AMD Contrast Adaptive Sharpening: brings back detail without halos.";
>
{
    pass { VertexShader = SharpenVS; PixelShader = SharpenPS; }
}
