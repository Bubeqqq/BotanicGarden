using System;
using Godot;

namespace BotanicGarden.Common.Settings;

public static class SettingsManager
{
    private const string _configPath = "user://settings.cfg";
    static readonly ConfigFile _cfg = new();

    public static void Startup()
    {
        Load();
        ApplySettings();
    }

    public static void Load() => _cfg.Load(_configPath);
    public static void Save() => _cfg.Save(_configPath);

    public static void ApplySettings()
    {
        ApplyBindings();
        ApplyAudio();
    }

    // Audio
    static readonly string AudioSection = "audio";
    public static double Volume {
        get => Mathf.Clamp((float)_cfg.GetValue(AudioSection, "volume", 0.5f), 0f, 1f);
        set {
            _cfg.SetValue(AudioSection, "volume", Mathf.Clamp(value, 0f, 1f));
            SettingsManager.ApplyAudio();
        }
    }

    public static void ApplyAudio()
    {
        int master = AudioServer.GetBusIndex("Master");
        AudioServer.SetBusVolumeDb(master, Mathf.LinearToDb((float)Volume));
    }


    // Input
    static readonly string InputSection = "input";
    public static void SetBinding(StringName action, InputEvent ev)
    {
        InputMap.ActionEraseEvents(action); // remove this line to allow multiple binds (I think?)
        InputMap.ActionAddEvent(action, ev);
        _cfg.SetValue(InputSection, action, InputMap.ActionGetEvents(action));
        Save();
    }

    public static void RemoveBinding(StringName action)
    {
        InputMap.ActionEraseEvents(action);
        _cfg.SetValue(InputSection, action, new Godot.Collections.Array<InputEvent>());
        Save();
    }

    public static void ApplyBindings()
    {
        if (!_cfg.HasSection(InputSection)) return;
        foreach (StringName action in _cfg.GetSectionKeys(InputSection))
        {
            if (!InputMap.HasAction(action)) continue;

            InputMap.ActionEraseEvents(action);
            foreach (InputEvent ev in _cfg.GetValue(InputSection, action).AsGodotArray<InputEvent>())
            {
                InputMap.ActionAddEvent(action, ev);
            }
        }
    }

    public static void ResetBindings()
    {
        _cfg.EraseSection(InputSection);
        InputMap.LoadFromProjectSettings();
        Save();
    }
}
