// Compare.fx - before/after split for ReShade.
//
// Put it at the TOP of the effect list: it saves the untouched frame there,
// and its second technique, "Compare (show)", placed at the BOTTOM, draws that
// untouched frame back over one side of the screen. Self-contained.

uniform float Position <
    ui_type = "slider"; ui_min = 0.0; ui_max = 1.0; ui_step = 0.01;
    ui_label = "Position";
    ui_tooltip = "Where the dividing line sits across the screen.";
> = 0.5;

uniform int Side <
    ui_type = "combo"; ui_items = "Before on the left\0Before on the right\0";
    ui_label = "Side";
    ui_tooltip = "Which side of the line shows the untouched frame.";
> = 0;

texture CompareBackBufferTex : COLOR;
sampler CompareBackBuffer { Texture = CompareBackBufferTex; };

texture CompareBeforeTex { Width = BUFFER_WIDTH; Height = BUFFER_HEIGHT; Format = RGBA8; };
sampler CompareBefore { Texture = CompareBeforeTex; };

void CompareVS(in uint id : SV_VertexID, out float4 position : SV_Position, out float2 texcoord : TEXCOORD)
{
    texcoord.x = (id == 2) ? 2.0 : 0.0;
    texcoord.y = (id == 1) ? 2.0 : 0.0;
    position = float4(texcoord * float2(2.0, -2.0) + float2(-1.0, 1.0), 0.0, 1.0);
}

float4 SavePS(float4 position : SV_Position, float2 texcoord : TEXCOORD) : SV_Target
{
    return tex2D(CompareBackBuffer, texcoord);
}

float3 ShowPS(float4 position : SV_Position, float2 texcoord : TEXCOORD) : SV_Target
{
    float3 after = tex2D(CompareBackBuffer, texcoord).rgb;
    float3 before = tex2D(CompareBefore, texcoord).rgb;
    // A one-pixel line marks the split.
    if (abs(texcoord.x - Position) < 1.0 / BUFFER_WIDTH)
        return 1.0;
    bool left = texcoord.x < Position;
    return (left == (Side == 0)) ? before : after;
}

technique Compare <
    ui_tooltip = "Before/after split, part 1. Put this at the top of the effect list.";
>
{
    pass { VertexShader = CompareVS; PixelShader = SavePS; RenderTarget = CompareBeforeTex; }
}

technique CompareShow <
    ui_label = "Compare (show)";
    ui_tooltip = "Before/after split, part 2. Put this at the bottom of the effect list.";
>
{
    pass { VertexShader = CompareVS; PixelShader = ShowPS; }
}
