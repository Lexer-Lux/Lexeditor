using Helper;
using System;
using System.Collections.Generic;
using System.IO;
using static RDR2_RPF_Tool.Core.RPF8;

namespace RDR2_RPF_Tool.Core
{
    public class RPFC
    {
        public RPF8 rpf8;
        
        public Platform platform;

        public Entry entry;

        public string FileKeyHash;

        public string PFMFilePath;

        public MStream memorylist;

        public bool LoadedFromRPF;

        public struct FileEntry
        {
            public uint hash;
            public int Rpf8Size;
            public int NameSize;
            public int len;
            public string RpfName;
            public long BlockOffset;
            // public byte[] Rpf8Header;
        }


        public Dictionary<string, FileEntry> RPFCValue = new Dictionary<string, FileEntry>();


        public static RPFC Load(RPF8 rpf8)
        {
            RPFC rpfc = new RPFC();
            rpfc.LoadedFromRPF = true;
            rpfc.rpf8 = rpf8;
            rpfc.platform = rpf8.header.PlatformId;
            rpfc.FileKeyHash = RPFHelper.FileHash("0x25CF7830"/*pfm.dat*/, rpfc.platform);


            rpfc.entry = rpf8.Entries[rpfc.FileKeyHash];
            rpfc.LoadFile(rpf8.GetFile(rpfc.FileKeyHash));
            //  Console.WriteLine(rpfc.rpf8.FilePath);

            return rpfc;
        }

        public static RPFC Load(string PfmFile)
        {
            RPFC rpfc = new RPFC();
            rpfc.LoadedFromRPF = false;
            rpfc.PFMFilePath = PfmFile;
            rpfc.platform = Platform.Ps4;
            rpfc.LoadFile(File.ReadAllBytes(PfmFile));
            return rpfc;
        }


        public void LoadFile(byte[] bytes)
        {
            memorylist = new MStream(bytes);

            if (memorylist.GetUIntValue() != 0x43465052 /*RPFC*/)
            {
                throw new Exception("Invalid 'pfm.dat' file!");
            }
            memorylist.Skip(4); //unkown

            int Files = memorylist.GetIntValue();
            memorylist.Seek(44);

            FileEntry[] FilesEntries = new FileEntry[Files];

            for (int i = 0; i < Files; i++)
            {
                memorylist.Skip(4);//HENT
                FilesEntries[i].hash = memorylist.GetUIntValue();
                FilesEntries[i].Rpf8Size = memorylist.GetIntValue();
                FilesEntries[i].NameSize = memorylist.GetIntValue();
                int FileNameLenght = memorylist.GetIntValue();
                string FileName = memorylist.GetStringValue(FileNameLenght).TrimEnd('\0');

                FilesEntries[i].RpfName = FixedPath(FileName);

                //  Console.WriteLine(FilesEntries[i].RpfName);
                int TableCount = memorylist.GetIntValue();
                memorylist.Skip(TableCount * 8);
            }

            memorylist.Skip(4);//HDAT

            for (int i = 0; i < Files; i++)
            {
                FilesEntries[i].BlockOffset = memorylist.GetPosition();
                // FilesEntries[i].Rpf8Header = memorylist.GetBytes(FilesEntries[i].Rpf8Size);
                //Console.WriteLine(FilesEntries[i].BlockOffset);
                memorylist.Skip(FilesEntries[i].Rpf8Size);
                RPFCValue.Add(FilesEntries[i].RpfName, FilesEntries[i]);
            }
        }


        public void UpdateRpfBlock(string FileKey, byte[] Rpfbytes)
        {

            if (!RPFCValue.ContainsKey(FileKey))
            {
                Console.WriteLine("Can't find this entry: " + FileKey);
                return;
            }

            Console.WriteLine("entry: " + FileKey);

            FileEntry fileEntry = RPFCValue[FileKey];
            memorylist.Seek(fileEntry.BlockOffset);
            memorylist.SetBytes(Rpfbytes);

            if (LoadedFromRPF)
            {
                rpf8.ImportFile(FileKeyHash, memorylist.ToArray());
                rpf8.ReBuild();
            }
            else
            {
                memorylist.WriteFile(PFMFilePath);
            }

        }


        public string FixedPath(string path)
        {

            path = path.Replace("update:/", "");
            path = path.Replace("update_platform:/", "");

            if (platform == Platform.Pc)
            {
                path = path.Replace("platform:/", "x64/");
            }
            else if (platform == Platform.Ps4)
            {
                path = path.Replace("platform:/", "ps4/");
            }

            //    Console.WriteLine(path);
            return RPFHelper.FileHash(path, platform);
        }





    }
}
