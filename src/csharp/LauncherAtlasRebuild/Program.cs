using System;
using System.IO;
using System.Linq;
using FreeMote;
using FreeMote.Psb;

internal static class Program
{
    // Usage: LauncherAtlasRebuild <raw-psb> <source-bin> <source-index> <key-prefix> <out-bin> <out-index>
    private static byte[] Pack(byte[] raw, string key)
    {
        using (var input = new MemoryStream(raw, false))
        using (var mdf = MPack.CompressPsbToMdfStream(input, false))
        using (var encrypted = PsbExtension.EncodeMdf(mdf, key, 64, true)) return encrypted.ToArray();
    }
    private static byte[] Unpack(byte[] shell, string key)
    {
        using (var input = new MemoryStream(shell, false))
        using (var decoded = PsbExtension.EncodeMdf(input, key, 64, true))
        using (var raw = MPack.MdfDecompressToStream(decoded)) return ((MemoryStream)raw).ToArray();
    }
    private static int Main(string[] a)
    {
        if (a.Length != 6) { Console.Error.WriteLine("Usage: LauncherAtlasRebuild <raw-psb> <source-bin> <source-index> <key-prefix> <out-bin> <out-index>"); return 2; }
        var key = a[3]; var raw = File.ReadAllBytes(a[0]);
        var mdf = Pack(raw, key + "txt_en.psb.m");
        if (!Unpack(mdf, key + "txt_en.psb.m").SequenceEqual(raw)) throw new InvalidDataException("English PSB MDF round-trip failed");
        var bin = File.ReadAllBytes(a[1]); var offset = (bin.Length + 0x7ff) & ~0x7ff;
        var newBin = new byte[offset + mdf.Length]; Buffer.BlockCopy(bin, 0, newBin, 0, bin.Length); Buffer.BlockCopy(mdf, 0, newBin, offset, mdf.Length);
        var indexRaw = Unpack(File.ReadAllBytes(a[2]), key + "alldata.psb.m");
        var psb = new PSB(new MemoryStream(indexRaw, false), false); var root = (PsbDictionary)psb.Root;
        var info = (PsbDictionary)root["file_info"]; var item = (PsbList)info["system/motion/txt_en.psb.m"];
        item[0] = new PsbNumber((long)offset); item[1] = new PsbNumber((long)mdf.Length); psb.Merge(true);
        var newIndex = Pack(psb.Build(), key + "alldata.psb.m");
        var verify = new PSB(new MemoryStream(Unpack(newIndex, key + "alldata.psb.m"), false), false);
        var vi = (PsbDictionary)((PsbDictionary)verify.Root)["file_info"]; var ve = (PsbList)vi["system/motion/txt_en.psb.m"];
        if (((PsbNumber)ve[0]).AsLong != offset || !Unpack(newBin.Skip(offset).Take(mdf.Length).ToArray(), key + "txt_en.psb.m").SequenceEqual(raw)) throw new InvalidDataException("Index/resource verification failed");
        File.WriteAllBytes(a[4], newBin); File.WriteAllBytes(a[5], newIndex);
        Console.WriteLine("Verified English atlas resource: offset=0x{0:X}, MDF={1}, raw PSB={2}", offset, mdf.Length, raw.Length); return 0;
    }
}
