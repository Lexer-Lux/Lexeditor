using System;
using System.IO;
using Magic_RDR;
using Magic_RDR.Application;
using Magic_RDR.RPF;

internal static class Rpf6CopyFixture
{
    private static int Main(string[] args)
    {
        if (args.Length != 2)
        {
            Console.Error.WriteLine("Rpf6CopyFixture <output.rpf> <payload-file>");
            return 2;
        }
        string outputPath = Path.GetFullPath(args[0]);
        byte[] payload = File.ReadAllBytes(Path.GetFullPath(args[1]));
        AppGlobals.SetPlatform(AppGlobals.PlatformEnum.Switch);

        RPF6 archive = new RPF6();
        archive.Header.Encrypted = false;
        // The PC port uses the Switch/RSC85 layout in MagicRDR. The bridge's
        // platform probe distinguishes that layout by a non-zero header word.
        archive.Header.DebugDataOffset = 1;

        RPF6.RPF6TOC.TOCSuperEntry root = new RPF6.RPF6TOC.TOCSuperEntry();
        RPF6.RPF6TOC.DirectoryEntry rootEntry = new RPF6.RPF6TOC.DirectoryEntry();
        rootEntry.Name = "root";
        root.Entry = rootEntry;
        rootEntry.SuperOwner = root;
        archive.TOC.SuperEntries.Add(root);

        RPF6.RPF6TOC.TOCSuperEntry child = new RPF6.RPF6TOC.TOCSuperEntry();
        RPF6.RPF6TOC.FileEntry file = new RPF6.RPF6TOC.FileEntry();
        file.Name = "test.xml";
        file.Parent = rootEntry;
        file.FlagInfo = new ResourceUtils.FlagInfo();
        file.FlagInfo.IsCompressed = true;
        file.FlagInfo.SetTotalSize(payload.Length, 0);
        file.SizeInArchive = payload.Length;
        child.Entry = file;
        file.SuperOwner = child;
        child.CustomDataStream = new MemoryStream(payload, false);
        child.ReadBackFromRPF = false;
        root.AddChild(child);

        archive.TOC.Rebuild();
        archive.Header.TOCSize = ((archive.Header.EntryCount * 20 + 15) / 16) * 16;
        string parent = Path.GetDirectoryName(outputPath);
        if (!string.IsNullOrEmpty(parent)) Directory.CreateDirectory(parent);
        using (FileStream output = new FileStream(outputPath, FileMode.Create, FileAccess.ReadWrite, FileShare.None))
        {
            archive.Write(output);
            output.Flush(true);
        }
        archive.CloseAllStreams();
        return 0;
    }
}
