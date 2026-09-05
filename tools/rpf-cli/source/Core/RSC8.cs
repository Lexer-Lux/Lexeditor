using Helper;
using System;
using System.Runtime.InteropServices;
using static RDR2_RPF_Tool.Core.RPF8;

namespace RDR2_RPF_Tool.Core
{
    public class RSC8
    {


        public static uint RSC8Magic = 0x38435352;

        public struct RSC8Info
        {
            public uint Magic { get; set; }
            public uint Val1 { get; set; }
            public ulong Val2 { get; set; }

            public GetResourceType GetResourceId()
            {
                return (GetResourceType)(Val1 & 0xFF);
            }

            public void SetResourceId(GetResourceType ResourceId)
            {
                Val1 = Val1.ReplaceBits((uint)ResourceId, 0, 8);
            }

            public Compressorid GetCompressorId()
            {

                byte compressorid = (byte)((Val1 >> 8) & 0x1f);//get 5 bits

                if (compressorid == 0x1f)
                {
                    return Compressorid.None;
                }
                else
                {
                    compressorid++;
                    return (Compressorid)compressorid;

                }
            }

            public void SetCompressorId(Compressorid CompressorId)
            {
                Val1 = Val1.ReplaceBits((uint)(CompressorId - 1) & 0x1f, 8, 5);
            }


            public bool IsSignatureProtected
            {
                get
                {
                    return (byte)((Val1 >> 13) & 0x7) != 0;
                }

                set
                {
                    Val1 = Val1.ReplaceBits(Convert.ToUInt32(value), 13, 3);
                }

            }

            public byte GetEncryptionKeyId()
            {
                return (byte)(((Val1 >> 16) & 0xff) - 1);
            }

            public void SetEncryptionKeyId(byte EncryptionKeyId)
            {
                Val1 = Val1.ReplaceBits((uint)(EncryptionKeyId) + 1, 16, 8);
            }

            public byte GetEncryptionConfig()
            {
                return (byte)((Val1 >> 24) & 0xff);
            }

            public void SetEncryptionConfig(byte EncryptionConfig)
            {
                Val1 = Val1.ReplaceBits((uint)(EncryptionConfig), 24, 8);
            }

            public void SetOrignalSize(int Size)
            {
                Val2 = Val2.ReplaceBits((ulong)Size, 0, 32);
            }

        }





        public static void CreateRsc8(ref byte[] bytes, Entry entry, bool UseEntry = false)
        {

            if (!entry.IsResource)
            {
                return;
            }

            var rsc8info = new RSC8Info();

            if (!UseEntry)
            {
                rsc8info.Magic = RSC8Magic;
                rsc8info.SetResourceId(entry.GetResourceType());
                rsc8info.SetCompressorId(entry.GetCompressorId());
                rsc8info.IsSignatureProtected = entry.IsSignatureProtected;
                rsc8info.SetEncryptionConfig(entry.GetEncryptionConfig());
                rsc8info.SetEncryptionKeyId(entry.GetEncryptionKeyId());
                rsc8info.Val2 = entry.Val3;
            }
            else
            {
                rsc8info.Magic = RSC8Magic;
                rsc8info.SetResourceId(entry.GetResourceType());
                rsc8info.SetCompressorId(0);
                rsc8info.IsSignatureProtected = false;
                rsc8info.SetEncryptionConfig(0);
                rsc8info.SetEncryptionKeyId(0xff);//not encrypted
                rsc8info.Val2 = entry.Val3;
            }



            bytes = CreateHeader(bytes, rsc8info);

        }

        public static void CreateRsc8(ref byte[] bytes, RSC8Info rsc8info, bool UseEntry = true)
        {

            bytes = CreateHeader(bytes, rsc8info);

        }







        private static byte[] CreateHeader(byte[] bytes, RSC8Info rsc8info)
        {
            var structureSize = Marshal.SizeOf(typeof(RSC8Info));
            var buffer = new byte[structureSize];
            var handle = GCHandle.Alloc(buffer, GCHandleType.Pinned);
            Marshal.StructureToPtr(rsc8info, handle.AddrOfPinnedObject(), false);
            handle.Free();

            byte[] TempArray = new byte[buffer.Length + bytes.Length];
            Buffer.BlockCopy(buffer, 0, TempArray, 0, buffer.Length);
            Buffer.BlockCopy(bytes, 0, TempArray, buffer.Length, bytes.Length);
            bytes = TempArray;


#if false
            Console.WriteLine("RSC8 Magic: " + rsc8info.Magic.ToString("X"));
            Console.WriteLine("RSC8 Val1: " + rsc8info.Val1.ToString("X"));
            Console.WriteLine("RSC8 Val2: " + rsc8info.val2.ToString("X"));
            Console.WriteLine("ResourceId: " + rsc8info.GetResourceId());
            Console.WriteLine("CompressorId: " + rsc8info.GetCompressorId());
            Console.WriteLine("IsSignatureProtected: " + rsc8info.IsSignatureProtected);
            Console.WriteLine("GetEncryptionKeyId: " + rsc8info.GetEncryptionKeyId());
            Console.WriteLine("GetEncryptionConfig: " + rsc8info.GetEncryptionConfig());
            Console.WriteLine("------------------------------------------------");
            Console.WriteLine("ResourceId: " + entry.GetResourceType());
            Console.WriteLine("CompressorId: " + entry.GetCompressorId());
            Console.WriteLine("IsSignatureProtected: " + entry.IsSignatureProtected);
            Console.WriteLine("GetEncryptionKeyId: " + entry.GetEncryptionKeyId());
            Console.WriteLine("GetEncryptionConfig: " + entry.GetEncryptionConfig());
#endif



            return bytes;
        }

        public static RSC8Info ReadRsc8(byte[] bytes)
        {
            RSC8Info rsc8info = new RSC8Info();
            rsc8info.Magic = BitConverter.ToUInt32(bytes, 0);
            rsc8info.Val1 = BitConverter.ToUInt32(bytes, 4);
            rsc8info.Val2 = BitConverter.ToUInt64(bytes, 8);

            if (rsc8info.Magic != RSC8Magic)
            {
                throw new Exception("Invalid resource header");
            }
#if false
            Console.WriteLine("RSC8 Magic: " + rsc8info.Magic.ToString("X"));
            Console.WriteLine("RSC8 Val1: " + rsc8info.Val1.ToString("X"));
            Console.WriteLine("RSC8 Val2: " + rsc8info.val2.ToString("X"));
            Console.WriteLine("ResourceId: " + rsc8info.GetResourceId());
            Console.WriteLine("CompressorId: " + rsc8info.GetCompressorId());
            Console.WriteLine("IsSignatureProtected: " + rsc8info.IsSignatureProtected);
            Console.WriteLine("GetEncryptionKeyId: " + rsc8info.GetEncryptionKeyId());
            Console.WriteLine("GetEncryptionConfig: " + rsc8info.GetEncryptionConfig());
#endif
            return rsc8info;
        }


        public static RSC8Info ReadRsc8(IStream memoryList)
        {
            RSC8Info rsc8info = new RSC8Info();
            rsc8info.Magic = memoryList.GetUIntValue(false, 0);
            rsc8info.Val1 = memoryList.GetUIntValue(false, 4);
            rsc8info.Val2 = memoryList.GetUInt64Value(false, 8);

            if (rsc8info.Magic != RSC8Magic)
            {
                throw new Exception("Invalid resource header");
            }

            return rsc8info;
        }

    }
}
