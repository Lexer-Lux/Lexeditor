using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Text.Json;
using RageLib.GTA5.RBF;
using RageLib.GTA5.RBFWrappers;
using RDR2_RPF_Tool.Core;

internal static class Program
{
    private const string Usage =
        "usage:\n" +
        "  RpfCli <archive.rpf> <entry> <output>\n" +
        "  RpfCli <archive.rpf> --extract-chain <entry> [nested-entry ...] <output>\n" +
        "  RpfCli <archive.rpf> --extract-chain-xml <entry> [nested-entry ...] <output.xml>\n" +
        "  RpfCli <archive.rpf> --extract-chain-pso-xml <entry> [nested-entry ...] <output.xml>\n" +
        "  RpfCli <archive.rpf> --extract-chain-text-json <entry> [nested-entry ...] <output.json>\n" +
        "  RpfCli <archive.rpf> --extract-prefix <prefix> <output-directory>\n" +
        "  RpfCli <archive.rpf> --extract-selected <output-directory> <entry> [entry ...]\n" +
        "  RpfCli <archive.rpf> --list-chain <entry> [nested-entry ...]\n" +
        "  RpfCli <archive.rpf> --list [filter]\n" +
        "  RpfCli <archive.rpf> --list-content\n" +
        "  RpfCli --rbf-to-xml <input.ymt> <output.xml>\n" +
        "  RpfCli --pso-to-xml <input.ymt> <output.xml>\n" +
        "  RpfCli --yldb-to-json <input.yldb> <output.json>";

    private static string FindEntry(RPF8 archive, string requested)
    {
        string normalized = requested.Replace('\\', '/').TrimStart('/');
        var candidates = new List<string> { normalized, Path.GetFileName(normalized) };
        string[] parts = normalized.Split('/');
        for (int i = 1; i < parts.Length; i++)
            candidates.Add(string.Join("/", parts.Skip(i)));

        foreach (string candidate in candidates.Distinct(StringComparer.OrdinalIgnoreCase))
        {
            if (archive.Entries.ContainsKey(candidate)) return candidate;
            string key = RPFHelper.FileHash(candidate, archive.header.PlatformId);
            if (archive.Entries.ContainsKey(key)) return key;
        }
        throw new FileNotFoundException(requested);
    }

    public static int Main(string[] args)
    {
        if (args.Length == 1 && args[0] == "--version")
        {
            Console.WriteLine($"RpfCli {typeof(Program).Assembly.GetName().Version}");
            return 0;
        }

        if (args.Length == 3 && args[0] == "--rbf-to-xml")
        {
            try
            {
                WriteRbfXmlOutput(args[2], File.ReadAllBytes(args[1]));
                Console.WriteLine($"CONVERTED\t{args[1]}\t{args[2]}");
                return 0;
            }
            catch (Exception error)
            {
                Console.Error.WriteLine($"ERROR\t{error}");
                return 1;
            }
        }

        if (args.Length == 3 && args[0] == "--pso-to-xml")
        {
            try
            {
                WritePsoXmlOutput(args[2], File.ReadAllBytes(args[1]));
                Console.WriteLine($"CONVERTED_PSO\t{args[1]}\t{args[2]}");
                return 0;
            }
            catch (Exception error)
            {
                Console.Error.WriteLine($"ERROR\t{error}");
                return 1;
            }
        }

        if (args.Length == 3 && args[0] == "--yldb-to-json")
        {
            try
            {
                WriteTextJsonOutput(args[2], File.ReadAllBytes(args[1]));
                Console.WriteLine($"CONVERTED_TEXT\t{args[1]}\t{args[2]}");
                return 0;
            }
            catch (Exception error)
            {
                Console.Error.WriteLine($"ERROR\t{error.GetType().Name}\t{error.Message}");
                return 1;
            }
        }

        if (args.Length < 2)
        {
            Console.Error.WriteLine(Usage);
            return 2;
        }

        try
        {
            if (args[1] == "--list-chain")
            {
                if (args.Length < 3)
                {
                    Console.Error.WriteLine(Usage);
                    return 2;
                }
                return ListChain(args[0], args.Skip(2).ToArray());
            }

            if (args[1] == "--extract-chain" || args[1] == "--extract-chain-xml" ||
                args[1] == "--extract-chain-pso-xml" ||
                args[1] == "--extract-chain-text-json")
            {
                if (args.Length < 4)
                {
                    Console.Error.WriteLine(Usage);
                    return 2;
                }
                string conversion = args[1] == "--extract-chain-xml" ? "rbf-xml" :
                    args[1] == "--extract-chain-pso-xml" ? "pso-xml" :
                    args[1] == "--extract-chain-text-json" ? "text-json" : "none";
                return ExtractChain(args[0], args.Skip(2).Take(args.Length - 3).ToArray(),
                    args[^1], conversion);
            }

            RPF8 archive = RPF8.Load(args[0]);
            try
            {
            if (args[1] == "--extract-prefix")
            {
                if (args.Length != 4)
                {
                    Console.Error.WriteLine(Usage);
                    return 2;
                }
                return ExtractPrefix(archive, args[2], args[3]);
            }

            if (args[1] == "--extract-selected")
            {
                if (args.Length < 4)
                {
                    Console.Error.WriteLine(Usage);
                    return 2;
                }
                return ExtractSelected(archive, args[2], args.Skip(3).ToArray());
            }

            if (args[1] == "--list-content")
            {
                if (args.Length != 2)
                {
                    Console.Error.WriteLine(Usage);
                    return 2;
                }
                foreach (string contentKey in archive.Entries.Keys
                    .Where(x => x.EndsWith("content.xml", StringComparison.OrdinalIgnoreCase))
                    .OrderBy(x => x, StringComparer.OrdinalIgnoreCase))
                    Console.WriteLine(contentKey);
                return 0;
            }

            if (args[1] == "--list")
            {
                if (args.Length > 3)
                {
                    Console.Error.WriteLine(Usage);
                    return 2;
                }
                string filter = args.Length == 3 ? args[2] : "";
                foreach (string entryKey in archive.Entries.Keys
                    .Where(x => x.Contains(filter, StringComparison.OrdinalIgnoreCase))
                    .OrderBy(x => x, StringComparer.OrdinalIgnoreCase))
                    Console.WriteLine(entryKey);
                return 0;
            }

                if (args.Length != 3)
                {
                    Console.Error.WriteLine(Usage);
                    return 2;
                }
                string key = FindEntry(archive, args[1]);
                byte[] bytes = archive.GetFile(key, true);
                WriteOutput(args[2], bytes);
                Console.WriteLine($"EXTRACTED\t{args[1]}\t{key}\t{bytes.Length}\t{args[2]}");
                return 0;
            }
            finally
            {
                archive.Destroy();
            }
        }
        catch (Exception error)
        {
            Console.Error.WriteLine($"ERROR\t{error.GetType().Name}\t{error.Message}");
            return 1;
        }
    }

    private static int ExtractChain(string archivePath, string[] entries, string outputPath, string conversion)
    {
        RPF8 archive = RPF8.Load(archivePath);
        try
        {
            for (int index = 0; index < entries.Length; index++)
            {
                string requested = entries[index];
                string key = FindEntry(archive, requested);
                byte[] bytes = archive.GetFile(key, true);
                if (index == entries.Length - 1)
                {
                    if (conversion == "rbf-xml")
                        WriteRbfXmlOutput(outputPath, bytes);
                    else if (conversion == "pso-xml")
                        WritePsoXmlOutput(outputPath, bytes);
                    else if (conversion == "text-json")
                        WriteTextJsonOutput(outputPath, bytes);
                    else
                        WriteOutput(outputPath, bytes);
                    Console.WriteLine($"EXTRACTED\t{requested}\t{key}\t{bytes.Length}\t{outputPath}");
                    return 0;
                }

                if (bytes.Length < 4 || BitConverter.ToUInt32(bytes, 0) != 0x52504638u)
                    throw new InvalidDataException($"Chain entry is not an RPF8 archive: {requested}");

                RPF8 nested = RPF8.Load(requested, bytes);
                archive.Destroy();
                archive = nested;
            }
            throw new InvalidOperationException("No extraction entry was supplied.");
        }
        finally
        {
            archive.Destroy();
        }
    }

    private static int ListChain(string archivePath, string[] entries)
    {
        RPF8 archive = RPF8.Load(archivePath);
        try
        {
            foreach (string requested in entries)
            {
                string key = FindEntry(archive, requested);
                byte[] bytes = archive.GetFile(key, true);
                if (bytes.Length < 4 || BitConverter.ToUInt32(bytes, 0) != 0x52504638u)
                    throw new InvalidDataException($"Chain entry is not an RPF8 archive: {requested}");
                RPF8 nested = RPF8.Load(requested, bytes);
                archive.Destroy();
                archive = nested;
            }
            foreach (string entryKey in archive.Entries.Keys
                .OrderBy(x => x, StringComparer.OrdinalIgnoreCase))
                Console.WriteLine(entryKey);
            return 0;
        }
        finally
        {
            archive.Destroy();
        }
    }

    private static int ExtractPrefix(RPF8 archive, string prefix, string outputDirectory)
    {
        string normalized = prefix.Replace('\\', '/').Trim('/');
        string prefixWithSlash = normalized + "/";
        string[] keys = archive.Entries.Keys
            .Where(key => key.Equals(normalized, StringComparison.OrdinalIgnoreCase) ||
                          key.StartsWith(prefixWithSlash, StringComparison.OrdinalIgnoreCase))
            .OrderBy(key => key, StringComparer.OrdinalIgnoreCase)
            .ToArray();
        if (keys.Length == 0)
            throw new DirectoryNotFoundException(prefix);

        string root = Path.GetFullPath(outputDirectory);
        int separator = normalized.LastIndexOf('/');
        string parentPrefix = separator >= 0 ? normalized.Substring(0, separator + 1) : "";
        Directory.CreateDirectory(root);
        foreach (string key in keys)
        {
            string relativeKey = parentPrefix.Length > 0 &&
                key.StartsWith(parentPrefix, StringComparison.OrdinalIgnoreCase)
                ? key.Substring(parentPrefix.Length)
                : key;
            string relative = relativeKey.Replace('/', Path.DirectorySeparatorChar);
            string output = Path.GetFullPath(Path.Combine(root, relative));
            if (!output.StartsWith(root + Path.DirectorySeparatorChar,
                    StringComparison.OrdinalIgnoreCase))
                throw new InvalidDataException($"Entry path leaves the output directory: {key}");
            byte[] bytes = archive.GetFile(key, true);
            WriteOutput(output, bytes);
            Console.WriteLine($"EXTRACTED\t{key}\t{bytes.Length}\t{output}");
        }
        Console.WriteLine($"EXTRACTED_PREFIX\t{normalized}\t{keys.Length}\t{root}");
        return 0;
    }

    private static int ExtractSelected(RPF8 archive, string outputDirectory, string[] entries)
    {
        string root = Path.GetFullPath(outputDirectory);
        Directory.CreateDirectory(root);
        foreach (string requested in entries.Distinct(StringComparer.OrdinalIgnoreCase))
        {
            string normalized = requested.Replace('\\', '/').TrimStart('/');
            string relative = normalized.Replace('/', Path.DirectorySeparatorChar);
            string output = Path.GetFullPath(Path.Combine(root, relative));
            if (!output.StartsWith(root + Path.DirectorySeparatorChar,
                    StringComparison.OrdinalIgnoreCase))
                throw new InvalidDataException($"Entry path leaves the output directory: {requested}");
            string key = FindEntry(archive, requested);
            byte[] bytes = archive.GetFile(key, true);
            WriteOutput(output, bytes);
            Console.WriteLine($"EXTRACTED\t{requested}\t{key}\t{bytes.Length}\t{output}");
        }
        Console.WriteLine($"EXTRACTED_SELECTED\t{entries.Length}\t{root}");
        return 0;
    }

    private static void WriteOutput(string outputPath, byte[] bytes)
    {
        Directory.CreateDirectory(Path.GetDirectoryName(Path.GetFullPath(outputPath))!);
        File.WriteAllBytes(outputPath, bytes);
    }

    private static void WriteRbfXmlOutput(string outputPath, byte[] bytes)
    {
        Directory.CreateDirectory(Path.GetDirectoryName(Path.GetFullPath(outputPath))!);
        using MemoryStream input = new MemoryStream(bytes, false);
        RbfStructure root = new RbfFile().Load(input);
        using FileStream output = new FileStream(outputPath, FileMode.Create, FileAccess.Write, FileShare.None);
        new RbfXmlExporter().Export(root, output);
    }

    private static void WritePsoXmlOutput(string outputPath, byte[] bytes)
    {
        Directory.CreateDirectory(Path.GetDirectoryName(Path.GetFullPath(outputPath))!);
        PsoConverter.WriteXml(outputPath, bytes);
    }

    private static void WriteTextJsonOutput(string outputPath, byte[] bytes)
    {
        var values = new SortedDictionary<string, string>(StringComparer.Ordinal);
        foreach (string line in DataBaseFile.ExportTexts(bytes))
        {
            int separator = line.IndexOf('=');
            if (separator <= 0) continue;
            uint hash = Convert.ToUInt32(line.Substring(2, separator - 2), 16);
            values[$"0x{hash:X8}"] = line.Substring(separator + 1);
        }
        Directory.CreateDirectory(Path.GetDirectoryName(Path.GetFullPath(outputPath))!);
        string json = JsonSerializer.Serialize(values, new JsonSerializerOptions { WriteIndented = false });
        File.WriteAllText(outputPath, json + Environment.NewLine);
    }
}
