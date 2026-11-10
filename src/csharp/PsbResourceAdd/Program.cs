using System;
using System.IO;
using System.Linq;
using FreeMote;
using FreeMote.Psb;

internal static class Program
{
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

    private static PsbDictionary FileInfo(PSB index) => (PsbDictionary)((PsbDictionary)index.Root)["file_info"];

    private static byte[] ReadResource(byte[] bin, PSB index, string prefix, string name)
    {
        var entry = (PsbList)FileInfo(index)[name];
        var offset = ((PsbNumber)entry[0]).AsLong;
        var length = ((PsbNumber)entry[1]).AsLong;
        if (offset < 0 || length < 0 || offset + length > bin.LongLength || length > int.MaxValue)
            throw new InvalidDataException("Invalid resource bounds: " + name);
        var shell = new byte[(int)length];
        Buffer.BlockCopy(bin, (int)offset, shell, 0, shell.Length);
        return Unpack(shell, prefix + name.Split('/').Last());
    }

    private static int Main(string[] args)
    {
        if (args.Length != 8 || args[0] != "add")
        {
            Console.Error.WriteLine("Usage: add <raw-psb> <source-bin> <source-index> <key-prefix> <resource-name> <out-bin> <out-index>");
            return 2;
        }

        var raw = File.ReadAllBytes(args[1]);
        var bin = File.ReadAllBytes(args[2]);
        var prefix = args[4];
        var name = args[5];
        var indexRaw = Unpack(File.ReadAllBytes(args[3]), prefix + "alldata.psb.m");
        var index = new PSB(new MemoryStream(indexRaw, false), false);
        var info = FileInfo(index);
        if (info.ContainsKey(name)) throw new InvalidOperationException("Resource already exists: " + name);

        var packed = Pack(raw, prefix + name.Split('/').Last());
        if (!Unpack(packed, prefix + name.Split('/').Last()).SequenceEqual(raw))
            throw new InvalidDataException("Resource MDF round-trip failed");

        var offset = (bin.Length + 0x7ff) & ~0x7ff;
        var newBin = new byte[offset + packed.Length];
        Buffer.BlockCopy(bin, 0, newBin, 0, bin.Length);
        Buffer.BlockCopy(packed, 0, newBin, offset, packed.Length);
        info[name] = new PsbList { new PsbNumber((long)offset), new PsbNumber((long)packed.Length) };
        index.Merge(true);
        var newIndex = Pack(index.Build(), prefix + "alldata.psb.m");
        var check = new PSB(new MemoryStream(Unpack(newIndex, prefix + "alldata.psb.m"), false), false);
        if (!ReadResource(newBin, check, prefix, name).SequenceEqual(raw))
            throw new InvalidDataException("Added resource verification failed");

        File.WriteAllBytes(args[6], newBin);
        File.WriteAllBytes(args[7], newIndex);
        Console.WriteLine("Added {0}: raw={1}, offset=0x{2:X}, MDF={3}", name, raw.Length, offset, packed.Length);
        return 0;
    }
}
