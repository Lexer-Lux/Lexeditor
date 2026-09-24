// LexerianDepth.fxh - one depth buffer setup for every Lexerian effect.
//
// Uses the same preprocessor names as ReShade's own ReShade.fxh, so the
// depth settings in ReShade's global preprocessor definitions apply here too:
// set them once per game and ambient occlusion and depth of field both follow.

#pragma once

#ifndef RESHADE_DEPTH_INPUT_IS_UPSIDE_DOWN
    #define RESHADE_DEPTH_INPUT_IS_UPSIDE_DOWN 0
#endif
#ifndef RESHADE_DEPTH_INPUT_IS_REVERSED
    #define RESHADE_DEPTH_INPUT_IS_REVERSED 1
#endif
#ifndef RESHADE_DEPTH_INPUT_IS_LOGARITHMIC
    #define RESHADE_DEPTH_INPUT_IS_LOGARITHMIC 0
#endif
#ifndef RESHADE_DEPTH_LINEARIZATION_FAR_PLANE
    #define RESHADE_DEPTH_LINEARIZATION_FAR_PLANE 1000.0
#endif
#ifndef RESHADE_DEPTH_MULTIPLIER
    #define RESHADE_DEPTH_MULTIPLIER 1
#endif

namespace Lexerian
{
    static const float2 PixelSize = float2(1.0 / BUFFER_WIDTH, 1.0 / BUFFER_HEIGHT);
    static const float AspectRatio = float(BUFFER_WIDTH) / float(BUFFER_HEIGHT);

    texture BackBufferTex : COLOR;
    texture DepthBufferTex : DEPTH;

    sampler BackBuffer { Texture = BackBufferTex; };
    sampler DepthBuffer { Texture = DepthBufferTex; MagFilter = POINT; MinFilter = POINT; MipFilter = POINT; };

    // 0 at the camera, 1 at the far plane.
    float LinearDepth(float2 texcoord)
    {
#if RESHADE_DEPTH_INPUT_IS_UPSIDE_DOWN
        texcoord.y = 1.0 - texcoord.y;
#endif
        float depth = tex2Dlod(DepthBuffer, float4(texcoord, 0, 0)).x * RESHADE_DEPTH_MULTIPLIER;
#if RESHADE_DEPTH_INPUT_IS_LOGARITHMIC
        const float C = 0.01;
        depth = (exp(depth * log(C + 1.0)) - 1.0) / C;
#endif
#if RESHADE_DEPTH_INPUT_IS_REVERSED
        depth = 1.0 - depth;
#endif
        const float N = 1.0;
        return depth / (RESHADE_DEPTH_LINEARIZATION_FAR_PLANE - depth * (RESHADE_DEPTH_LINEARIZATION_FAR_PLANE - N));
    }

    void FullscreenVS(in uint id : SV_VertexID, out float4 position : SV_Position, out float2 texcoord : TEXCOORD)
    {
        texcoord.x = (id == 2) ? 2.0 : 0.0;
        texcoord.y = (id == 1) ? 2.0 : 0.0;
        position = float4(texcoord * float2(2.0, -2.0) + float2(-1.0, 1.0), 0.0, 1.0);
    }
}
