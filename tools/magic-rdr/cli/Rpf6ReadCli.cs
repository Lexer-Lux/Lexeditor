using System;
using System.Collections.Generic;
using System.Globalization;
using System.IO;
using System.Linq;
using System.Text.RegularExpressions;
using Magic_RDR;
using Magic_RDR.Application;
using Magic_RDR.RPF;
using Magic_RDR.Viewers;

internal static class Rpf6ReadCli
{
    private static int Main(string[] args)
    {
        try
        {
            if (args.Length < 2)
            {
                PrintUsage();
                return 2;
            }

            string command = args[0].ToLowerInvariant();
            if (command == "resource-unpack")
            {
                if (args.Length != 3)
                {
                    PrintUsage();
                    return 2;
                }
                return UnpackResourceFile(
                    Path.GetFullPath(args[1]), Path.GetFullPath(args[2]));
            }
            if (command == "resource-pack")
            {
                if (args.Length != 4)
                {
                    PrintUsage();
                    return 2;
                }
                return PackResourceFile(
                    Path.GetFullPath(args[1]),
                    Path.GetFullPath(args[2]),
                    Path.GetFullPath(args[3]));
            }
            string archivePath = Path.GetFullPath(args[1]);
            LoadFileNames();
            SetPlatform(archivePath);

            using (FileStream input = new FileStream(
                archivePath, FileMode.Open, FileAccess.Read, FileShare.Read))
            {
                RPF6 archive = new RPF6(input);
                try
                {
                    if (command == "list")
                    {
                        string pattern = args.Length >= 3 ? args[2] : "**";
                        return List(archive, pattern);
                    }
                    if (command == "extract")
                    {
                        if (args.Length < 3)
                        {
                            PrintUsage();
                            return 2;
                        }
                        string outputRoot = Path.GetFullPath(args[2]);
                        string pattern = args.Length >= 4 ? args[3] : "**";
                        return Extract(archive, outputRoot, pattern);
                    }
                    if (command == "unpack")
                    {
                        if (args.Length < 3)
                        {
                            PrintUsage();
                            return 2;
                        }
                        string outputRoot = Path.GetFullPath(args[2]);
                        string pattern = args.Length >= 4 ? args[3] : "**";
                        return UnpackResources(archive, outputRoot, pattern);
                    }
                    if (command == "decompile")
                    {
                        if (args.Length < 3)
                        {
                            PrintUsage();
                            return 2;
                        }
                        string outputRoot = Path.GetFullPath(args[2]);
                        string pattern = args.Length >= 4 ? args[3] : "**/*.wsc";
                        return Decompile(archive, outputRoot, pattern);
                    }
                    if (command == "textures")
                    {
                        if (args.Length < 3)
                        {
                            PrintUsage();
                            return 2;
                        }
                        string outputRoot = Path.GetFullPath(args[2]);
                        string pattern = args.Length >= 4 ? args[3] : "**/*.wtd";
                        return ExportTextures(archive, outputRoot, pattern);
                    }
                }
                finally
                {
                    archive.CloseAllStreams();
                }
            }

            throw new ArgumentException("Unknown command: " + command);
        }
        catch (Exception error)
        {
            Console.Error.WriteLine("ERROR\t" + error.GetType().Name + "\t" + error.Message);
            return 1;
        }
    }

    private static void PrintUsage()
    {
        Console.Error.WriteLine("Rpf6ReadCli list <archive.rpf> [wildcard]");
        Console.Error.WriteLine("Rpf6ReadCli extract <archive.rpf> <output-directory> [wildcard]");
        Console.Error.WriteLine("Rpf6ReadCli unpack <archive.rpf> <output-directory> [wildcard]");
        Console.Error.WriteLine("Rpf6ReadCli decompile <archive.rpf> <output-directory> [wildcard]");
        Console.Error.WriteLine("Rpf6ReadCli textures <archive.rpf> <output-directory> [wildcard]");
        Console.Error.WriteLine("Rpf6ReadCli resource-unpack <resource-file> <output-file>");
        Console.Error.WriteLine("Rpf6ReadCli resource-pack <template-resource> <unpacked-file> <output-file>");
    }

    private static void AtomicWrite(string target, byte[] payload)
    {
        string parent = Path.GetDirectoryName(target);
        if (!string.IsNullOrEmpty(parent))
            Directory.CreateDirectory(parent);
        string temporary = target + ".lexeditor.tmp";
        using (FileStream output = new FileStream(
            temporary, FileMode.Create, FileAccess.Write, FileShare.None))
        {
            output.Write(payload, 0, payload.Length);
            output.Flush(true);
        }
        if (File.Exists(target))
            File.Replace(temporary, target, null);
        else
            File.Move(temporary, target);
    }

    private static int UnpackResourceFile(string source, string target)
    {
        AppGlobals.SetPlatform(AppGlobals.PlatformEnum.Switch);
        byte[] packed = File.ReadAllBytes(source);
        byte[] unpacked = ResourceUtils.ResourceInfo.GetDataFromResourceBytes(packed);
        if (unpacked == null)
            throw new InvalidDataException("The input is not a supported RSC resource.");
        AtomicWrite(target, unpacked);
        Console.WriteLine(source + "\t" + target + "\tresourceBytes="
            + unpacked.Length.ToString(CultureInfo.InvariantCulture));
        return 0;
    }

    private static int PackResourceFile(string template, string source, string target)
    {
        AppGlobals.SetPlatform(AppGlobals.PlatformEnum.Switch);
        byte[] packed = File.ReadAllBytes(template);
        if (packed.Length < 16 || BitConverter.ToUInt32(packed, 0) != ResourceUtils.FlagInfo.RSC85Magic)
            throw new InvalidDataException("The template is not an RSC85 resource.");
        int resourceType = BitConverter.ToInt32(packed, 4);
        if (resourceType == 2)
            throw new InvalidDataException("Encrypted RSC85 resources are not supported by this command.");
        byte[] original = ResourceUtils.ResourceInfo.GetDataFromResourceBytes(packed);
        byte[] unpacked = File.ReadAllBytes(source);
        if (original == null || original.Length != unpacked.Length)
            throw new InvalidDataException("The unpacked resource length must match the template.");

        byte[] compressed = DataUtils.CompressZStandard(unpacked);
        byte[] result = new byte[16 + compressed.Length];
        Buffer.BlockCopy(packed, 0, result, 0, 16);
        Buffer.BlockCopy(compressed, 0, result, 16, compressed.Length);
        byte[] verified = ResourceUtils.ResourceInfo.GetDataFromResourceBytes(result);
        if (verified == null || !verified.SequenceEqual(unpacked))
            throw new InvalidDataException("The packed resource did not verify after compression.");
        AtomicWrite(target, result);
        Console.WriteLine(template + "\t" + target + "\tpackedBytes="
            + result.Length.ToString(CultureInfo.InvariantCulture));
        return 0;
    }

    private static void LoadFileNames()
    {
        string appRoot = AppDomain.CurrentDomain.BaseDirectory;
        string namesPath = Path.Combine(appRoot, "Settings", "ImportedFileNames.txt");
        using (FileStream names = new FileStream(
            namesPath, FileMode.Open, FileAccess.Read, FileShare.Read))
        {
            RPF6FileNameHandler.LoadNames(names);
        }
    }

    private static void SetPlatform(string archivePath)
    {
        byte[] value = new byte[4];
        using (FileStream input = new FileStream(
            archivePath, FileMode.Open, FileAccess.Read, FileShare.Read))
        {
            if (input.Length < 12)
                throw new InvalidDataException("The file is too small to be an RPF6 archive.");
            input.Position = 8;
            if (input.Read(value, 0, value.Length) != value.Length)
                throw new EndOfStreamException();
        }
        AppGlobals.SetPlatform(
            BitConverter.ToUInt32(value, 0) == 0
                ? AppGlobals.PlatformEnum.Xbox
                : AppGlobals.PlatformEnum.Switch);
    }

    private static IEnumerable<RPF6.RPF6TOC.TOCSuperEntry> Files(
        RPF6 archive, string pattern)
    {
        Regex matcher = Wildcard(pattern);
        return archive.TOC.SuperEntries.Where(delegate(RPF6.RPF6TOC.TOCSuperEntry entry)
        {
            return !entry.IsDir && matcher.IsMatch(NormalizePath(entry.Entry.GetPath()));
        });
    }

    private static int List(RPF6 archive, string pattern)
    {
        int count = 0;
        Console.WriteLine("path\tstoredSize\ttotalSize\tcompressed\tresource");
        foreach (RPF6.RPF6TOC.TOCSuperEntry entry in Files(archive, pattern))
        {
            RPF6.RPF6TOC.FileEntry file = entry.Entry.AsFile;
            Console.WriteLine(string.Join("\t", new string[] {
                NormalizePath(entry.Entry.GetPath()),
                file.SizeInArchive.ToString(CultureInfo.InvariantCulture),
                file.FlagInfo.GetTotalSize().ToString(CultureInfo.InvariantCulture),
                file.FlagInfo.IsCompressed ? "1" : "0",
                file.FlagInfo.IsResource ? "1" : "0"
            }));
            count++;
        }
        Console.Error.WriteLine("LISTED\t" + count.ToString(CultureInfo.InvariantCulture));
        return 0;
    }

    private static int Extract(RPF6 archive, string outputRoot, string pattern)
    {
        Directory.CreateDirectory(outputRoot);
        string rootWithSeparator = EnsureTrailingSeparator(Path.GetFullPath(outputRoot));
        int count = 0;
        foreach (RPF6.RPF6TOC.TOCSuperEntry entry in Files(archive, pattern))
        {
            string archivePath = NormalizePath(entry.Entry.GetPath());
            string relative = archivePath.StartsWith("root/", StringComparison.OrdinalIgnoreCase)
                ? archivePath.Substring(5)
                : archivePath;
            string target = Path.GetFullPath(Path.Combine(
                outputRoot, relative.Replace('/', Path.DirectorySeparatorChar)));
            if (!target.StartsWith(rootWithSeparator, StringComparison.OrdinalIgnoreCase))
                throw new InvalidDataException("Archive entry escapes the output directory: " + archivePath);

            string parent = Path.GetDirectoryName(target);
            if (!string.IsNullOrEmpty(parent))
                Directory.CreateDirectory(parent);
            string temporary = target + ".lexeditor.tmp";
            using (FileStream output = new FileStream(
                temporary, FileMode.Create, FileAccess.Write, FileShare.None))
            {
                archive.TOC.ExtractFile(entry, output);
                output.Flush(true);
            }
            if (File.Exists(target))
                File.Replace(temporary, target, null);
            else
                File.Move(temporary, target);
            Console.WriteLine(archivePath + "\t" + target);
            count++;
        }
        Console.Error.WriteLine("EXTRACTED\t" + count.ToString(CultureInfo.InvariantCulture));
        return count == 0 ? 3 : 0;
    }

    private static int UnpackResources(RPF6 archive, string outputRoot, string pattern)
    {
        Directory.CreateDirectory(outputRoot);
        string rootWithSeparator = EnsureTrailingSeparator(Path.GetFullPath(outputRoot));
        int count = 0;
        foreach (RPF6.RPF6TOC.TOCSuperEntry entry in Files(archive, pattern))
        {
            RPF6.RPF6TOC.FileEntry file = entry.Entry.AsFile;
            if (!file.FlagInfo.IsResource)
                continue;

            string archivePath = NormalizePath(entry.Entry.GetPath());
            string relative = archivePath.StartsWith("root/", StringComparison.OrdinalIgnoreCase)
                ? archivePath.Substring(5)
                : archivePath;
            string target = Path.GetFullPath(Path.Combine(
                outputRoot, relative.Replace('/', Path.DirectorySeparatorChar)));
            if (!target.StartsWith(rootWithSeparator, StringComparison.OrdinalIgnoreCase))
                throw new InvalidDataException("Archive entry escapes the output directory: " + archivePath);

            string parent = Path.GetDirectoryName(target);
            if (!string.IsNullOrEmpty(parent))
                Directory.CreateDirectory(parent);

            archive.RPFIO.Position = file.GetOffset();
            byte[] resource = ResourceUtils.ResourceInfo.GetDataFromResourceBytes(
                archive.RPFIO.ReadBytes(file.SizeInArchive));
            string temporary = target + ".lexeditor.tmp";
            using (FileStream output = new FileStream(
                temporary, FileMode.Create, FileAccess.Write, FileShare.None))
            {
                output.Write(resource, 0, resource.Length);
                output.Flush(true);
            }
            if (File.Exists(target))
                File.Replace(temporary, target, null);
            else
                File.Move(temporary, target);
            Console.WriteLine(string.Join("\t", new string[] {
                archivePath,
                target,
                "objectStart=" + file.FlagInfo.RSC85_ObjectStart.ToString(CultureInfo.InvariantCulture),
                "resourceBytes=" + resource.Length.ToString(CultureInfo.InvariantCulture)
            }));
            count++;
        }
        Console.Error.WriteLine("UNPACKED\t" + count.ToString(CultureInfo.InvariantCulture));
        return count == 0 ? 3 : 0;
    }

    private static int Decompile(RPF6 archive, string outputRoot, string pattern)
    {
        Directory.CreateDirectory(outputRoot);
        string rootWithSeparator = EnsureTrailingSeparator(Path.GetFullPath(outputRoot));
        string previousDirectory = Directory.GetCurrentDirectory();
        int count = 0;
        try
        {
            Directory.SetCurrentDirectory(AppDomain.CurrentDomain.BaseDirectory);
            foreach (RPF6.RPF6TOC.TOCSuperEntry entry in Files(archive, pattern))
            {
                RPF6.RPF6TOC.FileEntry file = entry.Entry.AsFile;
                if (!file.FlagInfo.IsResource)
                    continue;

                string archivePath = NormalizePath(entry.Entry.GetPath());
                string relative = archivePath.StartsWith("root/", StringComparison.OrdinalIgnoreCase)
                    ? archivePath.Substring(5)
                    : archivePath;
                relative = Path.ChangeExtension(relative, ".c");
                string target = Path.GetFullPath(Path.Combine(
                    outputRoot, relative.Replace('/', Path.DirectorySeparatorChar)));
                if (!target.StartsWith(rootWithSeparator, StringComparison.OrdinalIgnoreCase))
                    throw new InvalidDataException("Archive entry escapes the output directory: " + archivePath);

                string parent = Path.GetDirectoryName(target);
                if (!string.IsNullOrEmpty(parent))
                    Directory.CreateDirectory(parent);

                archive.RPFIO.Position = file.GetOffset();
                byte[] resource = ResourceUtils.ResourceInfo.GetDataFromResourceBytes(
                    archive.RPFIO.ReadBytes(file.SizeInArchive));
                using (MemoryStream stream = new MemoryStream(resource, false))
                {
                    IOReader.Endian endian = AppGlobals.Platform == AppGlobals.PlatformEnum.Switch
                        ? IOReader.Endian.Little
                        : IOReader.Endian.Big;
                    IOReader reader = new IOReader(stream, endian);
                    reader.BaseStream.Seek(file.FlagInfo.RSC85_ObjectStart, SeekOrigin.Begin);
                    new ScriptFile(reader, file);
                }

                string temporary = target + ".lexeditor.tmp";
                File.WriteAllText(temporary, ScriptViewerForm.DecompiledCode);
                if (File.Exists(target))
                    File.Replace(temporary, target, null);
                else
                    File.Move(temporary, target);
                Console.WriteLine(archivePath + "\t" + target);
                count++;
            }
        }
        finally
        {
            Directory.SetCurrentDirectory(previousDirectory);
        }
        Console.Error.WriteLine("DECOMPILED\t" + count.ToString(CultureInfo.InvariantCulture));
        return count == 0 ? 3 : 0;
    }

    private static int ExportTextures(RPF6 archive, string outputRoot, string pattern)
    {
        Directory.CreateDirectory(outputRoot);
        string rootWithSeparator = EnsureTrailingSeparator(Path.GetFullPath(outputRoot));
        int dictionaries = 0;
        int textures = 0;
        foreach (RPF6.RPF6TOC.TOCSuperEntry entry in Files(archive, pattern))
        {
            RPF6.RPF6TOC.FileEntry file = entry.Entry.AsFile;
            if (!file.FlagInfo.IsResource)
                continue;

            string archivePath = NormalizePath(entry.Entry.GetPath());
            string relative = archivePath.StartsWith("root/", StringComparison.OrdinalIgnoreCase)
                ? archivePath.Substring(5)
                : archivePath;
            relative = Path.ChangeExtension(relative, null);
            string dictionaryRoot = Path.GetFullPath(Path.Combine(
                outputRoot, relative.Replace('/', Path.DirectorySeparatorChar)));
            if (!EnsureTrailingSeparator(dictionaryRoot).StartsWith(
                    rootWithSeparator, StringComparison.OrdinalIgnoreCase))
                throw new InvalidDataException(
                    "Archive entry escapes the output directory: " + archivePath);
            Directory.CreateDirectory(dictionaryRoot);

            archive.RPFIO.Position = file.GetOffset();
            byte[] resource = ResourceUtils.ResourceInfo.GetDataFromResourceBytes(
                archive.RPFIO.ReadBytes(file.SizeInArchive));
            using (MemoryStream stream = new MemoryStream(resource, false))
            {
                IOReader.Endian endian = AppGlobals.Platform == AppGlobals.PlatformEnum.Switch
                    ? IOReader.Endian.Little
                    : IOReader.Endian.Big;
                IOReader reader = new IOReader(stream, endian);
                reader.BaseStream.Seek(file.FlagInfo.RSC85_ObjectStart, SeekOrigin.Begin);
                TextureViewerForm.XTD_TextureDictionary dictionary =
                    new TextureViewerForm.XTD_TextureDictionary(reader, file);
                Magic_RDR.RPF.Texture.TextureInfo[] infos =
                    TextureViewerForm.XTD_TextureDictionary.TexInfos;
                Console.Error.WriteLine(string.Join("\t", new string[] {
                    "DICTIONARY",
                    archivePath,
                    "objectStart=" + file.FlagInfo.RSC85_ObjectStart.ToString(CultureInfo.InvariantCulture),
                    "resourceBytes=" + resource.Length.ToString(CultureInfo.InvariantCulture),
                    "declared=" + dictionary.TextureCount.ToString(CultureInfo.InvariantCulture),
                    "decoded=" + infos.Length.ToString(CultureInfo.InvariantCulture)
                }));
                bool useMetadataFallback = infos.Length == 0 &&
                    dictionary.TexturesPointers != null;
                int count = useMetadataFallback
                    ? dictionary.TexturesPointers.Length
                    : infos.Length;
                for (int index = 0; index < count; index++)
                {
                    Magic_RDR.RPF.Texture.TextureInfo info;
                    try
                    {
                        info = useMetadataFallback
                            ? ReadTextureInfo(reader, file, dictionary.TexturesPointers[index])
                            : infos[index];
                    }
                    catch (Exception error)
                    {
                        Console.Error.WriteLine("TEXTURE_ERROR\t" + archivePath + "\t"
                            + index.ToString(CultureInfo.InvariantCulture) + "\t"
                            + error.GetType().Name + "\t" + error.Message);
                        continue;
                    }
                    if (info == null)
                        continue;
                    string sourceFormat = AppGlobals.Platform == AppGlobals.PlatformEnum.Switch &&
                        dictionary.TexturesPointers != null &&
                        index < dictionary.TexturesPointers.Length
                            ? ReadSwitchTextureFormat(reader, dictionary.TexturesPointers[index])
                            : info.PixelFormat.ToString();
                    string safeName = SafeFileName(info.TextureName);
                    if (sourceFormat == "CRND" &&
                        safeName.EndsWith(".crn", StringComparison.OrdinalIgnoreCase))
                    {
                        safeName = safeName.Substring(0, safeName.Length - 4);
                    }
                    string target = Path.Combine(dictionaryRoot,
                        index.ToString("D4", CultureInfo.InvariantCulture) + "_" + safeName +
                        (sourceFormat == "CRND" ? ".crn" : ".dds"));
                    if (sourceFormat == "CRND")
                    {
                        reader.BaseStream.Position = info.TextureDataPointer;
                        File.WriteAllBytes(target, reader.ReadBytes(checked((int)info.TextureSize)));
                    }
                    else
                    {
                        Magic_RDR.RPF.Texture.SaveDDS(reader, target, info);
                    }
                    Console.WriteLine(string.Join("\t", new string[] {
                        archivePath,
                        index.ToString(CultureInfo.InvariantCulture),
                        info.TextureName,
                        info.Width.ToString(CultureInfo.InvariantCulture),
                        info.Height.ToString(CultureInfo.InvariantCulture),
                        info.MipMaps.ToString(CultureInfo.InvariantCulture),
                        sourceFormat,
                        target
                    }));
                    textures++;
                }
            }
            dictionaries++;
        }
        Console.Error.WriteLine("TEXTURES\t" + textures.ToString(CultureInfo.InvariantCulture)
            + "\tDICTIONARIES\t" + dictionaries.ToString(CultureInfo.InvariantCulture));
        return dictionaries == 0 ? 3 : 0;
    }

    private static string ReadSwitchTextureFormat(IOReader reader, uint pointer)
    {
        reader.BaseStream.Seek(pointer + 0x24, SeekOrigin.Begin);
        return reader.ReadString(IOReader.StringType.ASCII, 4);
    }

    private static Magic_RDR.RPF.Texture.TextureInfo ReadTextureInfo(
        IOReader reader,
        RPF6.RPF6TOC.FileEntry file,
        uint pointer)
    {
        reader.BaseStream.Seek(pointer + 0x14, SeekOrigin.Begin);
        uint textureSize = reader.ReadUInt32();
        int namePointer = reader.ReadOffset(reader.ReadInt32());
        int d3dBaseTexturePointer = reader.ReadOffset(reader.ReadInt32());
        ushort width = reader.ReadUInt16();
        ushort height = reader.ReadUInt16();
        int mipMaps = reader.ReadInt32();
        int textureDataPointer;
        int mipDataPointer = 0;
        Magic_RDR.RPF.Texture.TextureType pixelFormat;

        if (AppGlobals.Platform == AppGlobals.PlatformEnum.Switch)
        {
            reader.BaseStream.Seek(reader.BaseStream.Position - 4, SeekOrigin.Begin);
            string format = reader.ReadString(IOReader.StringType.ASCII, 4);
            switch (format)
            {
                case "CRND":
                case "DXT1":
                    pixelFormat = Magic_RDR.RPF.Texture.TextureType.DXT1;
                    break;
                case "DXT3":
                    pixelFormat = Magic_RDR.RPF.Texture.TextureType.DXT3;
                    break;
                case "DXT5":
                    pixelFormat = Magic_RDR.RPF.Texture.TextureType.DXT5;
                    break;
                case "2\0\0\0":
                    pixelFormat = Magic_RDR.RPF.Texture.TextureType.L8;
                    break;
                default:
                    pixelFormat = Magic_RDR.RPF.Texture.TextureType.A8R8G8B8;
                    break;
            }
            reader.ReadByte();
            reader.ReadUInt16();
            mipMaps = reader.ReadByte();
            for (int index = 0; index < 6; index++)
                reader.ReadSingle();
            reader.ReadOffset(reader.ReadInt32());
            reader.ReadOffset(reader.ReadInt32());
            textureDataPointer = reader.ReadOffset(reader.ReadInt32());
            if ((textureDataPointer >> 28) == 6)
            {
                textureDataPointer = file.FlagInfo.BaseResourceSizeV
                    + reader.GetDataOffset(textureDataPointer);
            }
            if (textureSize == 0)
            {
                textureSize = (uint)(pixelFormat == Magic_RDR.RPF.Texture.TextureType.DXT1
                    ? width * height / 2
                    : width * height);
            }
        }
        else
        {
            reader.BaseStream.Seek(d3dBaseTexturePointer + 0x1C, SeekOrigin.Begin);
            int format = reader.ReadInt32();
            int value = reader.ReadInt32();
            reader.ReadOffset(value);
            pixelFormat = (Magic_RDR.RPF.Texture.TextureType)(value & byte.MaxValue);
            reader.ReadInt32();
            reader.ReadInt32();
            reader.ReadInt32();
            int flags = reader.ReadInt32();
            uint baseAddress = (uint)(value >> 0xC);
            textureDataPointer = ((int)(baseAddress << 12) & 0xFFFFFFF)
                + file.FlagInfo.BaseResourceSizeV;
            uint mipAddress = (uint)(flags >> 0xC);
            mipDataPointer = ((int)(mipAddress << 12) & 0xFFFFFFF)
                + file.FlagInfo.BaseResourceSizeV;
        }

        string name = reader.ReadCustomString(
            IOReader.StringType.ASCII_NULL_TERMINATED, 0, namePointer);
        return new Magic_RDR.RPF.Texture.TextureInfo
        {
            TextureName = name,
            Width = width,
            Height = height,
            MipMaps = mipMaps,
            TextureSize = textureSize,
            TextureDataPointer = textureDataPointer,
            MipDataPointer = mipDataPointer,
            PixelFormat = pixelFormat
        };
    }

    private static string SafeFileName(string value)
    {
        string result = value ?? "texture";
        foreach (char invalid in Path.GetInvalidFileNameChars())
            result = result.Replace(invalid, '_');
        result = result.Trim();
        return result.Length == 0 ? "texture" : result;
    }

    private static Regex Wildcard(string pattern)
    {
        string normalized = NormalizePath(pattern);
        string optionalPath = normalized.IndexOf('/') < 0 ? "(?:.*/)?" : "";
        string expression = "^" + optionalPath + Regex.Escape(normalized)
            .Replace("\\*\\*", ".*")
            .Replace("\\*", "[^/]*")
            .Replace("\\?", "[^/]") + "$";
        return new Regex(expression, RegexOptions.IgnoreCase | RegexOptions.CultureInvariant);
    }

    private static string NormalizePath(string value)
    {
        return value.Replace('\\', '/');
    }

    private static string EnsureTrailingSeparator(string value)
    {
        return value.EndsWith(Path.DirectorySeparatorChar.ToString(), StringComparison.Ordinal)
            ? value
            : value + Path.DirectorySeparatorChar;
    }
}
