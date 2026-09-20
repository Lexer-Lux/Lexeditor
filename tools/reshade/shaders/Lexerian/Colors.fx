// Colors.fx - Lexeditor's colour adjustments for ReShade.
//
// Brightness, contrast, saturation, vibrance and gamma, done the way the
// common open-source effects do them (SweetFX Vibrance, prod80 Contrast /
// Brightness / Saturation). Every default leaves the image unchanged.
// Self-contained: needs no include from any other shader collection.

uniform float Brightness <
    ui_type = "slider"; ui_min = -1.0; ui_max = 1.0; ui_step = 0.01;
    ui_label = "Brightness";
    ui_tooltip = "Lightens or darkens the whole image by the same amount.";
> = 0.0;

uniform float Contrast <
    ui_type = "slider"; ui_min = -1.0; ui_max = 1.0; ui_step = 0.01;
    ui_label = "Contrast";
    ui_tooltip = "Pushes tones away from, or pulls them toward, middle grey.";
> = 0.0;

uniform float Saturation <
    ui_type = "slider"; ui_min = -1.0; ui_max = 1.0; ui_step = 0.01;
    ui_label = "Saturation";
    ui_tooltip = "Makes every colour stronger or weaker. -1 is black and white.";
> = 0.0;

uniform float Vibrance <
    ui_type = "slider"; ui_min = -1.0; ui_max = 1.0; ui_step = 0.01;
    ui_label = "Vibrance";
    ui_tooltip = "Like saturation, but mostly boosts muted colours and leaves already strong ones alone.";
> = 0.0;

uniform float Gamma <
    ui_type = "slider"; ui_min = 0.5; ui_max = 2.0; ui_step = 0.01;
    ui_label = "Gamma";
    ui_tooltip = "Brightens (above 1) or darkens (below 1) the midtones without moving black or white.";
> = 1.0;

texture ColorsBackBufferTex : COLOR;
sampler ColorsBackBuffer { Texture = ColorsBackBufferTex; };

static const float3 LumaWeights = float3(0.2126, 0.7152, 0.0722);

void ColorsVS(in uint id : SV_VertexID, out float4 position : SV_Position, out float2 texcoord : TEXCOORD)
{
    texcoord.x = (id == 2) ? 2.0 : 0.0;
    texcoord.y = (id == 1) ? 2.0 : 0.0;
    position = float4(texcoord * float2(2.0, -2.0) + float2(-1.0, 1.0), 0.0, 1.0);
}

float3 ColorsPS(float4 position : SV_Position, float2 texcoord : TEXCOORD) : SV_Target
{
    float3 color = tex2D(ColorsBackBuffer, texcoord).rgb;

    color += Brightness;
    color = (color - 0.5) * (Contrast + 1.0) + 0.5;
    color = saturate(color);

    float luma = dot(color, LumaWeights);
    color = lerp(luma.xxx, color, Saturation + 1.0);

    float strength = max(color.r, max(color.g, color.b)) - min(color.r, min(color.g, color.b));
    color = lerp(luma.xxx, color, 1.0 + Vibrance * (1.0 - sign(Vibrance) * strength));

    color = pow(saturate(color), 1.0 / Gamma);
    return color;
}

technique Colors <
    ui_tooltip = "Brightness, contrast, saturation, vibrance and gamma.";
>
{
    pass
    {
        VertexShader = ColorsVS;
        PixelShader = ColorsPS;
    }
}
