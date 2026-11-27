using Godot;
using System;
using System.Collections.Generic;
using System.Linq;
using System.Text.Json;
using BotanicGarden.Simulation;

namespace BotanicGarden.UI;

public readonly record struct SpeciesVisualInfo(string Name, Color Color);

public static class SpeciesMetadataLoader
{
    public static Dictionary<uint, SpeciesVisualInfo> Load(
        string voxelDataJsonPath = "res://voxel_data/voxel_data.json",
        string auxJsonPath = "res://voxel_data/voxel_editor_aux.json")
    {
        var result = new Dictionary<uint, SpeciesVisualInfo>();

        var voxelStructs = VoxelData.LoadStruct(voxelDataJsonPath);
        var voxelColors = VoxelData.LoadColors();

        if (voxelStructs.Length == 0 || !Godot.FileAccess.FileExists(auxJsonPath))
            return result;

        using var doc = JsonDocument.Parse(Godot.FileAccess.GetFileAsString(auxJsonPath));
        var root = doc.RootElement;

        var voxelNames = new Dictionary<int, string>();
        if (root.TryGetProperty("voxel_names", out var namesEl))
        {
            foreach (var prop in namesEl.EnumerateObject())
            {
                if (int.TryParse(prop.Name, out int idx))
                    voxelNames[idx] = prop.Value.GetString() ?? prop.Name;
            }
        }

        if (root.TryGetProperty("groups", out var groupsEl))
        {
            foreach (var groupProp in groupsEl.EnumerateObject())
            {
                string groupName = groupProp.Name;
                var indices = groupProp.Value.EnumerateArray().Select(e => e.GetInt32()).ToList();
                if (indices.Count == 0) continue;

                int repIdx = indices.FirstOrDefault(
                    idx => voxelNames.TryGetValue(idx, out var n) &&
                           (n.Contains("flower_center", StringComparison.OrdinalIgnoreCase) ||
                            n.Contains("flower_leaf", StringComparison.OrdinalIgnoreCase)),
                    indices[0]);

                Color color = Colors.LightGreen;
                if (repIdx >= 0 && repIdx < voxelColors.Length && voxelColors[repIdx].A > 0f)
                {
                    var c = voxelColors[repIdx];
                    color = new Color(c.R, c.G, c.B, c.A);
                }

                foreach (int idx in indices)
                {
                    if (idx >= 0 && idx < voxelStructs.Length)
                    {
                        uint speciesId = voxelStructs[idx].s1;
                        if (speciesId != 0)
                        {
                            result[speciesId] = new SpeciesVisualInfo(groupName, color);
                        }
                    }
                }
            }
        }

        return result;
    }

    public static SpeciesVisualInfo Resolve(Dictionary<uint, SpeciesVisualInfo> map, uint speciesId)
    {
        if (map.TryGetValue(speciesId, out var info))
            return info;

        float hue = (speciesId * 0.61803398875f) % 1.0f;
        return new SpeciesVisualInfo($"Gatunek #{speciesId}", Color.FromHsv(hue, 0.7f, 0.95f));
    }
}