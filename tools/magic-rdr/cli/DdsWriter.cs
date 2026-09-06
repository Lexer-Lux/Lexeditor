using System;
using System.IO;
using Magic_RDR.RPF;

internal static class DdsWriter
{
    private const uint DdsMagic = 0x20534444;
    private const uint HeaderFlags = 0x0002100F;
    private const uint PixelFourCc = 0x00000004;
    private const uint PixelRgb = 0x00000040;
    private const uint PixelAlpha = 0x00000001;
    private const uint PixelLuminance = 0x00020000;
    private const uint CapsTexture = 0x00001000;
    private const uint CapsComplex = 0x00000008;
    private const uint CapsMipmap = 0x00400000;

    internal static void Write(Stream output, Texture.TextureInfo texture, byte[] pixels)
    {
        if (output == null) throw new ArgumentNullException("output");
        if (texture == null) throw new ArgumentNullException("texture");
        if (pixels == null) throw new ArgumentNullException("pixels");
        if (texture.Width <= 0 || texture.Height <= 0) throw new InvalidDataException("DDS dimensions must be positive.");

        using (BinaryWriter writer = new BinaryWriter(output, System.Text.Encoding.ASCII, true))
        {
            writer.Write(DdsMagic);
            writer.Write(124U);
            writer.Write(HeaderFlags);
            writer.Write((uint)texture.Height);
            writer.Write((uint)texture.Width);
            writer.Write((uint)pixels.Length);
            writer.Write(0U);
            writer.Write((uint)Math.Max(1, texture.MipMaps));
            for (int index = 0; index < 11; index++) writer.Write(0U);

            writer.Write(32U);
            WritePixelFormat(writer, texture.PixelFormat);
            uint caps = CapsTexture;
            if (texture.MipMaps > 1) caps |= CapsComplex | CapsMipmap;
            writer.Write(caps);
            writer.Write(0U);
            writer.Write(0U);
            writer.Write(0U);
            writer.Write(0U);
            writer.Write(pixels);
        }
    }

    private static void WritePixelFormat(BinaryWriter writer, Texture.TextureType format)
    {
        switch (format)
        {
            case Texture.TextureType.DXT1:
                writer.Write(PixelFourCc); writer.Write(FourCc("DXT1"));
                WriteMasks(writer, 0, 0, 0, 0, 0); return;
            case Texture.TextureType.DXT3:
                writer.Write(PixelFourCc); writer.Write(FourCc("DXT3"));
                WriteMasks(writer, 0, 0, 0, 0, 0); return;
            case Texture.TextureType.DXT5:
                writer.Write(PixelFourCc); writer.Write(FourCc("DXT5"));
                WriteMasks(writer, 0, 0, 0, 0, 0); return;
            case Texture.TextureType.L8:
                writer.Write(PixelLuminance); writer.Write(0U);
                WriteMasks(writer, 8, 0x000000ff, 0, 0, 0); return;
            default:
                writer.Write(PixelRgb | PixelAlpha); writer.Write(0U);
                WriteMasks(writer, 32, 0x00ff0000, 0x0000ff00, 0x000000ff, 0xff000000); return;
        }
    }

    private static void WriteMasks(BinaryWriter writer, uint bits, uint red, uint green, uint blue, uint alpha)
    {
        writer.Write(bits); writer.Write(red); writer.Write(green); writer.Write(blue); writer.Write(alpha);
    }

    private static uint FourCc(string value)
    {
        return (uint)value[0] | ((uint)value[1] << 8) | ((uint)value[2] << 16) | ((uint)value[3] << 24);
    }
}
