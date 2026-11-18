using Godot;

namespace BotanicGarden.Common.Settings;

public partial class SettingsBot : Node
{
    public override void _EnterTree()
    {
        Settings.Startup();
    }
}