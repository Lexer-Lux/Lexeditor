using System;
using System.Collections.Generic;
using static RDR2_RPF_Tool.Core.RPF8;
using static RDR2_RPF_Tool.Core.Tfit2CbcCipher;

namespace RDR2_RPF_Tool.Core
{
    public static class Cipher
    {

        public static ICipher GetCipher(int Tag, Platform platform)
        {

            if (platform == Platform.Pc)
            {
                Tfit2Key tfit2Keyvalue;
                if (!KeysContainer.keysValues.TryGetValue(Tag, out tfit2Keyvalue))
                {
                    throw new Exception("Can't get encoder key!");
                }
                return new Tfit2CbcCipher(tfit2Keyvalue, KeysContainer.iv, KeysContainer.tfit2Context);
            }
            else if (platform == Platform.Ps4)
            {

                if (Tag >= 163)
                {
                    if (Tag == 0xC0)
                        Tag = 163;
                    else
                        throw new Exception("Can't get encoder key!");
                }

                return new TfitCbcCipher(KeysContainer.RDR2_PS4_TFIT_KEYS[Tag], KeysContainer.RDR2_PS4_TFIT_TABLES, KeysContainer.iv);
            }
            else
            {
                throw new Exception("unknown platform!");
            }
        }



        public static byte[] DecodeBlock(byte[] bytes, Entry entry)
        {
            if (entry.GetEncryptionKeyId() == 255)
            {
                return bytes;
            }

            int size = entry.GetOrignalSize();
            int raw_size = entry.GetOnDiskSize();
            bool is_compressed = entry.GetCompressorId() != 0;

            if (entry.IsSignatureProtected)
            {
                raw_size -= 0x100;
            }

            if (entry.IsResource)
            {
                raw_size -= 16;
            }


            long chunk_size = entry.IsResource
            // pgStreamer reads compressed data in chunks of 0x80000
            ? (is_compressed ? 0x80000 : size)
            // fiPackFile8 reads compressed data in chunks of 0x2000
            // fiStream reads data in chunks of 0x1000 (depending on reads)
            : (is_compressed ? 0x2000 : 0x1000);

            List<List<long>> longs = StridedCipher.UnpackConfig(entry.GetEncryptionConfig(), raw_size, chunk_size);
            ICipher tfit2CbcCipher = GetCipher(entry.GetEncryptionKeyId(), entry.platform);


            foreach (List<long> BlockOffset in longs)
            {
                int start = (int)BlockOffset[0];
                int lenght = (int)(BlockOffset[1] - BlockOffset[0]);
                bytes = tfit2CbcCipher.Decode(bytes, start, lenght);
            }


            return bytes;
        }



    }
}
