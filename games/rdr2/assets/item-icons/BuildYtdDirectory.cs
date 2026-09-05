using System;
using System.IO;
using System.Linq;
using RageLib.Helpers;
using RageLib.ResourceWrappers.GTA5.PC.Textures;

internal static class BuildYtdDirectory
{
    private static int Main(string[] args)
    {
        if (args.Length != 2 || !Directory.Exists(args[1]))
        {
            Console.Error.WriteLine("usage: BuildYtdDirectory output.ytd dds-directory");
            return 2;
        }
        var paths = Directory.GetFiles(args[1], "*.dds").OrderBy(p => p).ToArray();
        var file = new TextureDictionaryFileWrapper_GTA5_pc();
        foreach (var path in paths)
        {
            var texture = new TextureWrapper_GTA5_pc { Name = Path.GetFileNameWithoutExtension(path) };
            DDSIO.LoadTextureData(texture, path);
            file.TextureDictionary.Textures.Add(texture);
        }
        file.Save(args[0]);
        Console.WriteLine("Wrote {0} with {1} textures.", args[0], paths.Length);
        return 0;
    }
}
