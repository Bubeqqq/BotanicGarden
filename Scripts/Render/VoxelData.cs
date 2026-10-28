using Godot;
using System;
using System.Text.Json;
using System.Text.Json.Serialization;

/*
    Indexes divided by types of voxels
 
    Type 0: 0-2047       - Special voxels (air, ...)
    Type 1: 2048-4095    - Static blocks
    Type 2: 4096-6143    - Flowers
    Type 3: 6144-8191    -
    Type 4: 8192-10239   -
    Type 5: 10240-12287  -
    Type 6: 12288-14335  -
    Type 7: 14336-16383  -
    Type 8: 16384-18431  -
    Type 9: 18432-20479  -
    Type 10: 20480-22527 -
    Type 11: 22528-24575 -
    Type 12: 24576-26623 -
    Type 13: 26624-28671 -
    Type 14: 28672-30719 -
    Type 15: 30720-32767 -
    Type 16: 32768-34815 -
    Type 17: 34816-36863 -
    Type 18: 36864-38911 -
    Type 19: 38912-40959 -
    Type 20: 40960-43007 -
    Type 21: 43008-45055 -
    Type 22: 45056-47103 -
    Type 23: 47104-49151 -
    Type 24: 49152-51199 -
    Type 25: 51200-53247 -
    Type 26: 53248-55295 -
    Type 27: 55296-57343 -
    Type 28: 57344-59391 -
    Type 29: 59392-61439 -
    Type 30: 61440-63487 -
    Type 31: 63488-65535 -
 */

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

