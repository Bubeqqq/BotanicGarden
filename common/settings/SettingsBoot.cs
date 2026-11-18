using Godot;

namespace BotanicGarden.Common.Settings;

public partial class SettingsBoot : Node
{
    public override void _EnterTree()
    {
        SettingsManager.Startup();
        // SettingsManager.SetBinding("move_down", new InputEventKey { Keycode = Key.Ctrl });
        // SettingsManager.SetBinding("sprint", new InputEventKey { Keycode = Key.Shift });
    }
}