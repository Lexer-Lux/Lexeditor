using Helper;
using System;
using System.Collections;
using System.IO;
using System.Linq;


namespace RDR2_RPF_Tool.Core
{
    internal static class RPFHelper
    {

        public static int SetPadding(this IStream fStream, byte PaddingByte = 0x00)
        {

            int padding = 0;
            if (fStream.Length % 16 != 0)
            {
                padding = (int)((long)(1 << 4) - fStream.Length % (long)(1 << 4));
                fStream.SetBytes(Enumerable.Repeat((byte)PaddingByte, padding).ToArray());
            }
            return padding;
        }

        private static byte[] ConvertToArray(this BitArray bitArray)
        {
            byte[] array = new byte[bitArray.Length / 8];
            bitArray.CopyTo(array, 0);
            return array;
        }

        
        public static ulong ReplaceBits(this ulong input, ulong value, int pos, int BitSize)
        {
            BitArray bitArray = new BitArray(BitConverter.GetBytes(input));
            BitArray bitArray2 = new BitArray(BitConverter.GetBytes(value));
            for (int i = 0; i < BitSize; i++)
            {
                bitArray[pos + i] = bitArray2[i];
            }
            return BitConverter.ToUInt64(bitArray.ConvertToArray(), 0);
        }

        public static uint ReplaceBits(this uint input, uint value, int pos, int BitSize)
        {
            BitArray bitArray = new BitArray(BitConverter.GetBytes(input));
            BitArray bitArray2 = new BitArray(BitConverter.GetBytes(value));
            for (int i = 0; i < BitSize; i++)
            {
                bitArray[pos + i] = bitArray2[i];
            }
            return BitConverter.ToUInt32(bitArray.ConvertToArray(), 0);
        }



        public static string FileHash(string path, Platform platform)
        {

            int Fileid = GetFileExtId(System.IO.Path.GetExtension(path), platform);

            string FilePath = path.Replace("\\", "/");
            if (FilePath.StartsWith("0x", StringComparison.OrdinalIgnoreCase))
            {
                FilePath = GetFileName(Convert.ToUInt32(System.IO.Path.GetFileNameWithoutExtension(path), 16));
                return FilePath + GetFileExt(Fileid, platform);
            }
            else if (Fileid != 255)
            {
                return GetFileName(JOAATHash.Calc(Path.ChangeExtension(path, null))) + GetFileExt(Fileid, platform);
            }
            else
            {
                return GetFileName(JOAATHash.Calc(path)) + GetFileExt(Fileid, platform);
            }
        }



        private static string[] BaseRageExts = { "rpf", "#mf", "#dr", "#ft", "#dd", "#td", "#bn", "#bd", "#pd", "#bs", "#sd", "#mt", "#sc", "#cs" };

        private static string[] ExtraRageExts = { "mrf", "cut", "gfx", "#cd", "#ld", "#pmd", "#pm", "#ed", "#pt", "#map", "#typ", "#ch", "#ldb", "#jd", "#ad", "#nv", "#hn", "#pl", "#nd", "#vr", "#wr", "#nh", "#fd", "#as" };

        public static int GetFileExtId(string ext, Platform platform)
        {
            ext = ext.TrimStart('.').Trim();
            for (int i = 0; i < BaseRageExts.Length; i++)
            {
                if (BaseRageExts[i].Replace('#', (char)platform) == ext)
                {
                    return i;
                }
            }

            for (int i = 0; i < ExtraRageExts.Length; i++)
            {
                if (ExtraRageExts[i].Replace('#', (char)platform) == ext)
                {
                    return i + 64;
                }
            }
            return 255; //bin
        }


        public static string GetFileExt(int id, Platform platform)
        {

            if (id >= 0 && id < BaseRageExts.Length)
            {
                return "." + BaseRageExts[id].Replace('#', (char)platform);
            }
            else if (id >= 64 && id <= 87)
            {
                return "." + ExtraRageExts[id - 64].Replace('#', (char)platform);
            }

            return "";
        }



        public static string GetFileName(uint Hash)
        {

            if (NamesContainer.Names.ContainsKey(Hash))
            {
                return NamesContainer.Names[Hash];
            }

            return "0x" + Hash.ToString("x2").ToUpper();
        }
    }


}