using System;
using System.IO;
using Magic_RDR;
using Magic_RDR.Application;
using Magic_RDR.RPF;

internal static class Rsc85Type2Fixture
{
    private static int Main(string[] args)
    {
        if (args.Length != 2)
        {
            Console.Error.WriteLine("Rsc85Type2Fixture <output.rsc> <unpacked.bin>");
            return 2;
        }
        AppGlobals.SetPlatform(AppGlobals.PlatformEnum.Switch);
        byte[] unpacked = File.ReadAllBytes(args[1]);
        if (unpacked.Length != 4096)
            throw new InvalidDataException("Synthetic type-2 fixture expects exactly 4096 unpacked bytes.");

        ResourceUtils.FlagInfo flags = new ResourceUtils.FlagInfo();
        flags.RSC85_bResource = true;
        flags.RSC85_bUseExtendedSize = true;
        flags.RSC85_SetMemSizes(unpacked.Length, 0);
        flags.RSC85_ObjectStartPageSize = 4096;
        byte[] compressed = DataUtils.CompressZStandard(unpacked);
        byte[] encrypted = DataUtils.Encrypt(compressed, AppGlobals.EncryptionKey);
        byte[] result = new byte[16 + encrypted.Length];
        Buffer.BlockCopy(BitConverter.GetBytes(ResourceUtils.FlagInfo.RSC85Magic), 0, result, 0, 4);
        Buffer.BlockCopy(BitConverter.GetBytes(2), 0, result, 4, 4);
        Buffer.BlockCopy(BitConverter.GetBytes(flags.Flag1), 0, result, 8, 4);
        Buffer.BlockCopy(BitConverter.GetBytes(flags.Flag2), 0, result, 12, 4);
        Buffer.BlockCopy(encrypted, 0, result, 16, encrypted.Length);
        File.WriteAllBytes(args[0], result);
        return 0;
    }
}
