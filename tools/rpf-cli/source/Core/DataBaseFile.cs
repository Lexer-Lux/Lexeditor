using Helper;
using System;
using System.Collections.Generic;
using System.Linq;
using System.Text;

namespace RDR2_RPF_Tool.Core
{
    public class DataBaseFile
    {



        IStream stream;
        RSC8.RSC8Info Header;



        public struct TextEntry
        {
            public uint hash { get; set; }
            public long TextBlockOffset { get; set; }
            public long Offset { get; set; }
            public long StringLength { get; set; }

        }



        public DataBaseFile(byte[] bytes)
        {
            stream = new MStream(bytes);
        }


        public static string[] ExportTexts(byte[] data)
        {
            return new DataBaseFile(data).ExportText();
        }


        public static byte[] ImportTexts(byte[] data, string[] text)
        {
            return new DataBaseFile(data).ImportText(text);
        }


        public string[] ExportText()
        {

            var strings = new List<string>();
            foreach (var entry in GetTextEntries())
            {
                strings.Add("0x" + entry.Value.hash.ToString("x2") + "=" + stream.GetStringValue((int)entry.Value.StringLength, false, (int)entry.Value.Offset, Encoding.UTF8).Trim('\0'));
                //  Console.WriteLine(strings[strings.Count - 1]);
            }
            return strings.ToArray();
        }

        public byte[] ImportText(string[] TextTable)//[hash] = [text]
        {
            TextTable = TextTable.Where(x => x.Contains("=")).ToArray();
            var Entries = GetTextEntries();



            foreach (var str in TextTable)
            {

                var Line = str.Split(new[] { '=' }, 2);
                uint hash = Convert.ToUInt32(Line[0].Trim(), 16);
                string text = Line[1];


                if (!Entries.ContainsKey(hash))
                {
                    continue;
                }


                var Entry = Entries[hash];

                stream.Seek(Entry.TextBlockOffset);
                stream.SetInt64Value(OffsetPut(stream.Length));
                stream.SetInt64Value(Encoding.UTF8.GetBytes(text).Length + 1);

                stream.Seek(stream.Length);
                stream.SetStringValueN(text, true, -1, Encoding.UTF8);
                stream.SetPadding();

            }

            var bytes = stream.ToArray();

            Header.SetOrignalSize(bytes.Length);

            RSC8.CreateRsc8(ref bytes, Header);
            return bytes;
        }





        public Dictionary<uint, TextEntry> GetTextEntries()
        {

            var textEntries = new Dictionary<uint, TextEntry>();

            Header = RSC8.ReadRsc8(stream);

            if (Header.Magic != RSC8.RSC8Magic)
            {
                throw new Exception("Invalid RSC8 File!");
            }

            if (Header.GetResourceId() != GetResourceType.Text)
            {
                throw new Exception("this not text file resource!");
            }

            stream.DeleteBytes(0x10); //delete header
            stream.SetPosition(0x10);

            var Containeroffset = FixedOffset(stream.GetInt64Value());
            var offsetsCount = stream.GetIntValue();
            stream.Skip(4);
            stream.Skip(4);//text count after export


            stream.Seek(Containeroffset);
            var offsets = stream.GetArray<long>(offsetsCount).Where(x => x != 0);


            foreach (var offset in offsets)
            {
                var Cur_offset = FixedOffset(offset);
                while (Cur_offset != 0)
                {
                    var textentry = new TextEntry();

                    stream.Seek(Cur_offset);
                    textentry.hash = (uint)stream.GetInt64Value();
                    textentry.TextBlockOffset = FixedOffset(stream.GetInt64Value()) + 0x10;
                    Cur_offset = FixedOffset(stream.GetInt64Value());


                    stream.Seek(textentry.TextBlockOffset);

                    textentry.Offset = FixedOffset(stream.GetInt64Value());
                    textentry.StringLength = stream.GetInt64Value();

                    textEntries.Add(textentry.hash, textentry);
                }

            }


            return textEntries;
        }








        public int FixedOffset(long value)
        {
            return (int)(value & 0xFFFFFF);
        }

        public long OffsetPut(long value)
        {
            return value | 0x50 << 24;
        }








    }
}
