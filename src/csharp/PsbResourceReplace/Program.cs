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

    private static PsbList Entry(PSB index, string name)
    {
        var root = (PsbDictionary)index.Root;
        var info = (PsbDictionary)root["file_info"];
        return (PsbList)info[name];
    }

    private static byte[] ReadResource(byte[] bin, PSB index, string prefix, string name)
    {
        var entry = Entry(index, name);
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
        // extract <source-bin> <source-index> <key-prefix> <resource-name> <output-raw>
        // replace <new-raw> <source-bin> <source-index> <key-prefix> <resource-name> <out-bin> <out-index>
        if (!((args.Length == 6 && args[0] == "extract") || (args.Length == 8 && args[0] == "replace")))
        {
            Console.Error.WriteLine("Usage: extract <source-bin> <source-index> <key-prefix> <resource-name> <output-raw>");
            Console.Error.WriteLine("   or: replace <new-raw> <source-bin> <source-index> <key-prefix> <resource-name> <out-bin> <out-index>");
            return 2;
        }

        var replacing = args[0] == "replace";
        var bin = File.ReadAllBytes(args[replacing ? 2 : 1]);
        var prefix = args[replacing ? 4 : 3];
        var name = args[replacing ? 5 : 4];
        var indexRaw = Unpack(File.ReadAllBytes(args[replacing ? 3 : 2]), prefix + "alldata.psb.m");
        var index = new PSB(new MemoryStream(indexRaw, false), false);
        var oldRaw = ReadResource(bin, index, prefix, name);
        if (!replacing)
        {
            File.WriteAllBytes(args[5], oldRaw);
            Console.WriteLine("Extracted {0}: {1} bytes", name, oldRaw.Length);
            return 0;
        }

        var newRaw = File.ReadAllBytes(args[1]);
        var packed = Pack(newRaw, prefix + name.Split('/').Last());
        if (!Unpack(packed, prefix + name.Split('/').Last()).SequenceEqual(newRaw))
            throw new InvalidDataException("Resource MDF round-trip failed");
        var offset = (bin.Length + 0x7ff) & ~0x7ff;
        var newBin = new byte[offset + packed.Length];
        Buffer.BlockCopy(bin, 0, newBin, 0, bin.Length);
        Buffer.BlockCopy(packed, 0, newBin, offset, packed.Length);
        var entry = Entry(index, name);
        entry[0] = new PsbNumber((long)offset);
        entry[1] = new PsbNumber((long)packed.Length);
        index.Merge(true);
        var newIndex = Pack(index.Build(), prefix + "alldata.psb.m");
        var check = new PSB(new MemoryStream(Unpack(newIndex, prefix + "alldata.psb.m"), false), false);
        if (!ReadResource(newBin, check, prefix, name).SequenceEqual(newRaw))
            throw new InvalidDataException("Rebuilt resource verification failed");
        File.WriteAllBytes(args[6], newBin);
        File.WriteAllBytes(args[7], newIndex);
        Console.WriteLine("Replaced {0}: old={1}, new={2}, offset=0x{3:X}, MDF={4}",
            name, oldRaw.Length, newRaw.Length, offset, packed.Length);
        return 0;
    }
}
