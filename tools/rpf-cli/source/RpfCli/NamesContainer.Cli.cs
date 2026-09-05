using System;
using System.Collections.Generic;
using System.IO;

namespace RDR2_RPF_Tool.Core
{
    public static class NamesContainer
    {
        public static readonly Dictionary<uint, string> Names = LoadNames();

        private static Dictionary<uint, string> LoadNames()
        {
            var names = new Dictionary<uint, string>();
            string path = Path.Combine(AppContext.BaseDirectory, "names.txt");
            foreach (string raw in File.ReadLines(path))
            {
                string name = raw.Trim();
                if (name.Length == 0) continue;
                Add(names, name.Replace("%platform%", "x64"));
                Add(names, name.Replace("%platform%", "ps4"));
            }
            return names;
        }

        private static void Add(Dictionary<uint, string> names, string name)
        {
            uint hash = JOAATHash.Calc(name);
            if (!names.ContainsKey(hash)) names.Add(hash, name);
        }
    }
}
