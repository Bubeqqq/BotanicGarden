using Godot;

namespace BotanicGarden.Common.Settings;

public partial class SettingsBoot : Node
{
    public override void _EnterTree()
    {
        Settings.Startup();
    }
}