using Godot;

namespace BotanicGarden.WorldGen;

public class Model(Vector3I origin, Vector3I size, ushort[] data)
{
    public Vector3I origin = origin;
    public Vector3I size = size;
    public ushort[] data = data;

    public override string ToString()
    {
        return $"origin: {origin}\nsize{size}\ndata{string.Join(", ", data)}";
    }
}