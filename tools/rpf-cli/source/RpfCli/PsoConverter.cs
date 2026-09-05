using System;
using System.Collections.Generic;
using System.IO;
using RageLib.GTA5.PSOWrappers;
using RageLib.Hash;

internal static class PsoConverter
{
    private static readonly string[] LicensedListFiles =
    {
        "PsoTypeNames.txt",
        "PsoFieldNames.txt",
        "PsoEnumValues.txt",
        "PsoCommon.txt",
        "FileNames.txt",
        "PsoCollisions.txt",
    };

    // These names are the exact element contract read by games/rdr2/server.py.
    // They are case-sensitive because RDR2 PSO schema hashes are case-sensitive.
    private static readonly string[] ContractNames =
    {
        "ItemDatabaseParser",
        "catalog", "items", "item", "effectsids", "shopsinventories",
        "type", "requirementgroups", "count", "key", "category", "group",
        "tags", "effectids", "multiplicity", "quantity", "slotid",
        "acquirecosts", "sellprices", "ui", "description", "model",
        "textures", "id", "dict", "costtype", "unlocks",
        "durationcategory", "value", "percent", "time", "timeunits",
        "CWeaponInfoBlob", "CWeaponInfo", "CAmmoInfo", "Name", "AmmoInfo",
        "DamageFallOffInfo", "AccuracyInfo", "Distance", "Damage",
        "ProjectileFlags", "VfxWeaponShellInfoHashName",
    };

    public static void WriteXml(string outputPath, byte[] bytes)
    {
        using var input = new MemoryStream(bytes, false);
        var value = new PsoReader().Read(input);
        var exporter = new PsoXmlExporter
        {
            HashMapping = LoadHashMapping(),
        };
        using var output = new FileStream(outputPath, FileMode.Create, FileAccess.Write, FileShare.None);
        exporter.Export(value, output);
    }

    private static Dictionary<int, string> LoadHashMapping()
    {
        var mapping = new Dictionary<int, string>();
        string listDirectory = Path.Combine(AppContext.BaseDirectory, "pso-names");
        foreach (string fileName in LicensedListFiles)
        {
            string path = Path.Combine(listDirectory, fileName);
            if (!File.Exists(path))
                throw new FileNotFoundException("Bundled PSO name list is missing.", path);
            foreach (string line in File.ReadLines(path))
            {
                string name = line.Trim();
                if (name.Length == 0) continue;
                int hash = unchecked((int)Jenkins.Hash(name));
                if (!mapping.ContainsKey(hash)) mapping.Add(hash, name);
            }
        }

        foreach (string name in ContractNames)
            mapping[unchecked((int)Jenkins.Hash(name))] = name;
        return mapping;
    }
}
