using System;
using System.Collections.Generic;

namespace RDR2_RPF_Tool.Core
{
    public class StridedCipher
    {


        // head_length  in [0, 0x1000, 0x4000, 0x10000]
        // block_length in [0, 0x400, 0x800, 0x1000, 0x2000, 0x4000, 0x8000, 0x10000, 0x20000]
        // block_stride in [0, 0x10000, 0x20000, 0x30000, 0x40000, 0x50000, 0x60000, 0x70000, 0x80000]
        internal static void UnpackConfig(byte config, ref long head_length, ref long block_length, ref long block_stride)
        {
            byte head_config = (byte)(config & 0b11);
            if ((config & 0b11) != 0)
            {
                head_length = (long)(0x400) << (head_config * 2);
            }

            byte length_config = (byte)((config >> 2) & 0b111);
            if (((config >> 2) & 0b111) != 0)
            {
                byte stride_config = (byte)((config >> 5) & 0b111); // Config[5:8]
                block_length = (long)(0x400) << length_config;
                block_stride = (long)(stride_config + 1) << 16;
            }
        }

        public static List<List<long>> UnpackConfig(byte config, long file_size, long chunk_size)
        {
            List<List<long>> results = new List<List<long>>();
            long offset = 0;

            Action<long, long> Update = (long start, long end) =>
            {
                start = Math.Max(start, offset);
                end = Math.Min(end, file_size);

                if (start < end)
                {
                    results.Add(new List<long>() { start, end });
                    offset = end;
                }
            };

            long tail_length = 0x400;
            long tail_offset = file_size - tail_length;

            long head_length = 0;
            long block_length = 0;
            long block_stride = 0;

            UnpackConfig(config, ref head_length, ref block_length, ref block_stride);

            Update(0, head_length);


            if (head_length < tail_offset)
            {
                if (block_length != 0 || block_stride != 0)
                {


                    if ((block_stride == chunk_size) && (tail_offset < block_stride) && (block_stride < file_size))
                    {
                        offset = block_stride;
                    }

                    else
                    {
                        for (long block = offset != 0 ? block_stride : 0; block + block_length <= tail_offset; block += block_stride)
                        {
                            Update(block, block + block_length);
                        }
                    }
                }

                Update(tail_offset, file_size);
            }

            return results;
        }

    }
}
