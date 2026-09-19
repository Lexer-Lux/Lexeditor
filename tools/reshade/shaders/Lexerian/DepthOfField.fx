// DepthOfField.fx - Lexeditor's depth of field for ReShade.
//
// Blurs what is out of focus, the way common open-source DoF effects do it:
// a circle of confusion from depth against the focus distance, then a disc
// gather weighted by it. Auto focus reads the depth at the screen centre and
// eases toward it. Depth setup comes from LexerianDepth.fxh.
//
// ReShade sees the finished frame, HUD included. To keep the HUD sharp, run
// this before the HUD with the ReshadeEffectShaderToggler add-on Lexeditor
// installs beside ReShade.

#include "LexerianDepth.fxh"

uniform int FocusMode <
    ui_type = "combo"; ui_items = "Auto (screen centre)\0Manual\0";
    ui_label = "Focus";
    ui_tooltip = "Focus on whatever is at the centre of the screen, or at a fixed distance.";
> = 0;

uniform float FocusDistance <
    ui_type = "slider"; ui_min = 0.0; ui_max = 1.0; ui_step = 0.001;
    ui_label = "Focus distance";
    ui_tooltip = "Used when focus is manual. 0 is the camera, 1 is the far plane.";
> = 0.05;

uniform float FocusSpeed <
    ui_type = "slider"; ui_min = 0.01; ui_max = 1.0; ui_step = 0.01;
    ui_label = "Focus speed";
    ui_tooltip = "How quickly auto focus follows a change in distance.";
> = 0.2;

uniform float BlurStrength <
    ui_type = "slider"; ui_min = 0.0; ui_max = 20.0; ui_step = 0.1;
    ui_label = "Blur strength";
    ui_tooltip = "How blurry out-of-focus areas get, in pixels. 0 turns it off.";
> = 6.0;

uniform float FocusRange <
    ui_type = "slider"; ui_min = 0.0; ui_max = 1.0; ui_step = 0.001;
    ui_label = "Focus range";
    ui_tooltip = "How much depth either side of the focus point stays sharp.";
> = 0.02;

uniform bool NearBlur <
    ui_label = "Near blur";
    ui_tooltip = "Also blur things closer than the focus point.";
> = false;

uniform bool DebugView <
    ui_label = "Debug view";
    ui_tooltip = "Black is in focus, red is behind it, blue is in front of it.";
> = false;

uniform float FrameTime < source = "frametime"; >;

texture FocusTex { Format = R32F; };
sampler FocusSampler { Texture = FocusTex; MagFilter = POINT; MinFilter = POINT; };
texture FocusLastTex { Format = R32F; };
sampler FocusLastSampler { Texture = FocusLastTex; MagFilter = POINT; MinFilter = POINT; };

texture CoCTex { Width = BUFFER_WIDTH; Height = BUFFER_HEIGHT; Format = R16F; };
sampler CoCSampler { Texture = CoCTex; };

static const int Taps = 32;

float FocusPS(float4 position : SV_Position, float2 texcoord : TEXCOORD) : SV_Target
{
    if (FocusMode == 1)
        return FocusDistance;
    float target = 0.0;
    // Average a small cross at the centre so one pixel of foliage does not steal focus.
    target += Lexerian::LinearDepth(float2(0.5, 0.5));
    target += Lexerian::LinearDepth(float2(0.48, 0.5));
    target += Lexerian::LinearDepth(float2(0.52, 0.5));
    target += Lexerian::LinearDepth(float2(0.5, 0.47));
    target += Lexerian::LinearDepth(float2(0.5, 0.53));
    target /= 5.0;
    float last = tex2Dlod(FocusLastSampler, float4(0.5, 0.5, 0, 0)).r;
    float ease = saturate(FrameTime * 0.001 * FocusSpeed * 10.0);
    return lerp(last, target, ease);
}

float StorePS(float4 position : SV_Position, float2 texcoord : TEXCOORD) : SV_Target
{
    return tex2Dlod(FocusSampler, float4(0.5, 0.5, 0, 0)).r;
}

// Signed: positive behind focus, negative in front, -1..1.
float CoCPS(float4 position : SV_Position, float2 texcoord : TEXCOORD) : SV_Target
{
    float focus = tex2Dlod(FocusSampler, float4(0.5, 0.5, 0, 0)).r;
    float depth = Lexerian::LinearDepth(texcoord);
    float difference = depth - focus;
    float coc = sign(difference) * saturate((abs(difference) - FocusRange) / max(focus + FocusRange, 1e-3));
    if (!NearBlur)
        coc = max(coc, 0.0);
    return coc;
}

float3 BlurPS(float4 position : SV_Position, float2 texcoord : TEXCOORD) : SV_Target
{
    float centreCoC = tex2D(CoCSampler, texcoord).r;
    float3 colour = tex2D(Lexerian::BackBuffer, texcoord).rgb;

    if (DebugView)
        return centreCoC > 0.0 ? float3(centreCoC, 0, 0) : float3(0, 0, -centreCoC);
    if (BlurStrength <= 0.0)
        return colour;

    float3 sum = colour;
    float weights = 1.0;
    float radius = BlurStrength;
    for (int i = 0; i < Taps; i++)
    {
        float t = sqrt((i + 0.5) / Taps);
        float angle = i * 2.39996323;
        float2 offset = float2(cos(angle), sin(angle)) * t * radius * Lexerian::PixelSize;
        float2 uv = texcoord + offset;
        float sampleCoC = tex2Dlod(CoCSampler, float4(uv, 0, 0)).r;
        // A sample only spreads onto this pixel as far as its own blur reaches,
        // and sharp foreground never picks up blurred background behind it.
        float reach = abs(sampleCoC);
        float w = saturate((reach - t * abs(centreCoC)) * 4.0 + 0.5) * reach;
        if (sampleCoC > 0.0 && centreCoC <= 0.0)
            w *= saturate(1.0 - abs(centreCoC));
        sum += tex2Dlod(Lexerian::BackBuffer, float4(uv, 0, 0)).rgb * w;
        weights += w;
    }
    float3 blurred = sum / weights;
    return lerp(colour, blurred, saturate(abs(centreCoC) * 4.0));
}

technique DepthOfField <
    ui_label = "Depth of Field";
    ui_tooltip = "Blurs what is out of focus. Run it before the HUD with the Effect Shader Toggler add-on to keep the HUD sharp.";
>
{
    pass { VertexShader = Lexerian::FullscreenVS; PixelShader = FocusPS; RenderTarget = FocusTex; }
    pass { VertexShader = Lexerian::FullscreenVS; PixelShader = StorePS; RenderTarget = FocusLastTex; }
    pass { VertexShader = Lexerian::FullscreenVS; PixelShader = CoCPS; RenderTarget = CoCTex; }
    pass { VertexShader = Lexerian::FullscreenVS; PixelShader = BlurPS; }
}
