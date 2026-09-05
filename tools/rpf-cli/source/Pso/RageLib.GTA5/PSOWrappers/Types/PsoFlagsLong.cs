/* Derived from MIT-licensed Neodymium RageLib PSO value wrappers. */
using RageLib.Data;
using RageLib.GTA5.PSO;
using RageLib.GTA5.PSOWrappers.Data;

namespace RageLib.GTA5.PSOWrappers.Types
{
    public class PsoFlagsLong : IPsoValue
    {
        public PsoEnumInfo TypeInfo;
        public ulong Value { get; set; }

        public void Read(PsoDataReader reader) { Value = reader.ReadUInt64(); }
        public void Write(DataWriter writer) { writer.Write(Value); }
    }
}
