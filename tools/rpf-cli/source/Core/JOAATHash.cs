namespace RDR2_RPF_Tool.Core
{
    public static class JOAATHash
    {
        public static uint Calc(string input)
        {
            uint hash = 0;

            foreach (var item in input)
            {
                var byte_of_data = (byte)item;

                hash += byte_of_data;
                hash += hash << 10;
                hash ^= hash >> 6;
            }

            hash += hash << 3;
            hash ^= hash >> 11;
            hash += hash << 15;

            return hash;
        }
    }
}
