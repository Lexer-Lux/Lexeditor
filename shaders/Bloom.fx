// Bloom.fx - Lexeditor's bloom for ReShade.
//
// Glow around bright areas, done the way common open-source blooms do it:
// keep only what is brighter than a threshold (with a soft knee), blur it at
// low resolution, and add it back over the image.
// Self-contained: needs no include from any other shader collection.

uniform float Intensity <
    ui_type = "slider"; ui_min = 0.0; ui_max = 2.0; ui_step = 0.01;
    ui_label = "Intensity";
    ui_tooltip = "How strong the glow is. 0 turns it off.";
> = 0.5;

uniform float Threshold <
    ui_type = "slider"; ui_min = 0.0; ui_max = 1.0; ui_step = 0.01;
    ui_label = "Threshold";
    ui_tooltip = "How bright something must be before it glows. Lower makes more of the image glow.";
> = 0.8;

uniform float Radius <
    ui_type = "slider"; ui_min = 0.5; ui_max = 4.0; ui_step = 0.01;
    ui_label = "Radius";
    ui_tooltip = "How far the glow spreads from bright areas.";
> = 1.0;

texture BloomBackBufferTex : COLOR;
sampler BloomBackBuffer { Texture = BloomBackBufferTex; };

texture BloomBrightTex { Width = BUFFER_WIDTH / 2; Height = BUFFER_HEIGHT / 2; Format = RGBA16F; MipLevels = 4; };
sampler BloomBright { Texture = BloomBrightTex; };

texture BloomBlurXTex { Width = BUFFER_WIDTH / 8; Height = BUFFER_HEIGHT / 8; Format = RGBA16F; };
sampler BloomBlurX { Texture = BloomBlurXTex; };

texture BloomBlurYTex { Width = BUFFER_WIDTH / 8; Height = BUFFER_HEIGHT / 8; Format = RGBA16F; };
sampler BloomBlurY { Texture = BloomBlurYTex; };

static const float2 BlurTexel = float2(8.0 / BUFFER_WIDTH, 8.0 / BUFFER_HEIGHT);
static const float Knee = 0.1;
// Nine-tap Gaussian, centre first.
static const float Weights[5] = { 0.2270270270, 0.1945945946, 0.1216216216, 0.0540540541, 0.0162162162 };

void BloomVS(in uint id : SV_VertexID, out float4 position : SV_Position, out float2 texcoord : TEXCOORD)
{
    texcoord.x = (id == 2) ? 2.0 : 0.0;
    texcoord.y = (id == 1) ? 2.0 : 0.0;
    position = float4(texcoord * float2(2.0, -2.0) + float2(-1.0, 1.0), 0.0, 1.0);
}

float4 BrightPS(float4 position : SV_Position, float2 texcoord : TEXCOORD) : SV_Target
{
    float3 color = tex2D(BloomBackBuffer, texcoord).rgb;
    float brightness = max(color.r, max(color.g, color.b));
    // Soft knee: tones just under the threshold fade in instead of snapping on.
    float soft = clamp(brightness - Threshold + Knee, 0.0, 2.0 * Knee);
    soft = soft * soft / (4.0 * Knee + 1e-5);
    float contribution = max(soft, brightness - Threshold) / max(brightness, 1e-5);
    return float4(color * contribution, 1.0);
}

float4 Blur(sampler source, float2 texcoord, float2 direction, float lod)
{
    float3 sum = tex2Dlod(source, float4(texcoord, 0.0, lod)).rgb * Weights[0];
    for (int i = 1; i < 5; i++)
    {
        float2 offset = direction * BlurTexel * Radius * i;
        sum += tex2Dlod(source, float4(texcoord + offset, 0.0, lod)).rgb * Weights[i];
        sum += tex2Dlod(source, float4(texcoord - offset, 0.0, lod)).rgb * Weights[i];
    }
    return float4(sum, 1.0);
}

float4 BlurXPS(float4 position : SV_Position, float2 texcoord : TEXCOORD) : SV_Target
{
    return Blur(BloomBright, texcoord, float2(1.0, 0.0), 2.0);
}

float4 BlurYPS(float4 position : SV_Position, float2 texcoord : TEXCOORD) : SV_Target
{
    return Blur(BloomBlurX, texcoord, float2(0.0, 1.0), 0.0);
}

float3 CompositePS(float4 position : SV_Position, float2 texcoord : TEXCOORD) : SV_Target
{
    float3 color = tex2D(BloomBackBuffer, texcoord).rgb;
    float3 glow = tex2D(BloomBlurY, texcoord).rgb;
    // Screen blend, so the glow brightens without clipping to flat white.
    glow = saturate(glow * Intensity);
    return 1.0 - (1.0 - color) * (1.0 - glow);
}

technique Bloom <
    ui_tooltip = "Glow around bright areas.";
>
{
    pass Bright { VertexShader = BloomVS; PixelShader = BrightPS; RenderTarget = BloomBrightTex; }
    pass BlurX { VertexShader = BloomVS; PixelShader = BlurXPS; RenderTarget = BloomBlurXTex; }
    pass BlurY { VertexShader = BloomVS; PixelShader = BlurYPS; RenderTarget = BloomBlurYTex; }
    pass Composite { VertexShader = BloomVS; PixelShader = CompositePS; }
}
