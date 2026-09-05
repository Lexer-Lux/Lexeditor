using System;
using System.Collections.Generic;
using System.Linq;

namespace RDR2_RPF_Tool.Core
{
    public class Tfit2CbcCipher : ICipher
    {
        public struct Block
        {
            public ulong[/*16*/] Masks { get; set; }
            public uint Xor { get; set; }
        }
        public struct Round
        {
            public ulong[/*4096*/] Lookup { get; set; }
            public Block[/*16*/] Blocks { get; set; }
        }

        public struct Tfit2Context
        {
            public ulong[/*16*/][/*256*/] InitTables { get; set; }
            public Round[/*17*/] Rounds { get; set; }
            public ulong[/*16*/][/*8*/] EndMasks { get; set; }
            public byte[/*16*/][/*256*/] EndTables { get; set; }
            public byte[/*16*/] EndXor { get; set; }
        };


        /// <summary>
        /// ulong[18][2] Data
        /// </summary>
        public struct Tfit2Key
        {
            public ulong[/*18*/][/*2*/] Data;
        };



        public ulong[][] keys_;
        public Tfit2Context ctx_;
        public byte[/*16*/] iv_;
        //////////////////////////////////////////////////////////
        //////////////////////////////////////////////////////////
        /////////////////////////////////////////////////////////
        ////////////////////////////////////////////////////////


        static void TFIT2_DecryptSplatBytes(byte[/*8*/] bytes, ulong[/*8*/] output)
        {
            for (int i = 0; i < 8; ++i)
                output[i] = 0x0101010101010101u * bytes[7 - i];
        }


        static ulong TFIT2_DecryptRoundBlock(ulong[/*8*/] input1, ulong[/*16*/] masks, uint xorr, ulong[/*4096*/] lookup)
        {

            // 4096 = 256 * 16
            ulong lower = masks[0xF] & input1[0x7] ^ masks[0xE] & input1[0x6] ^ masks[0xD] & input1[0x5] ^
                masks[0xC] & input1[0x4] ^ masks[0xB] & input1[0x3] ^ masks[0xA] & input1[0x2] ^ masks[0x9] & input1[0x1] ^
                masks[0x8] & input1[0x0];



            lower ^= lower >> 1;
            lower ^= lower >> 2;
            lower ^= lower >> 4;
            lower &= 0x101010101010101u;

            lower |= lower >> 7;
            lower |= lower >> 14;
            lower |= lower >> 28;

            ulong upper = masks[0x7] & input1[0x7] ^ masks[0x6] & input1[0x6] ^ masks[0x5] & input1[0x5] ^
                masks[0x4] & input1[0x4] ^ masks[0x3] & input1[0x3] ^ masks[0x2] & input1[0x2] ^ masks[0x1] & input1[0x1] ^
                masks[0x0] & input1[0x0];


            upper ^= upper << 1;
            upper ^= upper >> 2;
            upper ^= upper >> 4;
            upper &= 0x202020202020202u;

            upper |= upper << 7;
            upper |= upper >> 14;

            return lookup[(lower & 0xFF) ^ (upper & 0xF00) ^ xorr];
        }


        static void TFIT2_DecryptRoundA(Tfit2Context ctx, byte[/*16*/] data)
        {
            ulong[/*2*/] values = {
            ctx.InitTables[0x0][data[0x0]] ^ ctx.InitTables[0x1][data[0x1]] ^ ctx.InitTables[0x2][data[0x2]] ^
                ctx.InitTables[0x3][data[0x3]] ^ ctx.InitTables[0x4][data[0x4]] ^ ctx.InitTables[0x5][data[0x5]] ^
                ctx.InitTables[0x6][data[0x6]] ^ ctx.InitTables[0x7][data[0x7]],

            ctx.InitTables[0x8][data[0x8]] ^ ctx.InitTables[0x9][data[0x9]] ^ ctx.InitTables[0xA][data[0xA]] ^
                ctx.InitTables[0xB][data[0xB]] ^ ctx.InitTables[0xC][data[0xC]] ^ ctx.InitTables[0xD][data[0xD]] ^
                ctx.InitTables[0xE][data[0xE]] ^ ctx.InitTables[0xF][data[0xF]],};

            Buffer.BlockCopy(values, 0, data, 0, 16);
        }


        static void TFIT2_DecryptRoundB(Tfit2Context ctx, int index, byte[/*16*/] data, ulong[/*2*/] key)
        {
            var round = ctx.Rounds[index];

            ulong[/*8*/] v0 = new ulong[8];
            ulong[/*8*/] v1 = new ulong[8];

            List<byte> dataList = data.ToList();

            TFIT2_DecryptSplatBytes(dataList.GetRange(0, 8).ToArray(), v0);
            TFIT2_DecryptSplatBytes(dataList.GetRange(8, 8).ToArray(), v1);


            ulong[/*2*/] val ={
            key[0] ^ TFIT2_DecryptRoundBlock(v0, round.Blocks[0x0].Masks, round.Blocks[0x0].Xor, round.Lookup) ^
                TFIT2_DecryptRoundBlock(v0, round.Blocks[0x1].Masks, round.Blocks[0x1].Xor, round.Lookup) ^
                TFIT2_DecryptRoundBlock(v0, round.Blocks[0x2].Masks, round.Blocks[0x2].Xor, round.Lookup) ^
                TFIT2_DecryptRoundBlock(v0, round.Blocks[0x3].Masks, round.Blocks[0x3].Xor, round.Lookup) ^
                TFIT2_DecryptRoundBlock(v0, round.Blocks[0x4].Masks, round.Blocks[0x4].Xor, round.Lookup) ^
                TFIT2_DecryptRoundBlock(v0, round.Blocks[0x5].Masks, round.Blocks[0x5].Xor, round.Lookup) ^
                TFIT2_DecryptRoundBlock(v0, round.Blocks[0x6].Masks, round.Blocks[0x6].Xor, round.Lookup) ^
                TFIT2_DecryptRoundBlock(v0, round.Blocks[0x7].Masks, round.Blocks[0x7].Xor, round.Lookup),

            key[1] ^ TFIT2_DecryptRoundBlock(v1, round.Blocks[0x8].Masks, round.Blocks[0x8].Xor, round.Lookup) ^
                TFIT2_DecryptRoundBlock(v1, round.Blocks[0x9].Masks, round.Blocks[0x9].Xor, round.Lookup) ^
                TFIT2_DecryptRoundBlock(v1, round.Blocks[0xA].Masks, round.Blocks[0xA].Xor, round.Lookup) ^
                TFIT2_DecryptRoundBlock(v1, round.Blocks[0xB].Masks, round.Blocks[0xB].Xor, round.Lookup) ^
                TFIT2_DecryptRoundBlock(v1, round.Blocks[0xC].Masks, round.Blocks[0xC].Xor, round.Lookup) ^
                TFIT2_DecryptRoundBlock(v1, round.Blocks[0xD].Masks, round.Blocks[0xD].Xor, round.Lookup) ^
                TFIT2_DecryptRoundBlock(v1, round.Blocks[0xE].Masks, round.Blocks[0xE].Xor, round.Lookup) ^
                TFIT2_DecryptRoundBlock(v1, round.Blocks[0xF].Masks, round.Blocks[0xF].Xor, round.Lookup),
        };


            Buffer.BlockCopy(val, 0, data, 0, 16);
        }


        static void TFIT2_DecryptRoundC(Tfit2Context ctx, int index, byte[/*16*/] data, ulong[/*2*/] key)
        {
            var round = ctx.Rounds[index];


            ulong[] v0 = new ulong[8];
            ulong[] v1 = new ulong[8];

            List<byte> dataList = data.ToList();
            TFIT2_DecryptSplatBytes(dataList.GetRange(0, 8).ToArray(), v0);
            TFIT2_DecryptSplatBytes(dataList.GetRange(8, 8).ToArray(), v1);

            ulong[/*2*/] val ={
            key[0] ^ TFIT2_DecryptRoundBlock(v0, round.Blocks[0x0].Masks, round.Blocks[0x0].Xor, round.Lookup) ^
                TFIT2_DecryptRoundBlock(v1, round.Blocks[0x1].Masks, round.Blocks[0x1].Xor, round.Lookup) ^
                TFIT2_DecryptRoundBlock(v1, round.Blocks[0x2].Masks, round.Blocks[0x2].Xor, round.Lookup) ^
                TFIT2_DecryptRoundBlock(v0, round.Blocks[0x3].Masks, round.Blocks[0x3].Xor, round.Lookup) ^
                TFIT2_DecryptRoundBlock(v0, round.Blocks[0x4].Masks, round.Blocks[0x4].Xor, round.Lookup) ^
                TFIT2_DecryptRoundBlock(v0, round.Blocks[0x5].Masks, round.Blocks[0x5].Xor, round.Lookup) ^
                TFIT2_DecryptRoundBlock(v1, round.Blocks[0x6].Masks, round.Blocks[0x6].Xor, round.Lookup) ^
                TFIT2_DecryptRoundBlock(v1, round.Blocks[0x7].Masks, round.Blocks[0x7].Xor, round.Lookup),

            key[1] ^ TFIT2_DecryptRoundBlock(v1, round.Blocks[0x8].Masks, round.Blocks[0x8].Xor, round.Lookup) ^
                TFIT2_DecryptRoundBlock(v0, round.Blocks[0x9].Masks, round.Blocks[0x9].Xor, round.Lookup) ^
                TFIT2_DecryptRoundBlock(v0, round.Blocks[0xA].Masks, round.Blocks[0xA].Xor, round.Lookup) ^
                TFIT2_DecryptRoundBlock(v1, round.Blocks[0xB].Masks, round.Blocks[0xB].Xor, round.Lookup) ^
                TFIT2_DecryptRoundBlock(v1, round.Blocks[0xC].Masks, round.Blocks[0xC].Xor, round.Lookup) ^
                TFIT2_DecryptRoundBlock(v1, round.Blocks[0xD].Masks, round.Blocks[0xD].Xor, round.Lookup) ^
                TFIT2_DecryptRoundBlock(v0, round.Blocks[0xE].Masks, round.Blocks[0xE].Xor, round.Lookup) ^
                TFIT2_DecryptRoundBlock(v0, round.Blocks[0xF].Masks, round.Blocks[0xF].Xor, round.Lookup),
        };

            Buffer.BlockCopy(val, 0, data, 0, 16);
        }


        static byte TFIT2_DecryptSquashBytes(ulong[/*8*/] input, ulong[/*8*/] lookup)
        {
            ulong v1 = lookup[7] & input[7] ^ lookup[6] & input[6] ^ lookup[5] & input[5] ^ lookup[4] & input[4] ^
                lookup[3] & input[3] ^ lookup[2] & input[2] ^ lookup[1] & input[1] ^ lookup[0] & input[0];

            v1 ^= v1 >> 1;
            v1 ^= v1 >> 2;
            v1 ^= v1 >> 4;

            v1 &= 0x101010101010101u; // Each byte is 1 bit, the "sum" of xoring all bits of that byte

            // Compress the value back into a byte (using the lowest bit of each byte)
            v1 |= v1 >> 7;
            v1 |= v1 >> 14;
            v1 |= v1 >> 28;

            return (byte)(v1);
        }



        static void TFIT2_DecryptRoundD(Tfit2Context ctx, byte[/*16*/] data)
        {
            ulong[] v0 = new ulong[8];
            ulong[] v1 = new ulong[8];

            List<byte> dataList = data.ToList();
            TFIT2_DecryptSplatBytes(dataList.GetRange(0, 8).ToArray(), v0);
            TFIT2_DecryptSplatBytes(dataList.GetRange(8, 8).ToArray(), v1);

            data[0x0] = ctx.EndTables[0x0][TFIT2_DecryptSquashBytes(v0, ctx.EndMasks[0x0]) ^ ctx.EndXor[0x0]];
            data[0x1] = ctx.EndTables[0x1][TFIT2_DecryptSquashBytes(v0, ctx.EndMasks[0x1]) ^ ctx.EndXor[0x1]];
            data[0x2] = ctx.EndTables[0x2][TFIT2_DecryptSquashBytes(v0, ctx.EndMasks[0x2]) ^ ctx.EndXor[0x2]];
            data[0x3] = ctx.EndTables[0x3][TFIT2_DecryptSquashBytes(v0, ctx.EndMasks[0x3]) ^ ctx.EndXor[0x3]];
            data[0x4] = ctx.EndTables[0x4][TFIT2_DecryptSquashBytes(v0, ctx.EndMasks[0x4]) ^ ctx.EndXor[0x4]];
            data[0x5] = ctx.EndTables[0x5][TFIT2_DecryptSquashBytes(v0, ctx.EndMasks[0x5]) ^ ctx.EndXor[0x5]];
            data[0x6] = ctx.EndTables[0x6][TFIT2_DecryptSquashBytes(v0, ctx.EndMasks[0x6]) ^ ctx.EndXor[0x6]];
            data[0x7] = ctx.EndTables[0x7][TFIT2_DecryptSquashBytes(v0, ctx.EndMasks[0x7]) ^ ctx.EndXor[0x7]];

            data[0x8] = ctx.EndTables[0x8][TFIT2_DecryptSquashBytes(v1, ctx.EndMasks[0x8]) ^ ctx.EndXor[0x8]];
            data[0x9] = ctx.EndTables[0x9][TFIT2_DecryptSquashBytes(v1, ctx.EndMasks[0x9]) ^ ctx.EndXor[0x9]];
            data[0xA] = ctx.EndTables[0xA][TFIT2_DecryptSquashBytes(v1, ctx.EndMasks[0xA]) ^ ctx.EndXor[0xA]];
            data[0xB] = ctx.EndTables[0xB][TFIT2_DecryptSquashBytes(v1, ctx.EndMasks[0xB]) ^ ctx.EndXor[0xB]];
            data[0xC] = ctx.EndTables[0xC][TFIT2_DecryptSquashBytes(v1, ctx.EndMasks[0xC]) ^ ctx.EndXor[0xC]];
            data[0xD] = ctx.EndTables[0xD][TFIT2_DecryptSquashBytes(v1, ctx.EndMasks[0xD]) ^ ctx.EndXor[0xD]];
            data[0xE] = ctx.EndTables[0xE][TFIT2_DecryptSquashBytes(v1, ctx.EndMasks[0xE]) ^ ctx.EndXor[0xE]];
            data[0xF] = ctx.EndTables[0xF][TFIT2_DecryptSquashBytes(v1, ctx.EndMasks[0xF]) ^ ctx.EndXor[0xF]];
        }



        static void TFIT2_DecryptBlock(Tfit2Context ctx, ulong[/*17*/][/*2*/] key, byte[/*16*/] input, byte[/*16*/] output)
        {
            byte[/*16*/] temp = new byte[16];
            Array.Copy(input, temp, 16);

            TFIT2_DecryptRoundA(ctx, temp);

            TFIT2_DecryptRoundB(ctx, 0, temp, key[0]);


            TFIT2_DecryptRoundB(ctx, 1, temp, key[1]);


            for (int i = 2; i < 16; ++i)
                TFIT2_DecryptRoundC(ctx, i, temp, key[i]);


            TFIT2_DecryptRoundB(ctx, 16, temp, key[16]);


            TFIT2_DecryptRoundD(ctx, temp);

            Buffer.BlockCopy(temp, 0, output, 0, 16);
        }


        const int TFIT2_BLOCK_SIZE = 16;
        public Tfit2CbcCipher(Tfit2Key key, byte[/*16*/] iv, Tfit2Context ctx)
        {
            iv_ = new byte[iv.Length];
            Array.Copy(iv, iv_, 16);
            keys_ = key.Data.Skip(1).ToArray();
            ctx_ = ctx;
        }



        public byte[] Decode(byte[] input, int? start = null, int? lenght = null)
        {
            if (start == null && lenght == null)
            {
                start = 0;
                lenght = input.Length;
            }

            int StartPosition = (int)start;
            int BlockSize = (int)lenght;


            int Size = BlockSize - BlockSize % TFIT2_BLOCK_SIZE;

            byte[] Cur_iv = iv_;


            for (int i = StartPosition; i < StartPosition + Size; i += TFIT2_BLOCK_SIZE)
            {
                byte[] bytes = new byte[TFIT2_BLOCK_SIZE];
                byte[] Next_iv = new byte[TFIT2_BLOCK_SIZE];

                Array.Copy(input, i, Next_iv, 0, TFIT2_BLOCK_SIZE);


                byte[] outbytes = new byte[TFIT2_BLOCK_SIZE];

                Array.Copy(input, i, bytes, 0, TFIT2_BLOCK_SIZE);

                TFIT2_DecryptBlock(ctx_, keys_, bytes, outbytes);

                for (int j = 0; j < 16; j++)
                    input[i + j] = (byte)(outbytes[j] ^ Cur_iv[j]);

                Cur_iv = Next_iv;
            }
            Array.Copy(Cur_iv, iv_, 16);

            return input;
        }



        public static byte[] TFIT2_DecryptBytes(Tfit2Key key, byte[/*16*/] iv, Tfit2Context ctx, byte[] input, int? start = null, int? lenght = null)
        {

            Tfit2CbcCipher tfit2CbcCipher = new Tfit2CbcCipher(key, iv, ctx);


            return tfit2CbcCipher.Decode(input, start, lenght);
        }





    }
}
