// AmbientOcclusion.fx - Lexeditor's ambient occlusion for ReShade.
//
// Screen-space ambient occlusion from the depth buffer, the way common
// open-source SSAO effects do it: rebuild positions and normals from depth,
// sample a spiral of points around each pixel, darken where geometry blocks
// them, then blur the result. Depth setup comes from LexerianDepth.fxh.

#include "LexerianDepth.fxh"

uniform float Intensity <
    ui_type = "slider"; ui_min = 0.0; ui_max = 4.0; ui_step = 0.01;
    ui_label = "Intensity";
    ui_tooltip = "How dark the contact shadows get. 0 turns it off.";
> = 1.0;

uniform float Radius <
    ui_type = "slider"; ui_min = 0.1; ui_max = 5.0; ui_step = 0.01;
    ui_label = "Radius";
    ui_tooltip = "How far from an object its shadow reaches.";
> = 1.0;

uniform int Quality <
    ui_type = "combo"; ui_items = "Low (8 samples)\0Medium (16 samples)\0High (32 samples)\0";
    ui_label = "Quality";
    ui_tooltip = "More samples look smoother and cost more speed.";
> = 1;

uniform float FadeDistance <
    ui_type = "slider"; ui_min = 0.01; ui_max = 1.0; ui_step = 0.01;
    ui_label = "Fade distance";
    ui_tooltip = "How far away occlusion fades out, so distant scenery and the sky are left alone.";
> = 0.4;

uniform bool DebugView <
    ui_label = "Debug view";
    ui_tooltip = "Show only the occlusion, for tuning.";
> = false;

texture AOTex { Width = BUFFER_WIDTH / 2; Height = BUFFER_HEIGHT / 2; Format = R8; };
sampler AOSampler { Texture = AOTex; };
texture AOBlurTex { Width = BUFFER_WIDTH / 2; Height = BUFFER_HEIGHT / 2; Format = R8; };
sampler AOBlurSampler { Texture = AOBlurTex; };

// View-space position with depth in the far-plane units LinearDepth returns.
float3 ViewPosition(float2 texcoord)
{
    float depth = Lexerian::LinearDepth(texcoord) * RESHADE_DEPTH_LINEARIZATION_FAR_PLANE;
    float2 ndc = texcoord * 2.0 - 1.0;
    ndc.x *= Lexerian::AspectRatio;
    return float3(ndc * depth, depth);
}

float3 ViewNormal(float2 texcoord, float3 centre)
{
    float3 right = ViewPosition(texcoord + float2(Lexerian::PixelSize.x, 0)) - centre;
    float3 down = ViewPosition(texcoord + float2(0, Lexerian::PixelSize.y)) - centre;
    return normalize(cross(down, right));
}

float OcclusionPS(float4 position : SV_Position, float2 texcoord : TEXCOORD) : SV_Target
{
    float depthHere = Lexerian::LinearDepth(texcoord);
    if (depthHere >= FadeDistance || Intensity <= 0.0)
        return 1.0;

    float3 centre = ViewPosition(texcoord);
    float3 normal = ViewNormal(texcoord, centre);
    int samples = Quality == 0 ? 8 : (Quality == 1 ? 16 : 32);

    // Per-pixel rotation so a few samples read as fine noise, not banding.
    float noise = frac(52.9829189 * frac(dot(position.xy, float2(0.06711056, 0.00583715))));
    float screenRadius = Radius / max(centre.z, 1e-3) * 0.5;

    float occlusion = 0.0;
    for (int i = 0; i < samples; i++)
    {
        float t = (i + 0.5) / samples;
        float angle = (i * 2.39996323 + noise * 6.2831853);
        float2 offset = float2(cos(angle), sin(angle)) * t * screenRadius;
        offset.x /= Lexerian::AspectRatio;
        float3 delta = ViewPosition(texcoord + offset) - centre;
        float distance2 = dot(delta, delta);
        float facing = max(dot(normal, delta) / sqrt(distance2 + 1e-5) - 0.05, 0.0);
        float range = saturate(1.0 - distance2 / (Radius * Radius * 4.0));
        occlusion += facing * range;
    }
    occlusion = 1.0 - saturate(occlusion / samples * Intensity * 2.0);
    return lerp(occlusion, 1.0, smoothstep(FadeDistance * 0.7, FadeDistance, depthHere));
}

float BlurPS(float4 position : SV_Position, float2 texcoord : TEXCOORD) : SV_Target
{
    float centreDepth = Lexerian::LinearDepth(texcoord);
    float sum = 0.0, weights = 0.0;
    for (int x = -2; x <= 2; x++)
    for (int y = -2; y <= 2; y++)
    {
        float2 uv = texcoord + float2(x, y) * Lexerian::PixelSize * 2.0;
        // Depth-aware, so shadows do not bleed across object edges.
        float w = 1.0 / (1e-4 + abs(Lexerian::LinearDepth(uv) - centreDepth) * 200.0);
        sum += tex2D(AOSampler, uv).r * w;
        weights += w;
    }
    return sum / weights;
}

float3 CompositePS(float4 position : SV_Position, float2 texcoord : TEXCOORD) : SV_Target
{
    float occlusion = tex2D(AOBlurSampler, texcoord).r;
    if (DebugView)
        return occlusion;
    return tex2D(Lexerian::BackBuffer, texcoord).rgb * occlusion;
}

technique AmbientOcclusion <
    ui_label = "Ambient Occlusion";
    ui_tooltip = "Contact shadows where objects meet, from the depth buffer.";
>
{
    pass { VertexShader = Lexerian::FullscreenVS; PixelShader = OcclusionPS; RenderTarget = AOTex; }
    pass { VertexShader = Lexerian::FullscreenVS; PixelShader = BlurPS; RenderTarget = AOBlurTex; }
    pass { VertexShader = Lexerian::FullscreenVS; PixelShader = CompositePS; }
}
