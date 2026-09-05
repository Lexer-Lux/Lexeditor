/* Derived from MIT-licensed Neodymium RageLib PSO value wrappers. */
using RageLib.Data;
using RageLib.GTA5.PSO;
using RageLib.GTA5.PSOWrappers.Data;

namespace RageLib.GTA5.PSOWrappers.Types
{
    public class PsoEnumShort : IPsoValue
    {
        public PsoEnumInfo TypeInfo { get; set; }
        public int Value { get; set; }
        public void Read(PsoDataReader reader) { Value = reader.ReadInt32(); }
        public void Write(DataWriter writer) { writer.Write(Value); }
    }
}
