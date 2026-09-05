/*
    Copyright(c) 2016 Neodymium

    Permission is hereby granted, free of charge, to any person obtaining a copy
    of this software and associated documentation files (the "Software"), to deal
    in the Software without restriction, including without limitation the rights
    to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
    copies of the Software, and to permit persons to whom the Software is
    furnished to do so, subject to the following conditions:

    The above copyright notice and this permission notice shall be included in
    all copies or substantial portions of the Software.

    THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
    IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
    FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
    AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
    LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
    OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
    THE SOFTWARE.
*/

using RageLib.Data;
using RageLib.GTA5.PSOWrappers.Data;
using System;

namespace RageLib.GTA5.PSOWrappers.Types
{
    public class PsoString1 : IPsoValue
    {
        public string Value { get; set; }

        public void Read(PsoDataReader reader)
        {
            int x1 = reader.ReadInt32();
            int x2 = reader.ReadInt32();
            uint high = unchecked((uint)x2);
            high = (high >> 24) | ((high >> 8) & 0x0000FF00) | ((high << 8) & 0x00FF0000) | (high << 24);
            ulong pointer = unchecked((uint)x1) | ((ulong)high << 32);
            var BlockIndex = (int)(pointer & 0x000FFFFF);
            var Offset = (long)(pointer >> 20);

            // read reference data...
            var backupOfSection = reader.CurrentSectionIndex;
            var backupOfPosition = reader.Position;

            reader.SetSectionIndex(BlockIndex - 1);
            reader.Position = Offset;

            Value = reader.ReadString();

            reader.SetSectionIndex(backupOfSection);
            reader.Position = backupOfPosition;
        }

        public void Write(DataWriter writer)
        {

        }
    }
}
