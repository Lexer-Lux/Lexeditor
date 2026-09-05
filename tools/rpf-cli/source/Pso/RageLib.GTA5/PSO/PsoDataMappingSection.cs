/* Derived from MIT-licensed Neodymium RageLib PSO structures. */
using RageLib.Data;
using System.Collections.Generic;

namespace RageLib.GTA5.PSO
{
    public class PsoDataMappingSection
    {
        public int Ident { get; set; } = 0x504D4150;
        public int Length { get; private set; }
        public int RootIndex { get; set; }
        public short EntriesCount { get; private set; }
        public short Unknown_Eh { get; set; } = 0x7070;
        public List<PsoDataMappingEntry> Entries { get; set; }

        public void Read(DataReader reader)
        {
            Ident = reader.ReadInt32(); Length = reader.ReadInt32(); RootIndex = reader.ReadInt32();
            EntriesCount = reader.ReadInt16(); Unknown_Eh = reader.ReadInt16();
            if (EntriesCount <= 0)
            {
                EntriesCount = reader.ReadInt16();
                reader.ReadInt16(); reader.ReadInt16(); reader.ReadInt16();
            }
            Entries = new List<PsoDataMappingEntry>();
            for (int i = 0; i < EntriesCount; i++) { var entry = new PsoDataMappingEntry(); entry.Read(reader); Entries.Add(entry); }
        }

        public void Write(DataWriter writer) { throw new System.NotSupportedException(); }
    }

    public class PsoDataMappingEntry
    {
        public int NameHash { get; set; }
        public int Offset { get; set; }
        public int Unknown_8h { get; set; }
        public int Length { get; set; }
        public void Read(DataReader reader) { NameHash=reader.ReadInt32(); Offset=reader.ReadInt32(); Unknown_8h=reader.ReadInt32(); Length=reader.ReadInt32(); }
        public void Write(DataWriter writer) { throw new System.NotSupportedException(); }
    }
}
