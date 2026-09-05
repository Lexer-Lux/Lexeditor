using System;
using System.Linq;

namespace RDR2_RPF_Tool.Core
{
    public class TfitCbcCipher : ICipher
    {

        public uint[/*17*/][/*4*/] keys_;
        public uint[/*17*/][/*16*/][/*256*/] tables_;
        public byte[/*16*/] iv_;
        //////////////////////////////////////////////////////////
        //////////////////////////////////////////////////////////
        /////////////////////////////////////////////////////////
        ////////////////////////////////////////////////////////


        static void TFIT_DecryptRoundA(byte[/*16*/] data, uint[/*4*/] key, uint[/*16*/][/*256*/] table)
        {
            uint[/*4*/] temp ={
            table[0][data[0]] ^ table[1][data[1]] ^ table[2][data[2]] ^ table[3][data[3]] ^ key[0],
            table[4][data[4]] ^ table[5][data[5]] ^ table[6][data[6]] ^ table[7][data[7]] ^ key[1],
            table[8][data[8]] ^ table[9][data[9]] ^ table[10][data[10]] ^ table[11][data[11]] ^ key[2],
            table[12][data[12]] ^ table[13][data[13]] ^ table[14][data[14]] ^ table[15][data[15]] ^ key[3],
           };

            Buffer.BlockCopy(temp, 0, data, 0, 16);
        }

        static void TFIT_DecryptRoundB(byte[/*16*/] data, uint[/*4*/] key, uint[/*16*/][/*256*/] table)
        {
            uint[/*4*/] temp ={
            table[0][data[0]] ^ table[1][data[7]] ^ table[2][data[10]] ^ table[3][data[13]] ^ key[0],
            table[4][data[1]] ^ table[5][data[4]] ^ table[6][data[11]] ^ table[7][data[14]] ^ key[1],
            table[8][data[2]] ^ table[9][data[5]] ^ table[10][data[8]] ^ table[11][data[15]] ^ key[2],
            table[12][data[3]] ^ table[13][data[6]] ^ table[14][data[9]] ^ table[15][data[12]] ^ key[3],
        };

            Buffer.BlockCopy(temp, 0, data, 0, 16);
        }


        static void TFIT_DecryptBlock(byte[/*16*/] input, byte[/*16*/] output, uint[/*17*/][/*4*/] keys, uint[/*17*/][/*16*/][/*256*/] tables)
        {
            byte[] temp = new byte[16];
            Array.Copy(input, 0, temp, 0, 16);

            TFIT_DecryptRoundA(temp, keys[0], tables[0]);

            TFIT_DecryptRoundA(temp, keys[1], tables[1]);

            for (int i = 2; i < 16; ++i)
                TFIT_DecryptRoundB(temp, keys[i], tables[i]);

            TFIT_DecryptRoundA(temp, keys[16], tables[16]);

            Buffer.BlockCopy(temp, 0, output, 0, 16);

        }
        const int TFIT_BLOCK_SIZE = 16;




        public TfitCbcCipher(uint[/*17*/][/*4*/] keys, uint[/*17*/][/*16*/][/*256*/] tables, byte[/*16*/] iv)
        {
            iv_ = new byte[iv.Length];
            Array.Copy(iv, iv_, 16);
            keys_ = keys.Skip(1).ToArray();
            tables_ = tables;
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


            int Size = BlockSize - BlockSize % TFIT_BLOCK_SIZE;

            byte[] Cur_iv = iv_;


            for (int i = StartPosition; i < StartPosition + Size; i += TFIT_BLOCK_SIZE)
            {
                byte[] bytes = new byte[TFIT_BLOCK_SIZE];
                byte[] Next_iv = new byte[TFIT_BLOCK_SIZE];

                Buffer.BlockCopy(input, i, Next_iv, 0, TFIT_BLOCK_SIZE);


                byte[] outbytes = new byte[TFIT_BLOCK_SIZE];

                Buffer.BlockCopy(input, i, bytes, 0, TFIT_BLOCK_SIZE);

                TFIT_DecryptBlock(bytes, outbytes, keys_, tables_);

                for (int j = 0; j < 16; j++)
                    input[i + j] = (byte)(outbytes[j] ^ Cur_iv[j]);

                Buffer.BlockCopy(Next_iv, 0, Cur_iv, 0, 16);

            }
            Buffer.BlockCopy(Cur_iv, 0, iv_, 0, 16);

            return input;
        }



        public static byte[] TFIT_DecryptBytes(uint[][] keys, uint[][][] tables, byte[] iv, byte[] input, int? start = null, int? lenght = null)
        {

            TfitCbcCipher tfit2CbcCipher = new TfitCbcCipher(keys, tables, iv);
            return tfit2CbcCipher.Decode(input, start, lenght);
        }




    }
}
