using Helper;
using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Reflection;
using System.Runtime.InteropServices;



namespace RDR2_RPF_Tool.Core
{
    public enum Compressorid : byte
    {
        None = 0,
        Deflate,
        Oodle
    }

    public enum Platform : ushort
    {
        Pc = 121,
        Ps4 = 111
    }
    public enum GetResourceType : byte
    {
        None = 0,
        Text = 5
    }

    public class RPF8
    {

        public readonly uint RPF8MAGIC = 0x52504638;
        public string FilePath;
        public RPFC RPFCFile;


        public struct Rpf8Header
        {
            public uint Magic;
            public int EntryCount;
            public int NamesLength;
            public ushort DecryptionTag;
            [MarshalAs(UnmanagedType.U2)]
            public Platform PlatformId;
        }


        public class Entry
        {
            public Platform platform;
            public ulong Val1
            {
                get; set;
            }
            public ulong Val2
            {
                get; set;
            }
            public ulong Val3
            {
                get; set;
            }

            public string GetName()
            {
                return RPFHelper.GetFileName(GetHash()) + RPFHelper.GetFileExt(GetFileExtId(), platform);
            }

            public string GetAttributes()
            {
                var attributes = "";

                if (IsResource)
                {
                    attributes = $"Resourced [Virsion: {(int)GetResourceType()}];";
                }

                if (GetCompressorId() != Compressorid.None)
                {
                    attributes += $"Compressed [{GetCompressorId()}];";
                }

                if (GetEncryptionKeyId() != 255)
                {
                    attributes += "Encrypted;";
                }

                if (string.IsNullOrEmpty(attributes))
                {
                    attributes = "No";
                }

                return attributes;
            }


            #region Val 1
            public uint GetHash()
            {
                return (uint)Val1;
            }
            public void SetHash(uint Hash)
            {

                Val1 = Val1.ReplaceBits(Hash, 0, 32);
            }

            public byte GetEncryptionConfig()
            {
                return (byte)((Val1 >> 32) & 0xFF);
            }
            public void SetEncryptionConfig(byte EncryptionConfig)
            {
                Val1 = Val1.ReplaceBits(EncryptionConfig, 32, 8);
            }

            public byte GetEncryptionKeyId()
            {
                return (byte)((Val1 >> 40) & 0xFF);
            }

            public void SetEncryptionKeyId(byte EncryptionKeyId)
            {
                Val1 = Val1.ReplaceBits(EncryptionKeyId, 40, 8);
            }

            public byte GetFileExtId()
            {
                return (byte)((Val1 >> 48) & 0xFF);
            }

            public void SetFileExtId(byte FileExtId)
            {
                Val1 = Val1.ReplaceBits(FileExtId, 48, 8);
            }

            public bool IsResource
            {
                get
                {
                    return Convert.ToBoolean((byte)((Val1 >> 56) & 1));
                }
                set
                {
                    Val1 = Val1.ReplaceBits(Convert.ToByte(value), 56, 1);
                }
            }


            public bool IsSignatureProtected
            {
                get
                {
                    return Convert.ToBoolean((byte)((Val1 >> 57) & 1));
                }
                set
                {
                    Val1 = Val1.ReplaceBits(Convert.ToByte(value), 56, 1);
                }
            }

            #endregion

            #region Val 2
            public int GetOnDiskSize()
            {
                return (int)(Val2 & 0xFFFFFFF) << 4;
            }
            public void SetOnDiskSize(int OnDiskSize)
            {
                Val2 = Val2.ReplaceBits((ulong)(OnDiskSize >> 4), 0, 28);
            }

            public long GetOffset()
            {
                return (long)((Val2 >> 28) & 0x7FFFFFFF) << 4;
            }

            public void SetOffset(long Offset)
            {
                Val2 = Val2.ReplaceBits((ulong)(Offset >> 4), 28, 31);
            }

            public Compressorid GetCompressorId()
            {
                return (Compressorid)((Val2 >> 59) & 0x1F);
            }

            public void SetCompressorId(Compressorid compressorid)
            {
                Val2 = Val2.ReplaceBits((ulong)compressorid, 59, 5);
            }
            #endregion

            #region Val 3

            public int GetOrignalSize()
            {
                if (!IsResource)
                {
                    return (int)Val3;
                }
                else
                {
                    return (int)(Val3 & 0xFFFFFFF0) + (int)((Val3 >> 32) & 0xFFFFFFF0);
                }

            }
            public void SetOrignalSize(int Size)
            {
                Val3 = Val3.ReplaceBits((ulong)Size, 0, 32);
            }


            public GetResourceType GetResourceType()
            {
                return (GetResourceType)((Val3 >> 32) & 0xF);
            }


            #endregion



        }





        public IStream Rpf8StreamFile;
        public Rpf8Header header;
        public byte[] rsa_signature;
        public Dictionary<string, Entry> Entries = new Dictionary<string, Entry>();
        public byte[] Names;
        public bool IsTemp = false;

        public static RPF8 Load(string path)
        {
            RPF8 rpf8 = new RPF8();
            rpf8.Rpf8StreamFile = FStream.Open(path, FileMode.Open, FileAccess.Read);
            rpf8.FilePath = path;
            rpf8.Load();
            rpf8.FilePath = Path.GetFullPath(rpf8.FilePath).Replace(Path.GetFullPath(Path.GetDirectoryName(rpf8.FilePath)), "").TrimStart('\\');
            return rpf8;
        }


        public static RPF8 Load(string VirtualPath, byte[] bytes)
        {
            string TempPath = Path.Combine(Path.GetTempPath(), Assembly.GetExecutingAssembly().GetCustomAttribute<AssemblyTitleAttribute>().Title, Path.GetDirectoryName(VirtualPath), DateTime.Now.ToString("yyyy-dd-M--HH-mm-ss"), Path.GetFileName(VirtualPath));

            if (!Directory.Exists(Path.GetDirectoryName(TempPath)))
            {
                Directory.CreateDirectory(Path.GetDirectoryName(TempPath));
            }

            File.WriteAllBytes(TempPath, bytes);

            var rpf8 = RPF8.Load(TempPath);
            rpf8.IsTemp = true;
            rpf8.FilePath = VirtualPath;
            return rpf8;
        }


        public void Load()
        {
            header = Rpf8StreamFile.GetStructureValues<Rpf8Header>();
            if (header.Magic != RPF8MAGIC)
            {
                Rpf8StreamFile.Close();
                throw new Exception($"This file '{FilePath}' is not rpf8 format!");
            }

            rsa_signature = Rpf8StreamFile.GetBytes(0x100);


            MStream memoryList;
            if (header.DecryptionTag != 255)
                memoryList = new MStream(Cipher.GetCipher(header.DecryptionTag, header.PlatformId).Decode(Rpf8StreamFile.GetBytes(header.EntryCount * 24)));
            else
                memoryList = new MStream(Rpf8StreamFile.GetBytes(header.EntryCount * 24));


            for (int i = 0; i < header.EntryCount; i++)
            {
                Entry entry = new Entry();
                entry.platform = header.PlatformId;
                entry.Val1 = memoryList.GetUInt64Value();
                entry.Val2 = memoryList.GetUInt64Value();
                entry.Val3 = memoryList.GetUInt64Value();
                Entries.Add(entry.GetName(), entry);
            }


            Rpf8StreamFile.Seek(Rpf8StreamFile.GetSize() - header.NamesLength, System.IO.SeekOrigin.Begin);
            Names = Rpf8StreamFile.GetBytes(header.NamesLength);
            Console.WriteLine("FilePath: " + FilePath);
        }



        public void Destroy()
        {
            if (Rpf8StreamFile != null)
            {
                var path = Rpf8StreamFile.Name;
                Rpf8StreamFile.Close();
                Rpf8StreamFile.Dispose();
                Rpf8StreamFile = null;
                Entries.Clear();
                header = new Rpf8Header();
                rsa_signature = null;
                Names = null;

                if (IsTemp)
                {
                    File.Delete(path);
                }
            }
        }

        ~RPF8()
        {
            Destroy();
        }


        void UpdateHeader(IStream fStream)
        {
            long oldPosition = fStream.Position;
            fStream.Position = 0;
            header.DecryptionTag = 0xff;
            fStream.SetStructureValus(header);
            fStream.SetBytes(rsa_signature);
            foreach (KeyValuePair<string, Entry> entry in Entries)
            {
                fStream.SetUInt64Value(entry.Value.Val1);
                fStream.SetUInt64Value(entry.Value.Val2);
                fStream.SetUInt64Value(entry.Value.Val3);
            }

            if (RPFCFile != null && !IsTemp)
            {
                int HeaderSize = (int)fStream.GetPosition();
                fStream.Position = 0;
                byte[] Header = fStream.GetBytes(HeaderSize);
                Console.WriteLine("This is the path: " + FilePath);
                RPFCFile.UpdateRpfBlock(RPFHelper.FileHash(FilePath, header.PlatformId), Header);
            }
            fStream.Position = oldPosition;
        }

        public void ReBuild()
        {
            IStream fStream = new FStream(Rpf8StreamFile.Name + ".temp.rpf", FileMode.Create, FileAccess.ReadWrite);

            UpdateHeader(fStream);
            fStream.Seek(16 + 256 + (24 * Entries.Count));
            fStream.SetPadding();

            for (int i = 0; i < Entries.Count; i++)
            {
                KeyValuePair<string, Entry> entry = Entries.ElementAt(i);
                Entry FileEntrie = entry.Value;

                Rpf8StreamFile.Seek(FileEntrie.GetOffset());


                // Console.WriteLine("NFile off: " + fStream.Position);
                // Console.WriteLine("File off: " + FileEntrie.GetOffset());
                // Console.WriteLine("File size: " + FileEntrie.GetOnDiskSize());


                FileEntrie.SetOffset(fStream.Position);

                fStream.SetBytes(Rpf8StreamFile.GetBytes(FileEntrie.GetOnDiskSize()));
                fStream.SetPadding();//for make sure
                Entries[entry.Key] = FileEntrie;
            }

            fStream.SetBytes(Names);

            UpdateHeader(fStream);
            fStream.Close();
            Rpf8StreamFile.Close();

            File.Delete(Rpf8StreamFile.Name);
            File.Move(Rpf8StreamFile.Name + ".temp.rpf", Rpf8StreamFile.Name);


            this.Rpf8StreamFile = FStream.Open(Rpf8StreamFile.Name, FileMode.Open, FileAccess.ReadWrite);
        }


        public void ImportFiles(string FileMap)
        {
            ImportFiles(File.ReadAllLines(FileMap), Path.GetDirectoryName(FileMap));
        }


        public void ImportFiles(string[] FileList, string Directory)
        {
            string[] Files = FileList.Where(x => !string.IsNullOrWhiteSpace(x)).ToArray();


            foreach (string FilePath in Files)
            {
                string path = Path.Combine(Directory, FilePath);
                if (!File.Exists(path))
                {
                    throw new FileNotFoundException("Can't find this file in directory: " + path);
                }
            }



            foreach (string filePath in Files)
            {
                string Hash = RPFHelper.FileHash(filePath, header.PlatformId);

                // Console.WriteLine("Hash: "+ Hash);

                if (!Entries.ContainsKey(Hash))
                {
                    Console.WriteLine("Can't find this file '{0}'", filePath);
                    continue;
                }


                string FilePath = Path.Combine(Directory, filePath);

                byte[] FileBytes = File.ReadAllBytes(FilePath);

                ImportFile(Hash, FileBytes);
            }
        }



        public void ImportFiles(string[] Entrykeys, byte[][] FilesBytes)
        {
            if (FilesBytes.Length!= Entrykeys.Length)
            {
                throw new Exception("Entrykeys and FilesBytes size do not match");
            }
            //Check Files
            for (int i=0;i< Entrykeys.Length;i++)
            {
                if (Entries[Entrykeys[i]].IsResource)
                {
                    RSC8.ReadRsc8(FilesBytes[i]); //for make sure the given file is resource file
                }
            }

            //Resize RPF File
            Rpf8StreamFile.SetLength(Rpf8StreamFile.GetSize() - header.NamesLength);
            Rpf8StreamFile.Seek(Rpf8StreamFile.Length);
            Rpf8StreamFile.SetPadding();

            for (int i = 0; i < Entrykeys.Length; i++)
            {
                Entry entry = Entries[Entrykeys[i]];
                entry.SetOffset(Rpf8StreamFile.Length);
                Rpf8StreamFile.SetBytes(FilesBytes[i]);
                int padding = Rpf8StreamFile.SetPadding();

                //update entry info
                if (!entry.IsResource)
                {
                    entry.SetEncryptionConfig(0);
                    entry.SetEncryptionKeyId(0xff);
                    entry.SetCompressorId(Compressorid.None);
                    entry.SetOnDiskSize(padding + FilesBytes[i].Length);
                    entry.SetOrignalSize(FilesBytes[i].Length);
                }
                else
                {
                    var Header = RSC8.ReadRsc8(FilesBytes[i]);
                    entry.SetEncryptionConfig(Header.GetEncryptionConfig());
                    entry.SetEncryptionKeyId(Header.GetEncryptionKeyId());
                    entry.SetCompressorId(Header.GetCompressorId());
                    entry.SetOnDiskSize(padding + FilesBytes[i].Length);
                    entry.Val3 = Header.Val2;
                }
                Entries[Entrykeys[i]] = entry;

                if (Entrykeys[i].EndsWith(".rpf", StringComparison.OrdinalIgnoreCase))
                {
                    RPFCFile.UpdateRpfBlock(RPFHelper.FileHash(Entrykeys[i], header.PlatformId),
                    FilesBytes[i].ToList().GetRange(0, 16 + 256 + (24 * BitConverter.ToInt32(FilesBytes[i], 4))).ToArray());
                }
            }

            UpdateHeader(Rpf8StreamFile);
            Rpf8StreamFile.Seek(Rpf8StreamFile.Length);
            Rpf8StreamFile.SetBytes(Names);
            
        }

        
        public void ImportFile(string EntryKey, byte[] FileBytes)
        {
            Console.WriteLine("Entry key: " + EntryKey);

            Entry entry = Entries[EntryKey];

            if (entry.IsResource)
            {
                RSC8.ReadRsc8(FileBytes); //for make sure the given file is resource file
            }

            Rpf8StreamFile.SetLength(Rpf8StreamFile.GetSize() - header.NamesLength);
            Rpf8StreamFile.Seek(Rpf8StreamFile.Length);
            Rpf8StreamFile.SetPadding();

            entry.SetOffset(Rpf8StreamFile.Length);
            Rpf8StreamFile.SetBytes(FileBytes);
            int padding = Rpf8StreamFile.SetPadding();

            //update entry info
            if (!entry.IsResource)
            {
                entry.SetEncryptionConfig(0);
                entry.SetEncryptionKeyId(0xff);
                entry.SetCompressorId(Compressorid.None);
                entry.SetOnDiskSize(padding + FileBytes.Length);
                entry.SetOrignalSize(FileBytes.Length);
            }
            else
            {
                var Header = RSC8.ReadRsc8(FileBytes);
                entry.SetEncryptionConfig(Header.GetEncryptionConfig());
                entry.SetEncryptionKeyId(Header.GetEncryptionKeyId());
                entry.SetCompressorId(Header.GetCompressorId());
                entry.SetOnDiskSize(padding + FileBytes.Length);
                entry.Val3 = Header.Val2;
            }

            Entries[EntryKey] = entry;
            UpdateHeader(Rpf8StreamFile);
            Rpf8StreamFile.Seek(Rpf8StreamFile.Length);
            Rpf8StreamFile.SetBytes(Names);


            if (EntryKey.EndsWith(".rpf", StringComparison.OrdinalIgnoreCase))
            {
                RPFCFile.UpdateRpfBlock(RPFHelper.FileHash(EntryKey, header.PlatformId),
                FileBytes.ToList().GetRange(0, 16 + 256 + (24 * BitConverter.ToInt32(FileBytes, 4))).ToArray());
            }

        }



        public byte[] GetFile(string hash, bool DecodeResourceFile = true)
        {

            Entry entry = Entries[hash];

            byte[] Filebytes;

            int raw_size = entry.GetOnDiskSize();
            long offset = entry.GetOffset();

            if (entry.IsSignatureProtected)
            {
                if (raw_size < 0x100)
                    throw new Exception("Signature protected file is too small");

                raw_size -= 0x100;
            }

            if (entry.IsResource)
            {
                if (raw_size < 16)
                    throw new Exception("Resource raw size is too small");
                offset += 16;
                raw_size -= 16;
            }


            Rpf8StreamFile.Seek(offset);

            Filebytes = Rpf8StreamFile.GetBytes(raw_size);

            if (entry.IsResource && DecodeResourceFile || !entry.IsResource)
            {
                Filebytes = Cipher.DecodeBlock(Filebytes, entry);
                Filebytes = Compression.DecompressFile(Filebytes, entry.GetOrignalSize(), entry.GetCompressorId());
            }


            RSC8.CreateRsc8(ref Filebytes, entry, DecodeResourceFile);
            return Filebytes;
        }

    }
}
