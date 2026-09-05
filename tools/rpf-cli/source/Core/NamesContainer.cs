using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;

namespace RDR2_RPF_Tool.Core
{
    public static class NamesContainer
    {
        public static Dictionary<uint, string> Names = new Dictionary<uint, string>();

        public static bool LoedNames = LoedNamesFile();

        public static bool LoedNamesFile()
        {


            foreach (string line in CoreResource.names.Split(new string[] { "\r\n", "\n" }, StringSplitOptions.RemoveEmptyEntries))
            {
                AddName(line.Replace("%platform%", "x64"));
                AddName(line.Replace("%platform%", "ps4"));
            }

            
            if (File.Exists("names.txt"))
            {
                foreach (string line in File.ReadAllLines("names.txt").Where(x=>!string.IsNullOrEmpty(x)))
                    AddName(line);
            }

            return true;
        }


        private static void AddName(string name)
        {
            uint Hash = JOAATHash.Calc(name);
            if (!Names.ContainsKey(Hash))
            {
                Names.Add(JOAATHash.Calc(name), name);
            }
        }
    }
}
