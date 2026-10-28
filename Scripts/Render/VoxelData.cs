using Godot;
using System;
using System.Text.Json;
using System.Text.Json.Serialization;

namespace BotanicGarden.Scripts.Render
{
    public class VoxelData
    {
        public static VoxelColor[] LoadColors()
        {
            using var file = Godot.FileAccess.Open("VoxelData/VoxelColors.json", Godot.FileAccess.ModeFlags.Read);
            if (file == null)
            {
                Godot.GD.PrintErr($"Nie można otworzyć pliku JSON: {Godot.FileAccess.GetOpenError()}");
                return System.Array.Empty<VoxelColor>();
            }

            var jsonText = file.GetAsText();
        
            var options = new JsonSerializerOptions { PropertyNameCaseInsensitive = true };
            var colors = JsonSerializer.Deserialize<VoxelColor[]>(jsonText, options);
            var result = new VoxelColor[ushort.MaxValue];

            foreach (var color in colors)
            {
                result[color.index] = color;
            }


            return result;
        }
    }

    public struct VoxelColor
    {
        [JsonInclude]
        public ushort index;
    
        [JsonInclude]
        public float R;
    
        [JsonInclude]
        public float G;
    
        [JsonInclude]
        public float B;
    }
}

