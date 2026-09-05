namespace RDR2_RPF_Tool.Core
{
    public interface ICipher
    {
        byte[] Decode(byte[] input, int? start = null, int? lenght = null);
    }
}
