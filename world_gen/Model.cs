using Godot;

namespace BotanicGarden.WorldGen;

public struct Model
{
    // public int origin_x;
    // public int origin_z;
    // public int origin_y;
    public Vector3I origin;
    public Vector3I size;
    public ushort [] data;
}